#!/usr/bin/env bash
# Daily disk housekeeping on the VM. Installed by vm_migrate.sh step 7 as
#   15 4 * * * $REMOTE/scripts/vm_housekeeping.sh >> $REMOTE/logs/cron.log 2>&1
#
# WHAT ACTUALLY GROWS HERE, measured 2026-09-12, against ~11GB free:
#
#   monitor_ticks/      ~20-25 MB/day  (20 instruments at 1 Hz)   7-9 GB/year
#   docker images       GBs, in steps  (every --build leaves dangling layers)
#   logs/               ~1 MB/day      (heartbeat, one line per 10s)
#   scan_history/       ~1-2 MB/day
#   30m candle data     ~63 MB/year    <- NOT a problem, and not touched
#
# The first two are the only ones that can fill the disk. Ticks and scan history
# are pruned inside the Python processes, where the retention rule sits next to
# the code that writes them (research/book_state.py). This script handles what
# Python cannot: Docker, and anything the processes missed because they were
# down.
#
# THE LEDGER IS NEVER TOUCHED. scanner_trades.csv is the record of what the
# account did, equity is re-summed from it on every start, and it is small.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) housekeeping ==="
echo "-- before --"
df -h / | tail -1

# Dangling images and stopped one-shot scanner containers. NOT `docker system
# prune -a`, which would also drop the pairs-trading image itself and force a
# full rebuild on the next deploy.
docker container prune -f --filter "until=24h" 2>/dev/null | tail -1
docker image prune -f 2>/dev/null | tail -1
docker builder prune -f --filter "until=168h" 2>/dev/null | tail -1

# Belt and braces: the processes prune their own output, but only while they are
# running. If the monitor was down for a week, nothing expired.
python3 - <<'PY'
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "research"))
import book_state as cfg
for d, days in ((cfg.TICKS_DIR, cfg.RETAIN_TICK_DAYS),
                (cfg.SCAN_HISTORY_DIR, cfg.RETAIN_SCAN_HISTORY_DAYS)):
    gone = cfg.prune_dated(d, days)
    print(f"  {os.path.basename(d)}: pruned {len(gone)} day(s) older than {days}d")
for name in cfg.rotate_logs_in():
    print(f"  rotated {name}")
PY

# cron.log has no rotation of its own and is append-only from two jobs.
if [ -f "$ROOT/logs/cron.log" ] && [ "$(wc -c < "$ROOT/logs/cron.log")" -gt 33554432 ]; then
    mv "$ROOT/logs/cron.log" "$ROOT/logs/cron.log.1"
    echo "  rotated cron.log"
fi

echo "-- after --"
df -h / | tail -1
du -sh "$ROOT/trading_data" 2>/dev/null
