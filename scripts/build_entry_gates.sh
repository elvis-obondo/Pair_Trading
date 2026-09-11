#!/usr/bin/env bash
# Build research/entry_gates.parquet on a memory-constrained laptop.
#
# The gate computation is ~660k OU fits. On this 8GB machine the first attempt
# ran 8 workers, held every result row in the parent, and took the machine down
# twice without producing a file. entry_gates_dataset.py now checkpoints each
# shard to research/entry_gates_parts/, so the only thing left is to keep
# restarting it until it converges -- which is what this does.
#
#   ./scripts/build_entry_gates.sh            # default 3 workers
#   WORKERS=2 ./scripts/build_entry_gates.sh  # slower, gentler
#
# Safe to Ctrl-C and rerun; finished shards are never recomputed.
set -u
cd "$(dirname "$0")/.."

WORKERS="${WORKERS:-3}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-40}"
LOG="research/entry_gates_build.log"

echo "building entry gates with $WORKERS workers; log -> $LOG"
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "--- attempt $attempt at $(date '+%H:%M:%S')" | tee -a "$LOG"
    # -u so progress is visible immediately; a buffered log looks like a hang
    # and sent me chasing a crash that had not happened.
    python -u research/entry_gates_dataset.py --workers "$WORKERS" --shard-pairs "${SHARD:-50}" 2>&1 | tee -a "$LOG"
    if [ -f research/entry_gates.parquet ]; then
        echo "done after $attempt attempt(s)" | tee -a "$LOG"
        exit 0
    fi
    echo "attempt $attempt ended without a merged file; retrying" | tee -a "$LOG"
    sleep 5
done
echo "gave up after $MAX_ATTEMPTS attempts; shards so far:" | tee -a "$LOG"
ls research/entry_gates_parts/ | wc -l | tee -a "$LOG"
exit 1
