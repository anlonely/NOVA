from __future__ import annotations

import base64
import json
import os
import socket
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from custom_dns import dns_override, parse_dns_hosts, parse_dns_servers, target_hosts_for_url

VOICE_CLONE_RESOURCE_ID = "seed-icl-2.0"
VOICE_CLONE_TRAIN_RESOURCE_IDS = ("seed-icl-2.0", "seed-icl-1.0")
VOICE_CLONE_SYNTH_RESOURCE_IDS = ("seed-icl-2.0", "seed-icl-1.0")
VOICE_CLONE_BILLING_RESOURCE_ID = "volc.megatts.default"
VOICE_CLONE_UPLOAD_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/audio/upload"
VOICE_CLONE_STATUS_URL = "https://openspeech.bytedance.com/api/v1/mega_tts/status"
TTS_HTTP_URL = "https://openspeech.bytedance.com/api/v1/tts"

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".m4a", ".aac", ".pcm"}
VOICE_LANGUAGE_CODES = {
    "zh": 0,
    "en": 1,
    "ja": 2,
    "es": 3,
    "id": 4,
    "pt": 5,
}


class VoiceCloneError(RuntimeError):
    pass


def use_system_proxy() -> bool:
    return str(os.getenv("NOVA_USE_SYSTEM_PROXY", "")).strip().lower() in {"1", "true", "yes", "on"}


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    dns_servers: tuple[str, ...] = (),
    dns_hosts: tuple[str, ...] = (),
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        opener = urllib.request.build_opener() if use_system_proxy() else urllib.request.build_opener(urllib.request.ProxyHandler({}))
        target_hosts = target_hosts_for_url(url, dns_hosts)
        with dns_override(target_hosts, dns_servers):
            with opener.open(request, timeout=90) as response:
                raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise VoiceCloneError(f"HTTP {exc.code}: {body or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise VoiceCloneError(f"Network error: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise VoiceCloneError("Request timed out while waiting for the voice service.") from exc

    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise VoiceCloneError(f"Invalid JSON response: {raw[:200]}") from exc

    base_resp = data.get("BaseResp") or {}
    status_code = int(base_resp.get("StatusCode", 0) or 0)
    if status_code != 0:
        raise VoiceCloneError(base_resp.get("StatusMessage") or f"Voice clone request failed with code {status_code}")
    return data


def _access_headers(access_token: str, resource_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer; {access_token}",
        "Resource-Id": resource_id,
    }


def detect_audio_format(audio_path: str) -> str:
    suffix = Path(audio_path).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise VoiceCloneError(f"Unsupported audio format: {suffix or 'unknown'}")
    return suffix.lstrip(".")


def infer_voice_language(text: str) -> str:
    sample = str(text or "")
    for char in sample:
        if "\u4e00" <= char <= "\u9fff":
            return "zh"
    return "en"


class VoiceCloneManager:
    def __init__(
        self,
        app_id: str,
        access_token: str,
        resource_id: str = "",
        fallback_resource_ids: tuple[str, ...] = VOICE_CLONE_TRAIN_RESOURCE_IDS,
        dns_servers: tuple[str, ...] = (),
        dns_hosts: tuple[str, ...] = (),
    ) -> None:
        self.app_id = str(app_id or "").strip()
        self.access_token = str(access_token or "").strip()
        primary = str(resource_id or "").strip()
        candidates = [primary] if primary else []
        candidates.extend(item for item in fallback_resource_ids if item and item not in candidates)
        self.resource_ids = tuple(candidates) or VOICE_CLONE_TRAIN_RESOURCE_IDS
        self.dns_servers = parse_dns_servers(dns_servers)
        self.dns_hosts = parse_dns_hosts(dns_hosts)

    def _require_credentials(self) -> None:
        if not self.app_id or not self.access_token:
            raise VoiceCloneError("App ID and Access Token are required.")

    def _request_with_fallback(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: VoiceCloneError | None = None
        for resource_id in self.resource_ids:
            try:
                return _post_json(
                    url,
                    payload,
                    _access_headers(self.access_token, resource_id),
                    self.dns_servers,
                    self.dns_hosts,
                )
            except VoiceCloneError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise VoiceCloneError("No voice clone resource ID configured.")

    def upload_training_sample(
        self,
        speaker_id: str,
        audio_path: str,
        language_code: str = "zh",
        reference_text: str = "",
        enable_audio_denoise: bool = False,
        denoise_model_id: str = "SpeechInpaintingV2",
        enable_mss: bool = False,
        demo_text: str = "",
        model_type: int = 5,
    ) -> dict[str, Any]:
        self._require_credentials()
        if not speaker_id.strip():
            raise VoiceCloneError("Speaker ID is required.")
        if not audio_path.strip():
            raise VoiceCloneError("Audio sample path is required.")

        path = Path(audio_path).expanduser()
        if not path.exists() or not path.is_file():
            raise VoiceCloneError(f"Sample file not found: {path}")

        audio_format = detect_audio_format(str(path))
        raw = path.read_bytes()
        if not raw:
            raise VoiceCloneError("Sample file is empty.")
        if len(raw) > 10 * 1024 * 1024:
            raise VoiceCloneError("Sample file exceeds the 10MB upload limit.")

        extra_params = {
            "enable_audio_denoise": bool(enable_audio_denoise),
            "voice_clone_denoise_model_id": denoise_model_id or "SpeechInpaintingV2",
            "voice_clone_enable_mss": bool(enable_mss),
        }
        if demo_text.strip():
            extra_params["demo_text"] = demo_text.strip()

        payload: dict[str, Any] = {
            "appid": self.app_id,
            "speaker_id": speaker_id.strip(),
            "audios": [
                {
                    "audio_bytes": base64.b64encode(raw).decode("ascii"),
                    "audio_format": audio_format,
                    **({"text": reference_text.strip()} if reference_text.strip() else {}),
                }
            ],
            "source": 2,
            "language": VOICE_LANGUAGE_CODES.get(language_code, 0),
            "model_type": int(model_type),
            "extra_params": json.dumps(extra_params, ensure_ascii=False),
        }
        return self._request_with_fallback(VOICE_CLONE_UPLOAD_URL, payload)

    def query_status(self, speaker_id: str) -> dict[str, Any]:
        self._require_credentials()
        if not speaker_id.strip():
            raise VoiceCloneError("Speaker ID is required.")
        payload = {"appid": self.app_id, "speaker_id": speaker_id.strip()}
        return self._request_with_fallback(VOICE_CLONE_STATUS_URL, payload)


class CloneTTSSynthesizer:
    def __init__(
        self,
        app_id: str,
        access_token: str,
        cluster: str = "volcano_icl",
        resource_id: str = VOICE_CLONE_RESOURCE_ID,
        fallback_resource_ids: tuple[str, ...] = VOICE_CLONE_SYNTH_RESOURCE_IDS,
        dns_servers: tuple[str, ...] = (),
        dns_hosts: tuple[str, ...] = (),
    ) -> None:
        self.app_id = str(app_id or "").strip()
        self.access_token = str(access_token or "").strip()
        self.cluster = str(cluster or "volcano_icl").strip() or "volcano_icl"
        primary = str(resource_id or "").strip()
        candidates = [primary] if primary else []
        candidates.extend(item for item in fallback_resource_ids if item and item not in candidates)
        self.resource_ids = tuple(candidates) or VOICE_CLONE_SYNTH_RESOURCE_IDS
        self.dns_servers = parse_dns_servers(dns_servers)
        self.dns_hosts = parse_dns_hosts(dns_hosts)

    def _synthesize_with_fallback(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: VoiceCloneError | None = None
        for resource_id in self.resource_ids:
            try:
                return _post_json(
                    TTS_HTTP_URL,
                    payload,
                    {
                        "Authorization": f"Bearer; {self.access_token}",
                        "Resource-Id": resource_id,
                    },
                    self.dns_servers,
                    self.dns_hosts,
                )
            except VoiceCloneError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise VoiceCloneError("No voice clone synthesis resource ID configured.")

    def synthesize_pcm(
        self,
        text: str,
        voice_type: str,
        sample_rate: int = 16000,
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
        enable_clone_opt: bool = True,
        explicit_language: str = "",
    ) -> bytes:
        if not self.app_id or not self.access_token:
            raise VoiceCloneError("App ID and Access Token are required.")
        if not voice_type.strip():
            raise VoiceCloneError("Voice type / speaker ID is required.")
        cleaned = str(text or "").strip()
        if not cleaned:
            return b""
        resolved_language = str(explicit_language or "").strip() or infer_voice_language(cleaned)

        audio_payload: dict[str, Any] = {
            "voice_type": voice_type.strip(),
            "encoding": "pcm",
            "rate": int(sample_rate),
            "speed_ratio": float(speed_ratio),
            "volume_ratio": float(volume_ratio),
            "clone_voice_opt": "1" if enable_clone_opt else "0",
        }
        if resolved_language in VOICE_LANGUAGE_CODES:
            audio_payload["explicit_language"] = resolved_language

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.access_token,
                "cluster": self.cluster,
            },
            "user": {
                "uid": os.getenv("USERNAME", "nova-local"),
            },
            "audio": audio_payload,
            "request": {
                "reqid": str(uuid.uuid4()),
                "operation": "query",
                "text": cleaned[:1024],
            },
        }
        data = self._synthesize_with_fallback(payload)
        audio_data = data.get("data") or ""
        if not audio_data:
            raise VoiceCloneError(data.get("message") or "Empty TTS response.")
        try:
            return base64.b64decode(audio_data)
        except Exception as exc:
            raise VoiceCloneError("Invalid TTS audio payload.") from exc
