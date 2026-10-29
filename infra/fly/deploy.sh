#!/usr/bin/env bash
# Fallback host: deploy (or redeploy) Unsaid on Fly.io when the Nebius Serverless endpoint is not available.
# Requires: flyctl logged in (`fly auth login`) and .env with NEBIUS_API_KEY, TAVILY_API_KEY and JUDGE_CODE.
# The image is built on Fly's remote amd64 builder, so nothing is emulated locally. Prints nothing secret.
#   APP=unsaid-demo REGION=ams infra/fly/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
APP="${APP:-unsaid-demo}"
REGION="${REGION:-ams}"
ORG="${ORG:-personal}"

for key in NEBIUS_API_KEY TAVILY_API_KEY JUDGE_CODE; do
  grep -qE "^${key}=.+" .env || { echo "missing in .env: ${key}" >&2; exit 1; }
done

if ! fly status --app "$APP" >/dev/null 2>&1; then
  fly apps create "$APP" --org "$ORG"
  fly volumes create unsaid_data --app "$APP" --region "$REGION" --size 3 --yes
fi
grep -E '^(NEBIUS_API_KEY|NEBIUS_API_KEY_BACKUP|TAVILY_API_KEY|JUDGE_CODE)=.+' .env | fly secrets import --app "$APP" --stage
fly deploy . --app "$APP" --config infra/fly/fly.toml --dockerfile Dockerfile --remote-only \
  --primary-region "$REGION" --ha=false --wait-timeout 10m
fly status --app "$APP"
curl -fsS --max-time 30 "https://${APP}.fly.dev/api/health" | head -c 400 && echo
echo "Demo URL: https://${APP}.fly.dev"
