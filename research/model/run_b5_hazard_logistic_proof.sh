#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_b5_hazard_logistic_proof.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_b5_hazard_logistic_proof.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
if [ -f "$L/b5_hazard_logistic_proof.log" ]; then
  echo "research/model/logs/b5_hazard_logistic_proof.log already exists: refusing to overwrite an existing log" >&2
  exit 1
fi
rm -f "$L/b5_hazard_logistic_proof_done.log"
# A 3,000-event smoke subset, 5 columns, 2 L-BFGS-B fits is seconds, but _cache_info() hashes the full
# 29 GB cache file once per process to validate it (checker's note) -- a few minutes, not seconds.
timeout 900 python -u research/model/b5_hazard_logistic_proof.py > "$L/b5_hazard_logistic_proof.log" 2>&1
EXIT=$?
echo "exit_code=$EXIT" >> "$L/b5_hazard_logistic_proof.log"
echo "pid=$$ exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/b5_hazard_logistic_proof_done.log"
