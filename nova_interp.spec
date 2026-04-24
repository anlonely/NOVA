# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH)
datas = [
    (str(project_root / "web_dashboard"), "web_dashboard"),
    (str(project_root / "config.example.json"), "."),
    (str(project_root / "app_version.json"), "."),
]

native_core = project_root / "native_audio_core" / "target" / "release" / "nova-audio-core.exe"
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
