from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "app_version.json"
DOWNLOAD_DIR = ROOT / "output" / "updates"


def _parse_version(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(value or "0").replace("v", "").split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts)


class AppUpdater:
    def __init__(self) -> None:
        self.current = self._load_current()

    def _load_current(self) -> dict[str, Any]:
        if not VERSION_FILE.exists():
            return {"version": "0.0.0", "channel": "stable", "manifest_url": "", "notes": ""}
        try:
            return json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"version": "0.0.0", "channel": "stable", "manifest_url": "", "notes": ""}

    def set_manifest_url(self, manifest_url: str) -> dict[str, Any]:
        self.current["manifest_url"] = str(manifest_url or "").strip()
        VERSION_FILE.write_text(json.dumps(self.current, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.current

    def check(self, manifest_url: str = "") -> dict[str, Any]:
        url = str(manifest_url or self.current.get("manifest_url", "")).strip()
        if not url:
            return {
                "ok": False,
                "error": "No update manifest URL configured.",
                "current": self.current,
            }

        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                manifest = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return {"ok": False, "error": f"HTTP {exc.code} while checking updates.", "current": self.current}
        except urllib.error.URLError as exc:
            return {"ok": False, "error": f"Network error while checking updates: {exc.reason}", "current": self.current}
        except json.JSONDecodeError:
            return {"ok": False, "error": "Update manifest is not valid JSON.", "current": self.current}

        latest_version = str(manifest.get("version", "0.0.0"))
        update_available = _parse_version(latest_version) > _parse_version(self.current.get("version", "0.0.0"))
        return {
            "ok": True,
            "current": self.current,
            "manifest": manifest,
            "updateAvailable": update_available,
        }

    def download(self, download_url: str, filename: str = "") -> dict[str, Any]:
        url = str(download_url or "").strip()
        if not url:
            return {"ok": False, "error": "No download URL provided."}

        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        target_name = filename.strip() or Path(urllib.parse.urlparse(url).path).name or "nova-update.bin"
        target = DOWNLOAD_DIR / target_name

        try:
            with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
                shutil.copyfileobj(response, output)
        except urllib.error.HTTPError as exc:
            return {"ok": False, "error": f"HTTP {exc.code} while downloading update."}
        except urllib.error.URLError as exc:
            return {"ok": False, "error": f"Network error while downloading update: {exc.reason}"}

        return {"ok": True, "path": str(target), "name": target.name, "size": target.stat().st_size}
