# NOVA Native Audio Core v2 完整开发蓝图

本蓝图是 `codex/native-audio-core-v2` 分支的最终实施规划。后续实现以此为准，不再临时扩大或改变范围。目标是在不影响 `main` 已可用 Python 音频链路的前提下，新增可灰度启用、可回退、可观测的 Rust 原生音频核心。

---

## 1. 总目标

将 NOVA 的实时音频链路拆分为：

```text
Rust Native Audio Core：设备、采集、VAD、预卷、AGC、重采样、指标、播放预留
Python Controller：配置、AST WebSocket、字幕事件、TTS 数据、UI 桥接
Web Dashboard：启停、字幕、线路诊断、Native 状态和指标
```

第一阶段一次性完成 **Native Capture MVP + 完整可观测 + 配置/UI/打包/测试**。播放链路保留 Python，但 Rust 协议与模块预留 playback 接口，避免后续推倒重来。

---

## 2. 不变边界

- 默认仍使用 Python capture，避免破坏现有可用体验。
- Native capture 必须通过配置显式启用。
- Native capture 出错必须自动回退 Python capture。
- AST WebSocket、字幕事件、TTS 返回、声音克隆流程不迁移。
- 不引入后台常驻系统服务。
- 不提交 `config.local.json`、构建产物和密钥。

---

## 3. 开发顺序总览

1. **Rust 协议与 CLI**
   - 保留 `list-devices`
   - 新增 `health`
   - 新增 `serve` JSONL 子进程模式
2. **Rust Capture Engine**
   - 输入设备匹配
   - cpal 输入流
   - f32/i16/u16 输入转换
   - stereo/multi-channel 转 mono
   - 低延迟重采样到 16k
   - PCM16 chunk 输出
3. **Rust 语音前处理**
   - RMS dBFS
   - noise gate
   - silence hold
   - pre-roll
   - 可选 AGC
   - metrics 输出
4. **Python Native Bridge**
   - 长期子进程
   - JSONL 命令/事件
   - audio chunk 读取
   - metrics 合并
   - 生命周期和超时处理
5. **TranslationChannel 接入**
   - `capture_backend` 字段
   - native capture thread
   - 失败回退 Python capture
   - 保持 `_audio_queue` 和 AST 发送逻辑不变
6. **Controller / Config**
   - `audio_core.capture_backend`
   - `native_capture_fallback`
   - `pre_roll_ms`
   - 状态快照扩展
7. **Web UI**
   - 音频核心状态
   - Native/Python capture 切换
   - 回退提示
   - native metrics 展示
8. **打包**
   - Windows PyInstaller 继续带 `.exe`
   - macOS PyInstaller 继续带无扩展名二进制
   - CI 构建脚本保持一致
9. **测试验证**
   - Rust build
   - Rust serve health
   - Python bridge smoke
   - Controller start/stop
   - JS syntax
   - Python compile
   - macOS package build

---

## 4. Rust 模块规划

当前仓库保持单 binary，内部按结构体和函数分层，避免一次性拆太多文件影响构建。

### 4.1 CLI 命令

```bash
nova-audio-core list-devices
nova-audio-core health
nova-audio-core serve
```

### 4.2 JSONL 协议

#### Python -> Rust

```json
{"cmd":"health"}
{"cmd":"list-devices"}
{"cmd":"start-capture","channel":"a","device_id":"99","sample_rate":16000,"chunk_ms":20,"noise_gate_db":-46,"silence_hold_ms":140,"pre_roll_ms":160,"input_gain":1.08,"enable_agc":false,"agc_target_dbfs":-18,"max_agc_gain":6}
{"cmd":"stop-capture"}
{"cmd":"shutdown"}
```

#### Rust -> Python

```json
{"event":"ready","backend":"coreaudio"}
{"event":"health","ok":true,"backend":"coreaudio"}
{"event":"devices","snapshot":{}}
{"event":"capture_started","channel":"a","device_name":"MacBook Pro麦克风","input_sample_rate":48000,"target_sample_rate":16000}
{"event":"audio_chunk","channel":"a","seq":1,"sample_rate":16000,"duration_ms":20,"speech":true,"level_db":-28.4,"queue_depth":0,"dropped_silent_chunks":3,"data":"base64-pcm16"}
{"event":"metrics","channel":"a","sample_rate":16000,"level_db":-31,"speech":false,"queue_depth":0,"dropped_silent_chunks":10}
{"event":"ok","cmd":"stop-capture"}
{"event":"error","message":"..."}
{"event":"shutdown"}
```

### 4.3 Capture Engine

- 设备匹配支持：稳定 ID、设备名、索引、包含匹配。
- 输入格式支持：`f32`、`i16`、`u16`。
- 目标输出：`pcm_s16le`、`mono`、`16000 Hz`。
- chunk 默认：20ms，可配置 10–120ms。
- 重采样：线性重采样 MVP，后续可替换 `rubato`。

### 4.4 VAD / Gate / Pre-roll

- `level_db >= noise_gate_db` 视为 speech。
- speech 开始后附带 pre-roll 缓冲。
- speech 结束后保留 `silence_hold_ms`。
- 静音 chunk 不发送，只累计 `dropped_silent_chunks`。
- 每 240ms 输出一次 metrics。

### 4.5 AGC

- 默认关闭。
- 开启时按 `target_dbfs` 计算 gain。
- gain 限制 `0.25..max_agc_gain`。
- 与 `input_gain` 叠乘。

---

## 5. Python 模块规划

### 5.1 `audio_core_bridge.py`

新增：

- `NativeAudioCoreBridge.health()`
- `NativeCaptureSession`
- `start_capture(config)`
- `read_event(timeout)`
- `stop()`
- `close()`

要求：

- 子进程 stdout JSONL。
- stderr 后台收集最近错误。
- stop/shutdown 幂等。
- 超时不阻塞主线程。
- 启动失败返回明确错误。

### 5.2 `ast_bridge.py`

新增字段：

- `ChannelSettings.capture_backend`
- `ChannelSettings.native_capture_fallback`
- `ChannelSettings.pre_roll_ms`

新增逻辑：

- `_capture_audio_native()`
- `_capture_audio_python()` 保留原实现
- `_capture_audio()` 根据 backend 分发
- native event `audio_chunk` 进入 `_audio_queue`
- native event `metrics` 更新 `ChannelStats`
- native error 且 fallback 开启时回退 Python

### 5.3 `nova_controller.py`

新增配置：

```json
"audio_core": {
  "capture_backend": "python",
  "native_capture_fallback": true,
  "pre_roll_ms": 160
}
```

新增状态：

```json
"nativeAudioCore": {
  "available": true,
  "runtime": "native|python",
  "captureBackend": "python|native",
  "fallbackEnabled": true,
  "preRollMs": 160
}
```

---

## 6. UI 规划

### 6.1 设置位置

在平台/音频核心区域展示：

- Native core available / unavailable
- Capture backend：Python / Native
- Native fallback：on / off
- Pre-roll ms

### 6.2 诊断显示

线路与诊断继续显示：

- 通道状态
- 输入/输出设备
- 电平
- 队列
- 丢弃数
- AST/TTS 延迟
- capture backend
- fallback 状态

---

## 7. 打包规划

### Windows

- `native_audio_core/target/release/nova-audio-core.exe`
- PyInstaller spec 自动带入。
- GitHub Actions windows workflow 继续构建。

### macOS

- `native_audio_core/target/release/nova-audio-core`
- PyInstaller spec 自动带入。
- `scripts/build_macos.sh` 构建 `.app` 和 zip。

---

## 8. 测试规划

### Rust

```bash
cargo build --manifest-path native_audio_core/Cargo.toml
cargo build --release --manifest-path native_audio_core/Cargo.toml
native_audio_core/target/release/nova-audio-core health
native_audio_core/target/release/nova-audio-core list-devices
```

### Python

```bash
python -m py_compile audio_core_bridge.py ast_bridge.py nova_controller.py desktop_webview.py
python - <<'PY'
from audio_core_bridge import NativeAudioCoreBridge
bridge = NativeAudioCoreBridge()
print(bridge.health())
PY
```

### Frontend

```bash
node --check web_dashboard/dashboard.js
```

### Controller smoke

- Python capture start/stop。
- Native capture start/stop。
- Native unavailable fallback。
- Config save/load。

### Packaging

```bash
./scripts/build_macos.sh
```

Windows 构建由 GitHub Actions 验证。

---

## 9. 验收标准

- 默认 Python capture 与原逻辑兼容。
- Native capture 可启用并能输出音频 chunk。
- Native capture 失败时不影响启动，可回退 Python。
- UI 能看到当前 capture backend。
- 线路诊断能看到 native metrics。
- macOS build 成功。
- 不提交本地密钥和构建产物。
- 所有改动在 `codex/native-audio-core-v2` 分支。

---

## 10. 本阶段明确不做

- Rust playback 正式替换。
- 二进制 socket 协议。
- denoise 算法引入。
- 多进程多通道复杂调度优化。
- 代码签名和 notarization。

---

## 10. Native Audio Core v3 优化顺序（一次性执行版）

本节固化本轮“全部优化”的最终顺序，后续不再扩展范围，避免影响当前可用主链路。

1. **重采样升级**
   - 默认 `sinc-lite`，用 cubic interpolation 提升 48k/44.1k -> 16k 的语音稳定性。
   - 保留 `linear` 作为最低 CPU 回退。
2. **VAD 升级**
   - 默认 `adaptive`，结合 RMS、动态噪声底、过零率评分。
   - 保留 `gate` 作为简单阈值回退。
3. **低延迟协议扩展**
   - `audio_chunk` 和 `metrics` 增加 `vad_score`、`noise_floor_db`、`agc_gain`、`resampler`、`emitted_at_ms`。
   - 预留 native playback 命令：`start-playback`、`playback-chunk`、`stop-playback`。
4. **设备热插拔**
   - `serve` 模式每 2 秒轮询设备数量变化，变化时发出 `devices_changed`。
5. **平台策略暴露**
   - Windows 标记 `wasapi-event-shared-low-latency`。
   - macOS 标记 `coreaudio-cpal-hal-compatible`。
   - 深层 WASAPI exclusive / AudioUnit HAL 作为后续需专用权限和设备验证的替换实现，不在本轮破坏性切换。
6. **AST 发送策略优化**
   - native capture 支持 `adaptive_chunking`，语音活跃时限制低延迟 chunk。
   - Python AST 队列保持兼容，不改变服务端协议。
7. **诊断增强**
   - Controller/UI 展示 capture backend、playback backend、resampler、VAD mode、pre-roll、fallback、health。
   - 分通道 stats 增加 native VAD、噪声底、AGC gain、resampler、chunk latency。
8. **自动性能档位**
   - 开启 `auto_profile` 后根据 native 可用性和虚拟/loopback 输入自动选择更稳的 resampler/VAD/chunk 策略。
