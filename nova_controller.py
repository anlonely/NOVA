from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
import queue
import subprocess
import threading
import time
import uuid
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from audio_core_bridge import NativeAudioCoreBridge
from ast_bridge import (
    DEFAULT_INPUT_SAMPLE_RATE,
    DEFAULT_RESOURCE_ID,
    LANGUAGE_OPTIONS,
    PERFORMANCE_PRESETS,
    SUBTITLE_MODES,
    ChannelSettings,
    Credentials,
    DeviceCatalog,
    TranslationChannel,
    float_to_pcm16,
    samples_to_dbfs,
    use_system_proxy as ast_use_system_proxy,
)
from custom_dns import dns_override, format_dns_csv, parse_dns_hosts, parse_dns_servers, target_hosts_for_url
from paths import get_app_root, get_resource_root
from updater import AppUpdater
from voice_clone_manager import (
    VOICE_CLONE_BILLING_RESOURCE_ID,
    VOICE_CLONE_RESOURCE_ID,
    VoiceCloneError,
    VoiceCloneManager,
)
from python_protogen.common.events_pb2 import Type
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest, TranslateResponse

APP_ROOT = get_app_root()
RESOURCE_ROOT = get_resource_root()
ROOT = APP_ROOT
CONFIG_PATH = APP_ROOT / "config.local.json"
OUTPUT_DIR = APP_ROOT / "output"
VERSION_PATH = RESOURCE_ROOT / "app_version.json"
VOICE_CLONE_SAMPLE_DIR = APP_ROOT / ".downloads" / "voice_clone_samples"
VOICE_PREVIEW_SOURCE_DIR = APP_ROOT / ".downloads" / "voice_preview_sources"
VOICE_CLONE_RECORD_SAMPLE_RATE = DEFAULT_INPUT_SAMPLE_RATE
VOICE_CLONE_RECORD_BLOCK_FRAMES = 1600
VOICE_CLONE_MIN_SAMPLE_SECONDS = 1.2

CHANNEL_MAP = {"a": "outbound", "b": "inbound"}
CHANNEL_ID_TO_ALIAS = {value: key for key, value in CHANNEL_MAP.items()}
CHANNEL_ALIASES = tuple(CHANNEL_MAP.keys())
CHANNEL_IDS = tuple(CHANNEL_MAP.values())
CHANNEL_TITLE_MAP = {"a": "Channel A", "b": "Channel B"}
CHANNEL_COPY_MAP = {
    "a": "Outbound lane for your microphone, translated for the remote side.",
    "b": "Inbound lane for Discord or voice platform audio, translated back for your monitoring bus.",
}
CHANNEL_PANE_TITLE_MAP = {
    "a": "Channel A to Remote",
    "b": "Discord to You",
}
CHANNEL_SCENE_MAP = {"a": "outbound", "b": "inbound"}
CHANNEL_INPUT_PURPOSE = {"a": "voice_in", "b": "loopback_in"}
CORPUS_LIMIT = 1000
UI_LANGUAGE_OPTIONS = (
    {"value": "zh", "label": "简体中文", "hint": "Chinese interface"},
    {"value": "en", "label": "English", "hint": "English interface"},
)
VOICE_CLONE_STATUS_LABELS = {
    0: "Not Found",
    1: "Training",
    2: "Ready",
    3: "Failed",
    4: "Active",
}
LOCAL_CLONE_TTS_LANGUAGES = {"zh", "en"}
DEFAULT_VOICE_CLONE_CATALOG = (
    {"speaker_id": "S_ATMtmRu02", "label": "Primary Clone", "note": "Recommended slot"},
    {"speaker_id": "S_zTMtmRu02", "label": "Clone Slot 02", "note": "Console slot"},
    {"speaker_id": "S_yTMtmRu02", "label": "Clone Slot 03", "note": "Console slot"},
    {"speaker_id": "S_xTMtmRu02", "label": "Clone Slot 04", "note": "Console slot"},
    {"speaker_id": "S_wTMtmRu02", "label": "Clone Slot 05", "note": "Console slot"},
    {"speaker_id": "S_vTMtmRu02", "label": "Clone Slot 06", "note": "Console slot"},
    {"speaker_id": "S_uTMtmRu02", "label": "Clone Slot 07", "note": "Console slot"},
    {"speaker_id": "S_tTMtmRu02", "label": "Clone Slot 08", "note": "Console slot"},
    {"speaker_id": "S_sTMtmRu02", "label": "Clone Slot 09", "note": "Console slot"},
    {"speaker_id": "S_rTMtmRu02", "label": "Clone Slot 10", "note": "Console slot"},
)
PRIMARY_VOICE_CLONE_SPEAKER = DEFAULT_VOICE_CLONE_CATALOG[0]["speaker_id"]
DEFAULT_AST_VOICE_OPTION = {
    "speaker_id": "",
    "label": "Default AST Voice",
    "note": "Default / neutral / fastest setup",
}
AST_PRESET_VOICE_CATALOG = (
    {
        "speaker_id": "zh_female_vv_uranus_bigtts",
        "label": "Vivi 2.0",
        "note": "Female / bright / clear / lively",
    },
    {
        "speaker_id": "zh_female_xiaohe_uranus_bigtts",
        "label": "Xiaohe 2.0",
        "note": "Female / soft / steady / natural",
    },
    {
        "speaker_id": "zh_female_wenroushunv_mars_bigtts",
        "label": "Wenrou",
        "note": "Female / warm / gentle / relaxed",
    },
    {
        "speaker_id": "zh_male_m191_uranus_bigtts",
        "label": "Yunzhou 2.0",
        "note": "Male / deep / natural / broadcast",
    },
    {
        "speaker_id": "zh_male_taocheng_uranus_bigtts",
        "label": "Xiaotian 2.0",
        "note": "Male / clean / steady / neutral",
    },
    {
        "speaker_id": "zh_male_ruyaqingnian_mars_bigtts",
        "label": "Ruya",
        "note": "Male / gentle / calm / soft",
    },
)
AST_PRESET_VOICE_MAP = {item["speaker_id"]: item for item in AST_PRESET_VOICE_CATALOG}
VOICE_PREVIEW_SOURCE_TEXT = {
    "zh": "你好，这是 Nova 同传音色试听。现在测试翻译后的输出声音。",
    "en": "Hello, this is the Nova interpreter voice preview. We are testing the translated output voice now.",
}
VOICE_PREVIEW_SOURCE_CULTURE = {
    "zh": "zh-CN",
    "en": "en-US",
}
VOICE_PREVIEW_TARGET_RATE = 24000
VOICE_PREVIEW_CHUNK_BYTES = 3200

SCENE_TEMPLATES: dict[str, dict[str, Any]] = {
    "discord_bidirectional": {
        "label": "Discord Bidirectional",
        "description": "Chinese -> English and English -> Chinese for real-time Discord conversation.",
        "outbound": {
            "source_language": "zh",
            "target_language": "en",
            "performance_profile": "turbo",
            "subtitle_mode": "bilingual",
        },
        "inbound": {
            "source_language": "en",
            "target_language": "zh",
            "performance_profile": "turbo",
            "subtitle_mode": "bilingual",
        },
    },
}

RUST_TARGET_OVERRIDES_ZH_EN: tuple[tuple[str, str], ...] = (
    ("自动炮台给我授权", "Authorize me on the auto turret."),
    ("炮台给我授权", "Authorize me on the turret."),
    ("领地柜给我授权", "Authorize me on the TC."),
    ("tc给我授权", "Authorize me on the TC."),
    ("自动炮台授权", "Authorize me on the auto turret."),
    ("炮台授权", "Authorize me on the turret."),
)

RUST_TARGET_OVERRIDES_ZH_EN = (
    ("自动炮台给我授权", "Authorize me on the auto turret."),
    ("炮台给我授权", "Authorize me on the turret."),
    ("领地柜给我授权", "Authorize me on the TC."),
    ("tc给我授权", "Authorize me on the TC."),
    ("自动炮台授权", "Authorize me on the auto turret."),
    ("炮台授权", "Authorize me on the turret."),
)

DOMAIN_PACKS: dict[str, dict[str, Any]] = {
    "generic": {
        "label": "Generic Voice",
        "description": "Balanced general-purpose speech recognition and translation.",
        "context": "",
        "hot_words": [],
        "correct_words": {},
        "glossary": {},
    },
    "rust": {
        "label": "Rust Raid",
        "description": "Biases recognition and translation toward Rust raid, farming, and roaming comms.",
        "context": (
            "This is a real-time voice conversation about the survival game Rust. "
            "Common terms include Tool Cupboard or TC, raid, counter raid, sulfur, scrap, recycler, "
            "Bradley, Chinook, Oil Rig, Cargo, Launch Site, Outpost, Bandit Camp, Workbench, "
            "garage door, armored door, sheet metal, AK-47, MP5, C4, satchel, rocket, auto turret, "
            "and authorizing teammates on auto turrets or TC during raids."
        ),
        "hot_words": [
            "Rust",
            "TC",
            "Tool Cupboard",
            "raid",
            "counter raid",
            "Bradley",
            "Chinook",
            "Oil Rig",
            "Launch Site",
            "Cargo",
            "Outpost",
            "Bandit Camp",
            "Workbench",
            "garage door",
            "armored door",
            "sheet metal",
            "AK-47",
            "MP5",
            "C4",
            "satchel",
            "rocket",
            "sulfur",
            "scrap",
            "recycler",
            "auto turret",
            "authorize",
            "自动炮台",
            "炮台",
            "授权",
            "领地柜",
            "回收机",
            "发射基地",
            "货船",
        ],
        "correct_words": {
            "tc": "TC",
            "t c": "TC",
            "tool cupboard": "Tool Cupboard",
            "launchsite": "Launch Site",
            "oilrig": "Oil Rig",
            "cargo ship": "Cargo",
            "ak47": "AK-47",
            "ak 47": "AK-47",
            "mp 5": "MP5",
            "c 4": "C4",
            "satchel charge": "Satchel",
            "work bench": "Workbench",
            "sheetmetal": "Sheet Metal",
            "counterrate": "Counter Raid",
            "自动炮塔": "自动炮台",
            "自动跑台": "自动炮台",
            "领地归": "领地柜",
            "领地贵": "领地柜",
            "反超": "反抄",
            "发射场": "发射基地",
        },
        "glossary": {
            "领地柜": "Tool Cupboard (TC)",
            "抄家": "Raid",
            "反抄": "Counter Raid",
            "废料": "Scrap",
            "硫磺": "Sulfur",
            "回收机": "Recycler",
            "油井": "Oil Rig",
            "发射基地": "Launch Site",
            "货船": "Cargo",
            "工作台": "Workbench",
            "车库门": "Garage Door",
            "装甲门": "Armored Door",
            "铁皮": "Sheet Metal",
            "自动炮台": "Auto Turret",
            "炮台": "Turret",
            "自动炮台给我授权": "Authorize me on the auto turret",
            "炮台给我授权": "Authorize me on the turret",
            "领地柜给我授权": "Authorize me on the TC",
            "TC给我授权": "Authorize me on the TC",
            "给我授权": "Authorize me",
            "帮我授权": "Authorize me",
        },
    },
    "tactical_fps": {
        "label": "Tactical FPS",
        "description": "Biases recognition for tactical callouts, map names, and weapon terms.",
        "context": (
            "This is a real-time tactical FPS voice chat. Common terms include flank, rotate, push, hold, "
            "peek, smoke, flash, frag, sniper, mid, A site, B site, eco, and full buy."
        ),
        "hot_words": [
            "flank",
            "rotate",
            "site",
            "smoke",
            "flash",
            "frag",
            "eco",
            "full buy",
            "sniper",
            "mid",
        ],
        "correct_words": {},
        "glossary": {
            "侧拉": "Flank",
            "转点": "Rotate",
            "爆弹": "Utility dump",
            "静步": "Walk",
        },
    },
}

UI_LANGUAGE_OPTIONS = (
    {"value": "zh", "label": "简体中文", "hint": "Chinese interface"},
    {"value": "en", "label": "English", "hint": "English interface"},
)
DOMAIN_PACKS["rust"]["glossary"] = {
    "领地柜": "Tool Cupboard (TC)",
    "抄家": "Raid",
    "反抄": "Counter Raid",
    "废料": "Scrap",
    "硫磺": "Sulfur",
    "回收机": "Recycler",
    "油井": "Oil Rig",
    "发射基地": "Launch Site",
    "货船": "Cargo",
    "工作台": "Workbench",
    "车库门": "Garage Door",
    "装甲门": "Armored Door",
    "铁皮": "Sheet Metal",
    "自动炮台": "Auto Turret",
    "炮台": "Turret",
    "自动炮台给我授权": "Authorize me on the auto turret",
    "炮台给我授权": "Authorize me on the turret",
    "领地柜给我授权": "Authorize me on the TC",
    "TC给我授权": "Authorize me on the TC",
    "给我授权": "Authorize me",
    "帮我授权": "Authorize me",
}
DOMAIN_PACKS["tactical_fps"]["glossary"] = {
    "侧拉": "Flank",
    "转点": "Rotate",
    "爆弹": "Utility dump",
    "静步": "Walk",
}


RUST_COMMON_CONTEXT = (
    "This is a real-time voice conversation about the survival game Rust. "
    "Bias recognition and translation toward short raid, roam, farming, and base-defense callouts. "
    "Prefer domain-accurate terms such as Tool Cupboard, TC, auto turret, counter raid, counters, "
    "compound, roof, seal the breach, patch the wall, one down, full dead, pick me up, loot him, "
    "garage door, armored door, sheet metal, sulfur, scrap, recycler, minicopter, scrap heli, C4, "
    "satchel, rocket, Bradley, Chinook, Oil Rig, Cargo Ship, Launch Site, Outpost, Bandit Camp, "
    "Workbench, honeycomb, and high external walls. "
    "Examples include 'authorize me on the TC', 'people at the door', 'we have counters', "
    "'someone is in the compound', 'seal the breach', 'patch the wall', 'one dead', and 'full dead'."
)

RUST_COMMON_HOT_WORDS = (
    "Rust",
    "TC",
    "Tool Cupboard",
    "raid",
    "counter raid",
    "counters",
    "door camp",
    "Bradley",
    "Chinook",
    "Oil Rig",
    "Cargo Ship",
    "Launch Site",
    "Outpost",
    "Bandit Camp",
    "Workbench",
    "garage door",
    "armored door",
    "sheet metal",
    "auto turret",
    "turret",
    "compound",
    "roof",
    "breach",
    "seal the breach",
    "patch the wall",
    "one down",
    "full dead",
    "pick me up",
    "loot him",
    "loot the body",
    "Minicopter",
    "Scrap Heli",
    "High External Wall",
    "High External Gate",
    "C4",
    "satchel",
    "rocket",
    "explosive ammo",
    "sulfur",
    "scrap",
    "recycler",
    "\u9886\u5730\u67dc",
    "\u81ea\u52a8\u70ae\u53f0",
    "\u70ae\u53f0",
    "\u6284\u5bb6",
    "\u53cd\u6284",
    "\u95e8\u53e3\u6709\u4eba",
    "\u5916\u9762\u6709\u4eba",
    "\u5c4b\u9876\u6709\u4eba",
    "\u9662\u5b50\u91cc\u6709\u4eba",
    "\u697c\u4e0a\u6709\u4eba",
    "\u5c01\u95e8",
    "\u5c01\u53e3",
    "\u8865\u5899",
    "\u5012\u4e00\u4e2a",
    "\u6b7b\u900f\u4e86",
    "\u6276\u6211",
    "\u6361\u4ed6",
    "\u8214\u5305",
    "\u7ed9\u6211\u706b\u7bad",
    "\u7ed9\u6211C4",
    "\u7ed9\u6211\u5b50\u5f39",
    "\u7ed9\u6211\u836f",
    "\u5f00\u95e8",
    "\u5173\u95e8",
    "\u9ad8\u5899",
    "\u8702\u5de2",
    "\u5c0f\u98de\u673a",
    "\u5927\u98de\u673a",
    "\u56de\u6536\u673a",
    "\u6cb9\u4e95",
    "\u53d1\u5c04\u57fa\u5730",
    "\u8d27\u8239",
    "\u5de5\u4f5c\u53f0",
    "\u8f66\u5e93\u95e8",
    "\u88c5\u7532\u95e8",
    "\u94c1\u76ae",
    "\u786b\u78fa",
    "\u5e9f\u6599",
)

RUST_COMMON_CORRECT_WORDS: dict[str, str] = {
    "tc": "TC",
    "t c": "TC",
    "tool cupboard": "Tool Cupboard",
    "toolcupboard": "Tool Cupboard",
    "autoturret": "Auto Turret",
    "auto turrent": "Auto Turret",
    "auto turet": "Auto Turret",
    "launchsite": "Launch Site",
    "oilrig": "Oil Rig",
    "cargo ship": "Cargo Ship",
    "banditcamp": "Bandit Camp",
    "out post": "Outpost",
    "work bench": "Workbench",
    "sheetmetal": "Sheet Metal",
    "counterrate": "Counter Raid",
    "mini copter": "Minicopter",
    "mini chopper": "Minicopter",
    "scrap heli": "Scrap Heli",
    "\u81ea\u52a8\u70ae\u5854": "\u81ea\u52a8\u70ae\u53f0",
    "\u81ea\u52a8\u8dd1\u53f0": "\u81ea\u52a8\u70ae\u53f0",
    "\u70ae\u5854": "\u70ae\u53f0",
    "\u9886\u5730\u5f52": "\u9886\u5730\u67dc",
    "\u9886\u5730\u8d35": "\u9886\u5730\u67dc",
    "\u53cd\u8d85": "\u53cd\u6284",
    "\u53cd\u7092": "\u53cd\u6284",
    "\u53d1\u5c04\u573a": "\u53d1\u5c04\u57fa\u5730",
    "\u56de\u6536\u5668": "\u56de\u6536\u673a",
}

RUST_COMMON_GLOSSARY: dict[str, str] = {
    "\u9886\u5730\u67dc": "Tool Cupboard (TC)",
    "\u81ea\u52a8\u70ae\u53f0": "Auto Turret",
    "\u70ae\u53f0": "Turret",
    "\u6284\u5bb6": "Raid",
    "\u53cd\u6284": "Counter Raid",
    "\u5e9f\u6599": "Scrap",
    "\u786b\u78fa": "Sulfur",
    "\u56de\u6536\u673a": "Recycler",
    "\u6cb9\u4e95": "Oil Rig",
    "\u53d1\u5c04\u57fa\u5730": "Launch Site",
    "\u8d27\u8239": "Cargo Ship",
    "\u5de5\u4f5c\u53f0": "Workbench",
    "\u8f66\u5e93\u95e8": "Garage Door",
    "\u88c5\u7532\u95e8": "Armored Door",
    "\u94c1\u76ae": "Sheet Metal",
    "\u9662\u5b50": "Compound",
    "\u5c4b\u9876": "Roof",
    "\u8702\u5de2": "Honeycomb",
    "\u9ad8\u5899": "High External Wall",
    "\u5c0f\u98de\u673a": "Minicopter",
    "\u5927\u98de\u673a": "Scrap Heli",
    "\u95e8\u53e3\u6709\u4eba": "People at the door",
    "\u5916\u9762\u6709\u4eba": "People outside",
    "\u5c4b\u9876\u6709\u4eba": "Someone is on the roof",
    "\u9662\u5b50\u91cc\u6709\u4eba": "Someone is in the compound",
    "\u697c\u4e0a\u6709\u4eba": "Someone is upstairs",
    "\u5c01\u95e8": "Seal the door",
    "\u5c01\u53e3": "Seal the breach",
    "\u8865\u5899": "Patch the wall",
    "\u5012\u4e00\u4e2a": "One down",
    "\u6b7b\u900f\u4e86": "Full dead",
    "\u6276\u6211": "Pick me up",
    "\u6361\u4ed6": "Loot him",
    "\u8214\u5305": "Loot the body",
    "\u5f00\u95e8": "Open the door",
    "\u5173\u95e8": "Close the door",
    "\u7ed9\u6211\u706b\u7bad": "Give me rockets",
    "\u7ed9\u6211C4": "Give me C4",
    "\u7ed9\u6211\u5b50\u5f39": "Give me ammo",
    "\u7ed9\u6211\u836f": "Give me meds",
    "Tool Cupboard": "\u9886\u5730\u67dc (TC)",
    "Auto Turret": "\u81ea\u52a8\u70ae\u53f0",
    "Counter Raid": "\u53cd\u6284",
    "Oil Rig": "\u6cb9\u4e95",
    "Launch Site": "\u53d1\u5c04\u57fa\u5730",
    "Cargo Ship": "\u8d27\u8239",
    "Workbench": "\u5de5\u4f5c\u53f0",
    "Garage Door": "\u8f66\u5e93\u95e8",
    "Armored Door": "\u88c5\u7532\u95e8",
    "Sheet Metal": "\u94c1\u76ae",
    "Compound": "\u9662\u5b50",
    "Roof": "\u5c4b\u9876",
    "Honeycomb": "\u8702\u5de2",
    "Minicopter": "\u5c0f\u98de\u673a",
    "Scrap Heli": "\u5927\u98de\u673a",
    "People at the door": "\u95e8\u53e3\u6709\u4eba",
    "People outside": "\u5916\u9762\u6709\u4eba",
    "Someone is on the roof": "\u5c4b\u9876\u6709\u4eba",
    "Someone is in the compound": "\u9662\u5b50\u91cc\u6709\u4eba",
    "Someone is upstairs": "\u697c\u4e0a\u6709\u4eba",
    "Seal the breach": "\u5148\u5c01\u53e3",
    "Seal the door": "\u5c01\u95e8",
    "Patch the wall": "\u8865\u5899",
    "One down": "\u5012\u4e00\u4e2a",
    "One dead": "\u5012\u4e00\u4e2a",
    "Full dead": "\u6b7b\u900f\u4e86",
    "Pick me up": "\u6276\u6211",
    "Loot him": "\u6361\u4ed6",
    "Loot the body": "\u8214\u5305",
    "Open the door": "\u5f00\u95e8",
    "Close the door": "\u5173\u95e8",
    "Give me rockets": "\u7ed9\u6211\u706b\u7bad",
    "Give me C4": "\u7ed9\u6211C4",
    "Give me ammo": "\u7ed9\u6211\u5b50\u5f39",
    "Give me meds": "\u7ed9\u6211\u836f",
}

RUST_TARGET_OVERRIDES_ZH_EN = (
    ("\u81ea\u52a8\u70ae\u53f0\u7ed9\u6211\u6388\u6743", "Authorize me on the auto turret."),
    ("\u70ae\u53f0\u7ed9\u6211\u6388\u6743", "Authorize me on the turret."),
    ("\u9886\u5730\u67dc\u7ed9\u6211\u6388\u6743", "Authorize me on the TC."),
    ("tc\u7ed9\u6211\u6388\u6743", "Authorize me on the TC."),
    ("\u81ea\u52a8\u70ae\u53f0\u6388\u6743", "Authorize me on the auto turret."),
    ("\u70ae\u53f0\u6388\u6743", "Authorize me on the turret."),
    ("\u6709\u4eba\u6765\u53cd\u6284\u4e86", "We have counters."),
    ("\u6709\u4eba\u53cd\u6284", "We have counters."),
    ("\u95e8\u53e3\u6709\u4eba", "People at the door."),
    ("\u5916\u9762\u6709\u4eba", "People outside."),
    ("\u5c4b\u9876\u6709\u4eba", "Someone is on the roof."),
    ("\u9662\u5b50\u91cc\u6709\u4eba", "Someone is in the compound."),
    ("\u697c\u4e0a\u6709\u4eba", "Someone is upstairs."),
    ("\u5148\u5c01\u95e8", "Seal the door first."),
    ("\u5c01\u95e8", "Seal the door."),
    ("\u5c01\u53e3", "Seal the breach."),
    ("\u8865\u5899", "Patch the wall."),
    ("\u5012\u4e00\u4e2a", "One down."),
    ("\u6b7b\u900f\u4e86", "Full dead."),
    ("\u6276\u6211", "Pick me up."),
    ("\u6361\u4ed6", "Loot him."),
    ("\u8214\u5305", "Loot the body."),
    ("\u5f00\u95e8", "Open the door."),
    ("\u5173\u95e8", "Close the door."),
    ("\u7ed9\u6211\u706b\u7bad", "Give me rockets."),
    ("\u7ed9\u6211c4", "Give me C4."),
    ("\u7ed9\u6211\u5b50\u5f39", "Give me ammo."),
    ("\u7ed9\u6211\u836f", "Give me meds."),
    ("\u524d\u95e8\u6709\u4eba", "Someone is at the front door."),
    ("\u540e\u95e8\u6709\u4eba", "Someone is at the back door."),
)

RUST_TARGET_OVERRIDES_EN_ZH = (
    ("authorize me on the auto turret", "\u7ed9\u6211\u81ea\u52a8\u70ae\u53f0\u6388\u6743\u3002"),
    ("authorize me on the turret", "\u7ed9\u6211\u70ae\u53f0\u6388\u6743\u3002"),
    ("authorize me on the tc", "\u7ed9\u6211\u9886\u5730\u67dc\u6388\u6743\u3002"),
    ("authorize me on the tool cupboard", "\u7ed9\u6211\u9886\u5730\u67dc\u6388\u6743\u3002"),
    ("we have counters", "\u6709\u4eba\u6765\u53cd\u6284\u4e86\u3002"),
    ("counters", "\u6709\u4eba\u6765\u53cd\u6284\u4e86\u3002"),
    ("people at the door", "\u95e8\u53e3\u6709\u4eba\u3002"),
    ("people outside", "\u5916\u9762\u6709\u4eba\u3002"),
    ("someone is on the roof", "\u5c4b\u9876\u6709\u4eba\u3002"),
    ("on the roof", "\u5728\u5c4b\u9876\u3002"),
    ("someone is in the compound", "\u9662\u5b50\u91cc\u6709\u4eba\u3002"),
    ("in the compound", "\u5728\u9662\u5b50\u91cc\u3002"),
    ("someone is upstairs", "\u697c\u4e0a\u6709\u4eba\u3002"),
    ("seal the breach", "\u5148\u5c01\u53e3\u3002"),
    ("seal the door", "\u5c01\u95e8\u3002"),
    ("patch the wall", "\u8865\u5899\u3002"),
    ("one down", "\u5012\u4e00\u4e2a\u3002"),
    ("one dead", "\u5012\u4e00\u4e2a\u3002"),
    ("full dead", "\u6b7b\u900f\u4e86\u3002"),
    ("pick me up", "\u6276\u6211\u3002"),
    ("loot him", "\u6361\u4ed6\u3002"),
    ("loot the body", "\u8214\u5305\u3002"),
    ("open the door", "\u5f00\u95e8\u3002"),
    ("close the door", "\u5173\u95e8\u3002"),
    ("give me rockets", "\u7ed9\u6211\u706b\u7bad\u3002"),
    ("give me c4", "\u7ed9\u6211C4\u3002"),
    ("give me ammo", "\u7ed9\u6211\u5b50\u5f39\u3002"),
    ("give me meds", "\u7ed9\u6211\u836f\u3002"),
    ("front door", "\u524d\u95e8"),
    ("back door", "\u540e\u95e8"),
)

DOMAIN_PACKS["rust"]["context"] = RUST_COMMON_CONTEXT
DOMAIN_PACKS["rust"]["hot_words"] = list(RUST_COMMON_HOT_WORDS)
DOMAIN_PACKS["rust"]["correct_words"] = dict(RUST_COMMON_CORRECT_WORDS)
DOMAIN_PACKS["rust"]["glossary"] = dict(RUST_COMMON_GLOSSARY)


def format_ts(timestamp: float | None) -> str:
    if not timestamp:
        return time.strftime("%H:%M:%S")
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def scene_id_from_label(label: str) -> str:
    return "discord_bidirectional"


def parse_hot_words(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    normalized = (text or "").replace("；", ";").replace("，", ",").replace("、", ",").replace(";", ",")
    for raw_line in normalized.splitlines():
        for raw_token in raw_line.split(","):
            token = raw_token.strip()
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            tokens.append(token)
    return tokens


def parse_mapping_text(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        separator = None
        for candidate in ("=>", "->", "=", ":", "：", "\t"):
            if candidate in line:
                separator = candidate
                break
        if separator is None:
            continue
        left, right = line.split(separator, 1)
        source = left.strip()
        target = right.strip()
        if source and target:
            mapping[source] = target
    return mapping


def serialize_hot_words(items: list[str]) -> str:
    return ", ".join(items)


def serialize_mapping(mapping: dict[str, str]) -> str:
    return "\n".join(f"{key} => {value}" for key, value in mapping.items())


def apply_replacements(text: str, mapping: dict[str, str]) -> str:
    if not text or not mapping:
        return text
    result = text
    for source in sorted(mapping, key=len, reverse=True):
        if source:
            result = result.replace(source, mapping[source])
    return result


def looks_garbled(text: str) -> bool:
    sample = str(text or "")
    markers = ("锛", "鎶", "鍙", "瑁", "閾", "", "鍥", "璐", "鐖", "杞", "棰")
    return any(marker in sample for marker in markers)


def normalize_phrase_key(text: str) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def apply_domain_translation_override(
    domain_id: str,
    source_text: str,
    target_text: str,
    target_language: str,
) -> str:
    if domain_id != "rust":
        return target_text
    normalized_source = normalize_phrase_key(source_text)
    if not normalized_source:
        return target_text
    target_code = str(target_language or "").lower()
    if target_code.startswith("en"):
        overrides = RUST_TARGET_OVERRIDES_ZH_EN
    elif target_code.startswith("zh"):
        overrides = RUST_TARGET_OVERRIDES_EN_ZH
    else:
        overrides = ()
    for source_phrase, override_text in overrides:
        if normalized_source == normalize_phrase_key(source_phrase):
            return override_text
    return target_text


def looks_garbled(text: str) -> bool:
    sample = str(text or "")
    if not sample:
        return False
    markers = (
        "\ufffd",
        "鑷姩鐐彴",
        "棰嗗湴鏌",
        "鎶勫",
        "鍙嶆妱",
        "搴熸枡",
        "纭：",
        "鍥炴敹鏈",
        "娌逛簳",
        "鍙戝皠鍩哄湴",
        "璐ц埞",
        "宸ヤ綔鍙",
        "杞﹀簱闂",
        "瑁呯敳闂",
        "閾佺毊",
        "渚ф媺",
        "杞偣",
        "闈欐",
    )
    return any(marker in sample for marker in markers)


def looks_garbled(text: str) -> bool:
    sample = str(text or "")
    if not sample:
        return False
    markers = (
        "\ufffd",
        "鑷姩鐐彴",
        "棰嗗湴鏌",
        "鎶勫",
        "鍙嶆妱",
        "搴熸枡",
        "纭：",
        "鍥炴敹鏈",
        "娌逛簳",
        "鍙戝皠鍩哄湴",
        "璐ц埞",
        "宸ヤ綔鍙",
        "杞﹀簱闂",
        "瑁呯敳闂",
        "閾佺毊",
        "渚ф媺",
        "杞偣",
        "闈欐",
    )
    return any(marker in sample for marker in markers)


def safe_int(value: Any, fallback: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def looks_like_console_speaker_id(value: str) -> bool:
    text = str(value or "").strip()
    return text.startswith("S_") or text.startswith("ICL_")


def normalize_voice_clone_catalog(
    catalog: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *speaker_ids: str,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_entry(speaker_id: str, label: str = "", note: str = "", status_label: str = "") -> None:
        sid = str(speaker_id or "").strip()
        if not sid or sid in seen or not looks_like_console_speaker_id(sid):
            return
        seen.add(sid)
        slot_index = len(normalized) + 1
        normalized.append(
            {
                "speaker_id": sid,
                "label": label.strip() or f"Clone Slot {slot_index:02d}",
                "note": note.strip(),
                "status_label": status_label.strip(),
            }
        )

    for item in DEFAULT_VOICE_CLONE_CATALOG:
        add_entry(
            speaker_id=str(item.get("speaker_id", "")),
            label=str(item.get("label", "")),
            note=str(item.get("note", "")),
            status_label=str(item.get("status_label", "")),
        )

    for item in catalog or []:
        if isinstance(item, dict):
            add_entry(
                speaker_id=str(item.get("speaker_id", "")),
                label=str(item.get("label", "")),
                note=str(item.get("note", "")),
                status_label=str(item.get("status_label", "")),
            )
        else:
            add_entry(str(item))

    for speaker_id in speaker_ids:
        add_entry(str(speaker_id or ""))

    return normalized


class NovaController:
    def __init__(self) -> None:
        self.catalog = DeviceCatalog()
        self.native_audio_core = NativeAudioCoreBridge()
        self.updater = AppUpdater()
        self.event_queue: queue.Queue[dict] = queue.Queue()
        self.channels: dict[str, TranslationChannel] = {}
        self.stats_by_channel: dict[str, dict[str, Any]] = {channel_id: {} for channel_id in CHANNEL_IDS}
        self.transcripts: dict[str, list[dict[str, str]]] = {channel_id: [] for channel_id in CHANNEL_IDS}
        self.partials: dict[str, dict[str, str]] = {channel_id: {"source": "", "target": ""} for channel_id in CHANNEL_IDS}
        self.channel_status: dict[str, str] = {channel_id: "Ready" for channel_id in CHANNEL_IDS}
        self.last_error: dict[str, str] = {channel_id: "" for channel_id in CHANNEL_IDS}
        self.correction_maps: dict[str, dict[str, str]] = {channel_id: {} for channel_id in CHANNEL_IDS}

        self.credentials = {
            "appId": "",
            "accessToken": "",
            "secretKey": "",
            "resourceId": DEFAULT_RESOURCE_ID,
        }
        self.native_audio_snapshot: dict[str, Any] = self.native_audio_core.enumerate_devices() or {}
        self.native_audio_health: dict[str, Any] = self.native_audio_core.health() if self.native_audio_core.available else {"ok": False}
        self.native_audio_health_checked_at = time.time()
        self.native_audio_last_device_change: dict[str, Any] | None = None
        self.native_audio_degraded_reason = ""
        self.native_audio_affected_channels: list[dict[str, Any]] = []
        self.native_audio_recovered_routes: list[dict[str, Any]] = []
        self.update_snapshot: dict[str, Any] = {
            "current": dict(self.updater.current),
            "lastCheck": None,
            "result": None,
            "download": None,
        }
        self.voice_clone_snapshot: dict[str, Any] = {
            "speakerId": "",
            "statusCode": None,
            "statusLabel": "Not Configured",
            "message": "",
            "demoAudio": "",
            "version": "",
            "updatedAt": "",
            "apiResourceId": VOICE_CLONE_RESOURCE_ID,
            "billingResourceId": VOICE_CLONE_BILLING_RESOURCE_ID,
        }
        self.voice_clone_catalog = normalize_voice_clone_catalog(DEFAULT_VOICE_CLONE_CATALOG)
        self._voice_clone_record_lock = threading.Lock()
        self._voice_clone_record_stop = threading.Event()
        self._voice_clone_record_thread: threading.Thread | None = None
        self._voice_preview_lock = threading.Lock()
        self._voice_preview_job: dict[str, Any] | None = None
        self._voice_clone_record_device_id = ""
        self._voice_clone_record_device_name = ""
        self._voice_clone_record_started_at = 0.0
        self._voice_clone_record_duration_sec = 0.0
        self._voice_clone_record_level_db = -96.0
        self._config_migration_needed = False
        self._runtime_credentials: Credentials | None = None
        self._local_tts_disabled_channels: set[str] = set()
        self.values = self._default_values()
        self.scene_id = "discord_bidirectional"
        self.domain_id = "rust"

        self._load_config()
        config_repaired = self._sanitize_values()
        self.refresh_devices(preserve_selection=True)
        self._rebuild_correction_maps()
        if config_repaired or self._config_migration_needed:
            self.save_config()

    def shutdown(self) -> None:
        self.stop_channels()
        self._stop_voice_clone_recording(wait_timeout=2.0)

    def _default_values(self) -> dict[str, str]:
        return {
            "scene": "discord_bidirectional",
            "ui-language": "zh",
            "domain-preset": "rust",
            "domain-context": DOMAIN_PACKS["rust"]["context"],
            "domain-hot-words": serialize_hot_words(DOMAIN_PACKS["rust"]["hot_words"]),
            "domain-correct-words": serialize_mapping(DOMAIN_PACKS["rust"]["correct_words"]),
            "domain-glossary": serialize_mapping(DOMAIN_PACKS["rust"]["glossary"]),
            "network-dns-servers": "",
            "network-dns-hosts": "",
            "update-manifest-url": str(self.updater.current.get("manifest_url", "") or ""),
            "audio-capture-backend": "python",
            "audio-native-fallback": "1",
            "audio-pre-roll-ms": "160",
            "audio-resampler-quality": "sinc-lite",
            "audio-vad-mode": "adaptive",
            "audio-noise-floor": "1",
            "audio-adaptive-chunking": "1",
            "audio-playback-backend": "python",
            "audio-auto-profile": "1",
            "audio-device-auto-recover": "0",
            "voice-clone-speaker-id": PRIMARY_VOICE_CLONE_SPEAKER,
            "voice-clone-sample-path": "",
            "voice-clone-reference-text": "",
            "voice-clone-demo-text": "This is a cloned voice preview for Nova Interp.",
            "voice-clone-language": "zh",
            "voice-clone-record-device": "",
            "a-enabled": "1",
            "a-input-enabled": "1",
            "a-output-enabled": "1",
            "a-monitor-enabled": "1",
            "a-input": "",
            "a-output": "",
            "a-monitor-output": "",
            "a-source": "zh",
            "a-target": "en",
            "a-speaker": "",
            "a-profile": "turbo",
            "a-subtitle": "bilingual",
            "a-startup-buffer": "16",
            "a-noise-gate": "-46",
            "a-hold-ms": "140",
            "a-skip-silence": "1",
            "a-enable-agc": "1",
            "a-agc-target": "-18",
            "a-agc-max-gain": "6",
            "a-enable-denoise": "1",
            "a-denoise-strength": "0.22",
            "a-clone-enabled": "0",
            "a-clone-speaker": PRIMARY_VOICE_CLONE_SPEAKER,
            "a-clone-speed": "1.0",
            "b-enabled": "1",
            "b-input-enabled": "1",
            "b-output-enabled": "1",
            "b-monitor-enabled": "0",
            "b-input": "",
            "b-output": "",
            "b-monitor-output": "",
            "b-source": "en",
            "b-target": "zh",
            "b-speaker": "",
            "b-profile": "turbo",
            "b-subtitle": "bilingual",
            "b-startup-buffer": "16",
            "b-noise-gate": "-46",
            "b-hold-ms": "140",
            "b-skip-silence": "1",
            "b-enable-agc": "1",
            "b-agc-target": "-18",
            "b-agc-max-gain": "6",
            "b-enable-denoise": "1",
            "b-denoise-strength": "0.22",
            "b-clone-enabled": "0",
            "b-clone-speaker": PRIMARY_VOICE_CLONE_SPEAKER,
            "b-clone-speed": "1.0",
        }

    def _load_config(self) -> None:
        if not CONFIG_PATH.exists():
            return
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except Exception:
            return

        if "domain" not in data:
            self._config_migration_needed = True

        self.credentials = {
            "appId": data.get("app_key", ""),
            "accessToken": data.get("access_key", ""),
            "secretKey": data.get("secret_key", ""),
            "resourceId": data.get("resource_id", DEFAULT_RESOURCE_ID) or DEFAULT_RESOURCE_ID,
        }
        self.scene_id = scene_id_from_label(data.get("selected_scene", ""))
        self.values["scene"] = self.scene_id
        self.values["ui-language"] = str(data.get("ui_language", self.values["ui-language"]) or self.values["ui-language"])

        updater = data.get("updater", {})
        manifest_url = str(updater.get("manifest_url", self.values["update-manifest-url"]) or "")
        self.values["update-manifest-url"] = manifest_url
        if manifest_url:
            self.updater.set_manifest_url(manifest_url)
        self.update_snapshot["current"] = dict(self.updater.current)

        network = data.get("network", {})
        self.values["network-dns-servers"] = format_dns_csv(parse_dns_servers(network.get("dns_servers")))
        self.values["network-dns-hosts"] = format_dns_csv(parse_dns_hosts(network.get("dns_hosts")))

        audio_core = data.get("audio_core", {})
        self.values["audio-capture-backend"] = str(audio_core.get("capture_backend", self.values["audio-capture-backend"]) or "python")
        self.values["audio-native-fallback"] = "1" if audio_core.get("native_capture_fallback", self.values["audio-native-fallback"] == "1") else "0"
        self.values["audio-pre-roll-ms"] = str(audio_core.get("pre_roll_ms", self.values["audio-pre-roll-ms"]))
        self.values["audio-resampler-quality"] = str(audio_core.get("resampler_quality", self.values["audio-resampler-quality"]) or "sinc-lite")
        self.values["audio-vad-mode"] = str(audio_core.get("vad_mode", self.values["audio-vad-mode"]) or "adaptive")
        self.values["audio-noise-floor"] = "1" if audio_core.get("enable_noise_floor", self.values["audio-noise-floor"] == "1") else "0"
        self.values["audio-adaptive-chunking"] = "1" if audio_core.get("adaptive_chunking", self.values["audio-adaptive-chunking"] == "1") else "0"
        self.values["audio-playback-backend"] = str(audio_core.get("playback_backend", self.values["audio-playback-backend"]) or "python")
        self.values["audio-auto-profile"] = "1" if audio_core.get("auto_profile", self.values["audio-auto-profile"] == "1") else "0"
        self.values["audio-device-auto-recover"] = "1" if audio_core.get("device_auto_recover", self.values["audio-device-auto-recover"] == "1") else "0"

        voice_clone = data.get("voice_clone", {})
        self.values["voice-clone-speaker-id"] = str(voice_clone.get("speaker_id", self.values["voice-clone-speaker-id"]) or "")
        self.values["voice-clone-sample-path"] = str(voice_clone.get("sample_path", self.values["voice-clone-sample-path"]) or "")
        self.values["voice-clone-reference-text"] = str(voice_clone.get("reference_text", self.values["voice-clone-reference-text"]) or "")
        self.values["voice-clone-demo-text"] = str(voice_clone.get("demo_text", self.values["voice-clone-demo-text"]) or "")
        self.values["voice-clone-language"] = str(voice_clone.get("language", self.values["voice-clone-language"]) or self.values["voice-clone-language"])
        self.values["voice-clone-record-device"] = str(voice_clone.get("record_device", self.values["voice-clone-record-device"]) or "")
        self.voice_clone_snapshot.update(
            {
                "speakerId": self.values["voice-clone-speaker-id"],
                "statusCode": voice_clone.get("status_code"),
                "statusLabel": str(voice_clone.get("status_label", self.voice_clone_snapshot["statusLabel"]) or self.voice_clone_snapshot["statusLabel"]),
                "message": str(voice_clone.get("message", "") or ""),
                "demoAudio": str(voice_clone.get("demo_audio", "") or ""),
                "version": str(voice_clone.get("version", "") or ""),
                "updatedAt": str(voice_clone.get("updated_at", "") or ""),
            }
        )

        domain = data.get("domain", {})
        domain_id = domain.get("preset", self.values["domain-preset"])
        self._apply_domain_pack_values(domain_id, overwrite_custom=False)
        for config_key, value_key in (
            ("context", "domain-context"),
            ("hot_words", "domain-hot-words"),
            ("correct_words", "domain-correct-words"),
            ("glossary", "domain-glossary"),
        ):
            if domain.get(config_key) is None:
                continue
            configured_value = str(domain.get(config_key) or "")
            if configured_value.strip() or domain_id != "rust":
                self.values[value_key] = configured_value

        channels = data.get("channels", {})
        outbound = channels.get("outbound", {})
        inbound = channels.get("inbound", {})
        self.voice_clone_catalog = normalize_voice_clone_catalog(
            voice_clone.get("speaker_catalog"),
            voice_clone.get("speaker_id", ""),
            outbound.get("voice_clone_speaker_id", ""),
            inbound.get("voice_clone_speaker_id", ""),
        )
        if "game_inbound" in channels:
            self._config_migration_needed = True
        for channel_data in (outbound, inbound):
            required_fields = {
                "enabled",
                "capture_enabled",
                "playback_enabled",
                "startup_buffer_ms",
                "skip_silence",
                "noise_gate_db",
                "silence_hold_ms",
                "enable_agc",
                "agc_target_dbfs",
                "max_agc_gain",
                "enable_denoise",
                "denoise_strength",
                "monitor_playback_enabled",
                "monitor_playback_device_id",
                "speaker_id",
                "voice_clone_enabled",
                "voice_clone_speaker_id",
                "voice_clone_speed",
            }
            if channel_data and not required_fields <= set(channel_data):
                self._config_migration_needed = True

        self.values.update(
            {
                "a-input": str(outbound.get("capture_device_id", "") or ""),
                "a-output": str(outbound.get("playback_device_id", "") or ""),
                "a-monitor-output": str(outbound.get("monitor_playback_device_id", "") or ""),
                "a-source": outbound.get("source_language", self.values["a-source"]),
                "a-target": outbound.get("target_language", self.values["a-target"]),
                "a-speaker": str(outbound.get("speaker_id", self.values["a-speaker"]) or ""),
                "a-profile": outbound.get("performance_profile", self.values["a-profile"]),
                "a-subtitle": outbound.get("subtitle_mode", self.values["a-subtitle"]),
                "a-startup-buffer": str(outbound.get("startup_buffer_ms", self.values["a-startup-buffer"])),
                "a-noise-gate": str(outbound.get("noise_gate_db", self.values["a-noise-gate"])),
                "a-hold-ms": str(outbound.get("silence_hold_ms", self.values["a-hold-ms"])),
                "a-skip-silence": "1" if outbound.get("skip_silence", True) else "0",
                "a-enable-agc": "1" if outbound.get("enable_agc", True) else "0",
                "a-agc-target": str(outbound.get("agc_target_dbfs", self.values["a-agc-target"])),
                "a-agc-max-gain": str(outbound.get("max_agc_gain", self.values["a-agc-max-gain"])),
                "a-enable-denoise": "1" if outbound.get("enable_denoise", True) else "0",
                "a-denoise-strength": str(outbound.get("denoise_strength", self.values["a-denoise-strength"])),
                "a-clone-enabled": "1" if outbound.get("voice_clone_enabled", False) else "0",
                "a-clone-speaker": str(outbound.get("voice_clone_speaker_id", self.values["a-clone-speaker"]) or ""),
                "a-clone-speed": str(outbound.get("voice_clone_speed", self.values["a-clone-speed"])),
                "a-enabled": "1" if outbound.get("enabled", True) else "0",
                "a-input-enabled": "1" if outbound.get("capture_enabled", True) else "0",
                "a-output-enabled": "1" if outbound.get("playback_enabled", True) else "0",
                "a-monitor-enabled": "1" if outbound.get("monitor_playback_enabled", self.values["a-monitor-enabled"] == "1") else "0",
                "b-input": str(inbound.get("capture_device_id", "") or ""),
                "b-output": str(inbound.get("playback_device_id", "") or ""),
                "b-monitor-output": str(inbound.get("monitor_playback_device_id", "") or ""),
                "b-source": inbound.get("source_language", self.values["b-source"]),
                "b-target": inbound.get("target_language", self.values["b-target"]),
                "b-speaker": str(inbound.get("speaker_id", self.values["b-speaker"]) or ""),
                "b-profile": inbound.get("performance_profile", self.values["b-profile"]),
                "b-subtitle": inbound.get("subtitle_mode", self.values["b-subtitle"]),
                "b-startup-buffer": str(inbound.get("startup_buffer_ms", self.values["b-startup-buffer"])),
                "b-noise-gate": str(inbound.get("noise_gate_db", self.values["b-noise-gate"])),
                "b-hold-ms": str(inbound.get("silence_hold_ms", self.values["b-hold-ms"])),
                "b-skip-silence": "1" if inbound.get("skip_silence", True) else "0",
                "b-enable-agc": "1" if inbound.get("enable_agc", True) else "0",
                "b-agc-target": str(inbound.get("agc_target_dbfs", self.values["b-agc-target"])),
                "b-agc-max-gain": str(inbound.get("max_agc_gain", self.values["b-agc-max-gain"])),
                "b-enable-denoise": "1" if inbound.get("enable_denoise", True) else "0",
                "b-denoise-strength": str(inbound.get("denoise_strength", self.values["b-denoise-strength"])),
                "b-clone-enabled": "1" if inbound.get("voice_clone_enabled", False) else "0",
                "b-clone-speaker": str(inbound.get("voice_clone_speaker_id", self.values["b-clone-speaker"]) or ""),
                "b-clone-speed": str(inbound.get("voice_clone_speed", self.values["b-clone-speed"])),
                "b-enabled": "1" if inbound.get("enabled", True) else "0",
                "b-input-enabled": "1" if inbound.get("capture_enabled", True) else "0",
                "b-output-enabled": "1" if inbound.get("playback_enabled", True) else "0",
                "b-monitor-enabled": "1" if inbound.get("monitor_playback_enabled", self.values["b-monitor-enabled"] == "1") else "0",
            }
        )

    def _apply_domain_pack_values(self, domain_id: str, overwrite_custom: bool = True) -> None:
        domain_id = domain_id if domain_id in DOMAIN_PACKS else "generic"
        pack = DOMAIN_PACKS[domain_id]
        self.domain_id = domain_id
        self.values["domain-preset"] = domain_id
        if overwrite_custom or not self.values["domain-context"].strip():
            self.values["domain-context"] = pack["context"]
        if overwrite_custom or not self.values["domain-hot-words"].strip():
            self.values["domain-hot-words"] = serialize_hot_words(pack["hot_words"])
        if overwrite_custom or not self.values["domain-correct-words"].strip():
            self.values["domain-correct-words"] = serialize_mapping(pack["correct_words"])
        if overwrite_custom or not self.values["domain-glossary"].strip():
            self.values["domain-glossary"] = serialize_mapping(pack["glossary"])

    def _sanitize_values(self) -> bool:
        changed = False

        if self.values.get("ui-language") not in {"zh", "en"}:
            self.values["ui-language"] = "zh"
            changed = True
        normalized_dns_servers = format_dns_csv(parse_dns_servers(self.values.get("network-dns-servers", "")))
        normalized_dns_hosts = format_dns_csv(parse_dns_hosts(self.values.get("network-dns-hosts", "")))
        if self.values.get("network-dns-servers", "") != normalized_dns_servers:
            self.values["network-dns-servers"] = normalized_dns_servers
            changed = True
        if self.values.get("network-dns-hosts", "") != normalized_dns_hosts:
            self.values["network-dns-hosts"] = normalized_dns_hosts
            changed = True
        if self.values["network-dns-servers"] and not self.values["network-dns-hosts"]:
            self.values["network-dns-hosts"] = "openspeech.bytedance.com"
            changed = True

        if self.values.get("voice-clone-language") not in {code for _, code in LANGUAGE_OPTIONS if code in {"zh", "en"}}:
            self.values["voice-clone-language"] = "zh"
            changed = True
        if self.values.get("voice-clone-record-device") not in self.catalog.microphones:
            self.values["voice-clone-record-device"] = self.values.get("a-input") or self.catalog.default_microphone_id()
            changed = True

        self.voice_clone_catalog = normalize_voice_clone_catalog(
            self.voice_clone_catalog,
            self.values.get("voice-clone-speaker-id", ""),
            self.values.get("a-clone-speaker", ""),
            self.values.get("b-clone-speaker", ""),
        )
        if not self.values.get("voice-clone-speaker-id"):
            self.values["voice-clone-speaker-id"] = PRIMARY_VOICE_CLONE_SPEAKER
            changed = True

        if self.values.get("scene") not in SCENE_TEMPLATES:
            self.values["scene"] = "discord_bidirectional"
            self.scene_id = "discord_bidirectional"
            changed = True

        if self.values.get("domain-preset") not in DOMAIN_PACKS:
            self._apply_domain_pack_values("rust", overwrite_custom=True)
            changed = True
        elif any(
            looks_garbled(self.values.get(key, ""))
            for key in ("domain-context", "domain-hot-words", "domain-correct-words", "domain-glossary")
        ):
            self._apply_domain_pack_values(self.values["domain-preset"], overwrite_custom=True)
            changed = True

        if self.values.get("audio-capture-backend") not in {"python", "native"}:
            self.values["audio-capture-backend"] = "python"
            changed = True
        if self.values.get("audio-native-fallback") not in {"0", "1"}:
            self.values["audio-native-fallback"] = "1"
            changed = True
        pre_roll_ms = max(0, min(safe_int(self.values.get("audio-pre-roll-ms"), 160), 600))
        if self.values.get("audio-pre-roll-ms") != str(pre_roll_ms):
            self.values["audio-pre-roll-ms"] = str(pre_roll_ms)
            changed = True
        for option_key, allowed, fallback in (
            ("audio-resampler-quality", {"linear", "sinc-lite"}, "sinc-lite"),
            ("audio-vad-mode", {"gate", "adaptive"}, "adaptive"),
            ("audio-playback-backend", {"python", "native"}, "python"),
        ):
            if self.values.get(option_key) not in allowed:
                self.values[option_key] = fallback
                changed = True
        for toggle_key in ("audio-noise-floor", "audio-adaptive-chunking", "audio-auto-profile"):
            if self.values.get(toggle_key) not in {"0", "1"}:
                self.values[toggle_key] = "1"
                changed = True
        if self.values.get("audio-device-auto-recover") not in {"0", "1"}:
            self.values["audio-device-auto-recover"] = "0"
            changed = True

        if self.values.get("audio-auto-profile") == "1":
            self._auto_tune_audio_profile()

        for alias in CHANNEL_ALIASES:
            scene_defaults = SCENE_TEMPLATES[self.scene_id][CHANNEL_SCENE_MAP[alias]]

            if self.values.get(f"{alias}-profile") not in PERFORMANCE_PRESETS:
                self.values[f"{alias}-profile"] = scene_defaults["performance_profile"]
                changed = True
            if self.values.get(f"{alias}-subtitle") not in {code for _, code in SUBTITLE_MODES}:
                self.values[f"{alias}-subtitle"] = scene_defaults["subtitle_mode"]
                changed = True
            for toggle_key, default in (
                (f"{alias}-enabled", "1" if alias in {"a", "b"} else "0"),
                (f"{alias}-input-enabled", "1"),
                (f"{alias}-output-enabled", "1"),
                (f"{alias}-monitor-enabled", "1" if alias == "a" else "0"),
                (f"{alias}-skip-silence", "1"),
                (f"{alias}-enable-agc", "1"),
                (f"{alias}-enable-denoise", "1"),
                (f"{alias}-clone-enabled", "0"),
            ):
                if self.values.get(toggle_key) not in {"0", "1"}:
                    self.values[toggle_key] = default
                    changed = True

            if self._validate_language_pair(alias):
                self.values[f"{alias}-source"] = scene_defaults["source_language"]
                self.values[f"{alias}-target"] = scene_defaults["target_language"]
                changed = True

            if not str(self.values.get(f"{alias}-startup-buffer", "")).strip():
                changed = True
            if not str(self.values.get(f"{alias}-noise-gate", "")).strip():
                changed = True
            if not str(self.values.get(f"{alias}-hold-ms", "")).strip():
                changed = True
            if not str(self.values.get(f"{alias}-agc-target", "")).strip():
                self.values[f"{alias}-agc-target"] = "-18"
                changed = True
            if not str(self.values.get(f"{alias}-agc-max-gain", "")).strip():
                self.values[f"{alias}-agc-max-gain"] = "6"
                changed = True
            if not str(self.values.get(f"{alias}-denoise-strength", "")).strip():
                self.values[f"{alias}-denoise-strength"] = "0.22"
                changed = True
            if not str(self.values.get(f"{alias}-clone-speed", "")).strip():
                self.values[f"{alias}-clone-speed"] = "1.0"
                changed = True
            if not str(self.values.get(f"{alias}-clone-speaker", "")).strip():
                self.values[f"{alias}-clone-speaker"] = self.values["voice-clone-speaker-id"]
                changed = True
            if self.values.get(f"{alias}-monitor-output") not in self.catalog.speakers:
                self.values[f"{alias}-monitor-output"] = self.catalog.default_speaker_id()
                changed = True

        if changed:
            self._apply_profile_defaults()
        self._update_clone_catalog_metadata(
            self.values["voice-clone-speaker-id"],
            status_label=str(self.voice_clone_snapshot.get("statusLabel", "") or ""),
            note=str(self.voice_clone_snapshot.get("message", "") or ""),
        )
        return changed


    def _auto_tune_audio_profile(self) -> None:
        native_available = self.native_audio_core.available and bool(self.native_audio_health.get("ok"))
        virtual_inputs = sum(1 for item in self.catalog.microphones.values() if item.virtual or item.loopback)
        if native_available:
            self.values["audio-resampler-quality"] = "sinc-lite"
            self.values["audio-vad-mode"] = "adaptive"
            self.values["audio-adaptive-chunking"] = "1"
        if virtual_inputs >= 1:
            self.values["audio-noise-floor"] = "1"
        if self.values.get("audio-capture-backend") == "native":
            for alias in CHANNEL_ALIASES:
                if self.values.get(f"{alias}-profile") == "studio":
                    self.values[f"{alias}-profile"] = "balanced"

    def refresh_devices(self, preserve_selection: bool = True) -> dict[str, Any]:
        previous = dict(self.values)
        self.catalog.refresh()
        self.native_audio_snapshot = self.native_audio_core.enumerate_devices() or {}
        self.native_audio_health = self.native_audio_core.health() if self.native_audio_core.available else {"ok": False}
        self.native_audio_health_checked_at = time.time()
        self.native_audio_degraded_reason = ""
        self.native_audio_affected_channels = []
        self.native_audio_recovered_routes = []
        if preserve_selection:
            for alias in CHANNEL_ALIASES:
                self.values[f"{alias}-input"] = self._resolve_selection(previous[f"{alias}-input"], self.catalog.microphones, f"{alias}-input")
                self.values[f"{alias}-output"] = self._resolve_selection(previous[f"{alias}-output"], self.catalog.speakers, f"{alias}-output")
                self.values[f"{alias}-monitor-output"] = self._resolve_selection(
                    previous.get(f"{alias}-monitor-output", ""),
                    self.catalog.speakers,
                    f"{alias}-monitor-output",
                )
            self.values["voice-clone-record-device"] = self._resolve_selection(
                previous.get("voice-clone-record-device", ""),
                self.catalog.microphones,
                "voice-clone-record-device",
            )
        else:
            for alias in CHANNEL_ALIASES:
                self.values[f"{alias}-input"] = self._fallback_input_device(alias)
                self.values[f"{alias}-output"] = self._fallback_output_device(alias)
                self.values[f"{alias}-monitor-output"] = self.catalog.default_speaker_id()
            self.values["voice-clone-record-device"] = self.catalog.default_microphone_id()
        return self.get_state()

    def _drain_native_audio_events(self) -> None:
        try:
            events = self.native_audio_core.drain_events()
        except Exception:
            return
        for event in events:
            event_name = event.get("event")
            if event_name == "devices_changed":
                snapshot = event.get("snapshot") if isinstance(event.get("snapshot"), dict) else {}
                self.native_audio_snapshot = snapshot
                previous_microphones = dict(self.catalog.microphones)
                previous_speakers = dict(self.catalog.speakers)
                try:
                    self.catalog.refresh()
                except Exception as exc:
                    self.native_audio_degraded_reason = f"Native devices changed, but Python device refresh failed: {exc}"
                previous_count = int(event.get("previous_device_count") or 0)
                device_count = int(event.get("device_count") or 0)
                self.native_audio_last_device_change = {
                    "timestamp": time.time(),
                    "previousDeviceCount": previous_count,
                    "deviceCount": device_count,
                }
                if self.values.get("audio-device-auto-recover") == "1":
                    self.native_audio_recovered_routes = self._recover_missing_channel_devices(previous_microphones, previous_speakers)
                else:
                    self.native_audio_recovered_routes = []
                self.native_audio_affected_channels = self._detect_channel_device_issues()
                if self.native_audio_affected_channels:
                    labels = ", ".join(item.get("label", item.get("alias", "")) for item in self.native_audio_affected_channels)
                    self.native_audio_degraded_reason = f"Audio devices changed ({previous_count} -> {device_count}); affected channels: {labels}."
                elif self._recovered_routes_need_restart():
                    labels = ", ".join(item.get("label", item.get("alias", "")) for item in self.native_audio_recovered_routes)
                    self.native_audio_degraded_reason = (
                        f"Audio devices changed ({previous_count} -> {device_count}); "
                        f"recovered routes for running channels: {labels}. Restart affected channels to apply."
                    )
                elif not self.native_audio_degraded_reason:
                    self.native_audio_degraded_reason = (
                        f"Native audio devices changed ({previous_count} -> {device_count}). "
                        "No active channel device bindings are missing."
                    )
            elif event_name == "error" and not event.get("channel"):
                self.native_audio_degraded_reason = str(event.get("message") or "Native audio core error")

    def _detect_channel_device_issues(self) -> list[dict[str, Any]]:
        affected: list[dict[str, Any]] = []
        device_error_prefix = "Audio device unavailable:"
        for alias in CHANNEL_ALIASES:
            channel_id = CHANNEL_MAP[alias]
            issues: list[dict[str, str]] = []
            if self.values.get(f"{alias}-enabled") == "1" and self.values.get(f"{alias}-input-enabled") == "1":
                input_id = self.values.get(f"{alias}-input", "")
                if input_id and input_id not in self.catalog.microphones:
                    issues.append({"kind": "input", "deviceId": input_id})
            if self.values.get(f"{alias}-enabled") == "1" and self.values.get(f"{alias}-output-enabled") == "1":
                output_id = self.values.get(f"{alias}-output", "")
                if output_id and output_id not in self.catalog.speakers:
                    issues.append({"kind": "output", "deviceId": output_id})
            if self.values.get(f"{alias}-enabled") == "1" and self.values.get(f"{alias}-monitor-enabled") == "1":
                monitor_id = self.values.get(f"{alias}-monitor-output", "")
                if monitor_id and monitor_id not in self.catalog.speakers:
                    issues.append({"kind": "monitor", "deviceId": monitor_id})

            if issues:
                message = f"{device_error_prefix} " + ", ".join(f"{item['kind']}={item['deviceId']}" for item in issues)
                self.channel_status[channel_id] = "Device Degraded"
                self.last_error[channel_id] = message
                affected.append(
                    {
                        "alias": alias,
                        "channelId": channel_id,
                        "label": CHANNEL_TITLE_MAP[alias],
                        "issues": issues,
                    }
                )
            elif self.last_error.get(channel_id, "").startswith(device_error_prefix):
                self.last_error[channel_id] = ""
                if channel_id in self.channels:
                    self.channel_status[channel_id] = "Running"
        return affected

    def _match_replacement_device(self, old_ref: object | None, mapping: dict[str, object]) -> str:
        old_name = str(getattr(old_ref, "name", "") or "").strip().casefold()
        if not old_name:
            return ""
        for device_id, ref in mapping.items():
            if str(getattr(ref, "name", "") or "").strip().casefold() == old_name:
                return device_id
        return ""

    def _device_recovery_candidate(
        self,
        alias: str,
        kind: str,
        old_device_id: str,
        previous_mapping: dict[str, object],
        current_mapping: dict[str, object],
    ) -> tuple[str, str]:
        replacement = self._match_replacement_device(previous_mapping.get(old_device_id), current_mapping)
        if replacement:
            return replacement, "name"
        if kind == "input":
            return self._fallback_input_device(alias), "fallback"
        if kind == "output":
            return self._fallback_output_device(alias), "fallback"
        return self.catalog.default_speaker_id(), "fallback"

    def _recover_missing_channel_devices(
        self,
        previous_microphones: dict[str, object],
        previous_speakers: dict[str, object],
    ) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        for alias in CHANNEL_ALIASES:
            if self.values.get(f"{alias}-enabled") != "1":
                continue
            recovery_targets = (
                ("input", f"{alias}-input", f"{alias}-input-enabled", previous_microphones, self.catalog.microphones),
                ("output", f"{alias}-output", f"{alias}-output-enabled", previous_speakers, self.catalog.speakers),
                ("monitor", f"{alias}-monitor-output", f"{alias}-monitor-enabled", previous_speakers, self.catalog.speakers),
            )
            for kind, value_key, enabled_key, previous_mapping, current_mapping in recovery_targets:
                old_device_id = self.values.get(value_key, "")
                if self.values.get(enabled_key) != "1" or not old_device_id or old_device_id in current_mapping:
                    continue
                new_device_id, strategy = self._device_recovery_candidate(alias, kind, old_device_id, previous_mapping, current_mapping)
                if not new_device_id or new_device_id not in current_mapping:
                    continue
                self.values[value_key] = new_device_id
                old_ref = previous_mapping.get(old_device_id)
                new_ref = current_mapping.get(new_device_id)
                recovered.append(
                    {
                        "alias": alias,
                        "channelId": CHANNEL_MAP[alias],
                        "label": CHANNEL_TITLE_MAP[alias],
                        "kind": kind,
                        "oldDeviceId": old_device_id,
                        "oldDeviceName": str(getattr(old_ref, "name", "") or old_device_id),
                        "newDeviceId": new_device_id,
                        "newDeviceName": str(getattr(new_ref, "name", "") or new_device_id),
                        "strategy": strategy,
                    }
                )

        running_channels = {channel_id for channel_id in self.channels}
        for channel_id in {item["channelId"] for item in recovered if item["channelId"] in running_channels}:
            kinds = ", ".join(item["kind"] for item in recovered if item["channelId"] == channel_id)
            self.channel_status[channel_id] = "Route Recovered"
            self.last_error[channel_id] = f"Audio route recovered: {kinds}. Restart this channel to apply the new device binding."
        return recovered

    def _recovered_routes_need_restart(self) -> bool:
        return any(item.get("channelId") in self.channels for item in self.native_audio_recovered_routes)

    def _first_key(self, mapping: dict[str, object]) -> str:
        return next(iter(mapping.keys()), "")

    def _fallback_input_device(self, alias: str) -> str:
        if alias == "a":
            return self.catalog.default_microphone_id()
        return self.catalog.default_loopback_id()

    def _fallback_output_device(self, alias: str) -> str:
        if alias == "a":
            for item in self.catalog.speaker_options():
                if item.virtual:
                    return item.device_id
        return self.catalog.default_speaker_id()

    def _resolve_selection(self, value: str, mapping: dict[str, object], key: str) -> str:
        value = str(value or "")
        if value and value in mapping:
            return value
        alias = key.split("-", 1)[0]
        if key.endswith("-input") and alias in CHANNEL_MAP:
            return self._fallback_input_device(alias)
        if key.endswith("-output") and alias in CHANNEL_MAP:
            return self._fallback_output_device(alias)
        if key.endswith("-monitor-output") and alias in CHANNEL_MAP:
            return self.catalog.default_speaker_id()
        if key == "voice-clone-record-device":
            return self.values.get("a-input") or self.catalog.default_microphone_id()
        return self._first_key(mapping)

    def _device_rank(self, item: Any, purpose: str) -> tuple[int, int, int, str]:
        lowered = item.name.lower()
        if purpose == "voice_in":
            return (1 if item.loopback else 0, 0 if item.virtual else 1, 0 if "microphone" in lowered or "mic" in lowered else 1, lowered)
        if purpose == "loopback_in":
            return (0 if item.loopback else 1, 0 if item.virtual else 1, lowered)
        if purpose == "voice_out":
            return (0 if item.virtual else 1, 0 if "head" in lowered else 1, lowered)
        return (0 if item.virtual else 1, lowered)

    def _device_hint(self, item: Any, purpose: str) -> str:
        tags: list[str] = []
        if item.virtual:
            tags.append("Virtual")
        if item.loopback:
            tags.append("Loopback")
        tags.append(f"{max(1, int(item.channels or 1))}ch")

        if purpose == "voice_in":
            role = "Mic capture"
        elif purpose == "loopback_in":
            role = "Loopback capture"
        else:
            role = "Playback output"
        return f"{role} / {' / '.join(tags)}"

    def _device_options(self, mapping: dict[str, object], purpose: str) -> list[dict[str, str]]:
        options: list[dict[str, str]] = []
        ranked = sorted(mapping.values(), key=lambda item: self._device_rank(item, purpose))
        for item in ranked:
            label = " ".join(item.name.split()).strip() or item.device_id
            if item.loopback:
                label = f"{label} / Loopback"
            if item.virtual and "Virtual" not in label:
                label = f"{label} / Virtual"
            options.append({"value": item.device_id, "label": label, "hint": self._device_hint(item, purpose)})
        return options

    def _language_options(self) -> list[dict[str, str]]:
        return [{"value": code, "label": label, "hint": code} for label, code in LANGUAGE_OPTIONS if code in {"zh", "en"}]

    def _performance_options(self) -> list[dict[str, str]]:
        options: list[dict[str, str]] = []
        for preset in PERFORMANCE_PRESETS.values():
            options.append(
                {
                    "value": preset.key,
                    "label": preset.label,
                    "hint": f"{preset.chunk_ms}ms chunk / {preset.jitter_buffer_ms}ms jitter / {preset.target_audio_rate // 1000}kHz",
                }
            )
        return options

    def _subtitle_options(self) -> list[dict[str, str]]:
        return [{"value": code, "label": label, "hint": code} for label, code in SUBTITLE_MODES]

    def _domain_options(self) -> list[dict[str, str]]:
        return [{"value": key, "label": pack["label"], "hint": pack["description"]} for key, pack in DOMAIN_PACKS.items()]

    def _voice_clone_options(self) -> list[dict[str, str]]:
        options = [{"value": "", "label": "Not Selected", "hint": "Use AST voice output"}]
        for item in self.voice_clone_catalog:
            hint_bits = [item.get("speaker_id", "")]
            if item.get("status_label"):
                hint_bits.append(item["status_label"])
            elif item.get("note"):
                hint_bits.append(item["note"])
            options.append(
                {
                    "value": item["speaker_id"],
                    "label": item.get("label", item["speaker_id"]),
                    "hint": " / ".join(bit for bit in hint_bits if bit),
                }
            )
        return options

    def _ast_voice_options(self) -> list[dict[str, str]]:
        options = [
            {
                "value": DEFAULT_AST_VOICE_OPTION["speaker_id"],
                "label": DEFAULT_AST_VOICE_OPTION["label"],
                "hint": DEFAULT_AST_VOICE_OPTION["note"],
            }
        ]
        for item in AST_PRESET_VOICE_CATALOG:
            options.append(
                {
                    "value": item["speaker_id"],
                    "label": item["label"],
                    "hint": f"{item['speaker_id']} / {item['note']}",
                }
            )
        return options

    def _option_groups(self) -> dict[str, list[dict[str, str]]]:
        return {
            "ui-language": list(UI_LANGUAGE_OPTIONS),
            "scene": [{"value": key, "label": scene["label"], "hint": scene["description"]} for key, scene in SCENE_TEMPLATES.items()],
            "domain-preset": self._domain_options(),
            "a-input": self._device_options(self.catalog.microphones, "voice_in"),
            "a-output": self._device_options(self.catalog.speakers, "voice_out"),
            "a-monitor-output": self._device_options(self.catalog.speakers, "voice_out"),
            "b-input": self._device_options(self.catalog.microphones, "loopback_in"),
            "b-output": self._device_options(self.catalog.speakers, "voice_out"),
            "b-monitor-output": self._device_options(self.catalog.speakers, "voice_out"),
            "voice-clone-record-device": self._device_options(self.catalog.microphones, "voice_in"),
            "a-source": self._language_options(),
            "a-target": self._language_options(),
            "a-speaker": self._ast_voice_options(),
            "b-source": self._language_options(),
            "b-target": self._language_options(),
            "b-speaker": self._ast_voice_options(),
            "a-profile": self._performance_options(),
            "b-profile": self._performance_options(),
            "a-subtitle": self._subtitle_options(),
            "b-subtitle": self._subtitle_options(),
            "voice-clone-speaker-id": self._voice_clone_options(),
            "a-clone-speaker": self._voice_clone_options(),
            "b-clone-speaker": self._voice_clone_options(),
            "voice-clone-language": [{"value": code, "label": label, "hint": code} for label, code in LANGUAGE_OPTIONS if code in {"zh", "en"}],
        }

    def apply_scene(self, scene_id: str) -> dict[str, Any]:
        scene_id = scene_id if scene_id in SCENE_TEMPLATES else "discord_bidirectional"
        scene = SCENE_TEMPLATES[scene_id]
        self.scene_id = scene_id
        self.values["scene"] = scene_id

        for alias in CHANNEL_ALIASES:
            config = scene[CHANNEL_SCENE_MAP[alias]]
            self.values[f"{alias}-source"] = config["source_language"]
            self.values[f"{alias}-target"] = config["target_language"]
            self.values[f"{alias}-profile"] = config["performance_profile"]
            self.values[f"{alias}-subtitle"] = config["subtitle_mode"]

        self._apply_profile_defaults()
        self.save_config()
        return self.get_state()

    def apply_domain_pack(self, domain_id: str) -> dict[str, Any]:
        self._apply_domain_pack_values(domain_id, overwrite_custom=True)
        self._rebuild_correction_maps()
        self.save_config()
        return self.get_state()

    def update_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = payload.get("values", {})
        previous_global_clone = self.values.get("voice-clone-speaker-id", "")
        for key in self.values:
            if key in values:
                self.values[key] = str(values[key] or "")

        credentials = payload.get("credentials", {})
        if credentials:
            app_id = credentials.get("appId")
            if app_id is not None and not self._looks_redacted(app_id):
                self.credentials["appId"] = str(app_id or "")

            access_token = credentials.get("accessToken")
            if access_token is not None and not self._looks_redacted(access_token):
                self.credentials["accessToken"] = str(access_token or "")

            secret_key = credentials.get("secretKey")
            if secret_key is not None and not self._looks_redacted(secret_key):
                self.credentials["secretKey"] = str(secret_key or "")

            resource_id = str(credentials.get("resourceId", self.credentials["resourceId"]) or "").strip()
            self.credentials["resourceId"] = resource_id or DEFAULT_RESOURCE_ID

        self.scene_id = self.values.get("scene", self.scene_id)
        self.domain_id = self.values.get("domain-preset", self.domain_id)
        self.voice_clone_catalog = normalize_voice_clone_catalog(
            self.voice_clone_catalog,
            self.values.get("voice-clone-speaker-id", ""),
            self.values.get("a-clone-speaker", ""),
            self.values.get("b-clone-speaker", ""),
        )
        current_global_clone = self.values.get("voice-clone-speaker-id", "")
        if current_global_clone != previous_global_clone:
            for key in ("a-clone-speaker", "b-clone-speaker"):
                if not self.values.get(key) or self.values.get(key) == previous_global_clone:
                    self.values[key] = current_global_clone
        self._rebuild_correction_maps()
        return self.get_state()

    def _apply_profile_defaults(self) -> None:
        for alias in CHANNEL_ALIASES:
            profile = PERFORMANCE_PRESETS.get(self.values[f"{alias}-profile"], PERFORMANCE_PRESETS["balanced"])
            startup_default = min(profile.jitter_buffer_ms, 16 if profile.key == "turbo" else 36 if profile.key == "balanced" else 96)
            gate_default = -46 if profile.key == "turbo" else -50 if profile.key == "balanced" else -56
            hold_default = 140 if profile.key == "turbo" else 220 if profile.key == "balanced" else 320
            self.values[f"{alias}-startup-buffer"] = str(startup_default)
            self.values[f"{alias}-noise-gate"] = str(gate_default)
            self.values[f"{alias}-hold-ms"] = str(hold_default)

    def save_config(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload is not None:
            self.update_state(payload)

        self._rebuild_correction_maps()
        self.updater.set_manifest_url(self.values["update-manifest-url"])
        self.update_snapshot["current"] = dict(self.updater.current)
        self.voice_clone_snapshot["speakerId"] = self.values["voice-clone-speaker-id"]
        self._update_clone_catalog_metadata(
            self.voice_clone_snapshot.get("speakerId", ""),
            status_label=str(self.voice_clone_snapshot.get("statusLabel", "") or ""),
            note=str(self.voice_clone_snapshot.get("message", "") or ""),
        )
        data = {
            "app_key": self.credentials["appId"],
            "access_key": self.credentials["accessToken"],
            "secret_key": self.credentials["secretKey"],
            "resource_id": self.credentials["resourceId"] or DEFAULT_RESOURCE_ID,
            "selected_scene": SCENE_TEMPLATES.get(self.scene_id, SCENE_TEMPLATES["discord_bidirectional"])["label"],
            "ui_language": self.values["ui-language"],
            "updater": {
                "manifest_url": self.values["update-manifest-url"],
            },
            "voice_clone": {
                "api_resource_id": VOICE_CLONE_RESOURCE_ID,
                "billing_resource_id": VOICE_CLONE_BILLING_RESOURCE_ID,
                "speaker_id": self.values["voice-clone-speaker-id"],
                "sample_path": self.values["voice-clone-sample-path"],
                "record_device": self.values["voice-clone-record-device"],
                "reference_text": self.values["voice-clone-reference-text"],
                "demo_text": self.values["voice-clone-demo-text"],
                "language": self.values["voice-clone-language"],
                "status_code": self.voice_clone_snapshot.get("statusCode"),
                "status_label": self.voice_clone_snapshot.get("statusLabel", ""),
                "message": self.voice_clone_snapshot.get("message", ""),
                "demo_audio": self.voice_clone_snapshot.get("demoAudio", ""),
                "version": self.voice_clone_snapshot.get("version", ""),
                "updated_at": self.voice_clone_snapshot.get("updatedAt", ""),
                "speaker_catalog": self._clone_catalog_for_config(),
            },
            "domain": {
                "preset": self.values["domain-preset"],
                "context": self.values["domain-context"],
                "hot_words": self.values["domain-hot-words"],
                "correct_words": self.values["domain-correct-words"],
                "glossary": self.values["domain-glossary"],
            },
            "network": {
                "dns_servers": list(parse_dns_servers(self.values["network-dns-servers"])),
                "dns_hosts": list(parse_dns_hosts(self.values["network-dns-hosts"])),
            },
            "audio_core": {
                "capture_backend": self.values["audio-capture-backend"],
                "native_capture_fallback": self.values["audio-native-fallback"] == "1",
                "pre_roll_ms": max(0, min(safe_int(self.values["audio-pre-roll-ms"], 160), 600)),
                "resampler_quality": self.values["audio-resampler-quality"],
                "vad_mode": self.values["audio-vad-mode"],
                "enable_noise_floor": self.values["audio-noise-floor"] == "1",
                "adaptive_chunking": self.values["audio-adaptive-chunking"] == "1",
                "playback_backend": self.values["audio-playback-backend"],
                "auto_profile": self.values["audio-auto-profile"] == "1",
                "device_auto_recover": self.values["audio-device-auto-recover"] == "1",
            },
            "channels": {
                "outbound": self._channel_config("a"),
                "inbound": self._channel_config("b"),
            },
        }
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.get_state()

    def _channel_config(self, alias: str) -> dict[str, Any]:
        profile = PERFORMANCE_PRESETS[self.values[f"{alias}-profile"]]
        startup_buffer = max(16, safe_int(self.values[f"{alias}-startup-buffer"], min(profile.jitter_buffer_ms, 32)))
        clone_enabled = self.values[f"{alias}-clone-enabled"] == "1"
        return {
            "enabled": self.values[f"{alias}-enabled"] == "1",
            "capture_enabled": self.values[f"{alias}-input-enabled"] == "1",
            "playback_enabled": self.values[f"{alias}-output-enabled"] == "1",
            "monitor_playback_enabled": self.values[f"{alias}-monitor-enabled"] == "1",
            "capture_device_id": self.values[f"{alias}-input"],
            "playback_device_id": self.values[f"{alias}-output"],
            "monitor_playback_device_id": self.values[f"{alias}-monitor-output"],
            "source_language": self.values[f"{alias}-source"],
            "target_language": self.values[f"{alias}-target"],
            "speaker_id": self.values[f"{alias}-speaker"].strip(),
            "performance_profile": profile.key,
            "chunk_ms": profile.chunk_ms,
            "jitter_buffer_ms": profile.jitter_buffer_ms,
            "startup_buffer_ms": startup_buffer,
            "target_audio_rate": profile.target_audio_rate,
            "input_gain": profile.input_gain,
            "subtitle_mode": self.values[f"{alias}-subtitle"],
            "skip_silence": self.values[f"{alias}-skip-silence"] == "1",
            "noise_gate_db": safe_float(self.values[f"{alias}-noise-gate"], -52.0),
            "silence_hold_ms": max(0, safe_int(self.values[f"{alias}-hold-ms"], 260)),
            "enable_agc": self.values[f"{alias}-enable-agc"] == "1",
            "agc_target_dbfs": safe_float(self.values[f"{alias}-agc-target"], -18.0),
            "max_agc_gain": safe_float(self.values[f"{alias}-agc-max-gain"], 6.0),
            "enable_denoise": self.values[f"{alias}-enable-denoise"] == "1",
            "denoise_strength": safe_float(self.values[f"{alias}-denoise-strength"], 0.22),
            "voice_clone_enabled": clone_enabled,
            "voice_clone_speaker_id": self.values[f"{alias}-clone-speaker"].strip(),
            "voice_clone_speed": safe_float(self.values[f"{alias}-clone-speed"], 1.0),
        }

    def _build_channel_settings(self, alias: str) -> ChannelSettings:
        channel_id = CHANNEL_MAP[alias]
        profile = PERFORMANCE_PRESETS[self.values[f"{alias}-profile"]]
        channel_config = self._channel_config(alias)
        clone_speaker = channel_config["voice_clone_speaker_id"].strip()
        local_tts_disabled = channel_id in self._local_tts_disabled_channels
        use_local_tts = bool(
            channel_config["voice_clone_enabled"]
            and clone_speaker
            and self._supports_local_clone_tts(channel_config["target_language"])
            and not local_tts_disabled
        )
        return ChannelSettings(
            channel_id=channel_id,
            display_name=CHANNEL_TITLE_MAP[alias],
            capture_device_id=channel_config["capture_device_id"],
            playback_device_id=channel_config["playback_device_id"],
            source_language=channel_config["source_language"],
            target_language=channel_config["target_language"],
            speaker_id="" if use_local_tts else channel_config["speaker_id"].strip(),
            mode="s2t" if use_local_tts else "s2s",
            performance_profile=profile.key,
            chunk_ms=profile.chunk_ms,
            jitter_buffer_ms=profile.jitter_buffer_ms,
            startup_buffer_ms=channel_config["startup_buffer_ms"],
            target_audio_rate=profile.target_audio_rate,
            input_gain=profile.input_gain,
            subtitle_mode=channel_config["subtitle_mode"],
            max_queue_chunks=profile.max_queue_chunks,
            skip_silence=channel_config["skip_silence"],
            noise_gate_db=channel_config["noise_gate_db"],
            silence_hold_ms=channel_config["silence_hold_ms"],
            context_prompt=self.values["domain-context"].strip(),
            hot_words=parse_hot_words(self.values["domain-hot-words"]),
            correct_words=parse_mapping_text(self.values["domain-correct-words"]),
            glossary=parse_mapping_text(self.values["domain-glossary"]),
            enable_agc=channel_config["enable_agc"],
            agc_target_dbfs=channel_config["agc_target_dbfs"],
            max_agc_gain=max(1.0, channel_config["max_agc_gain"]),
            enable_denoise=channel_config["enable_denoise"],
            denoise_strength=max(0.0, min(channel_config["denoise_strength"], 0.95)),
            capture_enabled=channel_config["capture_enabled"],
            playback_enabled=channel_config["playback_enabled"],
            monitor_playback_enabled=channel_config["monitor_playback_enabled"],
            monitor_playback_device_id=channel_config["monitor_playback_device_id"],
            use_local_tts=use_local_tts,
            local_tts_voice=clone_speaker,
            local_tts_cluster="volcano_icl",
            local_tts_speed=max(0.6, min(channel_config["voice_clone_speed"], 1.8)),
            capture_backend=self.values["audio-capture-backend"],
            native_capture_fallback=self.values["audio-native-fallback"] == "1",
            pre_roll_ms=max(0, min(safe_int(self.values["audio-pre-roll-ms"], 160), 600)),
            resampler_quality=self.values["audio-resampler-quality"],
            vad_mode=self.values["audio-vad-mode"],
            enable_noise_floor=self.values["audio-noise-floor"] == "1",
            adaptive_chunking=self.values["audio-adaptive-chunking"] == "1",
            playback_backend=self.values["audio-playback-backend"],
        )

    def _validate_language_pair(self, alias: str) -> str | None:
        source = self.values[f"{alias}-source"]
        target = self.values[f"{alias}-target"]
        channel_name = CHANNEL_TITLE_MAP[alias]

        if source == target and source != "zhen":
            return f"{channel_name} source and target languages must be different."
        if source == "zhen" or target == "zhen":
            if not (source == "zhen" and target == "zhen"):
                return f"{channel_name} mixed Chinese-English mode requires both source and target to be zhen."
            return None
        if "zh" not in {source, target} and "en" not in {source, target}:
            return f"{channel_name} must include Chinese or English as one side of the translation pair."
        return None

    def _validate_corpus(self) -> str | None:
        hot_words = parse_hot_words(self.values["domain-hot-words"])
        glossary = parse_mapping_text(self.values["domain-glossary"])
        total_items = len(hot_words) + len(glossary)
        if total_items > CORPUS_LIMIT:
            return f"Hot words and glossary combined exceed the AST limit of {CORPUS_LIMIT} items."
        return None

    def _rebuild_correction_maps(self) -> None:
        replace_map = parse_mapping_text(self.values["domain-correct-words"])
        self.correction_maps = {channel_id: dict(replace_map) for channel_id in CHANNEL_IDS}

    def start_channels(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload is not None:
            self.update_state(payload)
            self.save_config()

        if not self.credentials["appId"].strip() or not self.credentials["accessToken"].strip():
            return {"ok": False, "error": "App ID and Access Token are required."}

        active_aliases = [
            alias
            for alias in CHANNEL_ALIASES
            if self.values[f"{alias}-enabled"] == "1" and self.values[f"{alias}-input-enabled"] == "1"
        ]
        if not active_aliases:
            return {"ok": False, "error": "Enable at least one channel with input capture before starting."}

        for alias in active_aliases:
            if self.values[f"{alias}-input"] not in self.catalog.microphones:
                return {"ok": False, "error": f"Invalid input device for {alias.upper()}."}
            if self.values[f"{alias}-output-enabled"] == "1" and self.values[f"{alias}-output"] not in self.catalog.speakers:
                return {"ok": False, "error": f"Invalid output device for {alias.upper()}."}
            if self.values[f"{alias}-monitor-enabled"] == "1" and self.values[f"{alias}-monitor-output"] not in self.catalog.speakers:
                return {"ok": False, "error": f"Invalid monitor output device for {alias.upper()}."}
            error = self._validate_language_pair(alias)
            if error:
                return {"ok": False, "error": error}
            if self.values[f"{alias}-clone-enabled"] == "1" and not self.values[f"{alias}-clone-speaker"].strip():
                return {"ok": False, "error": f"{CHANNEL_TITLE_MAP[alias]} requires a clone speaker ID when cloned voice is enabled."}
        corpus_error = self._validate_corpus()
        if corpus_error:
            return {"ok": False, "error": corpus_error}

        self.stop_channels()
        self._rebuild_correction_maps()
        self._local_tts_disabled_channels.clear()

        credentials = Credentials(
            app_key=self.credentials["appId"].strip(),
            access_key=self.credentials["accessToken"].strip(),
            resource_id=self.credentials["resourceId"].strip() or DEFAULT_RESOURCE_ID,
            dns_servers=parse_dns_servers(self.values["network-dns-servers"]),
            dns_hosts=parse_dns_hosts(self.values["network-dns-hosts"]),
        )
        self._runtime_credentials = credentials
        self.channels = {}
        self.transcripts = {channel_id: [] for channel_id in CHANNEL_IDS}
        self.partials = {channel_id: {"source": "", "target": ""} for channel_id in CHANNEL_IDS}
        self.stats_by_channel = {channel_id: {} for channel_id in CHANNEL_IDS}
        self.channel_status = {channel_id: "Ready" for channel_id in CHANNEL_IDS}
        self.last_error = {channel_id: "" for channel_id in CHANNEL_IDS}
        for alias in CHANNEL_ALIASES:
            channel_id = CHANNEL_MAP[alias]
            if self.values[f"{alias}-enabled"] != "1":
                self.channel_status[channel_id] = "Disabled"
                continue
            if self.values[f"{alias}-input-enabled"] != "1":
                self.channel_status[channel_id] = "Input Off"
                continue
            self.channel_status[channel_id] = "Starting"
            self.channels[channel_id] = TranslationChannel(self.catalog, self._build_channel_settings(alias), credentials, self.event_queue.put)
        for channel in self.channels.values():
            channel.start()
        return {"ok": True, "state": self.get_state()}

    def stop_channels(self) -> dict[str, Any]:
        for channel in self.channels.values():
            channel.stop()
        for channel in self.channels.values():
            channel.join(timeout=2.0)
        self.channels = {}
        self.channel_status = {channel_id: "Ready" for channel_id in CHANNEL_IDS}
        self.last_error = {channel_id: "" for channel_id in CHANNEL_IDS}
        self._runtime_credentials = None
        return {"ok": True, "state": self.get_state()}

    def export_session(self) -> dict[str, Any]:
        self._drain_native_audio_events()
        self._drain_events()
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_path = OUTPUT_DIR / f"diagnostic-session-{timestamp}.json"
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "schema": "nova-diagnostic-session-v2",
            "version": dict(self.updater.current),
            "scene": self.scene_id,
            "domain_preset": self.values["domain-preset"],
            "credentials": self._redacted_credentials(),
            "values": self._redacted_values(),
            "network": {
                "dns_servers": list(parse_dns_servers(self.values["network-dns-servers"])),
                "dns_hosts": list(parse_dns_hosts(self.values["network-dns-hosts"])),
            },
            "devices": self._device_diagnostics(),
            "nativeAudioCore": self._native_audio_state(),
            "voiceClone": self._voice_clone_state(),
            "updater": self._updater_state(),
            "runtime": self._runtime_snapshot(),
            "logs": self._recent_log_diagnostics(),
            "channels": {
                "outbound": {
                    "settings": asdict(self._build_channel_settings("a")),
                    "stats": self.stats_by_channel["outbound"],
                    "transcript": self.transcripts["outbound"],
                },
                "inbound": {
                    "settings": asdict(self._build_channel_settings("b")),
                    "stats": self.stats_by_channel["inbound"],
                    "transcript": self.transcripts["inbound"],
                },
            },
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "path": str(output_path), "name": output_path.name}

    def _redact_secret(self, value: str) -> str:
        value = str(value or "")
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return f"{value[:3]}***{value[-3:]}"

    def _looks_redacted(self, value: Any) -> bool:
        value = str(value or "")
        if not value:
            return False
        if value == "***":
            return True
        if len(value) <= 8:
            return False
        masked = value[3:-3]
        return "*" not in value[:3] and "*" not in value[-3:] and set(masked) == {"*"} and len(masked) >= 3

    def _redacted_credentials(self) -> dict[str, str]:
        return {
            "appId": self._redact_secret(self.credentials.get("appId", "")),
            "accessToken": self._redact_secret(self.credentials.get("accessToken", "")),
            "secretKey": self._redact_secret(self.credentials.get("secretKey", "")),
            "resourceId": self.credentials.get("resourceId", DEFAULT_RESOURCE_ID) or DEFAULT_RESOURCE_ID,
        }

    def _redacted_values(self) -> dict[str, str]:
        redacted = dict(self.values)
        for key in ("voice-clone-sample-path",):
            if redacted.get(key):
                redacted[key] = str(Path(redacted[key]).name)
        return redacted

    def _device_diagnostics(self) -> dict[str, Any]:
        return {
            "inputs": [asdict(item) for item in self.catalog.microphone_options()],
            "outputs": [asdict(item) for item in self.catalog.speaker_options()],
        }

    def _recent_log_diagnostics(self, limit: int = 5, tail_bytes: int = 8192) -> list[dict[str, Any]]:
        log_dir = OUTPUT_DIR / "logs"
        if not log_dir.exists():
            return []
        logs: list[dict[str, Any]] = []
        for path in sorted(log_dir.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            try:
                raw = path.read_bytes()[-tail_bytes:]
                text = raw.decode("utf-8", errors="replace")
                logs.append(
                    {
                        "name": path.name,
                        "size": path.stat().st_size,
                        "modified": path.stat().st_mtime,
                        "tail": text,
                    }
                )
            except Exception as exc:
                logs.append({"name": path.name, "error": str(exc)})
        return logs

    def get_state(self) -> dict[str, Any]:
        self._drain_native_audio_events()
        self._drain_events()
        domain = DOMAIN_PACKS.get(self.values["domain-preset"], DOMAIN_PACKS["generic"])
        return {
            "values": dict(self.values),
            "credentials": dict(self.credentials),
            "network": {
                "dnsServers": list(parse_dns_servers(self.values["network-dns-servers"])),
                "dnsHosts": list(parse_dns_hosts(self.values["network-dns-hosts"])),
            },
            "version": dict(self.updater.current),
            "optionGroups": self._option_groups(),
            "domain": {
                "id": self.values["domain-preset"],
                "label": domain["label"],
                "description": domain["description"],
            },
            "devices": {
                "inputs": len(self.catalog.microphones),
                "outputs": len(self.catalog.speakers),
                "virtualInputs": sum(1 for item in self.catalog.microphones.values() if item.virtual),
                "virtualOutputs": sum(1 for item in self.catalog.speakers.values() if item.virtual),
            },
            "nativeAudioCore": self._native_audio_state(),
            "voiceClone": self._voice_clone_state(),
            "updater": self._updater_state(),
            "channels": {
                "a": {
                    "title": CHANNEL_TITLE_MAP["a"],
                    "copy": CHANNEL_COPY_MAP["a"],
                    "paneTitle": CHANNEL_PANE_TITLE_MAP["a"],
                },
                "b": {
                    "title": CHANNEL_TITLE_MAP["b"],
                    "copy": CHANNEL_COPY_MAP["b"],
                    "paneTitle": CHANNEL_PANE_TITLE_MAP["b"],
                },
            },
            "transcripts": {
                "a": self.transcripts["outbound"][-80:],
                "b": self.transcripts["inbound"][-80:],
            },
            "partials": {
                "a": dict(self.partials["outbound"]),
                "b": dict(self.partials["inbound"]),
            },
            "runtime": self._runtime_snapshot(),
        }

    def poll_state(self) -> dict[str, Any]:
        self._drain_native_audio_events()
        self._drain_events()
        return {
            "nativeAudioCore": self._native_audio_state(),
            "voiceClone": self._voice_clone_state(),
            "updater": self._updater_state(),
            "transcripts": {
                "a": self.transcripts["outbound"][-24:],
                "b": self.transcripts["inbound"][-24:],
            },
            "partials": {
                "a": dict(self.partials["outbound"]),
                "b": dict(self.partials["inbound"]),
            },
            "runtime": self._runtime_snapshot(),
        }

    def _native_audio_state(self) -> dict[str, Any]:
        native_devices = self.native_audio_snapshot.get("devices", []) if isinstance(self.native_audio_snapshot, dict) else []
        capture_backend = self.values.get("audio-capture-backend", "python")
        if self.native_audio_core.available and time.time() - self.native_audio_health_checked_at > 15.0:
            self.native_audio_health = self.native_audio_core.health()
            self.native_audio_health_checked_at = time.time()
        health = self.native_audio_health if self.native_audio_core.available else {"ok": False}
        runtime = "native" if capture_backend == "native" and health.get("ok") else "python"
        degraded_reason = self.native_audio_degraded_reason
        if capture_backend == "native" and not health.get("ok"):
            degraded_reason = degraded_reason or str(health.get("error") or "Native audio core is not healthy.")
        return {
            "available": self.native_audio_core.available,
            "enumerated": bool(self.native_audio_snapshot),
            "runtime": runtime,
            "degraded": bool(degraded_reason),
            "degradedReason": degraded_reason,
            "affectedChannels": self.native_audio_affected_channels,
            "captureBackend": capture_backend,
            "fallbackEnabled": self.values.get("audio-native-fallback", "1") == "1",
            "preRollMs": max(0, min(safe_int(self.values.get("audio-pre-roll-ms"), 160), 600)),
            "resamplerQuality": self.values.get("audio-resampler-quality", "sinc-lite"),
            "vadMode": self.values.get("audio-vad-mode", "adaptive"),
            "noiseFloorEnabled": self.values.get("audio-noise-floor", "1") == "1",
            "adaptiveChunking": self.values.get("audio-adaptive-chunking", "1") == "1",
            "playbackBackend": self.values.get("audio-playback-backend", "python"),
            "autoProfile": self.values.get("audio-auto-profile", "1") == "1",
            "deviceAutoRecover": self.values.get("audio-device-auto-recover", "0") == "1",
            "recoveredRoutes": self.native_audio_recovered_routes,
            "health": health,
            "binaryPath": str(self.native_audio_core.binary_path),
            "deviceCount": len(native_devices),
            "lastDeviceChange": self.native_audio_last_device_change,
            "lastSnapshot": self.native_audio_snapshot,
        }

    def _voice_clone_state(self) -> dict[str, Any]:
        active_channels = self._local_clone_channels()
        fallback_channels = self._clone_fallback_channels()
        record_state = self._voice_clone_recording_state()
        return {
            **self.voice_clone_snapshot,
            "apiResourceId": VOICE_CLONE_RESOURCE_ID,
            "billingResourceId": VOICE_CLONE_BILLING_RESOURCE_ID,
            "samplePath": self.values["voice-clone-sample-path"],
            "recordDeviceId": self.values["voice-clone-record-device"],
            "referenceText": self.values["voice-clone-reference-text"],
            "demoText": self.values["voice-clone-demo-text"],
            "language": self.values["voice-clone-language"],
            "activeChannels": active_channels,
            "fallbackChannels": fallback_channels,
            "runtimeLanguages": sorted(LOCAL_CLONE_TTS_LANGUAGES),
            "catalog": self._clone_catalog_for_config(),
            **record_state,
        }

    def _voice_clone_recording_state(self) -> dict[str, Any]:
        with self._voice_clone_record_lock:
            recording = bool(self._voice_clone_record_thread and self._voice_clone_record_thread.is_alive())
            return {
                "recording": recording,
                "recordingDeviceId": self._voice_clone_record_device_id,
                "recordingDeviceName": self._voice_clone_record_device_name,
                "recordingStartedAt": self._voice_clone_record_started_at,
                "recordingDurationSec": round(self._voice_clone_record_duration_sec, 1),
                "recordingLevelDb": round(self._voice_clone_record_level_db, 1),
            }

    def _updater_state(self) -> dict[str, Any]:
        return {
            "current": dict(self.updater.current),
            "manifestUrl": self.values["update-manifest-url"],
            "lastCheck": self.update_snapshot.get("lastCheck"),
            "result": self.update_snapshot.get("result"),
            "download": self.update_snapshot.get("download"),
        }

    def _clone_catalog_for_config(self) -> list[dict[str, str]]:
        return [
            {
                "speaker_id": item.get("speaker_id", ""),
                "label": item.get("label", ""),
                "note": item.get("note", ""),
                "status_label": item.get("status_label", ""),
            }
            for item in self.voice_clone_catalog
            if item.get("speaker_id")
        ]

    def _update_clone_catalog_metadata(
        self,
        speaker_id: str,
        status_label: str = "",
        note: str = "",
    ) -> None:
        target = str(speaker_id or "").strip()
        if not target:
            return
        updated = False
        for item in self.voice_clone_catalog:
            if item.get("speaker_id") != target:
                continue
            if status_label:
                item["status_label"] = status_label
            if note:
                item["note"] = note
            updated = True
            break
        if not updated and looks_like_console_speaker_id(target):
            self.voice_clone_catalog.append(
                {
                    "speaker_id": target,
                    "label": f"Clone Slot {len(self.voice_clone_catalog) + 1:02d}",
                    "note": note,
                    "status_label": status_label,
                }
            )

    def _supports_local_clone_tts(self, target_language: str) -> bool:
        return str(target_language or "").strip() in LOCAL_CLONE_TTS_LANGUAGES

    def _local_clone_channels(self) -> list[str]:
        active_channels: list[str] = []
        for alias in CHANNEL_ALIASES:
            if self.values[f"{alias}-enabled"] != "1" or self.values[f"{alias}-output-enabled"] != "1":
                continue
            if self.values[f"{alias}-clone-enabled"] != "1":
                continue
            clone_speaker = self.values[f"{alias}-clone-speaker"].strip()
            if (
                clone_speaker
                and self._supports_local_clone_tts(self.values[f"{alias}-target"])
                and CHANNEL_MAP[alias] not in self._local_tts_disabled_channels
            ):
                active_channels.append(CHANNEL_TITLE_MAP[alias])
        return active_channels

    def _clone_fallback_channels(self) -> list[str]:
        fallback_channels: list[str] = []
        for alias in CHANNEL_ALIASES:
            if self.values[f"{alias}-enabled"] != "1" or self.values[f"{alias}-output-enabled"] != "1":
                continue
            if self.values[f"{alias}-clone-enabled"] != "1":
                continue
            clone_speaker = self.values[f"{alias}-clone-speaker"].strip()
            if clone_speaker and (
                not self._supports_local_clone_tts(self.values[f"{alias}-target"])
                or CHANNEL_MAP[alias] in self._local_tts_disabled_channels
            ):
                fallback_channels.append(CHANNEL_TITLE_MAP[alias])
        return fallback_channels

    def _clone_manager(self) -> VoiceCloneManager:
        return VoiceCloneManager(
            app_id=self.credentials["appId"].strip(),
            access_token=self.credentials["accessToken"].strip(),
            dns_servers=parse_dns_servers(self.values["network-dns-servers"]),
            dns_hosts=parse_dns_hosts(self.values["network-dns-hosts"]),
        )

    def _update_voice_clone_snapshot(self, payload: dict[str, Any], message: str = "") -> None:
        status_code = payload.get("status")
        status_label = VOICE_CLONE_STATUS_LABELS.get(status_code, "Uploaded" if status_code is None else f"Status {status_code}")
        speaker_id = str(payload.get("speaker_id", self.values["voice-clone-speaker-id"]) or self.values["voice-clone-speaker-id"])
        self.voice_clone_snapshot.update(
            {
                "speakerId": speaker_id,
                "statusCode": status_code,
                "statusLabel": status_label,
                "message": message or self.voice_clone_snapshot.get("message", ""),
                "demoAudio": str(payload.get("demo_audio", "") or ""),
                "version": str(payload.get("version", "") or ""),
                "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                "apiResourceId": VOICE_CLONE_RESOURCE_ID,
                "billingResourceId": VOICE_CLONE_BILLING_RESOURCE_ID,
            }
        )
        self._update_clone_catalog_metadata(speaker_id, status_label=status_label, note=message or "")

    def _ast_voice_label(self, speaker_id: str) -> str:
        speaker_id = str(speaker_id or "").strip()
        if not speaker_id:
            return DEFAULT_AST_VOICE_OPTION["label"]
        entry = AST_PRESET_VOICE_MAP.get(speaker_id)
        return str(entry.get("label", speaker_id)) if entry else speaker_id

    def _preview_source_language(self, alias: str, values: dict[str, str] | None = None) -> str:
        values_map = values or self.values
        source_language = str(values_map.get(f"{alias}-source", "") or "").strip().lower()
        if source_language.startswith("zh"):
            return "zh"
        if source_language.startswith("en"):
            return "en"
        raise VoiceCloneError("Voice preview currently supports Chinese and English source channels only.")

    def _ensure_preview_source_audio(self, language_code: str) -> Path:
        normalized = str(language_code or "").strip().lower()
        if normalized not in VOICE_PREVIEW_SOURCE_TEXT:
            raise VoiceCloneError("Unsupported preview source language.")

        VOICE_PREVIEW_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        path = VOICE_PREVIEW_SOURCE_DIR / f"preview-source-{normalized}.wav"
        if path.exists() and path.stat().st_size > 1024:
            return path

        text = VOICE_PREVIEW_SOURCE_TEXT[normalized]
        culture = VOICE_PREVIEW_SOURCE_CULTURE[normalized]
        escaped_target = str(path).replace("'", "''")
        escaped_text = text.replace("'", "''")
        escaped_culture = culture.replace("'", "''")
        script = f"""
Add-Type -AssemblyName System.Speech
$target = '{escaped_target}'
$text = '{escaped_text}'
$culture = '{escaped_culture}'
$parent = Split-Path -Parent $target
if ($parent) {{
  [System.IO.Directory]::CreateDirectory($parent) | Out-Null
}}
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $synth.GetInstalledVoices() | Where-Object {{
  $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $culture
}} | Select-Object -First 1
if (-not $voice) {{
  throw \"No installed voice found for $culture\"
}}
$synth.SelectVoice($voice.VoiceInfo.Name)
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
  16000,
  [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
  [System.Speech.AudioFormat.AudioChannel]::Mono
)
$synth.SetOutputToWaveFile($target, $format)
$synth.Speak($text)
$synth.Dispose()
"""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0 or not path.exists() or path.stat().st_size <= 1024:
            stderr = (result.stderr or result.stdout or "").strip()
            raise VoiceCloneError(stderr or "Failed to generate the local preview source audio.")
        return path

    def _wav_payload_chunks(self, path: Path, chunk_size: int = VOICE_PREVIEW_CHUNK_BYTES) -> tuple[list[bytes], int, int, int]:
        with wave.open(str(path), "rb") as wav_file:
            channels = int(wav_file.getnchannels())
            sample_width = int(wav_file.getsampwidth())
            sample_rate = int(wav_file.getframerate())
        raw = path.read_bytes()
        chunks = [raw[index : index + chunk_size] for index in range(0, len(raw), chunk_size)]
        return chunks, sample_rate, sample_width * 8, channels

    def _pcm_float32_to_wav_bytes(self, raw_audio: bytes, sample_rate: int = VOICE_PREVIEW_TARGET_RATE) -> bytes:
        if not raw_audio:
            return b""
        samples = np.frombuffer(raw_audio, dtype=np.float32)
        clipped = np.clip(samples, -1.0, 1.0)
        pcm16 = (clipped * 32767.0).astype(np.int16)
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm16.tobytes())
            return buffer.getvalue()

    async def _render_channel_preview_audio(
        self,
        alias: str,
        speaker_id: str,
        values: dict[str, str] | None = None,
        credentials: dict[str, str] | None = None,
    ) -> bytes:
        values_map = values or self.values
        credentials_map = credentials or self.credentials
        source_language = str(values_map.get(f"{alias}-source", "") or "").strip()
        target_language = str(values_map.get(f"{alias}-target", "") or "").strip()
        if "zhen" in {source_language, target_language}:
            raise VoiceCloneError("Voice preview does not support mixed Chinese-English mode yet.")

        source_asset = self._ensure_preview_source_audio(self._preview_source_language(alias, values_map))
        chunks, source_rate, source_bits, source_channels = self._wav_payload_chunks(source_asset)
        session_id = str(uuid.uuid4())
        connect_id = str(uuid.uuid4())
        ws_url = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
        dns_hosts = target_hosts_for_url(ws_url, parse_dns_hosts(values_map.get("network-dns-hosts", "")))
        dns_servers = parse_dns_servers(values_map.get("network-dns-servers", ""))
        headers = {
            "X-Api-App-Key": str(credentials_map.get("appId", "") or "").strip(),
            "X-Api-Access-Key": str(credentials_map.get("accessToken", "") or "").strip(),
            "X-Api-Resource-Id": str(credentials_map.get("resourceId", "") or "").strip() or DEFAULT_RESOURCE_ID,
            "X-Api-Connect-Id": connect_id,
        }
        if not headers["X-Api-App-Key"] or not headers["X-Api-Access-Key"]:
            raise VoiceCloneError("App ID and Access Token are required for voice preview.")

        import websockets

        audio_buffer = bytearray()

        def build_request(event: int, chunk: bytes = b"") -> bytes:
            request = TranslateRequest()
            request.request_meta.SessionID = session_id
            request.event = event
            if event == Type.StartSession:
                request.user.uid = "nova-voice-preview"
                request.user.did = "nova-voice-preview"
                request.source_audio.format = "wav"
                request.source_audio.codec = "raw"
                request.source_audio.rate = source_rate
                request.source_audio.bits = source_bits
                request.source_audio.channel = source_channels
                request.target_audio.format = "pcm"
                request.target_audio.rate = VOICE_PREVIEW_TARGET_RATE
                request.request.mode = "s2s"
                request.request.source_language = source_language
                request.request.target_language = target_language
                if speaker_id.strip():
                    request.request.speaker_id = speaker_id.strip()
            elif event == Type.TaskRequest:
                request.source_audio.binary_data = chunk
            return request.SerializeToString()

        with dns_override(dns_hosts, dns_servers):
            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                max_size=32 * 1024 * 1024,
                compression=None,
                proxy=True if ast_use_system_proxy() else None,
                open_timeout=15,
                ping_interval=20,
                ping_timeout=20,
            ) as websocket:
                await websocket.send(build_request(Type.StartSession))

                while True:
                    response = TranslateResponse()
                    response.ParseFromString(await websocket.recv())
                    if response.event == Type.SessionStarted:
                        break
                    if response.event == Type.SessionFailed:
                        raise VoiceCloneError(response.response_meta.Message or "AST preview session failed during startup.")

                frame_bytes = max(1, source_channels * max(1, source_bits // 8))
                chunk_delay = max(0.02, (VOICE_PREVIEW_CHUNK_BYTES / frame_bytes) / max(1, source_rate))
                for chunk in chunks:
                    await websocket.send(build_request(Type.TaskRequest, chunk))
                    await asyncio.sleep(chunk_delay)

                finish_request = TranslateRequest()
                finish_request.request_meta.SessionID = session_id
                finish_request.event = Type.FinishSession
                await websocket.send(finish_request.SerializeToString())

                while True:
                    response = TranslateResponse()
                    response.ParseFromString(await websocket.recv())
                    if response.event == Type.TTSResponse and response.data:
                        audio_buffer.extend(response.data)
                    elif response.event == Type.SessionFailed:
                        raise VoiceCloneError(response.response_meta.Message or "AST preview session failed.")
                    elif response.event == Type.SessionFinished:
                        break

        wav_bytes = self._pcm_float32_to_wav_bytes(bytes(audio_buffer))
        if not wav_bytes:
            raise VoiceCloneError("Preview returned no translated audio.")
        return wav_bytes

    def _preview_payload(self, alias: str, speaker_id: str, wav_bytes: bytes, values: dict[str, str]) -> dict[str, Any]:
        return {
            "alias": alias,
            "speakerId": speaker_id,
            "label": self._ast_voice_label(speaker_id),
            "audioBase64": base64.b64encode(wav_bytes).decode("ascii"),
            "sourceLanguage": values.get(f"{alias}-source", ""),
            "targetLanguage": values.get(f"{alias}-target", ""),
        }

    def _voice_preview_worker(
        self,
        job_id: str,
        alias: str,
        speaker_id: str,
        values_snapshot: dict[str, str],
        credentials_snapshot: dict[str, str],
    ) -> None:
        preview_payload: dict[str, Any] | None = None
        error_message = ""
        status = "completed"
        try:
            preview_wav = asyncio.run(
                self._render_channel_preview_audio(
                    alias,
                    speaker_id,
                    values=values_snapshot,
                    credentials=credentials_snapshot,
                )
            )
            preview_payload = self._preview_payload(alias, speaker_id, preview_wav, values_snapshot)
        except VoiceCloneError as exc:
            status = "failed"
            error_message = str(exc)
        except Exception as exc:
            status = "failed"
            error_message = f"Voice preview failed: {exc}"

        with self._voice_preview_lock:
            job = self._voice_preview_job
            if not job or job.get("id") != job_id:
                return
            job["status"] = status
            job["completedAt"] = time.time()
            job["preview"] = preview_payload
            job["error"] = error_message

    def preview_channel_voice(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload:
            self.update_state(payload)
        if any(channel.is_running for channel in self.channels.values()):
            return {"ok": False, "error": "Stop the interpreter engine before previewing a voice.", "state": self.get_state()}

        alias = str((payload or {}).get("alias", "a") or "a").strip().lower()
        if alias not in CHANNEL_ALIASES:
            alias = "a"
        speaker_id = str(self.values.get(f"{alias}-speaker", "") or "").strip()
        if not speaker_id:
            return {"ok": False, "error": "Choose a built-in AST voice first.", "state": self.get_state()}

        values_snapshot = dict(self.values)
        credentials_snapshot = dict(self.credentials)
        with self._voice_preview_lock:
            active_job = self._voice_preview_job
            if active_job and active_job.get("status") == "running":
                active_alias = str(active_job.get("alias", "") or "").strip() or "channel"
                return {
                    "ok": False,
                    "error": f"Voice preview is already rendering for {active_alias.upper()}.",
                    "state": self.get_state(),
                }
            job_id = str(uuid.uuid4())
            self._voice_preview_job = {
                "id": job_id,
                "alias": alias,
                "speakerId": speaker_id,
                "status": "running",
                "preview": None,
                "error": "",
                "startedAt": time.time(),
                "completedAt": None,
            }

        worker = threading.Thread(
            target=self._voice_preview_worker,
            args=(job_id, alias, speaker_id, values_snapshot, credentials_snapshot),
            name=f"voice-preview-{alias}",
            daemon=True,
        )
        worker.start()
        return {
            "ok": True,
            "pending": True,
            "jobId": job_id,
            "state": self.get_state(),
        }

    def poll_preview_channel_voice(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        requested_job_id = str((payload or {}).get("jobId", "") or "").strip()
        with self._voice_preview_lock:
            current_job = dict(self._voice_preview_job or {})
        if not current_job:
            return {"ok": False, "error": "No voice preview task is available.", "state": self.get_state()}
        if requested_job_id and requested_job_id != str(current_job.get("id", "") or ""):
            return {"ok": False, "error": "Voice preview task not found.", "state": self.get_state()}

        status = str(current_job.get("status", "") or "")
        response = {
            "ok": status == "completed",
            "pending": status == "running",
            "done": status in {"completed", "failed"},
            "jobId": str(current_job.get("id", "") or ""),
            "state": self.get_state(),
        }
        if status == "completed" and current_job.get("preview"):
            response["preview"] = current_job["preview"]
        elif status == "failed":
            response["error"] = str(current_job.get("error", "") or "Voice preview failed.")
        return response

    def _extract_download_url(self, manifest: dict[str, Any]) -> str:
        for key in ("download_url", "downloadUrl", "url"):
            value = str(manifest.get(key, "") or "").strip()
            if value:
                return value
        assets = manifest.get("assets")
        if isinstance(assets, dict):
            if sys.platform == "darwin":
                platform_keys = ("macos", "mac", "darwin", "osx", "universal2", "arm64", "x64")
            elif sys.platform.startswith("win"):
                platform_keys = ("windows", "win64", "win")
            elif sys.platform.startswith("linux"):
                platform_keys = ("linux", "linux64", "x64")
            else:
                platform_keys = (sys.platform,)
            for platform_key in platform_keys:
                node = assets.get(platform_key)
                if isinstance(node, dict):
                    for key in ("download_url", "downloadUrl", "url"):
                        value = str(node.get(key, "") or "").strip()
                        if value:
                            return value
        return ""

    def train_voice_clone(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload:
            self.update_state(payload)
        if not looks_like_console_speaker_id(self.values["voice-clone-speaker-id"]):
            message = "Voice clone training requires a console speaker ID such as S_xxx or ICL_xxx."
            self.voice_clone_snapshot.update(
                {
                    "speakerId": self.values["voice-clone-speaker-id"],
                    "statusCode": None,
                    "statusLabel": "Speaker ID Needed",
                    "message": message,
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self._update_clone_catalog_metadata(self.values["voice-clone-speaker-id"], status_label="Speaker ID Needed", note=message)
            self.save_config()
            return {"ok": False, "error": message, "state": self.get_state()}
        try:
            manager = self._clone_manager()
            response = manager.upload_training_sample(
                speaker_id=self.values["voice-clone-speaker-id"],
                audio_path=self.values["voice-clone-sample-path"],
                language_code=self.values["voice-clone-language"],
                reference_text=self.values["voice-clone-reference-text"],
                demo_text=self.values["voice-clone-demo-text"],
                model_type=5,
            )
        except VoiceCloneError as exc:
            self.voice_clone_snapshot.update(
                {
                    "speakerId": self.values["voice-clone-speaker-id"],
                    "statusCode": None,
                    "statusLabel": "Error",
                    "message": str(exc),
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self._update_clone_catalog_metadata(self.values["voice-clone-speaker-id"], status_label="Error", note=str(exc))
            self.save_config()
            return {"ok": False, "error": str(exc), "state": self.get_state()}

        self._update_voice_clone_snapshot(response, message="Training sample uploaded.")
        self.save_config()
        return {"ok": True, "state": self.get_state(), "voiceClone": self._voice_clone_state()}

    def refresh_voice_clone_status(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload:
            self.update_state(payload)
        if not looks_like_console_speaker_id(self.values["voice-clone-speaker-id"]):
            message = "Voice clone status requires a console speaker ID such as S_xxx or ICL_xxx."
            self.voice_clone_snapshot.update(
                {
                    "speakerId": self.values["voice-clone-speaker-id"],
                    "statusCode": None,
                    "statusLabel": "Speaker ID Needed",
                    "message": message,
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self._update_clone_catalog_metadata(self.values["voice-clone-speaker-id"], status_label="Speaker ID Needed", note=message)
            self.save_config()
            return {"ok": False, "error": message, "state": self.get_state()}
        try:
            manager = self._clone_manager()
            response = manager.query_status(self.values["voice-clone-speaker-id"])
        except VoiceCloneError as exc:
            self.voice_clone_snapshot.update(
                {
                    "speakerId": self.values["voice-clone-speaker-id"],
                    "statusLabel": "Error",
                    "message": str(exc),
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self._update_clone_catalog_metadata(self.values["voice-clone-speaker-id"], status_label="Error", note=str(exc))
            self.save_config()
            return {"ok": False, "error": str(exc), "state": self.get_state()}

        self._update_voice_clone_snapshot(response, message="Voice clone status refreshed.")
        self.save_config()
        return {"ok": True, "state": self.get_state(), "voiceClone": self._voice_clone_state()}

    def start_voice_clone_recording(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload:
            self.update_state(payload)
        if any(channel.is_running for channel in self.channels.values()):
            return {"ok": False, "error": "Stop the interpreter engine before recording a clone sample.", "state": self.get_state()}
        if self._voice_clone_record_thread and self._voice_clone_record_thread.is_alive():
            return {"ok": True, "state": self.get_state(), "voiceClone": self._voice_clone_state()}

        device_id = str(self.values.get("voice-clone-record-device", "") or self.values.get("a-input", "") or "").strip()
        if not device_id or device_id not in self.catalog.microphones:
            device_id = self.catalog.default_microphone_id()
            self.values["voice-clone-record-device"] = device_id
        microphone_ref = self.catalog.microphones.get(device_id)
        if microphone_ref is None:
            return {"ok": False, "error": "Voice clone recording input device is not available.", "state": self.get_state()}

        self._voice_clone_record_stop.clear()
        with self._voice_clone_record_lock:
            self._voice_clone_record_device_id = device_id
            self._voice_clone_record_device_name = microphone_ref.name
            self._voice_clone_record_started_at = time.time()
            self._voice_clone_record_duration_sec = 0.0
            self._voice_clone_record_level_db = -96.0
        self._voice_clone_record_thread = threading.Thread(
            target=self._voice_clone_record_loop,
            args=(device_id,),
            name="voice-clone-record",
            daemon=True,
        )
        self._voice_clone_record_thread.start()
        self.voice_clone_snapshot.update(
            {
                "statusLabel": "Recording",
                "message": f"Recording sample from {microphone_ref.name}. Speak naturally, then press stop.",
                "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        return {"ok": True, "state": self.get_state(), "voiceClone": self._voice_clone_state()}

    def stop_voice_clone_recording(self) -> dict[str, Any]:
        thread = self._voice_clone_record_thread
        if thread is None or not thread.is_alive():
            return {"ok": False, "error": "Voice clone recording is not active.", "state": self.get_state()}
        self._stop_voice_clone_recording(wait_timeout=12.0)
        if self._voice_clone_record_thread is not None and self._voice_clone_record_thread.is_alive():
            return {"ok": False, "error": "Voice clone recording is still stopping. Please try again in a moment.", "state": self.get_state()}
        return {"ok": True, "state": self.get_state(), "voiceClone": self._voice_clone_state()}

    def _stop_voice_clone_recording(self, wait_timeout: float = 0.0) -> None:
        self._voice_clone_record_stop.set()
        thread = self._voice_clone_record_thread
        if thread is not None and wait_timeout > 0:
            thread.join(timeout=wait_timeout)
            if not thread.is_alive():
                self._voice_clone_record_thread = None

    def _voice_clone_record_loop(self, device_id: str) -> None:
        frames: list[np.ndarray] = []
        total_samples = 0
        microphone = self.catalog.get_microphone(device_id)
        if microphone is None:
            self.voice_clone_snapshot.update(
                {
                    "statusLabel": "Error",
                    "message": "Voice clone recording input device is not available.",
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self._voice_clone_record_thread = None
            return

        try:
            with microphone.recorder(
                samplerate=VOICE_CLONE_RECORD_SAMPLE_RATE,
                channels=1,
                blocksize=VOICE_CLONE_RECORD_BLOCK_FRAMES,
            ) as recorder:
                while not self._voice_clone_record_stop.is_set():
                    captured = recorder.record(numframes=VOICE_CLONE_RECORD_BLOCK_FRAMES)
                    if captured is None or captured.size == 0:
                        continue
                    mono = captured.mean(axis=1) if captured.ndim > 1 else captured
                    chunk = mono.astype(np.float32, copy=False)
                    frames.append(np.array(chunk, copy=True))
                    total_samples += chunk.size
                    with self._voice_clone_record_lock:
                        self._voice_clone_record_duration_sec = total_samples / VOICE_CLONE_RECORD_SAMPLE_RATE
                        self._voice_clone_record_level_db = samples_to_dbfs(chunk)
        except Exception as exc:
            self.voice_clone_snapshot.update(
                {
                    "statusLabel": "Error",
                    "message": f"Voice clone recording failed: {exc}",
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            with self._voice_clone_record_lock:
                self._voice_clone_record_duration_sec = 0.0
                self._voice_clone_record_level_db = -96.0
            self._voice_clone_record_thread = None
            return

        try:
            merged = np.concatenate(frames).astype(np.float32, copy=False) if frames else np.empty(0, dtype=np.float32)
            trimmed = self._trim_voice_clone_samples(merged)
            duration_sec = trimmed.size / VOICE_CLONE_RECORD_SAMPLE_RATE if trimmed.size else 0.0
            if duration_sec < VOICE_CLONE_MIN_SAMPLE_SECONDS:
                raise VoiceCloneError("Recorded sample is too short. Please record at least 2 seconds of speech.")

            peak = float(np.max(np.abs(trimmed))) if trimmed.size else 0.0
            if peak > 1e-5:
                trimmed = np.clip(trimmed * min(0.96 / peak, 4.0), -1.0, 1.0)

            sample_path = self._recorded_sample_path()
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(sample_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(VOICE_CLONE_RECORD_SAMPLE_RATE)
                wav_file.writeframes(float_to_pcm16(trimmed))

            self.values["voice-clone-sample-path"] = str(sample_path)
            self.values["voice-clone-record-device"] = device_id
            self.voice_clone_snapshot.update(
                {
                    "statusLabel": "Sample Ready",
                    "message": f"Recorded {duration_sec:.1f}s sample from {self._voice_clone_record_device_name}. Ready to train.",
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            with self._voice_clone_record_lock:
                self._voice_clone_record_duration_sec = duration_sec
                self._voice_clone_record_level_db = samples_to_dbfs(trimmed)
            self.save_config()
        except Exception as exc:
            self.voice_clone_snapshot.update(
                {
                    "statusLabel": "Error",
                    "message": str(exc),
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        finally:
            self._voice_clone_record_stop.clear()
            self._voice_clone_record_thread = None

    def _recorded_sample_path(self) -> Path:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        return VOICE_CLONE_SAMPLE_DIR / f"voice-clone-{timestamp}.wav"

    def _trim_voice_clone_samples(self, samples: np.ndarray) -> np.ndarray:
        if samples.size == 0:
            return samples
        threshold = 0.012
        active_indices = np.flatnonzero(np.abs(samples) >= threshold)
        if active_indices.size == 0:
            return samples
        pad = int(VOICE_CLONE_RECORD_SAMPLE_RATE * 0.12)
        start = max(0, int(active_indices[0]) - pad)
        end = min(samples.size, int(active_indices[-1]) + pad)
        return np.array(samples[start:end], copy=True)

    def check_updates(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest_url = ""
        if payload:
            manifest_url = str(payload.get("manifestUrl", "") or payload.get("url", "") or "").strip()
            if not manifest_url:
                self.update_state(payload)
        manifest_url = manifest_url or self.values["update-manifest-url"]
        if manifest_url:
            self.values["update-manifest-url"] = manifest_url
            self.updater.set_manifest_url(manifest_url)

        result = self.updater.check(self.values["update-manifest-url"])
        self.update_snapshot["current"] = dict(self.updater.current)
        self.update_snapshot["lastCheck"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.update_snapshot["result"] = result
        self.save_config()
        return {"ok": bool(result.get("ok")), "state": self.get_state(), "updater": self._updater_state(), **result}

    def download_update(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest = self.update_snapshot.get("result", {}).get("manifest", {}) if isinstance(self.update_snapshot.get("result"), dict) else {}
        download_url = ""
        filename = ""
        if payload:
            download_url = str(payload.get("downloadUrl", "") or payload.get("url", "") or "").strip()
            filename = str(payload.get("filename", "") or "").strip()
        download_url = download_url or self._extract_download_url(manifest)
        result = self.updater.download(download_url, filename)
        self.update_snapshot["download"] = result
        return {"ok": bool(result.get("ok")), "state": self.get_state(), "updater": self._updater_state(), **result}

    def _drain_events(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self._apply_event(event)

    def _fallback_channel_to_ast_tts(self, channel_id: str, reason: str) -> None:
        alias = CHANNEL_ID_TO_ALIAS.get(channel_id, "")
        if not alias:
            return

        self._local_tts_disabled_channels.add(channel_id)
        message = "Clone TTS failed; falling back to AST voice."
        if reason:
            message = f"{message} {reason}"
        self.channel_status[channel_id] = message

        previous = self.channels.pop(channel_id, None)
        if previous is not None:
            previous.stop()
            previous.join(timeout=2.0)

        if self._runtime_credentials is None:
            self.last_error[channel_id] = message
            return
        if self.values.get(f"{alias}-enabled") != "1" or self.values.get(f"{alias}-input-enabled") != "1":
            return

        try:
            channel = TranslationChannel(
                self.catalog,
                self._build_channel_settings(alias),
                self._runtime_credentials,
                self.event_queue.put,
            )
            self.channels[channel_id] = channel
            self.channel_status[channel_id] = "Clone TTS fallback active; AST voice restarted."
            channel.start()
        except Exception as exc:
            self.last_error[channel_id] = f"Failed to restart AST voice fallback: {exc}"
            self.channel_status[channel_id] = self.last_error[channel_id]

    def _apply_event(self, event: dict[str, Any]) -> None:
        channel_id = event["channel"]
        alias = CHANNEL_ID_TO_ALIAS.get(channel_id, "")
        kind = event["kind"]
        text = str(event.get("text", "") or "")
        timestamp = float(event.get("timestamp") or time.time())
        stamp = format_ts(timestamp)
        correction_map = self.correction_maps.get(channel_id, {})
        target_language = self.values.get(f"{alias}-target", "") if alias else ""

        if kind == "status":
            self.channel_status[channel_id] = text
            return

        if kind == "error":
            self.last_error[channel_id] = text
            self.channel_status[channel_id] = text
            return

        if kind == "local_tts_failed":
            self._fallback_channel_to_ast_tts(channel_id, text)
            return

        if kind == "stats":
            self.stats_by_channel[channel_id] = dict(event.get("stats", {}) or {})
            return

        if kind == "source_partial":
            self.partials[channel_id]["source"] = apply_replacements(text, correction_map)
            return

        if kind == "source_final":
            normalized = apply_replacements(text, correction_map)
            self.partials[channel_id]["source"] = normalized
            if self.partials[channel_id].get("target"):
                self.partials[channel_id]["target"] = apply_domain_translation_override(
                    self.values["domain-preset"],
                    normalized,
                    self.partials[channel_id]["target"],
                    target_language,
                )
            self._append_transcript(channel_id, stamp, source=normalized)
            return

        if kind == "target_partial":
            normalized = apply_replacements(text, correction_map)
            normalized = apply_domain_translation_override(
                self.values["domain-preset"],
                self.partials[channel_id].get("source", ""),
                normalized,
                target_language,
            )
            self.partials[channel_id]["target"] = normalized
            return

        if kind == "target_final":
            normalized = apply_replacements(text, correction_map)
            normalized = apply_domain_translation_override(
                self.values["domain-preset"],
                self.partials[channel_id].get("source", ""),
                normalized,
                target_language,
            )
            self.partials[channel_id]["target"] = normalized
            self._append_transcript(channel_id, stamp, target=normalized)
            return

    def _append_transcript(self, channel_id: str, stamp: str, source: str = "", target: str = "") -> None:
        entries = self.transcripts[channel_id]
        if target:
            alias = CHANNEL_ID_TO_ALIAS.get(channel_id, "")
            target_language = self.values.get(f"{alias}-target", "") if alias else ""
            for item in reversed(entries):
                if not item.get("target"):
                    item["target"] = apply_domain_translation_override(
                        self.values["domain-preset"],
                        str(item.get("source", "")),
                        target,
                        target_language,
                    )
                    item["time"] = stamp
                    return
            entries.append(
                {
                    "time": stamp,
                    "source": "",
                    "target": apply_domain_translation_override(
                        self.values["domain-preset"],
                        "",
                        target,
                        target_language,
                    ),
                }
            )
            return
        entries.append({"time": stamp, "source": source, "target": ""})

    def _runtime_snapshot(self) -> dict[str, Any]:
        out_stats = self.stats_by_channel["outbound"]
        in_stats = self.stats_by_channel["inbound"]
        running = any(channel.is_running for channel in self.channels.values())
        has_error = any(bool(self.last_error[channel_id]) for channel_id in CHANNEL_IDS)
        domain = DOMAIN_PACKS.get(self.values["domain-preset"], DOMAIN_PACKS["generic"])
        virtual_out_count = sum(1 for item in self.catalog.speakers.values() if item.virtual)
        local_clone_channels = self._local_clone_channels()
        proxy_mode = "system proxy" if ast_use_system_proxy() else "direct"
        dns_servers = parse_dns_servers(self.values["network-dns-servers"])
        dns_hosts = parse_dns_hosts(self.values["network-dns-hosts"])

        if has_error:
            global_status = "Error"
        elif running:
            global_status = "Live"
        else:
            global_status = "Ready"

        hint_parts = [domain["description"], f"AST path: {proxy_mode}"]
        if dns_servers and dns_hosts:
            hint_parts.append(f"Custom DNS: {' / '.join(dns_servers)} for {' / '.join(dns_hosts)}.")
        if virtual_out_count:
            hint_parts.append(f"{virtual_out_count} virtual outputs detected.")
        if local_clone_channels:
            hint_parts.append(
                f"Local clone TTS on {' / '.join(local_clone_channels)} waits for sentence end, so it is slower than AST voice."
            )
        fallback_channels = self._clone_fallback_channels()
        if fallback_channels:
            hint_parts.append(f"Clone TTS uses AST voice on {' / '.join(fallback_channels)}.")
        hint = " / ".join(hint_parts)

        return {
            "running": running,
            "globalStatus": global_status,
            "globalHint": hint,
            "networkMode": "system_proxy" if ast_use_system_proxy() else "direct",
            "channels": {
                "a": self._channel_runtime("a", "outbound", out_stats),
                "b": self._channel_runtime("b", "inbound", in_stats),
            },
            "metrics": {
                "inputA": self._input_metric(out_stats),
                "inputB": self._input_metric(in_stats),
                "ast": self._latency_metric(
                    out_stats.get("first_translation_latency_ms"),
                    in_stats.get("first_translation_latency_ms"),
                ),
                "tts": self._latency_metric(
                    out_stats.get("first_audio_latency_ms"),
                    in_stats.get("first_audio_latency_ms"),
                ),
            },
        }

    def _channel_runtime(self, alias: str, channel_id: str, stats: dict[str, Any]) -> dict[str, Any]:
        state = str(stats.get("session_state", "") or "")
        last_status = self.channel_status[channel_id]
        error = self.last_error[channel_id] or str(stats.get("last_error", "") or "")
        signal = "idle"
        label = "Ready"
        pane = "Idle"
        enabled = self.values[f"{alias}-enabled"] == "1"
        capture_enabled = self.values[f"{alias}-input-enabled"] == "1"
        playback_enabled = self.values[f"{alias}-output-enabled"] == "1" or self.values[f"{alias}-monitor-enabled"] == "1"

        if not enabled:
            return {
                "signal": "idle",
                "label": "Disabled",
                "pane": "Disabled",
                "status": "Channel disabled",
                "stats": stats,
            }
        if not capture_enabled:
            return {
                "signal": "idle",
                "label": "Input Off",
                "pane": "Standby",
                "status": "Input capture disabled",
                "stats": stats,
            }

        if error:
            signal = "error"
            label = "Error"
            pane = "Error"
        elif state == "starting":
            signal = "warning"
            label = "Starting"
            pane = "Connecting" if playback_enabled else "Captions Only"
        elif state == "reconnecting":
            signal = "warning"
            label = "Connecting"
            pane = "Connecting"
        elif state == "running":
            signal = "ok"
            label = "Live"
            pane = "Streaming" if playback_enabled else "Captions Only"
        elif self.channels.get(channel_id):
            signal = "warning"
            label = "Running"
            pane = "Streaming" if playback_enabled else "Captions Only"

        return {
            "signal": signal,
            "label": label,
            "pane": pane,
            "status": error or last_status or ("Output playback disabled" if not playback_enabled else "Ready"),
            "stats": stats,
        }

    def _latency_metric(self, *values: Any) -> str:
        numeric = [float(value) for value in values if isinstance(value, (int, float))]
        if not numeric:
            return "--"
        return f"{min(numeric):.0f} ms"

    def _input_metric(self, stats: dict[str, Any]) -> str:
        if not stats:
            return "--"
        queue_depth = int(stats.get("input_queue_depth", 0) or 0)
        level = stats.get("audio_level_db")
        dropped = int(stats.get("dropped_silent_chunks", 0) or 0)
        if isinstance(level, (int, float)):
            return f"{level:.0f} dB / Q{queue_depth:02d} / Drop {dropped}"
        return f"Q{queue_depth:02d} / Drop {dropped}"
