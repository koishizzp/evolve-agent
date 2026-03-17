#!/usr/bin/env bash

set -euo pipefail

HOST="${EVOLVE_AGENT_API_HOST:-0.0.0.0}"
PORT="${EVOLVE_AGENT_API_PORT:-8110}"

exec uvicorn api.main:app --host "${HOST}" --port "${PORT}"
