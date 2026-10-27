#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_b5_profile_startup.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_b5_profile_startup.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
if [ -f "$L/b5_profile_startup.log" ]; then
  echo "research/model/logs/b5_profile_startup.log already exists: refusing to overwrite an existing log" >&2
  exit 1
fi
# load_search_events + build_folds alone are a tiny fraction of a full load_features call (the slow
# part is the group files, not events/labels); budget is generous but short on purpose.
timeout 600 python -u research/model/b5_profile_startup.py > "$L/b5_profile_startup.log" 2>&1
echo "exit_code=$?" >> "$L/b5_profile_startup.log"
echo "b5_profile_startup done" > "$L/b5_profile_startup_done.log"
