"""Independent recount for the HL-TARGET2 trial (no matrices, no lib code): for the trial's test-month events whose path lies inside one UTC day, rebuild the per-minute real-mid flags of that day
straight from the raw day files (ctxs cache day file + G8 slim day file) with plain pandas, and compare the per-leg longest missing run over path minutes 1..k_x with the label file's max_gap_len_leg.
Prints counts only (no label values). Reads logs/s2/trial/s2_labels_search.parquet (statuses, exit_k, gap fields) and the event list (tickers, t0).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
import harness as H  # noqa: E402

DAYS = ["2026-01-15", "2026-04-08"]
lab = pd.read_parquet(MODEL + "/logs/s2/trial/s2_labels_search.parquet", columns=["event_id", "t0", "status", "exit_k", "max_gap_len_leg", "gap_flag", "n_filled", "test"])
ev = H.load_search_events(columns=["ticker_a", "ticker_b"]).reset_index(drop=True)[["event_id", "ticker_a", "ticker_b"]]
lab = lab.merge(ev, on="event_id", validate="one_to_one")
tot = same = any_miss_lab = any_miss_me = 0
for day in DAYS:
    d0 = pd.Timestamp(day, tz="UTC")
    sub = lab[(lab["t0"].dt.strftime("%Y-%m-%d") == day) & (lab["status"] == 0)].copy()
    sub["mod"] = sub["t0"].dt.hour * 60 + sub["t0"].dt.minute
    sub = sub[sub["mod"] + sub["exit_k"] <= 1439]
    real = {}
    c = pd.read_parquet(MODEL + f"/logs/profit1/ctxs_cache/{day.replace('-', '')}.parquet", columns=["time", "coin", "mid_px"])
    c = c[(c["time"].dt.second == 0) & (c["time"].dt.microsecond == 0) & (c["mid_px"] > 0)]
    g = pd.read_parquet(MODEL + f"/logs/s2/g8_slim/{day.replace('-', '')}.parquet", columns=["coin", "minute", "mid"])
    g = g[g["mid"] > 0]
    base = int(d0.value // 60_000_000_000)
    cm = ((c["time"] - d0) // pd.Timedelta(minutes=1)).to_numpy()
    for coin, grp in pd.concat([pd.DataFrame({"coin": c["coin"].astype(str), "m": cm}), pd.DataFrame({"coin": g["coin"], "m": g["minute"].to_numpy().astype(np.int64) - base})]).groupby("coin"):
        a = np.zeros(1440, bool)
        m = grp["m"].to_numpy()
        a[m[(m >= 0) & (m < 1440)]] = True
        real[coin] = a
    mx = np.zeros(len(sub), int)
    for i, r in enumerate(sub.itertuples()):
        for coin in (r.ticker_a, r.ticker_b):
            miss = ~real[coin][r.mod + 1:r.mod + r.exit_k + 1]
            run = best = 0
            for v in miss:
                run = run + 1 if v else 0
                best = max(best, run)
            mx[i] = max(mx[i], best)
    n = len(sub)
    eq = int((mx == sub["max_gap_len_leg"].to_numpy()).sum())
    print(f"[TRIALCHECK] {day}: ok test events with the whole path in the day {n:,}; per-leg longest missing run recomputed from the raw day files equals the label file's max_gap_len_leg on {eq:,} ({100 * eq / max(n, 1):.2f}%); events with any missing minute: recount {int((mx > 0).sum()):,}, label file {int((sub['max_gap_len_leg'] > 0).sum()):,}; flagged (run >= 6): recount {int((mx >= 6).sum()):,}, label file {int(sub['gap_flag'].sum()):,}")
    tot += n
    same += eq
print(f"[TRIALCHECK] total {tot:,} events, equal on {same:,}")
assert same == tot
