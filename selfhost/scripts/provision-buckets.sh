#!/bin/bash
# Provision GCS buckets for the Omi self-host deployment. Idempotent — safe to re-run.
# Usage: PROJECT_ID=omi-xuan bash provision-buckets.sh
# Requires: gcloud/gsutil authenticated with an account that can create buckets and
# edit IAM on them (owner or storage.admin).
set -euo pipefail

PROJECT="${PROJECT_ID:?export PROJECT_ID=omi-xuan}"
REGION="${REGION:-asia-southeast1}"

SA_EMAIL=$(gcloud iam service-accounts list --project="$PROJECT" \
  --format="value(email)" | grep firebase-adminsdk | head -1)
if [ -z "$SA_EMAIL" ]; then
  echo "ERR: no firebase-adminsdk service account found in project $PROJECT" >&2
  exit 1
fi
echo "Granting objectAdmin on new buckets to SA: $SA_EMAIL"

for b in omi-private-cloud-sync omi-speech-profiles omi-memories-recordings \
         omi-postprocessing omi-temporal-sync-local omi-chat-files omi-app-thumbnails \
         omi-plugins-logos; do
  gsutil mb -p "$PROJECT" -l "$REGION" "gs://$b" 2>/dev/null || echo "[skip] $b already exists"
  gsutil iam ch "roles/storage.objectAdmin:serviceAccount:${SA_EMAIL}" "gs://$b"
done

echo "OK: 8 buckets ready in $REGION"
echo "Next: set matching BUCKET_* values in /opt/omi/.env and restart compose."
