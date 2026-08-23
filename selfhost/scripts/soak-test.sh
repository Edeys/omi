#!/bin/bash
# Multi-user soak check for the Omi self-host.
# Keeps N parallel health probes running for DURATION seconds, then counts
# backend "recovering stale" log lines — sustained growth there means the
# listen pipeline is not coping. Pass if the count stays below 5.
# Usage: DURATION=600 USERS=5 bash soak-test.sh   (run from the compose dir or with COMPOSE_DIR set)
set -u

DURATION="${DURATION:-600}"
USERS="${USERS:-5}"
STT_HEALTH_URL="${STT_HEALTH_URL:-http://127.0.0.1:8092/health}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/omi/compose}"

echo "soak: $USERS users x ${DURATION}s against $STT_HEALTH_URL"

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
  echo "RESULT: PASS"
else
  echo "RESULT: FAIL (listen pipeline recovering too often)"
  exit 1
fi
