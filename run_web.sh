#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! .venv/bin/python --version &>/dev/null; then
    echo "venv missing or broken - recreating..."
    rm -rf .venv
    python3 -m venv --system-site-packages .venv
    .venv/bin/python -m pip install --upgrade pip --quiet
    .venv/bin/python -m pip install pywebview==5.3.2 --quiet
fi

echo "Installing web dependencies..."
.venv/bin/python -m pip install flask anthropic duckduckgo-search --quiet

echo "Starting web UI -> http://localhost:5000"
.venv/bin/python web/app.py
