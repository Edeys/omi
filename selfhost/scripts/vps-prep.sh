#!/bin/bash
set -euo pipefail
# 1. Swap 2GB
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile
  mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "vm.swappiness=10" >> /etc/sysctl.d/99-omi.conf
  sysctl --system
fi
# 2. n8n memory limit (edit existing compose; idempotent)
COMPOSE=/opt/n8n/docker-compose.yml
if [ -f "$COMPOSE" ] && ! grep -q 'mem_limit' "$COMPOSE"; then
  sed -i '/restart: always/a\    mem_limit: 1g\n    memswap_limit: 1g' "$COMPOSE"
  cd /opt/n8n && docker compose up -d
fi
# 3. Create /opt/omi dirs
mkdir -p /opt/omi/{compose,secrets,data}
chmod 700 /opt/omi/secrets
# 4. Baseline measurement (record output)
free -m
docker stats --no-stream 2>/dev/null | head -20
uptime
echo "VPS_PREP_DONE"
