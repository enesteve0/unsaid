#!/usr/bin/env bash
# Everything that needs the Token Factory key, in order. Run from the repo root once .env has NEBIUS_API_KEY.
#   scripts/tf_day.sh            # smoke test, samples, evaluation
#   STEP=eval scripts/tf_day.sh  # just one step
set -euo pipefail
cd "$(dirname "$0")/../backend"
STEP="${STEP:-all}"

if [[ "$STEP" == all || "$STEP" == smoke ]]; then
  uv run python scripts/smoke.py
fi

if [[ "$STEP" == all || "$STEP" == samples ]]; then
  # Home-page example: Fourier analysis machine, 0:00-1:40 (CC BY 3.0).
  uv run python -m unsaid.cli describe data/eval/clips/fourier-a.mp4 --out data/tf/fourier-machine \
    --title "Explaining Fourier analysis with a machine (engineerguy)" \
    --source-url "https://commons.wikimedia.org/wiki/File:3_of_4_-_Analysis_-_Explaining_Fourier_analysis_with_a_machines.webm"
  uv run python -m unsaid.cli publish-sample --run data/tf/fourier-machine --video data/eval/clips/fourier-a.mp4 \
    --id fourier-machine --first --hero "57,72" \
    --credit "Bill Hammack, Steve Kranz and Bruce Carpenter (engineerguy)" --license "CC BY 3.0" \
    --license-url "https://creativecommons.org/licenses/by/3.0/" \
    --source-url "https://commons.wikimedia.org/wiki/File:3_of_4_-_Analysis_-_Explaining_Fourier_analysis_with_a_machines.webm"
  # Second example: capacitor discharge practical (CC BY 3.0).
  uv run python -m unsaid.cli describe data/eval/clips/capacitor.mp4 --out data/tf/capacitor \
    --title "A-level Physics: capacitor discharge (NUSTEM)" \
    --source-url "https://commons.wikimedia.org/wiki/File:A-level_Physics_Core_Practical-_Capacitor_Discharge.webm"
  uv run python -m unsaid.cli publish-sample --run data/tf/capacitor --video data/eval/clips/capacitor.mp4 \
    --id capacitor --credit "NUSTEM (Alom Shaha, Carol Davenport)" --license "CC BY 3.0" \
    --license-url "https://creativecommons.org/licenses/by/3.0/" \
    --source-url "https://commons.wikimedia.org/wiki/File:A-level_Physics_Core_Practical-_Capacitor_Discharge.webm"
fi

if [[ "$STEP" == all || "$STEP" == eval ]]; then
  # Fetch the clips if any listed in clips.json (development or held-out) is missing.
  uv run python -c "import json, os, sys; sys.exit(any(not os.path.exists(c['path']) for c in json.load(open('eval/clips.json'))))" \
    || eval/fetch_clips.sh
  # Two runs per clip: model outputs vary from run to run, so one run is too noisy to publish.
  uv run python -m eval.run_eval --clips eval/clips.json --out data/eval/out --report eval/report.json --repeat 2
fi

# Devpost text and the README results table, from the report and the home-page run (lists anything still unfilled).
python3 ../scripts/fill_numbers.py ${DEMO_URL:+--demo-url "$DEMO_URL"} || true
