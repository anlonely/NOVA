from __future__ import annotations

import argparse
import base64
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_BINARY = ROOT / "native_audio_core" / "target" / "release" / (
    "nova-audio-core.exe" if sys.platform.startswith("win") else "nova-audio-core"
)


class ServeSession:
    def __init__(self, binary: Path) -> None:
        self.process = subprocess.Popen(
            [str(binary), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stderr: queue.Queue[str] = queue.Queue()
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def send(self, payload: dict[str, Any]) -> None:
        if not self.process.stdin:
            raise RuntimeError("native core stdin is closed")
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def send_playback_binary(self, channel: str, sample_rate: int, pcm16: bytes) -> None:
        if not self.process.stdin:
            raise RuntimeError("native core stdin is closed")
        header = {
            "cmd": "playback-chunk-binary",
            "channel": channel,
            "sample_rate": sample_rate,
            "byte_len": len(pcm16),
        }
        self.process.stdin.buffer.write((json.dumps(header, ensure_ascii=False) + "\n").encode("utf-8"))
        self.process.stdin.buffer.write(pcm16)
        self.process.stdin.buffer.flush()

    def wait_for(self, predicate: Callable[[dict[str, Any]], bool], timeout: float) -> dict[str, Any]:
        deadline = time.time() + timeout
        last_event: dict[str, Any] | None = None
        while time.time() < deadline:
            try:
                event = self.events.get(timeout=min(0.2, max(0.01, deadline - time.time())))
            except queue.Empty:
                continue
            last_event = event
            if predicate(event):
                return event
            if event.get("event") == "error":
                raise RuntimeError(str(event.get("message") or event))
        raise TimeoutError(f"timed out waiting for native event; last={last_event}; stderr={self.recent_stderr()}")

    def shutdown(self) -> None:
        if self.process.poll() is None:
            try:
                self.send({"cmd": "shutdown"})
            except Exception:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def recent_stderr(self) -> str:
        lines: list[str] = []
        while True:
            try:
                lines.append(self.stderr.get_nowait())
            except queue.Empty:
                break
        return "\n".join(lines[-10:])

    def _read_stdout(self) -> None:
        if not self.process.stdout:
            return
        for line in self.process.stdout:
            try:
                self.events.put(json.loads(line))
            except json.JSONDecodeError:
                self.events.put({"event": "error", "message": f"invalid JSON: {line.strip()}"})

    def _read_stderr(self) -> None:
        if not self.process.stderr:
            return
        for line in self.process.stderr:
            self.stderr.put(line.rstrip())


def run_json(binary: Path, command: str) -> dict[str, Any]:
    result = subprocess.run(
        [str(binary), command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=8,
        check=True,
    )
    return json.loads(result.stdout or "{}")


def find_first_device(snapshot: dict[str, Any], kind: str, requested: str) -> str:
    devices = [item for item in snapshot.get("devices", []) if item.get("kind") == kind]
    if requested:
        for item in devices:
            if requested in {str(item.get("id", "")), str(item.get("name", ""))}:
                return str(item.get("id", ""))
        raise RuntimeError(f"{kind} device not found: {requested}")
    if not devices:
        raise RuntimeError(f"no {kind} devices reported by native core")
    return str(devices[0].get("id", ""))


def smoke_playback(binary: Path, output_device_id: str, channel_count: int = 1, binary_audio: bool = False) -> None:
    session = ServeSession(binary)
    try:
        session.wait_for(lambda event: event.get("event") == "ready", timeout=3)
        silence_bytes = bytes(960)
        silence_base64 = base64.b64encode(silence_bytes).decode("ascii")
        channels = [f"smoke-{index + 1}" for index in range(max(1, channel_count))]
        for channel in channels:
            session.send(
                {
                    "cmd": "start-playback",
                    "channel": channel,
                    "device_id": output_device_id,
                    "sample_rate": 24000,
                    "chunk_ms": 20,
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
        for channel in channels:
            if binary_audio:
                session.send_playback_binary(channel, 24000, silence_bytes)
                expected_cmd = "playback-chunk-binary"
            else:
                session.send({"cmd": "playback-chunk", "channel": channel, "sample_rate": 24000, "data": silence_base64})
                expected_cmd = "playback-chunk"
            session.wait_for(
                lambda event, expected=channel, cmd=expected_cmd: event.get("event") == "playback_queued"
                and event.get("channel") == expected
                and event.get("cmd") == cmd,
                timeout=3,
            )
        session.send({"cmd": "stop-playback"})
        session.wait_for(lambda event: event.get("event") == "ok" and event.get("cmd") == "stop-playback", timeout=3)
    finally:
        session.shutdown()


def smoke_capture(binary: Path, input_device_id: str, duration_ms: int) -> None:
    session = ServeSession(binary)
    try:
        session.wait_for(lambda event: event.get("event") == "ready", timeout=3)
        session.send(
            {
                "cmd": "start-capture",
                "channel": "smoke",
                "device_id": input_device_id,
                "sample_rate": 16000,
                "chunk_ms": 20,
                "noise_gate_db": -80,
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
        time.sleep(max(0, duration_ms) / 1000)
        session.send({"cmd": "stop-capture"})
        session.wait_for(lambda event: event.get("event") == "ok" and event.get("cmd") == "stop-capture", timeout=3)
    finally:
        session.shutdown()


def smoke_bridge_api(binary: Path, output_device_id: str, input_device_id: str, with_capture: bool) -> None:
    from audio_core_bridge import NativeAudioCoreBridge

    bridge = NativeAudioCoreBridge(binary)
    first = bridge.start_playback({"channel": "bridge-smoke", "device_id": output_device_id, "sample_rate": 24000, "chunk_ms": 20})
    second = bridge.start_playback({"channel": "bridge-smoke", "device_id": output_device_id, "sample_rate": 24000, "chunk_ms": 20})
    try:
        chunk = bytes(960)
        first.send_audio("bridge-smoke", chunk, 24000)
        second.send_audio("bridge-smoke", chunk, 24000)
        time.sleep(0.1)
    finally:
        first.close()
        second.close()

    if with_capture:
        capture = bridge.start_capture(
            {
                "channel": "bridge-capture-smoke",
                "device_id": input_device_id,
                "sample_rate": 16000,
                "chunk_ms": 20,
                "noise_gate_db": -80,
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
        try:
            deadline = time.time() + 2
            last_event: dict[str, Any] | None = None
            while time.time() < deadline:
                event = capture.read_event(timeout=0.25)
                if not event:
                    continue
                last_event = event
                if event.get("event") == "audio_chunk" and event.get("pcm16"):
                    break
            else:
                raise RuntimeError(f"bridge capture did not return an audio_chunk: {last_event}")
        finally:
            capture.close()

    NativeAudioCoreBridge.shutdown_all()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the NOVA native audio core.")
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--playback-device", default="")
    parser.add_argument("--capture-device", default="")
    parser.add_argument("--with-capture", action="store_true", help="Start a short native capture smoke test.")
    parser.add_argument("--multi-playback", action="store_true", help="Start two playback channels in one serve process.")
    parser.add_argument("--binary-playback", action="store_true", help="Send playback audio as binary IPC frames.")
    parser.add_argument("--bridge-api", action="store_true", help="Use audio_core_bridge.py instead of direct native stdin/stdout.")
    parser.add_argument("--capture-duration-ms", type=int, default=300)
    args = parser.parse_args()

    if not args.binary.exists():
        raise FileNotFoundError(f"native audio core binary not found: {args.binary}")

    health = run_json(args.binary, "health")
    if not health.get("ok"):
        raise RuntimeError(f"native core health failed: {health}")

    snapshot = run_json(args.binary, "list-devices")
    output_device_id = find_first_device(snapshot, "output", args.playback_device)
    input_device_id = find_first_device(snapshot, "input", args.capture_device) if args.with_capture or args.bridge_api else ""

    if args.bridge_api:
        smoke_bridge_api(args.binary, output_device_id, input_device_id, args.with_capture)
    else:
        smoke_playback(
            args.binary,
            output_device_id,
            channel_count=2 if args.multi_playback else 1,
            binary_audio=args.binary_playback,
        )

        if args.with_capture:
            smoke_capture(args.binary, input_device_id, args.capture_duration_ms)

    print(
        json.dumps(
            {
                "ok": True,
                "backend": health.get("backend"),
                "devices": len(snapshot.get("devices", [])),
                "playbackDevice": output_device_id,
                "playbackChannels": 2 if args.multi_playback else 1,
                "binaryPlayback": bool(args.binary_playback),
                "bridgeApi": bool(args.bridge_api),
                "captureTested": bool(args.with_capture),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
