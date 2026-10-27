#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_build_cache_v1_pair.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_build_cache_v1_pair.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
if [ -f "$L/build_cache_v1_pair.log" ]; then
  echo "research/model/logs/build_cache_v1_pair.log already exists: refusing to overwrite an existing log" >&2
  exit 1
fi
# planner ruling 2026-10-27: a stale done-marker from an earlier run nearly caused a false "finished"
# report more than once. Remove it before launch, write it only after the job actually exits.
rm -f "$L/build_cache_v1_pair_done.log"
# The full 6,697,756 x 1,091 load (Step 1/2 showed ~35s column-read + ~111s cold manifest_verify per full
# scan, now parallelized and verify-cached) plus the np.save write (~29 GB), PLUS the chunked equivalence
# check calling load_features (the parquet path) about 16 times (11 chunks fold 7 + 5 fold 0, ~40-70s
# each) plus two 29 GB file hashes (checker's round-2 estimate) -- could run close to 3600s, so budget
# 5400.
timeout 5400 python -u research/model/build_cache_v1_pair.py > "$L/build_cache_v1_pair.log" 2>&1
EXIT=$?
echo "exit_code=$EXIT" >> "$L/build_cache_v1_pair.log"
echo "pid=$$ exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/build_cache_v1_pair_done.log"
