#!/bin/bash
# One-command health dashboard for the Omi self-host on the VPS.
# Exit 1 if anything is down — suitable for cron alerting.
set -u

FAIL=0
DOMAINS=(omi-api omi-desk omi-ws omi-app)

echo "== containers =="
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'backend|pusher|redis|stt-adapter|omi-apps|notifications-job' || FAIL=1

echo "== public health endpoints =="
for h in "${DOMAINS[@]}"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$h.xuanloi.me/health")
  echo "$h: $code"
  [ "$code" = "200" ] || FAIL=1
done

echo "== resources =="
free -h | head -2
df -h / | tail -1

if [ "$FAIL" -ne 0 ]; then
  echo "RESULT: UNHEALTHY"
  exit 1
fi
echo "RESULT: all healthy"
