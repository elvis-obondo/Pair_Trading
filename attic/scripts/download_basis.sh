#!/usr/bin/env bash
# Download the two price series we have never used, for the whole whitelist.
#
#   index  -- the spot index price. New: no files existed before this script.
#   mark   -- OKX's fair perp price. Files existed but started 2025-08-09;
#             --prepend backfills them to the exchange's limit (~2024-04-21).
#
# With index on disk there are three prices per instrument instead of one, and
# two spreads that have never been measured:
#     mark - index   the basis: did the move happen in the perp or in spot
#     close - mark   execution dislocation: a trade printing away from fair
#
# funding_rate is NOT here. OKX caps it at 2026-06-08 and --prepend returns
# nothing, so that series stays partial no matter what we do.
#
# Usage: scripts/download_basis.sh [DAYS]   (default 900, the exchange limit)
set -uo pipefail
cd "$(dirname "$0")/.."
DAYS="${1:-900}"

echo "=== index (fresh download, $DAYS days) ==="
docker compose run --rm freqtrade download-data \
    --config user_data/config.json --exchange okx --trading-mode futures \
    --timeframes 1h --candle-types index --days "$DAYS"

echo
echo "=== mark (backfill existing files, $DAYS days) ==="
docker compose run --rm freqtrade download-data \
    --config user_data/config.json --exchange okx --trading-mode futures \
    --timeframes 1h --candle-types mark --days "$DAYS" --prepend

echo
echo "=== coverage ==="
python3 - <<'PY'
import glob, pandas as pd
for kind in ("index", "mark"):
    rows = []
    for f in sorted(glob.glob(f"user_data/data/okx/futures/*_USDT_USDT-1h-{kind}.feather")):
        d = pd.read_feather(f)
        if len(d):
            rows.append((f.split("/")[-1].split("_")[0], len(d), d.date.min(), d.date.max()))
    if not rows:
        print(f"{kind}: no files"); continue
    n = len(rows)
    starts = pd.Series([r[2] for r in rows])
    print(f"{kind}: {n} files, median rows {pd.Series([r[1] for r in rows]).median():.0f}, "
          f"earliest start {starts.min().date()}, median start {starts.median().date()}, "
          f"latest start {starts.max().date()}")
PY
