#!/usr/bin/env bash
# Run the overnight backlog as a Nebius Serverless Job (same image as the endpoint).
# The job writes per-lecture results and digest.json to an Object Storage bucket; the endpoint mounts the same bucket
# read-only at /backlog (BACKLOG_DIR=/backlog) to show the digest. Always dry-runs first.
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID (eu-west1 project)}"
REGION="${REGION:-eu-west1}"
BUCKET="${BUCKET:-unsaid-backlog}"
BUDGET="${BUDGET:-2}"
nebius config set parent-id "$PROJECT_ID" >/dev/null
REGISTRY_ID="$(nebius registry list --format json | jq -r '.items[] | select(.metadata.name=="unsaid") | .metadata.id' | head -1)"
IMAGE="cr.${REGION}.nebius.cloud/${REGISTRY_ID#*-}/unsaid:${TAG:-demo}"
nebius storage bucket get-by-name --name "$BUCKET" >/dev/null 2>&1 || nebius storage bucket create --name "$BUCKET"

ARGS=(--name "unsaid-backlog-$(date -u +%Y%m%d-%H%M)" --image "$IMAGE" --platform cpu-d3 --preset 4vcpu-16gb
      --disk-size 20Gi --timeout 1h --restart-policy never
      --container-command "uv run --no-sync python -m batch.run_batch --mode backlog --manifest batch/backlog.json --out /out --budget-usd ${BUDGET}"
      --env-secret NEBIUS_API_KEY=unsaid-secrets --env-secret TAVILY_API_KEY=unsaid-secrets
      --volume "s3://${BUCKET}:/out:rw")
nebius ai job create "${ARGS[@]}" --dry-run
nebius ai job create "${ARGS[@]}" --format json | jq '{id: .metadata.id, name: .metadata.name, state: .status.state}'
echo "follow logs with: nebius ai job logs <id> -f"
