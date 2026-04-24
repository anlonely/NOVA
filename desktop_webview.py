from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import tempfile
from typing import Any
from pathlib import Path

from PySide6.QtCore import QObject, Slot, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from nova_controller import NovaController
from paths import get_app_root, get_resource_root

APP_ROOT = get_app_root()
RESOURCE_ROOT = get_resource_root()
ROOT = APP_ROOT
HTML_PATH = RESOURCE_ROOT / "web_dashboard" / "index.html"
SINGLE_INSTANCE_MUTEX = None
SINGLE_INSTANCE_LOCK_FILE = None
ERROR_ALREADY_EXISTS = 183

if os.name == "nt":
    from ctypes import wintypes

    KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    KERNEL32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    KERNEL32.CreateMutexW.restype = wintypes.HANDLE
    KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    KERNEL32.CloseHandle.restype = wintypes.BOOL
else:
    KERNEL32 = None


def acquire_single_instance() -> bool:
    global SINGLE_INSTANCE_MUTEX, SINGLE_INSTANCE_LOCK_FILE
    mutex_name = f"Local\\NovaInterpDesktop_{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()}"
    if os.name != "nt":
        lock_name = f"nova-interp-{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()}.lock"
        lock_path = Path(tempfile.gettempdir()) / lock_name
        lock_file = lock_path.open("w")
        try:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            lock_file.close()
            return False
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        SINGLE_INSTANCE_LOCK_FILE = lock_file
        return True
    mutex = KERNEL32.CreateMutexW(None, False, mutex_name)
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        KERNEL32.CloseHandle(mutex)
        return False
    SINGLE_INSTANCE_MUTEX = mutex
    return True


def release_single_instance() -> None:
    global SINGLE_INSTANCE_MUTEX, SINGLE_INSTANCE_LOCK_FILE
    if os.name != "nt":
        if SINGLE_INSTANCE_LOCK_FILE:
            try:
                import fcntl

                fcntl.flock(SINGLE_INSTANCE_LOCK_FILE.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            SINGLE_INSTANCE_LOCK_FILE.close()
        SINGLE_INSTANCE_LOCK_FILE = None
        return
    if not SINGLE_INSTANCE_MUTEX:
        SINGLE_INSTANCE_MUTEX = None
        return
    KERNEL32.CloseHandle(SINGLE_INSTANCE_MUTEX)
    SINGLE_INSTANCE_MUTEX = None


class NovaBridge(QObject):
    def __init__(self, controller: NovaController) -> None:
        super().__init__()
        self.controller = controller

    def _normalize_json(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): self._normalize_json(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._normalize_json(item) for item in value]
        if hasattr(value, "item") and callable(getattr(value, "item")):
            try:
                return self._normalize_json(value.item())
            except Exception:
                pass
        return str(value)

    def _dump(self, payload: dict) -> str:
        return json.dumps(self._normalize_json(payload), ensure_ascii=False)

    @Slot(result=str)
    def get_state(self) -> str:
        return self._dump(self.controller.get_state())

    @Slot(str, result=str)
    def save_state(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.save_config(payload))

    @Slot(result=str)
    def refresh_devices(self) -> str:
        return self._dump(self.controller.refresh_devices())

    @Slot(str, result=str)
    def apply_scene(self, scene_id: str) -> str:
        return self._dump(self.controller.apply_scene(scene_id))

    @Slot(str, result=str)
    def apply_domain_pack(self, domain_id: str) -> str:
        return self._dump(self.controller.apply_domain_pack(domain_id))

    @Slot(str, result=str)
    def start_channels(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.start_channels(payload))

    @Slot(result=str)
    def stop_channels(self) -> str:
        return self._dump(self.controller.stop_channels())

    @Slot(result=str)
    def poll_state(self) -> str:
        return self._dump(self.controller.poll_state())

    @Slot(result=str)
    def export_session(self) -> str:
        return self._dump(self.controller.export_session())

    @Slot(str, result=str)
    def train_voice_clone(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.train_voice_clone(payload))

    @Slot(str, result=str)
    def refresh_voice_clone_status(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.refresh_voice_clone_status(payload))

    @Slot(str, result=str)
    def preview_channel_voice(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.preview_channel_voice(payload))

    @Slot(str, result=str)
    def poll_preview_channel_voice(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.poll_preview_channel_voice(payload))

    @Slot(str, result=str)
    def start_voice_clone_recording(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.start_voice_clone_recording(payload))

    @Slot(result=str)
    def stop_voice_clone_recording(self) -> str:
        return self._dump(self.controller.stop_voice_clone_recording())

    @Slot(str, result=str)
    def check_updates(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.check_updates(payload))

    @Slot(str, result=str)
    def download_update(self, payload_json: str) -> str:
        payload = json.loads(payload_json or "{}")
        return self._dump(self.controller.download_update(payload))

    @Slot(result=str)
    def pick_voice_clone_sample(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Choose voice clone sample",
            str(ROOT),
            "Audio Files (*.wav *.mp3 *.ogg *.m4a *.aac *.pcm);;All Files (*.*)",
        )
        return path or ""


class NovaWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.controller = NovaController()
        self.bridge = NovaBridge(self.controller)
        self.setWindowTitle("NOVA INTERP")
        self.resize(1600, 980)

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        page = self.view.page()
        profile = page.profile()
        profile.setHttpCacheType(QWebEngineProfile.NoCache)
        profile.clearHttpCache()
        channel = QWebChannel(page)
        channel.registerObject("novaBridge", self.bridge)
        page.setWebChannel(channel)
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.view.load(QUrl.fromLocalFile(str(HTML_PATH)))

    def closeEvent(self, event) -> None:  # pragma: no cover - GUI lifecycle
        self.controller.shutdown()
        super().closeEvent(event)


def main() -> None:
    if not acquire_single_instance():
        return
    try:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-features=msSmartScreenProtection")
        if sys.platform == "darwin":
            os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
        app = QApplication(sys.argv)
        app.setApplicationName("NOVA INTERP")
        window = NovaWindow()
        window.showMaximized()
        sys.exit(app.exec())
    finally:
        release_single_instance()


if __name__ == "__main__":
    main()
