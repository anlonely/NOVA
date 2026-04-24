from __future__ import annotations

import asyncio
import json
import time
import uuid
import wave
from collections import defaultdict
from pathlib import Path

import numpy as np
import websockets

from ast_bridge import DEFAULT_RESOURCE_ID, use_system_proxy
from custom_dns import dns_override, parse_dns_hosts, parse_dns_servers, target_hosts_for_url
from paths import get_app_root
from python_protogen.common.events_pb2 import Type
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest, TranslateResponse

ROOT = get_app_root()
CONFIG_PATH = ROOT / "config.local.json"
SAMPLE_AUDIO_PATH = ROOT / ".downloads" / "ast_python" / "ast_python" / "test_audio.wav"
OUTPUT_DIR = ROOT / "output"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    app_key = data.get("app_key", "").strip()
    access_key = data.get("access_key", "").strip()
    if not app_key or not access_key:
        raise RuntimeError("config.local.json is missing app_key or access_key")
    network = data.get("network", {})
    return {
        "app_key": app_key,
        "access_key": access_key,
        "resource_id": data.get("resource_id", DEFAULT_RESOURCE_ID).strip() or DEFAULT_RESOURCE_ID,
        "ws_url": data.get("ws_url", "wss://openspeech.bytedance.com/api/v4/ast/v2/translate").strip()
        or "wss://openspeech.bytedance.com/api/v4/ast/v2/translate",
        "dns_servers": parse_dns_servers(network.get("dns_servers")),
        "dns_hosts": parse_dns_hosts(network.get("dns_hosts")),
    }


def read_audio_chunks(chunk_size: int = 3200) -> list[bytes]:
    if not SAMPLE_AUDIO_PATH.exists():
        raise FileNotFoundError(f"Missing sample audio: {SAMPLE_AUDIO_PATH}")
    chunks: list[bytes] = []
    with SAMPLE_AUDIO_PATH.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
    return chunks


def build_start_request(session_id: str) -> TranslateRequest:
    request = TranslateRequest()
    request.request_meta.SessionID = session_id
    request.event = Type.StartSession
    request.user.uid = "codex-smoke-test"
    request.user.did = "codex-smoke-test"
    request.source_audio.format = "wav"
    request.source_audio.rate = 16000
    request.source_audio.bits = 16
    request.source_audio.channel = 1
    request.target_audio.format = "pcm"
    request.target_audio.rate = 24000
    request.request.mode = "s2s"
    request.request.source_language = "zh"
    request.request.target_language = "en"
    return request


def build_audio_request(session_id: str, chunk: bytes) -> TranslateRequest:
    request = TranslateRequest()
    request.request_meta.SessionID = session_id
    request.event = Type.TaskRequest
    request.source_audio.binary_data = chunk
    return request


def build_finish_request(session_id: str) -> TranslateRequest:
    request = TranslateRequest()
    request.request_meta.SessionID = session_id
    request.event = Type.FinishSession
    return request


def parse_response(payload: bytes) -> TranslateResponse:
    response = TranslateResponse()
    response.ParseFromString(payload)
    return response


def save_pcm_float32_as_wav(raw_audio: bytes, path: Path) -> None:
    if not raw_audio:
        return
    samples = np.frombuffer(raw_audio, dtype=np.float32)
    clipped = np.clip(samples, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm16.tobytes())


async def main() -> None:
    config = load_config()
    chunks = read_audio_chunks()
    session_id = str(uuid.uuid4())
    connect_id = str(uuid.uuid4())
    headers = {
        "X-Api-App-Key": config["app_key"],
        "X-Api-Access-Key": config["access_key"],
        "X-Api-Resource-Id": config["resource_id"],
        "X-Api-Connect-Id": connect_id,
    }

    print("Starting AST smoke test...")
    print(f"Sample audio: {SAMPLE_AUDIO_PATH}")
    print(f"Chunk count: {len(chunks)}")
    print(f"Proxy mode: {'system proxy' if use_system_proxy() else 'direct'}")
    dns_hosts = target_hosts_for_url(config["ws_url"], config["dns_hosts"])
    if dns_hosts and config["dns_servers"]:
        print(f"Custom DNS: {' / '.join(config['dns_servers'])} for {' / '.join(dns_hosts)}")

    started = time.perf_counter()
    source_events: list[str] = []
    translation_events: list[str] = []
    audio_buffer = bytearray()
    event_counts: defaultdict[str, int] = defaultdict(int)

    with dns_override(dns_hosts, config["dns_servers"]):
        async with websockets.connect(
            config["ws_url"],
            additional_headers=headers,
            max_size=32 * 1024 * 1024,
            compression=None,
            proxy=True if use_system_proxy() else None,
            open_timeout=15,
            ping_interval=20,
            ping_timeout=20,
        ) as websocket:
            logid = websocket.response.headers.get("X-Tt-Logid", "")
            print(f"Connected. Logid: {logid}")

            await websocket.send(build_start_request(session_id).SerializeToString())
            session_started = False

            while not session_started:
                response = parse_response(await websocket.recv())
                event_name = Type.Name(response.event)
                event_counts[event_name] += 1
                print(f"recv {event_name} message={response.response_meta.Message}")
                if response.event == Type.SessionFailed:
                    raise RuntimeError(response.response_meta.Message or "SessionFailed during startup")
                if response.event == Type.SessionStarted:
                    session_started = True

            for index, chunk in enumerate(chunks, start=1):
                await websocket.send(build_audio_request(session_id, chunk).SerializeToString())
                if index == 1 or index % 20 == 0 or index == len(chunks):
                    print(f"sent chunk {index}/{len(chunks)} size={len(chunk)}")
                await asyncio.sleep(0.1)

            await websocket.send(build_finish_request(session_id).SerializeToString())
            print("FinishSession sent.")

            while True:
                response = parse_response(await websocket.recv())
                event_name = Type.Name(response.event)
                event_counts[event_name] += 1

                if response.event == Type.SourceSubtitleEnd and response.text:
                    source_events.append(response.text)
                    print(f"source: {response.text}")
                elif response.event == Type.TranslationSubtitleEnd and response.text:
                    translation_events.append(response.text)
                    print(f"translation: {response.text}")
                elif response.event == Type.TTSResponse and response.data:
                    audio_buffer.extend(response.data)
                elif response.event == Type.UsageResponse:
                    print(f"usage status={response.response_meta.StatusCode} message={response.response_meta.Message}")
                    if response.response_meta.Billing.Items:
                        items = ", ".join(f"{item.Unit}={item.Quantity:.1f}" for item in response.response_meta.Billing.Items)
                        print(f"billing: {items}")
                elif response.event == Type.AudioMuted:
                    print(f"muted {response.muted_duration_ms} ms")
                elif response.event == Type.SessionFailed:
                    raise RuntimeError(response.response_meta.Message or "SessionFailed")
                elif response.event == Type.SessionFinished:
                    print("Session finished.")
                    break

    elapsed = time.perf_counter() - started
    OUTPUT_DIR.mkdir(exist_ok=True)
    wav_path = OUTPUT_DIR / "smoke_translation.wav"
    txt_path = OUTPUT_DIR / "smoke_translation.txt"
    save_pcm_float32_as_wav(bytes(audio_buffer), wav_path)
    txt_path.write_text(
        json.dumps(
            {
                "source": source_events,
                "translation": translation_events,
                "event_counts": dict(event_counts),
                "elapsed_seconds": round(elapsed, 3),
                "audio_bytes": len(audio_buffer),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Source sentences: {len(source_events)}")
    print(f"Translation sentences: {len(translation_events)}")
    print(f"Audio bytes: {len(audio_buffer)}")
    print(f"Saved text report: {txt_path}")
    print(f"Saved translated audio wav: {wav_path}")


if __name__ == "__main__":
    asyncio.run(main())
