#!/usr/bin/env bash
# Usage: ./run_scraper.sh "python developer" [--max-jobs 50] [--output ./data/jobs.csv]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$SCRIPT_DIR/data"

cd "$SCRIPT_DIR"
.venv/bin/python -m scraper "$@"
