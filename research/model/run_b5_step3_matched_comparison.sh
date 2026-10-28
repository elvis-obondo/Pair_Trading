#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_b5_step3_matched_comparison.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_b5_step3_matched_comparison.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
if [ -f "$L/b5_step3_matched_comparison.log" ]; then
  echo "research/model/logs/b5_step3_matched_comparison.log already exists: refusing to overwrite an existing log" >&2
  exit 1
fi
rm -f "$L/b5_step3_matched_comparison_done.log"
# 1 warm-up + 2 timed fold-7 combined loads, each ~35-100s warm per Step 1/2's own numbers -- budget
# generously for the cache manifest check and any cold spots.
timeout 1200 python -u research/model/b5_step3_matched_comparison.py > "$L/b5_step3_matched_comparison.log" 2>&1
EXIT=$?
echo "exit_code=$EXIT" >> "$L/b5_step3_matched_comparison.log"
echo "pid=$$ exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/b5_step3_matched_comparison_done.log"
