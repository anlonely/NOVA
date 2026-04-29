from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ast_bridge import apply_agc, apply_playback_limiter, samples_to_dbfs, spectral_denoise


def read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if sample_width == 1:
        raw = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
        samples = (raw - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 3:
        triples = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
        values = np.where(values & 0x800000, values - 0x1000000, values)
        samples = values.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width: {sample_width}")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32, copy=False), sample_rate


def synthetic_sample(sample_rate: int, duration_sec: float) -> np.ndarray:
    count = max(1, int(sample_rate * duration_sec))
    t = np.arange(count, dtype=np.float32) / float(sample_rate)
    tone = 0.72 * np.sin(2.0 * math.pi * 440.0 * t)
    overload_start = count // 3
    overload_end = min(count, overload_start + max(1, sample_rate // 5))
    tone[overload_start:overload_end] *= 1.85
    silence_start = (count * 2) // 3
    tone[silence_start:] *= 0.02
    return tone.astype(np.float32, copy=False)


def chunk_view(samples: np.ndarray, sample_rate: int, chunk_ms: int) -> list[np.ndarray]:
    chunk_size = max(1, int(sample_rate * max(1, chunk_ms) / 1000))
    return [samples[index : index + chunk_size] for index in range(0, samples.size, chunk_size)]


def count_clipped(samples: np.ndarray, threshold: float = 0.999) -> int:
    if samples.size == 0:
        return 0
    return int(np.count_nonzero(np.abs(samples) >= threshold))


def peak_dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -96.0
    peak = float(np.max(np.abs(samples)))
    if peak <= 1e-6:
        return -96.0
    return round(20.0 * math.log10(max(peak, 1e-6)), 1)


def analyze(samples: np.ndarray, sample_rate: int, args: argparse.Namespace, source: str) -> dict[str, Any]:
    input_samples = np.nan_to_num(samples.astype(np.float32, copy=False), nan=0.0, posinf=1.0, neginf=-1.0)
    processed = input_samples
    noise_profile = None
    if args.denoise:
        denoised: list[np.ndarray] = []
        for chunk in chunk_view(processed, sample_rate, args.chunk_ms):
            speech = samples_to_dbfs(chunk) >= args.noise_gate_db
            clean, noise_profile = spectral_denoise(chunk, noise_profile, args.denoise_strength, learn_noise=not speech)
            denoised.append(clean)
        processed = np.concatenate(denoised) if denoised else processed

    agc_gain = 1.0
    if args.agc:
        agc_chunks: list[np.ndarray] = []
        for chunk in chunk_view(processed, sample_rate, args.chunk_ms):
            adjusted, agc_gain = apply_agc(chunk, args.agc_target_dbfs, args.max_agc_gain, agc_gain)
            agc_chunks.append(adjusted)
        processed = np.concatenate(agc_chunks) if agc_chunks else processed

    limited, limiter_engaged, reduction_db, _ = apply_playback_limiter(processed)
    chunks = chunk_view(processed, sample_rate, args.chunk_ms)
    chunk_levels = [samples_to_dbfs(chunk) for chunk in chunks]
    speech_chunks = sum(1 for level in chunk_levels if level >= args.noise_gate_db)
    clipped_before = count_clipped(processed)
    clipped_after = count_clipped(limited)

    duration_sec = round(float(input_samples.size) / float(sample_rate), 3) if sample_rate else 0.0
    return {
        "ok": True,
        "source": source,
        "sampleRate": sample_rate,
        "durationSec": duration_sec,
        "chunkMs": args.chunk_ms,
        "input": {
            "peakDbfs": peak_dbfs(input_samples),
            "rmsDbfs": samples_to_dbfs(input_samples),
            "clippedSamples": count_clipped(input_samples),
        },
        "processed": {
            "peakDbfs": peak_dbfs(processed),
            "rmsDbfs": samples_to_dbfs(processed),
            "clippedSamples": clipped_before,
            "agcEnabled": bool(args.agc),
            "agcFinalGain": round(float(agc_gain), 3),
            "denoiseEnabled": bool(args.denoise),
        },
        "vad": {
            "noiseGateDb": args.noise_gate_db,
            "chunks": len(chunks),
            "speechChunks": speech_chunks,
            "silentChunks": max(0, len(chunks) - speech_chunks),
            "speechRatio": round(speech_chunks / max(1, len(chunks)), 3),
        },
        "limiter": {
            "engaged": bool(limiter_engaged),
            "reductionDb": reduction_db,
            "peakBeforeDbfs": peak_dbfs(processed),
            "peakAfterDbfs": peak_dbfs(limited),
            "clippedBefore": clipped_before,
            "clippedAfter": clipped_after,
        },
    }


def collect_inputs(path: Path | None) -> list[Path]:
    if path is None:
        return []
    if path.is_dir():
        return sorted(item for item in path.rglob("*.wav") if item.is_file())
    return [path]


def apply_thresholds(results: list[dict[str, Any]], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    for result in results:
        source = str(result.get("source", "unknown"))
        limiter = result.get("limiter", {})
        clipped_after = int(limiter.get("clippedAfter") or 0)
        peak_after = float(limiter.get("peakAfterDbfs") or -96.0)
        if args.max_clipped_after is not None and clipped_after > args.max_clipped_after:
            failures.append(f"{source}: clippedAfter {clipped_after} > {args.max_clipped_after}")
        if args.max_peak_after_dbfs is not None and peak_after > args.max_peak_after_dbfs:
            failures.append(f"{source}: peakAfterDbfs {peak_after} > {args.max_peak_after_dbfs}")
    return failures


def summarize(results: list[dict[str, Any]], failures: list[str]) -> dict[str, Any]:
    limiter_events = sum(1 for item in results if item.get("limiter", {}).get("engaged"))
    max_peak_after = max((float(item.get("limiter", {}).get("peakAfterDbfs") or -96.0) for item in results), default=-96.0)
    clipped_after = sum(int(item.get("limiter", {}).get("clippedAfter") or 0) for item in results)
    return {
        "ok": not failures,
        "files": len(results),
        "limiterEngagedFiles": limiter_events,
        "maxPeakAfterDbfs": max_peak_after,
        "totalClippedAfter": clipped_after,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Nova audio DSP and playback limiter behavior.")
    parser.add_argument("--input", type=Path, help="Optional WAV file or directory. If omitted, a synthetic stress sample is used.")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Synthetic sample rate.")
    parser.add_argument("--duration-sec", type=float, default=2.0, help="Synthetic sample duration.")
    parser.add_argument("--chunk-ms", type=int, default=20, help="Analysis chunk size.")
    parser.add_argument("--noise-gate-db", type=float, default=-46.0, help="Speech gate threshold.")
    parser.add_argument("--agc", action="store_true", help="Run the AGC stage before limiter analysis.")
    parser.add_argument("--agc-target-dbfs", type=float, default=-18.0)
    parser.add_argument("--max-agc-gain", type=float, default=6.0)
    parser.add_argument("--denoise", action="store_true", help="Run spectral denoise before limiter analysis.")
    parser.add_argument("--denoise-strength", type=float, default=0.22)
    parser.add_argument("--max-clipped-after", type=int, help="Fail when limiter output has more clipped samples than this.")
    parser.add_argument("--max-peak-after-dbfs", type=float, help="Fail when limiter output peak is above this dBFS value.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = collect_inputs(args.input)
    if args.input and not inputs:
        raise SystemExit(f"no WAV files found: {args.input}")
    if not inputs:
        sample_rate = max(1, args.sample_rate)
        samples = synthetic_sample(sample_rate, max(0.1, args.duration_sec))
        results = [analyze(samples, sample_rate, args, "synthetic")]
    else:
        results = []
        for path in inputs:
            samples, sample_rate = read_wav_mono(path)
            results.append(analyze(samples, sample_rate, args, str(path)))

    failures = apply_thresholds(results, args)
    if args.input and len(results) != 1:
        payload: dict[str, Any] = {"summary": summarize(results, failures), "results": results}
    else:
        payload = dict(results[0])
        payload["thresholds"] = {"ok": not failures, "failures": failures}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
