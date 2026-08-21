#!/bin/bash
set -euo pipefail

# Deploy Omi self-host backend + desktop-backend (+ pusher/redis) on the VPS.
# Prereqs: repo cloned at /opt/omi (branch feat/selfhost-backend), /opt/omi/.env (mode 600),
#          /opt/omi/secrets/firebase-service-account.json (600), nginx vhosts + certbot done (Task 3).
# Usage (on VPS):
#   /opt/omi/selfhost/scripts/deploy-backend.sh
# Or from anywhere: bash /opt/omi/selfhost/scripts/deploy-backend.sh

REPO_ROOT="/opt/omi"
COMPOSE_DIR="/opt/omi/compose"

echo "[deploy] repo root: $REPO_ROOT  compose dir: $COMPOSE_DIR"

# Ensure compose dir exists and has docker-compose.yml (Task 3 left it empty).
mkdir -p "$COMPOSE_DIR"
if [ -f "$REPO_ROOT/selfhost/docker-compose.yml" ]; then
  # Copy the repo-tracked compose file into /opt/omi/compose so that
  # the build context ../../ resolves to /opt/omi (repo root) as designed.
  cp -f "$REPO_ROOT/selfhost/docker-compose.yml" "$COMPOSE_DIR/docker-compose.yml"
  echo "[deploy] copied $REPO_ROOT/selfhost/docker-compose.yml -> $COMPOSE_DIR/docker-compose.yml"
elif [ ! -f "$COMPOSE_DIR/docker-compose.yml" ]; then
  echo "[deploy] ERROR: no docker-compose.yml at $REPO_ROOT/selfhost/docker-compose.yml nor $COMPOSE_DIR/docker-compose.yml" >&2
  exit 1
fi

# User supplies the real .env (mode 600). Optionally allow seeding from /tmp/omi/.env.
if [ ! -f "$REPO_ROOT/.env" ] && [ -f /tmp/omi/.env ]; then
  cp -n /tmp/omi/.env "$REPO_ROOT/.env" 2>/dev/null || true
  echo "[deploy] seeded $REPO_ROOT/.env from /tmp/omi/.env"
fi

if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "[deploy] ERROR: $REPO_ROOT/.env not found. Copy selfhost/.env.template -> $REPO_ROOT/.env and fill real values (mode 600)." >&2
  echo "       cp $REPO_ROOT/selfhost/.env.template $REPO_ROOT/.env && chmod 600 $REPO_ROOT/.env && nano $REPO_ROOT/.env" >&2
  exit 1
fi

chmod 600 "$REPO_ROOT/.env" 2>/dev/null || true

if [ ! -f "$REPO_ROOT/secrets/firebase-service-account.json" ] && [ ! -f "/opt/omi/secrets/firebase-service-account.json" ]; then
  echo "[deploy] WARNING: /opt/omi/secrets/firebase-service-account.json not found. Backend will fail to auth with Firestore." >&2
fi

cd "$COMPOSE_DIR"

echo "[deploy] building images (this may take several minutes on first run)..."
docker compose build

echo "[deploy] starting redis + backend + desktop-backend (pusher optional)..."
# Core services for Task 4 verification; pusher starts too if nginx omi-ws vhost expects it.
docker compose up -d redis backend desktop-backend pusher 2>/dev/null || docker compose up -d redis backend desktop-backend

echo "[deploy] compose ps:"
docker compose ps

echo ""
echo "[deploy] health checks (expect 200 after ~15s warmup):"
echo "  curl -s https://omi-api.xuanloi.me/v1/health"
echo "  curl -s https://omi-desk.xuanloi.me/health && curl -s https://omi-desk.xuanloi.me/ready"
echo "  curl -s -H \"Authorization: Bearer \${ADMIN_KEY}<uid>\" https://omi-api.xuanloi.me/v1/users/me"
echo ""
echo "[deploy] to tail logs: docker compose logs -f backend desktop-backend"
echo "[deploy] DONE"
