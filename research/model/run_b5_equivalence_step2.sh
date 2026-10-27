#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_b5_equivalence_step2.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_b5_equivalence_step2.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
if [ -f "$L/b5_equivalence_step2.log" ]; then
  echo "research/model/logs/b5_equivalence_step2.log already exists: refusing to overwrite an existing log" >&2
  exit 1
fi
# planner ruling 2026-10-27: a stale done-marker from an earlier run nearly caused a false "finished"
# report more than once. Remove it before launch, write it only after the job actually exits.
rm -f "$L/b5_equivalence_step2_done.log"
# OLD and NEW load_features each run once per fold (fold 7, fold 0), plus the load_fold_features and
# verify-cache checks; Step 1 showed a combined load costs 90-230s depending on page-cache state, so
# budget generously for ~4-6 full loads total.
timeout 3600 python -u research/model/b5_equivalence_step2.py > "$L/b5_equivalence_step2.log" 2>&1
EXIT=$?
echo "exit_code=$EXIT" >> "$L/b5_equivalence_step2.log"
echo "pid=$$ exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/b5_equivalence_step2_done.log"
