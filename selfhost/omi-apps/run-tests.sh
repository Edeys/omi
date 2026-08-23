#!/bin/bash
# Run omi-apps unit tests inside python:3.11-slim (no host Python needed).
# Usage (from repo root or anywhere): /opt/omi/selfhost/omi-apps/run-tests.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

docker run --rm \
  -v "$DIR":/srv \
  -w /srv \
  python:3.11-slim \
  bash -c 'pip install -q -r requirements.txt -r requirements-dev.txt && python -m pytest -q'
