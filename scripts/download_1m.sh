#!/usr/bin/env bash
# Download 1-minute candles for the whole universe, resumably.
#
# WHY THIS EXISTS AND update_data.sh DOES NOT DO IT
#
# A single `download-data` over 212 pairs at 1m fires enough concurrent OHLCV
# requests that OKX answers 50011 "Too Many Requests". freqtrade retries five
# times, gives up, and still exits 0 with a 100% progress bar -- so the run LOOKS
# complete while two thirds of the universe is missing. That happened once
# already: 62 of 212.
#
# So: small batches, a pause between them, a ccxt rateLimit overlay, and the
# batch list recomputed from what is ON DISK every pass. Re-running is always
# safe and always resumes -- freqtrade appends to an existing feather rather than
# refetching it.
#
# Usage:  scripts/download_1m.sh [DAYS] [BATCH] [SLEEP]
set -uo pipefail
cd "$(dirname "$0")/.."

DAYS="${1:-35}"
BATCH="${2:-8}"
PAUSE="${3:-15}"
LOG="logs/download_1m.log"
mkdir -p logs

missing() {
  python3 - <<'PY'
import json, glob, os
have = {os.path.basename(p).split("_USDT")[0]
        for p in glob.glob("user_data/data/okx/futures/*-1m-futures.feather")}
want = json.load(open("user_data/config.json"))["exchange"]["pair_whitelist"]
out = [p for p in want if p.split("/")[0] not in have]
print(" ".join(out))
PY
}

echo "=== 1m download started $(date '+%F %T')  days=$DAYS batch=$BATCH pause=${PAUSE}s ===" | tee -a "$LOG"

# Two passes. The first sweeps everything that is missing; the second picks up
# whatever the first still lost to a transient limit. If a pass downloads
# nothing new, stop -- those pairs have no 1m history on the venue and retrying
# forever would just burn hours.
for pass in 1 2 3; do
  todo=($(missing))
  n=${#todo[@]}
  echo "--- pass $pass: $n pairs missing ---" | tee -a "$LOG"
  [ "$n" -eq 0 ] && break
  before=$n

  for ((i = 0; i < n; i += BATCH)); do
    chunk=("${todo[@]:i:BATCH}")
    echo "[$(date '+%T')] pass $pass  $((i / BATCH + 1))/$(((n + BATCH - 1) / BATCH))  ${chunk[*]}" | tee -a "$LOG"
    docker compose run --rm freqtrade download-data \
        --config user_data/config.json \
        --config user_data/config_slow.json \
        --exchange okx --trading-mode futures \
        --timeframes 1m --days "$DAYS" \
        --pairs "${chunk[@]}" >>"$LOG" 2>&1
    sleep "$PAUSE"
  done

  after=$(missing | wc -w)
  echo "--- pass $pass done: $before -> $after missing ---" | tee -a "$LOG"
  [ "$after" -eq "$before" ] && { echo "no progress, stopping" | tee -a "$LOG"; break; }
done

echo "=== finished $(date '+%F %T'); $(missing | wc -w) still missing ===" | tee -a "$LOG"
python3 research/intrabar.py 2>&1 | tee -a "$LOG"
