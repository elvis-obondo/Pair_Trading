"""COSTS1 step 1b: the exact list of (coin, UTC hour) L2 archive files to pull, and which minutes of each file are needed. LOCAL, no AWS call.

    python -u research/model/diagnostics/costs_l2_targets.py > research/model/diagnostics/costs_l2_targets.log

Writes research/model/logs/costs1/l2_targets_priority.parquet: one row per file = coin, day (YYYYMMDD), hour, minutes (list of epoch-minute labels
floor(exchange ms / 60000) wanted from that file), n_minutes.

RULES (fixed before the run).
  Priority runs = q 1% / no stop / maker and taker, max_open 10 and 20, vault (tags vault_open10 / vault_open20) and test months (base / open20).
  Per trade and per leg (coin A and coin B), wall-clock minutes (UTC):
    entry book window  [t0 - 1, t0 + 15]   (t0 = the trade's t0 column = the wall-clock minute whose close prices the engine's entry fill; the book at t0 is the first
                                           snapshot of minute t0; t0 - 1 is kept as a before-the-fill reference; t0 + 1 .. t0 + 15 serve the maker waiting window
                                           up to 15 minutes and a taker fallback at its end)
    exit book window   [exit_time - 1, exit_time + 15]   (same roles at the exit)
  A needed minute m belongs to the file of its own UTC hour. The archive's folder hour is the node's receive clock, so a snapshot of minute m can sit in the
  previous folder hour: for minutes in the first 2 minutes of an hour the previous hour's file is added to the list for that minute (the extractor keeps the
  minimum-exchange-time snapshot of each wanted minute over all files it reads).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
T = os.path.join(MODEL, "logs", "profit1") + os.sep
OUT_DIR = os.path.join(MODEL, "logs", "costs1")
OUT = os.path.join(OUT_DIR, "l2_targets_priority.parquet")
PRIO = [(0.01, "none", "maker"), (0.01, "none", "taker")]
SIDES = {"vault": ["_vault_open10", "_vault_open20"], "test": ["", "_open20"]}


def load(suffixes):
    fr = []
    for sfx in suffixes:
        for (q, stop, fee) in PRIO:
            fr.append(pd.read_parquet(f"{T}trades_q{q}_stop{stop}_fee{fee}{sfx}.parquet", columns=["event_id", "ticker_a", "ticker_b", "t0", "exit_time"]))
    return pd.concat(fr, ignore_index=True)


def epoch_min(ts):
    return ((pd.to_datetime(ts, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(minutes=1)).to_numpy().astype("int64")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    wanted = {}                                   # (coin, epoch minute) -> None
    for side, sfx in SIDES.items():
        d = load(sfx).drop_duplicates(["event_id", "ticker_a", "ticker_b", "t0", "exit_time"])
        t0, tx = epoch_min(d["t0"]), epoch_min(d["exit_time"])
        n0 = len(wanted)
        for coin_col in ("ticker_a", "ticker_b"):
            coins = d[coin_col].to_numpy()
            for base, lo, hi in ((t0, -1, 15), (tx, -1, 15)):
                for off in range(lo, hi + 1):
                    ms = base + off
                    for c, m in zip(coins, ms):
                        wanted[(c, int(m))] = None
        print(f"[TARGETS] {side}: {len(d):,} distinct trades; wanted (coin, minute) pairs so far {len(wanted):,} (+{len(wanted) - n0:,})")
    df = pd.DataFrame(list(wanted.keys()), columns=["coin", "minute"])
    # file of each minute: own UTC hour; minutes 0 and 1 of an hour also ask the previous hour's file
    rows = []
    hour_id = df["minute"] // 60
    for k, (coin, minute, h) in enumerate(zip(df["coin"], df["minute"], hour_id)):
        rows.append((coin, int(h), int(minute)))
        if minute - h * 60 < 2:
            rows.append((coin, int(h) - 1, int(minute)))
    r = pd.DataFrame(rows, columns=["coin", "hour_id", "minute"])
    g = r.groupby(["coin", "hour_id"])["minute"].apply(lambda s: sorted(set(int(x) for x in s))).reset_index()
    ts = pd.to_datetime(g["hour_id"].to_numpy() * 3600, unit="s", utc=True)
    g["day"] = ts.strftime("%Y%m%d")
    g["hour"] = ts.hour
    g["n_minutes"] = g["minute"].map(len)
    g = g.rename(columns={"minute": "minutes"})[["coin", "day", "hour", "minutes", "n_minutes"]].sort_values(["day", "hour", "coin"]).reset_index(drop=True)
    g.to_parquet(OUT, index=False)
    print(f"[TARGETS] files {len(g):,}; coins {g['coin'].nunique()}; days {g['day'].nunique()}; wanted minutes in total {int(g['n_minutes'].sum()):,}; "
          f"files by period: vault (day >= 20260713) {int((g['day'] >= '20260713').sum()):,}, test {int((g['day'] < '20260713').sum()):,}; wrote {OUT}")
    import hashlib
    print(f"[TARGETS] sha256 {hashlib.sha256(open(OUT, 'rb').read()).hexdigest()}")


if __name__ == "__main__":
    main()
