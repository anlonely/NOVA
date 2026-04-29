from __future__ import annotations

import argparse
import json
import math
import queue
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from smoke_native_audio_core import DEFAULT_BINARY, ServeSession, find_first_device, run_json


DEFAULT_REPORT_PATH = ROOT / "output" / "stress_native_audio_core_report.json"
PROFILE_DURATIONS = {
    "quick": 4.0,
    "preflight": 60.0,
    "soak-2h": 7200.0,
    "soak-8h": 28800.0,
}
PROFILE_REPORT_INTERVALS = {
    "quick": 1.0,
    "preflight": 10.0,
    "soak-2h": 60.0,
    "soak-8h": 120.0,
}


def make_tone_chunk(sample_rate: int, chunk_ms: int, phase: float, hz: float = 440.0, amplitude: float = 0.0) -> tuple[bytes, float]:
    frames = max(1, int(sample_rate * max(1, chunk_ms) / 1000))
    step = 2.0 * math.pi * hz / float(sample_rate)
    angles = phase + np.arange(frames, dtype=np.float32) * step
    samples = max(0.0, min(float(amplitude), 0.25)) * np.sin(angles)
    next_phase = float((phase + frames * step) % (2.0 * math.pi))
    pcm16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    return pcm16, next_phase


def drain_events(session: ServeSession, counters: dict[str, Any]) -> None:
    while True:
        try:
            event = session.events.get_nowait()
        except queue.Empty:
            return
        name = str(event.get("event") or "unknown")
        counters["events"][name] = counters["events"].get(name, 0) + 1
        if name == "playback_queued":
            counters["playbackQueued"] += 1
        elif name == "audio_chunk":
            counters["captureChunks"] += 1
            counters["maxDroppedSilentChunks"] = max(
                counters["maxDroppedSilentChunks"],
                int(event.get("dropped_silent_chunks") or 0),
            )
            counters["maxCaptureQueueDepth"] = max(counters["maxCaptureQueueDepth"], int(event.get("queue_depth") or 0))
        elif name == "metrics":
            counters["captureMetrics"] += 1
            counters["maxDroppedSilentChunks"] = max(
                counters["maxDroppedSilentChunks"],
                int(event.get("dropped_silent_chunks") or 0),
            )
            counters["maxCaptureQueueDepth"] = max(counters["maxCaptureQueueDepth"], int(event.get("queue_depth") or 0))
        elif name == "devices_changed":
            counters["devicesChanged"] += 1
        elif name == "error":
            counters["errors"].append(event)


def process_rss_kb(pid: int) -> int | None:
    if pid <= 0:
        return None
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except Exception:
        return None
    text = result.stdout.strip()
    if not text:
        return None
    try:
        return int(text.splitlines()[-1].strip())
    except ValueError:
        return None


def make_sample(session: ServeSession, counters: dict[str, Any], chunks_sent: int, started_at: float) -> dict[str, Any]:
    rss_kb = process_rss_kb(session.process.pid)
    playback_queued = int(counters["playbackQueued"])
    return {
        "elapsedSec": round(time.time() - started_at, 3),
        "chunksSent": chunks_sent,
        "playbackQueued": playback_queued,
        "ackBacklog": max(0, chunks_sent - playback_queued),
        "rssKb": rss_kb,
        "devicesChanged": int(counters["devicesChanged"]),
        "errorCount": len(counters["errors"]),
        "processAlive": session.process.poll() is None,
    }


def threshold_failures(samples: list[dict[str, Any]], counters: dict[str, Any], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    if counters["errors"]:
        failures.append(f"native errors observed: {len(counters['errors'])}")
    if samples:
        max_backlog = max(int(item.get("ackBacklog") or 0) for item in samples)
        if args.max_ack_backlog is not None and max_backlog > args.max_ack_backlog:
            failures.append(f"max ack backlog {max_backlog} > {args.max_ack_backlog}")
        rss_values = [int(item["rssKb"]) for item in samples if item.get("rssKb") is not None]
        if len(rss_values) >= 2 and args.max_rss_growth_kb is not None:
            growth = max(rss_values) - rss_values[0]
            if growth > args.max_rss_growth_kb:
                failures.append(f"RSS growth {growth} KiB > {args.max_rss_growth_kb} KiB")
        if not all(bool(item.get("processAlive")) for item in samples):
            failures.append("native service exited during stress run")
    return failures


def run_stress(args: argparse.Namespace) -> dict[str, Any]:
    health = run_json(args.binary, "health")
    if not health.get("ok"):
        raise RuntimeError(f"native core health failed: {health}")
    snapshot = run_json(args.binary, "list-devices")
    output_device_id = find_first_device(snapshot, "output", args.playback_device)
    channels = [f"stress-{index + 1}" for index in range(max(1, args.channels))]
    counters: dict[str, Any] = {
        "events": {},
        "errors": [],
        "playbackQueued": 0,
        "captureChunks": 0,
        "captureMetrics": 0,
        "maxDroppedSilentChunks": 0,
        "maxCaptureQueueDepth": 0,
        "devicesChanged": 0,
    }
    chunks_sent = 0
    phase = 0.0
    started_at = time.time()
    samples: list[dict[str, Any]] = []

    session = ServeSession(args.binary)
    try:
        session.wait_for(lambda event: event.get("event") == "ready", timeout=3)
        input_device_id = ""
        if args.with_capture:
            input_device_id = find_first_device(snapshot, "input", args.capture_device)
            session.send(
                {
                    "cmd": "start-capture",
                    "channel": "stress-capture",
                    "device_id": input_device_id,
                    "sample_rate": 16000,
                    "chunk_ms": args.chunk_ms,
                    "noise_gate_db": args.noise_gate_db,
                    "silence_hold_ms": 120,
                    "pre_roll_ms": 80,
                    "input_gain": 1.0,
                    "enable_agc": False,
                    "resampler_quality": "sinc-lite",
                    "vad_mode": "gate",
                    "enable_noise_floor": False,
                    "adaptive_chunking": True,
                }
            )
            session.wait_for(lambda event: event.get("event") == "capture_started", timeout=5)
            session.wait_for(lambda event: event.get("event") == "ok" and event.get("cmd") == "start-capture", timeout=5)
        for channel in channels:
            session.send(
                {
                    "cmd": "start-playback",
                    "channel": channel,
                    "device_id": output_device_id,
                    "sample_rate": args.sample_rate,
                    "chunk_ms": args.chunk_ms,
                }
            )
            session.wait_for(
                lambda event, expected=channel: event.get("event") == "playback_started" and event.get("channel") == expected,
                timeout=5,
            )
            session.wait_for(
                lambda event, expected=channel: event.get("event") == "ok"
                and event.get("cmd") == "start-playback"
                and event.get("channel") == expected,
                timeout=5,
            )

        deadline = time.time() + max(0.1, args.duration_sec)
        next_report = time.time() + max(1.0, args.report_interval_sec)
        samples.append(make_sample(session, counters, chunks_sent, started_at))
        while time.time() < deadline:
            chunk, phase = make_tone_chunk(args.sample_rate, args.chunk_ms, phase, amplitude=args.tone_amplitude)
            for channel in channels:
                session.send_playback_binary(channel, args.sample_rate, chunk)
                chunks_sent += 1
            drain_events(session, counters)
            if time.time() >= next_report:
                next_report = time.time() + max(1.0, args.report_interval_sec)
                samples.append(make_sample(session, counters, chunks_sent, started_at))
                if args.verbose:
                    print(json.dumps(samples[-1], ensure_ascii=False), flush=True)
            time.sleep(max(0.001, args.chunk_ms / 1000.0))

        time.sleep(0.05)
        drain_events(session, counters)
        if args.with_capture:
            session.send({"cmd": "stop-capture", "channel": "stress-capture"})
            session.wait_for(lambda event: event.get("event") == "ok" and event.get("cmd") == "stop-capture", timeout=5)
            drain_events(session, counters)
        samples.append(make_sample(session, counters, chunks_sent, started_at))
        session.send({"cmd": "stop-playback"})
        session.wait_for(lambda event: event.get("event") == "ok" and event.get("cmd") == "stop-playback", timeout=5)
        drain_events(session, counters)
    finally:
        session.shutdown()

    elapsed = round(time.time() - started_at, 3)
    recent_stderr = session.recent_stderr()
    failures = threshold_failures(samples, counters, args)
    rss_values = [int(item["rssKb"]) for item in samples if item.get("rssKb") is not None]
    max_backlog = max((int(item.get("ackBacklog") or 0) for item in samples), default=0)
    return {
        "ok": not failures,
        "profile": args.profile,
        "argv": sys.argv[1:],
        "backend": health.get("backend"),
        "deviceCount": len(snapshot.get("devices", [])),
        "playbackDevice": output_device_id,
        "captureDevice": input_device_id,
        "channels": len(channels),
        "durationSec": elapsed,
        "sampleRate": args.sample_rate,
        "chunkMs": args.chunk_ms,
        "chunksSent": chunks_sent,
        "playbackQueued": counters["playbackQueued"],
        "captureChunks": counters["captureChunks"],
        "captureMetrics": counters["captureMetrics"],
        "maxDroppedSilentChunks": counters["maxDroppedSilentChunks"],
        "maxCaptureQueueDepth": counters["maxCaptureQueueDepth"],
        "maxAckBacklog": max_backlog,
        "rssStartKb": rss_values[0] if rss_values else None,
        "rssMaxKb": max(rss_values) if rss_values else None,
        "rssGrowthKb": (max(rss_values) - rss_values[0]) if len(rss_values) >= 2 else None,
        "devicesChanged": counters["devicesChanged"],
        "events": counters["events"],
        "errors": counters["errors"],
        "failures": failures,
        "samples": samples,
        "stderr": recent_stderr,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stress-test the NOVA native audio service for long-running playback stability.")
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--profile", choices=sorted(PROFILE_DURATIONS), default="quick", help="Preset duration/report interval for common stress runs.")
    parser.add_argument("--playback-device", default="")
    parser.add_argument("--capture-device", default="")
    parser.add_argument("--with-capture", action="store_true", help="Run a native capture session during the playback stress.")
    parser.add_argument("--duration-sec", type=float)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--chunk-ms", type=int, default=20)
    parser.add_argument("--tone-amplitude", type=float, default=0.0, help="Playback test tone amplitude. Defaults to silence to avoid audible noise.")
    parser.add_argument("--noise-gate-db", type=float, default=-80.0)
    parser.add_argument("--report-interval-sec", type=float)
    parser.add_argument("--report-json", type=Path, help=f"Write the final stress report JSON. Default: {DEFAULT_REPORT_PATH}")
    parser.add_argument("--max-ack-backlog", type=int, default=64, help="Fail if sent playback chunks exceed queued acknowledgements by more than this.")
    parser.add_argument("--max-rss-growth-kb", type=int, help="Fail if native process RSS grows more than this across samples.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def apply_profile_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if args.duration_sec is None:
        args.duration_sec = PROFILE_DURATIONS[args.profile]
    if args.report_interval_sec is None:
        args.report_interval_sec = PROFILE_REPORT_INTERVALS[args.profile]
    return args


def main() -> int:
    args = apply_profile_defaults(parse_args())
    if not args.binary.exists():
        raise FileNotFoundError(f"native audio core binary not found: {args.binary}")
    result = run_stress(args)
    report_path = args.report_json or DEFAULT_REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
