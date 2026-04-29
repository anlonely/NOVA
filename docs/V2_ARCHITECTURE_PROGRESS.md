# NOVA INTERP v2 架构规划与开发进度表

生成时间：2026-04-29（Asia/Shanghai）  
目标分支：`main`  
规划原则：优先端到端低延迟，其次长期稳定、可回退、可观测、可交付。

## 1. v2 总目标

v2 不只是把 Python 采集换成 Rust 采集，而是把实时链路拆成“控制面”和“实时音频面”：

```text
Web Dashboard / Qt Shell
        |
        v
Python Control Plane
- 配置、场景、AST WebSocket、字幕、TTS、声音克隆、更新
        |
        | IPC: control JSON + audio frames + metrics
        v
Rust Realtime Audio Plane
- 设备、采集、DSP、VAD、AGC、重采样、播放、混音、热插拔、指标
```

目标状态：
- Python 不再承担高频音频 DSP，只负责业务编排与云端 AST 协议。
- Rust 原生核心常驻为单进程音频服务，统一管理多通道采集和多设备播放。
- 所有 native 功能都可灰度开启，并且能按通道回退到 Python 路径。
- UI 必须能解释“当前走哪条链路、为什么回退、瓶颈在哪里”。

## 2. 架构分层

### 2.1 UI 层

职责：
- 展示 A/B/C 通道状态、路由、字幕、延迟、设备与错误。
- 配置 capture/playback backend、VAD、pre-roll、resampler、fallback。
- 提供一键诊断信息导出。

不做：
- 不在 UI 中保存复杂音频状态机。
- 不把运行状态只写成文案，所有关键状态必须来自 Controller 快照。

### 2.2 Python Control Plane

职责：
- 读取/保存配置，校验设备与语言组合。
- 管理通道生命周期和回退策略。
- 连接火山 AST WebSocket，处理字幕、TTS 和账单事件。
- 将 native metrics 合并进统一 `runtime` 快照。

边界：
- Python 可以保留 fallback capture/playback。
- Python 不应继续扩展复杂 DSP；AGC、VAD、重采样、预卷和噪声底应逐步下沉到 Rust。

### 2.3 Rust Realtime Audio Plane

最终目标模块：
- `CoreService`：单进程服务入口，管理所有通道。
- `DeviceManager`：设备枚举、默认设备、热插拔、稳定 ID。
- `CaptureGraph`：每个输入设备一个 capture node，输出标准 PCM frame。
- `DspPipeline`：高通、降噪、AGC、VAD、noise floor、pre-roll、resampler。
- `PlaybackGraph`：每个输出设备一个 playback node，支持 fanout 与 monitor。
- `MetricsBus`：周期性输出 dB、VAD、queue、drop、xruns、device change。
- `IpcServer`：控制命令、音频帧、错误和状态事件的边界。

实时线程规则：
- 音频 callback 内不得进行 JSON 序列化、磁盘 IO、网络 IO、锁等待和动态大分配。
- callback 只做最小拷贝并写入有界 ring buffer。
- DSP worker 从 ring buffer 消费，生成固定大小 frame。
- 所有队列必须有上限，满队列时明确丢弃策略并上报指标。

### 2.4 AST / 网络层

v2 阶段保留在 Python：
- 火山 AST protobuf/WebSocket 逻辑保持在 `ast_bridge.py`。
- 自定义 DNS、代理、字幕事件、TTS 事件继续由 Python 处理。

原因：
- AST 不是当前最大性能瓶颈；贸然迁移会扩大风险面。
- 云端协议、声音克隆和 UI 状态绑定已经在 Python 内闭环。

后续可选：
- 当 native audio 稳定后，再评估是否把 AST 发送线程下沉到 Rust，以减少 Python queue 与 base64/IPC 复制。

## 3. 最优性能链路

### 3.1 目标数据流

```text
Input Device
  -> OS Audio Callback
  -> Native Ring Buffer
  -> DSP Worker
  -> 16k mono PCM16 frames
  -> Python AST Sender Queue
  -> Volcengine AST
  -> Subtitle/TTS Events
  -> Native Playback Queue
  -> Output / Monitor Device
```

### 3.2 低延迟策略

- Capture chunk：10-20ms，默认 20ms。
- AST send batch：保持 20ms 粒度，避免过大 batch 增加首字延迟。
- Pre-roll：默认 120-180ms，避免 VAD 起点截断。
- Silence hold：120-260ms，避免短停顿导致断句抖动。
- Playback startup buffer：
  - Turbo：24-40ms
  - Balanced：60-90ms
  - Studio：120-180ms
- Resampler：
  - 默认 `sinc-lite` 或等价低延迟高质量流式重采样。
  - `linear` 只作为最低 CPU fallback。
- Queue policy：
  - 采集队列满：优先丢最旧静音帧。
  - 播放队列满：保留最近译音，丢过期旧音频，避免越积越迟。

### 3.3 稳定性策略

- 默认仍可用 Python backend，native 按配置灰度。
- native 子进程必须有 heartbeat 和超时退出。
- 单通道失败不能拖垮其他通道。
- 设备热插拔后进入 degraded 状态，自动重扫并尝试恢复。
- 每次回退必须记录：
  - channel
  - backend
  - device id
  - error
  - timestamp
  - fallback result

## 4. 推荐目标架构变更

当前分支已经具备 `serve`、native capture、native playback 和 UI 参数，但仍是“每个 native capture/playback 启动一个服务子进程”的形态。为了最佳性能和稳定性，建议进入 v2.1 后改成：

1. 单 native core 进程  
   一个 `nova-audio-core serve` 常驻，统一承载 A/B/C capture 和 playback。

2. 多通道命令协议  
   命令从 `start-capture` 扩展为 `create-channel` / `update-channel` / `delete-channel` / `start-all` / `stop-all`。

3. 音频帧协议升级  
   短期保留 JSONL + base64 兼容；中期改为“JSON 控制 + binary audio frame”混合协议，降低 base64 开销。

4. 统一 device graph  
   Rust 内维护设备节点，多个通道引用设备节点，避免重复打开同一个设备造成冲突。

5. 播放混音下沉  
   TTS 和本地 clone audio 统一进入 native playback mixer，Python 只负责发送译音帧。

6. 诊断包标准化  
   一键导出 `config redacted + runtime state + native metrics + recent logs`，用于定位硬件问题。

## 5. 开发进度表

| 阶段 | 状态 | 目标 | 性能价值 | 稳定价值 | 主要文件 | 验收标准 |
|---|---|---|---|---|---|---|
| P0 基础文档与范围 | 已完成 | 明确 v2 边界和分支文档 | 避免无效重构 | 降低范围漂移 | `docs/*` | 文档覆盖 main/v2 差异 |
| P1 Native CLI | 已完成 | `list-devices` / `health` / `serve` | 建立原生服务入口 | 可独立 smoke test | `native_audio_core/src/main.rs` | CLI 返回稳定 JSON |
| P2 Native Capture MVP | 已完成 | cpal 采集、mono、PCM16、metrics | 降低 Python 采集抖动 | 出错可回退 | `native_audio_core/src/main.rs`, `audio_core_bridge.py` | native capture 可产出 `audio_chunk` |
| P3 Controller/UI 接入 | 已完成 | backend 配置、状态、UI 控件 | 用户可灰度开启 | 可见 runtime/fallback | `nova_controller.py`, `web_dashboard/*` | UI 可切换 backend 并保存 |
| P4 Native Playback MVP | 已完成 | native playback path 与 fallback | 降低 Python 播放 jitter | 播放失败回 Python | `ast_bridge.py`, `audio_core_bridge.py`, `scripts/smoke_native_audio_core.py` | native playback smoke 可进目标输出设备 |
| P5 单进程 Native Service | 已完成 | 统一管理 A/B/C 通道 | 减少进程开销和重复设备打开 | 统一 watchdog/热插拔 | `audio_core_bridge.py`, `native_audio_core/src/*` | Python bridge 共享一个 native `serve` 进程，capture/playback session 按 channel 分发 |
| P6 Binary Audio IPC | 已完成 | 控制 JSON 与音频二进制分离 | 去掉 base64 CPU/内存开销 | 降低大帧解析失败风险 | `audio_core_bridge.py`, `native_audio_core/src/*`, `scripts/smoke_native_audio_core.py` | playback/capture 音频帧均支持二进制 IPC，旧 base64 路径保留 |
| P7 Device Hotplug Recovery | 已完成 | 设备变更自动重扫和恢复 | 减少手动重启 | 长时运行恢复能力 | `native_audio_core/src/*`, `audio_core_bridge.py`, `nova_controller.py`, `web_dashboard/*` | native 服务检测完整设备快照变化；Controller/UI 暴露 degraded、affectedChannels、recoveredRoutes 与 lastDeviceChange；自动恢复开关默认关闭 |
| P8 DSP 质量增强 | 已完成 | 更稳 resampler、AGC、VAD、限幅 | 降低截断、爆音、误触发 | 参数可控且可回退 | `ast_bridge.py`, `scripts/analyze_audio_pipeline.py`, `scripts/generate_audio_fixtures.py`, `native_audio_core/src/*` | 播放链路已增加统一限幅、峰值统计和可重复音频分析/fixtures 回归脚本 |
| P9 Playback Mixer | 已完成 | 多输出 fanout、monitor、ducking 预留 | 降低播放端抖动 | 单输出失败不影响其他输出 | `ast_bridge.py`, `audio_core_bridge.py`, `native_audio_core/src/*` | Python/native playback fanout 支持主输出+监听；单输出失败会摘除该输出，其他输出继续 |
| P10 长时稳定压测 | 进行中 | 2h/8h 会话压测 | 暴露延迟漂移 | 验证内存/线程/设备稳定 | `scripts/stress_native_audio_core.py` | 已具备可调时长 native service playback 压测入口；待执行 2h/8h soak |
| P11 发布打包闭环 | 进行中 | Windows/macOS 包含 native core | 性能能力可交付 | 安装包路径稳定 | `nova_interp.spec`, `scripts/build_macos.sh`, `scripts/build_windows.ps1`, `scripts/verify_release_bundle.py` | macOS PyInstaller 包已验证包含可执行 native core；Windows 脚本已强校验，待 Windows 环境实跑 |
| P12 诊断导出 | 已完成 | 导出脱敏运行包 | 缩短排障时间 | 商业交付必要 | `nova_controller.py`, UI | 现有导出按钮生成脱敏 diagnostic-session JSON，包含配置、native 状态、runtime、设备、日志尾部和转写 |

## 6. 推荐迭代节奏

### Sprint 1：稳定当前 v2 MVP

目标：把现有分支打磨成可测试版本。

- 修正 native playback 实测问题。
- 补充 `cargo build --release`、`python -m py_compile`、`node --check` 验证脚本。
- 给 native capture/playback 增加最小 smoke test。
- UI 增加“当前生效 backend”与“最近 fallback 原因”。

验收：
- Python backend 默认可用。
- Native capture 可开启，可失败回退。
- 所有配置可保存并重启恢复。
- `scripts/smoke_native_audio_core.py` 可验证 health、device snapshot、native playback；加 `--with-capture` 可验证短采集。

### Sprint 2：单 native service 重构

目标：从每通道子进程转为单服务多通道。

- `NativeAudioCoreBridge` 改为单例服务进程。
- Rust core 维护 channel registry。
- 支持 `create-channel` / `start-channel` / `stop-channel` / `shutdown`。
- 通道失败隔离，单通道错误只关闭对应 node。

验收：
- A/B/C 同时 native capture 不重复启动 3 个服务进程。
- 停止某个通道不影响其他通道。

### Sprint 3：性能协议升级

目标：降低 JSONL/base64 在音频热路径中的开销。

- 控制命令继续 JSON。
- audio frames 走 length-prefixed binary。
- metrics 仍可 JSON，频率限制 4-10Hz。
- 增加队列水位和 dropped frame 统计。

验收：
- CPU 占用低于 JSONL/base64 版本。
- 连续 30 分钟无 IPC 解析错误。

### Sprint 4：设备恢复与发布验证

目标：让 v2 成为可交付架构。

- 设备热插拔恢复。
- 自动重连和 degraded UI 状态。
- 诊断包导出。
- Windows/macOS 打包验证。
- 长时压测。

验收：
- 2 小时混合场景运行无崩溃。
- 虚拟声卡断开后能自动提示并恢复或稳定回退。

## 7. 技术决策建议

| 决策项 | 建议 | 原因 |
|---|---|---|
| AST 是否迁移 Rust | 暂不迁移 | AST 不是当前主要瓶颈，迁移会扩大风险 |
| Native core 形态 | 单进程服务 | 减少进程开销和设备冲突 |
| IPC | 先 JSONL，后 binary frame | 当前易调试，后续优化热路径 |
| 默认 backend | Python | 商业交付必须优先稳定 |
| Native 开启策略 | 按通道灰度 | 设备差异大，不能全局强推 |
| DSP 所属 | Rust | DSP 是实时路径，应远离 Python GIL |
| UI 状态 | 统一来自 Controller | 避免 UI 与运行状态分叉 |

## 8. 关键验收指标

性能：
- Turbo 模式首音频上行延迟稳定在 20-60ms 本地链路内。
- 采集队列不持续增长，丢帧只发生在静音或过期帧。
- Native capture CPU 占用低于 Python capture 路径。

稳定：
- 单通道 native 失败可回 Python。
- 设备热插拔不会导致应用崩溃。
- 停止/重启通道不遗留子进程或音频流。
- 长时运行无内存持续增长。

可观测：
- 每个通道能看到 capture backend、playback backend、queue、drop、dB、VAD、fallback。
- 每次 native error 都有最近 stderr 和 runtime snapshot。
- 导出的会话包可复盘配置、设备、错误与延迟。

## 9. 当前开发记录

### 2026-04-29

已完成：
- 过滤 native device snapshot 中 `channels=0` / 空采样率的无效输入输出设备。
- 修正 native device stable id 生成与 `start-capture` / `start-playback` 查找逻辑不一致的问题。
- 修正 `capture_started.channel` 错误返回设备 id 的问题，现在返回业务 channel，并单独返回 `device_id`。
- native playback 增加输出采样格式兼容（`f32` / `i16` / `u16`）。
- native playback 增加播放输入采样率到实际设备输出采样率的线性重采样，避免设备不支持目标采样率时播放变速。
- Rust `serve` 从单 capture/playback slot 改为按 channel 管理多个 capture/playback runtime。
- `stop-capture` / `stop-playback` 支持可选 `channel`，不传 channel 时保留“停止全部”的兼容行为。
- 新增 `scripts/smoke_native_audio_core.py`，覆盖 health、list-devices、playback、multi-playback、可选 capture smoke。
- `audio_core_bridge.py` 改为共享 native service：`NativeAudioCoreBridge` 按 binary 复用一个 `nova-audio-core serve` 进程，session 只注册/注销 channel，不再各自启动子进程。
- capture events 按业务 channel 分发；playback session 使用内部唯一 runtime channel，保留同一业务通道同时输出到主设备与 monitor 设备的能力。

验证：
- `cargo build --release` 通过。
- `node --check web_dashboard/dashboard.js` 通过。
- `python3 -m py_compile` 通过。
- `python3 scripts/smoke_native_audio_core.py` 通过。
- `python3 scripts/smoke_native_audio_core.py --multi-playback` 通过。
- `python3 scripts/smoke_native_audio_core.py --with-capture --capture-device 'input::MacBook Pro麦克风::1' --capture-duration-ms 200` 通过。
- 通过 `audio_core_bridge.py` 共享服务 API 启动两个 playback session 并发送音频，通过。
- 通过 `audio_core_bridge.py` 共享服务 API 启动 capture session 并读取 `audio_chunk`，通过。

### 2026-04-29 P6 进展

已完成：
- Rust `serve` 新增 `playback-chunk-binary` 命令：JSON 控制头包含 `channel`、`sample_rate`、`byte_len`，随后紧跟 PCM16 原始字节。
- 旧 `playback-chunk` base64 命令保留，确保兼容旧调用和调试脚本。
- `audio_core_bridge.py` 的 `NativePlaybackSession.send_audio()` 改为默认发送二进制 playback frame。
- `scripts/smoke_native_audio_core.py` 新增 `--binary-playback`，可分别验证 base64 与 binary playback 路径。
- Rust capture 新增可选 `audio_chunk_binary` 输出：JSON header 后紧跟 PCM16 原始字节。
- `audio_core_bridge.py` 启动 native capture 时默认请求 binary audio events，并在 stdout reader 中转换回上层兼容的 `audio_chunk` + `pcm16`。
- `scripts/smoke_native_audio_core.py` 新增 `--bridge-api`，覆盖 Python bridge 共享服务路径下的 binary playback/capture。

验证：
- `cargo build --release` 通过。
- `python3 -m py_compile audio_core_bridge.py scripts/smoke_native_audio_core.py` 通过。
- `python3 scripts/smoke_native_audio_core.py` 通过。
- `python3 scripts/smoke_native_audio_core.py --binary-playback` 通过。
- `python3 scripts/smoke_native_audio_core.py --multi-playback --binary-playback` 通过。
- 通过 `audio_core_bridge.py` API 启动两个 playback session 并发送二进制音频，通过。
- `python3 scripts/smoke_native_audio_core.py --with-capture --capture-device 'input::MacBook Pro麦克风::1' --capture-duration-ms 200 --binary-playback` 通过。
- `python3 scripts/smoke_native_audio_core.py --bridge-api --with-capture --capture-device 'input::MacBook Pro麦克风::1'` 通过。
- `node --check web_dashboard/dashboard.js` 通过。
- 全量 Python `py_compile` 通过。

下一步：
- 开始 P7：设备热插拔恢复和 degraded 状态建模。

### 2026-04-29 P7 进展

已完成：
- Rust device watcher 从“只比较设备数量”改为比较完整设备快照签名，覆盖设备名、ID、输入输出类型、通道数、采样率和虚拟设备标记变化。
- Rust `devices_changed` 事件增加 `previous_device_count` 与 `device_count`，便于 Controller/UI 展示变化。
- `audio_core_bridge.py` 增加 `drain_events()`，Controller 可读取 native service 的全局事件。
- bridge 全局事件队列只接收服务级事件，避免高频 channel 音频事件进入全局队列。
- `nova_controller.py` 增加 `native_audio_last_device_change`、`native_audio_degraded_reason`，在 `get_state()` / `poll_state()` 前消化 native 事件。
- `nativeAudioCore` 状态增加 `degraded`、`degradedReason`、`lastDeviceChange`。
- Dashboard 平台状态展示 degraded、设备变化时间与降级原因。
- Controller 在设备变化后刷新 Python 设备目录但不静默改用户路由；如运行通道绑定的输入/输出/监听设备缺失，会按通道写入 `Audio device unavailable` 错误。
- `nativeAudioCore` 状态增加 `affectedChannels`，Dashboard 平台状态展示受影响通道。
- 增加 `audio_core.device_auto_recover` / `audio-device-auto-recover`，默认关闭；开启后设备变化会按旧设备名称优先恢复缺失路由，找不到同名设备再按通道默认设备回退。
- `nativeAudioCore` 状态增加 `deviceAutoRecover` 与 `recoveredRoutes`，Dashboard 平台状态展示自动恢复开关和恢复结果。
- 运行中的通道如果发生路由恢复，只标记 `Route Recovered` 并提示重启通道生效，不在后台静默断开或重建会话。

验证：
- `cargo build --release` 通过。
- `node --check web_dashboard/dashboard.js` 通过。
- 全量 Python `py_compile` 通过。
- `python3 scripts/smoke_native_audio_core.py --bridge-api --with-capture --capture-device 'input::MacBook Pro麦克风::1'` 通过。
- `python3 scripts/smoke_native_audio_core.py --multi-playback --binary-playback` 通过。
- `python3 scripts/smoke_native_audio_core.py --with-capture --capture-device 'input::MacBook Pro麦克风::1' --capture-duration-ms 200 --binary-playback` 通过。
- 使用 `.venv/bin/python` 实例化 `NovaController` 并确认 `nativeAudioCore` 输出包含 `degraded`、`degradedReason`、`lastDeviceChange`、`deviceCount`。
- 使用 `.venv/bin/python` 模拟 A 通道输入/输出设备缺失，确认 `nativeAudioCore.degraded=true`、`affectedChannels` 和通道错误状态正确输出。
- 使用 `.venv/bin/python` 模拟旧设备 ID 消失但同名设备重新出现，确认 `audio-device-auto-recover=1` 时可恢复 A 通道输入/输出路由，且 `affectedChannels=0`。

待继续：
- P8 DSP 质量增强：补录音样本回放验证，比较 AGC/VAD/denoise 参数下的削波、截字和误触发情况。

### 2026-04-29 P8 进展

已完成：
- 播放链路增加统一 `apply_playback_limiter()`，在音频进入播放队列前做 NaN/Inf 清理、峰值检测和 0.98 ceiling 限幅。
- 限幅接入 `_enqueue_playback_audio()`，因此 Python playback 与 native playback 共用同一保护路径。
- `ChannelStats` 增加 `playback_limiter_events`、`playback_limiter_reduction_db`、`playback_peak_dbfs`，可在现有 `runtime.channels.*.stats` 中观察削波风险。
- Dashboard 队列 chip 增加 Limiter/限幅计数展示。
- 新增 `scripts/analyze_audio_pipeline.py`，支持 WAV 输入或内置合成压力样本，输出 input/processed/VAD/limiter JSON 指标。
- 分析脚本可选 `--agc` / `--denoise`，用于对比 AGC、降噪、噪声门与 limiter 的组合效果。
- 分析脚本支持目录批量扫描 WAV，并提供 `--max-clipped-after` / `--max-peak-after-dbfs` 阈值退出码，便于后续接入 CI 或 P10 长时压测报告。

验证：
- `node --check web_dashboard/dashboard.js` 通过。
- 排除构建目录后的全量 Python `py_compile` 通过。
- 使用 `.venv/bin/python` 构造超过 0 dBFS 的 float32 payload，确认 limiter 触发且输出峰值不超过 0.98。
- `python3 scripts/smoke_native_audio_core.py --multi-playback --binary-playback` 通过。
- `.venv/bin/python scripts/analyze_audio_pipeline.py` 通过；合成压力样本从 `peakBeforeDbfs=2.5` 限幅到 `peakAfterDbfs=-0.2`，`clippedAfter=0`。
- `.venv/bin/python scripts/analyze_audio_pipeline.py --agc --denoise --duration-sec 1.5 --chunk-ms 20` 通过，输出 AGC 末端增益、speech/silent chunk 比例与 limiter 状态。
- `.venv/bin/python scripts/analyze_audio_pipeline.py --max-clipped-after 0 --max-peak-after-dbfs 0` 通过，确认阈值模式可用于自动化判定。

待继续：
- P10 长时稳定压测：增加 2h/8h 会话压测脚本，观察队列、drop、limiter、输出故障与 native service 健康。

### 2026-04-29 P10 进展

已完成：
- 新增 `scripts/stress_native_audio_core.py`，可按 `--duration-sec`、`--channels`、`--chunk-ms` 对 native service 进行可调时长 playback 压测。
- 压测脚本复用 native `serve` 二进制 IPC，持续发送 PCM16 binary playback frame，并统计 `playback_queued`、`devices_changed`、`error`、stderr 与退出状态。
- 默认短时可本机快速跑；同一脚本可通过 `--duration-sec 7200` / `--duration-sec 28800` 用于 2h/8h soak。
- 压测脚本增加周期 samples、native 进程 RSS、ack backlog、失败原因列表和 `--report-json` 报告输出。
- 压测脚本增加 `--max-ack-backlog` 与 `--max-rss-growth-kb` 阈值，可用退出码判断 soak 是否失败。
- 压测脚本增加 `--with-capture`，可在 playback 压测同时启动 native capture，并统计 `audio_chunk`、`metrics`、最大 dropped silent 与 capture queue depth。
- 压测脚本增加 `--profile quick|preflight|soak-2h|soak-8h`，统一短测、60 秒预检和 2h/8h soak 参数。
- 修复 native playback 24kHz 译音电流噪声：AST 24kHz PCM 为 float32，而 Rust binary playback IPC 按 PCM16 解码；现在 Python 进入 native playback IPC 前统一转换为 PCM16。
- 压测脚本默认改为静音播放，避免稳定性测试期间向系统扬声器持续输出测试音；如需听感检查可显式设置 `--tone-amplitude`。

验证：
- `.venv/bin/python scripts/stress_native_audio_core.py --duration-sec 3 --channels 2 --report-interval-sec 2` 通过，3.328 秒内发送/确认 `242/242` 个 playback chunks，`errors=[]`，`stderr=""`。
- `.venv/bin/python scripts/stress_native_audio_core.py --duration-sec 4 --channels 2 --report-interval-sec 1 --report-json output/stress_native_audio_core_report.json --max-ack-backlog 64 --max-rss-growth-kb 65536` 通过，4.518 秒内发送/确认 `328/328` 个 playback chunks，`maxAckBacklog=2`，`rssGrowthKb=0`，`failures=[]`。
- `.venv/bin/python scripts/stress_native_audio_core.py --duration-sec 2 --channels 1 --with-capture --report-interval-sec 1 --report-json output/stress_native_audio_core_capture_report.json --max-ack-backlog 64` 通过，采集 `audio_chunk=99`、`metrics=9`，`maxDroppedSilentChunks=0`，`maxCaptureQueueDepth=0`，`failures=[]`。
- `.venv/bin/python scripts/stress_native_audio_core.py --profile quick --channels 2 --with-capture --report-json output/stress_native_audio_core_quick_profile.json --max-ack-backlog 64 --max-rss-growth-kb 65536` 通过，发送/确认 `330/330` 个 playback chunks，`captureChunks=201`，`maxAckBacklog=2`，`rssGrowthKb=320`，`failures=[]`。
- `.venv/bin/python scripts/stress_native_audio_core.py --profile preflight --channels 2 --with-capture --report-json output/stress_native_audio_core_preflight.json --max-ack-backlog 64 --max-rss-growth-kb 65536` 通过，61.978 秒内发送/确认 `4964/4964` 个 playback chunks，`captureChunks=2957`，`captureMetrics=243`，`maxAckBacklog=2`，`rssGrowthKb=0`，`failures=[]`。
- 使用 `.venv/bin/python` 定向验证 24kHz float32 playback payload 会转为 PCM16 后再进入 native IPC，避免 Rust 侧按 PCM16 误解 float32 字节。
- `.venv/bin/python scripts/stress_native_audio_core.py --profile quick --channels 1 --report-json output/stress_native_audio_core_silent_quick.json --max-ack-backlog 64 --max-rss-growth-kb 65536` 通过，默认静音压测发送/确认 `164/164` 个 playback chunks。
- 排除构建目录后的全量 Python `py_compile` 通过。
- `node --check web_dashboard/dashboard.js` 通过。

待继续：
- 执行更长时间的 2h/8h soak，或先增加 Controller/runtime 级别的长时状态采样导出。

### 2026-04-29 P11 进展

已完成：
- `scripts/build_macos.sh` 不再在缺少 Cargo/native core 时静默跳过，打包前强制构建并校验 `native_audio_core/target/release/nova-audio-core` 可执行。
- `scripts/build_windows.ps1` 不再在缺少 Cargo/native core 时静默跳过，打包前强制构建并校验 `native_audio_core\target\release\nova-audio-core.exe` 存在。
- 新增 `scripts/verify_release_bundle.py`，验证 PyInstaller dist 或 macOS `.app` 中包含 `native_audio_core/target/release/nova-audio-core(.exe)`。
- macOS/Windows build 脚本在 PyInstaller 后调用 release bundle 校验，避免产出缺 native core 的包。

验证：
- `cargo build --release` 通过。
- `bash -n scripts/build_macos.sh` 通过。
- 排除构建目录后的全量 Python `py_compile` 通过。
- `node --check web_dashboard/dashboard.js` 通过。
- 使用临时 bundle fixture 验证 `scripts/verify_release_bundle.py --dist-path output/verify_bundle_fixture` 可找到 native core。

待继续：
- 执行完整 macOS PyInstaller 打包，并对 `dist/NOVA INTERP.app` 运行 bundle 校验。
- 在 Windows 环境执行 `scripts/build_windows.ps1` 完整打包与 bundle 校验。

### 2026-04-29 P11 验证补充

验证：
- `.venv/bin/python -m PyInstaller --noconfirm --clean nova_interp.spec` 完整 macOS 构建通过，生成 `dist/NOVA INTERP.app`。
- `.venv/bin/python scripts/verify_release_bundle.py --dist-path 'dist/NOVA INTERP.app'` 通过，确认 `.app` 内包含 `Contents/Resources/native_audio_core/target/release/nova-audio-core`。
- 打包后的 `nova-audio-core health` 返回 `{"backend":"coreaudio","ok":true}`。

待继续：
- Windows 环境执行 `scripts/build_windows.ps1` 完整打包与 bundle 校验。
- P12 诊断导出：导出脱敏运行包，包含配置、native 状态、runtime stats、错误和最近日志。

### 2026-04-29 P12 进展

已完成：
- `export_session()` 从普通会话导出升级为 `diagnostic-session-*.json` 诊断包。
- 诊断包 schema 为 `nova-diagnostic-session-v2`，包含版本、场景、脱敏凭证、配置、网络、设备摘要、native audio core 状态、voice clone、updater、runtime、通道 stats、转写和最近日志尾部。
- 凭证 `appId` / `accessToken` / `secretKey` 做遮罩；voice clone 样本路径只保留文件名。
- 复用现有 Dashboard “导出会话”按钮，不新增用户操作入口。

验证：
- 排除构建目录后的全量 Python `py_compile` 通过。
- `node --check web_dashboard/dashboard.js` 通过。
- 使用 `.venv/bin/python` 实例化 `NovaController` 并执行 `export_session()` 通过，生成 `output/diagnostic-session-*.json`。
- 验证导出文件不包含明文 `accessToken` / `secretKey`，并包含 `nativeAudioCore` 与 `nova-diagnostic-session-v2`。

待继续：
- Windows 环境执行 `scripts/build_windows.ps1` 完整打包与 bundle 校验。
- 根据真实用户问题样本完善诊断包字段，例如系统音频设备权限、macOS/Windows 音频后端版本和最近 native stderr。

### 2026-04-29 P9 进展

已完成：
- Python playback fanout 已保留主输出 + monitor 双输出队列。
- Python playback 输出 worker 报错后不再触发整条播放链路失败；Controller 会摘除失败输出队列，剩余输出继续播放。
- 仅当所有 Python playback 输出都失败时，才抛出 `All playback outputs failed` 并停止播放。
- Native playback 多 session 发送失败时会关闭并移除失败 session，剩余 native playback session 继续接收音频。
- `ChannelStats` 增加 `playback_active_outputs`、`playback_output_failures`、`playback_failed_outputs`，Dashboard 队列 chip 展示输出失败计数。

验证：
- 排除构建目录后的全量 Python `py_compile` 通过。
- `node --check web_dashboard/dashboard.js` 通过。
- `python3 scripts/smoke_native_audio_core.py --multi-playback --binary-playback` 通过。
- 使用 `.venv/bin/python` 定向模拟 monitor 输出失败，确认 primary 队列保留、失败计数增加；再模拟 primary 失败，确认全部输出失败时才抛错。

待继续：
- P10 长时稳定压测：增加 2h/8h 会话压测脚本，观察队列、drop、limiter、输出故障与 native service 健康。

### 2026-04-29 P8 收尾

已完成：
- 新增 `scripts/generate_audio_fixtures.py`，生成确定性 WAV 回归样本到 `output/audio_fixtures/`。
- fixtures 覆盖低音量、爆音、强噪声、短句起音、长静音后短语五类压力场景。
- `scripts/analyze_audio_pipeline.py` 显式传入空目录时会失败，避免误回退到 synthetic 样本。

验证：
- `.venv/bin/python scripts/generate_audio_fixtures.py` 通过，生成 5 个 WAV fixtures。
- `.venv/bin/python scripts/analyze_audio_pipeline.py --input output/audio_fixtures --max-clipped-after 0 --max-peak-after-dbfs 0` 通过，5 个样本 `totalClippedAfter=0`，最大限幅后峰值 `-0.2 dBFS`。
- `.venv/bin/python scripts/analyze_audio_pipeline.py --input output/audio_fixtures --agc --denoise --max-clipped-after 0 --max-peak-after-dbfs 0` 通过，AGC/denoise 组合后 `totalClippedAfter=0`。
- 排除构建目录后的全量 Python `py_compile` 通过。
- `node --check web_dashboard/dashboard.js` 通过。

待继续：
- P9 Playback Mixer：实现播放 fanout 的故障隔离，单输出失败不影响其他输出。

### 2026-04-30 P13 桌面弹窗/桥接修正（按顺序执行）

目标：把你提到的桌面弹窗稳定性与性能优化一次性收敛成可交付序列。

执行顺序与状态：

1. [x] 任务 A：弹窗桥接调用的参数鲁棒性（Payload 防御）
   - 覆盖 `open_transcript_window / close_transcript_window / is_transcript_window_open / set_transcript_window_topmost` 的 JSON 反序列化失败与非法类型保护；
   - 统一错误码返回（`invalid_payload`）；
   - 降低前端传参异常导致窗口管理链路中断的概率。

2. [x] 任务 B：弹窗窗口生命周期状态收口
   - 统一入口透传 `alias` 与 `lang`；
   - 窗口标题按语言和通道保持一致；
   - 关闭回调与字典状态清理路径不重叠，避免“UI 以为窗口关闭、窗口字典未清”的状态漂移。

3. [x] 任务 C：弹窗轮询降载（性能）
   - `transcript_window.js` 引入动态轮询策略（活跃态快轮询、空闲态降频）；
   - 活跃态保持近实时状态更新，空闲态显著减少不必要的 `poll_state`；
   - 页面退出前清理定时器，避免窗口关闭后残留任务。

4. [x] 任务 D：维护性收敛
   - i18n 文案尽量集中在单一字典；
   - 标题、按钮提示、空状态文案与主界面语言一致；
   - 作为下一步：整理 popup 文案与 `dashboard.js` 的通用翻译入口复用（不影响当前发布）。

5. [x] 任务 E：渲染稳定性与性能收敛
   - 在 `transcript_window.js` 增加快照差分状态，短时间无变化时跳过 `innerHTML` 与文本重设；
   - 消除重复首轮轮询路径，降低空转重绘带来的 UI 抖动；
   - 对 `transcripts` 与 `partial` 数据结构做健壮性兼容，避免异常结构导致前端抛错。

6. [x] 任务 F：验证闭环
   - `python3 -m py_compile desktop_webview.py`
   - `node --check web_dashboard/transcript_window.js`
   - `node --check web_dashboard/dashboard.js`
   - 用桌面端打开 popup，切换中英，验证窗口标题与按钮文案随语言变更且不闪退。

当前进度：
- 已按顺序完成任务 A/B/C/D/E 的代码落地；
- 任务 F 已完成：语法检查通过；
- 下一步请在桌面端执行验收：
  - 弹窗标题与按钮文案跟随语言（中/英）更新；
  - 置顶/关闭按钮独立窗口可用；
  - 长时运行下 CPU 与无效重绘抖动明显降低；
  - 手工验证 `poll_state` 在空闲通道下不被空转拉高。
