# Nebula Interp Console

这是当前工作区里的 `V2` 桌面原型，定位已经不是“最小可跑 Demo”，而是朝着商用交付形态推进的一版控制台。

## 这版已经具备的能力

- 双通道独立配置
- 输入设备 / 输出设备 / 回环输入选择
- 双通道源语言 / 目标语言独立设置
- 低延迟性能档位：`Turbo` / `Balanced` / `Studio`
- 每通道可调：
  - 分包时长
  - 播放缓冲
  - 输出采样率
  - 输入增益
  - 音色 ID
  - 字幕模式
- 路由图、诊断面板、实时延迟指标
- 字幕浮窗
- 会话导出
- 本地配置持久化

## 启动

```powershell
.\launch.ps1
```

如果虚拟环境已经存在，也可以直接：

```powershell
.\.venv\Scripts\python app.py
```

## 快速联调

无需打开界面，直接验证 AST 联通：

```powershell
.\.venv\Scripts\python smoke_test_ast.py
```

它会在 `output/` 下生成：

- `smoke_translation.txt`
- `smoke_translation.wav`

## 当前界面建议场景

- `Discord 双向同传`
- `双向都听英文`
- `字幕优先低延迟`
- `演示保真模式`

## 凭证

当前这条 AST WebSocket 实测使用：

- `APP ID`
- `Access Token`
- `Resource ID`

`Secret Key` 已在界面和配置中保留，但当前版本没有用于 AST 直连。后续如果加声音复刻 API 或服务端签名代理，会用到它。

## 文档

商用版产品方案和落地路线已经整理到：

- [docs/COMMERCIAL_V2_PLAN.md](docs/COMMERCIAL_V2_PLAN.md)
- [docs/DELIVERY_BACKLOG.md](docs/DELIVERY_BACKLOG.md)
