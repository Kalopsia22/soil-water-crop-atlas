#!/usr/bin/env bash
# Reproduce everything from the raw CSVs in data/raw/. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
python src/download_boundaries.py
python src/ingest.py
python src/crosswalk.py
python src/features.py
python src/index.py > /dev/null
python src/cluster.py > /dev/null
python src/geo_join.py
python src/extras.py
python src/change.py
python src/insights.py
python src/more.py
python src/figures.py
python -m pytest -q tests
echo "Done. Launch the app with: streamlit run app/main.py"
