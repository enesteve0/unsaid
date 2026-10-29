#!/usr/bin/env bash
# The demo video, end to end, against a running Unsaid (the full app: the pipeline scene runs the example live).
#   scripts/make_video.sh http://127.0.0.1:8080 https://enesteve0.github.io/unsaid
# 1. narration (Kokoro) with numbers from the report and hosting claims from the demo; 2. scene recordings
# (Playwright's Chromium); 3. assembly (ffmpeg); 4. Devpost gallery screenshots. Output: video/build/.
set -euo pipefail
cd "$(dirname "$0")/.."
APP="${1:?the running full app, e.g. http://127.0.0.1:8080}"
DEMO="${2:-$APP}"   # the public demo: hosting claims and the end card come from it
(cd video && DEMO_URL="$DEMO" uv run --project ../backend --with kokoro-onnx --with soundfile python tts.py)
(cd web && node scripts/record-video.mjs "$APP" ../video/build/rec)
(cd video && DEMO_URL="$DEMO" uv run --project ../backend python assemble.py)
(cd video && uv run --project ../backend python captions.py)
(cd web && node scripts/gallery.mjs "$APP" ../video/build/gallery)
ffmpeg -v error -y -i video/build/unsaid-demo.mp4 -vf "fps=1/20,scale=480:-1,tile=4x3" -frames:v 1 video/build/contact-sheet.jpg
echo "video: video/build/unsaid-demo.mp4 ($(ffprobe -v error -show_entries format=duration -of csv=p=0 video/build/unsaid-demo.mp4 | cut -d. -f1) s)"
