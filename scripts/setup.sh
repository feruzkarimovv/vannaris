#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$PWD/.cache/pip}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-$PWD/.cache/npm}"
VANNARIS_PYTHON="${VANNARIS_PYTHON:-python3.13}"

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python "$VANNARIS_PYTHON" --seed .venv
  else
    "$VANNARIS_PYTHON" -m venv .venv
  fi
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 13), "Use Python 3.13 for the tested runtime"'
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m pip check
npm ci --include=dev --no-audit --no-fund
printf '\nSetup complete. Run make check, make serve, or make demo.\n'
