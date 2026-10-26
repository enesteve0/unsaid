#!/usr/bin/env bash
# Store the API keys in Nebius SecretStash (MysteryBox) once. Reads them from the local .env; prints nothing secret.
set -euo pipefail
set -a; source .env; set +a
: "${NEBIUS_API_KEY:?missing in .env}" "${TAVILY_API_KEY:?missing in .env}" "${JUDGE_CODE:?missing in .env}"
nebius mysterybox secret create --name unsaid-secrets --secret-version-payload "$(jq -nc \
  --arg a "$NEBIUS_API_KEY" --arg t "$TAVILY_API_KEY" --arg j "$JUDGE_CODE" \
  '[{key:"NEBIUS_API_KEY",string_value:$a},{key:"TAVILY_API_KEY",string_value:$t},{key:"JUDGE_CODE",string_value:$j}]')" \
  --format json | jq '{id: .metadata.id, name: .metadata.name}'
