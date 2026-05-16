# NOVA Discord 中英双通道精简版规划文档

生成日期：2026-05-16  
目标仓库：`anlonely/NOVA`  
目标形态：只保留 Discord 中英双通道实时语音翻译，删除或隐藏其余场景与功能。

## 1. 核心目标

把 NOVA 从“三通道通用实时翻译控制台”收敛成一个极简、低延迟、高稳定的 Discord 专用工具：

- 我方通道：我的麦克风中文输入 -> 英文翻译语音输出到 Discord，译音使用我的音色。
- 对方通道：Discord 对方英文输入 -> 中文翻译语音输出到本地监听，译音使用对方音色。
- 只保留中英双向：中文 -> 英文、英文 -> 中文。
- 优先目标：稳定、低延迟、低 CPU、长时间运行不崩、不越跑越慢。
- 删除目标：游戏通道、会议场景、多语种场景、复杂场景预设、更新器、旧 Tk UI、非必要导出/演示/商业化文档入口。Rust 游戏翻译热词和术语表需要保留，用于提升 Discord 游戏语音里的识别与翻译稳定性。

## 2. 当前仓库判断

当前代码已经具备可复用基础：

- `desktop_webview.py`：PySide6 桌面壳和 JS/Python 桥。
- `web_dashboard/`：三通道 Web 控制台。
- `nova_controller.py`：配置、设备、通道生命周期、声音复刻、诊断状态。
- `ast_bridge.py`：Volcengine AST WebSocket，音频采集、翻译、TTS 播放、重连、队列。
- `voice_clone_manager.py`：声音复刻训练、状态查询、克隆 TTS。
- `native_audio_core/` + `audio_core_bridge.py`：Rust 原生音频核心，适合保留作为性能和稳定性的主链路。

需要重点注意：

- 当前 `CHANNEL_MAP` 是 A/B/C：`outbound`、`inbound`、`game_inbound`，C 通道应删除。
- 当前 `SCENE_TEMPLATES` 包含 Discord、字幕优先、Studio Demo 等，精简版只保留 Discord。
- 当前 `LOCAL_CLONE_TTS_LANGUAGES = {"en"}`，意味着“我方中文 -> 英文克隆音色”已有路线，但“对方英文 -> 中文克隆音色”需要打开并验证中文克隆 TTS。
- 如果 Discord 音频是系统混音/虚拟声卡输入，多个远端用户会被混在一起，无法自动知道谁是谁。若要“每个对方都用自己的音色”，必须改成 Discord Bot/SDK 方式按用户分轨采集；如果只是一名对方，当前双通道模型足够。

## 3. 保留范围

必须保留：

- 双通道运行核心：A `outbound`、B `inbound`。
- Volcengine AST 流式识别、翻译、TTS 或字幕输出。
- 声音复刻训练、Speaker ID 管理、克隆 TTS。
- 音频设备选择：麦克风、Discord 虚拟声卡/Loopback、输出设备。
- Rust native audio core、Python fallback、设备热插拔检测、基础诊断。
- Windows 打包脚本和最小运行脚本。

保留但大幅简化：

- Web Dashboard：只显示两个通道、启动/停止、设备、音色、延迟、状态。
- 字幕窗口：可保留为故障排查/辅助阅读，但不作为核心卖点扩展。
- 诊断导出：保留脱敏日志和状态快照，删除复杂商业化信息。

删除或隐藏：

- C 通道 / game voice 入口。Rust 游戏翻译热词本身保留，但不作为独立游戏通道入口展示。
- 非 Discord 场景模板。
- 多语种选择，只保留 zh/en。
- 更新器 `updater.py` 和相关 UI。
- 旧 Tk UI 已移除；`app.py` 和 `launch_legacy_tk.ps1` 只保留兼容转发到 Web/Qt 主界面。
- 复杂域词包 UI，只保留一个 Discord 固定上下文、Rust 游戏热词/术语表和可选自定义热词文本框。
- 过多文档、商业计划、演示脚本入口，不进入最终发布包。

## 4. 目标架构

```text
我的麦克风
  -> Native/Python Capture
  -> AST 识别翻译 zh -> en
  -> 我的英文克隆音色 TTS
  -> 虚拟麦克风 / Discord 输入

Discord 输出 / 虚拟声卡 / Loopback
  -> Native/Python Capture
  -> AST 识别翻译 en -> zh
  -> 对方中文克隆音色 TTS
  -> 我的耳机 / 本地监听
```

推荐链路策略：

- 默认 capture/playback 使用 `native`，失败自动回退 `python`。
- 采集统一 16kHz mono PCM16，chunk 20ms。
- 播放默认 16kHz，追求速度优先；如音质优先可在设置里切 24kHz，但不作为默认。
- 对实时语音，优先使用 AST 流式 TTS；需要克隆音色时，如果 AST 支持克隆 Speaker ID 直出，走 AST s2s 快速路径；否则走 s2t + 本地克隆 TTS，稳定但会等句尾，延迟更高。

## 5. 音色方案

### 单对单 Discord

配置两个固定音色档案：

- `self_voice_profile`：我的声音复刻 Speaker ID，用于 A 通道中文 -> 英文。
- `remote_voice_profile`：对方声音复刻 Speaker ID，用于 B 通道英文 -> 中文。

配置落地：

```json
{
  "voice_profiles": {
    "self": {
      "speaker_id": "S_xxx",
      "target_channel": "outbound"
    },
    "remote_default": {
      "speaker_id": "S_yyy",
      "target_channel": "inbound"
    }
  }
}
```

### 多人 Discord

如果只是读取 Discord 混音输出，无法稳定区分每个远端用户的音色。要做到多人各自音色，需要后续加一个 Discord Bot 分轨模式：

- Bot 加入语音频道。
- 按 Discord user id 接收独立 PCM。
- 每个 user id 绑定自己的 Speaker ID。
- 每个用户独立做识别、翻译、TTS，再混音到本地监听。

这个模式工程量明显更大，建议作为第二阶段，不放进第一版精简交付。

## 6. 性能目标

第一版验收指标：

- 本地采集到 AST 发送：稳定 20-60ms。
- 首个译文字幕：网络正常时目标 300-800ms。
- AST 原生 TTS 首段译音：目标 800-1500ms。
- 克隆 TTS：若必须等句尾，目标 1500-3000ms，不承诺和 AST 原生 TTS 一样快。
- 连续运行 2 小时无崩溃、无明显内存增长、队列不持续堆积。
- 8 小时 soak 测试无子进程残留、无音频设备死锁。
- 设备断开后进入 degraded 状态，不崩溃；恢复后可手动或自动重连。

核心策略：

- 热路径不做复杂 UI 重绘。
- 所有音频队列有上限，满队列时丢弃过期音频而不是积压延迟。
- 重连有指数退避和次数上限。
- native core 心跳、stderr、最近错误进入诊断包。
- 克隆 TTS 失败时自动回退预设 AST voice，保证对话不中断。

## 7. 文件级改造计划

### `nova_controller.py`

- 将 `CHANNEL_MAP` 改为只包含 `a/outbound` 和 `b/inbound`。
- 删除或隔离所有 `c`、`game_inbound`、Channel C 的状态、配置、运行时快照。
- `SCENE_TEMPLATES` 只保留 `discord_bidirectional`。
- `LANGUAGE_OPTIONS` 在 UI 层只暴露 `zh` 和 `en`。
- `DOMAIN_PACKS` 保留 Rust 游戏热词、纠错词和 glossary；默认可继续使用 Rust 术语增强，但 UI 不再暴露复杂词包切换。
- 将 `LOCAL_CLONE_TTS_LANGUAGES` 扩展为 `{"zh", "en"}`，并增加真实 API smoke 验证。
- 新增 `voice_profiles.self` 和 `voice_profiles.remote_default` 配置结构。
- `start_channels()` 固定只启动 A/B，且默认 A=zh->en、B=en->zh。
- 删除 updater 状态和相关 bridge 接口。

### `ast_bridge.py`

- 保留 `TranslationChannel`，重点优化队列、重连、播放失败隔离。
- 克隆 TTS 走独立 worker，但要增加超时、失败回退、每通道错误计数。
- 为 A/B 增加明确的音色来源字段，诊断里能看到当前使用 AST voice 还是 clone voice。
- 对 `s2s`、`s2t + clone_tts` 两条路径分别打点，避免误判延迟。

### `voice_clone_manager.py`

- 保留训练、查询、合成。
- UI 命名改成“我的音色 / 对方音色”，隐藏底层资源 ID。
- 对中文目标克隆合成增加 smoke 测试和错误提示。
- Speaker ID 不写入公开样例，只写入 `config.local.json`。

### `web_dashboard/`

- `index.html`：删除 Channel C 卡片、C 字幕、C 弹窗、复杂场景入口、更新入口。
- `dashboard.js`：`CHANNELS = ["a", "b"]`；删除所有 C 相关状态和事件处理。
- `dashboard.css`：清理 C 通道样式，保留紧凑双栏布局。
- 页面只保留：
  - 启动/停止
  - A/B 设备路由
  - 我的音色 / 对方音色
  - 延迟与错误状态
  - 简单热词/上下文
  - 诊断导出

### `config.example.json`

- 删除 `game_inbound`。
- 默认：
  - `outbound`: enabled, zh -> en, clone enabled using `self`
  - `inbound`: enabled, en -> zh, clone enabled using `remote_default`
- 默认保留 Rust 游戏热词、纠错词和术语表，适配 Discord 里的 Rust 游戏沟通。
- 默认 performance profile 为 `turbo`。
- 默认 `native_capture_fallback = true`。

### `desktop_webview.py`

- 移除 `check_updates()`、`download_update()` bridge。
- 保留 `start_channels()`、`stop_channels()`、`poll_state()`、声音复刻、诊断导出、字幕窗口。

### 可删除或不进发布包

- `app.py` 内的旧 Tk 实现，只保留兼容转发入口。
- `launch_legacy_tk.ps1` 内的旧 Tk 启动逻辑，只保留兼容转发入口。
- `updater.py`
- `docs/COMMERCIAL_V2_PLAN.md`
- 非精简版产品文档
- 不必要的演示/旧状态导出文件

## 8. 阶段计划

### P0：建立精简分支与基线

- 创建分支：`codex/discord-bilingual-lite`。
- 运行基线检查：
  - `python -m py_compile nova_controller.py ast_bridge.py voice_clone_manager.py desktop_webview.py audio_core_bridge.py`
  - `node --check web_dashboard/dashboard.js`
  - `cargo build --release --manifest-path native_audio_core/Cargo.toml`
- 记录当前三通道行为，避免裁剪时误删核心链路。

验收：基线检查通过，新增规划文档完成。

### P1：后端范围收缩

- Controller 只保留 A/B。
- 配置 schema 改成只保存 outbound/inbound。
- 删除 C 通道运行时状态、指标、转写、设备 fallback。
- 删除 updater。

验收：应用启动后状态快照只包含 A/B；保存配置不再生成 `game_inbound`。

### P2：前端极简化

- Dashboard 改成 Discord 双通道专用界面。
- 删除 C、场景切换、多语种复杂控件、更新器 UI。
- 音色配置改成“我的音色”和“对方音色”。

验收：页面无 C 通道残留；`node --check` 通过；启动/停止仍可调用后端。

### P3：音色保持闭环

- A 通道：中文输入 -> 英文 clone TTS 使用我的 Speaker ID。
- B 通道：英文输入 -> 中文 clone TTS 使用对方 Speaker ID。
- 克隆失败自动回退 AST 预设音色并报警。
- 增加试听和状态检查。

验收：两个通道都能选择克隆 Speaker ID；诊断能显示每路实际音色策略。

### P4：性能稳定优化

- 默认 native capture/playback。
- Python fallback 保留。
- 队列满时丢弃过期音频，避免延迟雪球。
- 断线重连、设备断开、TTS 超时进入可见状态。

验收：30 分钟双通道运行无队列持续增长；模拟设备断开不崩溃。

### P5：长测与发布包

- 2 小时 soak。
- 8 小时 soak。
- Windows 打包验证。
- 诊断包脱敏检查。

验收：Windows 包可运行；无密钥泄露；长测指标达标。

## 9. 测试清单

基础检查：

```powershell
python -m py_compile nova_controller.py ast_bridge.py voice_clone_manager.py desktop_webview.py audio_core_bridge.py
node --check web_dashboard/dashboard.js
cargo build --release --manifest-path native_audio_core/Cargo.toml
```

音频核心：

```powershell
python scripts/smoke_native_audio_core.py --bridge-api
python scripts/stress_native_audio_core.py --profile preflight --channels 2 --with-capture
```

真实链路：

- A 通道麦克风中文输入，Discord 虚拟麦克风收到英文译音。
- B 通道 Discord 英文输入，本地耳机收到中文译音。
- A/B 同时开，互不抢设备。
- 关闭 Discord 虚拟声卡后应用不崩溃。
- 断网后显示 reconnecting，恢复网络后可继续或可手动重启。
- 克隆 Speaker ID 错误时能回退，不中断字幕和基础翻译。

## 10. 关键风险

- 声音复刻会增加延迟，尤其是本地克隆 TTS 需要等译文句尾时。
- 对方多人音色保持不能靠 Discord 混音输入完成，必须引入 Discord Bot 分轨。
- 虚拟声卡配置会决定真实体验，Windows 推荐 VB-Cable 或 VoiceMeeter。
- 真实稳定性必须靠长测，不靠短 smoke 测试判断。
- 声音复刻需要对方授权和清晰样本，否则音色相似度和稳定性都会不可靠。

## 11. 推荐第一版交付定义

第一版不做 Discord Bot 分轨，只做单对单或“对方默认音色”的双通道精简版：

- A：我的中文 -> 英文，我的音色，输出到 Discord。
- B：对方英文 -> 中文，对方默认音色，输出到本地。
- 双通道同时运行。
- C 通道和所有非 Discord 功能从 UI 与配置中移除。
- native 音频核心默认启用，Python fallback 可用。
- 克隆失败自动降级，翻译不中断。

第二版再做：

- Discord Bot 分轨。
- 多个远端用户 -> 多个 Speaker ID。
- 每个用户独立音色翻译和混音。
