#!/usr/bin/env bash
# Air Ocean Lead Finder - one-time setup (macOS / Linux, for developers).
set -e
cd "$(dirname "$0")"

python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium || echo "playwright browser install skipped"

echo "Setup complete. Run ./run.sh to start."
