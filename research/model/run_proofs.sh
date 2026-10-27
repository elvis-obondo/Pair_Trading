#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_proofs.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_proofs.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
# planner ruling 2026-10-27: a stale done-marker from an earlier run nearly caused a false "finished"
# report more than once. Remove it before launch, write it only after the job actually exits.
rm -f "$L/proofs_done.log"
python -u research/model/proofs_v1_pair.py > "$L/proofs_v1_pair.log" 2>&1
EXIT=$?
echo "pid=$$ exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/proofs_done.log"
