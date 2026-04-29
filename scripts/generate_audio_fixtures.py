from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "output" / "audio_fixtures"


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples.astype(np.float32, copy=False), -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm16.tobytes())


def sine(sample_rate: int, duration_sec: float, hz: float, amplitude: float) -> np.ndarray:
    count = max(1, int(sample_rate * duration_sec))
    t = np.arange(count, dtype=np.float32) / float(sample_rate)
    return (amplitude * np.sin(2.0 * math.pi * hz * t)).astype(np.float32)


def fade_edges(samples: np.ndarray, sample_rate: int, fade_ms: int = 8) -> np.ndarray:
    result = np.array(samples, dtype=np.float32, copy=True)
    fade = min(result.size // 2, max(1, int(sample_rate * fade_ms / 1000)))
    envelope = np.linspace(0.0, 1.0, fade, dtype=np.float32)
    result[:fade] *= envelope
    result[-fade:] *= envelope[::-1]
    return result


def make_fixtures(sample_rate: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(20260429)

    low_volume = fade_edges(sine(sample_rate, 2.0, 440.0, 0.018), sample_rate)

    clipped_burst = sine(sample_rate, 2.0, 330.0, 0.55)
    start = int(sample_rate * 0.65)
    end = start + int(sample_rate * 0.28)
    clipped_burst[start:end] *= 2.8
    clipped_burst = fade_edges(clipped_burst, sample_rate)

    noisy_voice = sine(sample_rate, 2.5, 220.0, 0.16)
    noisy_voice += sine(sample_rate, 2.5, 660.0, 0.05)
    noisy_voice += rng.normal(0.0, 0.08, noisy_voice.size).astype(np.float32)
    noisy_voice = fade_edges(noisy_voice, sample_rate)

    short_onset = np.zeros(int(sample_rate * 1.4), dtype=np.float32)
    burst = fade_edges(sine(sample_rate, 0.22, 510.0, 0.34), sample_rate, fade_ms=3)
    short_onset[int(sample_rate * 0.42) : int(sample_rate * 0.42) + burst.size] = burst

    long_silence = np.zeros(int(sample_rate * 3.0), dtype=np.float32)
    phrase = fade_edges(sine(sample_rate, 0.55, 390.0, 0.25), sample_rate)
    long_silence[int(sample_rate * 1.85) : int(sample_rate * 1.85) + phrase.size] = phrase

    return {
        "low_volume_tone.wav": low_volume,
        "clipped_burst.wav": clipped_burst,
        "noisy_voice_like.wav": noisy_voice,
        "short_onset.wav": short_onset,
        "long_silence_then_phrase.wav": long_silence,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic WAV fixtures for Nova DSP regression checks.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-rate", type=int, default=16000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample_rate = max(1, args.sample_rate)
    fixtures = make_fixtures(sample_rate)
    for name, samples in fixtures.items():
        write_wav(args.output_dir / name, samples, sample_rate)
    for path in sorted(args.output_dir.glob("*.wav")):
        print(path)


if __name__ == "__main__":
    main()
