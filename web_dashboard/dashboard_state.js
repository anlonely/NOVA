window.__NOVA_STATE__ = {
  "values": {
    "scene": "discord_bidirectional",
    "ui-language": "zh",
    "domain-preset": "rust",
    "domain-context": "This is a real-time voice conversation about the survival game Rust. Common terms include Tool Cupboard or TC, raid, counter raid, sulfur, scrap, recycler, Bradley, Chinook, Oil Rig, Cargo, Launch Site, Outpost, Bandit Camp, Workbench, garage door, armored door, sheet metal, AK-47, MP5, C4, satchel, rocket.",
    "domain-hot-words": "Rust, TC, Tool Cupboard, raid, counter raid, Bradley, Chinook, Oil Rig, Launch Site, Cargo, Outpost, Bandit Camp, Workbench, garage door, armored door, sheet metal, AK-47, MP5, C4, satchel, rocket, sulfur, scrap, recycler",
    "domain-correct-words": "tc => TC\nt c => TC\ntool cupboard => Tool Cupboard\nlaunchsite => Launch Site\noilrig => Oil Rig\ncargo ship => Cargo\nak47 => AK-47\nak 47 => AK-47\nmp 5 => MP5\nc 4 => C4\nsatchel charge => Satchel\nwork bench => Workbench\nsheetmetal => Sheet Metal\ncounterrate => Counter Raid",
    "domain-glossary": "领地柜 => Tool Cupboard (TC)\n抄家 => Raid\n反抄 => Counter Raid\n废料 => Scrap\n硫磺 => Sulfur\n回收机 => Recycler\n油井 => Oil Rig\n发射基地 => Launch Site\n货船 => Cargo\n工作台 => Workbench\n车库门 => Garage Door\n装甲门 => Armored Door\n铁皮 => Sheet Metal",
    "update-manifest-url": "",
    "voice-clone-speaker-id": "S_ATMtmRu02",
    "voice-clone-sample-path": ".downloads/ast_python/ast_python/test_audio.wav",
    "voice-clone-reference-text": "",
    "voice-clone-demo-text": "NOVA Interp clone training smoke test.",
    "voice-clone-language": "zh",
    "a-enabled": "1",
    "a-input-enabled": "1",
    "a-output-enabled": "1",
    "a-input": "{0.0.1.00000000}.{18ab67cf-f79b-466d-8e0f-da833afc0026}",
    "a-output": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
    "a-source": "zh",
    "a-target": "en",
    "a-profile": "turbo",
    "a-subtitle": "target_only",
    "a-startup-buffer": "16",
    "a-noise-gate": "-46",
    "a-hold-ms": "140",
    "a-skip-silence": "1",
    "a-enable-agc": "1",
    "a-agc-target": "-18.0",
    "a-agc-max-gain": "6.0",
    "a-enable-denoise": "1",
    "a-denoise-strength": "0.22",
    "a-clone-enabled": "1",
    "a-clone-speaker": "S_ATMtmRu02",
    "a-clone-speed": "1.0",
    "b-enabled": "1",
    "b-input-enabled": "1",
    "b-output-enabled": "1",
    "b-input": "{0.0.0.00000000}.{6d6f8827-c3f1-45ad-8289-6453111e8f54}",
    "b-output": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
    "b-source": "en",
    "b-target": "zh",
    "b-profile": "turbo",
    "b-subtitle": "bilingual",
    "b-startup-buffer": "16",
    "b-noise-gate": "-46",
    "b-hold-ms": "140",
    "b-skip-silence": "1",
    "b-enable-agc": "1",
    "b-agc-target": "-18.0",
    "b-agc-max-gain": "6.0",
    "b-enable-denoise": "1",
    "b-denoise-strength": "0.22",
    "b-clone-enabled": "0",
    "b-clone-speaker": "S_ATMtmRu02",
    "b-clone-speed": "1.0",
    "c-enabled": "0",
    "c-input-enabled": "1",
    "c-output-enabled": "1",
    "c-input": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
    "c-output": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
    "c-source": "en",
    "c-target": "zh",
    "c-profile": "turbo",
    "c-subtitle": "bilingual",
    "c-startup-buffer": "16",
    "c-noise-gate": "-46",
    "c-hold-ms": "140",
    "c-skip-silence": "1",
    "c-enable-agc": "1",
    "c-agc-target": "-18",
    "c-agc-max-gain": "6",
    "c-enable-denoise": "1",
    "c-denoise-strength": "0.24",
    "c-clone-enabled": "0",
    "c-clone-speaker": "S_ATMtmRu02",
    "c-clone-speed": "1.0"
  },
  "credentials": {
    "appId": "**********",
    "accessToken": "************************",
    "secretKey": "************************",
    "resourceId": "volc.service_type.10053"
  },
  "version": {
    "version": "0.4.0",
    "channel": "alpha",
    "manifest_url": "",
    "notes": "Qt/Web dashboard with bilingual UI toggle, AGC/denoise tuning, voice clone workflow, updater hooks, and native audio core scaffold."
  },
  "optionGroups": {
    "ui-language": [
      {
        "value": "zh",
        "label": "简体中文",
        "hint": "Chinese interface"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "English interface"
      }
    ],
    "scene": [
      {
        "value": "discord_bidirectional",
        "label": "Discord Bidirectional",
        "hint": "Chinese -> English and English -> Chinese for real-time Discord conversation."
      },
      {
        "value": "caption_priority",
        "label": "Caption Priority",
        "hint": "Subtitle-first mode with lower startup buffer and aggressive silence trimming."
      },
      {
        "value": "studio_demo",
        "label": "Studio Demo",
        "hint": "Higher playback fidelity and more conservative buffering for demos and capture."
      }
    ],
    "domain-preset": [
      {
        "value": "generic",
        "label": "Generic Voice",
        "hint": "Balanced general-purpose speech recognition and translation."
      },
      {
        "value": "rust",
        "label": "Rust Raid",
        "hint": "Biases recognition and translation toward Rust raid, farming, and roaming comms."
      },
      {
        "value": "tactical_fps",
        "label": "Tactical FPS",
        "hint": "Biases recognition for tactical callouts, map names, and weapon terms."
      }
    ],
    "a-input": [
      {
        "value": "{0.0.1.00000000}.{7550d819-41d1-4e37-a76c-3ada12cc7548}",
        "label": "麦克风 (Steam Streaming Microphone) / Virtual",
        "hint": "Mic capture / Virtual / 1ch"
      },
      {
        "value": "{0.0.1.00000000}.{18ab67cf-f79b-466d-8e0f-da833afc0026}",
        "label": "Microphone (Logitech BRIO)",
        "hint": "Mic capture / 2ch"
      },
      {
        "value": "{0.0.1.00000000}.{2e8e70b1-e541-4313-a2ba-b658d53f18b2}",
        "label": "麦克风 (HyperX Cloud III)",
        "hint": "Mic capture / 1ch"
      },
      {
        "value": "{0.0.0.00000000}.{4052e65c-e02e-4177-a776-77592e252e44}",
        "label": "扬声器 (Steam Streaming Microphone) / Loopback / Virtual",
        "hint": "Mic capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8fa1199e-6917-413b-991f-1c45320800ca}",
        "label": "扬声器 (Steam Streaming Speakers) / Loopback / Virtual",
        "hint": "Mic capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8bd736e6-6706-4bc2-a213-7907f7370c39}",
        "label": "扬声器 (ToDesk Virtual Audio) / Loopback",
        "hint": "Mic capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{4993f409-e780-4794-b971-38214484e3e9}",
        "label": "27G1 (NVIDIA High Definition Audio) / Loopback",
        "hint": "Mic capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
        "label": "扬声器 (Realtek(R) Audio) / Loopback",
        "hint": "Mic capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{6d6f8827-c3f1-45ad-8289-6453111e8f54}",
        "label": "耳机 (HyperX Cloud III) / Loopback",
        "hint": "Mic capture / Loopback / 2ch"
      }
    ],
    "a-output": [
      {
        "value": "{0.0.0.00000000}.{4052e65c-e02e-4177-a776-77592e252e44}",
        "label": "扬声器 (Steam Streaming Microphone) / Virtual",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8fa1199e-6917-413b-991f-1c45320800ca}",
        "label": "扬声器 (Steam Streaming Speakers) / Virtual",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8bd736e6-6706-4bc2-a213-7907f7370c39}",
        "label": "扬声器 (ToDesk Virtual Audio)",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{4993f409-e780-4794-b971-38214484e3e9}",
        "label": "27G1 (NVIDIA High Definition Audio)",
        "hint": "Playback output / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
        "label": "扬声器 (Realtek(R) Audio)",
        "hint": "Playback output / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{6d6f8827-c3f1-45ad-8289-6453111e8f54}",
        "label": "耳机 (HyperX Cloud III)",
        "hint": "Playback output / 2ch"
      }
    ],
    "b-input": [
      {
        "value": "{0.0.0.00000000}.{4052e65c-e02e-4177-a776-77592e252e44}",
        "label": "扬声器 (Steam Streaming Microphone) / Loopback / Virtual",
        "hint": "Loopback capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8fa1199e-6917-413b-991f-1c45320800ca}",
        "label": "扬声器 (Steam Streaming Speakers) / Loopback / Virtual",
        "hint": "Loopback capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8bd736e6-6706-4bc2-a213-7907f7370c39}",
        "label": "扬声器 (ToDesk Virtual Audio) / Loopback",
        "hint": "Loopback capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{4993f409-e780-4794-b971-38214484e3e9}",
        "label": "27G1 (NVIDIA High Definition Audio) / Loopback",
        "hint": "Loopback capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
        "label": "扬声器 (Realtek(R) Audio) / Loopback",
        "hint": "Loopback capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{6d6f8827-c3f1-45ad-8289-6453111e8f54}",
        "label": "耳机 (HyperX Cloud III) / Loopback",
        "hint": "Loopback capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.1.00000000}.{7550d819-41d1-4e37-a76c-3ada12cc7548}",
        "label": "麦克风 (Steam Streaming Microphone) / Virtual",
        "hint": "Loopback capture / Virtual / 1ch"
      },
      {
        "value": "{0.0.1.00000000}.{18ab67cf-f79b-466d-8e0f-da833afc0026}",
        "label": "Microphone (Logitech BRIO)",
        "hint": "Loopback capture / 2ch"
      },
      {
        "value": "{0.0.1.00000000}.{2e8e70b1-e541-4313-a2ba-b658d53f18b2}",
        "label": "麦克风 (HyperX Cloud III)",
        "hint": "Loopback capture / 1ch"
      }
    ],
    "b-output": [
      {
        "value": "{0.0.0.00000000}.{4052e65c-e02e-4177-a776-77592e252e44}",
        "label": "扬声器 (Steam Streaming Microphone) / Virtual",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8fa1199e-6917-413b-991f-1c45320800ca}",
        "label": "扬声器 (Steam Streaming Speakers) / Virtual",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8bd736e6-6706-4bc2-a213-7907f7370c39}",
        "label": "扬声器 (ToDesk Virtual Audio)",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{4993f409-e780-4794-b971-38214484e3e9}",
        "label": "27G1 (NVIDIA High Definition Audio)",
        "hint": "Playback output / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
        "label": "扬声器 (Realtek(R) Audio)",
        "hint": "Playback output / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{6d6f8827-c3f1-45ad-8289-6453111e8f54}",
        "label": "耳机 (HyperX Cloud III)",
        "hint": "Playback output / 2ch"
      }
    ],
    "c-input": [
      {
        "value": "{0.0.0.00000000}.{4052e65c-e02e-4177-a776-77592e252e44}",
        "label": "扬声器 (Steam Streaming Microphone) / Loopback / Virtual",
        "hint": "Loopback capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8fa1199e-6917-413b-991f-1c45320800ca}",
        "label": "扬声器 (Steam Streaming Speakers) / Loopback / Virtual",
        "hint": "Loopback capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8bd736e6-6706-4bc2-a213-7907f7370c39}",
        "label": "扬声器 (ToDesk Virtual Audio) / Loopback",
        "hint": "Loopback capture / Virtual / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{4993f409-e780-4794-b971-38214484e3e9}",
        "label": "27G1 (NVIDIA High Definition Audio) / Loopback",
        "hint": "Loopback capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
        "label": "扬声器 (Realtek(R) Audio) / Loopback",
        "hint": "Loopback capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{6d6f8827-c3f1-45ad-8289-6453111e8f54}",
        "label": "耳机 (HyperX Cloud III) / Loopback",
        "hint": "Loopback capture / Loopback / 2ch"
      },
      {
        "value": "{0.0.1.00000000}.{7550d819-41d1-4e37-a76c-3ada12cc7548}",
        "label": "麦克风 (Steam Streaming Microphone) / Virtual",
        "hint": "Loopback capture / Virtual / 1ch"
      },
      {
        "value": "{0.0.1.00000000}.{18ab67cf-f79b-466d-8e0f-da833afc0026}",
        "label": "Microphone (Logitech BRIO)",
        "hint": "Loopback capture / 2ch"
      },
      {
        "value": "{0.0.1.00000000}.{2e8e70b1-e541-4313-a2ba-b658d53f18b2}",
        "label": "麦克风 (HyperX Cloud III)",
        "hint": "Loopback capture / 1ch"
      }
    ],
    "c-output": [
      {
        "value": "{0.0.0.00000000}.{4052e65c-e02e-4177-a776-77592e252e44}",
        "label": "扬声器 (Steam Streaming Microphone) / Virtual",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8fa1199e-6917-413b-991f-1c45320800ca}",
        "label": "扬声器 (Steam Streaming Speakers) / Virtual",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{8bd736e6-6706-4bc2-a213-7907f7370c39}",
        "label": "扬声器 (ToDesk Virtual Audio)",
        "hint": "Playback output / Virtual / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{4993f409-e780-4794-b971-38214484e3e9}",
        "label": "27G1 (NVIDIA High Definition Audio)",
        "hint": "Playback output / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{83365fe4-d46d-4786-a36d-66acb3ee5186}",
        "label": "扬声器 (Realtek(R) Audio)",
        "hint": "Playback output / 2ch"
      },
      {
        "value": "{0.0.0.00000000}.{6d6f8827-c3f1-45ad-8289-6453111e8f54}",
        "label": "耳机 (HyperX Cloud III)",
        "hint": "Playback output / 2ch"
      }
    ],
    "a-source": [
      {
        "value": "zh",
        "label": "Chinese",
        "hint": "zh"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "en"
      },
      {
        "value": "ja",
        "label": "Japanese",
        "hint": "ja"
      },
      {
        "value": "id",
        "label": "Indonesian",
        "hint": "id"
      },
      {
        "value": "es",
        "label": "Spanish",
        "hint": "es"
      },
      {
        "value": "pt",
        "label": "Portuguese",
        "hint": "pt"
      },
      {
        "value": "de",
        "label": "German",
        "hint": "de"
      },
      {
        "value": "fr",
        "label": "French",
        "hint": "fr"
      },
      {
        "value": "zhen",
        "label": "Chinese + English",
        "hint": "zhen"
      }
    ],
    "a-target": [
      {
        "value": "zh",
        "label": "Chinese",
        "hint": "zh"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "en"
      },
      {
        "value": "ja",
        "label": "Japanese",
        "hint": "ja"
      },
      {
        "value": "id",
        "label": "Indonesian",
        "hint": "id"
      },
      {
        "value": "es",
        "label": "Spanish",
        "hint": "es"
      },
      {
        "value": "pt",
        "label": "Portuguese",
        "hint": "pt"
      },
      {
        "value": "de",
        "label": "German",
        "hint": "de"
      },
      {
        "value": "fr",
        "label": "French",
        "hint": "fr"
      },
      {
        "value": "zhen",
        "label": "Chinese + English",
        "hint": "zhen"
      }
    ],
    "b-source": [
      {
        "value": "zh",
        "label": "Chinese",
        "hint": "zh"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "en"
      },
      {
        "value": "ja",
        "label": "Japanese",
        "hint": "ja"
      },
      {
        "value": "id",
        "label": "Indonesian",
        "hint": "id"
      },
      {
        "value": "es",
        "label": "Spanish",
        "hint": "es"
      },
      {
        "value": "pt",
        "label": "Portuguese",
        "hint": "pt"
      },
      {
        "value": "de",
        "label": "German",
        "hint": "de"
      },
      {
        "value": "fr",
        "label": "French",
        "hint": "fr"
      },
      {
        "value": "zhen",
        "label": "Chinese + English",
        "hint": "zhen"
      }
    ],
    "b-target": [
      {
        "value": "zh",
        "label": "Chinese",
        "hint": "zh"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "en"
      },
      {
        "value": "ja",
        "label": "Japanese",
        "hint": "ja"
      },
      {
        "value": "id",
        "label": "Indonesian",
        "hint": "id"
      },
      {
        "value": "es",
        "label": "Spanish",
        "hint": "es"
      },
      {
        "value": "pt",
        "label": "Portuguese",
        "hint": "pt"
      },
      {
        "value": "de",
        "label": "German",
        "hint": "de"
      },
      {
        "value": "fr",
        "label": "French",
        "hint": "fr"
      },
      {
        "value": "zhen",
        "label": "Chinese + English",
        "hint": "zhen"
      }
    ],
    "c-source": [
      {
        "value": "zh",
        "label": "Chinese",
        "hint": "zh"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "en"
      },
      {
        "value": "ja",
        "label": "Japanese",
        "hint": "ja"
      },
      {
        "value": "id",
        "label": "Indonesian",
        "hint": "id"
      },
      {
        "value": "es",
        "label": "Spanish",
        "hint": "es"
      },
      {
        "value": "pt",
        "label": "Portuguese",
        "hint": "pt"
      },
      {
        "value": "de",
        "label": "German",
        "hint": "de"
      },
      {
        "value": "fr",
        "label": "French",
        "hint": "fr"
      },
      {
        "value": "zhen",
        "label": "Chinese + English",
        "hint": "zhen"
      }
    ],
    "c-target": [
      {
        "value": "zh",
        "label": "Chinese",
        "hint": "zh"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "en"
      },
      {
        "value": "ja",
        "label": "Japanese",
        "hint": "ja"
      },
      {
        "value": "id",
        "label": "Indonesian",
        "hint": "id"
      },
      {
        "value": "es",
        "label": "Spanish",
        "hint": "es"
      },
      {
        "value": "pt",
        "label": "Portuguese",
        "hint": "pt"
      },
      {
        "value": "de",
        "label": "German",
        "hint": "de"
      },
      {
        "value": "fr",
        "label": "French",
        "hint": "fr"
      },
      {
        "value": "zhen",
        "label": "Chinese + English",
        "hint": "zhen"
      }
    ],
    "a-profile": [
      {
        "value": "turbo",
        "label": "Turbo",
        "hint": "40ms chunk / 45ms jitter / 16kHz"
      },
      {
        "value": "balanced",
        "label": "Balanced",
        "hint": "60ms chunk / 75ms jitter / 16kHz"
      },
      {
        "value": "studio",
        "label": "Studio",
        "hint": "90ms chunk / 140ms jitter / 24kHz"
      }
    ],
    "b-profile": [
      {
        "value": "turbo",
        "label": "Turbo",
        "hint": "40ms chunk / 45ms jitter / 16kHz"
      },
      {
        "value": "balanced",
        "label": "Balanced",
        "hint": "60ms chunk / 75ms jitter / 16kHz"
      },
      {
        "value": "studio",
        "label": "Studio",
        "hint": "90ms chunk / 140ms jitter / 24kHz"
      }
    ],
    "c-profile": [
      {
        "value": "turbo",
        "label": "Turbo",
        "hint": "40ms chunk / 45ms jitter / 16kHz"
      },
      {
        "value": "balanced",
        "label": "Balanced",
        "hint": "60ms chunk / 75ms jitter / 16kHz"
      },
      {
        "value": "studio",
        "label": "Studio",
        "hint": "90ms chunk / 140ms jitter / 24kHz"
      }
    ],
    "a-subtitle": [
      {
        "value": "bilingual",
        "label": "Bilingual",
        "hint": "bilingual"
      },
      {
        "value": "source_only",
        "label": "Source Only",
        "hint": "source_only"
      },
      {
        "value": "target_only",
        "label": "Target Only",
        "hint": "target_only"
      }
    ],
    "b-subtitle": [
      {
        "value": "bilingual",
        "label": "Bilingual",
        "hint": "bilingual"
      },
      {
        "value": "source_only",
        "label": "Source Only",
        "hint": "source_only"
      },
      {
        "value": "target_only",
        "label": "Target Only",
        "hint": "target_only"
      }
    ],
    "c-subtitle": [
      {
        "value": "bilingual",
        "label": "Bilingual",
        "hint": "bilingual"
      },
      {
        "value": "source_only",
        "label": "Source Only",
        "hint": "source_only"
      },
      {
        "value": "target_only",
        "label": "Target Only",
        "hint": "target_only"
      }
    ],
    "voice-clone-speaker-id": [
      {
        "value": "",
        "label": "Not Selected",
        "hint": "Use AST voice output"
      },
      {
        "value": "S_ATMtmRu02",
        "label": "Primary Clone",
        "hint": "S_ATMtmRu02 / Ready"
      },
      {
        "value": "S_zTMtmRu02",
        "label": "Clone Slot 02",
        "hint": "S_zTMtmRu02 / Console slot"
      },
      {
        "value": "S_yTMtmRu02",
        "label": "Clone Slot 03",
        "hint": "S_yTMtmRu02 / Console slot"
      },
      {
        "value": "S_xTMtmRu02",
        "label": "Clone Slot 04",
        "hint": "S_xTMtmRu02 / Console slot"
      },
      {
        "value": "S_wTMtmRu02",
        "label": "Clone Slot 05",
        "hint": "S_wTMtmRu02 / Console slot"
      },
      {
        "value": "S_vTMtmRu02",
        "label": "Clone Slot 06",
        "hint": "S_vTMtmRu02 / Console slot"
      },
      {
        "value": "S_uTMtmRu02",
        "label": "Clone Slot 07",
        "hint": "S_uTMtmRu02 / Console slot"
      },
      {
        "value": "S_tTMtmRu02",
        "label": "Clone Slot 08",
        "hint": "S_tTMtmRu02 / Console slot"
      },
      {
        "value": "S_sTMtmRu02",
        "label": "Clone Slot 09",
        "hint": "S_sTMtmRu02 / Console slot"
      },
      {
        "value": "S_rTMtmRu02",
        "label": "Clone Slot 10",
        "hint": "S_rTMtmRu02 / Console slot"
      }
    ],
    "a-clone-speaker": [
      {
        "value": "",
        "label": "Not Selected",
        "hint": "Use AST voice output"
      },
      {
        "value": "S_ATMtmRu02",
        "label": "Primary Clone",
        "hint": "S_ATMtmRu02 / Ready"
      },
      {
        "value": "S_zTMtmRu02",
        "label": "Clone Slot 02",
        "hint": "S_zTMtmRu02 / Console slot"
      },
      {
        "value": "S_yTMtmRu02",
        "label": "Clone Slot 03",
        "hint": "S_yTMtmRu02 / Console slot"
      },
      {
        "value": "S_xTMtmRu02",
        "label": "Clone Slot 04",
        "hint": "S_xTMtmRu02 / Console slot"
      },
      {
        "value": "S_wTMtmRu02",
        "label": "Clone Slot 05",
        "hint": "S_wTMtmRu02 / Console slot"
      },
      {
        "value": "S_vTMtmRu02",
        "label": "Clone Slot 06",
        "hint": "S_vTMtmRu02 / Console slot"
      },
      {
        "value": "S_uTMtmRu02",
        "label": "Clone Slot 07",
        "hint": "S_uTMtmRu02 / Console slot"
      },
      {
        "value": "S_tTMtmRu02",
        "label": "Clone Slot 08",
        "hint": "S_tTMtmRu02 / Console slot"
      },
      {
        "value": "S_sTMtmRu02",
        "label": "Clone Slot 09",
        "hint": "S_sTMtmRu02 / Console slot"
      },
      {
        "value": "S_rTMtmRu02",
        "label": "Clone Slot 10",
        "hint": "S_rTMtmRu02 / Console slot"
      }
    ],
    "b-clone-speaker": [
      {
        "value": "",
        "label": "Not Selected",
        "hint": "Use AST voice output"
      },
      {
        "value": "S_ATMtmRu02",
        "label": "Primary Clone",
        "hint": "S_ATMtmRu02 / Ready"
      },
      {
        "value": "S_zTMtmRu02",
        "label": "Clone Slot 02",
        "hint": "S_zTMtmRu02 / Console slot"
      },
      {
        "value": "S_yTMtmRu02",
        "label": "Clone Slot 03",
        "hint": "S_yTMtmRu02 / Console slot"
      },
      {
        "value": "S_xTMtmRu02",
        "label": "Clone Slot 04",
        "hint": "S_xTMtmRu02 / Console slot"
      },
      {
        "value": "S_wTMtmRu02",
        "label": "Clone Slot 05",
        "hint": "S_wTMtmRu02 / Console slot"
      },
      {
        "value": "S_vTMtmRu02",
        "label": "Clone Slot 06",
        "hint": "S_vTMtmRu02 / Console slot"
      },
      {
        "value": "S_uTMtmRu02",
        "label": "Clone Slot 07",
        "hint": "S_uTMtmRu02 / Console slot"
      },
      {
        "value": "S_tTMtmRu02",
        "label": "Clone Slot 08",
        "hint": "S_tTMtmRu02 / Console slot"
      },
      {
        "value": "S_sTMtmRu02",
        "label": "Clone Slot 09",
        "hint": "S_sTMtmRu02 / Console slot"
      },
      {
        "value": "S_rTMtmRu02",
        "label": "Clone Slot 10",
        "hint": "S_rTMtmRu02 / Console slot"
      }
    ],
    "c-clone-speaker": [
      {
        "value": "",
        "label": "Not Selected",
        "hint": "Use AST voice output"
      },
      {
        "value": "S_ATMtmRu02",
        "label": "Primary Clone",
        "hint": "S_ATMtmRu02 / Ready"
      },
      {
        "value": "S_zTMtmRu02",
        "label": "Clone Slot 02",
        "hint": "S_zTMtmRu02 / Console slot"
      },
      {
        "value": "S_yTMtmRu02",
        "label": "Clone Slot 03",
        "hint": "S_yTMtmRu02 / Console slot"
      },
      {
        "value": "S_xTMtmRu02",
        "label": "Clone Slot 04",
        "hint": "S_xTMtmRu02 / Console slot"
      },
      {
        "value": "S_wTMtmRu02",
        "label": "Clone Slot 05",
        "hint": "S_wTMtmRu02 / Console slot"
      },
      {
        "value": "S_vTMtmRu02",
        "label": "Clone Slot 06",
        "hint": "S_vTMtmRu02 / Console slot"
      },
      {
        "value": "S_uTMtmRu02",
        "label": "Clone Slot 07",
        "hint": "S_uTMtmRu02 / Console slot"
      },
      {
        "value": "S_tTMtmRu02",
        "label": "Clone Slot 08",
        "hint": "S_tTMtmRu02 / Console slot"
      },
      {
        "value": "S_sTMtmRu02",
        "label": "Clone Slot 09",
        "hint": "S_sTMtmRu02 / Console slot"
      },
      {
        "value": "S_rTMtmRu02",
        "label": "Clone Slot 10",
        "hint": "S_rTMtmRu02 / Console slot"
      }
    ],
    "voice-clone-language": [
      {
        "value": "zh",
        "label": "Chinese",
        "hint": "zh"
      },
      {
        "value": "en",
        "label": "English",
        "hint": "en"
      }
    ]
  },
  "domain": {
    "id": "rust",
    "label": "Rust Raid",
    "description": "Biases recognition and translation toward Rust raid, farming, and roaming comms."
  },
  "devices": {
    "inputs": 9,
    "outputs": 6,
    "virtualInputs": 4,
    "virtualOutputs": 3
  },
  "nativeAudioCore": {
    "available": false,
    "enumerated": false,
    "runtime": "python",
    "binaryPath": "C:\\Users\\ANNN\\Documents\\Codex\\2026-04-22-in-out-discord-api-2-0\\native_audio_core\\target\\release\\nova-audio-core.exe",
    "deviceCount": 0,
    "lastSnapshot": {}
  },
  "voiceClone": {
    "speakerId": "S_ATMtmRu02",
    "statusCode": 2,
    "statusLabel": "Ready",
    "message": "Voice clone status refreshed.",
    "demoAudio": "https://lf6-lab-speech-tt-sign.bytespeech.com/tos-cn-o-14155/oUwLAdBWA6OOQDBNgAQim9atEf0s0RiBnAjxpG?x-expires=1776939538&x-signature=NkkBwJXU9AtnI1YVv4K6eZhGlVk%3D",
    "version": "V1",
    "updatedAt": "2026-04-23 16:18:58",
    "apiResourceId": "seed-icl-2.0",
    "billingResourceId": "volc.megatts.default",
    "samplePath": ".downloads/ast_python/ast_python/test_audio.wav",
    "referenceText": "",
    "demoText": "NOVA Interp clone training smoke test.",
    "language": "zh",
    "activeChannels": [
      "Channel A"
    ],
    "fallbackChannels": [],
    "runtimeLanguages": [
      "en"
    ],
    "catalog": [
      {
        "speaker_id": "S_ATMtmRu02",
        "label": "Primary Clone",
        "note": "Voice clone status refreshed.",
        "status_label": "Ready"
      },
      {
        "speaker_id": "S_zTMtmRu02",
        "label": "Clone Slot 02",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_yTMtmRu02",
        "label": "Clone Slot 03",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_xTMtmRu02",
        "label": "Clone Slot 04",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_wTMtmRu02",
        "label": "Clone Slot 05",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_vTMtmRu02",
        "label": "Clone Slot 06",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_uTMtmRu02",
        "label": "Clone Slot 07",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_tTMtmRu02",
        "label": "Clone Slot 08",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_sTMtmRu02",
        "label": "Clone Slot 09",
        "note": "Console slot",
        "status_label": ""
      },
      {
        "speaker_id": "S_rTMtmRu02",
        "label": "Clone Slot 10",
        "note": "Console slot",
        "status_label": ""
      }
    ]
  },
  "updater": {
    "current": {
      "version": "0.4.0",
      "channel": "alpha",
      "manifest_url": "",
      "notes": "Qt/Web dashboard with bilingual UI toggle, AGC/denoise tuning, voice clone workflow, updater hooks, and native audio core scaffold."
    },
    "manifestUrl": "",
    "lastCheck": null,
    "result": null,
    "download": null
  },
  "channels": {
    "a": {
      "title": "Channel A",
      "copy": "Outbound lane for your microphone, translated for the remote side.",
      "paneTitle": "Channel A to Remote"
    },
    "b": {
      "title": "Channel B",
      "copy": "Inbound lane for Discord or voice platform audio, translated back for your monitoring bus.",
      "paneTitle": "Discord to You"
    },
    "c": {
      "title": "Channel C",
      "copy": "Inbound lane for game voice audio, translated for your local monitoring without touching game effects routing.",
      "paneTitle": "Rust Voice to You"
    }
  },
  "transcripts": {
    "a": [
      {
        "time": "18:00:21",
        "source": "请写一段，",
        "target": "Please write a paragraph"
      },
      {
        "time": "18:00:24",
        "source": "衣柜男，",
        "target": "about a man in the closet."
      },
      {
        "time": "18:00:27",
        "source": "是，的责任心和担当。",
        "target": "About responsibility and commitment."
      },
      {
        "time": "18:00:30",
        "source": "我刚才上了电脑看了一下论坛，",
        "target": "I just checked the forum on my computer."
      },
      {
        "time": "18:00:33",
        "source": "看到了你发表的主题贴，",
        "target": "I saw your post."
      },
      {
        "time": "18:00:36",
        "source": "非常非常的好，",
        "target": "It's great,"
      },
      {
        "time": "18:00:39",
        "source": "比我高出不止十几个等级。",
        "target": "much better than mine."
      },
      {
        "time": "18:00:42",
        "source": "你以后不要叫我师父了，",
        "target": "You don't have to call me master anymore."
      },
      {
        "time": "18:00:45",
        "source": "我这个当不起呀，加油！",
        "target": "I don't deserve it. Keep it up."
      }
    ],
    "b": [
      {
        "time": "18:00:21",
        "source": "Please write a paragraph",
        "target": "请写一段，"
      },
      {
        "time": "18:00:24",
        "source": "about a man in the closet.",
        "target": "衣柜男，"
      },
      {
        "time": "18:00:27",
        "source": "About responsibility and commitment.",
        "target": "是，的责任心和担当。"
      },
      {
        "time": "18:00:30",
        "source": "I just checked the forum on my computer.",
        "target": "我刚才上了电脑看了一下论坛，"
      },
      {
        "time": "18:00:33",
        "source": "I saw your post.",
        "target": "看到了你发表的主题贴，"
      },
      {
        "time": "18:00:36",
        "source": "It's great,",
        "target": "非常非常的好，"
      },
      {
        "time": "18:00:39",
        "source": "much better than mine.",
        "target": "比我高出不止十几个等级。"
      },
      {
        "time": "18:00:42",
        "source": "You don't have to call me master anymore.",
        "target": "你以后不要叫我师父了，"
      },
      {
        "time": "18:00:45",
        "source": "I don't deserve it. Keep it up.",
        "target": "我这个当不起呀，加油！"
      }
    ]
  },
  "partials": {
    "a": {
      "source": "我这个当不起呀，加油！",
      "target": "I don't deserve it. Keep it up."
    },
    "b": {
      "source": "I don't deserve it. Keep it up.",
      "target": "我这个当不起呀，加油！"
    }
  },
  "runtime": {
    "running": false,
    "globalStatus": "Ready",
    "globalHint": "Biases recognition and translation toward Rust raid, farming, and roaming comms. / 3 virtual outputs detected.",
    "channels": {
      "a": {
        "signal": "idle",
        "label": "Ready",
        "pane": "Idle",
        "status": "Ready",
        "stats": {}
      },
      "b": {
        "signal": "idle",
        "label": "Ready",
        "pane": "Idle",
        "status": "Ready",
        "stats": {}
      },
      "c": {
        "signal": "idle",
        "label": "Disabled",
        "pane": "Disabled",
        "status": "Channel disabled",
        "stats": {}
      }
    },
    "metrics": {
      "inputA": "--",
      "inputB": "--",
      "inputC": "--",
      "ast": "--",
      "tts": "--"
    }
  },
  "meta": {
    "generatedAt": "2026-04-23T18:00:48",
    "smoke": {
      "elapsedSeconds": 23.553,
      "audioBytes": 1340976,
      "eventCounts": {
        "SessionStarted": 1,
        "SourceSubtitleStart": 9,
        "SourceSubtitleResponse": 59,
        "SourceSubtitleEnd": 9,
        "TranslationSubtitleStart": 9,
        "TranslationSubtitleResponse": 68,
        "TranslationSubtitleEnd": 9,
        "TTSSentenceStart": 9,
        "TTSResponse": 48,
        "UsageResponse": 10,
        "TTSSentenceEnd": 9,
        "SessionFinished": 1
      }
    }
  }
};
