# NOVA INTERP 产品文档（历史版本：native-audio-core-v2）

说明：此文档保存 `native-audio-core-v2` 设计期内容，作为 `main`（当前主线）与 `old_v1` 对照的历史档案，生成时间：2026-04-29（Asia/Shanghai）。

## 1. 分支定位

该分支在 `main` 的基础上落地“原生音频核心可选链路”，目标是把高频链路中的采集/播放能力从 Python 迁移到 Rust 核心，同时保留自动回退和观测能力，降低语音延迟与稳定性风险。

- 语音链路主变更：新增原生采集/播放后端 (`capture_backend` / `playback_backend`) 可配置
- 风险控制：异常时自动回退到 Python 路径，保障可用性
- 可观测性：新增 native 端指标（VAD、噪声底、AGC、重采样、chunk 延迟）进入状态面板

## 2. 与 main 的新增价值

- 支持 `native` 与 `python` 双采集后端的运行时切换
- 支持 `native` 与 `python` 双播放后端切换（含原生多设备广播）
- 引入可配置的 native 音频参数：
  - pre-roll（0~600ms）
  - 重采样策略（`linear` / `sinc-lite`）
  - VAD 模式（`adaptive` / `gate`）
  - 自适应噪声底、AGC、分片策略等
- 增强更新与状态层：`_native_audio_state` 扩展健康、后端、参数快照
- 在 UI 平台设置页增加音频核心高级开关与状态说明
- Rust core 功能从“设备枚举”扩展为“服务化采集/播放协议 + 健康接口”

## 3. 系统架构（v2）

- 桌面壳层：`desktop_webview.py`
  - 增加图标资源挂载，保持单实例机制不变
- 控制层：`nova_controller.py`
  - 新增音频内核全局配置字段：`audio_core` 区段持久化/加载
  - `get_state()` 中加入 `nativeAudioCore` 扩展状态：运行后端、回退开关、健康与参数
- 通道层：`ast_bridge.py`
  - `ChannelSettings` 新增：
    - `capture_backend`（`python|native`）
    - `native_capture_fallback`
    - `pre_roll_ms`
    - `resampler_quality`
    - `vad_mode`
    - `enable_noise_floor`
    - `adaptive_chunking`
    - `playback_backend`（`python|native`）
  - `TranslationChannel` 的采集/播放逻辑按配置路由：
    - Native 模式调用 `NativeAudioCoreBridge`
    - Native 失败按配置可回退 Python 模式
  - 采集事件解析新增：
    - audio_chunk -> `stats` 中更新音量、VAD、噪声底、AGC、chunk 延迟
    - metrics -> 持续刷新通道状态（用于 UI 指标）
- 桥接层：`audio_core_bridge.py`
  - 新增 `start_capture` / `start_playback` 子进程会话与事件读取
  - 支持 stderr 捕捉、`ready/ok/error` 解析、幂等关闭
- 原生服务：`native_audio_core/src/main.rs`
  - 命令：
    - `list-devices`
    - `health`
    - `serve`（长期 JSONL 流式服务）
  - `serve` 命令支持：
    - start-capture / stop-capture
    - start-playback / playback-chunk / stop-playback / shutdown
    - 采集端口事件：`ready`、`capture_started`、`audio_chunk`、`metrics`、`error`
    - 播放端口事件：`playback_started`、`playback_queued`、`ok`、`shutdown`
  - DSP 与采集增强：
    - 多采样格式输入转换（f32/i16/u16）
    - mono 混合
    - 简化 resample（sinc-lite / linear）
    - VAD 与自适应片段机制
    - pre-roll + silence hold + 预静音丢弃统计
    - queue 与 metrics 周期输出

## 4. 核心用户流程（v2）

### 4.1 Native + 回退链路

1. 用户在 UI 选择 `audio-capture-backend` 与 `audio-playback-backend`
2. 启动通道后，`TranslationChannel` 在 `_capture_audio()` 中按配置选择 native 或 python 采集
3. native path 启动成功：
   - 读取 `native` 事件并转为内部 PCM 队列
   - 结合 AST 发送逻辑与播放逻辑
4. native path 失败且 `native_capture_fallback=on`：
   - 通知并切换为 Python path（继续会话，不中断主流程）
5. UI 即时显示 `runtime` 与 `captureBackend`，可观察故障原因

### 4.2 可配置性能策略

- 用户可通过平台设置启停：
  - `audio-pre-roll-ms`
  - `audio-resampler-quality`
  - `audio-vad-mode`
  - `audio-noise-floor`
  - `audio-adaptive-chunking`
  - `audio-auto-profile`（根据 native 健康与虚拟输入自动调整）
- `audio-auto-profile` 开启时可动态调节：
  - 强化 native 路径参数
  - 在检测到虚拟输入时优先启用噪声底

## 5. 关键接口与数据面

### 5.1 配置文件（`config.local.json`）

新增 `audio_core` 段（当前分支默认值）：  

- `capture_backend: "python"`
- `native_capture_fallback: true`
- `pre_roll_ms: 160`
- `resampler_quality: "sinc-lite"`
- `vad_mode: "adaptive"`
- `enable_noise_floor: true`
- `adaptive_chunking: true`
- `playback_backend: "python"`
- `auto_profile: true`

### 5.2 状态暴露（Controller）

`get_state()["nativeAudioCore"]` 额外返回：

- `available`：native 二进制是否存在
- `runtime`：当前生效路径（native 成功/失败后的 python）
- `captureBackend` / `playbackBackend`
- `fallbackEnabled`
- `preRollMs`、`resamplerQuality`、`vadMode`
- `noiseFloorEnabled`、`adaptiveChunking`、`autoProfile`
- `health`：`{ok, backend, error}`（定期刷新）
- `binaryPath`、`deviceCount`、`lastSnapshot`

### 5.3 Dashboard 新增字段

- 平台设置新增控件：
  - Capture Backend、Playback Backend 下拉
  - Pre-roll 输入框
  - Resampler / VAD 模式下拉
  - 回退开关、Adaptive Noise Floor、Adaptive Chunking、Auto Profile
  - 音频核心状态说明行（当前 backend、参数、回退、健康）
- 路由详情新增展示原生 VAD 指标（如有）

## 6. 性能与稳定性目标

- 目标场景：Discord 语音、游戏语音、会议通道同时运行
- v2 的性能增益点：
  - 采样链路低抖动控制（线程优先级、queue 管理、分片策略）
  - native 音频预处理可减少 Python runtime 波动引入的抖动
- 风险点：
  - native 子进程与 UI 的生命周期协作（启动超时、回收时机）
  - Linux 平台与少数 Windows 驱动上的行为差异
  - 长时会话中的 queue 漏斗与断链恢复策略还需稳定性验证

## 7. 交付验证建议（v2）

1. 设备发现：`list-devices` 与 `health` 可用
2. Native capture 正常：启动后 `ready -> capture_started -> audio_chunk`
3. 播放通路兼容：`playback-chunk` 进入目标设备并无异常音质退化
4. 回退链路：模拟 native 启动失败，确认 Python 无感切换
5. UI 联动：参数修改后 `get_state()` 与 `renderPlatformState` 生效
6. 打包：`scripts/build_macos.sh` 与 `scripts/build_windows.ps1` 可产出可运行产物

## 8. 版本边界

本分支仍保留原生核心与 Python 代码并行的策略，未强制所有终端都走 native；因此是“渐进式迁移”而非一次性大迁移，适合分阶段灰度与问题闭环。
