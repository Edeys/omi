#!/bin/sh
# Runs the upstream notifications cron (modal/job.py) at the top of every UTC hour.
while true; do
  python modal/job.py || echo "[notifications-job] run failed; retrying next hour"
  sleep $(( 3600 - $(date +%s) % 3600 ))
done
