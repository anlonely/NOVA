# NOVA INTERP

一款面向 Discord、游戏语音、会议和跨语言协作场景的低延迟桌面实时翻译控制台。

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Qt%20WebEngine-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-Audio%20Core-000000?style=for-the-badge&logo=rust&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-App%20Bundle-111111?style=for-the-badge&logo=apple&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-Packaging-0078D4?style=for-the-badge&logo=windows&logoColor=white)

NOVA INTERP 将麦克风、平台音频和游戏语音拆成独立通道，接入火山引擎 AST 流式语音翻译，并提供字幕盯读、音频路由、音色试听、延迟观测和打包发布能力。

---

## ✨ 项目特性

- 🎙️ **三通道实时翻译**：A/B/C 通道分别覆盖外发麦克风、远端监听和游戏语音监听。
- 🔀 **独立音频路由**：每个通道可单独选择输入、输出和监听设备，适配 VB-Cable、BlackHole 等虚拟声卡。
- ⚡ **低延迟字幕模式**：启动后可自动切换到字幕盯读视图，停止后恢复控制视图。
- 🧭 **线路与诊断面板**：展示通道状态、输入/输出、AST 延迟、TTS 延迟、队列、丢弃数和电平。
- 🧠 **领域词汇偏置**：内置 Rust 游戏、战术 FPS、通用语音等识别和翻译偏置模板。
- 🗣️ **声音克隆工作流**：包含训练样本、状态刷新、试听生成和通道音色配置入口。
- 🖥️ **跨平台桌面端**：支持 Windows 打包流程，新增 macOS `.app` Bundle 与 release zip。
- 🦀 **原生音频核心**：Rust `cpal` 音频设备枚举核心，Windows 使用 WASAPI，macOS 使用 CoreAudio。

---

## 📦 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 桌面框架 | PySide6 + Qt WebEngine | 本地桌面窗口与 Web UI 容器 |
| 后端控制 | Python | 配置、状态桥接、通道编排、AST WebSocket |
| 前端界面 | HTML / CSS / JavaScript | 仪表盘、字幕区、诊断面板和抽屉设置 |
| 音频设备 | soundcard | 麦克风、扬声器、虚拟声卡枚举和采集播放 |
| 原生核心 | Rust + cpal | WASAPI / CoreAudio 设备快照 |
| 打包 | PyInstaller | Windows bundle 与 macOS `.app` |
| 服务 | Volcengine AST | 流式识别、翻译和 TTS 音频返回 |

---

## 🚀 快速开始

### 前置要求

- Python 3.9+
- Rust 工具链（可选，用于构建 `native_audio_core`）
- 火山引擎 AST 凭据：`APP ID`、`Access Token`、`Secret Key`
- 虚拟声卡（可选但推荐）
  - Windows：VB-Cable / VoiceMeeter
  - macOS：VB-Cable / BlackHole / Loopback

### 1. 克隆项目

```bash
git clone https://github.com/anlonely/NOVA.git
cd NOVA
```

### 2. 创建本地配置

macOS / Linux：

```bash
cp config.example.json config.local.json
```

Windows PowerShell：

```powershell
Copy-Item .\config.example.json .\config.local.json
```

填写 `config.local.json`：

```json
{
  "app_key": "你的 APP ID",
  "access_key": "你的 Access Token",
  "secret_key": "你的 Secret Key"
}
```

> `config.local.json` 已加入 `.gitignore`，不要提交真实密钥。

### 3. 启动桌面端

macOS：

```bash
./launch_macos.sh
```

Windows：

```powershell
.\launch.ps1
```

### 4. 验证 AST 连接

```bash
. .venv/bin/activate
python smoke_test_ast.py
```

测试成功后会输出：

- `output/smoke_translation.txt`
- `output/smoke_translation.wav`

---

## 🎛️ 使用说明

### 通道模型

| 通道 | 默认用途 | 常见配置 |
|------|----------|----------|
| A | 我的麦克风 → 英文外发 | 输入选真实麦克风，输出选虚拟声卡或远端设备 |
| B | Discord / 远端 → 中文监听 | 输入选平台音频虚拟声卡，输出选耳机/扬声器 |
| C | 游戏语音 → 中文监听 | 输入选游戏语音虚拟声卡，输出选本地监听设备 |

### 字幕模式

- 点击启动后可自动进入字幕模式。
- 字幕模式隐藏通道配置，保留线路与诊断状态。
- 停止后自动回到控制模式。
- 原文弱化、译文高亮，适合长时间盯读。

### 线路与诊断

诊断面板会显示：

- 通道运行状态
- 输入/输出设备
- AST 延迟和音频延迟
- TTS 延迟
- 队列深度与静音丢弃数
- 输入电平 dB
- AST 连接路径和整体运行状态

---

## 🧰 开发命令

### 安装依赖

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 启动 Qt 桌面入口

```bash
python desktop_webview.py
```

### 静态 Web 预览

macOS：

```bash
./launch_web_dashboard_macos.sh
```

Windows：

```powershell
.\launch_web_dashboard.ps1
```

### Python 编译检查

```bash
find . \( -path './.venv' -o -path './.git' -o -path './build' -o -path './dist' -o -path './native_audio_core/target' \) -prune -o -name '*.py' -print0 | xargs -0 python -m py_compile
```

### 前端语法检查

```bash
node --check web_dashboard/dashboard.js
```

---

## 📦 打包发布

### Windows

```powershell
.\scripts\build_windows.ps1
```

输出：

```text
output\release\NOVA-INTERP-windows-x64-v<version>.zip
output\release\NOVA-INTERP-windows-x64-v<version>.zip.sha256
```

### macOS

```bash
./scripts/build_macos.sh
```

输出：

```text
dist/NOVA INTERP.app
output/release/NOVA-INTERP-macOS-v<version>.zip
output/release/NOVA-INTERP-macOS-v<version>.zip.sha256
```

macOS 首次打开如果被系统拦截，可右键 `NOVA INTERP.app` → 打开。

---

## 📁 项目结构

```text
NOVA/
├── desktop_webview.py              # Qt + Web dashboard 桌面入口
├── nova_controller.py              # 运行时控制器、配置、状态桥接
├── ast_bridge.py                   # Volcengine AST WebSocket 通道实现
├── voice_clone_manager.py          # 声音克隆训练、查询和试听接口
├── audio_core_bridge.py            # Python 调用 Rust 原生音频核心
├── web_dashboard/                  # HTML/CSS/JS 仪表盘界面
│   ├── index.html
│   ├── dashboard.css
│   └── dashboard.js
├── native_audio_core/              # Rust cpal 音频设备枚举核心
├── python_protogen/                # AST protobuf 生成代码
├── scripts/
│   ├── build_windows.ps1           # Windows 打包脚本
│   └── build_macos.sh              # macOS 打包脚本
├── launch.ps1                      # Windows 启动脚本
├── launch_macos.sh                 # macOS 启动脚本
├── smoke_test_ast.py               # AST 端到端冒烟测试
├── config.example.json             # 安全配置模板
└── README.md
```

---

## 🔐 安全说明

- `config.local.json` 只用于本地运行，已被 `.gitignore` 忽略。
- 不要把火山引擎密钥、Access Token 或声音克隆 Speaker ID 提交到公开仓库。
- 打包产物不会自动携带你的本地真实配置；分发前请确认配置策略。
- 如果密钥曾经出现在聊天、日志或截图中，建议在控制台轮换。

---

## ⚠️ 平台注意事项

### macOS

- `soundcard` 会提示 macOS 不支持系统级 loopback，这是系统限制。
- 远端音频/游戏语音建议通过 VB-Cable、BlackHole 或 Loopback 进入输入通道。
- 原生音频核心使用 CoreAudio 设备快照。

### Windows

- Windows 仍是完整支持目标。
- 原生音频核心使用 WASAPI。
- GitHub Actions 会构建 Windows release zip。

---

## 🗺️ 路线图

- [ ] 更稳定的多平台音频路由抽象
- [ ] macOS 权限引导和设备诊断向导
- [ ] 字幕窗口独立浮窗模式
- [ ] 语音克隆训练流程进一步产品化
- [ ] 自动更新安装器
- [ ] Windows / macOS 签名发布流程

---

## 📄 许可证

本仓库未显式声明许可证。使用、分发或商业化前请先确认授权范围。

---

<div align="center">
  <p>NOVA INTERP · Low-latency bilingual interpreting console</p>
</div>
