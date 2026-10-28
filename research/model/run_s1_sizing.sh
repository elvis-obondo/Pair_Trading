#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_s1_sizing.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_s1_sizing.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
LOG="$L/s1_sizing.log"
if [ -f "$LOG" ]; then
  echo "research/model/logs/s1_sizing.log already exists: refusing to overwrite an existing log" >&2
  exit 1
fi
rm -f "$L/s1_sizing_done.log"

# Planner ruling 2026-10-28: S1's own run script gets the "confirm it started" check now (the general fix
# to the other run_*.sh scripts is deferred until after S1 launches). Launch python in the BACKGROUND
# under this script's own timeout, wait a few seconds, then check the pid is still alive AND the log
# already shows the script's own header (the five sha256 lines it prints before touching the 29 GB cache
# file) -- a silent crash in the first second (e.g. an import error) must not look identical to "still
# running" for however long `timeout` would otherwise let it sit.
# Budget: data load + preprocessing + 2 FISTA fits on fold 7's full train set, no subsampling. The 29 GB
# cache file's own sha256 alone has run in minutes elsewhere in B5; generous headroom for the fits
# themselves, which this script exists to measure.
timeout 7200 python -u research/model/s1_sizing.py > "$LOG" 2>&1 &
PY_PID=$!
sleep 5
if ! kill -0 "$PY_PID" 2>/dev/null; then
  echo "FAILED-TO-START: s1_sizing.py exited within 5s of launch (pid $PY_PID gone)" | tee -a "$LOG" >&2
  echo "pid=$PY_PID exit_code=FAILED-TO-START finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/s1_sizing_done.log"
  exit 1
fi
if ! grep -q "sha256 s1_sizing.py" "$LOG" 2>/dev/null; then
  echo "FAILED-TO-START: s1_sizing.py pid $PY_PID is alive but its log shows no header after 5s -- stuck before main() or writing nowhere" | tee -a "$LOG" >&2
  kill "$PY_PID" 2>/dev/null || true
  echo "pid=$PY_PID exit_code=FAILED-TO-START finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/s1_sizing_done.log"
  exit 1
fi
echo "[RUN-S1-SIZING] started OK: pid $PY_PID alive, header confirmed in log after 5s" >> "$LOG"
wait "$PY_PID"
EXIT=$?
echo "exit_code=$EXIT" >> "$LOG"
echo "pid=$PY_PID exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/s1_sizing_done.log"
