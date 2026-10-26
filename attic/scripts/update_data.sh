#!/usr/bin/env bash
# Incrementally update OKX futures OHLCV data -- no delete, no full redownload.
#
# freqtrade's `download-data` already does this by default: when a feather
# file already exists and --erase isn't passed, it reads that file's last
# candle timestamp and only fetches forward from there (see freqtrade's
# freqtrade/data/history/history_utils.py::_load_cached_data_for_updating --
# `start = data.iloc[-1]["date"]` when no --prepend). --days only matters for
# a ticker with no cached file yet; for everything else it's ignored in favor
# of resuming from the cache. This script is just that same call, wrapped
# with a before/after sanity check so a stalled or no-op update is visible
# instead of silent (see the LOOKBACK_DAYS silent-fallback bug this project
# already hit once in run_backtest.py/pair_analysis.py -- don't trust a
# data command that exits 0 without also checking what it actually wrote).
#
# Whatever lands in user_data/data/okx/futures/*.feather here is picked up
# automatically -- research/adapters/okx_futures.py::sync_normalized_store()
# rebuilds user_data/normalized/*.feather + manifest.json from these raw
# files on every get_price_levels() call (pair_analysis.py, run_backtest.py,
# run_trading.py). No separate normalization step needed.
#
# Usage: scripts/update_data.sh [DAYS]
#   DAYS defaults to 60 -- only used for tickers with no cached data yet.
#
# ------------------------------------------------------------------------ #
# Scheduled run: this script is also fired every 12 hours by a macOS
# LaunchAgent (independent of any Claude Code / terminal session -- runs
# whenever the Mac is on, awake, and Docker Desktop is up).
#
#   Plist:  ~/Library/LaunchAgents/com.pairtrading.update-data.plist
#   Label:  com.pairtrading.update-data
#   Logs:   logs/update_data.log       (this script's own before/after output)
#           logs/launchd.out.log       (launchd stdout, should mirror the above)
#           logs/launchd.err.log       (launchd stderr -- should stay empty)
#
# Useful commands:
#   tail -f logs/update_data.log                                     # watch it live
#   launchctl list | grep pairtrading                                # confirm it's loaded
#   launchctl print gui/$(id -u)/com.pairtrading.update-data         # full status (runs, last exit code, interval)
#   launchctl kickstart -k gui/$(id -u)/com.pairtrading.update-data  # force an immediate run
#   launchctl bootout gui/$(id -u)/com.pairtrading.update-data \
#     && rm ~/Library/LaunchAgents/com.pairtrading.update-data.plist # uninstall
# ------------------------------------------------------------------------ #
set -euo pipefail
cd "$(dirname "$0")/.."

DAYS="${1:-60}"
DATA_DIR="user_data/data/okx/futures"

snapshot() {
    python3 - "$DATA_DIR" <<'EOF'
import sys, glob
import pandas as pd

files = sorted(glob.glob(f"{sys.argv[1]}/*_USDT_USDT-30m-futures.feather"))
if not files:
    print("  (no futures feather files found)")
    sys.exit(0)

rows = []
for f in files:
    ticker = f.split("/")[-1].split("_")[0]
    df = pd.read_feather(f)
    rows.append((ticker, len(df), df["date"].max() if len(df) else None))

n = len(rows)
last_dates = [r[2] for r in rows if r[2] is not None]
total_bars = sum(r[1] for r in rows)
print(f"  {n} tickers, {total_bars} total bars")
print(f"  most recent bar across tickers: {max(last_dates)}")
print(f"  stalest ticker's most recent bar: {min(last_dates)}"
      + (f" ({[r[0] for r in rows if r[2] == min(last_dates)][0]})" if last_dates else ""))

# Stash per-ticker (ticker, bars, last_date) for the diff step below.
import json
with open("/tmp/_update_data_snapshot.json", "w") as fh:
    json.dump([[t, b, str(d)] for t, b, d in rows], fh)
EOF
}

echo "=== Before ==="
snapshot
cp /tmp/_update_data_snapshot.json /tmp/_update_data_before.json 2>/dev/null || true

echo
echo "=== Downloading (incremental -- no --erase) ==="
docker compose run --rm freqtrade download-data \
    --config user_data/config.json \
    --exchange okx \
    --trading-mode futures \
    --timeframes 30m 1h \
    --days "$DAYS"

echo
echo "=== After ==="
snapshot

echo
python3 <<'EOF'
import json
before = {t: (b, d) for t, b, d in json.load(open("/tmp/_update_data_before.json"))}
after = json.load(open("/tmp/_update_data_snapshot.json"))

unchanged = [t for t, b, d in after if before.get(t, (None, None))[1] == d]
new_tickers = [t for t, b, d in after if t not in before]

if unchanged:
    print(f"WARNING: {len(unchanged)} ticker(s) got no new bars this run: {', '.join(unchanged)}")
    print("  (fine if you updated very recently; worth a second look otherwise)")
else:
    print("Every existing ticker's most recent bar advanced. Looks good.")
if new_tickers:
    print(f"New tickers picked up: {', '.join(new_tickers)}")
EOF
