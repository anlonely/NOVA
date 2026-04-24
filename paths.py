from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", "")
    if _is_frozen() and meipass:
        return Path(meipass).resolve()
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_app_root() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
