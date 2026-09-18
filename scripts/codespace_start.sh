#!/usr/bin/env bash
set -u

ROOT="${WORKSPACE_FOLDER:-/workspaces/AICognitiveMind}"
RUNTIME_DIR="$ROOT/.runtime"
API_URL="http://127.0.0.1:8000"

mkdir -p "$RUNTIME_DIR"
cd "$ROOT"

log() {
  printf '[codespace-start] %s\n' "$*"
}

wait_http() {
  local url="$1"
  local attempts="${2:-30}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

log "Checking MongoDB..."
if python - <<'PY'
import os
from pymongo import MongoClient

uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017")
client = MongoClient(uri, serverSelectionTimeoutMS=3000)
client.admin.command("ping")
client.close()
PY
then
  log "MongoDB is healthy."
else
  log "ERROR: MongoDB is not reachable."
  exit 1
fi

PROVIDER="$(python -c 'from aicognitive_mind.config import get_settings; print(get_settings().reasoning_provider)')"

if [[ "$PROVIDER" == "ollama" ]]; then
  OLLAMA_BASE_URL="$(python -c 'from aicognitive_mind.config import get_settings; print(get_settings().ollama_base_url)')"
  OLLAMA_ROOT="${OLLAMA_BASE_URL%/v1}"
  OLLAMA_MODEL="$(python -c 'from aicognitive_mind.config import get_settings; print(get_settings().ollama_model)')"

  if ! curl -fsS "$OLLAMA_ROOT/api/tags" >/dev/null 2>&1; then
    if ! command -v ollama >/dev/null 2>&1; then
      log "ERROR: Ollama is required but is not installed. Rebuild the Codespace so postCreateCommand can install it."
      exit 1
    fi

    log "Starting Ollama..."
    nohup ollama serve >"$RUNTIME_DIR/ollama.log" 2>&1 &
    echo $! >"$RUNTIME_DIR/ollama.pid"
    if ! wait_http "$OLLAMA_ROOT/api/tags" 30; then
      log "ERROR: Ollama did not become ready. See .runtime/ollama.log"
      exit 1
    fi
  fi
  log "Ollama is healthy."

  if ! ollama list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -Fxq "$OLLAMA_MODEL"; then
    log "Required model '$OLLAMA_MODEL' is missing; pulling it now..."
    if ! ollama pull "$OLLAMA_MODEL"; then
      log "ERROR: Could not pull Ollama model '$OLLAMA_MODEL'."
      exit 1
    fi
  fi
  log "Ollama model '$OLLAMA_MODEL' is available."
fi

BRANCH="$(git branch --show-current)"
if [[ -n "$BRANCH" ]] && ! pgrep -f "scripts/dev_sync.sh $BRANCH" >/dev/null 2>&1; then
  log "Starting repository sync watcher for '$BRANCH'..."
  nohup bash scripts/dev_sync.sh "$BRANCH" >"$RUNTIME_DIR/dev_sync.log" 2>&1 &
  echo $! >"$RUNTIME_DIR/dev_sync.pid"
else
  log "Repository sync watcher is already running (or branch is unavailable)."
fi

if curl -fsS "$API_URL/health" >/dev/null 2>&1; then
  log "Cognitive Mind API is already healthy."
else
  log "Starting Cognitive Mind API on port 8000..."
  nohup python -m uvicorn aicognitive_mind.api:app \
    --host 0.0.0.0 --port 8000 --reload \
    >"$RUNTIME_DIR/api.log" 2>&1 &
  echo $! >"$RUNTIME_DIR/api.pid"

  if ! wait_http "$API_URL/health" 60; then
    log "ERROR: Cognitive Mind API did not become healthy. Recent log output:"
    tail -n 40 "$RUNTIME_DIR/api.log" 2>/dev/null || true
    exit 1
  fi
fi

REVISION="$(curl -fsS "$API_URL/debug/revision" 2>/dev/null || true)"
log "Cognitive Mind API is healthy: ${REVISION:-revision unavailable}"

EXPECTED_REVISION="$(git rev-parse HEAD)"
log "Running local cognitive acceptance..."
if COGNITIVE_MIND_TEST_URL="$API_URL" EXPECTED_REVISION="$EXPECTED_REVISION" python scripts/run_acceptance.py >"$RUNTIME_DIR/acceptance.log" 2>&1; then
  log "Local cognitive acceptance passed."
else
  log "WARNING: Local cognitive acceptance failed. See .runtime/acceptance.log"
fi

log "Startup checks complete. Runtime logs are in .runtime/."
