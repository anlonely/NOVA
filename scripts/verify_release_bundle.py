from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE_CORE_NAME = "nova-audio-core.exe" if sys.platform.startswith("win") else "nova-audio-core"


def candidate_roots(dist_path: Path) -> list[Path]:
    roots = [dist_path]
    contents = dist_path / "Contents"
    if contents.exists():
        roots.extend([contents / "Resources", contents / "MacOS"])
    return roots


def find_native_core(dist_path: Path) -> Path | None:
    expected_suffix = Path("native_audio_core") / "target" / "release" / NATIVE_CORE_NAME
    for root in candidate_roots(dist_path):
        candidate = root / expected_suffix
        if candidate.exists():
            return candidate
    for candidate in dist_path.rglob(NATIVE_CORE_NAME):
        if "native_audio_core" in candidate.parts and "release" in candidate.parts:
            return candidate
    return None


def verify(dist_path: Path) -> dict[str, object]:
    if not dist_path.exists():
        return {"ok": False, "error": f"dist path not found: {dist_path}"}
    native_core = find_native_core(dist_path)
    if native_core is None:
        return {"ok": False, "error": f"native audio core missing from bundle: {NATIVE_CORE_NAME}"}
    return {
        "ok": True,
        "distPath": str(dist_path),
        "nativeCore": str(native_core),
        "nativeCoreSize": native_core.stat().st_size,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify NOVA release bundle contents.")
    parser.add_argument("--dist-path", type=Path, required=True, help="PyInstaller dist folder or macOS .app path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = verify(args.dist_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
