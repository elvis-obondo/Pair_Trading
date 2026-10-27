#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_b5_profile.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_b5_profile.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
# Shell-level circuit breaker, same reasoning as B4: most wall time is inside compiled
# pyarrow/pandas code, not pure Python bytecode, so an in-process alarm may not fire promptly.
# 8 load_features calls total (fold 7: 3 separate + 1 combined; fold 0: 3 separate + 1 combined),
# each of which the B4 run showed costs ~219s regardless of event count (dominated by per-column
# full-file reads, not row selection) -- budget generously.
timeout 5400 python -u research/model/b5_profile.py > "$L/b5_profile.log" 2>&1
echo "exit_code=$?" >> "$L/b5_profile.log"
echo "b5_profile done" > "$L/b5_profile_done.log"
