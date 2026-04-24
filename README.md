# NOVA INTERP

NOVA INTERP is a Windows-first desktop console for low-latency bilingual interpreting with independent audio routing, real-time subtitles, Volcengine AST streaming, and voice-clone workflow hooks.

This repository currently ships:

- A Qt + Web dashboard for the primary desktop app
- A legacy Tk prototype kept for fallback testing
- Volcengine AST WebSocket integration
- Voice Clone V3 training and preview hooks
- A 3-lane routing model for mic, platform audio, and game voice
- Optional Rust native audio-core scaffolding for future WASAPI upgrades

## Current feature set

- Channel A, B, and C can each choose independent input/output devices
- Dual-pane live transcript area with source and translated text
- Per-channel performance profiles, subtitle modes, and latency stats
- Domain bias packs, including a Rust-focused recognition preset
- Voice Clone V3 controls, status polling, and preview playback hooks
- Update-check hooks and version manifest support
- Windows-friendly dark dashboard with custom dropdowns and drawers

## Quick start

1. Create a local config file from the example:

```powershell
Copy-Item .\config.example.json .\config.local.json
```

2. Fill in your local credentials in `config.local.json`:

- `app_key`
- `access_key`
- `secret_key`

3. Launch the desktop app:

```powershell
.\launch.ps1
```

## Other entry points

- Main desktop dashboard: `.\launch.ps1`
- Legacy Tk prototype: `.\launch_legacy_tk.ps1`
- Static dashboard preview in browser: `.\launch_web_dashboard.ps1`
- AST smoke test: `.\.venv\Scripts\python smoke_test_ast.py`

## Packaging for Windows

Use the local build script to generate a distributable Windows package:

```powershell
.\scripts\build_windows.ps1
```

The script will:

- install runtime and build dependencies into `.venv`
- optionally build `native_audio_core` if Rust is available
- package the desktop app with PyInstaller
- emit a versioned zip bundle and SHA256 file under `output\release`

## GitHub Actions

The repository includes a Windows packaging workflow:

- push to `main`: build the app and upload the release bundle as an artifact
- push a tag like `v0.4.0`: build the app and publish the zip bundle to GitHub Releases
- manual trigger: run the workflow from GitHub Actions without creating a tag

## Security notes

- `config.local.json` is intentionally ignored and should never be committed
- `config.example.json` is the safe template to share publicly
- local build outputs, logs, downloads, and virtual environments are ignored

## Repository layout

- `desktop_webview.py`: desktop entry point for the Qt/Web app
- `nova_controller.py`: runtime controller, channel orchestration, and state bridge
- `web_dashboard/`: dashboard HTML, CSS, and JS
- `ast_bridge.py`: Volcengine AST streaming channel implementation
- `voice_clone_manager.py`: voice-clone API calls and preview helpers
- `native_audio_core/`: Rust audio-core scaffold
- `docs/`: product plan and delivery backlog
- `scripts/`: local packaging helpers

## Product docs

- [Commercial plan](docs/COMMERCIAL_V2_PLAN.md)
- [Delivery backlog](docs/DELIVERY_BACKLOG.md)
