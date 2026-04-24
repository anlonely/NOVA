#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python_bin="${PYTHON:-python3}"
if [[ ! -x .venv/bin/python ]]; then
  "$python_bin" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

if command -v cargo >/dev/null 2>&1 && [[ -f native_audio_core/Cargo.toml ]]; then
  cargo build --release --manifest-path native_audio_core/Cargo.toml
else
  echo "Cargo not found. Skipping native audio core build."
fi

rm -rf build dist
mkdir -p output/release
python -m PyInstaller --noconfirm --clean nova_interp.spec

version="$(python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('app_version.json').read_text(encoding='utf-8')).get('version', '0.0.0'))
PY
)"
zip_name="NOVA-INTERP-macOS-v${version}.zip"
zip_path="output/release/${zip_name}"
rm -f "$zip_path" "$zip_path.sha256"
ditto -c -k --sequesterRsrc --keepParent "dist/NOVA INTERP.app" "$zip_path"
shasum -a 256 "$zip_path" | sed "s#  .*#  ${zip_name}#" > "$zip_path.sha256"

echo "Release bundle created:"
echo "  $zip_path"
echo "  $zip_path.sha256"
