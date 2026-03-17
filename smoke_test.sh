#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${EVOLVE_AGENT_BASE_URL:-http://127.0.0.1:8110}"

echo "[1/3] health"
curl -fsS "${BASE_URL}/health"
echo

echo "[2/3] ui status"
curl -fsS "${BASE_URL}/ui/status"
echo

if [[ -n "${EVOLVE_AGENT_SMOKE_FASTA_PATH:-}" ]]; then
  echo "[3/3] run_evolution"
  curl -fsS -X POST "${BASE_URL}/run_evolution" \
    -H "Content-Type: application/json" \
    -d "{\"fasta_path\":\"${EVOLVE_AGENT_SMOKE_FASTA_PATH}\",\"task\":\"${EVOLVE_AGENT_SMOKE_TASK:-冷启动优化这个蛋白}\",\"strategy\":\"${EVOLVE_AGENT_SMOKE_STRATEGY:-multievolve}\"}"
  echo
else
  echo "[3/3] skipped run_evolution because EVOLVE_AGENT_SMOKE_FASTA_PATH is not set"
fi
