#!/usr/bin/env bash
# Extend OKX history BACKWARDS. Companion to update_data.sh, which only goes forward.
#
# update_data.sh cannot do this. freqtrade's download-data resumes from each
# feather's last candle and ignores --days for any ticker that already has a
# cached file, so running it with --days 730 fetches nothing new for the 212
# tickers already on disk -- it only ever extends the recent end.
#
# --prepend fetches the span BEFORE each file's existing start and leaves the
# cached bars untouched. freqtrade disables appending while prepending, so a
# normal update_data.sh run afterwards closes the forward gap.
#
# WHY: every parameter conclusion in research/param_stability.py rests on 43
# train days and 29 test days of a single quiet quarter. Train and test agreed
# on take-profit and disagreed on stop, and there is no way to tell a real
# effect from noise at that sample size. More calendar, spanning more than one
# regime, is the only fix.
#
# Usage: scripts/backfill_history.sh [DAYS]   (default 730 = 2 years)
set -euo pipefail
cd "$(dirname "$0")/.."

DAYS="${1:-730}"
LOG="logs/backfill_history.log"
mkdir -p logs

echo "=== backfill to $DAYS days, started $(date '+%F %T') ===" | tee -a "$LOG"
echo "Coverage BEFORE:" | tee -a "$LOG"
python3 scripts/history_coverage.py 2>&1 | tee -a "$LOG"

echo | tee -a "$LOG"
echo "=== downloading (prepend only; forward gap closed afterwards) ===" | tee -a "$LOG"
docker compose run --rm freqtrade download-data \
    --config user_data/config.json \
    --exchange okx \
    --trading-mode futures \
    --timeframes 30m 1h \
    --days "$DAYS" \
    --prepend 2>&1 | tee -a "$LOG"

echo | tee -a "$LOG"
echo "=== closing the forward gap ===" | tee -a "$LOG"
docker compose run --rm freqtrade download-data \
    --config user_data/config.json \
    --exchange okx \
    --trading-mode futures \
    --timeframes 30m 1h \
    --days "$DAYS" 2>&1 | tee -a "$LOG"

echo | tee -a "$LOG"
echo "Coverage AFTER:" | tee -a "$LOG"
python3 scripts/history_coverage.py 2>&1 | tee -a "$LOG"
echo "=== finished $(date '+%F %T') ===" | tee -a "$LOG"
