#!/usr/bin/env bash
# Deploy (or redeploy) Unsaid as a Nebius Serverless CPU endpoint.
# Requires: nebius CLI >= 0.12.277 with a profile (`nebius profile create`), Docker with buildx,
# and the secrets created once with create_secrets.sh.
#
# Defaults that matter: the CLI otherwise picks an H100/H200 GPU platform and a 250 GiB disk, so both are set
# explicitly here. eu-west1 has a non-GPU vCPU quota by default; eu-north1 and us-central1 do not.
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID to your Nebius project in eu-west1}"
REGION="${REGION:-eu-west1}"
NAME="${NAME:-unsaid}"
PRESET="${PRESET:-4vcpu-16gb}"
TAG="${TAG:-demo}"   # a moving tag, so `restart` picks up new builds and the URL stays the same

nebius config set parent-id "$PROJECT_ID" >/dev/null
REGISTRY_ID="$(nebius registry list --format json | jq -r '.items[] | select(.metadata.name=="unsaid") | .metadata.id' | head -1)"
if [ -z "$REGISTRY_ID" ]; then
  REGISTRY_ID="$(nebius registry create --name unsaid --format json | jq -r '.metadata.id')"
  nebius registry configure-helper
fi
IMAGE="cr.${REGION}.nebius.cloud/${REGISTRY_ID#*-}/unsaid:${TAG}"

docker buildx build --platform linux/amd64 -t "$IMAGE" --push .

EXISTING="$(nebius ai endpoint get-by-name --name "$NAME" --format json 2>/dev/null | jq -r '.metadata.id // empty' || true)"
if [ -n "$EXISTING" ]; then
  nebius ai endpoint restart --id "$EXISTING"
else
  ARGS=(--name "$NAME" --image "$IMAGE" --platform cpu-d3 --preset "$PRESET" --disk-size 20Gi
        --container-port 8080 --auth none --env HOST="Nebius AI Cloud"
        --env-secret NEBIUS_API_KEY=unsaid-secrets --env-secret TAVILY_API_KEY=unsaid-secrets
        --env-secret JUDGE_CODE=unsaid-secrets)
  if [ -n "${FILESYSTEM_ID:-}" ]; then
    ARGS+=(--volume "${FILESYSTEM_ID}:/data:rw")
  else
    echo "warning: no FILESYSTEM_ID: runs, spend caps and rate limits reset whenever the container restarts" >&2
  fi
  nebius ai endpoint create "${ARGS[@]}" --dry-run
  nebius ai endpoint create "${ARGS[@]}"
fi
nebius ai endpoint get-by-name --name "$NAME" --format json | jq '{id: .metadata.id, state: .status.state, urls: .status.public_endpoints}'
