# NOVA INTERP

Low-latency desktop real-time translation console for Discord, gaming voice, meetings, and cross-language collaboration.

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Qt%20WebEngine-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-Audio%20Core-000000?style=for-the-badge&logo=rust&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-App%20Bundle-111111?style=for-the-badge&logo=apple&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-Packaging-0078D4?style=for-the-badge&logo=windows&logoColor=white)

This repo now keeps Chinese and English documentation together. [中文说明](README.md).

---

## Features

- 3 independent channels (A/B/C) for microphone, incoming call audio, and game chat.
- Per-channel input/output/monitor device routing.
- Live subtitle mode and line diagnostics (AST latency, TTS latency, queue depth, clipping/drop events).
- Domain/preset tuning for recognition and translation context.
- Voice clone workflow (sample upload, train, preview, channel assignment).
- macOS `.app` bundle and Windows release packaging.

---

## 🚀 Get Started (Out of the Box)

### Prerequisites

- Volcengine account (for enabling Doubao Speech and free trial quota)
- Virtual audio cable if needed:
  - Windows: VB-Cable / VoiceMeeter
  - macOS: VB-Cable / BlackHole / Loopback

### 1. Download and run packaged app (recommended)

#### macOS

1. Open [Releases](https://github.com/anlonely/NOVA/releases/latest) and download the latest `NOVA-INTERP-macOS-*.zip`.
2. Unzip and double click `NOVA INTERP.app`.
3. If macOS blocks it, allow opening in system security settings.

#### Windows

1. Open [Releases](https://github.com/anlonely/NOVA/releases/latest) and download the latest `NOVA-INTERP-windows-x64-*.zip`.
2. Unzip and run `NOVA-INTERP.exe`.

### 2. Fill credentials in app settings (ready to run)

After launch, open **Engine Access** in the left settings drawer and fill:

- `APP ID`
- `Access Token` (recommended first)
- `Secret Key` (optional when using Token mode)
- `resource_id` (default `volc.service_type.10053`)

### 3. Open Volcengine account and get credentials (3–5 minutes)

1. Visit <https://console.volcengine.com/speech/app> and complete identity verification.
2. Create an app, select region, enable:
   - `Doubao model speech translation` (required)
   - `Voice clone` (optional if you need cloning)
3. Copy `APP ID`, `Access Token`, `secret_key` from app details.
4. If Signature mode is required, create IAM access key at <https://console.volcengine.com/iam/credential/access-keys>.
5. Keep `resource_id` as `volc.service_type.10053` for first verification.

### 4. Start quickly and validate

```bash
python smoke_test_ast.py
```

Expected output:

- `output/smoke_translation.txt`
- `output/smoke_translation.wav`

### 5. First run note

- If you see “credentials not configured”, go back to **Engine Access** and save `APP ID` + `Access Token`.
- Click **Connect/Start**; if it still does not connect, restart the app.

### 6. Optional: run from source

```bash
git clone https://github.com/anlonely/NOVA.git
cd NOVA
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
./launch_macos.sh    # macOS
.\launch.ps1         # Windows
```

---

## Development

- `desktop_webview.py` is the main desktop entry.
- `python desktop_webview.py` runs the app directly.
- Build releases with `scripts/build_macos.sh` or `scripts/build_windows.ps1`.
- Keep secrets out of the repo and rotate keys that ever appear in logs, screenshots, or chat history.
