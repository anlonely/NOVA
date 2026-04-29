#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

pick_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      "$candidate" - <<'PY' && { echo "$candidate"; return 0; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
    fi
  done
  return 1
}

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
else
  PYTHON_BIN="$(pick_python)"
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python 3.9+ is required. Install it with Homebrew: brew install python@3.12" >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

. .venv/bin/activate
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements.txt

if command -v cargo >/dev/null 2>&1 && [[ -f native_audio_core/Cargo.toml ]]; then
  cargo build --release --manifest-path native_audio_core/Cargo.toml >/dev/null
fi

export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
export QT_MAC_WANTS_LAYER=1
exec "$PYTHON_BIN" desktop_webview.py
