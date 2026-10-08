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
# TWO MODES, because "needs work" means opposite things in each.
#
#   FORWARD (default) -- a pair needs work if its last 1m candle is behind the
#   30m store. This is the keep-current mode run after update_data.sh.
#
#   BACKFILL=1 -- a pair needs work if its FIRST 1m candle is later than
#   BACKFILL_START, and freqtrade is given --prepend so it fills backward. OKX
#   serves 1m back to 2024-04-21 (measured 2026-10-07: 1,272,988 bars for BTC,
#   884 days), which covers the whole dislocation set -- but the files on disk
#   started 2026-08-09, which put every 1m-covered dislocation AFTER the
#   2026-07-18 split and left nothing to train on. 30MB per instrument, so the
#   full backfill is ~6.4GB and ~15 hours.
#
#   --prepend only fills backward and does not advance the tail, so a complete
#   job is a BACKFILL pass followed by a normal forward pass.
#
# Usage:  scripts/download_1m.sh [DAYS] [BATCH] [SLEEP]
#         BACKFILL=1 scripts/download_1m.sh 900        # fill history backward
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
BACKFILL="${BACKFILL:-0}"
BACKFILL_START="${BACKFILL_START:-2024-04-21}"
missing() {
  STALE_MINUTES="$STALE_MINUTES" BACKFILL="$BACKFILL" \
  BACKFILL_START="$BACKFILL_START" python3 - <<'PY'
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

backfill = os.environ.get("BACKFILL", "0") == "1"
# A day of slack: an instrument listed after BACKFILL_START can never reach it,
# and without the tolerance those pairs would be retried on every pass forever.
start = pd.Timestamp(os.environ.get("BACKFILL_START", "2024-04-21"), tz="UTC") \
        + pd.Timedelta(days=1)

last, first = {}, {}
for f in glob.glob(f"{D}/*-1m-futures.feather"):
    t = os.path.basename(f).split("_USDT")[0]
    try:
        d = pd.read_feather(f, columns=["date"]).date
        last[t], first[t] = d.max(), d.min()
    except Exception:
        last[t] = first[t] = None

want = json.load(open("user_data/config.json"))["exchange"]["pair_whitelist"]
out = []
for p in want:
    t = p.split("/")[0]
    if t not in last or last[t] is None:
        out.append(p)
    elif backfill:
        # Backward: needs work while its earliest candle is later than target.
        if first[t] > start:
            out.append(p)
    elif cut is not None and last[t] < cut:
        out.append(p)
print(" ".join(out))
PY
}

PREPEND_FLAG=""
MODE="forward (keep current)"
if [ "$BACKFILL" = "1" ]; then
    PREPEND_FLAG="--prepend"
    MODE="BACKFILL to $BACKFILL_START"
fi
echo "=== 1m download started $(date '+%F %T')  mode=$MODE days=$DAYS batch=$BATCH pause=${PAUSE}s ===" | tee -a "$LOG"

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
        ${PREPEND_FLAG} \
        --pairs "${chunk[@]}" >>"$LOG" 2>&1
    sleep "$PAUSE"
  done

  after=$(missing | wc -w)
  echo "--- pass $pass done: $before -> $after missing ---" | tee -a "$LOG"
  [ "$after" -eq "$before" ] && { echo "no progress, stopping" | tee -a "$LOG"; break; }
done

echo "=== finished $(date '+%F %T'); $(missing | wc -w) still missing or stale ===" | tee -a "$LOG"
python3 research/intrabar.py 2>&1 | tee -a "$LOG"
