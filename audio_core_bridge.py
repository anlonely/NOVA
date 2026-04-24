from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
NATIVE_CORE_EXE = ROOT / "native_audio_core" / "target" / "release" / "nova-audio-core.exe"


class NativeAudioCoreBridge:
    def __init__(self, binary_path: Path | None = None) -> None:
        self.binary_path = binary_path or NATIVE_CORE_EXE

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
