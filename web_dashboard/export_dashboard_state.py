from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "output" / "smoke_translation.txt"
STATE_PATH = Path(__file__).resolve().parent / "dashboard_state.js"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nova_controller import NovaController


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def mask_value(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return "*" * max(10, min(24, len(value)))


def build_transcripts(smoke_data: dict) -> dict[str, list[dict[str, str]]]:
    source_list = smoke_data.get("source") or []
    target_list = smoke_data.get("translation") or []
    now = datetime.now()

    pairs: list[dict[str, str]] = []
    for index, source_text in enumerate(source_list):
        target_text = target_list[index] if index < len(target_list) else ""
        stamp = (now - timedelta(seconds=max(0, (len(source_list) - index) * 3))).strftime("%H:%M:%S")
        pairs.append(
            {
                "time": stamp,
                "source": str(source_text or "").strip(),
                "target": str(target_text or "").strip(),
            }
        )

    if not pairs:
        pairs = [
            {
                "time": now.strftime("%H:%M:%S"),
                "source": "Waiting for live subtitles.",
                "target": "Live translation will appear here.",
            }
        ]

    reverse_pairs = [
        {
            "time": item["time"],
            "source": item["target"] or item["source"],
            "target": item["source"] or item["target"],
        }
        for item in pairs
    ]
    return {"a": pairs, "b": reverse_pairs}


def main() -> None:
    controller = NovaController()
    state = controller.get_state()
    smoke_data = load_json(SMOKE_PATH)

    state["credentials"] = {
        "appId": mask_value(state["credentials"].get("appId", "")),
        "accessToken": mask_value(state["credentials"].get("accessToken", "")),
        "secretKey": mask_value(state["credentials"].get("secretKey", "")),
        "resourceId": state["credentials"].get("resourceId", ""),
    }

    if not state.get("transcripts", {}).get("a"):
        state["transcripts"] = build_transcripts(smoke_data)
        state["partials"] = {
            "a": {
                "source": state["transcripts"]["a"][-1]["source"],
                "target": state["transcripts"]["a"][-1]["target"],
            },
            "b": {
                "source": state["transcripts"]["b"][-1]["source"],
                "target": state["transcripts"]["b"][-1]["target"],
            },
        }

    state["meta"] = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "smoke": {
            "elapsedSeconds": smoke_data.get("elapsed_seconds"),
            "audioBytes": smoke_data.get("audio_bytes"),
            "eventCounts": smoke_data.get("event_counts", {}),
        },
    }

    payload = "window.__NOVA_STATE__ = " + json.dumps(state, ensure_ascii=False, indent=2) + ";\n"
    STATE_PATH.write_text(payload, encoding="utf-8")
    controller.shutdown()
    print(f"Wrote {STATE_PATH}")


if __name__ == "__main__":
    main()
