#!/usr/bin/env python3
"""Snapshot open interest for every OKX perpetual, every 5 minutes.

WHY THIS EXISTS. Open interest is the only reading that separates a liquidation
from a repricing: OI falling means contracts were destroyed and somebody was
forced out, OI rising means somebody took a new position. Nothing else in this
project's data can tell those apart -- the perp basis (mark minus index) widens
the same way whether a trader was liquidated out or leveraged in.

WHY WE COLLECT IT FORWARD INSTEAD OF DOWNLOADING IT. OKX serves OI history at
5m/1h/1d only, and the depth is capped: 1h reaches ~21 days, 1d reaches 180, and
paging further back returns error 50030 "Illegal time range". Measured
2026-10-07. The 180-day daily series is also currency-aggregated and
quote-denominated, so a 5% price drop looks like a 5% OI drop. There is no
archive to buy and no archive to fetch. The only way to have this series in a
year is to start now.

WHY 5 MINUTES. Measured 2026-10-07, polling every 15s for 4 minutes: OI is live,
not throttled. BTC and ETH change on every 15-second poll; the illiquid names
(ZORA, YGG) change about every 45 seconds. So the exchange would support
1-minute sampling and every reading would be genuinely new.
5 minutes is chosen anyway, because:
  - it puts SIX samples inside each 30-minute bar of the price panel, which is
    what it takes to see whether OI fell or rose around a dislocation. One
    sample per bar cannot answer the question this series exists to answer.
  - every 6th row IS the 30-minute panel, and the grid still aligns if the
    1-minute price work ever happens.
  - 13.5MB/day raw (measured: 47KB per poll, 288 polls), ~700MB/year as
    parquet. 1-minute would be 68MB/day on a 20GB disk with 8.9GB free.
  - per-minute changes on a small-cap OI series are mostly tick noise that you
    would average back up to 5 minutes before using.

THE ts FIELD IS NOT A LAST-UPDATED TIME. It moved on every single poll for all
five instruments measured, including ZORA whose OI value only changed 5 times in
16 polls. It is the server's response clock. It says NOTHING about how stale a
reading is -- do not build a staleness feature out of it. The index is poll_ts,
our own UTC clock, which is what the 5-minute grid is defined on. srv_ts is
carried for diagnostics only.

oi_ccy IS THE COLUMN THAT MATTERS: coin-denominated open interest, which does
not move when price moves. oi (contracts) and oi_usd are carried because they
cost nothing and let the contract multiplier be reconstructed if a coin ever
changes it.

Stdlib only -- no ccxt, no requests -- so it runs anywhere with python3. OKX
returns 403 without a User-Agent header, which is the one non-obvious part.

Usage: scripts/collect_oi.py [OUTDIR]       (default trading_data/oi)
Writes/appends OUTDIR/YYYY-MM-DD.csv, one row per instrument per poll.
Exits nonzero on failure without writing a partial row, so cron logs the gap.
"""
import csv
import datetime as dt
import json
import os
import sys
import urllib.request

URL = "https://www.okx.com/api/v5/public/open-interest?instType=SWAP"
UA = "Mozilla/5.0 (compatible; pairs-research/1.0)"
COLS = ["poll_ts", "inst_id", "oi", "oi_ccy", "oi_usd", "srv_ts"]


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as fh:
        payload = json.load(fh)
    if payload.get("code") != "0":
        raise RuntimeError(f"okx code {payload.get('code')}: {payload.get('msg')}")
    rows = payload.get("data") or []
    if not rows:
        raise RuntimeError("okx returned no instruments")
    return rows


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trading_data", "oi")
    os.makedirs(outdir, exist_ok=True)

    rows = fetch()
    # Our own clock, floored to the minute: the grid is defined on poll time,
    # never on the exchange's response clock. See the note above about srv_ts.
    now = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    poll_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    path = os.path.join(outdir, f"{now.date()}.csv")

    # Build every row before opening the file: a bad payload must not leave a
    # half-written poll behind for the merge step to trip over.
    out = [[poll_ts, r["instId"], r["oi"], r["oiCcy"], r["oiUsd"], r["ts"]] for r in rows]

    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COLS)
        w.writerows(out)
    print(f"[oi] {poll_ts}  {len(out)} instruments -> {path}")


if __name__ == "__main__":
    main()
