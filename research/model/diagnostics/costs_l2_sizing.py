"""COSTS1 pre-build sizing (planner brief 2026-11-13): how many (coin, UTC hour) L2 archive files cover every entry and exit leg of the saved
vault and test-month trades, how many bytes that is (from the 2026-10-25 pilot's per-file sizes, build8_l2_pilot.log), what it costs, and how big
the traded legs are against the extractor's fixed $1,000 slippage size. ANALYSIS OF SAVED FILES ONLY: no AWS call, no engine run.

    python -u research/model/diagnostics/costs_l2_sizing.py > research/model/diagnostics/costs_l2_sizing.log

File set rule (stated, fixed before the run): per trade and per leg (coin A, coin B) the hours containing [t0 - 1 min, t0 + 15 min] (entry book and the
maker-fill window) and [exit - 1 min, exit + 1 min] (exit book). "Priority" = q 1% / no stop / maker and taker, max_open 10 and 20 (vault: tags
vault_open10 / vault_open20; test months: base and open20). "All 48" = every saved run of the 4 tags (24 per tag).
Bytes per file: pilot totals (compressed GB / files): 2025-07-15 2.613/4824, 2025-10-10 2.642/5198, 2026-03-01 1.789/4632, 2026-09-15 0.467/4272. The snapshot
cadence fell from ~0.55 s to ~5 s somewhere between 2026-03-01 and 2026-09-15 (date unknown: not listed, no AWS call made). Size per file BY DAY (checker 2026-11-13):
days up to and including 2026-03-01: low 0.386 MB (2026-03-01), high 0.542 MB (2025-07-15, the largest pilot size); days between 2026-03-01 and 2026-09-15: low 0.109 MB, high 0.386 MB
(the change could be on any day between); days from 2026-09-15: 0.109 MB both. The pilot averages include every coin while traded coins skew illiquid, so the high bound is probably generous.
Two exit-window designs are sized: exit books [exit - 1, exit + 1] and [exit - 1, exit + 15] (a resting-order window at the exit for maker runs).
Prices: pilot's own figures, laptop egress $0.68 / 7.51 GB = $0.0905 per GB; EC2 us-east-2 cross-region $10 / 970 GB = $0.0103 per GB (instance time extra, not counted).
Throughput: pilot 4,824 files / 1,083 s = 4.45 files per second per process (laptop).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
assert os.environ.get("PROFIT1_VAULT", "") != "1"
import harness as H  # noqa: E402
import vault_loader as VL  # noqa: E402

T = os.path.join(MODEL, "logs", "profit1") + os.sep
PILOT = {"2025-07-15": (2.613, 4824), "2025-10-10": (2.642, 5198), "2026-03-01": (1.789, 4632), "2026-09-15": (0.467, 4272)}
MB = {k: v[0] * 1e3 / v[1] for k, v in PILOT.items()}
EGRESS_LAPTOP, EGRESS_EC2 = 0.68 / 7.51, 10.0 / 970.0
FPS = 4824 / 1083.0
PRIO = [(0.01, "none", "maker"), (0.01, "none", "taker")]
ALL = [(q, s, f) for q in (0.01, 0.005, 0.001) for s in ("0p5", "1p0", "2p0", "none") for f in ("maker", "taker")]
SIDES = {"vault": ["_vault_open10", "_vault_open20"], "test": ["", "_open20"]}


def load(suffixes, runs):
    fr = []
    for sfx in suffixes:
        for (q, stop, fee) in runs:
            d = pd.read_parquet(f"{T}trades_q{q}_stop{stop}_fee{fee}{sfx}.parquet", columns=["event_id", "ticker_a", "ticker_b", "t0", "exit_time", "notional"])
            d["run"] = f"{q}_{stop}_{fee}{sfx}"
            fr.append(d)
    return pd.concat(fr, ignore_index=True)


def mb_by_day(day, bound):
    if day <= "20260301":
        return 0.386 if bound == "low" else 0.542
    if day < "20260915":
        return 0.109 if bound == "low" else 0.386
    return 0.109


def files(d, exit_hi):
    t0, tx = pd.to_datetime(d["t0"], utc=True), pd.to_datetime(d["exit_time"], utc=True)
    S = set()
    for side in ("ticker_a", "ticker_b"):
        for t in (t0 - pd.Timedelta(minutes=1), t0 + pd.Timedelta(minutes=15), tx - pd.Timedelta(minutes=1), tx + pd.Timedelta(minutes=exit_hi)):
            S |= set(zip(d[side], t.dt.strftime("%Y%m%d"), t.dt.hour))
    # every hour between the two ends of the entry window is covered because the window is 16 minutes
    return S


def main():
    print("[SIZING] file set rule, bytes per file and prices: see the docstring. No AWS call was made.")
    for nm, (a, n) in PILOT.items():
        print(f"[SIZING] pilot {nm}: {a} GB / {n:,} files = {MB[nm]:.3f} MB per file")
    print(f"[SIZING] egress $/GB: laptop {EGRESS_LAPTOP:.4f}, EC2 us-east-2 cross-region {EGRESS_EC2:.4f}; pilot throughput {FPS:.2f} files/s per process")
    tot = {}
    for exit_hi in (1, 15):
        for rn, runs in (("priority", PRIO), ("all48", ALL)):
            for side in ("vault", "test"):
                d = load(SIDES[side], runs)
                F = files(d, exit_hi)
                n = len(F)
                lo = sum(mb_by_day(x, "low") for _, x, _ in F) / 1e3
                hi = sum(mb_by_day(x, "high") for _, x, _ in F) / 1e3
                print(f"[SIZING] exit window [exit-1, exit+{exit_hi}] {rn} {side}: {len(d):,} trades, {d.drop_duplicates(['event_id']).shape[0]:,} distinct events, {n:,} coin-hour files, {len({c for c, _, _ in F})} coins, "
                      f"{len({x for _, x, _ in F})} days; compressed {lo:.1f} to {hi:.1f} GB")
                tot[(exit_hi, rn, side)] = (n, lo, hi)
            n = sum(tot[(exit_hi, rn, s_)][0] for s_ in ("vault", "test"))
            lo = sum(tot[(exit_hi, rn, s_)][1] for s_ in ("vault", "test"))
            hi = sum(tot[(exit_hi, rn, s_)][2] for s_ in ("vault", "test"))
            print(f"[SIZING] exit window +{exit_hi} {rn} both sides: {n:,} files, {lo:.1f} to {hi:.1f} GB compressed; egress to laptop ${lo * EGRESS_LAPTOP:.2f} to ${hi * EGRESS_LAPTOP:.2f}; "
                  f"EC2 us-east-2 cross-region ${lo * EGRESS_EC2:.2f} to ${hi * EGRESS_EC2:.2f} (instance time extra); "
                  f"one process at the pilot rate {n / FPS / 3600:.1f} h, 16 processes {n / FPS / 3600 / 16:.2f} h")
    # leg size against the extractor's fixed $1,000 slippage size
    geo_v = VL.load_vault_events(columns=["beta"]).reset_index(drop=True).set_index("event_id")["beta"]
    geo_t = H.load_search_events(columns=["beta"])["beta"]
    for side, beta in (("vault", geo_v), ("test", geo_t)):
        d = load(SIDES[side], PRIO)
        b = beta.reindex(d["event_id"]).abs().to_numpy()
        la, lb = d["notional"].to_numpy() / (1 + b), d["notional"].to_numpy() * b / (1 + b)
        big = np.maximum(la, lb)
        print(f"[SIZING] {side} priority runs, larger leg USD: median {np.median(big):,.0f}, p90 {np.quantile(big, 0.9):,.0f}, max {big.max():,.0f}; "
              f"share of trades with a larger leg above $1,000: {float((big > 1000).mean()):.1%}; above $500: {float((big > 500).mean()):.1%}")


if __name__ == "__main__":
    main()
