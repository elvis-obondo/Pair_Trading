#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_b4_rsf.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_b4_rsf.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
# planner ruling 2026-10-27: a stale done-marker from an earlier run nearly caused a false "finished"
# report more than once. Remove it before launch, write it only after the job actually exits.
rm -f "$L/b4_rsf_done.log"
# checker, 2026-10-27: the in-script signal.alarm only fires between Python bytecode instructions and the
# RSF fit/predict calls spend almost all their time in compiled sklearn/sksurv code, so they might not
# self-interrupt. The real circuit breaker is this shell-level `timeout`, not the in-script alarm.
timeout 2700 python -u research/model/b4_rsf_feasibility.py > "$L/b4_rsf_feasibility.log" 2>&1
EXIT=$?
echo "exit_code=$EXIT" >> "$L/b4_rsf_feasibility.log"
echo "pid=$$ exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/b4_rsf_done.log"
