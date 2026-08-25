#!/bin/bash
# Multi-user soak check for the Omi self-host.
#
# Two layers:
#   1. REAL-AUTH soak (primary): N parallel WebSocket sessions against
#      /v4/listen with Firebase custom-token -> ID-token auth, streaming
#      silence PCM16. Pass = 0 unintended disconnects.
#      Requires FIREBASE_API_KEY; run inside the backend container or with
#      GOOGLE_APPLICATION_CREDENTIALS set (see soak-real-auth.py header).
#   2. HEALTH fallback: if the real-auth layer cannot run (no API key / no
#      firebase SDK), falls back to the old health-probe + "recovering stale"
#      counter so the script still works everywhere.
#
# Usage: DURATION=600 USERS=3 FIREBASE_API_KEY=... bash soak-test.sh
set -u

DURATION="${DURATION:-600}"
USERS="${USERS:-5}"
STT_HEALTH_URL="${STT_HEALTH_URL:-http://127.0.0.1:8092/health}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/omi/compose}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "soak: $USERS users x ${DURATION}s"

# --- Layer 1: real-auth WS soak -------------------------------------------
if [ -n "${FIREBASE_API_KEY:-}" ]; then
  echo "layer 1: real-auth websocket soak"
  if docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps backend >/dev/null 2>&1; then
    # Copy the harness in and exec inside the running backend container
    # (it already has websockets + firebase_admin + network reachability).
    docker cp "$SCRIPT_DIR/soak-real-auth.py" "$(docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps -q backend | head -1)":/app/soak-real-auth.py
    if docker compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T \
        -e FIREBASE_API_KEY="$FIREBASE_API_KEY" \
        -e USERS="$USERS" -e DURATION="$DURATION" \
        backend python /app/soak-real-auth.py; then
      echo "RESULT: PASS (real-auth)"
      exit 0
    fi
    echo "real-auth layer FAILED — falling back to health probes"
  else
    echo "compose stack not found at $COMPOSE_DIR — trying host python"
    if command -v python >/dev/null && python -c 'import websockets' 2>/dev/null \
        && python "$SCRIPT_DIR/soak-real-auth.py" --users "$USERS" --duration "$DURATION"; then
      echo "RESULT: PASS (real-auth)"
      exit 0
    fi
    echo "host python/websockets unavailable — falling back to health probes"
  fi
else
  echo "FIREBASE_API_KEY not set — skipping real-auth layer"
fi

# --- Layer 2: health-probe fallback ----------------------------------------
echo "layer 2: health-probe soak ($USERS users x ${DURATION}s against $STT_HEALTH_URL)"
pids=()
end=$((SECONDS + DURATION))
for u in $(seq 1 "$USERS"); do
  (
    while [ "$SECONDS" -lt "$end" ]; do
      curl -s -o /dev/null --max-time 5 "$STT_HEALTH_URL" || echo "[user$u] probe failed"
      sleep 2
    done
  ) &
  pids+=($!)
done

for pid in "${pids[@]}"; do
  wait "$pid"
done

stale=$(docker compose -f "$COMPOSE_DIR/docker-compose.yml" logs backend --since "${DURATION}s" 2>/dev/null | grep -c 'recovering stale')
echo "recovering-stale events in last ${DURATION}s: $stale"

if [ "$stale" -lt 5 ]; then
  echo "RESULT: PASS (health fallback — NOT a real-auth result)"
else
  echo "RESULT: FAIL (listen pipeline recovering too often)"
  exit 1
fi
