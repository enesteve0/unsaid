#!/usr/bin/env bash
# The static demo: the web app plus the recorded examples and the evaluation report, for GitHub Pages.
# No server and no model calls, so it cannot spend anything; it stays up for free through judging.
#   infra/pages/build.sh            # writes site/ for https://enesteve0.github.io/unsaid/
set -euo pipefail
cd "$(dirname "$0")/../.."
BASE_PATH="${BASE_PATH:-/unsaid/}"
OUT="${OUT:-$PWD/site}"
(cd web && VITE_STATIC=1 VITE_BASE="$BASE_PATH" pnpm exec vite build --outDir "$OUT" --emptyOutDir)
mkdir -p "$OUT/media/samples" "$OUT/eval"
cp samples/manifest.json samples/ATTRIBUTION.md "$OUT/media/samples/"
for id in $(python3 -c "import json; print(' '.join(s['id'] for s in json.load(open('samples/manifest.json'))))"); do
  cp -R "samples/$id" "$OUT/media/samples/$id"   # only the published examples, never samples/raw
done
if [ -f backend/eval/report.json ]; then cp backend/eval/report.json "$OUT/eval/report.json"; fi
cp "$OUT/index.html" "$OUT/404.html"   # deep links (/unsaid/samples/...) load the app, which then routes
touch "$OUT/.nojekyll"
echo "static demo in $OUT ($(du -sh "$OUT" | cut -f1))"
