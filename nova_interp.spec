# -*- mode: python ; coding: utf-8 -*-

import json
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH)
app_version = json.loads((project_root / "app_version.json").read_text(encoding="utf-8")).get("version", "0.0.0")
datas = [
    (str(project_root / "web_dashboard"), "web_dashboard"),
    (str(project_root / "assets"), "assets"),
    (str(project_root / "config.example.json"), "."),
    (str(project_root / "app_version.json"), "."),
]

app_icon = project_root / "assets" / "icons" / ("nova_interp.ico" if sys.platform.startswith("win") else "nova_interp.icns")
native_core_name = "nova-audio-core.exe" if sys.platform.startswith("win") else "nova-audio-core"
native_core = project_root / "native_audio_core" / "target" / "release" / native_core_name
if native_core.exists():
    datas.append((str(native_core), "native_audio_core/target/release"))

hiddenimports = collect_submodules(
    "python_protogen",
    filter=lambda name: "__pycache__" not in name and not name.endswith("_grpc"),
)


a = Analysis(
    ["desktop_webview.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NOVA-INTERP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(app_icon) if app_icon.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NOVA-INTERP",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="NOVA INTERP.app",
        icon=str(app_icon) if app_icon.exists() else None,
        bundle_identifier="com.nova.interp",
        info_plist={
            "CFBundleName": "NOVA INTERP",
            "CFBundleDisplayName": "NOVA INTERP",
            "CFBundleShortVersionString": str(app_version),
            "CFBundleVersion": str(app_version),
            "NSHighResolutionCapable": True,
            "NSMicrophoneUsageDescription": "NOVA INTERP needs microphone access for real-time interpreting.",
        },
    )
