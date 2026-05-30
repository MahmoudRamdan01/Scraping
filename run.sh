#!/usr/bin/env bash
# Air Ocean Lead Finder - start the app (macOS / Linux).
set -e
cd "$(dirname "$0")"
# shellcheck disable=SC1091
. .venv/bin/activate
export PYTHONPATH=src
streamlit run src/aol_leadfinder/ui/app.py
