#!/usr/bin/env bash
set -e

echo "[setup] Installing system packages ..."
sudo apt-get update
sudo apt-get install -y \
    python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-webkit2-4.1 \
    python3-venv

echo "[setup] Creating virtual environment ..."
python3 -m venv --system-site-packages .venv

echo "[setup] Installing Python packages ..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install pywebview==5.3.2

echo "[setup] Done. Run the scraper with: ./run_scraper.sh \"python developer\""
