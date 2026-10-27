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
python -u research/model/proofs_v1_pair.py > "$L/proofs_v1_pair.log" 2>&1
echo "proofs done" > "$L/proofs_done.log"
