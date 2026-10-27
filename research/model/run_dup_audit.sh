#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_dup_audit.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_dup_audit.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
python -u research/model/dup_audit_v1_pair.py > "$L/dup_audit_v1_pair.log" 2>&1
echo "dup_audit done" > "$L/dup_audit_done.log"
