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

# STALE COUNTS AS MISSING. This used to list only pairs with NO 1m feather at
# all. Once every ticker had one the function returned empty forever: pass 1
# broke immediately and the script exited 0 having downloaded nothing, while
# the 1m store sat nine days behind the 30m store. That is the same
# silent-success failure the header warns about, arriving from the other
# direction -- a data command that exits 0 without checking what it wrote.
#
# A pair needs work if it has no 1m file, or if its last 1m candle is more than
# STALE_MINUTES behind the newest 30m candle on disk. The 30m store is the
# reference because update_data.sh advances it and it is what the research
# engine reads, so "as fresh as 30m" is the only definition of current that
# matters here. freqtrade resumes from each feather's last candle, so a stale
# pair is appended to rather than refetched.
STALE_MINUTES="${STALE_MINUTES:-60}"
missing() {
  STALE_MINUTES="$STALE_MINUTES" python3 - <<'PY'
import glob, json, os
import pandas as pd

D = "user_data/data/okx/futures"
slack = pd.Timedelta(minutes=float(os.environ.get("STALE_MINUTES", "60")))

ref = None
for f in glob.glob(f"{D}/*-30m-futures.feather"):
    try:
        m = pd.read_feather(f, columns=["date"]).date.max()
    except Exception:
        continue
    if m is not None and (ref is None or m > ref):
        ref = m
cut = None if ref is None else ref - slack

last = {}
for f in glob.glob(f"{D}/*-1m-futures.feather"):
    t = os.path.basename(f).split("_USDT")[0]
    try:
        last[t] = pd.read_feather(f, columns=["date"]).date.max()
    except Exception:
        last[t] = None

want = json.load(open("user_data/config.json"))["exchange"]["pair_whitelist"]
out = []
for p in want:
    t = p.split("/")[0]
    if t not in last or last[t] is None:
        out.append(p)
    elif cut is not None and last[t] < cut:
        out.append(p)
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
  echo "--- pass $pass: $n pairs missing or stale ---" | tee -a "$LOG"
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

echo "=== finished $(date '+%F %T'); $(missing | wc -w) still missing or stale ===" | tee -a "$LOG"
python3 research/intrabar.py 2>&1 | tee -a "$LOG"
