const fallbackExternalState = window.__NOVA_STATE__ || {};

const CHANNELS = ["a", "b", "c"];
const PROFILE_DEFAULTS = {
  turbo: { startup: "24", gate: "-46", hold: "180" },
  balanced: { startup: "44", gate: "-50", hold: "240" },
  studio: { startup: "96", gate: "-56", hold: "320" },
};

const SCENE_COPY = {
  en: {
    discord_bidirectional: {
      label: "Discord Bidirectional",
      hint: "Chinese -> English outbound, English -> Chinese inbound",
    },
    caption_priority: {
      label: "Caption Priority",
      hint: "Lower startup buffer and subtitle-first rendering",
    },
    studio_demo: {
      label: "Studio Demo",
      hint: "Safer buffers and smoother high-fidelity playback",
    },
  },
  zh: {
    discord_bidirectional: {
      label: "Discord 双向",
      hint: "中文外发转英文，英文入站转中文",
    },
    caption_priority: {
      label: "字幕优先",
      hint: "更低起播缓冲，优先保障字幕速度",
    },
    studio_demo: {
      label: "演示保真",
      hint: "更稳的缓冲和更平滑的高保真输出",
    },
  },
};

const DOMAIN_COPY = {
  en: {
    generic: { label: "Generic Voice", hint: "Balanced recognition and translation" },
    rust: { label: "Rust Game", hint: "Bias toward Rust comms, raid, and farming terms" },
    tactical_fps: { label: "Tactical FPS", hint: "Bias toward tactical shooter callouts" },
  },
  zh: {
    generic: { label: "通用语音", hint: "通用识别与翻译偏置" },
    rust: { label: "Rust 游戏", hint: "偏向 Rust 术语、抄家、打架和报点" },
    tactical_fps: { label: "战术射击", hint: "偏向战术射击报点和武器术语" },
  },
};

const LANGUAGE_COPY = {
  en: {
    zh: { label: "Chinese", hint: "zh" },
    en: { label: "English", hint: "en" },
    ja: { label: "Japanese", hint: "ja" },
    es: { label: "Spanish", hint: "es" },
    pt: { label: "Portuguese", hint: "pt" },
    fr: { label: "French", hint: "fr" },
    de: { label: "German", hint: "de" },
    id: { label: "Indonesian", hint: "id" },
    zhen: { label: "Chinese + English", hint: "zhen" },
  },
  zh: {
    zh: { label: "中文", hint: "zh" },
    en: { label: "英语", hint: "en" },
    ja: { label: "日语", hint: "ja" },
    es: { label: "西班牙语", hint: "es" },
    pt: { label: "葡萄牙语", hint: "pt" },
    fr: { label: "法语", hint: "fr" },
    de: { label: "德语", hint: "de" },
    id: { label: "印尼语", hint: "id" },
    zhen: { label: "中英混说", hint: "zhen" },
  },
};

const PROFILE_COPY = {
  en: {
    turbo: { label: "Turbo", hint: "Lowest startup latency" },
    balanced: { label: "Balanced", hint: "Mixed hardware stability" },
    studio: { label: "Studio", hint: "Safer playback fidelity" },
  },
  zh: {
    turbo: { label: "极速", hint: "最低起播延迟" },
    balanced: { label: "均衡", hint: "兼顾速度与稳定性" },
    studio: { label: "录音棚", hint: "更稳的缓冲与保真" },
  },
};

const SUBTITLE_COPY = {
  en: {
    bilingual: { label: "Bilingual", hint: "Source + translation" },
    source_only: { label: "Source Only", hint: "Show original text only" },
    target_only: { label: "Target Only", hint: "Show translated text only" },
  },
  zh: {
    bilingual: { label: "双语", hint: "原文 + 译文" },
    source_only: { label: "仅原文", hint: "只显示原文" },
    target_only: { label: "仅译文", hint: "只显示译文" },
  },
};

const CLONE_TRAIN_LANGUAGE_COPY = {
  en: {
    zh: { label: "Chinese", hint: "zh" },
    en: { label: "English", hint: "en" },
  },
  zh: {
    zh: { label: "中文", hint: "zh" },
    en: { label: "英语", hint: "en" },
  },
};

const I18N = {
  en: {
    "app.title": "NOVA INTERP",
    "tag.dualChannel": "Three Channel",
    "tag.lowLatency": "Low Latency",
    "header.scene": "Scenario Template",
    "button.start": "Start",
    "button.stop": "Stop",
    "button.saveConfig": "Save Config",
    "button.exportSession": "Export Session",
    "button.checkUpdates": "Check Updates",
    "button.downloadUpdate": "Download Update",
    "button.browse": "Browse",
    "button.previewVoice": "Preview",
    "button.recordClone": "Record from Mic",
    "button.stopRecording": "Stop Recording",
    "button.trainClone": "Train Clone",
    "button.refreshClone": "Refresh Status",
    "button.bias": "Bias",
    "button.latency": "Latency",
    "button.channelTools": "Clone + Tuning",
    "runtime.running": "Running",
    "runtime.locked": "Top routing is locked while the engine is active.",
    "channel.aEyebrow": "Channel A",
    "channel.bEyebrow": "Channel B",
    "channel.cEyebrow": "Channel C",
    "channel.drawerTitleA": "Channel A Clone & Tuning",
    "channel.drawerTitleB": "Channel B Clone & Tuning",
    "channel.drawerTitleC": "Channel C Clone & Tuning",
    "channel.drawerCopy": "Channel-specific voice clone, cleanup, and latency tuning.",
    "toggle.channel": "Channel",
    "toggle.input": "Input",
    "toggle.output": "Output",
    "field.inputDevice": "Input Device",
    "field.outputDevice": "Output Device",
    "field.sourceLanguage": "Source Language",
    "field.targetLanguage": "Target Language",
    "field.outputVoice": "Output Voice",
    "field.performance": "Performance",
    "field.transcriptMode": "Transcript Mode",
    "route.eyebrow": "Unified Route",
    "route.title": "Route & Diagnostics",
    "route.copy": "Shared AST core with per-channel routing, monitoring, and gap compensation.",
    "route.inputA": "Input A",
    "route.outputA": "Output A",
    "route.inputB": "Input B",
    "route.outputB": "Output B",
    "route.inputC": "Input C",
    "route.outputC": "Output C",
    "route.astVoice": "AST Voice",
    "route.astFallback": "AST Fallback",
    "route.gapGuard": "Gap Guard",
    "metric.inputA": "Input A",
    "metric.inputB": "Input B",
    "metric.inputC": "Input C",
    "metric.tts": "TTS",
    "dock.eyebrow": "Live Translation",
    "dock.title": "Tri-Pane Transcript Dock",
    "dock.copy": "Smooth auto-scroll, dimmed source text, and emphasized translated text for long-session readability.",
    "dock.autoScroll": "Auto Scroll",
    "dock.bilingual": "Bilingual",
    "pane.aEyebrow": "Channel A Feed",
    "pane.bEyebrow": "Channel B Feed",
    "pane.cEyebrow": "Channel C Feed",
    "drawer.eyebrow": "Engine Settings",
    "drawer.title": "Engine Credentials",
    "latency.eyebrow": "Latency",
    "latency.title": "Latency Measurement",
    "latency.copy": "Measure first audio, speech recognition, translation processing, and TTS generation from the current session.",
    "latency.summaryEyebrow": "Session Summary",
    "latency.summaryTitle": "Current Summary",
    "latency.channelEyebrow": "Per Channel",
    "latency.channelTitle": "Channel Breakdown",
    "latency.firstAudio": "First Audio",
    "latency.recognition": "Speech Recognition",
    "latency.translation": "Translation Processing",
    "latency.tts": "TTS Generation",
    "platform.eyebrow": "Platform",
    "platform.title": "Audio Core & Updates",
    "platform.updateManifest": "Update Manifest URL",
    "platform.captureBackend": "Capture Backend",
    "platform.preRollMs": "Pre-roll ms",
    "platform.nativeFallback": "Fallback to Python when native capture fails",
    "platform.resamplerQuality": "Resampler",
    "platform.vadMode": "VAD Mode",
    "platform.playbackBackend": "Playback Backend",
    "platform.noiseFloor": "Adaptive noise floor",
    "platform.adaptiveChunking": "Adaptive AST chunking",
    "platform.autoProfile": "Auto performance profile",
    "domain.eyebrow": "Domain Bias",
    "domain.title": "Recognition Bias",
    "domain.preset": "Domain Preset",
    "domain.context": "Context Bias",
    "domain.hotWords": "Hot Words",
    "domain.correctWords": "Correct Words",
    "domain.glossary": "Glossary",
    "clone.eyebrow": "Voice Clone",
    "clone.title": "Voice Clone V3",
    "clone.samplePath": "Training Sample",
    "clone.recordInput": "Record Input",
    "clone.recordAction": "Microphone Sample",
    "clone.speakerId": "Speaker ID",
    "clone.language": "Training Language",
    "clone.referenceText": "Reference Text",
    "clone.demoText": "Demo Text",
    "advanced.eyebrow": "Latency & Cleanup",
    "advanced.title": "Advanced Channel Tuning",
    "advanced.startupBuffer": "Startup Buffer (ms)",
    "advanced.noiseGate": "Noise Gate (dB)",
    "advanced.silenceHold": "Silence Hold (ms)",
    "advanced.dropSilence": "Drop silent chunks",
    "advanced.enableAgc": "Enable AGC",
    "advanced.agcTarget": "AGC Target (dBFS)",
    "advanced.agcMaxGain": "AGC Max Gain",
    "advanced.enableDenoise": "Enable Denoise",
    "advanced.denoiseStrength": "Denoise Strength",
    "advanced.useClone": "Use Cloned Voice",
    "advanced.cloneSpeaker": "Clone Speaker ID",
    "advanced.cloneSpeed": "Clone Speed",
    "advanced.monitorPlayback": "Monitor translated voice",
    "advanced.monitorDevice": "Monitor Device",
    "credentials.eyebrow": "Credentials",
    "credentials.title": "Engine Access",
    "credentials.accessToken": "Access Token",
    "credentials.secretKey": "Secret Key",
    "credentials.resourceId": "Resource ID",
    "credentials.note": "Virtual sound cards, loopback inputs, and hardware devices are refreshed from the local machine. Install a new cable, click refresh, and it will appear in the dropdowns.",
    "placeholder.mapping": "wrong => right",
    "placeholder.glossary": "source => target",
    "option.none": "Not Selected",
    "option.astVoice": "Use AST voice output",
    "status.ready": "Ready",
    "status.live": "Live",
    "status.error": "Error",
    "status.idle": "Idle",
    "status.streaming": "Streaming",
    "status.connecting": "Connecting",
    "status.starting": "Starting",
    "status.running": "Running",
    "status.disabled": "Disabled",
    "status.inputOff": "Input Off",
    "status.standby": "Standby",
    "status.captionsOnly": "Captions Only",
    "status.channelDisabled": "Channel disabled",
    "status.outputDisabled": "Playback disabled",
    "status.astReady": "AST Ready",
    "status.pythonAudio": "Python Audio Core",
    "status.nativeAudio": "Native WASAPI Core",
    "status.nativeScaffold": "Rust Core Scaffold",
    "status.virtualNone": "No virtual routes yet",
    "status.virtualReady": "Virtual-ready",
    "status.autosaved": "Saved locally.",
    "status.cloneIdle": "Select a console speaker ID such as S_xxx or ICL_xxx, then choose a training sample to train the clone profile.",
    "status.recording": "Recording",
    "status.sampleReady": "Sample Ready",
    "status.cloneFallback": "Clone fallback",
    "status.updateIdle": "No update check yet. Configure a manifest URL to enable package downloads.",
    "status.trainingUploaded": "Training sample uploaded",
    "status.speakerIdNeeded": "Speaker ID Needed",
    "alert.exportDesktop": "Export is available in the desktop build.",
    "alert.startFailed": "Unable to start the engine.",
    "alert.cloneSampleMissing": "Choose a training sample first.",
    "alert.updateMissing": "Check for updates first.",
  },
  zh: {
    "app.title": "NOVA INTERP",
    "tag.dualChannel": "三通道",
    "tag.lowLatency": "低延迟",
    "header.scene": "场景模板",
    "button.start": "启动",
    "button.stop": "停止",
    "button.saveConfig": "保存配置",
    "button.exportSession": "导出会话",
    "button.checkUpdates": "检查更新",
    "button.downloadUpdate": "下载安装包",
    "button.browse": "浏览",
    "button.trainClone": "训练音色",
    "button.refreshClone": "刷新状态",
    "button.bias": "识别偏置",
    "button.latency": "延迟测量",
    "button.channelTools": "音色与调优",
    "runtime.running": "运行中",
    "runtime.locked": "引擎运行时，上方路由会自动锁定，避免误操作。",
    "channel.aEyebrow": "通道 A",
    "channel.bEyebrow": "通道 B",
    "channel.cEyebrow": "通道 C",
    "channel.drawerTitleA": "通道 A 音色与调优",
    "channel.drawerTitleB": "通道 B 音色与调优",
    "channel.drawerTitleC": "通道 C 音色与调优",
    "channel.drawerCopy": "这里集中放每个通道自己的音色复刻、清理和低延迟调优。",
    "toggle.channel": "通道",
    "toggle.input": "输入",
    "toggle.output": "输出",
    "field.inputDevice": "输入设备",
    "field.outputDevice": "输出设备",
    "field.sourceLanguage": "源语言",
    "field.targetLanguage": "目标语言",
    "field.performance": "性能档位",
    "field.transcriptMode": "字幕模式",
    "route.eyebrow": "统一线路",
    "route.title": "线路与诊断",
    "route.copy": "共享 AST 核心，按通道独立路由、监控和音频补偿。",
    "route.inputA": "A 输入",
    "route.outputA": "A 输出",
    "route.inputB": "B 输入",
    "route.outputB": "B 输出",
    "route.inputC": "C 输入",
    "route.outputC": "C 输出",
    "route.astVoice": "AST 原生译音",
    "route.astFallback": "自动回退",
    "route.gapGuard": "音频补偿",
    "metric.inputA": "A 输入",
    "metric.inputB": "B 输入",
    "metric.inputC": "C 输入",
    "metric.tts": "语音",
    "dock.eyebrow": "实时翻译",
    "dock.title": "三栏实时字幕区",
    "dock.copy": "平滑自动滚动，原文弱化显示，译文高亮显示，适合长时间盯读。",
    "dock.autoScroll": "自动滚动",
    "dock.bilingual": "双语显示",
    "pane.aEyebrow": "通道 A 字幕",
    "pane.bEyebrow": "通道 B 字幕",
    "pane.cEyebrow": "通道 C 字幕",
    "drawer.eyebrow": "引擎设置",
    "drawer.title": "引擎凭证",
    "latency.eyebrow": "延迟",
    "latency.title": "延迟测量",
    "latency.copy": "从当前会话测量首音延迟、语音识别延迟、翻译处理延迟和 TTS 生成延迟。",
    "latency.summaryEyebrow": "会话汇总",
    "latency.summaryTitle": "当前汇总",
    "latency.channelEyebrow": "分通道",
    "latency.channelTitle": "通道细分",
    "latency.firstAudio": "首音延迟",
    "latency.recognition": "语音识别延迟",
    "latency.translation": "翻译处理延迟",
    "latency.tts": "TTS 生成延迟",
    "platform.eyebrow": "平台",
    "platform.title": "音频核心与更新",
    "platform.updateManifest": "更新清单地址",
    "platform.captureBackend": "采集后端",
    "platform.preRollMs": "预卷毫秒",
    "platform.nativeFallback": "原生采集失败时回退 Python",
    "platform.resamplerQuality": "重采样器",
    "platform.vadMode": "VAD 模式",
    "platform.playbackBackend": "播放后端",
    "platform.noiseFloor": "自适应噪声底",
    "platform.adaptiveChunking": "自适应 AST 分片",
    "platform.autoProfile": "自动性能档位",
    "domain.eyebrow": "领域偏置",
    "domain.title": "识别偏置",
    "domain.preset": "领域预设",
    "domain.context": "上下文偏置",
    "domain.hotWords": "热词",
    "domain.correctWords": "替换词",
    "domain.glossary": "术语表",
    "clone.eyebrow": "声音复刻",
    "clone.title": "声音复刻 V3",
    "clone.samplePath": "训练样本",
    "clone.speakerId": "Speaker ID",
    "clone.language": "训练语言",
    "clone.referenceText": "参考文本",
    "clone.demoText": "试听文本",
    "advanced.eyebrow": "延迟与净化",
    "advanced.title": "高级通道调优",
    "advanced.startupBuffer": "起播缓冲 (ms)",
    "advanced.noiseGate": "噪声门 (dB)",
    "advanced.silenceHold": "静音保持 (ms)",
    "advanced.dropSilence": "丢弃静音分片",
    "advanced.enableAgc": "启用 AGC",
    "advanced.agcTarget": "AGC 目标 (dBFS)",
    "advanced.agcMaxGain": "AGC 最大增益",
    "advanced.enableDenoise": "启用降噪",
    "advanced.denoiseStrength": "降噪强度",
    "advanced.useClone": "使用克隆音色",
    "advanced.cloneSpeaker": "克隆 Speaker ID",
    "advanced.cloneSpeed": "克隆语速",
    "credentials.eyebrow": "凭证",
    "credentials.title": "引擎接入",
    "credentials.accessToken": "Access Token",
    "credentials.secretKey": "Secret Key",
    "credentials.resourceId": "资源 ID",
    "credentials.note": "虚拟声卡、回环输入和硬件设备都会从本机刷新。装好新的虚拟声卡后点刷新，就会出现在下拉列表里。",
    "placeholder.mapping": "错误词 => 正确词",
    "placeholder.glossary": "源词 => 目标词",
    "option.none": "未选择",
    "option.astVoice": "使用 AST 原生译音",
    "status.ready": "就绪",
    "status.live": "在线",
    "status.error": "异常",
    "status.idle": "空闲",
    "status.streaming": "流式中",
    "status.connecting": "连接中",
    "status.starting": "启动中",
    "status.running": "运行中",
    "status.disabled": "已关闭",
    "status.inputOff": "输入关闭",
    "status.standby": "待命",
    "status.captionsOnly": "仅字幕",
    "status.channelDisabled": "通道已关闭",
    "status.outputDisabled": "播放已关闭",
    "status.astReady": "AST 就绪",
    "status.pythonAudio": "Python 音频核心",
    "status.nativeAudio": "原生 WASAPI 核心",
    "status.nativeScaffold": "Rust 音频核心脚手架",
    "status.virtualNone": "尚未检测到虚拟路由",
    "status.virtualReady": "虚拟声卡就绪",
    "status.autosaved": "已保存到本地。",
    "status.cloneIdle": "先选择控制台里的 Speaker ID，例如 S_xxx 或 ICL_xxx，再上传样本训练音色。",
    "status.cloneFallback": "克隆回退",
    "status.updateIdle": "还没有检查更新。配置清单地址后可以下载安装包。",
    "status.trainingUploaded": "训练样本已上传",
    "status.speakerIdNeeded": "需要 Speaker ID",
    "alert.exportDesktop": "导出功能仅桌面版可用。",
    "alert.startFailed": "启动引擎失败。",
    "alert.cloneSampleMissing": "请先选择训练样本。",
    "alert.updateMissing": "请先检查更新。",
  },
};

function makeCloneOptions() {
  return [
    { value: "", label: "Not Selected", hint: "Use AST voice output" },
    { value: "S_ATMtmRu02", label: "Primary Clone", hint: "S_ATMtmRu02 / Ready" },
    { value: "S_zTMtmRu02", label: "Clone Slot 02", hint: "S_zTMtmRu02 / Console slot" },
    { value: "S_yTMtmRu02", label: "Clone Slot 03", hint: "S_yTMtmRu02 / Console slot" },
    { value: "S_xTMtmRu02", label: "Clone Slot 04", hint: "S_xTMtmRu02 / Console slot" },
    { value: "S_wTMtmRu02", label: "Clone Slot 05", hint: "S_wTMtmRu02 / Console slot" },
    { value: "S_vTMtmRu02", label: "Clone Slot 06", hint: "S_vTMtmRu02 / Console slot" },
    { value: "S_uTMtmRu02", label: "Clone Slot 07", hint: "S_uTMtmRu02 / Console slot" },
    { value: "S_tTMtmRu02", label: "Clone Slot 08", hint: "S_tTMtmRu02 / Console slot" },
    { value: "S_sTMtmRu02", label: "Clone Slot 09", hint: "S_sTMtmRu02 / Console slot" },
    { value: "S_rTMtmRu02", label: "Clone Slot 10", hint: "S_rTMtmRu02 / Console slot" },
  ];
}

function makeAstVoiceOptions() {
  return [
    { value: "", label: "Default AST Voice", hint: "Default / neutral / fastest setup" },
    { value: "zh_female_vv_uranus_bigtts", label: "Vivi 2.0", hint: "Female / bright / clear / lively" },
    { value: "zh_female_xiaohe_uranus_bigtts", label: "Xiaohe 2.0", hint: "Female / soft / steady / natural" },
    { value: "zh_female_wenroushunv_mars_bigtts", label: "Wenrou", hint: "Female / warm / gentle / relaxed" },
    { value: "zh_male_m191_uranus_bigtts", label: "Yunzhou 2.0", hint: "Male / deep / natural / broadcast" },
    { value: "zh_male_taocheng_uranus_bigtts", label: "Xiaotian 2.0", hint: "Male / clean / steady / neutral" },
    { value: "zh_male_ruyaqingnian_mars_bigtts", label: "Ruya", hint: "Male / gentle / calm / soft" },
  ];
}

const AST_VOICE_COPY = {
  en: {
    "": { label: "Default AST Voice", hint: "Default / neutral / fastest setup" },
    zh_female_vv_uranus_bigtts: { label: "Vivi 2.0", hint: "Female / bright / clear / lively" },
    zh_female_xiaohe_uranus_bigtts: { label: "Xiaohe 2.0", hint: "Female / soft / steady / natural" },
    zh_female_wenroushunv_mars_bigtts: { label: "Wenrou", hint: "Female / warm / gentle / relaxed" },
    zh_male_m191_uranus_bigtts: { label: "Yunzhou 2.0", hint: "Male / deep / natural / broadcast" },
    zh_male_taocheng_uranus_bigtts: { label: "Xiaotian 2.0", hint: "Male / clean / steady / neutral" },
    zh_male_ruyaqingnian_mars_bigtts: { label: "Ruya", hint: "Male / gentle / calm / soft" },
  },
  zh: {
    "": { label: "默认 AST 音色", hint: "默认 / 中性 / 接入最快" },
    zh_female_vv_uranus_bigtts: { label: "Vivi 2.0", hint: "女声 / 清亮 / 通透 / 活力" },
    zh_female_xiaohe_uranus_bigtts: { label: "小禾 2.0", hint: "女声 / 柔和 / 稳定 / 自然" },
    zh_female_wenroushunv_mars_bigtts: { label: "温柔", hint: "女声 / 温暖 / 轻柔 / 放松" },
    zh_male_m191_uranus_bigtts: { label: "云舟 2.0", hint: "男声 / 低沉 / 自然 / 播报感" },
    zh_male_taocheng_uranus_bigtts: { label: "晓天 2.0", hint: "男声 / 干净 / 稳定 / 中性" },
    zh_male_ruyaqingnian_mars_bigtts: { label: "儒雅", hint: "男声 / 温和 / 平静 / 柔和" },
  },
};

const fallbackOptionGroups = {
  scene: Object.entries(SCENE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "domain-preset": Object.entries(DOMAIN_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "a-input": [
    { value: "mic-main", label: "Microphone (BRIO)", hint: "Microphone / 1ch" },
    { value: "mic-cable", label: "CABLE Output", hint: "Virtual microphone / 2ch" },
  ],
  "a-output": [
    { value: "cable-tx", label: "CABLE Input", hint: "Virtual playback / 2ch" },
    { value: "speaker-main", label: "Speakers (Realtek)", hint: "Playback / 2ch" },
  ],
  "a-monitor-output": [
    { value: "headphones", label: "Headphones", hint: "Playback / 2ch" },
    { value: "speaker-main", label: "Speakers (Realtek)", hint: "Playback / 2ch" },
  ],
  "b-input": [
    { value: "discord-loopback", label: "Discord RX Loopback", hint: "Virtual loopback / 2ch" },
    { value: "system-loopback", label: "Speakers Loopback", hint: "Loopback capture / 2ch" },
  ],
  "b-output": [
    { value: "headphones", label: "Headphones", hint: "Playback / 2ch" },
    { value: "speaker-main", label: "Speakers (Realtek)", hint: "Playback / 2ch" },
  ],
  "b-monitor-output": [
    { value: "headphones", label: "Headphones", hint: "Playback / 2ch" },
    { value: "speaker-main", label: "Speakers (Realtek)", hint: "Playback / 2ch" },
  ],
  "c-input": [
    { value: "rust-loopback", label: "Rust RX Loopback", hint: "Game voice loopback / 2ch" },
    { value: "vm-bus", label: "VoiceMeeter AUX Output", hint: "Mixer loopback / 2ch" },
  ],
  "c-output": [
    { value: "headphones", label: "Headphones", hint: "Playback / 2ch" },
    { value: "monitor-bus", label: "Monitor Bus", hint: "Virtual monitor / 2ch" },
  ],
  "c-monitor-output": [
    { value: "headphones", label: "Headphones", hint: "Playback / 2ch" },
    { value: "speaker-main", label: "Speakers (Realtek)", hint: "Playback / 2ch" },
  ],
  "voice-clone-record-device": [
    { value: "mic-main", label: "Microphone (BRIO)", hint: "Microphone / 1ch" },
    { value: "mic-cable", label: "CABLE Output", hint: "Virtual microphone / 2ch" },
  ],
  "a-source": Object.entries(LANGUAGE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "a-target": Object.entries(LANGUAGE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "a-speaker": makeAstVoiceOptions(),
  "b-source": Object.entries(LANGUAGE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "b-target": Object.entries(LANGUAGE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "b-speaker": makeAstVoiceOptions(),
  "c-source": Object.entries(LANGUAGE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "c-target": Object.entries(LANGUAGE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "c-speaker": makeAstVoiceOptions(),
  "a-profile": Object.entries(PROFILE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "b-profile": Object.entries(PROFILE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "c-profile": Object.entries(PROFILE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "a-subtitle": Object.entries(SUBTITLE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "b-subtitle": Object.entries(SUBTITLE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "c-subtitle": Object.entries(SUBTITLE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "voice-clone-language": Object.entries(CLONE_TRAIN_LANGUAGE_COPY.en).map(([value, copy]) => ({ value, ...copy })),
  "audio-capture-backend": [
    { value: "python", label: "Python Capture", hint: "Stable fallback path" },
    { value: "native", label: "Native Capture", hint: "Rust CoreAudio/WASAPI low-latency path" },
  ],
  "audio-resampler-quality": [
    { value: "sinc-lite", label: "Sinc Lite", hint: "Higher quality cubic resampling" },
    { value: "linear", label: "Linear", hint: "Lowest CPU fallback" },
  ],
  "audio-vad-mode": [
    { value: "adaptive", label: "Adaptive VAD", hint: "Noise floor + ZCR speech scoring" },
    { value: "gate", label: "Gate", hint: "Simple RMS gate" },
  ],
  "audio-playback-backend": [
    { value: "python", label: "Python Playback", hint: "Stable current playback" },
    { value: "native", label: "Native Playback", hint: "Rust playback protocol ready / safe fallback" },
  ],
  "voice-clone-speaker-id": makeCloneOptions(),
  "a-clone-speaker": makeCloneOptions(),
  "b-clone-speaker": makeCloneOptions(),
  "c-clone-speaker": makeCloneOptions(),
};

const fallbackState = {
  values: {
    scene: "discord_bidirectional",
    "ui-language": "zh",
    "domain-preset": "rust",
    "domain-context":
      "This is a real-time voice conversation about Rust raids, farming, roaming comms, and virtual audio routing.",
    "domain-hot-words":
      "Rust, TC, raid, counter raid, sulfur, scrap, recycler, Bradley, Chinook, Cargo, Launch Site, AK, MP5, C4, satchel, rocket",
    "domain-correct-words": "tc => TC\nak 47 => AK\nmp 5 => MP5\nc 4 => C4",
    "domain-glossary":
      "Tool Cupboard => Tool Cupboard (TC)\nCounter Raid => Counter Raid\nSulfur => Sulfur\nScrap => Scrap",
    "update-manifest-url": "",
    "audio-capture-backend": "python",
    "audio-native-fallback": "1",
    "audio-pre-roll-ms": "160",
    "audio-resampler-quality": "sinc-lite",
    "audio-vad-mode": "adaptive",
    "audio-noise-floor": "1",
    "audio-adaptive-chunking": "1",
    "audio-playback-backend": "python",
    "audio-auto-profile": "1",
    "voice-clone-speaker-id": "S_ATMtmRu02",
    "voice-clone-sample-path": "",
    "voice-clone-reference-text": "",
    "voice-clone-demo-text": "This is a cloned voice preview for Nova Interp.",
    "voice-clone-language": "zh",
    "voice-clone-record-device": "mic-main",
    "a-enabled": "1",
    "a-input-enabled": "1",
    "a-output-enabled": "1",
    "a-monitor-enabled": "1",
    "a-input": "mic-main",
    "a-output": "cable-tx",
    "a-monitor-output": "headphones",
    "a-source": "zh",
    "a-target": "en",
    "a-speaker": "",
    "a-profile": "turbo",
    "a-subtitle": "bilingual",
    "a-startup-buffer": "24",
    "a-noise-gate": "-46",
    "a-hold-ms": "180",
    "a-skip-silence": "1",
    "a-enable-agc": "1",
    "a-agc-target": "-18",
    "a-agc-max-gain": "6",
    "a-enable-denoise": "1",
    "a-denoise-strength": "0.22",
    "a-clone-enabled": "1",
    "a-clone-speaker": "S_ATMtmRu02",
    "a-clone-speed": "1.0",
    "b-enabled": "1",
    "b-input-enabled": "1",
    "b-output-enabled": "1",
    "b-monitor-enabled": "0",
    "b-input": "discord-loopback",
    "b-output": "headphones",
    "b-monitor-output": "headphones",
    "b-source": "en",
    "b-target": "zh",
    "b-speaker": "",
    "b-profile": "turbo",
    "b-subtitle": "bilingual",
    "b-startup-buffer": "28",
    "b-noise-gate": "-48",
    "b-hold-ms": "220",
    "b-skip-silence": "1",
    "b-enable-agc": "1",
    "b-agc-target": "-18",
    "b-agc-max-gain": "6",
    "b-enable-denoise": "1",
    "b-denoise-strength": "0.24",
    "b-clone-enabled": "0",
    "b-clone-speaker": "S_ATMtmRu02",
    "b-clone-speed": "1.0",
    "c-enabled": "0",
    "c-input-enabled": "1",
    "c-output-enabled": "1",
    "c-monitor-enabled": "0",
    "c-input": "rust-loopback",
    "c-output": "headphones",
    "c-monitor-output": "headphones",
    "c-source": "en",
    "c-target": "zh",
    "c-speaker": "",
    "c-profile": "balanced",
    "c-subtitle": "bilingual",
    "c-startup-buffer": "36",
    "c-noise-gate": "-54",
    "c-hold-ms": "260",
    "c-skip-silence": "1",
    "c-enable-agc": "1",
    "c-agc-target": "-18",
    "c-agc-max-gain": "6",
    "c-enable-denoise": "1",
    "c-denoise-strength": "0.28",
    "c-clone-enabled": "0",
    "c-clone-speaker": "",
    "c-clone-speed": "1.0",
    ...(fallbackExternalState.values || {}),
  },
  credentials: {
    appId: "",
    accessToken: "",
    secretKey: "",
    resourceId: "volc.service_type.10053",
    ...(fallbackExternalState.credentials || {}),
  },
  version: fallbackExternalState.version || { version: "0.5.0", channel: "alpha" },
  optionGroups: fallbackExternalState.optionGroups || fallbackOptionGroups,
  domain:
    fallbackExternalState.domain || {
      id: "rust",
      label: "Rust Game",
      description: "Bias toward Rust comms, raids, farming, and route names.",
    },
  devices:
    fallbackExternalState.devices || {
      inputs: 3,
      outputs: 3,
      virtualInputs: 2,
      virtualOutputs: 2,
    },
  nativeAudioCore:
    fallbackExternalState.nativeAudioCore || {
      available: false,
      enumerated: false,
      runtime: "python",
      binaryPath: "",
      deviceCount: 0,
    },
  voiceClone:
    fallbackExternalState.voiceClone || {
      speakerId: "S_ATMtmRu02",
      statusCode: null,
      statusLabel: "Ready",
      message: "",
      samplePath: "",
      recordDeviceId: "mic-main",
      recording: false,
      recordingDeviceId: "",
      recordingDeviceName: "",
      recordingStartedAt: 0,
      recordingDurationSec: 0,
      recordingLevelDb: -96,
      activeChannels: ["Outbound English"],
      fallbackChannels: [],
      runtimeLanguages: ["en"],
      catalog: makeCloneOptions().slice(1).map((item) => ({
        speaker_id: item.value,
        label: item.label,
        note: item.hint,
        status_label: "Ready",
      })),
    },
  updater:
    fallbackExternalState.updater || {
      current: { version: "0.5.0", channel: "alpha", manifest_url: "" },
      manifestUrl: "",
      lastCheck: null,
      result: null,
      download: null,
    },
  channels:
    fallbackExternalState.channels || {
      a: {
        title: "Outbound English",
        copy: "Your microphone translated for Discord, games, or a virtual cable.",
        paneTitle: "A · Outbound Feed",
      },
      b: {
        title: "Discord Inbound",
        copy: "Discord or remote speech translated back to your monitor bus.",
        paneTitle: "B · Discord Feed",
      },
      c: {
        title: "Game Voice Inbound",
        copy: "Game voice loopback translated locally without hijacking the whole game mix.",
        paneTitle: "C · Game Feed",
      },
    },
  transcripts:
    fallbackExternalState.transcripts || {
      a: [
        {
          time: "02:31:08",
          source: "我们刚把硫磺搬回 TC，准备开始抄家。",
          target: "We just moved the sulfur back to TC and we're about to start the raid.",
        },
      ],
      b: [
        {
          time: "02:31:12",
          source: "Hold Launch Site and keep the rockets for the garage door.",
          target: "守住 Launch Site，把火箭留给车库门。",
        },
      ],
      c: [
        {
          time: "02:31:19",
          source: "Two on the road by Oxum's, one has an MP5.",
          target: "Oxum's 路边有两个人，其中一个拿着 MP5。",
        },
      ],
    },
  partials:
    fallbackExternalState.partials || {
      a: {
        source: "门外有人，先卡住门口。",
        target: "There are people outside. Hold the door first.",
      },
      b: {
        source: "We are moving scrap to Outpost now.",
        target: "我们现在把废料搬去 Outpost。",
      },
      c: {
        source: "Someone is pushing from the recycler side.",
        target: "有人从回收机那边压过来了。",
      },
    },
  runtime:
    fallbackExternalState.runtime || {
      running: false,
      globalStatus: "Ready",
      globalHint: "Rust bias enabled / 2 virtual outputs detected.",
      channels: {
        a: {
          signal: "idle",
          label: "Ready",
          pane: "Idle",
          status: "Ready",
          stats: { audio_level_db: -58, input_queue_depth: 0, dropped_silent_chunks: 4 },
        },
        b: {
          signal: "idle",
          label: "Ready",
          pane: "Idle",
          status: "Ready",
          stats: { audio_level_db: -61, input_queue_depth: 0, dropped_silent_chunks: 2 },
        },
        c: {
          signal: "idle",
          label: "Disabled",
          pane: "Disabled",
          status: "Channel disabled",
          stats: { audio_level_db: -72, input_queue_depth: 0, dropped_silent_chunks: 0 },
        },
      },
      metrics: {
        inputA: "-58 dB / Q00 / Drop 4",
        inputB: "-61 dB / Q00 / Drop 2",
        inputC: "-72 dB / Q00 / Drop 0",
        ast: "--",
        tts: "--",
      },
    },
};

const appState = clone(fallbackState);
const TOP_CONTROLS_COLLAPSED_KEY = "nova.topControlsCollapsed";

const app = document.getElementById("app");
const topControls = document.getElementById("topControls");
const layoutToggleButton = document.getElementById("layoutToggleButton");
const drawer = document.getElementById("credentialsDrawer");
const biasDrawer = document.getElementById("biasDrawer");
const latencyDrawer = document.getElementById("latencyDrawer");
const channelDrawer = document.getElementById("channelDrawer");
const modalBackdrop = document.getElementById("modalBackdrop");
const engineStateTag = document.getElementById("engineStateTag");
const domainTag = document.getElementById("domainTag");
const nativeCoreTag = document.getElementById("nativeCoreTag");
const brandCopy = document.getElementById("brandCopy");
const routeCopy = document.getElementById("routeCopy");
const astCoreCopy = document.getElementById("astCoreCopy");
const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const settingsButton = document.getElementById("settingsButton");
const biasButton = document.getElementById("biasButton");
const latencyButton = document.getElementById("latencyButton");
const refreshButton = document.getElementById("refreshButton");
const saveConfigButton = document.getElementById("saveConfigButton");
const exportSessionButton = document.getElementById("exportSessionButton");
const languageToggleButton = document.getElementById("languageToggleButton");
const checkUpdateButton = document.getElementById("checkUpdateButton");
const downloadUpdateButton = document.getElementById("downloadUpdateButton");
const updateStatusNote = document.getElementById("updateStatusNote");
const audioCorePill = document.getElementById("audioCorePill");
const cloneStatusNote = document.getElementById("cloneStatusNote");
const closeDrawerButton = document.getElementById("closeDrawerButton");
const closeBiasDrawerButton = document.getElementById("closeBiasDrawerButton");
const closeLatencyDrawerButton = document.getElementById("closeLatencyDrawerButton");
const closeChannelDrawerButton = document.getElementById("closeChannelDrawerButton");
const channelDrawerEyebrow = document.getElementById("channelDrawerEyebrow");
const channelDrawerTitle = document.getElementById("channelDrawerTitle");
const channelDrawerCopy = document.getElementById("channelDrawerCopy");
const virtualDeviceHint = document.getElementById("virtualDeviceHint");
const summaryAst = document.getElementById("summaryAst");
const routeCard = document.getElementById("routeCard");
const latencySummaryScope = document.getElementById("latencySummaryScope");
const latencySummaryFirstAudio = document.getElementById("latencySummaryFirstAudio");
const latencySummaryRecognition = document.getElementById("latencySummaryRecognition");
const latencySummaryTranslation = document.getElementById("latencySummaryTranslation");
const latencySummaryTts = document.getElementById("latencySummaryTts");

const credentialAppId = document.getElementById("credentialAppId");
const credentialAccessToken = document.getElementById("credentialAccessToken");
const credentialSecretKey = document.getElementById("credentialSecretKey");
const credentialResourceId = document.getElementById("credentialResourceId");

const domainContextInput = document.getElementById("domainContextInput");
const domainHotWordsInput = document.getElementById("domainHotWordsInput");
const domainCorrectWordsInput = document.getElementById("domainCorrectWordsInput");
const domainGlossaryInput = document.getElementById("domainGlossaryInput");
const updateManifestInput = document.getElementById("updateManifestInput");
const audioPreRollInput = document.getElementById("audioPreRollInput");
const audioNativeFallbackInput = document.getElementById("audioNativeFallbackInput");
const audioNoiseFloorInput = document.getElementById("audioNoiseFloorInput");
const audioAdaptiveChunkingInput = document.getElementById("audioAdaptiveChunkingInput");
const audioAutoProfileInput = document.getElementById("audioAutoProfileInput");
const audioCoreStatusNote = document.getElementById("audioCoreStatusNote");
const voiceCloneSamplePathInput = document.getElementById("voiceCloneSamplePathInput");
const voiceCloneReferenceInput = document.getElementById("voiceCloneReferenceInput");
const voiceCloneDemoInput = document.getElementById("voiceCloneDemoInput");
const voiceCloneBrowseButton = document.getElementById("voiceCloneBrowseButton");
const voiceCloneRecordButton = document.getElementById("voiceCloneRecordButton");
const voiceCloneRecordNote = document.getElementById("voiceCloneRecordNote");
const trainVoiceCloneButton = document.getElementById("trainVoiceCloneButton");
const refreshVoiceCloneButton = document.getElementById("refreshVoiceCloneButton");
const voicePreviewRefs = {
  a: {
    button: document.getElementById("aPreviewVoiceButton"),
    note: document.getElementById("aPreviewVoiceNote"),
  },
  b: {
    button: document.getElementById("bPreviewVoiceButton"),
    note: document.getElementById("bPreviewVoiceNote"),
  },
  c: {
    button: document.getElementById("cPreviewVoiceButton"),
    note: document.getElementById("cPreviewVoiceNote"),
  },
};

const channelRefs = {
  a: makeChannelRefs("A", "a", "blue"),
  b: makeChannelRefs("B", "b", "green"),
  c: makeChannelRefs("C", "c", "amber"),
};

const routeDetailRefs = {
  a: makeRouteDetailRefs("A"),
  b: makeRouteDetailRefs("B"),
  c: makeRouteDetailRefs("C"),
  ast: {
    status: document.getElementById("routeDetailAstStatus"),
    path: document.getElementById("routeDetailAstPath"),
    astLatency: document.getElementById("routeDetailAstLatency"),
    ttsLatency: document.getElementById("routeDetailTtsLatency"),
    running: document.getElementById("routeDetailRunning"),
  },
};

const latencyRefs = {
  a: makeLatencyRefs("A", "a"),
  b: makeLatencyRefs("B", "b"),
  c: makeLatencyRefs("C", "c"),
};

const advancedFieldInputs = {
  "update-manifest-url": updateManifestInput,
  "audio-pre-roll-ms": audioPreRollInput,
  "voice-clone-sample-path": voiceCloneSamplePathInput,
  "voice-clone-reference-text": voiceCloneReferenceInput,
  "voice-clone-demo-text": voiceCloneDemoInput,
  "domain-context": domainContextInput,
  "domain-hot-words": domainHotWordsInput,
  "domain-correct-words": domainCorrectWordsInput,
  "domain-glossary": domainGlossaryInput,
};

const checkboxInputs = {
  "audio-native-fallback": audioNativeFallbackInput,
  "audio-noise-floor": audioNoiseFloorInput,
  "audio-adaptive-chunking": audioAdaptiveChunkingInput,
  "audio-auto-profile": audioAutoProfileInput,
};
const numericFieldInputs = {};
const transcriptScrollState = new Map();
CHANNELS.forEach((alias) => {
  checkboxInputs[`${alias}-enabled`] = channelRefs[alias].channelToggle;
  checkboxInputs[`${alias}-input-enabled`] = channelRefs[alias].inputToggle;
  checkboxInputs[`${alias}-output-enabled`] = channelRefs[alias].outputToggle;
  checkboxInputs[`${alias}-monitor-enabled`] = document.getElementById(`${alias}MonitorEnabledInput`);
  checkboxInputs[`${alias}-skip-silence`] = document.getElementById(`${alias}SkipSilenceInput`);
  checkboxInputs[`${alias}-enable-agc`] = document.getElementById(`${alias}EnableAgcInput`);
  checkboxInputs[`${alias}-enable-denoise`] = document.getElementById(`${alias}EnableDenoiseInput`);
  checkboxInputs[`${alias}-clone-enabled`] = document.getElementById(`${alias}CloneEnabledInput`);
  numericFieldInputs[`${alias}-startup-buffer`] = document.getElementById(`${alias}StartupBufferInput`);
  numericFieldInputs[`${alias}-noise-gate`] = document.getElementById(`${alias}NoiseGateInput`);
  numericFieldInputs[`${alias}-hold-ms`] = document.getElementById(`${alias}HoldInput`);
  numericFieldInputs[`${alias}-agc-target`] = document.getElementById(`${alias}AgcTargetInput`);
  numericFieldInputs[`${alias}-agc-max-gain`] = document.getElementById(`${alias}AgcMaxGainInput`);
  numericFieldInputs[`${alias}-denoise-strength`] = document.getElementById(`${alias}DenoiseStrengthInput`);
  numericFieldInputs[`${alias}-clone-speed`] = document.getElementById(`${alias}CloneSpeedInput`);
  transcriptScrollState.set(alias, { stickToBottom: true, top: 0 });
  channelRefs[alias].transcript?.addEventListener(
    "scroll",
    () => {
      const node = channelRefs[alias].transcript;
      if (!node) {
        return;
      }
      transcriptScrollState.set(alias, {
        stickToBottom: isTranscriptNearBottom(node),
        top: node.scrollTop,
      });
    },
    { passive: true }
  );
});

const channelPanels = Array.from(document.querySelectorAll(".channel-detail-panel"));

let backendBridge = null;
let backendMode = false;
let activeDrawer = "";
let activeChannelDrawer = "a";
let demoTimer = null;
let pollTimer = null;
let saveTimer = null;
let noticeTimer = null;
let pollInFlight = false;
let previewInFlight = "";
let previewJobId = "";
let previewAudio = null;
let openSelectKey = "";
let openSelectMenu = null;
let openSelectAnchor = null;
const selectScrollState = new Map();
let transientNotice = "";
let topControlsCollapsed = false;
let autoSubtitleFocus = false;

applyServerState(fallbackExternalState);

function makeChannelRefs(suffix, alias, accent) {
  return {
    alias,
    accent,
    card: document.getElementById(`channelCard${suffix}`),
    title: document.getElementById(`channel${suffix}Title`),
    copy: document.getElementById(`channel${suffix}Copy`),
    paneTitle: document.getElementById(`pane${suffix}Title`),
    paneStatus: document.getElementById(`pane${suffix}Status`),
    summary: document.getElementById(`summary${suffix}`),
    routeInput: document.getElementById(`routeInput${suffix}`),
    routeOutput: document.getElementById(`routeOutput${suffix}`),
    routeNote: document.getElementById(`${alias}RouteNote`),
    latencyChip: document.getElementById(`${alias}LatencyChip`),
    queueChip: document.getElementById(`${alias}QueueChip`),
    transcript: document.getElementById(`transcript${suffix}`),
    liveSource: document.getElementById(`livePreview${suffix}Source`),
    liveTarget: document.getElementById(`livePreview${suffix}Target`),
    routeInputNode: document.querySelector(`.node-input-${alias}`),
    routeOutputNode: document.querySelector(`.node-output-${alias}`),
    visualizer: document.querySelector(`[data-visualizer='${alias}']`),
    statusPill: document.querySelector(`[data-state-pill='${alias}']`),
    toolsButton: document.getElementById(`${alias}ChannelToolsButton`),
    channelToggle: document.getElementById(`${suffix.toLowerCase()}EnabledInput`),
    inputToggle: document.getElementById(`${suffix.toLowerCase()}InputEnabledInput`),
    outputToggle: document.getElementById(`${suffix.toLowerCase()}OutputEnabledInput`),
    metricInput: document.getElementById(`metricInput${suffix}`),
  };
}

function makeLatencyRefs(suffix, alias) {
  return {
    card: document.getElementById(`latencyCard${suffix}`),
    title: document.getElementById(`latencyTitle${suffix}`),
    status: document.getElementById(`latencyStatus${suffix}`),
    firstAudio: document.getElementById(`latency${suffix}FirstAudio`),
    recognition: document.getElementById(`latency${suffix}Recognition`),
    translation: document.getElementById(`latency${suffix}Translation`),
    tts: document.getElementById(`latency${suffix}Tts`),
  };
}

function makeRouteDetailRefs(suffix) {
  return {
    status: document.getElementById(`routeDetail${suffix}Status`),
    input: document.getElementById(`routeDetail${suffix}Input`),
    output: document.getElementById(`routeDetail${suffix}Output`),
    latency: document.getElementById(`routeDetail${suffix}Latency`),
    queue: document.getElementById(`routeDetail${suffix}Queue`),
    level: document.getElementById(`routeDetail${suffix}Level`),
  };
}

function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

function uiLanguage() {
  return appState.values["ui-language"] === "en" ? "en" : "zh";
}

function t(key) {
  const language = uiLanguage();
  return I18N[language]?.[key] || I18N.en[key] || key;
}

function readTopControlsPreference() {
  try {
    window.localStorage.removeItem(TOP_CONTROLS_COLLAPSED_KEY);
  } catch {
    // Ignore storage failures and fall back to expanded controls.
  }
  return false;
}

function saveTopControlsPreference(value) {
  try {
    // Keep subtitle mode session-scoped so the app never reopens with the routing UI hidden.
    if (!value) {
      window.localStorage.removeItem(TOP_CONTROLS_COLLAPSED_KEY);
    }
  } catch {
    // Ignore storage failures and keep the session state only.
  }
}

function renderTopControlsVisibility() {
  app.classList.toggle("is-subtitle-focus", topControlsCollapsed);
  if (!layoutToggleButton) {
    return;
  }
  const label = topControlsCollapsed
    ? uiLanguage() === "zh"
      ? "显示设置"
      : "Show Controls"
    : uiLanguage() === "zh"
      ? "字幕模式"
      : "Subtitle Mode";
  layoutToggleButton.textContent = label;
  layoutToggleButton.title = topControlsCollapsed
    ? uiLanguage() === "zh"
      ? "显示顶部通道配置"
      : "Show channel controls"
    : uiLanguage() === "zh"
      ? "隐藏通道配置，保留线路诊断和下方字幕区"
      : "Hide channel controls, keep route diagnostics and subtitles";
  layoutToggleButton.setAttribute("aria-pressed", topControlsCollapsed ? "true" : "false");
}

function setTopControlsCollapsed(value) {
  topControlsCollapsed = Boolean(value);
  if (topControlsCollapsed) {
    closeAllSelects();
    closeDrawers();
  }
  saveTopControlsPreference(topControlsCollapsed);
  renderTopControlsVisibility();
}

function toggleTopControlsCollapsed() {
  setTopControlsCollapsed(!topControlsCollapsed);
}

function normalizeStatusKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, "");
}

function displayStatus(value) {
  const mapping = {
    ready: "status.ready",
    live: "status.live",
    error: "status.error",
    idle: "status.idle",
    streaming: "status.streaming",
    connecting: "status.connecting",
    starting: "status.starting",
    running: "status.running",
    disabled: "status.disabled",
    inputoff: "status.inputOff",
    standby: "status.standby",
    captionsonly: "status.captionsOnly",
    channeldisabled: "status.channelDisabled",
  };
  const key = mapping[normalizeStatusKey(value)];
  return key ? t(key) : String(value || "");
}

function channelLocaleCopy(alias) {
  if (uiLanguage() === "zh") {
    return {
      a: {
        title: "我的麦克风 -> 英文外发",
        copy: "把你的中文麦克风翻成目标语，送到 Discord、游戏或虚拟声卡。",
        paneTitle: "A · 外发字幕",
      },
      b: {
        title: "Discord / 远端 -> 中文监听",
        copy: "把 Discord 或远端的英文语音翻回中文，送回你的监听耳机。",
        paneTitle: "B · Discord 字幕",
      },
      c: {
        title: "游戏语音 -> 中文监听",
        copy: "专门给 Rust 或游戏内语音预留的入站翻译，不直接劫持整路游戏音效。",
        paneTitle: "C · 游戏语音字幕",
      },
    }[alias];
  }
  return appState.channels?.[alias] || fallbackState.channels[alias];
}

function summarizeDomain() {
  const domainId = appState.values["domain-preset"];
  const copy = DOMAIN_COPY[uiLanguage()][domainId] || DOMAIN_COPY.en.generic;
  const virtualOutputs = Number(appState.devices?.virtualOutputs || 0);
  const cloneFallbacks = appState.voiceClone?.fallbackChannels || [];
  const parts = [copy.hint];
  if (virtualOutputs) {
    parts.push(uiLanguage() === "zh" ? `检测到 ${virtualOutputs} 个虚拟输出` : `${virtualOutputs} virtual outputs detected`);
  }
  if (cloneFallbacks.length) {
    parts.push(
      uiLanguage() === "zh"
        ? `克隆回退: ${cloneFallbacks.join(" / ")}`
        : `Clone fallback: ${cloneFallbacks.join(" / ")}`,
    );
  }
  return parts.join(" / ");
}

function setNotice(message, timeout = 3200) {
  transientNotice = message;
  clearTimeout(noticeTimer);
  noticeTimer = window.setTimeout(() => {
    transientNotice = "";
    renderHeader();
  }, timeout);
  renderHeader();
}

function localizeOption(key, option) {
  const normalizedOption = normalizeOption(option);
  const language = uiLanguage();
  let localized = null;

  if (key === "scene") {
    localized = SCENE_COPY[language][normalizedOption.value];
  } else if (key === "domain-preset") {
    localized = DOMAIN_COPY[language][normalizedOption.value];
  } else if (key === "voice-clone-language") {
    localized = CLONE_TRAIN_LANGUAGE_COPY[language][normalizedOption.value];
  } else if (key.endsWith("-source") || key.endsWith("-target")) {
    localized = LANGUAGE_COPY[language][normalizedOption.value];
  } else if (key.endsWith("-profile")) {
    localized = PROFILE_COPY[language][normalizedOption.value];
  } else if (key.endsWith("-subtitle")) {
    localized = SUBTITLE_COPY[language][normalizedOption.value];
  } else if (key.endsWith("-speaker") && !key.includes("-clone-speaker")) {
    localized = AST_VOICE_COPY[language]?.[normalizedOption.value];
  } else if (key === "voice-clone-speaker-id" || key.endsWith("-clone-speaker")) {
    if (!normalizedOption.value) {
      localized = { label: t("option.none"), hint: t("option.astVoice") };
    }
  }

  return localized ? { ...normalizedOption, ...localized } : normalizedOption;
}

function normalizeOption(option) {
  const value = String(option?.value ?? "").trim();
  const label = String(option?.label ?? value).trim() || value;
  const hint = String(option?.hint ?? "").trim();
  return { ...option, value, label, hint };
}

function buildCloneCatalogOptions() {
  const options = [{ value: "", label: t("option.none"), hint: t("option.astVoice") }];
  const seen = new Set([""]);
  const catalog = appState.voiceClone?.catalog || [];
  catalog.forEach((item) => {
    const value = String(item.speaker_id || "").trim();
    if (!value || seen.has(value)) {
      return;
    }
    seen.add(value);
    options.push({
      value,
      label: item.label || value,
      hint: [item.status_label, item.note].filter(Boolean).join(" / "),
    });
  });
  const currentValues = [
    appState.values["voice-clone-speaker-id"],
    ...CHANNELS.map((alias) => appState.values[`${alias}-clone-speaker`]),
  ];
  currentValues.forEach((value) => {
    const normalized = String(value || "").trim();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    options.push({ value: normalized, label: normalized, hint: t("status.ready") });
  });
  return options;
}

function normalizeOptionGroups(groups = {}) {
  const normalized = Object.fromEntries(
    Object.entries({ ...fallbackOptionGroups, ...groups }).map(([key, options]) => [
      key,
      Array.isArray(options) ? options.map((option) => normalizeOption(option)) : [],
    ]),
  );
  const cloneOptions = buildCloneCatalogOptions();
  normalized["voice-clone-speaker-id"] = cloneOptions;
  CHANNELS.forEach((alias) => {
    normalized[`${alias}-clone-speaker`] = cloneOptions;
  });
  return normalized;
}

function applyServerState(payload) {
  const nextState = payload && payload.state ? payload.state : payload;
  if (!nextState || typeof nextState !== "object") {
    return;
  }
  if (nextState.values) {
    appState.values = { ...appState.values, ...nextState.values };
  }
  if (nextState.credentials) {
    appState.credentials = { ...appState.credentials, ...nextState.credentials };
  }
  if (nextState.version) {
    appState.version = { ...appState.version, ...nextState.version };
  }
  if (nextState.optionGroups) {
    appState.optionGroups = normalizeOptionGroups(nextState.optionGroups);
  } else {
    appState.optionGroups = normalizeOptionGroups(appState.optionGroups);
  }
  if (nextState.domain) {
    appState.domain = { ...appState.domain, ...nextState.domain };
  }
  if (nextState.devices) {
    appState.devices = { ...appState.devices, ...nextState.devices };
  }
  if (nextState.nativeAudioCore) {
    appState.nativeAudioCore = { ...appState.nativeAudioCore, ...nextState.nativeAudioCore };
  }
  if (nextState.voiceClone) {
    appState.voiceClone = { ...appState.voiceClone, ...nextState.voiceClone };
    appState.optionGroups = normalizeOptionGroups(appState.optionGroups);
  }
  if (nextState.updater) {
    appState.updater = { ...appState.updater, ...nextState.updater };
  }
  if (nextState.channels) {
    appState.channels = { ...appState.channels, ...nextState.channels };
  }
  if (nextState.transcripts) {
    appState.transcripts = { ...appState.transcripts, ...nextState.transcripts };
  }
  if (nextState.partials) {
    appState.partials = { ...appState.partials, ...nextState.partials };
  }
  if (nextState.runtime) {
    appState.runtime = { ...appState.runtime, ...nextState.runtime };
  }
}

async function connectBackend() {
  if (!(window.qt && window.QWebChannel)) {
    return false;
  }
  await new Promise((resolve) => {
    new QWebChannel(window.qt.webChannelTransport, (channel) => {
      backendBridge = channel.objects.novaBridge;
      resolve();
    });
  });
  backendMode = Boolean(backendBridge);
  return backendMode;
}

async function callBackend(method, payload) {
  if (!backendMode || !backendBridge || typeof backendBridge[method] !== "function") {
    return null;
  }
  return new Promise((resolve) => {
    const callback = (result) => {
      if (typeof result !== "string") {
        resolve(result);
        return;
      }
      try {
        resolve(JSON.parse(result));
      } catch {
        resolve(result);
      }
    };
    if (payload === undefined) {
      backendBridge[method](callback);
      return;
    }
    const serialized = typeof payload === "string" ? payload : JSON.stringify(payload);
    backendBridge[method](serialized, callback);
  });
}

function syncInputValue(element, value) {
  if (!element || document.activeElement === element) {
    return;
  }
  element.value = value ?? "";
}

function syncCheckboxValue(element, value, disabled) {
  if (!element) {
    return;
  }
  if (document.activeElement !== element) {
    element.checked = value === "1";
  }
  element.disabled = disabled;
}

function persistFormToState() {
  appState.credentials.appId = credentialAppId.value.trim();
  appState.credentials.accessToken = credentialAccessToken.value.trim();
  appState.credentials.secretKey = credentialSecretKey.value.trim();
  appState.credentials.resourceId = credentialResourceId.value.trim();

  Object.entries(advancedFieldInputs).forEach(([key, element]) => {
    appState.values[key] = element.value;
  });
  Object.entries(numericFieldInputs).forEach(([key, element]) => {
    appState.values[key] = element.value;
  });
  Object.entries(checkboxInputs).forEach(([key, element]) => {
    appState.values[key] = element.checked ? "1" : "0";
  });
}

function currentPayload() {
  persistFormToState();
  return {
    values: { ...appState.values },
    credentials: {
      appId: appState.credentials.appId,
      accessToken: appState.credentials.accessToken,
      secretKey: appState.credentials.secretKey,
      resourceId: appState.credentials.resourceId,
    },
  };
}

function getRawOptionList(key) {
  return appState.optionGroups?.[key] || fallbackOptionGroups[key] || [];
}

function getOptionList(key) {
  const options = getRawOptionList(key);
  const current = String(appState.values[key] || "").trim();
  const list = options.map((option) => localizeOption(key, option));
  if (current && !list.some((option) => option.value === current)) {
    list.push({ value: current, label: current, hint: "" });
  }
  return list;
}

function getOption(key, value = appState.values[key]) {
  return getOptionList(key).find((item) => item.value === value) || getOptionList(key)[0] || null;
}

function getOptionLabel(key, value = appState.values[key]) {
  return getOption(key, value)?.label || "";
}

function getOptionHint(key, value = appState.values[key]) {
  return getOption(key, value)?.hint || "";
}

function applyProfileDefaults(alias) {
  const profile = appState.values[`${alias}-profile`];
  const defaults = PROFILE_DEFAULTS[profile] || PROFILE_DEFAULTS.balanced;
  appState.values[`${alias}-startup-buffer`] = defaults.startup;
  appState.values[`${alias}-noise-gate`] = defaults.gate;
  appState.values[`${alias}-hold-ms`] = defaults.hold;
}

function rememberOpenSelectState() {
  if (!openSelectKey || !openSelectMenu) {
    return;
  }
  selectScrollState.set(openSelectKey, openSelectMenu.scrollTop);
}

function restoreSelectMenuScroll(menu, key) {
  const scrollTop = selectScrollState.get(key) || 0;
  requestAnimationFrame(() => {
    menu.scrollTop = scrollTop;
  });
}

function ensureSelectMenuPortalRoot() {
  let portalRoot = document.querySelector(".select-menu-portal-root");
  if (!portalRoot) {
    portalRoot = document.createElement("div");
    portalRoot.className = "select-menu-portal-root";
    document.body.appendChild(portalRoot);
  }
  return portalRoot;
}

function clearOpenSelectMenu() {
  if (openSelectMenu) {
    openSelectMenu.remove();
  }
  openSelectMenu = null;
  openSelectAnchor = null;
}

function buildSelectSignature(key, options, current, disabled) {
  return JSON.stringify({
    language: uiLanguage(),
    key,
    disabled,
    value: current?.value || "",
    options: options.map((option) => ({
      value: option.value,
      label: option.label,
      hint: option.hint || "",
    })),
  });
}

function closeAllSelects() {
  openSelectKey = "";
  clearOpenSelectMenu();
  document.querySelectorAll(".custom-select.is-open").forEach((element) => {
    element.classList.remove("is-open");
  });
}

function iconChevron() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z"></path>
    </svg>
  `;
}

function escapeAttribute(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function isDeviceRoutingSelect(key) {
  return (
    key.endsWith("-input") ||
    key.endsWith("-output") ||
    key.endsWith("-monitor-output") ||
    key === "voice-clone-record-device"
  );
}

function buildTriggerMarkup(option, showHint = false) {
  const label = escapeAttribute(option?.label || "");
  const hint = escapeAttribute(option?.hint || "");
  return `
    <span class="value-wrap">
      <span class="value" title="${label}">${label}</span>
      ${showHint && hint ? `<span class="hint" title="${hint}">${hint}</span>` : ""}
    </span>
    ${iconChevron()}
  `;
}

function buildSelectMenu(selectRoot, key, options, disabled, isDeviceSelect) {
  const menu = document.createElement("div");
  menu.className = "select-menu is-portal";
  menu.dataset.selectMenu = key;
  menu.addEventListener(
    "scroll",
    () => {
      selectScrollState.set(key, menu.scrollTop);
    },
    { passive: true },
  );
  menu.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  options.forEach((option) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "select-option";
    if (option.value === appState.values[key]) {
      item.classList.add("is-active");
    }
    item.title = option.label;
    const label = escapeAttribute(option.label);
    const hint = escapeAttribute(option.hint || "");
    item.innerHTML = `
      <span class="select-option-label">${label}</span>
      <span class="select-option-hint">${hint}</span>
    `;
    item.addEventListener("click", async () => {
      if (disabled) {
        return;
      }
      appState.values[key] = option.value;
      if (key.endsWith("-profile")) {
        applyProfileDefaults(key.charAt(0));
      }
      closeAllSelects();

      if (backendMode && key === "scene") {
        const response = await callBackend("apply_scene", option.value);
        applyServerState(response);
      } else if (backendMode && key === "domain-preset") {
        const response = await callBackend("apply_domain_pack", option.value);
        applyServerState(response);
      } else {
        scheduleSave();
      }

      renderAll();
    });
    menu.appendChild(item);
  });

  return menu;
}

function positionOpenSelectMenu(selectRoot, menu, isDeviceSelect) {
  const trigger = selectRoot?.querySelector(".select-trigger");
  if (!trigger || !menu) {
    return;
  }
  const rect = trigger.getBoundingClientRect();
  const viewportPadding = 12;
  const preferredWidth = isDeviceSelect ? Math.max(rect.width, 460) : rect.width;
  const width = Math.min(preferredWidth, window.innerWidth - viewportPadding * 2);
  const maxVisibleHeight = isDeviceSelect ? 360 : 260;
  const spaceBelow = window.innerHeight - rect.bottom - viewportPadding - 8;
  const spaceAbove = rect.top - viewportPadding - 8;
  const openUpward = spaceBelow < 170 && spaceAbove > spaceBelow;
  const maxHeight = Math.max(160, Math.min(maxVisibleHeight, openUpward ? spaceAbove : spaceBelow));
  let left = rect.left;
  if (left + width > window.innerWidth - viewportPadding) {
    left = window.innerWidth - viewportPadding - width;
  }
  left = Math.max(viewportPadding, left);
  const top = openUpward ? Math.max(viewportPadding, rect.top - maxHeight - 8) : rect.bottom + 8;
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
  menu.style.width = `${width}px`;
  menu.style.maxHeight = `${maxHeight}px`;
}

function openSelectMenuFor(selectRoot) {
  const meta = selectRoot?._selectMeta;
  if (!selectRoot || !meta || meta.disabled || !meta.current) {
    clearOpenSelectMenu();
    return;
  }
  const portalRoot = ensureSelectMenuPortalRoot();
  if (openSelectMenu && openSelectAnchor === selectRoot && openSelectMenu.dataset.selectMenu === meta.key) {
    positionOpenSelectMenu(selectRoot, openSelectMenu, meta.isDeviceSelect);
    restoreSelectMenuScroll(openSelectMenu, meta.key);
    return;
  }

  clearOpenSelectMenu();
  const menu = buildSelectMenu(selectRoot, meta.key, meta.options, meta.disabled, meta.isDeviceSelect);
  portalRoot.appendChild(menu);
  openSelectMenu = menu;
  openSelectAnchor = selectRoot;
  positionOpenSelectMenu(selectRoot, menu, meta.isDeviceSelect);
  restoreSelectMenuScroll(menu, meta.key);
}

function syncOpenSelectMenu() {
  if (!openSelectKey) {
    clearOpenSelectMenu();
    return;
  }
  const selectRoot = document.querySelector(`.custom-select[data-select="${openSelectKey}"]`);
  if (!selectRoot || selectRoot.classList.contains("is-disabled")) {
    closeAllSelects();
    return;
  }
  selectRoot.classList.add("is-open");
  openSelectMenuFor(selectRoot);
}

function createSelect(selectRoot, key) {
  const options = getOptionList(key);
  const current = getOption(key);
  const disabled = Boolean(
    appState.runtime.running || (appState.voiceClone?.recording && key === "voice-clone-record-device"),
  );
  const isDeviceSelect = isDeviceRoutingSelect(key);
  const shouldStayOpen = !disabled && openSelectKey === key;
  const signature = buildSelectSignature(key, options, current, disabled);

  selectRoot.classList.toggle("is-disabled", disabled);
  selectRoot.classList.toggle("is-open", shouldStayOpen);
  selectRoot.classList.toggle("is-device-select", isDeviceSelect);
  selectRoot._selectMeta = { key, options, current, disabled, isDeviceSelect };
  if (!current) {
    selectRoot.innerHTML = "";
    selectRoot.dataset.selectSignature = "";
    return;
  }

  const existingTrigger = selectRoot.querySelector(".select-trigger");
  if (selectRoot.dataset.selectSignature === signature && existingTrigger) {
    const valueNode = existingTrigger.querySelector(".value");
    if (valueNode && valueNode.textContent !== current.label) {
      valueNode.textContent = current.label;
      valueNode.title = current.label;
      existingTrigger.title = isDeviceSelect && current.hint ? `${current.label} / ${current.hint}` : current.label;
    }
    const hintNode = existingTrigger.querySelector(".hint");
    if (hintNode && hintNode.textContent !== (current.hint || "")) {
      hintNode.textContent = current.hint || "";
      hintNode.title = current.hint || "";
    }
    return;
  }

  selectRoot.innerHTML = "";
  selectRoot.dataset.selectSignature = signature;

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "select-trigger";
  trigger.title = isDeviceSelect && current.hint ? `${current.label} / ${current.hint}` : current.label;
  trigger.innerHTML = buildTriggerMarkup(current, isDeviceSelect);

  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    if (disabled) {
      return;
    }
    const isOpen = selectRoot.classList.contains("is-open");
    rememberOpenSelectState();
    closeAllSelects();
    if (!isOpen) {
      openSelectKey = key;
      selectRoot.classList.add("is-open");
      openSelectMenuFor(selectRoot);
    }
  });

  selectRoot.appendChild(trigger);
}

function renderSelects() {
  if (appState.runtime.running) {
    openSelectKey = "";
  } else {
    rememberOpenSelectState();
  }
  document.querySelectorAll("[data-select]").forEach((element) => {
    createSelect(element, element.dataset.select);
  });
  syncOpenSelectMenu();
}

function renderTranslations() {
  document.documentElement.lang = uiLanguage() === "zh" ? "zh-CN" : "en";
  document.title = t("app.title");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  domainCorrectWordsInput.placeholder = t("placeholder.mapping");
  domainGlossaryInput.placeholder = t("placeholder.glossary");
  languageToggleButton.textContent = uiLanguage() === "zh" ? "EN" : "中文";
}

function renderHeader() {
  const runtime = appState.runtime || {};
  engineStateTag.textContent = displayStatus(runtime.globalStatus || "Ready");
  domainTag.textContent = DOMAIN_COPY[uiLanguage()][appState.values["domain-preset"]]?.label || appState.domain?.label || "Domain";
  brandCopy.textContent = transientNotice || runtime.globalHint || summarizeDomain();
}

function renderCredentials() {
  const disabled = Boolean(appState.runtime.running);
  syncInputValue(credentialAppId, appState.credentials.appId || "");
  syncInputValue(credentialAccessToken, appState.credentials.accessToken || "");
  syncInputValue(credentialSecretKey, appState.credentials.secretKey || "");
  syncInputValue(credentialResourceId, appState.credentials.resourceId || "");
  [credentialAppId, credentialAccessToken, credentialSecretKey, credentialResourceId].forEach((element) => {
    element.disabled = disabled;
  });
}

function renderFieldGroups() {
  const disabled = Boolean(appState.runtime.running);
  Object.entries(advancedFieldInputs).forEach(([key, element]) => {
    syncInputValue(element, appState.values[key] || "");
    element.disabled = disabled;
  });
  Object.entries(numericFieldInputs).forEach(([key, element]) => {
    syncInputValue(element, appState.values[key] || "");
    element.disabled = disabled;
  });
  Object.entries(checkboxInputs).forEach(([key, element]) => {
    syncCheckboxValue(element, appState.values[key], disabled);
  });
}

function localizedVoiceCloneStatus(label) {
  const normalized = normalizeStatusKey(label);
  const map = {
    ready: "status.ready",
    error: "status.error",
    speakeridneeded: "status.speakerIdNeeded",
    recording: "status.recording",
    sampleready: "status.sampleReady",
    uploaded: "status.trainingUploaded",
  };
  return map[normalized] ? t(map[normalized]) : label || t("status.ready");
}

function renderPlatformState() {
  const nativeCore = appState.nativeAudioCore || {};
  const captureBackend = nativeCore.captureBackend || appState.values["audio-capture-backend"] || "python";
  const captureLabel = captureBackend === "native" ? "Native" : "Python";
  if (nativeCore.available && nativeCore.enumerated) {
    nativeCoreTag.textContent = `${captureLabel} Audio Core`;
    audioCorePill.textContent = `${captureLabel} / ${nativeCore.deviceCount || 0}`;
  } else if (nativeCore.available) {
    nativeCoreTag.textContent = t("status.nativeScaffold");
    audioCorePill.textContent = `${captureLabel} / ${t("status.nativeScaffold")}`;
  } else {
    nativeCoreTag.textContent = t("status.pythonAudio");
    audioCorePill.textContent = t("status.pythonAudio");
  }
  if (audioCoreStatusNote) {
    const health = nativeCore.health || {};
    const healthText = nativeCore.available ? (health.ok ? "healthy" : health.error || "not ready") : "binary missing";
    audioCoreStatusNote.textContent = `Capture ${captureLabel} / playback ${nativeCore.playbackBackend || "python"} / ${nativeCore.resamplerQuality || "sinc-lite"} / ${nativeCore.vadMode || "adaptive"} / pre-roll ${nativeCore.preRollMs || appState.values["audio-pre-roll-ms"] || 0}ms / fallback ${nativeCore.fallbackEnabled ? "on" : "off"} / ${healthText}`;
  }

  const updater = appState.updater || {};
  const updateResult = updater.result || null;
  if (updateResult?.ok) {
    if (updateResult.updateAvailable) {
      updateStatusNote.textContent = `v${updateResult.current?.version || "--"} -> v${updateResult.manifest?.version || "--"}`;
    } else {
      updateStatusNote.textContent = `v${updateResult.current?.version || "--"} / latest`;
    }
  } else if (updateResult?.error) {
    updateStatusNote.textContent = updateResult.error;
  } else {
    updateStatusNote.textContent = t("status.updateIdle");
  }

  const voiceClone = appState.voiceClone || {};
  const activeChannels = voiceClone.activeChannels || [];
  const fallbackChannels = voiceClone.fallbackChannels || [];
  const cloneRecording = Boolean(voiceClone.recording);
  const cloneLabel = localizedVoiceCloneStatus(voiceClone.statusLabel);
  const cloneParts = [];
  if (cloneRecording) {
    const duration = Number(voiceClone.recordingDurationSec || 0);
    const inputLabel =
      getOptionLabel("voice-clone-record-device", voiceClone.recordingDeviceId || appState.values["voice-clone-record-device"]) ||
      voiceClone.recordingDeviceName ||
      "--";
    cloneParts.push(`${t("status.recording")} / ${inputLabel} / ${duration.toFixed(1)} s`);
  }
  if (voiceClone.statusLabel && normalizeStatusKey(voiceClone.statusLabel) !== "notconfigured") {
    cloneParts.push(cloneLabel);
    if (activeChannels.length) {
      cloneParts.push(activeChannels.join(" / "));
    }
    if (voiceClone.message) {
      cloneParts.push(voiceClone.message);
    }
  } else {
    cloneParts.push(t("status.cloneIdle"));
  }
  if (fallbackChannels.length) {
    cloneParts.push(`${t("status.cloneFallback")}: ${fallbackChannels.join(" / ")}`);
  }
  cloneStatusNote.textContent = cloneParts.join(" / ");
  voiceCloneRecordButton.textContent = cloneRecording ? t("button.stopRecording") : t("button.recordClone");
  voiceCloneRecordButton.disabled = Boolean(appState.runtime?.running);
  voiceCloneBrowseButton.disabled = cloneRecording;
  trainVoiceCloneButton.disabled = cloneRecording;
  refreshVoiceCloneButton.disabled = cloneRecording;
  voiceCloneSamplePathInput.disabled = Boolean(appState.runtime?.running || cloneRecording);
  voiceCloneRecordNote.textContent = cloneRecording
    ? `${Number(voiceClone.recordingDurationSec || 0).toFixed(1)} s / ${Number(voiceClone.recordingLevelDb ?? -96).toFixed(0)} dB`
    : voiceClone.samplePath
      ? String(voiceClone.samplePath).split(/[/\\\\]/).pop()
      : "";

  const routeParts = ["AST"];
  if (activeChannels.length) {
    routeParts.push(`Clone ${activeChannels.join(" / ")}`);
  } else {
    routeParts.push(t("route.astVoice"));
  }
  if (fallbackChannels.length) {
    routeParts.push(`${t("route.astFallback")} ${fallbackChannels.join(" / ")}`);
  }
  routeParts.push(t("route.gapGuard"));
  astCoreCopy.textContent = routeParts.join(" / ");

  const virtualInputs = Number(appState.devices?.virtualInputs || 0);
  const virtualOutputs = Number(appState.devices?.virtualOutputs || 0);
  if (virtualInputs || virtualOutputs) {
    virtualDeviceHint.textContent =
      uiLanguage() === "zh"
        ? `${virtualInputs} 虚拟输入 / ${virtualOutputs} 虚拟输出`
        : `${virtualInputs} virtual in / ${virtualOutputs} virtual out`;
  } else {
    virtualDeviceHint.textContent = t("status.virtualNone");
  }
  virtualDeviceHint.title = t("credentials.note");
}

function channelSummaryLabel(alias, runtime) {
  return `${alias.toUpperCase()} · ${displayStatus(runtime.label || "Ready")}`;
}

function setVisualizer(element, channelRuntime) {
  const level = Number(channelRuntime?.stats?.audio_level_db ?? -96);
  const hot = level > -48;
  const active = Boolean(appState.runtime.running) || channelRuntime?.signal === "ok" || hot;
  if (!element) {
    return;
  }
  element.classList.toggle("active", active);
  element.classList.toggle("is-hot", hot);
  element.title =
    uiLanguage() === "zh"
      ? `${displayStatus(channelRuntime?.label || "Idle")} / ${level.toFixed(0)} dB`
      : `${displayStatus(channelRuntime?.label || "Idle")} / ${level.toFixed(0)} dB`;
}

function setRouteState(element, signal) {
  if (!element) {
    return;
  }
  element.classList.remove("is-idle", "is-live", "is-error");
  if (signal === "error") {
    element.classList.add("is-error");
  } else if (signal === "ok" || signal === "warning") {
    element.classList.add("is-live");
  } else {
    element.classList.add("is-idle");
  }
}

function setSummaryState(element, signal, accent) {
  if (!element) {
    return;
  }
  element.classList.remove("active", "alt", "amber", "error");
  if (signal === "error") {
    element.classList.add("error");
    return;
  }
  if (signal === "ok" || signal === "warning") {
    element.classList.add("active");
    if (accent === "green") {
      element.classList.add("alt");
    }
    if (accent === "amber") {
      element.classList.add("amber");
    }
  }
}

function toFiniteNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatLatencyValue(value) {
  const numeric = toFiniteNumber(value);
  return numeric === null ? "--" : `${numeric.toFixed(0)} ms`;
}

function computeLatencyBreakdown(stats = {}) {
  const firstAudioMs = toFiniteNumber(stats.first_audio_latency_ms);
  const speechRecognitionMs = toFiniteNumber(stats.first_source_latency_ms);
  const firstTranslationMs = toFiniteNumber(stats.first_translation_latency_ms);
  const translationProcessingMs =
    speechRecognitionMs !== null && firstTranslationMs !== null
      ? Math.max(0, firstTranslationMs - speechRecognitionMs)
      : null;
  const ttsGenerationMs =
    firstTranslationMs !== null && firstAudioMs !== null
      ? Math.max(0, firstAudioMs - firstTranslationMs)
      : null;
  return {
    firstAudioMs,
    speechRecognitionMs,
    translationProcessingMs,
    ttsGenerationMs,
  };
}

function renderLatencyPanel() {
  const activeAliases = CHANNELS.filter(
    (alias) => appState.values[`${alias}-enabled`] === "1" && appState.values[`${alias}-input-enabled`] === "1",
  );
  const breakdowns = {};
  CHANNELS.forEach((alias) => {
    breakdowns[alias] = computeLatencyBreakdown(appState.runtime?.channels?.[alias]?.stats || {});
  });

  const summarySource = activeAliases.length ? activeAliases : CHANNELS;
  const pickMetric = (key) => {
    const values = summarySource
      .map((alias) => breakdowns[alias][key])
      .filter((value) => toFiniteNumber(value) !== null)
      .map((value) => Number(value));
    if (!values.length) {
      return null;
    }
    return Math.min(...values);
  };

  latencySummaryScope.textContent = activeAliases.length
    ? uiLanguage() === "zh"
      ? `${activeAliases.length} 条活跃通道`
      : `${activeAliases.length} active channels`
    : uiLanguage() === "zh"
      ? "等待会话"
      : "Standby";
  latencySummaryFirstAudio.textContent = formatLatencyValue(pickMetric("firstAudioMs"));
  latencySummaryRecognition.textContent = formatLatencyValue(pickMetric("speechRecognitionMs"));
  latencySummaryTranslation.textContent = formatLatencyValue(pickMetric("translationProcessingMs"));
  latencySummaryTts.textContent = formatLatencyValue(pickMetric("ttsGenerationMs"));

  CHANNELS.forEach((alias) => {
    const refs = latencyRefs[alias];
    const runtime = appState.runtime?.channels?.[alias] || {};
    const meta = channelLocaleCopy(alias);
    const values = breakdowns[alias];
    refs.title.textContent = meta.title;
    refs.status.textContent = displayStatus(runtime.label || "Idle");
    refs.firstAudio.textContent = formatLatencyValue(values.firstAudioMs);
    refs.recognition.textContent = formatLatencyValue(values.speechRecognitionMs);
    refs.translation.textContent = formatLatencyValue(values.translationProcessingMs);
    refs.tts.textContent = formatLatencyValue(values.ttsGenerationMs);
    refs.card.classList.toggle("has-error", runtime.signal === "error");
  });
}

function buildRouteNote(alias, runtime) {
  const enabled = appState.values[`${alias}-enabled`] === "1";
  const inputEnabled = appState.values[`${alias}-input-enabled`] === "1";
  const outputEnabled = appState.values[`${alias}-output-enabled`] === "1";
  const monitorEnabled = appState.values[`${alias}-monitor-enabled`] === "1";
  const astSpeaker = appState.values[`${alias}-speaker`] || "";
  const cloneEnabled = appState.values[`${alias}-clone-enabled`] === "1";
  const cloneSpeaker = appState.values[`${alias}-clone-speaker`] || "";
  const parts = [];

  if (!enabled) {
    return t("status.channelDisabled");
  }
  if (!inputEnabled) {
    parts.push(t("status.inputOff"));
  } else {
    parts.push(`${t("toggle.input")} ${getOptionLabel(`${alias}-input`)}`);
  }
  if (!outputEnabled) {
    parts.push(t("status.captionsOnly"));
  } else {
    parts.push(`${t("toggle.output")} ${getOptionLabel(`${alias}-output`)}`);
  }
  if (monitorEnabled) {
    parts.push(`${t("advanced.monitorPlayback")} ${getOptionLabel(`${alias}-monitor-output`)}`);
  }
  parts.push(`${getOptionLabel(`${alias}-source`)} -> ${getOptionLabel(`${alias}-target`)}`);
  if (astSpeaker) {
    parts.push(`Voice ${getOptionLabel(`${alias}-speaker`)}`);
  }
  if (cloneEnabled && cloneSpeaker) {
    parts.push(`Clone ${cloneSpeaker}`);
  }
  if (runtime?.status && normalizeStatusKey(runtime.status) !== normalizeStatusKey(runtime.label)) {
    parts.push(displayStatus(runtime.status));
  }
  return parts.join(" / ");
}

function formatLatency(stats) {
  const audio = stats?.first_audio_latency_ms;
  const translation = stats?.first_translation_latency_ms;
  if (typeof audio === "number") {
    return `${audio.toFixed(0)} ms audio`;
  }
  if (typeof translation === "number") {
    return `${translation.toFixed(0)} ms AST`;
  }
  return uiLanguage() === "zh" ? "等待音频" : "Awaiting audio";
}

function formatQueue(stats) {
  const depth = Number(stats?.input_queue_depth || 0);
  const dropped = Number(stats?.dropped_silent_chunks || 0);
  return uiLanguage() === "zh" ? `队列 ${depth.toString().padStart(2, "0")} / 丢弃 ${dropped}` : `Queue ${depth.toString().padStart(2, "0")} / Drop ${dropped}`;
}

function formatAudioLevel(stats) {
  const level = Number(stats?.audio_level_db ?? -96);
  return Number.isFinite(level) ? `${level.toFixed(0)} dB` : "--";
}

function formatRouteLatency(stats) {
  const audio = stats?.first_audio_latency_ms;
  const translation = stats?.first_translation_latency_ms;
  const parts = [];
  if (typeof translation === "number") {
    parts.push(`AST ${translation.toFixed(0)}ms`);
  }
  if (typeof audio === "number") {
    parts.push(`音频 ${audio.toFixed(0)}ms`);
  }
  return parts.join(" / ") || "--";
}

function renderRouteDetail(alias, runtime) {
  const refs = routeDetailRefs[alias];
  if (!refs) {
    return;
  }
  const stats = runtime?.stats || {};
  refs.status.textContent = displayStatus(runtime?.label || runtime?.status || "Ready");
  refs.input.textContent = getOptionLabel(`${alias}-input`) || "--";
  refs.output.textContent = getOptionLabel(`${alias}-output`) || "--";
  refs.latency.textContent = formatRouteLatency(stats);
  refs.queue.textContent = formatQueue(stats);
  const nativeBits = stats.native_vad_score != null ? ` / VAD ${Number(stats.native_vad_score).toFixed(2)}` : "";
  refs.level.textContent = `${formatAudioLevel(stats)}${nativeBits}`;
  refs.input.title = refs.input.textContent;
  refs.output.title = refs.output.textContent;
  refs.latency.title = refs.latency.textContent;
}

function renderChannel(alias) {
  const refs = channelRefs[alias];
  const runtime = appState.runtime?.channels?.[alias] || { signal: "idle", label: "Ready", pane: "Idle", status: "Ready", stats: {} };
  const meta = channelLocaleCopy(alias);
  refs.title.textContent = meta.title;
  refs.copy.textContent = meta.copy;
  refs.paneTitle.textContent = meta.paneTitle;
  refs.paneStatus.textContent = displayStatus(runtime.pane || runtime.label || "Idle");
  refs.statusPill.textContent = displayStatus(runtime.label || "Ready");
  refs.summary.textContent = channelSummaryLabel(alias, runtime);
  refs.routeNote.textContent = buildRouteNote(alias, runtime);
  refs.routeNote.title = refs.routeNote.textContent;
  refs.latencyChip.textContent = formatLatency(runtime.stats);
  refs.queueChip.textContent = formatQueue(runtime.stats);
  refs.routeInput.textContent = getOptionLabel(`${alias}-input`) || "—";
  refs.routeOutput.textContent = getOptionLabel(`${alias}-output`) || "—";
  refs.routeInput.title = getOptionHint(`${alias}-input`) || refs.routeInput.textContent;
  refs.routeOutput.title = getOptionHint(`${alias}-output`) || refs.routeOutput.textContent;
  refs.metricInput.textContent = appState.runtime?.metrics?.[`input${alias.toUpperCase()}`] || "--";
  renderRouteDetail(alias, runtime);

  setVisualizer(refs.visualizer, runtime);
  setRouteState(refs.routeInputNode, runtime.signal);
  setRouteState(refs.routeOutputNode, runtime.signal);
  setSummaryState(refs.summary, runtime.signal, refs.accent);
  refs.card.classList.toggle("has-error", runtime.signal === "error");
}

function renderRouteCard() {
  routeCopy.textContent = transientNotice || t("route.copy");
  summaryAst.textContent = appState.runtime?.metrics?.ast && appState.runtime.metrics.ast !== "--" ? `AST · ${appState.runtime.metrics.ast}` : t("status.astReady");
  summaryAst.classList.toggle("active", Boolean(appState.runtime?.running));
  routeCard.classList.toggle(
    "has-error",
    CHANNELS.some((alias) => appState.runtime?.channels?.[alias]?.signal === "error"),
  );
  document.getElementById("metricAst").textContent = appState.runtime?.metrics?.ast || "--";
  document.getElementById("metricTts").textContent = appState.runtime?.metrics?.tts || "--";
  const astRefs = routeDetailRefs.ast;
  if (astRefs) {
    astRefs.status.textContent = appState.runtime?.running ? (uiLanguage() === "zh" ? "运行中" : "Live") : t("status.astReady");
    astRefs.path.textContent = appState.runtime?.globalHint || "direct";
    astRefs.path.title = astRefs.path.textContent;
    astRefs.astLatency.textContent = appState.runtime?.metrics?.ast || "--";
    astRefs.ttsLatency.textContent = appState.runtime?.metrics?.tts || "--";
    const nativeCore = appState.nativeAudioCore || {};
    const backend = nativeCore.captureBackend || appState.values["audio-capture-backend"] || "python";
    const runtimeText = appState.runtime?.running ? (uiLanguage() === "zh" ? "已启动" : "Running") : (uiLanguage() === "zh" ? "待机" : "Standby");
    astRefs.running.textContent = `${runtimeText} / ${backend}`;
  }
}

function renderChannelCard(alias) {
  const refs = channelRefs[alias];
  const runtime = appState.runtime?.channels?.[alias] || { signal: "idle", label: "Ready", pane: "Idle", status: "Ready", stats: {} };
  const meta = channelLocaleCopy(alias);
  refs.title.textContent = meta.title;
  refs.copy.textContent = meta.copy;
  refs.paneTitle.textContent = meta.paneTitle;
  refs.paneStatus.textContent = displayStatus(runtime.pane || runtime.label || "Idle");
  refs.statusPill.textContent = displayStatus(runtime.label || "Ready");
  refs.summary.textContent = channelSummaryLabel(alias, runtime);
  refs.routeNote.textContent = buildRouteNote(alias, runtime);
  refs.routeNote.title = refs.routeNote.textContent;
  refs.latencyChip.textContent = formatLatency(runtime.stats);
  refs.queueChip.textContent = formatQueue(runtime.stats);
  refs.routeInput.textContent = getOptionLabel(`${alias}-input`) || "--";
  refs.routeOutput.textContent = getOptionLabel(`${alias}-output`) || "--";
  refs.routeInput.title = getOptionHint(`${alias}-input`) || refs.routeInput.textContent;
  refs.routeOutput.title = getOptionHint(`${alias}-output`) || refs.routeOutput.textContent;
  refs.metricInput.textContent = appState.runtime?.metrics?.[`input${alias.toUpperCase()}`] || "--";

  setVisualizer(refs.visualizer, runtime);
  setRouteState(refs.routeInputNode, runtime.signal);
  setRouteState(refs.routeOutputNode, runtime.signal);
  setSummaryState(refs.summary, runtime.signal, refs.accent);
  refs.card.classList.toggle("has-error", runtime.signal === "error");
}

function buildTranscriptEntry(alias, entry, mode) {
  const source = entry.source || "";
  const target = entry.target || "";
  const showSource = mode !== "target_only" && source;
  const showTarget = mode !== "source_only" && target;
  return `
    <article class="transcript-entry">
      <div class="entry-time">${entry.time || "--:--:--"}</div>
      ${showSource ? `<div class="entry-source">${escapeHtml(source)}</div>` : ""}
      ${showTarget ? `<div class="entry-target">${escapeHtml(target)}</div>` : ""}
    </article>
  `;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function isTranscriptNearBottom(node, topOverride = null) {
  if (!node) {
    return true;
  }
  const scrollTop = typeof topOverride === "number" ? topOverride : node.scrollTop;
  return node.scrollHeight - node.clientHeight - scrollTop <= 32;
}

function renderTranscriptPane(alias) {
  const refs = channelRefs[alias];
  const mode = appState.values[`${alias}-subtitle`] || "bilingual";
  const partial = appState.partials?.[alias] || {};
  const runtime = appState.runtime?.channels?.[alias] || {};
  const entries = appState.transcripts?.[alias] || [];
  const previousScrollTop = refs.transcript.scrollTop;
  const previousScrollState = transcriptScrollState.get(alias) || { stickToBottom: true, top: 0 };
  const shouldStick =
    previousScrollState.stickToBottom || isTranscriptNearBottom(refs.transcript, previousScrollTop);

  refs.liveSource.textContent = mode === "target_only" ? "" : partial.source || "";
  refs.liveTarget.textContent = mode === "source_only" ? "" : partial.target || "";
  refs.transcript.innerHTML = entries.map((entry) => buildTranscriptEntry(alias, entry, mode)).join("");
  refs.paneStatus.textContent = displayStatus(runtime.pane || runtime.label || "Idle");
  if (shouldStick) {
    refs.transcript.scrollTop = refs.transcript.scrollHeight;
  } else {
    refs.transcript.scrollTop = Math.max(0, previousScrollState.top ?? previousScrollTop);
  }
  transcriptScrollState.set(alias, {
    stickToBottom: shouldStick,
    top: refs.transcript.scrollTop,
  });
}

function renderChannelDrawer() {
  channelPanels.forEach((panel) => {
    panel.classList.toggle("is-hidden", panel.dataset.channelPanel !== activeChannelDrawer);
  });
  channelDrawerEyebrow.textContent = t(`channel.${activeChannelDrawer}Eyebrow`);
  channelDrawerTitle.textContent = t(`channel.drawerTitle${activeChannelDrawer.toUpperCase()}`);
  channelDrawerCopy.textContent = t("channel.drawerCopy");
  renderVoicePreviewState();
}

function renderDrawers() {
  const hasDrawer = Boolean(activeDrawer);
  modalBackdrop.hidden = !hasDrawer;
  drawer.classList.toggle("is-open", activeDrawer === "settings");
  biasDrawer.classList.toggle("is-open", activeDrawer === "bias");
  latencyDrawer.classList.toggle("is-open", activeDrawer === "latency");
  channelDrawer.classList.toggle("is-open", activeDrawer === "channel");
  drawer.setAttribute("aria-hidden", String(activeDrawer !== "settings"));
  biasDrawer.setAttribute("aria-hidden", String(activeDrawer !== "bias"));
  latencyDrawer.setAttribute("aria-hidden", String(activeDrawer !== "latency"));
  channelDrawer.setAttribute("aria-hidden", String(activeDrawer !== "channel"));
  renderChannelDrawer();
}

function renderRunningState() {
  const running = Boolean(appState.runtime?.running);
  if (running && !topControlsCollapsed) {
    autoSubtitleFocus = true;
    setTopControlsCollapsed(true);
  } else if (!running && autoSubtitleFocus && topControlsCollapsed) {
    autoSubtitleFocus = false;
    setTopControlsCollapsed(false);
  } else if (!running) {
    autoSubtitleFocus = false;
  }
  app.classList.toggle("is-running", running);
  startButton.disabled = running;
  stopButton.disabled = !running;
  refreshButton.disabled = running;
  saveConfigButton.disabled = running;
}

function renderAll() {
  renderTranslations();
  renderTopControlsVisibility();
  renderHeader();
  renderCredentials();
  renderFieldGroups();
  renderPlatformState();
  CHANNELS.forEach(renderChannelCard);
  renderRouteCard();
  renderLatencyPanel();
  CHANNELS.forEach(renderTranscriptPane);
  renderRunningState();
  renderSelects();
  renderDrawers();
}

function renderLiveState() {
  renderTopControlsVisibility();
  renderHeader();
  renderPlatformState();
  CHANNELS.forEach(renderChannelCard);
  renderRouteCard();
  renderLatencyPanel();
  CHANNELS.forEach(renderTranscriptPane);
  renderRunningState();
  renderVoicePreviewState();
}

function scheduleSave(delay = 280) {
  if (appState.runtime.running) {
    return;
  }
  clearTimeout(saveTimer);
  saveTimer = window.setTimeout(async () => {
    if (!backendMode) {
      setNotice(t("status.autosaved"));
      return;
    }
    const response = await callBackend("save_state", currentPayload());
    applyServerState(response);
    renderAll();
  }, delay);
}

function openDrawer(name) {
  activeDrawer = activeDrawer === name ? "" : name;
  closeAllSelects();
  renderDrawers();
}

function openChannelDrawer(alias) {
  activeChannelDrawer = alias;
  activeDrawer = "channel";
  closeAllSelects();
  renderDrawers();
}

function closeDrawers() {
  activeDrawer = "";
  renderDrawers();
}

function bindTextInput(element, key) {
  if (!element) {
    return;
  }
  element.addEventListener("input", () => {
    appState.values[key] = element.value;
    scheduleSave();
  });
}

function bindNumericInput(element, key) {
  if (!element) {
    return;
  }
  element.addEventListener("input", () => {
    appState.values[key] = element.value;
    scheduleSave();
  });
}

function bindCheckbox(element, key) {
  if (!element) {
    return;
  }
  element.addEventListener("change", () => {
    appState.values[key] = element.checked ? "1" : "0";
    scheduleSave();
    renderAll();
  });
}

function bindCredentialInput(element, key) {
  if (!element) {
    return;
  }
  element.addEventListener("input", () => {
    appState.credentials[key] = element.value.trim();
    scheduleSave();
  });
}

async function refreshDevices() {
  if (!backendMode) {
    setNotice(uiLanguage() === "zh" ? "预览模式下不会真实刷新设备。" : "Preview mode does not refresh real devices.");
    return;
  }
  const response = await callBackend("refresh_devices");
  applyServerState(response);
  renderAll();
  setNotice(uiLanguage() === "zh" ? "设备列表已刷新。" : "Device list refreshed.");
}

function pushDemoEntry(alias) {
  const samples = {
    a: [
      {
        source: "先别出门，门口还有两个人。",
        target: "Do not push out yet. There are still two people at the front door.",
      },
      {
        source: "我把火箭送去外圈箱子，你看一下车库门。",
        target: "I'm moving the rockets to the outer box. Watch the garage door.",
      },
    ],
    b: [
      {
        source: "We are holding the roof. Wait for the counter raid.",
        target: "我们现在守屋顶，先等一手反抄家。",
      },
      {
        source: "Move the scrap to Outpost and recycle the pipes.",
        target: "把废料搬去 Outpost，再把管子回收掉。",
      },
    ],
    c: [
      {
        source: "One on the recycler, one wide on the road.",
        target: "回收机一个，路上拉开身位还有一个。",
      },
      {
        source: "I hear SAR shots behind supermarket.",
        target: "我听到超市后面有 SAR 枪声。",
      },
    ],
  };
  const entry = samples[alias][Math.floor(Math.random() * samples[alias].length)];
  const time = new Date().toLocaleTimeString("en-GB", { hour12: false });
  appState.partials[alias] = { source: entry.source, target: entry.target };
  appState.transcripts[alias].push({ time, source: entry.source, target: entry.target });
  appState.transcripts[alias] = appState.transcripts[alias].slice(-30);
}

function startDemoStream() {
  if (demoTimer) {
    return;
  }
  appState.runtime.running = true;
  CHANNELS.forEach((alias) => {
    const enabled = appState.values[`${alias}-enabled`] === "1";
    const inputEnabled = appState.values[`${alias}-input-enabled`] === "1";
    if (!enabled) {
      appState.runtime.channels[alias] = { signal: "idle", label: "Disabled", pane: "Disabled", status: "Channel disabled", stats: {} };
      return;
    }
    if (!inputEnabled) {
      appState.runtime.channels[alias] = { signal: "idle", label: "Input Off", pane: "Standby", status: "Input capture disabled", stats: {} };
      return;
    }
    appState.runtime.channels[alias] = {
      signal: "ok",
      label: "Live",
      pane: appState.values[`${alias}-output-enabled`] === "1" ? "Streaming" : "Captions Only",
      status: "Streaming",
      stats: {
        audio_level_db: -34 + Math.round(Math.random() * 10),
        input_queue_depth: Math.round(Math.random() * 2),
        dropped_silent_chunks: Math.round(Math.random() * 6),
        first_audio_latency_ms: 80 + Math.round(Math.random() * 40),
        first_translation_latency_ms: 65 + Math.round(Math.random() * 30),
      },
    };
  });
  demoTimer = window.setInterval(() => {
    CHANNELS.forEach((alias) => {
      if (appState.values[`${alias}-enabled`] === "1" && appState.values[`${alias}-input-enabled`] === "1") {
        pushDemoEntry(alias);
        const stats = appState.runtime.channels[alias].stats || {};
        stats.audio_level_db = -28 - Math.round(Math.random() * 24);
        stats.input_queue_depth = Math.round(Math.random() * 3);
        stats.dropped_silent_chunks = Number(stats.dropped_silent_chunks || 0) + Math.round(Math.random());
        stats.first_audio_latency_ms = 72 + Math.round(Math.random() * 64);
        stats.first_translation_latency_ms = 58 + Math.round(Math.random() * 36);
        appState.runtime.channels[alias].stats = stats;
      }
    });
    appState.runtime.metrics.inputA = formatInputMetric(appState.runtime.channels.a.stats);
    appState.runtime.metrics.inputB = formatInputMetric(appState.runtime.channels.b.stats);
    appState.runtime.metrics.inputC = formatInputMetric(appState.runtime.channels.c.stats);
    appState.runtime.metrics.ast = `${62 + Math.round(Math.random() * 28)} ms`;
    appState.runtime.metrics.tts = `${86 + Math.round(Math.random() * 46)} ms`;
    appState.runtime.globalStatus = "Live";
    renderAll();
  }, 1500);
  renderAll();
}

function stopDemoStream() {
  clearInterval(demoTimer);
  demoTimer = null;
  appState.runtime.running = false;
  CHANNELS.forEach((alias) => {
    const enabled = appState.values[`${alias}-enabled`] === "1";
    appState.runtime.channels[alias] = {
      signal: "idle",
      label: enabled ? "Ready" : "Disabled",
      pane: enabled ? "Idle" : "Disabled",
      status: enabled ? "Ready" : "Channel disabled",
      stats: appState.runtime.channels[alias]?.stats || {},
    };
  });
  renderAll();
}

function formatInputMetric(stats) {
  if (!stats) {
    return "--";
  }
  const queueDepth = Number(stats.input_queue_depth || 0);
  const level = Number(stats.audio_level_db ?? 0);
  const dropped = Number(stats.dropped_silent_chunks || 0);
  return `${level.toFixed(0)} dB / Q${String(queueDepth).padStart(2, "0")} / Drop ${dropped}`;
}

async function startEngine() {
  stopVoicePreview();
  if (backendMode) {
    const response = await callBackend("start_channels", currentPayload());
    applyServerState(response);
    renderAll();
    if (response && response.ok === false) {
      setNotice(response.error || t("alert.startFailed"));
    }
    return;
  }
  startDemoStream();
}

async function stopEngine() {
  if (backendMode) {
    const response = await callBackend("stop_channels");
    applyServerState(response);
    renderAll();
    return;
  }
  stopVoicePreview();
  stopDemoStream();
}

async function exportSession() {
  if (!backendMode) {
    setNotice(t("alert.exportDesktop"));
    return;
  }
  const response = await callBackend("export_session");
  applyServerState(response);
  renderAll();
  if (response?.ok && response?.name) {
    setNotice(uiLanguage() === "zh" ? `已导出 ${response.name}` : `Exported ${response.name}`);
  }
}

async function checkUpdates() {
  const response = await callBackend("check_updates", currentPayload());
  applyServerState(response);
  renderAll();
}

async function downloadUpdate() {
  const response = await callBackend("download_update", currentPayload());
  applyServerState(response);
  renderAll();
}

async function browseVoiceCloneSample() {
  if (!backendMode) {
    setNotice(uiLanguage() === "zh" ? "预览模式下无法选择本地样本。" : "Preview mode cannot choose a local sample.");
    return;
  }
  const path = await callBackend("pick_voice_clone_sample");
  if (typeof path === "string" && path) {
    voiceCloneSamplePathInput.value = path;
    appState.values["voice-clone-sample-path"] = path;
    scheduleSave();
  }
}

async function toggleVoiceCloneRecording() {
  if (!backendMode) {
    setNotice(uiLanguage() === "zh" ? "桌面版里才能直接从麦克风录制样本。" : "Recording from the microphone is only available in the desktop build.");
    return;
  }
  const response = appState.voiceClone?.recording
    ? await callBackend("stop_voice_clone_recording")
    : await callBackend("start_voice_clone_recording", currentPayload());
  applyServerState(response);
  renderAll();
  if (response?.error) {
    setNotice(response.error);
  }
}

async function trainVoiceClone() {
  if (!appState.values["voice-clone-sample-path"]) {
    setNotice(t("alert.cloneSampleMissing"));
    return;
  }
  if (!backendMode) {
    setNotice(uiLanguage() === "zh" ? "预览模式不会真的提交训练。" : "Preview mode does not submit real training.");
    return;
  }
  const response = await callBackend("train_voice_clone", currentPayload());
  applyServerState(response);
  renderAll();
  if (response?.error) {
    setNotice(response.error);
  }
}

async function refreshVoiceCloneStatus() {
  if (!backendMode) {
    renderAll();
    return;
  }
  const response = await callBackend("refresh_voice_clone_status", currentPayload());
  applyServerState(response);
  renderAll();
  if (response?.error) {
    setNotice(response.error);
  }
}

function stopVoicePreview() {
  if (!previewAudio) {
    return;
  }
  previewAudio.pause();
  previewAudio.src = "";
  previewAudio = null;
}

function renderVoicePreviewState() {
  CHANNELS.forEach((alias) => {
    const refs = voicePreviewRefs[alias];
    if (!refs?.button || !refs?.note) {
      return;
    }
    const running = Boolean(appState.runtime?.running);
    const selected = appState.values[`${alias}-speaker`] || "";
    const label = getOptionLabel(`${alias}-speaker`);
    const hint = getOptionHint(`${alias}-speaker`);
    refs.button.disabled = running || Boolean(previewInFlight);
    refs.button.textContent =
      previewInFlight === alias
        ? uiLanguage() === "zh"
          ? "生成中..."
          : "Rendering..."
        : t("button.previewVoice");
    refs.note.textContent = selected
      ? [label, hint].filter(Boolean).join(" / ")
      : uiLanguage() === "zh"
        ? "未选择内置音色，运行时会使用 AST 默认音色。"
        : "No preset selected. Runtime will use the AST default voice.";
  });
}

async function waitForPreviewResult(jobId) {
  const startedAt = Date.now();
  while (true) {
    const response = await callBackend("poll_preview_channel_voice", { jobId });
    applyServerState(response);
    if (!response?.pending) {
      return response;
    }
    if (Date.now() - startedAt > 120000) {
      throw new Error(uiLanguage() === "zh" ? "试听生成超时，请稍后重试。" : "Voice preview timed out. Please try again.");
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, 260);
    });
  }
}

async function previewChannelVoice(alias) {
  const selected = String(appState.values[`${alias}-speaker`] || "").trim();
  if (!selected) {
    setNotice(uiLanguage() === "zh" ? "先选一个内置音色再试听。" : "Choose a built-in voice first.");
    return;
  }
  if (!backendMode) {
    setNotice(uiLanguage() === "zh" ? "试听需要桌面版后端。" : "Voice preview requires the desktop backend.");
    return;
  }

  previewInFlight = alias;
  previewJobId = "";
  renderVoicePreviewState();
  try {
    setNotice(uiLanguage() === "zh" ? "正在生成试听，请稍等…" : "Rendering voice preview...", 1800);
    const startResponse = await callBackend("preview_channel_voice", { ...currentPayload(), alias });
    applyServerState(startResponse);
    let response = startResponse;
    if (!startResponse?.ok && !startResponse?.pending) {
      setNotice(response?.error || (uiLanguage() === "zh" ? "试听失败。" : "Voice preview failed."));
      return;
    }

    previewJobId = String(startResponse?.jobId || "").trim();
    if (!previewJobId) {
      setNotice(uiLanguage() === "zh" ? "试听任务没有返回标识。" : "Voice preview task did not return an id.");
      return;
    }
    response = await waitForPreviewResult(previewJobId);
    if (!response?.ok || !response?.preview?.audioBase64) {
      setNotice(response?.error || (uiLanguage() === "zh" ? "试听失败。" : "Voice preview failed."));
      return;
    }

    stopVoicePreview();
    const audio = new Audio(`data:audio/wav;base64,${response.preview.audioBase64}`);
    previewAudio = audio;
    audio.addEventListener("ended", () => {
      if (previewAudio === audio) {
        previewAudio = null;
      }
    });
    await audio.play();
    setNotice(
      uiLanguage() === "zh"
        ? `正在试听 ${response.preview.label || getOptionLabel(`${alias}-speaker`)}`
        : `Previewing ${response.preview.label || getOptionLabel(`${alias}-speaker`)}`,
      2800,
    );
  } catch (error) {
    setNotice(String(error || (uiLanguage() === "zh" ? "试听失败。" : "Voice preview failed.")));
  } finally {
    previewInFlight = "";
    previewJobId = "";
    renderVoicePreviewState();
  }
}

async function pollBackendState() {
  if (!backendMode || pollInFlight) {
    return;
  }
  pollInFlight = true;
  try {
    const response = await callBackend("poll_state");
    applyServerState(response);
    renderLiveState();
  } finally {
    pollInFlight = false;
  }
}

function bindEvents() {
  layoutToggleButton?.addEventListener("click", toggleTopControlsCollapsed);
  settingsButton.addEventListener("click", () => openDrawer("settings"));
  biasButton.addEventListener("click", () => openDrawer("bias"));
  latencyButton.addEventListener("click", () => openDrawer("latency"));
  closeDrawerButton.addEventListener("click", closeDrawers);
  closeBiasDrawerButton.addEventListener("click", closeDrawers);
  closeLatencyDrawerButton.addEventListener("click", closeDrawers);
  closeChannelDrawerButton.addEventListener("click", closeDrawers);
  modalBackdrop.addEventListener("click", closeDrawers);

  refreshButton.addEventListener("click", refreshDevices);
  startButton.addEventListener("click", startEngine);
  stopButton.addEventListener("click", stopEngine);
  saveConfigButton.addEventListener("click", async () => {
    if (!backendMode) {
      setNotice(t("status.autosaved"));
      return;
    }
    const response = await callBackend("save_state", currentPayload());
    applyServerState(response);
    renderAll();
    setNotice(t("status.autosaved"));
  });
  exportSessionButton.addEventListener("click", exportSession);
  languageToggleButton.addEventListener("click", () => {
    appState.values["ui-language"] = uiLanguage() === "zh" ? "en" : "zh";
    renderAll();
    scheduleSave();
  });
  checkUpdateButton.addEventListener("click", checkUpdates);
  downloadUpdateButton.addEventListener("click", downloadUpdate);
  voiceCloneBrowseButton.addEventListener("click", browseVoiceCloneSample);
  voiceCloneRecordButton.addEventListener("click", toggleVoiceCloneRecording);
  trainVoiceCloneButton.addEventListener("click", trainVoiceClone);
  refreshVoiceCloneButton.addEventListener("click", refreshVoiceCloneStatus);
  CHANNELS.forEach((alias) => {
    voicePreviewRefs[alias]?.button?.addEventListener("click", () => previewChannelVoice(alias));
  });

  CHANNELS.forEach((alias) => {
    channelRefs[alias].toolsButton.addEventListener("click", () => openChannelDrawer(alias));
  });

  bindCredentialInput(credentialAppId, "appId");
  bindCredentialInput(credentialAccessToken, "accessToken");
  bindCredentialInput(credentialSecretKey, "secretKey");
  bindCredentialInput(credentialResourceId, "resourceId");

  Object.entries(advancedFieldInputs).forEach(([key, element]) => bindTextInput(element, key));
  Object.entries(numericFieldInputs).forEach(([key, element]) => bindNumericInput(element, key));
  Object.entries(checkboxInputs).forEach(([key, element]) => bindCheckbox(element, key));

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".custom-select")) {
      closeAllSelects();
    }
  });

  document.querySelector(".app-main")?.addEventListener(
    "scroll",
    () => {
      if (openSelectKey) {
        syncOpenSelectMenu();
      }
    },
    { passive: true },
  );
  window.addEventListener("resize", () => {
    if (openSelectKey) {
      syncOpenSelectMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAllSelects();
      closeDrawers();
    }
  });
}

async function initialize() {
  bindEvents();
  topControlsCollapsed = readTopControlsPreference();
  await connectBackend();
  if (backendMode) {
    const state = await callBackend("get_state");
    applyServerState(state);
    pollTimer = window.setInterval(pollBackendState, 900);
  }
  renderAll();
}

initialize();
