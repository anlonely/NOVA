# NOVA INTERP 产品文档（main 分支）

版本依据：`main` 分支（与当前仓库工作树一致），生成时间：2026-04-30（Asia/Shanghai）。

## 1. 分支定位

`main` 分支是当前对外可用的基础版本，产品目标是提供“桌面实时语音翻译控制台”，支持三路音频路由并支持字幕、译文显示与延迟观测。

- 交付形态：PySide6 + Qt WebEngine 桌面端，HTML/CSS/JavaScript 仪表盘
- 语音引擎：火山引擎 AST 流式翻译（WebSocket）
- 音频底层：Python `soundcard` + 原生/回退双链路路由播放 + 原生 Rust 设备枚举与服务化音频能力（可配置、可回退）
- 主要场景：Discord/游戏语音混合、会议、跨语种协作、直播盲听

## 2. 核心价值主张

1. 三路独立路由  
   A/B/C 分别对应外发麦克风、平台语音入站、游戏语音入站，支持独立设备绑定与启停。
2. 实时字幕与播报  
   通过 AST 事件输出原文/译文双通道字幕，并支持译文播放（远端 TTS）。
3. 业务可配置化  
   支持域名词偏置（hot words、纠错词、术语表）、场景模板（中英互译、字幕优先等）。
4. 声音克隆闭环  
   具备样本上传、训练刷新、试听、会话引用。
5. 透明运维  
   提供延迟面板、设备枚举、诊断状态、会话导出与更新能力。

## 3. 系统架构

- `desktop_webview.py`
  - Qt WebEngine 壳，`QWebChannel` 暴露 `NovaBridge`
  - 提供 JS/Python 的双向调用（读状态、保存配置、启动/停止等）
- `web_dashboard/`
  - `index.html`：控制台与侧边抽屉（路由、场景、域偏置、字幕、更新等）
  - `dashboard.js`：状态轮询、表单状态绑定、多语言文案、事件渲染
  - `dashboard.css`：运行状态与诊断面板样式
- `nova_controller.py`
  - 配置持久化（`config.local.json`）
  - 设备目录刷新、域偏置与场景配置聚合
  - 组装 `TranslationChannel` 并管理生命周期、状态快照与导出
- `ast_bridge.py`
  - `TranslationChannel`：音频采集→队列→AST 连接→字幕/音频回流
  - AST 协议：启动会话、音频分块、结束会话、字幕事件处理
  - 事件总线：`status/error/stats/source_partial/target_partial/target_final/...
`
- `voice_clone_manager.py`
  - 声音复刻训练与状态查询、试听生成的流程封装
- `audio_core_bridge.py`
  - 与 `native_audio_core` 二进制交互的最小封装（`list-devices`）
- `native_audio_core/`
  - Rust CLI 负责设备枚举（`list-devices`），返回 JSON 快照

## 4. 业务流程

### 4.1 启动流程

1. 启动桌面壳，`NovaController` 初始化并加载本地配置
2. 枚举设备（Python Catalog + Native Core）
3. 用户完成配置（场景、语言、设备、字幕模式、偏置）
4. 点击启动：  
   - 校验通道/设备/语言合法性  
   - 为每个启用通道创建 `TranslationChannel`  
   - 建立 AST WebSocket 连接并开始发送 PCM16 音频分块
5. UI 获取 `runtime/stats/state` 周期性刷新，展示字幕与诊断数据

### 4.2 停止流程

1. 请求停止并广播 `stop`，每个通道优雅退出线程与队列
2. 断开 AST 会话，清理播放/录音状态
3. 回填最终状态并保持配置不丢失

## 5. 状态与接口（面向产品）

### 5.1 UI 主要状态块

- 控制区域：A/B/C 通道设备 + 语言/音色 + subtitle mode + 开关
- 线路与诊断区：输入输出状态、队列、丢弃数、延迟、音量与 native core 概览
- 字幕区：三路流（原文/译文）显示
- 延迟面板：首包、识别、翻译、TTS 延迟
- 平台设置：更新清单、凭据、更新检查

### 5.2 关键运行指标（由 Controller/Channel 汇总）

- 通道状态：ready / running / reconnecting / error / idle
- AST：会话 ID、首音延迟、首字幕延迟、首译音延迟
- 传输与音频队列：input queue/playback queue/depth
- 质量指标：音量 dB、丢弃片段数、静音保持计数
- 会话统计：发送/接收 chunk 数、字幕条数、语音异常

## 6. 配置面

- 凭据
  - `appId / accessToken / secretKey / resourceId`
- 通道配置
  - 输入/输出设备、源目标语言、音色、性能档位、字幕模式、开启/关闭选项、滤波参数
- 偏置配置
  - 领域预设、上下文提示、hot words、纠错词、术语表
- 网络
  - DNS server / DNS hosts 覆盖
- 声音克隆
  - 全局 + 通道克隆音色、样本路径、参考文本、示例文本

## 7. 交付与约束

### 7.1 打包与部署

- Windows：`scripts/build_windows.ps1`
- macOS：`scripts/build_macos.sh` + `.app` / release zip

### 7.2 限制与风险

- 架构为“Python 控制面 + 原生可选音频面”的混合形态，极端情况下可自动回退到纯 Python 链路；
- 虚拟声卡、回声与系统混音质量高度依赖设备/驱动
- 长时运行稳定性与硬件兼容是主要验证项（需持续压测）

## 8. 分支差异说明（相对 old_v1）

`main` 为当前可交付主线，`old_v1` 为历史对照线：
- `old_v1`：Python 采集与播放为主链路，未全面引入原生音频核心能力；
- `main`：新增原生音频链路、通道回退、参数化控制与更丰富的运行诊断；
- 如需保留旧线对照，建议在 `old_v1` 分支查看对应提交快照。
