# NOVA Audio Core

Windows-first Rust audio core scaffold for future low-latency routing.

Current scope:

- WASAPI device enumeration
- virtual device detection
- JSON bridge for the Python controller

Build locally after installing Rust:

```powershell
cd native_audio_core
cargo build --release
```

The desktop app will automatically probe `target/release/nova-audio-core.exe` when it exists.
