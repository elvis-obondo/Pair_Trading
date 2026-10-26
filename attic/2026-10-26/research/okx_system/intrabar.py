"""Fine-resolution log prices, for checking exits between 30-minute bars.

WHY THIS EXISTS

The backtest checks its stop at 30-minute bar closes. A position that crosses the
level intrabar and recovers before the close is never stopped there -- it stays
open and can go on to take profit. The live monitor sees that crossing in ~100ms
and kills it.

So part of the backtest's 20% take-profit rate may be intrabar stop-outs in
disguise, and the live book converts them to losses. This module supplies the
1-minute prices needed to find out.

WHY IT DOES NOT USE data_loader.get_price_levels(timeframe="1m")

It would work, and it would destroy the 30-minute store on the way. The
normalized cache is one feather per TICKER -- user_data/normalized/BTC.feather --
with no timeframe in the name, so syncing it at 1m overwrites the 30m data every
downstream caller depends on. This reads the OKX futures feathers directly and
touches nothing else.

WHAT IS NOT RECOMPUTED HERE

Nothing about the signal. beta, alpha, mu and sigma are rolling statistics over
336 THIRTY-MINUTE bars and stay that way; the entry threshold, the stop distance
and the take-profit level are all defined in those terms. Only the question "has
the frozen level been crossed yet" moves to a finer grid -- and that needs no
rolling window at all, which is the same reason the live monitor can answer it on
every tick in 174MB.
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import glob

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OKX_FUTURES_DIR = os.path.join(PROJECT_ROOT, "user_data", "data", "okx", "futures")
SUFFIX = "_USDT_USDT-{tf}-futures.feather"


def _utc(ts) -> pd.Timestamp:
    """Coerce to a UTC-aware Timestamp, whether it arrives naive or aware."""
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def available(timeframe: str = "1m") -> dict:
    """{ticker: path} for every instrument with data at this timeframe."""
    pat = os.path.join(OKX_FUTURES_DIR, f"*_USDT_USDT-{timeframe}-futures.feather")
    out = {}
    for p in sorted(glob.glob(pat)):
        name = os.path.basename(p)
        out[name.split("_USDT_USDT-")[0]] = p
    return out


def coverage(timeframe: str = "1m") -> pd.DataFrame:
    """One row per instrument: bars, first and last timestamp.

    Cheap enough to run before a long job, and it answers the only question that
    matters up front -- whether the window you intend to test is actually there.
    """
    rows = []
    for t, p in available(timeframe).items():
        d = pd.read_feather(p, columns=["date"])
        if not len(d):
            continue
        rows.append({"ticker": t, "bars": len(d),
                     "first": d.date.iloc[0], "last": d.date.iloc[-1]})
    return pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame()


def load_panel(tickers=None, start=None, end=None,
               timeframe: str = "1m") -> pd.DataFrame:
    """LOG-price panel on a fine grid: datetime index, one column per ticker.

    Log prices, to match what the 30-minute path produces -- the spread geometry
    is defined on ln(close) and mixing the two would be silently wrong.

    Columns are NOT forced to a common index beyond an outer join. A missing
    minute stays NaN rather than being filled: a forward-filled price is a price
    nobody traded at, and checking a stop against one is the same stale-price
    mistake the live monitor refuses to make.
    """
    paths = available(timeframe)
    if tickers is not None:
        paths = {t: p for t, p in paths.items() if t in set(tickers)}
    if not paths:
        raise SystemExit(f"no {timeframe} data under {OKX_FUTURES_DIR}")

    cols = {}
    for t, p in paths.items():
        d = pd.read_feather(p, columns=["date", "close"])
        # Accept naive or tz-aware bounds. pd.Timestamp(x, tz=...) RAISES on an
        # already-aware value rather than converting, and the 30m panel's index
        # is aware, so a caller passing panel.index[i] straight through would
        # otherwise blow up.
        if start is not None:
            d = d[d.date >= _utc(start)]
        if end is not None:
            d = d[d.date <= _utc(end)]
        if not len(d):
            continue
        s = d.set_index("date").close
        s = s[s > 0]
        cols[t] = np.log(s.astype(float))
    if not cols:
        raise SystemExit(f"no {timeframe} rows in {start} .. {end}")
    panel = pd.DataFrame(cols).sort_index()
    # Force nanosecond resolution. The feathers carry datetime64[ms] and the 30m
    # panel is datetime64[ns]; pandas 2.x refuses to compare a ms-unit index
    # against an ns Timestamp, so the intrabar window slice raises rather than
    # silently doing the wrong thing. Normalise here, once.
    panel.index = pd.DatetimeIndex(panel.index).as_unit("ns")
    panel.index.name = "date"
    return panel


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()

    c = coverage(a.timeframe)
    if not len(c):
        raise SystemExit(f"no {a.timeframe} data yet")
    print(f"{len(c)} instruments with {a.timeframe} data")
    print(f"  bars   min {c.bars.min():,}  median {int(c.bars.median()):,}  max {c.bars.max():,}")
    print(f"  window {c['first'].max()}  ->  {c['last'].min()}   (common to all)")
    print(f"  widest {c['first'].min()}  ->  {c['last'].max()}")
    if a.summary:
        print()
        print(c.sort_values("bars").head(10).to_string())


if __name__ == "__main__":
    main()
