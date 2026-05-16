from __future__ import annotations

import asyncio
import ctypes
import json
import os
import platform
import queue
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundcard as sc
import websockets

from custom_dns import dns_override, target_hosts_for_url
from audio_core_bridge import NativeAudioCoreBridge, NativeCaptureSession, NativePlaybackSession
from paths import get_app_root
from python_protogen.common.events_pb2 import Type
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest, TranslateResponse
from voice_clone_manager import CloneTTSSynthesizer, VoiceCloneError

DEFAULT_WS_URL = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
DEFAULT_RESOURCE_ID = "volc.service_type.10053"
DEFAULT_INPUT_SAMPLE_RATE = 16000
DEFAULT_INPUT_BITS = 16
DEFAULT_INPUT_CHANNELS = 1
DEFAULT_TARGET_AUDIO_FORMAT = "pcm"
SILENCE_KEEPALIVE_INTERVAL_SEC = 0.35
SPEECH_PREROLL_MS = 180
POST_SPEECH_FINALIZE_MS = 360
AUTO_RECONNECT_BASE_DELAY_SEC = 1.5
AUTO_RECONNECT_MAX_DELAY_SEC = 12.0
AUTO_RECONNECT_MAX_ATTEMPTS = 6
ROOT = get_app_root()
LOG_DIR = ROOT / "output" / "logs"
DATACLASS_SLOTS = {"slots": True} if sys.version_info >= (3, 10) else {}

LANGUAGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Chinese", "zh"),
    ("English", "en"),
    ("Japanese", "ja"),
    ("Indonesian", "id"),
    ("Spanish", "es"),
    ("Portuguese", "pt"),
    ("German", "de"),
    ("French", "fr"),
    ("Chinese + English", "zhen"),
)

SUBTITLE_MODES: tuple[tuple[str, str], ...] = (
    ("Bilingual", "bilingual"),
    ("Source Only", "source_only"),
    ("Target Only", "target_only"),
)


@dataclass(**DATACLASS_SLOTS)
class PerformancePreset:
    key: str
    label: str
    description: str
    chunk_ms: int
    jitter_buffer_ms: int
    target_audio_rate: int
    input_gain: float
    max_queue_chunks: int


VIRTUAL_DEVICE_KEYWORDS = (
    "virtual",
    "vb-audio",
    "vb cable",
    "cable",
    "voicemeeter",
    "blackhole",
    "loopback",
    "obs",
    "streaming",
    "todesk",
)

PERFORMANCE_PRESETS: dict[str, PerformancePreset] = {
    "turbo": PerformancePreset(
        key="turbo",
        label="Turbo",
        description="Lowest startup latency for Discord, game chat, and fast turn-taking.",
        chunk_ms=20,
        jitter_buffer_ms=24,
        target_audio_rate=16000,
        input_gain=1.08,
        max_queue_chunks=96,
    ),
    "balanced": PerformancePreset(
        key="balanced",
        label="Balanced",
        description="Balanced latency and stability for long sessions and mixed hardware.",
        chunk_ms=60,
        jitter_buffer_ms=75,
        target_audio_rate=16000,
        input_gain=1.0,
        max_queue_chunks=160,
    ),
    "studio": PerformancePreset(
        key="studio",
        label="Studio",
        description="Higher playback fidelity and safer buffering for demos and recording.",
        chunk_ms=90,
        jitter_buffer_ms=140,
        target_audio_rate=24000,
        input_gain=1.0,
        max_queue_chunks=220,
    ),
}

_TIMER_LOCK = threading.Lock()
_TIMER_RESOLUTION_USERS = 0


def detect_virtual_device(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in VIRTUAL_DEVICE_KEYWORDS)


def request_timer_resolution() -> None:
    global _TIMER_RESOLUTION_USERS
    if os.name != "nt":
        return
    with _TIMER_LOCK:
        if _TIMER_RESOLUTION_USERS == 0:
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)
            except Exception:
                return
        _TIMER_RESOLUTION_USERS += 1


def release_timer_resolution() -> None:
    global _TIMER_RESOLUTION_USERS
    if os.name != "nt":
        return
    with _TIMER_LOCK:
        if _TIMER_RESOLUTION_USERS <= 0:
            return
        _TIMER_RESOLUTION_USERS -= 1
        if _TIMER_RESOLUTION_USERS == 0:
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass


def boost_current_thread_priority() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), 2)
    except Exception:
        pass


def use_system_proxy() -> bool:
    return str(os.getenv("NOVA_USE_SYSTEM_PROXY", "")).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(**DATACLASS_SLOTS)
class Credentials:
    app_key: str
    access_key: str
    resource_id: str = DEFAULT_RESOURCE_ID
    ws_url: str = DEFAULT_WS_URL
    dns_servers: tuple[str, ...] = ()
    dns_hosts: tuple[str, ...] = ()


@dataclass(**DATACLASS_SLOTS)
class AudioDeviceRef:
    device_id: str
    name: str
    kind: str
    loopback: bool = False
    channels: int = 1
    virtual: bool = False

    @property
    def label(self) -> str:
        prefix = "Loopback" if self.loopback else ("Input" if self.kind == "microphone" else "Output")
        return f"{prefix} | {self.name}"


@dataclass(**DATACLASS_SLOTS)
class ChannelSettings:
    channel_id: str
    display_name: str
    capture_device_id: str
    playback_device_id: str
    source_language: str
    target_language: str
    speaker_id: str = ""
    mode: str = "s2s"
    performance_profile: str = "balanced"
    chunk_ms: int = 80
    jitter_buffer_ms: int = 100
    startup_buffer_ms: int = 60
    target_audio_rate: int = 24000
    input_gain: float = 1.0
    subtitle_mode: str = "bilingual"
    max_queue_chunks: int = 180
    skip_silence: bool = False
    noise_gate_db: float = -52.0
    silence_hold_ms: int = 280
    context_prompt: str = ""
    hot_words: list[str] = field(default_factory=list)
    correct_words: dict[str, str] = field(default_factory=dict)
    glossary: dict[str, str] = field(default_factory=dict)
    enable_agc: bool = True
    agc_target_dbfs: float = -18.0
    max_agc_gain: float = 6.0
    enable_denoise: bool = True
    denoise_strength: float = 0.22
    capture_enabled: bool = True
    playback_enabled: bool = True
    monitor_playback_enabled: bool = False
    monitor_playback_device_id: str = ""
    use_local_tts: bool = False
    local_tts_voice: str = ""
    local_tts_cluster: str = "volcano_icl"
    local_tts_speed: float = 1.0
    capture_backend: str = "python"
    native_capture_fallback: bool = True
    pre_roll_ms: int = SPEECH_PREROLL_MS
    resampler_quality: str = "sinc-lite"
    vad_mode: str = "adaptive"
    enable_noise_floor: bool = True
    adaptive_chunking: bool = True
    playback_backend: str = "python"


@dataclass(**DATACLASS_SLOTS)
class ChannelStats:
    channel_id: str
    session_state: str = "idle"
    log_id: str = ""
    last_status: str = "idle"
    last_error: str = ""
    last_event: str = ""
    started_at: float = 0.0
    session_started_at: float = 0.0
    sent_chunks: int = 0
    sent_audio_bytes: int = 0
    source_partials: int = 0
    source_sentences: int = 0
    translation_partials: int = 0
    translation_sentences: int = 0
    tts_chunks: int = 0
    received_audio_bytes: int = 0
    usage_updates: int = 0
    first_source_latency_ms: float | None = None
    first_translation_latency_ms: float | None = None
    first_audio_latency_ms: float | None = None
    input_queue_depth: int = 0
    playback_queue_depth: int = 0
    last_source_text: str = ""
    last_target_text: str = ""
    audio_level_db: float | None = None
    dropped_silent_chunks: int = 0
    speech_active: bool = False
    external_tts_jobs: int = 0
    external_tts_failures: int = 0
    playback_gap_fills: int = 0
    playback_gap_fill_ms: int = 0
    playback_rejoins: int = 0
    playback_limiter_events: int = 0
    playback_limiter_reduction_db: float = 0.0
    playback_peak_dbfs: float | None = None
    playback_active_outputs: int = 0
    playback_output_failures: int = 0
    playback_failed_outputs: list[str] = field(default_factory=list)
    reconnect_attempts: int = 0
    reconnect_successes: int = 0
    last_disconnect_reason: str = ""
    capture_backend: str = "python"
    native_capture_active: bool = False
    native_capture_fallbacks: int = 0
    native_vad_score: float | None = None
    native_noise_floor_db: float | None = None
    native_agc_gain: float | None = None
    native_resampler: str = ""
    native_chunk_latency_ms: float | None = None
    playback_backend: str = "python"

    def snapshot(self) -> dict:
        now = time.time()
        uptime_sec = now - self.started_at if self.started_at else 0.0
        session_sec = now - self.session_started_at if self.session_started_at else 0.0
        return {
            "channel_id": self.channel_id,
            "session_state": self.session_state,
            "log_id": self.log_id,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_event": self.last_event,
            "uptime_sec": round(uptime_sec, 1),
            "session_sec": round(session_sec, 1),
            "sent_chunks": self.sent_chunks,
            "sent_audio_bytes": self.sent_audio_bytes,
            "source_partials": self.source_partials,
            "source_sentences": self.source_sentences,
            "translation_partials": self.translation_partials,
            "translation_sentences": self.translation_sentences,
            "tts_chunks": self.tts_chunks,
            "received_audio_bytes": self.received_audio_bytes,
            "usage_updates": self.usage_updates,
            "first_source_latency_ms": self.first_source_latency_ms,
            "first_translation_latency_ms": self.first_translation_latency_ms,
            "first_audio_latency_ms": self.first_audio_latency_ms,
            "input_queue_depth": self.input_queue_depth,
            "playback_queue_depth": self.playback_queue_depth,
            "last_source_text": self.last_source_text,
            "last_target_text": self.last_target_text,
            "audio_level_db": self.audio_level_db,
            "dropped_silent_chunks": self.dropped_silent_chunks,
            "speech_active": self.speech_active,
            "external_tts_jobs": self.external_tts_jobs,
            "external_tts_failures": self.external_tts_failures,
            "playback_gap_fills": self.playback_gap_fills,
            "playback_gap_fill_ms": self.playback_gap_fill_ms,
            "playback_rejoins": self.playback_rejoins,
            "playback_limiter_events": self.playback_limiter_events,
            "playback_limiter_reduction_db": self.playback_limiter_reduction_db,
            "playback_peak_dbfs": self.playback_peak_dbfs,
            "playback_active_outputs": self.playback_active_outputs,
            "playback_output_failures": self.playback_output_failures,
            "playback_failed_outputs": list(self.playback_failed_outputs),
            "reconnect_attempts": self.reconnect_attempts,
            "reconnect_successes": self.reconnect_successes,
            "last_disconnect_reason": self.last_disconnect_reason,
            "capture_backend": self.capture_backend,
            "native_capture_active": self.native_capture_active,
            "native_capture_fallbacks": self.native_capture_fallbacks,
            "native_vad_score": self.native_vad_score,
            "native_noise_floor_db": self.native_noise_floor_db,
            "native_agc_gain": self.native_agc_gain,
            "native_resampler": self.native_resampler,
            "native_chunk_latency_ms": self.native_chunk_latency_ms,
            "playback_backend": self.playback_backend,
        }


UiCallback = Callable[[dict], None]


class SessionReconnectRequested(RuntimeError):
    pass


def language_label(language_code: str) -> str:
    for label, code in LANGUAGE_OPTIONS:
        if code == language_code:
            return label
    return language_code


def event_name(event_value: int) -> str:
    try:
        return Type.Name(event_value)
    except ValueError:
        return str(event_value)


def float_to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype(np.int16).tobytes()


def apply_playback_limiter(
    samples: np.ndarray,
    ceiling: float = 0.98,
    threshold: float = 0.995,
) -> tuple[np.ndarray, bool, float, float]:
    if samples.size == 0:
        return samples.astype(np.float32, copy=False), False, 0.0, -96.0
    clean = np.nan_to_num(samples.astype(np.float32, copy=False), nan=0.0, posinf=1.0, neginf=-1.0)
    peak = float(np.max(np.abs(clean))) if clean.size else 0.0
    peak_dbfs = float(round(20.0 * np.log10(max(peak, 1e-6)), 1)) if peak > 0.0 else -96.0
    if peak <= threshold:
        return np.clip(clean, -1.0, 1.0), False, 0.0, peak_dbfs
    gain = min(1.0, ceiling / max(peak, 1e-6))
    reduction_db = float(round(-20.0 * np.log10(max(gain, 1e-6)), 2))
    return np.clip(clean * gain, -ceiling, ceiling), True, reduction_db, peak_dbfs


def make_gap_fill(tail: np.ndarray, sample_rate: int, duration_ms: int) -> np.ndarray:
    sample_count = max(1, int(sample_rate * max(duration_ms, 1) / 1000))
    if tail.size <= 0:
        return np.zeros(sample_count, dtype=np.float32)

    base = tail.astype(np.float32, copy=False)
    if base.size < sample_count:
        repeats = int(np.ceil(sample_count / max(base.size, 1)))
        base = np.tile(base, repeats)
    filler = np.array(base[-sample_count:], copy=True)
    envelope = np.linspace(0.9, 0.08, filler.size, dtype=np.float32)
    return np.clip(filler * envelope, -1.0, 1.0)


def crossfade_rejoin(previous_tail: np.ndarray, current: np.ndarray, sample_rate: int, fade_ms: int = 10) -> np.ndarray:
    if previous_tail.size <= 0 or current.size <= 0:
        return current
    fade_samples = min(previous_tail.size, current.size, max(1, int(sample_rate * max(fade_ms, 1) / 1000)))
    if fade_samples <= 0:
        return current

    result = np.array(current, copy=True)
    fade_out = np.linspace(1.0, 0.0, fade_samples, endpoint=True, dtype=np.float32)
    fade_in = 1.0 - fade_out
    result[:fade_samples] = (previous_tail[-fade_samples:] * fade_out) + (result[:fade_samples] * fade_in)
    return np.clip(result, -1.0, 1.0)


def samples_to_dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -96.0
    rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float32)))))
    if rms <= 1e-6:
        return -96.0
    return round(20.0 * np.log10(max(rms, 1e-6)), 1)


def safe_float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def get_preset(profile_key: str) -> PerformancePreset:
    return PERFORMANCE_PRESETS.get(profile_key, PERFORMANCE_PRESETS["balanced"])


def soft_highpass(samples: np.ndarray, previous: float) -> tuple[np.ndarray, float]:
    if samples.size == 0:
        return samples, previous
    alpha = 0.985
    filtered = np.empty_like(samples, dtype=np.float32)
    prev_y = 0.0
    prev_x = float(previous)
    for idx, sample in enumerate(samples.astype(np.float32, copy=False)):
        y = alpha * (prev_y + sample - prev_x)
        filtered[idx] = y
        prev_y = y
        prev_x = float(sample)
    return filtered, prev_x


def spectral_denoise(
    samples: np.ndarray,
    noise_profile: np.ndarray | None,
    strength: float,
    learn_noise: bool,
) -> tuple[np.ndarray, np.ndarray | None]:
    if samples.size == 0:
        return samples, noise_profile
    window = np.hanning(samples.size).astype(np.float32)
    framed = samples.astype(np.float32, copy=False) * window
    spectrum = np.fft.rfft(framed)
    magnitude = np.abs(spectrum)
    phase = np.angle(spectrum)

    if noise_profile is None or noise_profile.shape != magnitude.shape:
        noise_profile = magnitude * 0.35

    if learn_noise:
        noise_profile = noise_profile * 0.92 + magnitude * 0.08

    cleaned_magnitude = np.maximum(magnitude - (noise_profile * max(0.0, strength)), magnitude * 0.12)
    rebuilt = np.fft.irfft(cleaned_magnitude * np.exp(1j * phase), n=samples.size).astype(np.float32)
    rebuilt /= np.maximum(window, 1e-3)
    return np.clip(rebuilt, -1.0, 1.0), noise_profile


def apply_agc(
    samples: np.ndarray,
    target_dbfs: float,
    max_gain: float,
    previous_gain: float,
) -> tuple[np.ndarray, float]:
    rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float32))))) if samples.size else 0.0
    if rms <= 1e-6:
        return samples, previous_gain
    target_linear = float(10 ** (target_dbfs / 20.0))
    desired_gain = np.clip(target_linear / max(rms, 1e-6), 0.25, max(1.0, max_gain))
    smoothed_gain = previous_gain * 0.82 + desired_gain * 0.18
    adjusted = np.clip(samples.astype(np.float32, copy=False) * smoothed_gain, -1.0, 1.0)
    return adjusted, float(smoothed_gain)


class DeviceCatalog:
    def __init__(self) -> None:
        self.microphones: dict[str, AudioDeviceRef] = {}
        self.speakers: dict[str, AudioDeviceRef] = {}
        self.refresh()

    def refresh(self) -> None:
        self.microphones.clear()
        self.speakers.clear()

        for speaker in sc.all_speakers():
            ref = AudioDeviceRef(
                device_id=str(speaker.id),
                name=speaker.name,
                kind="speaker",
                loopback=False,
                channels=speaker.channels,
                virtual=detect_virtual_device(speaker.name),
            )
            self.speakers[ref.device_id] = ref

        for microphone in sc.all_microphones(include_loopback=True):
            ref = AudioDeviceRef(
                device_id=str(microphone.id),
                name=microphone.name,
                kind="microphone",
                loopback=bool(getattr(microphone, "isloopback", False)),
                channels=microphone.channels,
                virtual=detect_virtual_device(microphone.name),
            )
            self.microphones[ref.device_id] = ref

    def speaker_options(self) -> list[AudioDeviceRef]:
        return sorted(self.speakers.values(), key=lambda item: item.label.lower())

    def microphone_options(self) -> list[AudioDeviceRef]:
        return sorted(self.microphones.values(), key=lambda item: item.label.lower())

    def default_microphone_id(self) -> str:
        default = sc.default_microphone()
        if default is not None:
            return default.id
        microphones = [item for item in self.microphone_options() if not item.loopback]
        return microphones[0].device_id if microphones else ""

    def default_speaker_id(self) -> str:
        default = sc.default_speaker()
        if default is not None:
            return default.id
        speakers = self.speaker_options()
        return speakers[0].device_id if speakers else ""

    def default_loopback_id(self) -> str:
        default_speaker = sc.default_speaker()
        if default_speaker is not None:
            for microphone in self.microphone_options():
                if microphone.loopback and microphone.name == default_speaker.name:
                    return microphone.device_id
        loopbacks = [item for item in self.microphone_options() if item.loopback]
        return loopbacks[0].device_id if loopbacks else self.default_microphone_id()

    def get_microphone(self, device_id: str):
        if not device_id:
            return None
        return sc.get_microphone(id=parse_soundcard_device_id(device_id), include_loopback=True)

    def get_speaker(self, device_id: str):
        if not device_id:
            return None
        return sc.get_speaker(id=parse_soundcard_device_id(device_id))


def parse_soundcard_device_id(device_id: str) -> Any:
    value = str(device_id or "")
    if value.isdigit():
        return int(value)
    return value


class TranslationChannel:
    def __init__(self, catalog: DeviceCatalog, settings: ChannelSettings, credentials: Credentials, ui_callback: UiCallback):
        self.catalog = catalog
        self.settings = settings
        self.credentials = credentials
        self.ui_callback = ui_callback

        self._stop_requested = threading.Event()
        self._audio_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=self.settings.max_queue_chunks)
        self._playback_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=self.settings.max_queue_chunks)
        self._worker: threading.Thread | None = None
        self._capture_thread: threading.Thread | None = None
        self._playback_thread: threading.Thread | None = None
        self._local_tts_thread: threading.Thread | None = None
        self._local_tts_queue: queue.Queue[str | None] = queue.Queue(maxsize=48)
        self._input_block_frames = max(160, DEFAULT_INPUT_SAMPLE_RATE * self.settings.chunk_ms // 1000)
        self._last_stats_emit = 0.0
        self._first_audio_sent_at = 0.0
        self._finish_sent = False
        self._voice_hold_until = 0.0
        self._agc_gain = 1.0
        self._noise_profile: np.ndarray | None = None
        self._hp_prev_x = 0.0
        self._playback_tail = np.empty(0, dtype=np.float32)
        self._needs_playback_rejoin = False
        self._last_playback_emit_at = 0.0
        self._latency_armed = False
        self._last_speech_chunk_at = 0.0
        self._last_server_audio_at = 0.0
        self._silence_keepalive_chunk = b"\x00\x00" * self._input_block_frames
        self._speech_preroll_chunks: deque[bytes] = deque(
            maxlen=max(1, (self.settings.pre_roll_ms + max(self.settings.chunk_ms, 1) - 1) // max(self.settings.chunk_ms, 1))
        )
        self._post_speech_silence_until = 0.0
        self._speech_was_active = False
        self._log_lock = threading.Lock()
        self._reconnect_attempts = 0
        self._local_tts_fallback_requested = False
        self._local_tts = None
        self._native_capture: NativeCaptureSession | None = None
        self._native_playback_sessions: list[NativePlaybackSession] = []
        self._native_core = NativeAudioCoreBridge()
        if self.settings.use_local_tts and self.settings.local_tts_voice.strip():
            self._local_tts = CloneTTSSynthesizer(
                self.credentials.app_key,
                self.credentials.access_key,
                cluster=self.settings.local_tts_cluster,
                dns_servers=self.credentials.dns_servers,
                dns_hosts=self.credentials.dns_hosts,
            )

        self.stats = ChannelStats(channel_id=self.settings.channel_id)
        self.stats.capture_backend = self.settings.capture_backend
        self.stats.playback_backend = self.settings.playback_backend

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _any_playback_enabled(self) -> bool:
        return bool(
            (self.settings.playback_enabled and self.settings.playback_device_id.strip())
            or (self.settings.monitor_playback_enabled and self.settings.monitor_playback_device_id.strip())
        )

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_requested.clear()
        self._finish_sent = False
        self._reconnect_attempts = 0
        self._local_tts_fallback_requested = False
        request_timer_resolution()
        self.stats = ChannelStats(channel_id=self.settings.channel_id, session_state="starting", started_at=time.time())
        self.stats.capture_backend = self.settings.capture_backend
        self.stats.playback_backend = self.settings.playback_backend
        self._worker = threading.Thread(target=self._thread_main, name=f"ast-{self.settings.channel_id}", daemon=True)
        self._worker.start()
        self._emit("status", "Engine booting")
        self._maybe_emit_stats(force=True)

    def stop(self) -> None:
        self._stop_requested.set()
        if self._native_capture is not None:
            self._native_capture.close()
            self._native_capture = None
        for session in self._native_playback_sessions:
            session.close()
        self._native_playback_sessions.clear()
        self._enqueue(self._audio_queue, None)
        self._enqueue(self._playback_queue, None)
        self._enqueue(self._local_tts_queue, None)

    def join(self, timeout: float = 3.0) -> None:
        if self._worker is not None:
            self._worker.join(timeout=timeout)

    def _log_path(self) -> Path:
        day = time.strftime("%Y%m%d")
        return LOG_DIR / f"{self.settings.channel_id}-{day}.log"

    def _write_log(self, level: str, message: str, **extra: object) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "channel": self.settings.channel_id,
            "display_name": self.settings.display_name,
            "level": level,
            "message": str(message or ""),
            "session_state": self.stats.session_state,
            "last_status": self.stats.last_status,
            "last_error": self.stats.last_error,
            "log_id": self.stats.log_id,
        }
        if extra:
            entry["extra"] = extra
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with self._log_lock:
                with self._log_path().open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _clear_queue(self, target_queue: queue.Queue[Any]) -> None:
        while True:
            try:
                target_queue.get_nowait()
            except queue.Empty:
                return

    def _prepare_session_cycle(self) -> None:
        self._finish_sent = False
        self._first_audio_sent_at = 0.0
        self._latency_armed = False
        self._last_server_audio_at = 0.0
        self.stats.session_state = "starting" if self._reconnect_attempts == 0 else "reconnecting"
        self.stats.session_started_at = 0.0
        self.stats.log_id = ""
        self._playback_tail = np.empty(0, dtype=np.float32)
        self._needs_playback_rejoin = False
        self._speech_preroll_chunks.clear()
        self._post_speech_silence_until = 0.0
        self._speech_was_active = False
        self._clear_queue(self._audio_queue)
        self._clear_queue(self._playback_queue)
        self._clear_queue(self._local_tts_queue)

    def _reconnect_delay(self, attempt: int) -> float:
        return min(AUTO_RECONNECT_MAX_DELAY_SEC, AUTO_RECONNECT_BASE_DELAY_SEC * (2 ** max(0, attempt - 1)))

    def _sleep_with_stop(self, duration_sec: float) -> bool:
        deadline = time.time() + max(0.0, duration_sec)
        while not self._stop_requested.is_set():
            remaining = deadline - time.time()
            if remaining <= 0:
                return True
            time.sleep(min(0.2, remaining))
        return False

    def _thread_main(self) -> None:
        boost_current_thread_priority()
        if self.settings.capture_enabled:
            self._capture_thread = threading.Thread(target=self._capture_audio, name=f"capture-{self.settings.channel_id}", daemon=True)
            self._capture_thread.start()
        if self._any_playback_enabled():
            self._playback_thread = threading.Thread(target=self._play_audio, name=f"play-{self.settings.channel_id}", daemon=True)
            self._playback_thread.start()
        if self._local_tts is not None and self._any_playback_enabled():
            self._local_tts_thread = threading.Thread(target=self._run_local_tts, name=f"tts-{self.settings.channel_id}", daemon=True)
            self._local_tts_thread.start()

        try:
            while not self._stop_requested.is_set():
                self._prepare_session_cycle()
                try:
                    asyncio.run(self._run_session())
                    if self._stop_requested.is_set():
                        break
                    raise SessionReconnectRequested("AST session ended unexpectedly")
                except SessionReconnectRequested as exc:
                    if self._stop_requested.is_set():
                        break
                    self._reconnect_attempts += 1
                    self.stats.reconnect_attempts = self._reconnect_attempts
                    self.stats.session_state = "reconnecting"
                    self.stats.last_disconnect_reason = str(exc)
                    delay_sec = self._reconnect_delay(self._reconnect_attempts)
                    reconnect_message = (
                        f"{exc}. Reconnecting in {delay_sec:.1f}s "
                        f"({self._reconnect_attempts}/{AUTO_RECONNECT_MAX_ATTEMPTS})"
                    )
                    self.stats.last_status = reconnect_message
                    self.stats.last_error = ""
                    self._write_log(
                        "error",
                        str(exc),
                        reconnecting=True,
                        attempt=self._reconnect_attempts,
                        delay_sec=round(delay_sec, 1),
                    )
                    self._emit("status", reconnect_message)
                    self._maybe_emit_stats(force=True)
                    if self._reconnect_attempts >= AUTO_RECONNECT_MAX_ATTEMPTS or not self._sleep_with_stop(delay_sec):
                        raise RuntimeError(f"{exc}. Auto reconnect limit reached")
                except Exception as exc:  # pragma: no cover - surfaced in UI
                    self.stats.last_error = str(exc)
                    self.stats.session_state = "failed"
                    self._emit("error", f"{self.settings.display_name} failed: {exc}")
                    break
        finally:
            self._stop_requested.set()
            self._enqueue(self._audio_queue, None)
            self._enqueue(self._playback_queue, None)
            self._enqueue(self._local_tts_queue, None)
            if self._capture_thread is not None:
                self._capture_thread.join(timeout=1.5)
            if self._playback_thread is not None:
                self._playback_thread.join(timeout=1.5)
            if self._local_tts_thread is not None:
                self._local_tts_thread.join(timeout=1.5)
            if self.stats.session_state not in {"failed", "finished"}:
                self.stats.session_state = "stopped"
            self.stats.last_status = "Stopped"
            self._emit("status", self.stats.last_status)
            self._maybe_emit_stats(force=True)
            release_timer_resolution()

    def _capture_audio(self) -> None:
        if self.settings.capture_backend == "native":
            try:
                self._capture_audio_native()
                return
            except Exception as exc:  # pragma: no cover - hardware dependent
                self.stats.last_error = str(exc)
                self.stats.native_capture_active = False
                if not self.settings.native_capture_fallback or self._stop_requested.is_set():
                    self._emit("error", f"Native capture failed: {exc}")
                    self.stop()
                    return
                self.stats.native_capture_fallbacks += 1
                self.stats.capture_backend = "python"
                self._emit("status", f"Native capture failed, falling back to Python: {exc}")
                self._maybe_emit_stats(force=True)
        self._capture_audio_python()

    def _capture_audio_native(self) -> None:
        boost_current_thread_priority()
        config = {
            "channel": self.settings.channel_id,
            "device_id": self.settings.capture_device_id,
            "sample_rate": DEFAULT_INPUT_SAMPLE_RATE,
            "chunk_ms": self.settings.chunk_ms,
            "noise_gate_db": self.settings.noise_gate_db,
            "silence_hold_ms": self.settings.silence_hold_ms,
            "pre_roll_ms": self.settings.pre_roll_ms,
            "input_gain": self.settings.input_gain,
            "enable_agc": self.settings.enable_agc,
            "agc_target_dbfs": self.settings.agc_target_dbfs,
            "max_agc_gain": self.settings.max_agc_gain,
            "resampler_quality": self.settings.resampler_quality,
            "vad_mode": self.settings.vad_mode,
            "enable_noise_floor": self.settings.enable_noise_floor,
            "adaptive_chunking": self.settings.adaptive_chunking,
        }
        self._native_capture = self._native_core.start_capture(config)
        self.stats.capture_backend = "native"
        self.stats.native_capture_active = True
        self._emit("status", "Native input capture active")
        try:
            while not self._stop_requested.is_set():
                event = self._native_capture.read_event(timeout=0.2)
                if not event:
                    continue
                event_name = event.get("event")
                if event_name == "audio_chunk":
                    pcm_chunk = event.get("pcm16") or b""
                    if not pcm_chunk:
                        continue
                    now = time.time()
                    level_db = safe_float(event.get("level_db"), -96.0)
                    speech_active = bool(event.get("speech"))
                    self.stats.audio_level_db = level_db
                    self.stats.speech_active = speech_active
                    self._apply_native_metrics(event)
                    speech_latency_threshold_db = max(self.settings.noise_gate_db + 4.0, -42.0)
                    if speech_active and level_db >= speech_latency_threshold_db and now - self._last_speech_chunk_at > 0.85:
                        self._begin_latency_window()
                    if speech_active and level_db >= speech_latency_threshold_db:
                        self._last_speech_chunk_at = now
                    self._enqueue(self._audio_queue, pcm_chunk)
                    self._last_server_audio_at = now
                    self.stats.input_queue_depth = self._audio_queue.qsize()
                    self._maybe_emit_stats()
                elif event_name == "metrics":
                    self._apply_native_metrics(event)
                    self.stats.input_queue_depth = self._audio_queue.qsize()
                    self._maybe_emit_stats()
                elif event_name == "error":
                    raise RuntimeError(str(event.get("message") or "Native capture error"))
        finally:
            if self._native_capture is not None:
                self._native_capture.close()
                self._native_capture = None
            self.stats.native_capture_active = False


    def _apply_native_metrics(self, event: dict[str, object]) -> None:
        self.stats.audio_level_db = safe_float(event.get("level_db"), -96.0)
        self.stats.speech_active = bool(event.get("speech"))
        self.stats.dropped_silent_chunks = int(event.get("dropped_silent_chunks") or 0)
        self.stats.native_vad_score = safe_float(event.get("vad_score"), 0.0)
        self.stats.native_noise_floor_db = safe_float(event.get("noise_floor_db"), -96.0)
        self.stats.native_agc_gain = safe_float(event.get("agc_gain"), 1.0)
        self.stats.native_resampler = str(event.get("resampler") or "")
        emitted_at = event.get("emitted_at_ms")
        if emitted_at is not None:
            try:
                self.stats.native_chunk_latency_ms = max(0.0, time.time() * 1000.0 - float(emitted_at))
            except (TypeError, ValueError):
                self.stats.native_chunk_latency_ms = None

    def _capture_audio_python(self) -> None:
        boost_current_thread_priority()
        self.stats.capture_backend = "python"
        self.stats.native_capture_active = False
        microphone = self.catalog.get_microphone(self.settings.capture_device_id)
        if microphone is None:
            self.stats.last_error = "Input device not found"
            self._emit("error", "Input device not found")
            self.stop()
            return

        self._emit("status", f"Input device: {microphone.name}")
        try:
            with microphone.recorder(
                samplerate=DEFAULT_INPUT_SAMPLE_RATE,
                channels=DEFAULT_INPUT_CHANNELS,
                blocksize=self._input_block_frames,
            ) as recorder:
                while not self._stop_requested.is_set():
                    frames = recorder.record(numframes=self._input_block_frames)
                    if frames is None or frames.size == 0:
                        continue
                    mono = frames.mean(axis=1) if frames.ndim > 1 else frames
                    processed = mono.astype(np.float32)
                    processed, self._hp_prev_x = soft_highpass(processed, self._hp_prev_x)
                    processed = np.clip(processed * self.settings.input_gain, -1.0, 1.0)

                    now = time.time()
                    level_db = samples_to_dbfs(processed)
                    speech_active = level_db >= self.settings.noise_gate_db

                    if self.settings.enable_denoise:
                        processed, self._noise_profile = spectral_denoise(
                            processed,
                            self._noise_profile,
                            self.settings.denoise_strength,
                            learn_noise=not speech_active,
                        )

                    if self.settings.enable_agc:
                        processed, self._agc_gain = apply_agc(
                            processed,
                            self.settings.agc_target_dbfs,
                            self.settings.max_agc_gain,
                            self._agc_gain,
                        )
                        level_db = samples_to_dbfs(processed)

                    speech_active = level_db >= self.settings.noise_gate_db
                    self.stats.speech_active = speech_active
                    self.stats.audio_level_db = level_db
                    pcm_chunk = float_to_pcm16(processed)
                    if not speech_active:
                        self._speech_preroll_chunks.append(pcm_chunk)

                    was_active = self._speech_was_active
                    if speech_active:
                        speech_latency_threshold_db = max(self.settings.noise_gate_db + 4.0, -42.0)
                        if level_db >= speech_latency_threshold_db and now - self._last_speech_chunk_at > 0.85:
                            self._begin_latency_window()
                        if level_db >= speech_latency_threshold_db:
                            self._last_speech_chunk_at = now
                        self._voice_hold_until = now + max(0.0, self.settings.silence_hold_ms / 1000.0)
                        self._post_speech_silence_until = now + (POST_SPEECH_FINALIZE_MS / 1000.0)
                        if self.settings.skip_silence and not was_active and self._speech_preroll_chunks:
                            while self._speech_preroll_chunks:
                                self._enqueue(self._audio_queue, self._speech_preroll_chunks.popleft())

                    if self.settings.skip_silence and now > self._voice_hold_until:
                        self.stats.dropped_silent_chunks += 1
                        if now <= self._post_speech_silence_until:
                            self._enqueue(self._audio_queue, self._silence_keepalive_chunk)
                            self._last_server_audio_at = now
                            self.stats.input_queue_depth = self._audio_queue.qsize()
                            self._speech_was_active = False
                            self._maybe_emit_stats()
                            continue
                        if now - self._last_server_audio_at >= SILENCE_KEEPALIVE_INTERVAL_SEC:
                            self._enqueue(self._audio_queue, self._silence_keepalive_chunk)
                            self._last_server_audio_at = now
                        self.stats.input_queue_depth = self._audio_queue.qsize()
                        self._speech_was_active = False
                        self._maybe_emit_stats()
                        continue
                    self._enqueue(self._audio_queue, pcm_chunk)
                    self._last_server_audio_at = now
                    self.stats.input_queue_depth = self._audio_queue.qsize()
                    self._speech_was_active = speech_active
                    self._maybe_emit_stats()
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.stats.last_error = str(exc)
            self._emit("error", f"Capture failed: {exc}")
            self.stop()

    def _play_audio(self) -> None:
        if self.settings.playback_backend == "native":
            try:
                self._play_audio_native()
                return
            except Exception as exc:  # pragma: no cover - hardware dependent
                self.stats.last_error = str(exc)
                self.stats.playback_backend = "python"
                self._emit("status", f"Native playback failed, falling back to Python: {exc}")
                self._maybe_emit_stats(force=True)
        self._play_audio_python()

    def _play_audio_native(self) -> None:
        boost_current_thread_priority()
        primary_speaker = self.catalog.get_speaker(self.settings.playback_device_id) if self.settings.playback_enabled else None
        monitor_speaker = (
            self.catalog.get_speaker(self.settings.monitor_playback_device_id)
            if self.settings.monitor_playback_enabled and self.settings.monitor_playback_device_id.strip()
            else None
        )
        if primary_speaker is not None and monitor_speaker is not None and primary_speaker.id == monitor_speaker.id:
            monitor_speaker = None
        active_speakers = [speaker for speaker in (primary_speaker, monitor_speaker) if speaker is not None]
        if not active_speakers:
            raise RuntimeError("No playback device available")
        self._native_playback_sessions = [
            self._native_core.start_playback({
                "channel": self.settings.channel_id,
                "device_id": speaker.id,
                "sample_rate": self.settings.target_audio_rate,
                "chunk_ms": self.settings.chunk_ms,
            })
            for speaker in active_speakers
        ]
        session_labels = {id(session): active_speakers[index].name for index, session in enumerate(self._native_playback_sessions)}
        self.stats.playback_active_outputs = len(self._native_playback_sessions)
        self.stats.playback_backend = "native"
        self._emit("status", "Native playback active")
        try:
            while not self._stop_requested.is_set():
                try:
                    chunk = self._playback_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                self.stats.playback_queue_depth = self._playback_queue.qsize()
                native_chunk = self._playback_payload_to_pcm16(chunk)
                for session in list(self._native_playback_sessions):
                    try:
                        session.send_audio(self.settings.channel_id, native_chunk, self.settings.target_audio_rate)
                    except Exception as exc:  # pragma: no cover - hardware dependent
                        label = session_labels.get(id(session), "native output")
                        self._mark_playback_output_failed(label, str(exc))
                        try:
                            session.close()
                        except Exception:
                            pass
                        if session in self._native_playback_sessions:
                            self._native_playback_sessions.remove(session)
                        self.stats.playback_active_outputs = len(self._native_playback_sessions)
                        self._emit("status", f"Native playback output disabled: {label}: {exc}")
                if not self._native_playback_sessions:
                    raise RuntimeError("All native playback outputs failed")
                self._maybe_emit_stats()
        finally:
            for session in self._native_playback_sessions:
                session.close()
            self._native_playback_sessions.clear()

    def _play_audio_python(self) -> None:
        boost_current_thread_priority()
        self.stats.playback_backend = "python"
        primary_speaker = self.catalog.get_speaker(self.settings.playback_device_id) if self.settings.playback_enabled else None
        monitor_speaker = (
            self.catalog.get_speaker(self.settings.monitor_playback_device_id)
            if self.settings.monitor_playback_enabled and self.settings.monitor_playback_device_id.strip()
            else None
        )
        if primary_speaker is not None and monitor_speaker is not None and primary_speaker.id == monitor_speaker.id:
            monitor_speaker = None

        active_speakers = [speaker for speaker in (primary_speaker, monitor_speaker) if speaker is not None]
        if not active_speakers:
            self.stats.last_error = "No playback device available"
            self._emit("error", "No playback device available")
            self.stop()
            return

        output_names = []
        if primary_speaker is not None:
            output_names.append(primary_speaker.name)
        if monitor_speaker is not None:
            output_names.append(f"Monitor: {monitor_speaker.name}")
        self._emit("status", f"Output devices: {' / '.join(output_names)}")
        pending = bytearray()
        prebuffer_ms = self.settings.startup_buffer_ms or self.settings.jitter_buffer_ms
        prebuffer_bytes = self._raw_audio_bytes_for_ms(prebuffer_ms, self.settings.target_audio_rate)
        gap_fill_ms = max(18, min(self.settings.chunk_ms, 42))
        max_gap_fill_ms = max(gap_fill_ms * 3, self.settings.jitter_buffer_ms + 20)
        gap_fill_budget_ms = 0
        tail_samples = max(1, int(self.settings.target_audio_rate * 0.024))
        fanout_slice_frames = max(160, int(self.settings.target_audio_rate * 0.02))
        playback_started = False
        output_queues: list[queue.Queue[np.ndarray | None]] = [queue.Queue(maxsize=96) for _ in active_speakers]
        output_labels = list(output_names)
        output_threads: list[threading.Thread] = []
        output_errors: queue.Queue[dict[str, str]] = queue.Queue()
        self.stats.playback_active_outputs = len(output_queues)

        try:
            for index, speaker in enumerate(active_speakers):
                label = output_labels[index] if index < len(output_labels) else speaker.name
                worker = threading.Thread(
                    target=self._play_output_device,
                    args=(speaker, output_queues[index], fanout_slice_frames, label, output_errors),
                    name=f"play-output-{self.settings.channel_id}-{index}",
                    daemon=True,
                )
                worker.start()
                output_threads.append(worker)
            while True:
                try:
                    chunk = self._playback_queue.get(timeout=0.2)
                except queue.Empty:
                    self._drain_output_errors(output_errors, output_queues, output_labels, fail_when_all=True)
                    if self._stop_requested.is_set():
                        break
                    if playback_started and not pending and self._playback_tail.size and gap_fill_budget_ms < max_gap_fill_ms:
                        fill = make_gap_fill(self._playback_tail, self.settings.target_audio_rate, gap_fill_ms)
                        if fill.size:
                            frame = fill.reshape(-1, 1)
                            self._play_frame_to_outputs(output_queues, frame, fanout_slice_frames)
                            self._playback_tail = fill[-tail_samples:].copy()
                            self._last_playback_emit_at = time.time()
                            self._needs_playback_rejoin = True
                            gap_fill_budget_ms += gap_fill_ms
                            self.stats.playback_gap_fills += 1
                            self.stats.playback_gap_fill_ms += gap_fill_ms
                            self._maybe_emit_stats()
                    continue

                if chunk is None:
                    self._drain_output_errors(output_errors, output_queues, output_labels, fail_when_all=False)
                    break

                pending.extend(chunk)
                self.stats.playback_queue_depth = self._playback_queue.qsize()

                if not playback_started and len(pending) < prebuffer_bytes and not self._stop_requested.is_set():
                    self._maybe_emit_stats()
                    continue

                playback_started = True
                samples, consumed = self._decode_raw_audio(pending)
                if consumed <= 0:
                    continue
                del pending[:consumed]
                if samples.size:
                    if self._needs_playback_rejoin and self._playback_tail.size:
                        samples = crossfade_rejoin(self._playback_tail, samples, self.settings.target_audio_rate)
                        self.stats.playback_rejoins += 1
                        self._needs_playback_rejoin = False
                    gap_fill_budget_ms = 0
                    self._playback_tail = samples[-tail_samples:].copy()
                    self._last_playback_emit_at = time.time()
                    frame = samples.reshape(-1, 1)
                    self._play_frame_to_outputs(output_queues, frame, fanout_slice_frames)
                self._drain_output_errors(output_errors, output_queues, output_labels, fail_when_all=True)
                self._maybe_emit_stats()
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.stats.last_error = str(exc)
            self._emit("error", f"Playback failed: {exc}")
            self.stop()
        finally:
            for output_queue in output_queues:
                if output_queue is not None:
                    self._enqueue(output_queue, None)
            for worker in output_threads:
                worker.join(timeout=1.0)

    def _play_output_device(
        self,
        speaker: Any,
        frame_queue: queue.Queue[np.ndarray | None],
        blocksize: int,
        label: str,
        error_queue: queue.Queue[dict[str, str]],
    ) -> None:
        boost_current_thread_priority()
        try:
            with speaker.player(
                samplerate=self.settings.target_audio_rate,
                channels=1,
                blocksize=blocksize,
            ) as player:
                while True:
                    try:
                        frame = frame_queue.get(timeout=0.2)
                    except queue.Empty:
                        if self._stop_requested.is_set():
                            break
                        continue
                    if frame is None:
                        break
                    if frame.size:
                        player.play(frame)
        except Exception as exc:  # pragma: no cover - hardware dependent
            error_queue.put_nowait({"label": label, "error": str(exc)})

    def _mark_playback_output_failed(self, label: str, message: str) -> None:
        entry = f"{label}: {message}"
        self.stats.playback_output_failures += 1
        if entry not in self.stats.playback_failed_outputs:
            self.stats.playback_failed_outputs.append(entry)
        self.stats.last_error = f"Playback output failed: {entry}"

    def _drain_output_errors(
        self,
        error_queue: queue.Queue[dict[str, str]],
        output_queues: list[queue.Queue[np.ndarray | None] | None],
        output_labels: list[str],
        fail_when_all: bool,
    ) -> None:
        drained = False
        while True:
            try:
                error = error_queue.get_nowait()
            except queue.Empty:
                break
            drained = True
            label = str(error.get("label") or "output")
            message = str(error.get("error") or "playback output failed")
            self._mark_playback_output_failed(label, message)
            for index, existing_label in enumerate(output_labels):
                if existing_label == label and index < len(output_queues):
                    output_queues[index] = None
            self.stats.playback_active_outputs = sum(1 for item in output_queues if item is not None)
            self._emit("status", f"Playback output disabled: {label}: {message}")
        if drained:
            self._maybe_emit_stats(force=True)
        if fail_when_all and output_queues and not any(item is not None for item in output_queues):
            raise RuntimeError("All playback outputs failed")

    def _play_frame_to_outputs(
        self,
        output_queues: list[queue.Queue[np.ndarray | None] | None],
        frame: np.ndarray,
        slice_frames: int,
    ) -> None:
        if not output_queues or frame.size == 0:
            return
        step = max(1, slice_frames)
        for start in range(0, frame.shape[0], step):
            chunk = np.ascontiguousarray(frame[start : start + step], dtype=np.float32)
            for output_queue in output_queues:
                if output_queue is None:
                    continue
                if not self._enqueue_audio_output(output_queue, chunk):
                    return

    def _enqueue_audio_output(self, target_queue: queue.Queue[np.ndarray | None], item: np.ndarray | None) -> bool:
        if item is None:
            self._enqueue(target_queue, None)
            return True
        while not self._stop_requested.is_set():
            try:
                target_queue.put(item, timeout=0.2)
                return True
            except queue.Full:
                continue
        return False

    def _run_local_tts(self) -> None:
        boost_current_thread_priority()
        while not self._stop_requested.is_set():
            try:
                text = self._local_tts_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if text is None:
                break
            if self._local_tts is None:
                continue
            try:
                audio_bytes = self._local_tts.synthesize_pcm(
                    text=text,
                    voice_type=self.settings.local_tts_voice,
                    sample_rate=self.settings.target_audio_rate,
                    speed_ratio=self.settings.local_tts_speed,
                )
            except VoiceCloneError as exc:
                self.stats.external_tts_failures += 1
                self._emit("status", f"Clone TTS failed: {exc}")
                self._maybe_emit_stats(force=True)
                if not self._local_tts_fallback_requested:
                    self._local_tts_fallback_requested = True
                    self._emit("local_tts_failed", str(exc))
                    self.stop()
                    break
                continue

            if audio_bytes:
                self.stats.external_tts_jobs += 1
                self.stats.received_audio_bytes += len(audio_bytes)
                self._enqueue_playback_audio(audio_bytes)
                if self.stats.first_audio_latency_ms is None and self._first_audio_sent_at:
                    self._mark_latency("first_audio_latency_ms")
                self._maybe_emit_stats(force=True)

    async def _run_session(self) -> None:
        network_path = "system proxy" if use_system_proxy() else "direct"
        self._emit("status", f"AST network path: {network_path}")
        dns_hosts = target_hosts_for_url(self.credentials.ws_url, self.credentials.dns_hosts)
        if dns_hosts and self.credentials.dns_servers:
            self._emit(
                "status",
                f"AST custom DNS: {' / '.join(self.credentials.dns_servers)} for {' / '.join(dns_hosts)}",
            )
        if self._any_playback_enabled() and not self.settings.use_local_tts:
            sample_kind = "float32" if self._remote_pcm_bytes_per_sample() == 4 else "int16"
            self._emit("status", f"AST playback decode: pcm/{sample_kind} @ {self.settings.target_audio_rate}Hz")
        self._maybe_emit_stats(force=True)
        headers = {
            "X-Api-App-Key": self.credentials.app_key,
            "X-Api-Access-Key": self.credentials.access_key,
            "X-Api-Resource-Id": self.credentials.resource_id,
            "X-Api-Connect-Id": str(uuid.uuid4()),
        }

        try:
            with dns_override(dns_hosts, self.credentials.dns_servers):
                async with websockets.connect(
                    self.credentials.ws_url,
                    additional_headers=headers,
                    max_size=32 * 1024 * 1024,
                    compression=None,
                    proxy=True if use_system_proxy() else None,
                    open_timeout=15,
                    ping_interval=20,
                    ping_timeout=20,
                ) as websocket:
                    self.stats.log_id = websocket.response.headers.get("X-Tt-Logid", "")
                    self.stats.last_status = "Connected to AST"
                    self._emit("status", f"Connected to AST / logid={self.stats.log_id or 'N/A'}")
                    self._maybe_emit_stats(force=True)

                    session_id = str(uuid.uuid4())
                    await websocket.send(self._build_start_request(session_id).SerializeToString())
                    started = await self._wait_for_session_started(websocket)
                    if not started:
                        raise SessionReconnectRequested("AST did not confirm the session start")

                    sender = asyncio.create_task(self._sender_loop(websocket, session_id))
                    receiver = asyncio.create_task(self._receiver_loop(websocket))
                    try:
                        await asyncio.gather(sender, receiver)
                    finally:
                        for task in (sender, receiver):
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(sender, receiver, return_exceptions=True)
        except SessionReconnectRequested:
            raise
        except (asyncio.TimeoutError, OSError, websockets.ConnectionClosed) as exc:
            raise SessionReconnectRequested(f"AST connection dropped: {exc}") from exc

    async def _wait_for_session_started(self, websocket) -> bool:
        while True:
            response = await self._receive_proto(websocket)
            if response is None:
                return False
            if response.event == Type.SessionStarted:
                self.stats.session_state = "running"
                self.stats.session_started_at = time.time()
                self.stats.last_error = ""
                self.stats.last_disconnect_reason = ""
                if self._reconnect_attempts:
                    self.stats.reconnect_successes += 1
                    self.stats.last_status = f"SessionStarted / recovered after {self._reconnect_attempts} reconnect attempt(s)"
                    self._reconnect_attempts = 0
                    self.stats.reconnect_attempts = 0
                else:
                    self.stats.last_status = "SessionStarted"
                self._emit("status", self.stats.last_status)
                self._maybe_emit_stats(force=True)
                return True
            self._handle_response(response)
            if response.event == Type.SessionFailed:
                message = response.response_meta.Message or "Session setup failed"
                self.stats.last_status = message
                self.stats.last_disconnect_reason = message
                raise SessionReconnectRequested(message)

    async def _sender_loop(self, websocket, session_id: str) -> None:
        while True:
            chunk = await asyncio.to_thread(self._next_audio_chunk)
            if chunk is None:
                break
            if self._latency_armed and not self._first_audio_sent_at:
                self._first_audio_sent_at = time.time()
                self._latency_armed = False
            self.stats.sent_chunks += 1
            self.stats.sent_audio_bytes += len(chunk)
            self.stats.input_queue_depth = self._audio_queue.qsize()
            try:
                await websocket.send(self._build_audio_request(session_id, chunk).SerializeToString())
            except websockets.ConnectionClosed as exc:
                raise SessionReconnectRequested(f"Audio send failed: {exc}") from exc
            self._maybe_emit_stats()

        if not self._finish_sent:
            self._finish_sent = True
            await websocket.send(self._build_finish_request(session_id).SerializeToString())
            self.stats.last_status = "FinishSession sent"
            self._emit("status", self.stats.last_status)
            self._maybe_emit_stats(force=True)

    async def _receiver_loop(self, websocket) -> None:
        while True:
            response = await self._receive_proto(websocket)
            if response is None:
                return
            self._handle_response(response)
            if response.event == Type.SessionFinished:
                self.stats.session_state = "finished"
                self.stats.last_status = "SessionFinished"
                self.stats.last_disconnect_reason = "SessionFinished"
                if not self._stop_requested.is_set():
                    raise SessionReconnectRequested("AST session finished")
                self._maybe_emit_stats(force=True)
                return
            if response.event == Type.SessionFailed:
                message = response.response_meta.Message or "Session failed"
                self.stats.session_state = "reconnecting"
                self.stats.last_status = message
                self.stats.last_disconnect_reason = message
                self._maybe_emit_stats(force=True)
                if not self._stop_requested.is_set():
                    raise SessionReconnectRequested(message)
                return

    async def _receive_proto(self, websocket) -> TranslateResponse | None:
        while True:
            try:
                payload = await websocket.recv()
            except websockets.ConnectionClosed as exc:
                message = f"WebSocket closed ({exc.code})"
                self.stats.last_status = message
                self.stats.last_disconnect_reason = message
                self._emit("status", message)
                if self._stop_requested.is_set():
                    return None
                raise SessionReconnectRequested(message) from exc

            if isinstance(payload, str):
                self._emit("status", f"Text message received: {payload}")
                continue

            response = TranslateResponse()
            response.ParseFromString(payload)
            return response

    def _handle_response(self, response: TranslateResponse) -> None:
        self.stats.last_event = event_name(response.event)

        if response.event == Type.SourceSubtitleStart:
            self._mark_latency("first_source_latency_ms")
            self._emit("source_partial", "", speaker_changed=response.spk_chg)
            self._maybe_emit_stats()
            return

        if response.event == Type.SourceSubtitleResponse:
            self.stats.source_partials += 1
            self.stats.last_source_text = response.text
            self._mark_latency("first_source_latency_ms")
            self._emit("source_partial", response.text)
            self._maybe_emit_stats()
            return

        if response.event == Type.SourceSubtitleEnd:
            self.stats.source_sentences += 1
            self.stats.last_source_text = response.text
            self._emit("source_final", response.text, start_ms=response.start_time, end_ms=response.end_time)
            self._maybe_emit_stats()
            return

        if response.event == Type.TranslationSubtitleStart:
            self._mark_latency("first_translation_latency_ms")
            self._emit("target_partial", "", speaker_changed=response.spk_chg)
            self._maybe_emit_stats()
            return

        if response.event == Type.TranslationSubtitleResponse:
            self.stats.translation_partials += 1
            self.stats.last_target_text = response.text
            self._mark_latency("first_translation_latency_ms")
            self._emit("target_partial", response.text)
            self._maybe_emit_stats()
            return

        if response.event == Type.TranslationSubtitleEnd:
            self.stats.translation_sentences += 1
            self.stats.last_target_text = response.text
            self._emit("target_final", response.text, start_ms=response.start_time, end_ms=response.end_time)
            if self._local_tts is not None and self._any_playback_enabled() and response.text.strip():
                self._enqueue(self._local_tts_queue, response.text.strip())
            self._maybe_emit_stats()
            return

        if response.event == Type.TTSResponse:
            if not self._any_playback_enabled():
                self._maybe_emit_stats()
                return
            if self.settings.use_local_tts:
                self._maybe_emit_stats()
                return
            if response.data:
                self.stats.tts_chunks += 1
                self.stats.received_audio_bytes += len(response.data)
                self.stats.playback_queue_depth = self._playback_queue.qsize()
                self._mark_latency("first_audio_latency_ms")
                self._enqueue_playback_audio(bytes(response.data))
            self._maybe_emit_stats()
            return

        if response.event == Type.AudioMuted:
            self._emit("status", f"Input muted / total {response.muted_duration_ms} ms")
            self._maybe_emit_stats()
            return

        if response.event == Type.UsageResponse:
            self.stats.usage_updates += 1
            self._emit("status", self._format_billing(response))
            self._maybe_emit_stats()
            return

        if response.event in (Type.SessionStarted, Type.SessionFinished):
            self._emit("status", event_name(response.event))
            self._maybe_emit_stats()
            return

        if response.event == Type.TTSSentenceStart:
            self._emit("status", "Translated voice started")
            self._maybe_emit_stats()
            return

        if response.event == Type.TTSSentenceEnd:
            self._emit("status", "Translated voice sentence completed")
            self._maybe_emit_stats()
            return

        self._emit("status", f"Event: {event_name(response.event)}")
        self._maybe_emit_stats()

    def _format_billing(self, response: TranslateResponse) -> str:
        billing = response.response_meta.Billing
        parts: list[str] = []
        for item in billing.Items:
            parts.append(f"{item.Unit}={item.Quantity:.1f}")
        if billing.DurationMsec:
            parts.append(f"duration={billing.DurationMsec}ms")
        return "Usage: " + (", ".join(parts) if parts else "No detailed counters")

    def _mark_latency(self, attr_name: str) -> None:
        if not self._first_audio_sent_at or getattr(self.stats, attr_name) is not None:
            return
        latency_ms = round((time.time() - self._first_audio_sent_at) * 1000, 1)
        setattr(self.stats, attr_name, latency_ms)

    def _begin_latency_window(self) -> None:
        self._latency_armed = True
        self._first_audio_sent_at = 0.0
        self.stats.first_source_latency_ms = None
        self.stats.first_translation_latency_ms = None
        self.stats.first_audio_latency_ms = None

    def _next_audio_chunk(self) -> bytes | None:
        while True:
            if self._stop_requested.is_set() and self._audio_queue.empty():
                return None
            try:
                return self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

    def _emit(self, kind: str, text: str, **extra: object) -> None:
        if kind == "status" and text:
            self.stats.last_status = text
        elif kind == "error" and text:
            self.stats.last_error = text
        payload = {
            "channel": self.settings.channel_id,
            "kind": kind,
            "text": text,
            "timestamp": time.time(),
        }
        payload.update(extra)
        if kind in {"status", "error"}:
            self._write_log(kind, text, **extra)
        self.ui_callback(payload)

    def _maybe_emit_stats(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_stats_emit < 0.35:
            return
        self._last_stats_emit = now
        self.stats.input_queue_depth = self._audio_queue.qsize()
        self.stats.playback_queue_depth = self._playback_queue.qsize()
        self._emit("stats", "", stats=self.stats.snapshot())

    def _enqueue(self, target_queue: queue.Queue[Any], item: Any) -> None:
        try:
            target_queue.put_nowait(item)
            return
        except queue.Full:
            pass

        try:
            target_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            target_queue.put_nowait(item)
        except queue.Full:
            pass

    def _enqueue_playback_audio(self, payload: bytes) -> bool:
        payload = self._limit_playback_payload(payload)
        while not self._stop_requested.is_set():
            try:
                self._playback_queue.put(payload, timeout=0.2)
                self.stats.playback_queue_depth = self._playback_queue.qsize()
                return True
            except queue.Full:
                continue
        return False

    def _limit_playback_payload(self, payload: bytes) -> bytes:
        if not payload:
            return payload
        frame_bytes = 2 if self.settings.use_local_tts else self._remote_pcm_bytes_per_sample()
        usable = len(payload) - (len(payload) % frame_bytes)
        if usable <= 0:
            return payload
        raw = payload[:usable]
        tail = payload[usable:]
        if frame_bytes == 4:
            samples = np.frombuffer(raw, dtype=np.float32)
            limited, engaged, reduction_db, peak_dbfs = apply_playback_limiter(samples)
            encoded = limited.astype(np.float32).tobytes()
        else:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            limited, engaged, reduction_db, peak_dbfs = apply_playback_limiter(samples)
            encoded = float_to_pcm16(limited)

        self.stats.playback_peak_dbfs = peak_dbfs
        if engaged:
            self.stats.playback_limiter_events += 1
            self.stats.playback_limiter_reduction_db = reduction_db
        return encoded + tail

    def _playback_payload_to_pcm16(self, payload: bytes) -> bytes:
        if not payload:
            return payload
        if self.settings.use_local_tts or self._remote_pcm_bytes_per_sample() == 2:
            usable = len(payload) - (len(payload) % 2)
            return payload[:usable]
        frame_bytes = 4
        usable = len(payload) - (len(payload) % frame_bytes)
        if usable <= 0:
            return b""
        samples = np.frombuffer(payload[:usable], dtype=np.float32)
        return float_to_pcm16(samples)

    def _raw_audio_bytes_for_ms(self, duration_ms: int, sample_rate: int) -> int:
        if self.settings.use_local_tts:
            bytes_per_sample = 2
        else:
            bytes_per_sample = self._remote_pcm_bytes_per_sample()
        return max(bytes_per_sample, int(sample_rate * duration_ms / 1000) * bytes_per_sample)

    def _decode_raw_audio(self, raw_buffer: bytearray) -> tuple[np.ndarray, int]:
        if self.settings.use_local_tts:
            frame_bytes = 2
            usable = len(raw_buffer) - (len(raw_buffer) % frame_bytes)
            if usable <= 0:
                return np.empty(0, dtype=np.float32), 0
            samples = np.frombuffer(bytes(raw_buffer[:usable]), dtype=np.int16).astype(np.float32) / 32768.0
            return samples, usable

        frame_bytes = self._remote_pcm_bytes_per_sample()
        usable = len(raw_buffer) - (len(raw_buffer) % frame_bytes)
        if usable <= 0:
            return np.empty(0, dtype=np.float32), 0
        if frame_bytes == 4:
            samples = np.frombuffer(bytes(raw_buffer[:usable]), dtype=np.float32).astype(np.float32, copy=False)
        else:
            samples = np.frombuffer(bytes(raw_buffer[:usable]), dtype=np.int16).astype(np.float32) / 32768.0
        return samples, usable

    def _remote_pcm_bytes_per_sample(self) -> int:
        if DEFAULT_TARGET_AUDIO_FORMAT != "pcm":
            return 2
        # Volcengine AST PCM uses int16 at 16kHz and float32 at 24kHz.
        return 4 if self.settings.target_audio_rate >= 24000 else 2

    def _build_start_request(self, session_id: str) -> TranslateRequest:
        effective_mode = "s2t" if self.settings.use_local_tts else self.settings.mode
        request = TranslateRequest()
        request.request_meta.SessionID = session_id
        request.event = Type.StartSession
        request.user.uid = os.getenv("USERNAME", "local-user")
        request.user.did = platform.node()
        request.user.platform = platform.platform()
        request.user.sdk_version = "nebula-interp-v2"
        request.source_audio.format = "wav"
        request.source_audio.codec = "raw"
        request.source_audio.rate = DEFAULT_INPUT_SAMPLE_RATE
        request.source_audio.bits = DEFAULT_INPUT_BITS
        request.source_audio.channel = DEFAULT_INPUT_CHANNELS
        request.target_audio.format = DEFAULT_TARGET_AUDIO_FORMAT
        request.target_audio.rate = self.settings.target_audio_rate
        request.request.mode = effective_mode
        request.request.source_language = self.settings.source_language
        request.request.target_language = self.settings.target_language
        if self.settings.context_prompt.strip():
            request.request.corpus.context = self.settings.context_prompt.strip()
        if self.settings.hot_words:
            request.request.corpus.hot_words_list.extend([item for item in self.settings.hot_words if item.strip()])
        if self.settings.correct_words:
            request.request.corpus.correct_words = json.dumps(self.settings.correct_words, ensure_ascii=False)
        if self.settings.glossary:
            for key, value in self.settings.glossary.items():
                if key.strip() and value.strip():
                    request.request.corpus.glossary_list[key.strip()] = value.strip()
        if self.settings.speaker_id.strip():
            request.request.speaker_id = self.settings.speaker_id.strip()
        return request

    def _build_audio_request(self, session_id: str, chunk: bytes) -> TranslateRequest:
        request = TranslateRequest()
        request.request_meta.SessionID = session_id
        request.event = Type.TaskRequest
        request.source_audio.binary_data = chunk
        return request

    def _build_finish_request(self, session_id: str) -> TranslateRequest:
        request = TranslateRequest()
        request.request_meta.SessionID = session_id
        request.event = Type.FinishSession
        return request
