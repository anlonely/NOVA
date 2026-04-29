from __future__ import annotations

import atexit
import base64
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from paths import get_resource_root

ROOT = get_resource_root()
NATIVE_CORE_NAME = "nova-audio-core.exe" if sys.platform.startswith("win") else "nova-audio-core"
NATIVE_CORE_EXE = ROOT / "native_audio_core" / "target" / "release" / NATIVE_CORE_NAME
NATIVE_CORE_DEBUG_EXE = ROOT / "native_audio_core" / "target" / "debug" / NATIVE_CORE_NAME


class NativeAudioCoreBridge:
    _services: dict[Path, NativeAudioCoreService] = {}
    _services_lock = threading.Lock()

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
        service = self._service()
        session = NativeCaptureSession(service, str(config.get("channel") or "capture"))
        session.start(config)
        return session

    def start_playback(self, config: dict[str, Any]) -> NativePlaybackSession:
        service = self._service()
        session = NativePlaybackSession(service, str(config.get("channel") or "playback"))
        session.start(config)
        return session

    def _service(self) -> NativeAudioCoreService:
        if not self.binary_path.exists():
            raise RuntimeError(f"Native audio core binary is missing: {self.binary_path}")
        key = self.binary_path.resolve()
        with self._services_lock:
            service = self._services.get(key)
            if service is None or not service.is_running:
                service = NativeAudioCoreService(key)
                service.start()
                self._services[key] = service
            return service

    @classmethod
    def shutdown_all(cls) -> None:
        with cls._services_lock:
            services = list(cls._services.values())
            cls._services.clear()
        for service in services:
            service.shutdown()

    def drain_events(self, max_events: int = 64) -> list[dict[str, Any]]:
        with self._services_lock:
            service = self._services.get(self.binary_path.resolve()) if self.binary_path.exists() else None
        if service is None or not service.is_running:
            return []
        return service.drain_global_events(max_events=max_events)


class NativeAudioCoreService:
    def __init__(self, binary_path: Path) -> None:
        self.binary_path = binary_path
        self.process: subprocess.Popen[str] | None = None
        self.global_events: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=512)
        self.stderr_lines: queue.Queue[str] = queue.Queue(maxsize=128)
        self._channel_events: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._closed = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._playback_counter = 0

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None and not self._closed.is_set()

    def start(self) -> None:
        self.process = subprocess.Popen(
            [str(self.binary_path), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._reader_thread = threading.Thread(target=self._read_stdout, name="native-core-stdout", daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, name="native-core-stderr", daemon=True)
        self._reader_thread.start()
        self._stderr_thread.start()
        ready = self.wait_global(lambda event: event.get("event") == "ready", timeout=5)
        if not ready:
            self.shutdown()
            raise RuntimeError(f"Native audio core did not become ready: {self.recent_stderr()}")

    def register_channel(self, channel: str) -> queue.Queue[dict[str, Any]]:
        with self._lock:
            events: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=512)
            self._channel_events[channel] = events
            return events

    def unregister_channel(self, channel: str) -> None:
        with self._lock:
            self._channel_events.pop(channel, None)

    def allocate_playback_channel(self, base_channel: str) -> str:
        with self._lock:
            self._playback_counter += 1
            return f"{base_channel}:playback:{self._playback_counter}"

    def send(self, payload: dict[str, Any]) -> None:
        with self._write_lock:
            if not self.process or not self.process.stdin or self.process.poll() is not None:
                raise RuntimeError("Native audio core process is not running.")
            self.process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            self.process.stdin.flush()

    def send_playback_audio(self, channel: str, pcm16: bytes, sample_rate: int) -> None:
        header = {
            "cmd": "playback-chunk-binary",
            "channel": channel,
            "sample_rate": sample_rate,
            "byte_len": len(pcm16),
        }
        with self._write_lock:
            if not self.process or not self.process.stdin or self.process.poll() is not None:
                raise RuntimeError("Native audio core process is not running.")
            self.process.stdin.write((json.dumps(header, ensure_ascii=False) + "\n").encode("utf-8"))
            self.process.stdin.write(pcm16)
            self.process.stdin.flush()

    def wait_channel(
        self,
        events: queue.Queue[dict[str, Any]],
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float,
    ) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                event = events.get(timeout=min(0.25, max(0.01, deadline - time.time())))
            except queue.Empty:
                continue
            if predicate(event):
                return event
            if event.get("event") == "error":
                raise RuntimeError(str(event.get("message") or "Native audio core error."))
        return None

    def wait_global(self, predicate: Callable[[dict[str, Any]], bool], timeout: float) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                event = self.global_events.get(timeout=min(0.25, max(0.01, deadline - time.time())))
            except queue.Empty:
                continue
            if predicate(event):
                return event
            if event.get("event") == "error" and not event.get("channel"):
                raise RuntimeError(str(event.get("message") or "Native audio core error."))
        return None

    def drain_global_events(self, max_events: int = 64) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for _ in range(max(0, max_events)):
            try:
                events.append(self.global_events.get_nowait())
            except queue.Empty:
                break
        return events

    def shutdown(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        if self.process and self.process.poll() is None:
            try:
                self.send({"cmd": "shutdown"})
            except Exception:
                pass
            try:
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
        self.process = None
        with self._lock:
            self._channel_events.clear()

    def recent_stderr(self) -> str:
        items: list[str] = []
        while True:
            try:
                items.append(self.stderr_lines.get_nowait())
            except queue.Empty:
                break
        return "\n".join(items[-10:])

    def _read_stdout(self) -> None:
        if not self.process or not self.process.stdout:
            return
        while not self._closed.is_set():
            line = self.process.stdout.readline()
            if not line:
                break
            if self._closed.is_set():
                break
            try:
                payload = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {"event": "error", "message": f"Invalid native event: {line!r}"}
            if payload.get("event") == "audio_chunk_binary":
                byte_len = int(payload.get("byte_len") or 0)
                data = self.process.stdout.read(byte_len) if byte_len > 0 else b""
                payload["event"] = "audio_chunk"
                payload["pcm16"] = data
            self._dispatch_event(payload)

    def _read_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return
        for line in self.process.stderr:
            if self._closed.is_set():
                break
            self._put_bounded(self.stderr_lines, line.decode("utf-8", errors="replace").rstrip())

    def _dispatch_event(self, event: dict[str, Any]) -> None:
        channel = str(event.get("channel") or "")
        if not channel:
            self._put_bounded(self.global_events, event)
            return
        with self._lock:
            target = self._channel_events.get(channel)
        if target is not None:
            self._put_bounded(target, event)

    def _put_bounded(self, target: queue.Queue[Any], item: Any) -> None:
        try:
            target.put_nowait(item)
            return
        except queue.Full:
            pass
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        try:
            target.put_nowait(item)
        except queue.Full:
            pass


class NativeCaptureSession:
    def __init__(self, service: NativeAudioCoreService, channel: str) -> None:
        self.service = service
        self.channel = channel
        self.events = service.register_channel(channel)
        self._closed = threading.Event()

    @property
    def is_running(self) -> bool:
        return self.service.is_running and not self._closed.is_set()

    def start(self, config: dict[str, Any]) -> None:
        self.service.send({"cmd": "start-capture", **config, "channel": self.channel, "binary_audio_events": True})
        event = self.service.wait_channel(
            self.events,
            lambda payload: payload.get("event") == "ok" and payload.get("cmd") == "start-capture",
            timeout=5,
        )
        if not event:
            self.close()
            raise RuntimeError(f"Timed out while starting native capture: {self.recent_stderr()}")

    def send(self, payload: dict[str, Any]) -> None:
        self.service.send(payload)

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
                self.service.send({"cmd": "stop-capture", "channel": self.channel})
            except Exception:
                pass

    def close(self) -> None:
        if self._closed.is_set():
            return
        self.stop()
        self._closed.set()
        self.service.unregister_channel(self.channel)

    def recent_stderr(self) -> str:
        return self.service.recent_stderr()


class NativePlaybackSession:
    def __init__(self, service: NativeAudioCoreService, channel: str) -> None:
        self.service = service
        self.public_channel = channel
        self.channel = service.allocate_playback_channel(channel)
        self.events = service.register_channel(self.channel)
        self._closed = threading.Event()

    @property
    def is_running(self) -> bool:
        return self.service.is_running and not self._closed.is_set()

    def start(self, config: dict[str, Any]) -> None:
        self.service.send({"cmd": "start-playback", **config, "channel": self.channel})
        event = self.service.wait_channel(
            self.events,
            lambda payload: payload.get("event") == "ok" and payload.get("cmd") == "start-playback",
            timeout=5,
        )
        if not event:
            self.close()
            raise RuntimeError(f"Timed out while starting native playback: {self.recent_stderr()}")

    def send_audio(self, channel: str, pcm16: bytes, sample_rate: int) -> None:
        self.service.send_playback_audio(self.channel, pcm16, sample_rate)

    def stop(self) -> None:
        if self.is_running:
            try:
                self.service.send({"cmd": "stop-playback", "channel": self.channel})
            except Exception:
                pass

    def close(self) -> None:
        if self._closed.is_set():
            return
        self.stop()
        self._closed.set()
        self.service.unregister_channel(self.channel)

    def recent_stderr(self) -> str:
        return self.service.recent_stderr()


atexit.register(NativeAudioCoreBridge.shutdown_all)
