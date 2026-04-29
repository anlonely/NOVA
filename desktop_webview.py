from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QUrl, QUrlQuery, Slot, Qt
from PySide6.QtGui import QIcon
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
TRANSCRIPT_WINDOW_HTML_PATH = RESOURCE_ROOT / "web_dashboard" / "transcript_window.html"
APP_ICON_PATH = RESOURCE_ROOT / "assets" / "icons" / ("nova_interp.ico" if sys.platform.startswith("win") else "nova_interp.icns")
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
    def __init__(self, controller: NovaController, window_manager: Optional["TranscriptWindowManager"] = None) -> None:
        super().__init__()
        self.controller = controller
        self.window_manager = window_manager

    def _load_payload(self, payload_json: str) -> Optional[dict[str, Any]]:
        try:
            payload = json.loads(payload_json or "{}")
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

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

    @Slot(str, result=str)
    def open_transcript_window(self, payload_json: str) -> str:
        if self.window_manager is None:
            return self._dump({"ok": False, "open": False, "error": "window_manager_missing"})
        payload = self._load_payload(payload_json)
        if payload is None:
            return self._dump({"ok": False, "open": False, "error": "invalid_payload"})
        alias = payload.get("alias", "")
        return self._dump(self.window_manager.open_window(alias, payload))

    @Slot(str, result=str)
    def close_transcript_window(self, payload_json: str) -> str:
        if self.window_manager is None:
            return self._dump({"ok": False, "open": False, "error": "window_manager_missing"})
        payload = self._load_payload(payload_json)
        if payload is None:
            return self._dump({"ok": False, "open": False, "error": "invalid_payload"})
        alias = payload.get("alias", "")
        return self._dump(self.window_manager.close_window(alias))

    @Slot(str, result=str)
    def set_transcript_window_topmost(self, payload_json: str) -> str:
        if self.window_manager is None:
            return self._dump({"ok": False, "open": False, "error": "window_manager_missing"})
        payload = self._load_payload(payload_json)
        if payload is None:
            return self._dump({"ok": False, "open": False, "error": "invalid_payload"})
        alias = payload.get("alias", "")
        pinned = bool(payload.get("pinned", False))
        return self._dump(self.window_manager.set_window_topmost(alias, pinned))

    @Slot(str, result=str)
    def is_transcript_window_open(self, payload_json: str) -> str:
        if self.window_manager is None:
            return self._dump({"ok": False, "open": False})
        payload = self._load_payload(payload_json)
        if payload is None:
            return self._dump({"ok": False, "open": False, "error": "invalid_payload"})
        alias = payload.get("alias", "")
        return self._dump(self.window_manager.get_window_state(alias))

    @Slot(result=str)
    def close_all_transcript_windows(self) -> str:
        if self.window_manager is not None:
            self.window_manager.close_all()
        return self._dump({"ok": True})


class TranscriptWindow(QMainWindow):
    def __init__(
        self,
        alias: str,
        bridge: QObject,
        parent: QMainWindow,
        html_path: Path,
        on_closed: Callable[[str], None],
        language: str = "en",
    ) -> None:
        super().__init__(parent=parent)
        self.alias = alias
        self.language = self._normalize_language(language)
        self._on_closed = on_closed
        self.setWindowTitle(self._localized_title())
        self.resize(500, 520)
        self.setMinimumSize(360, 340)

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        page = self.view.page()
        channel = QWebChannel(page)
        channel.registerObject("novaBridge", bridge)
        page.setWebChannel(channel)
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self._load_page(html_path)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)

    @staticmethod
    def _normalize_language(language: str) -> str:
        return "zh" if str(language or "").lower().startswith("zh") else "en"

    def _localized_title(self) -> str:
        channel_label = f"通道 {self.alias.upper()}" if self.language == "zh" else f"Channel {self.alias.upper()}"
        return f"{channel_label}{' 实时翻译' if self.language == 'zh' else ' Live Translation'}"

    def _load_page(self, html_path: Path) -> None:
        url = QUrl.fromLocalFile(str(html_path))
        query = QUrlQuery()
        query.addQueryItem("alias", self.alias)
        query.addQueryItem("lang", self.language)
        url.setQuery(query)
        self.view.load(url)

    def set_topmost(self, topmost: bool) -> None:
        self.setWindowTitle(self._localized_title())
        self.setWindowFlag(Qt.WindowStaysOnTopHint, topmost)
        self.show()

    def set_language(self, language: str) -> None:
        next_language = self._normalize_language(language)
        if next_language == self.language:
            return
        self.language = next_language
        self.setWindowTitle(self._localized_title())
        self._load_page(Path(str(self.view.url().toLocalFile())))

    def closeEvent(self, event) -> None:  # pragma: no cover - GUI lifecycle
        self._on_closed(self.alias)
        super().closeEvent(event)


class TranscriptWindowManager:
    def __init__(self, bridge: QObject, parent: QMainWindow, html_path: Path) -> None:
        self.bridge = bridge
        self.parent = parent
        self.html_path = html_path
        self.windows: dict[str, TranscriptWindow] = {}
        self.pinned: dict[str, bool] = {}

    def _normalize_alias(self, alias: str) -> Optional[str]:
        return alias if alias in ("a", "b", "c") else None

    def _default_response(self, alias: str, open_state: bool, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": True, "alias": alias, "open": open_state, "pinned": bool(self.pinned.get(alias, False))}
        if extra is not None:
            payload.update(extra)
        return payload

    def get_window_state(self, alias: str) -> dict[str, Any]:
        alias = self._normalize_alias(alias.lower() if isinstance(alias, str) else "")
        if alias is None:
            return {"ok": False, "open": False, "error": "invalid_alias"}
        return {"ok": True, "open": alias in self.windows, "pinned": bool(self.pinned.get(alias, False))}

    def open_window(self, alias: str, payload: dict[str, Any]) -> dict[str, Any]:
        alias = self._normalize_alias(alias.lower() if isinstance(alias, str) else "")
        if alias is None:
            return {"ok": False, "open": False, "error": "invalid_alias"}
        pinned = bool(payload.get("pinned", self.pinned.get(alias, False)))
        self.pinned[alias] = pinned
        language = str(payload.get("lang", "en"))
        window = self.windows.get(alias)
        if window is None:
            window = TranscriptWindow(alias, self.bridge, self.parent, self.html_path, self._on_window_closed, language=language)
            self.windows[alias] = window
        else:
            window.set_language(language)
        window.set_topmost(pinned)
        window.raise_()
        window.activateWindow()
        window.show()
        return self._default_response(alias, True)

    def close_window(self, alias: str) -> dict[str, Any]:
        alias = self._normalize_alias(alias.lower() if isinstance(alias, str) else "")
        if alias is None:
            return {"ok": False, "open": False, "error": "invalid_alias"}
        window = self.windows.get(alias)
        if window is None:
            return self._default_response(alias, False)
        window.close()
        self.windows.pop(alias, None)
        return self._default_response(alias, False)

    def set_window_topmost(self, alias: str, pinned: bool) -> dict[str, Any]:
        alias = self._normalize_alias(alias.lower() if isinstance(alias, str) else "")
        if alias is None:
            return {"ok": False, "open": False, "error": "invalid_alias"}
        self.pinned[alias] = bool(pinned)
        window = self.windows.get(alias)
        if window is None:
            return {"ok": True, "open": False, "pinned": bool(pinned)}
        window.set_topmost(pinned)
        return {"ok": True, "open": True, "pinned": bool(pinned)}

    def close_all(self) -> None:
        for window in list(self.windows.values()):
            window.close()
        self.windows.clear()

    def _on_window_closed(self, alias: str) -> None:
        self.windows.pop(alias, None)


class NovaWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.controller = NovaController()
        self.bridge = NovaBridge(self.controller)
        self.transcript_window_manager = TranscriptWindowManager(self.bridge, self, TRANSCRIPT_WINDOW_HTML_PATH)
        self.bridge.window_manager = self.transcript_window_manager
        self.setWindowTitle("NOVA INTERP")
        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
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
        self.transcript_window_manager.close_all()
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
        if APP_ICON_PATH.exists():
            app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        window = NovaWindow()
        window.showMaximized()
        sys.exit(app.exec())
    finally:
        release_single_instance()


if __name__ == "__main__":
    main()
