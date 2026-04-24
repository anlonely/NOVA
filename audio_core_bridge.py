from __future__ import annotations

import base64
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from paths import get_resource_root

ROOT = get_resource_root()
NATIVE_CORE_NAME = "nova-audio-core.exe" if sys.platform.startswith("win") else "nova-audio-core"
NATIVE_CORE_EXE = ROOT / "native_audio_core" / "target" / "release" / NATIVE_CORE_NAME
NATIVE_CORE_DEBUG_EXE = ROOT / "native_audio_core" / "target" / "debug" / NATIVE_CORE_NAME


class NativeAudioCoreBridge:
    def __init__(self, binary_path: Path | None = None) -> None:
        self.binary_path = binary_path or (NATIVE_CORE_EXE if NATIVE_CORE_EXE.exists() else NATIVE_CORE_DEBUG_EXE)

    @property
    def available(self) -> bool:
        return self.binary_path.exists()

    def enumerate_devices(self) -> dict[str, Any] | None:
        if not self.available:
            return None
        try:
            result = subprocess.run(
                [str(self.binary_path), "list-devices"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=8,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

        try:
            return json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return None

    def health(self) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "error": "Native audio core binary is not available.", "binaryPath": str(self.binary_path)}
        try:
            result = subprocess.run(
                [str(self.binary_path), "health"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5,
                check=True,
            )
            payload = json.loads(result.stdout or "{}")
            payload["binaryPath"] = str(self.binary_path)
            return payload
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc), "binaryPath": str(self.binary_path)}

    def start_capture(self, config: dict[str, Any]) -> NativeCaptureSession:
        session = NativeCaptureSession(self.binary_path)
        session.start(config)
        return session


class NativeCaptureSession:
    def __init__(self, binary_path: Path) -> None:
        self.binary_path = binary_path
        self.process: subprocess.Popen[str] | None = None
        self.events: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=512)
        self.stderr_lines: queue.Queue[str] = queue.Queue(maxsize=64)
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._closed = threading.Event()

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, config: dict[str, Any]) -> None:
        if not self.binary_path.exists():
            raise RuntimeError(f"Native audio core binary is missing: {self.binary_path}")
        self.process = subprocess.Popen(
            [str(self.binary_path), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._reader_thread = threading.Thread(target=self._read_stdout, name="native-audio-stdout", daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, name="native-audio-stderr", daemon=True)
        self._reader_thread.start()
        self._stderr_thread.start()
        ready = self.read_event(timeout=5)
        if not ready or ready.get("event") != "ready":
            self.close()
            raise RuntimeError(f"Native audio core did not become ready: {ready or self.recent_stderr()}")
        self.send({"cmd": "start-capture", **config})
        deadline = time.time() + 5
        while time.time() < deadline:
            event = self.read_event(timeout=0.5)
            if not event:
                continue
            if event.get("event") == "ok" and event.get("cmd") == "start-capture":
                return
            if event.get("event") == "error":
                self.close()
                raise RuntimeError(str(event.get("message") or "Native capture failed."))
        self.close()
        raise RuntimeError("Timed out while starting native capture.")

    def send(self, payload: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin or self.process.poll() is not None:
            raise RuntimeError("Native audio core process is not running.")
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def read_event(self, timeout: float = 0.05) -> dict[str, Any] | None:
        try:
            event = self.events.get(timeout=timeout)
        except queue.Empty:
            return None
        if event.get("event") == "audio_chunk" and event.get("data"):
            try:
                event["pcm16"] = base64.b64decode(str(event.get("data") or ""))
            except Exception:
                event["pcm16"] = b""
        return event

    def stop(self) -> None:
        if self.is_running:
            try:
                self.send({"cmd": "stop-capture"})
            except Exception:
                pass

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        if self.is_running:
            try:
                self.send({"cmd": "shutdown"})
            except Exception:
                pass
            try:
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
        self.process = None

    def recent_stderr(self) -> str:
        items: list[str] = []
        while True:
            try:
                items.append(self.stderr_lines.get_nowait())
            except queue.Empty:
                break
        return "\n".join(items[-8:])

    def _read_stdout(self) -> None:
        if not self.process or not self.process.stdout:
            return
        for line in self.process.stdout:
            if self._closed.is_set():
                break
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {"event": "error", "message": f"Invalid native event: {line.strip()}"}
            self._put_event(payload)

    def _read_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return
        for line in self.process.stderr:
            if self._closed.is_set():
                break
            self._put_stderr(line.rstrip())

    def _put_event(self, event: dict[str, Any]) -> None:
        try:
            self.events.put_nowait(event)
        except queue.Full:
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            self.events.put_nowait(event)

    def _put_stderr(self, line: str) -> None:
        try:
            self.stderr_lines.put_nowait(line)
        except queue.Full:
            try:
                self.stderr_lines.get_nowait()
            except queue.Empty:
                pass
            self.stderr_lines.put_nowait(line)
