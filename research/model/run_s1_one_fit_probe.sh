#!/bin/bash
cd ~/Pair_Trading
L=research/model/logs
mkdir -p "$L"
LOCK=/tmp/run_s1_one_fit_probe.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_s1_one_fit_probe.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
LOG="$L/s1_one_fit_probe.log"
if [ -f "$LOG" ]; then
  echo "research/model/logs/s1_one_fit_probe.log already exists: refusing to overwrite an existing log" >&2
  exit 1
fi
rm -f "$L/s1_one_fit_probe_done.log"

# Planner's ruling, S1 review round 5: one fit, in isolation, timeout well above the ~2.3h scaling
# estimate (checker: "about 2.3h x 1.5"); planner set 4h explicitly. Per-10-iteration logging inside the
# script means a kill at this timeout still tells us iterations x seconds, unlike the prior chain run.
#
# Checker's ruling, S1 review round 5: thread count is R7's "fixed thread count, logged" choice, not a
# precision trade-off (unlike float32 matmuls or fewer iterations) -- gcp_run.sh's own launch wrapper sets
# OMP_NUM_THREADS=1 for every job, which would make a single-threaded BLAS fit on this 8-core VM look
# ~8x slower than it needs to be, biasing the whole sizing projection. Overridden HERE, for this job only
# -- scripts/gcp_run.sh's own default is unchanged, every other job still gets OMP_NUM_THREADS=1.
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8
timeout 14400 python -u research/model/s1_one_fit_probe.py > "$LOG" 2>&1 &
PY_PID=$!
sleep 5
if ! kill -0 "$PY_PID" 2>/dev/null; then
  echo "FAILED-TO-START: s1_one_fit_probe.py exited within 5s of launch (pid $PY_PID gone)" | tee -a "$LOG" >&2
  echo "pid=$PY_PID exit_code=FAILED-TO-START finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/s1_one_fit_probe_done.log"
  exit 1
fi
if ! grep -q "sha256 s1_one_fit_probe.py" "$LOG" 2>/dev/null; then
  echo "FAILED-TO-START: s1_one_fit_probe.py pid $PY_PID is alive but its log shows no header after 5s" | tee -a "$LOG" >&2
  kill "$PY_PID" 2>/dev/null || true
  echo "pid=$PY_PID exit_code=FAILED-TO-START finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/s1_one_fit_probe_done.log"
  exit 1
fi
echo "[RUN-S1-ONEFIT] started OK: pid $PY_PID alive, header confirmed in log after 5s" >> "$LOG"
wait "$PY_PID"
EXIT=$?
echo "exit_code=$EXIT" >> "$LOG"
echo "pid=$PY_PID exit_code=$EXIT finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$L/s1_one_fit_probe_done.log"
