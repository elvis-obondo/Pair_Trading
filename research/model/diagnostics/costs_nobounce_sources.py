"""COSTS1 no-bounce, source-sensitivity line (planner ruling 2026-11-18; print-only on existing data; no change to the headline cell or the bands).
For each of the eight priority runs: the trades that have BOTH a ctxs mid and a G8 table mid at all four stamps (entry and exit, both legs). On exactly those trades:
gross ratio with the ctxs mid, gross ratio with the G8 mid (mid-to-mid gross / saved close-based gross, summed), the share of the run's trades, and how the two mids differ
(median and p90 of |ctxs mid - G8 mid| in bp over the four stamps of every such trade). Same formulas, stamps and alignment as costs_nobounce.py reprice().
PERIOD-SENSITIVITY LINE (planner ruling 2026-11-18, print only): for every run and every entry month, the gross ratio with the ctxs + G8 fallback mid (the headline's version) on the trades with
all four mids, the trade counts, and the mid source used (share of those trades whose four mids are all ctxs, and share with at least one stamp taken from the G8 table).
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import costs_nobounce as N  # noqa: E402

RUNS = [(s, mo, fee) for s in ("vault", "test") for mo in (10, 20) for fee in ("maker", "taker")]
OUT = {}
t00 = time.time()
G8 = pd.read_parquet(N.C1 + "g8/g8_rows.parquet", columns=["coin", "minute", "mid"])
Gs = G8.drop_duplicates(["coin", "minute"]).set_index(["coin", "minute"])["mid"]
assert len(Gs) == len(G8)
print(f"[NOBOUNCE-SRC] script costs_nobounce_sources.py; G8 rows {len(G8):,}", flush=True)
for side in ("vault", "test"):
    ev = N.load_events(side)
    trades = {}
    ids = set()
    for mo in (10, 20):
        for fee in ("maker", "taker"):
            d = pd.read_parquet(f"{N.T}trades_q0.01_stopnone_fee{fee}{N.SFX[(side, mo)]}.parquet").reset_index(drop=True)
            trades[(mo, fee)] = d
            ids |= set(d["event_id"])
    geo = ev[ev["event_id"].isin(ids)].set_index("event_id")
    coins = sorted(set(geo["ticker_a"]) | set(geo["ticker_b"]))
    base = int(geo["t0m"].min()) - 1
    n_min = int(geo["t0m"].max()) + N.K + 2 - base
    cid, CL, ML, MS = N.load_arrays(side, coins, base, n_min)
    for (mo, fee), d in trades.items():
        g = geo.reindex(d["event_id"])
        b_ = np.abs(g["beta"].to_numpy())
        la, lb = d["notional"].to_numpy() / (1 + b_), d["notional"].to_numpy() * b_ / (1 + b_)
        z, beta = g["z"].to_numpy(), g["beta"].to_numpy()
        dira = np.where(z >= 0, -1.0, 1.0)
        dirb = np.where(z >= 0, 1.0, -1.0) * np.where(beta >= 0, 1.0, -1.0)
        t0m, exm = N.epoch_min(d["t0"]), N.epoch_min(d["exit_time"])
        ia, ib = d["ticker_a"].map(cid).to_numpy().astype(np.int64), d["ticker_b"].map(cid).to_numpy().astype(np.int64)
        mc = [ML[ia, t0m - base], ML[ia, exm - base], ML[ib, t0m - base], ML[ib, exm - base]]
        st4 = [(d["ticker_a"], t0m), (d["ticker_a"], exm), (d["ticker_b"], t0m), (d["ticker_b"], exm)]
        mg = []
        for c_, s_ in st4:
            v = Gs.reindex(pd.MultiIndex.from_arrays([np.asarray(c_), np.asarray(s_)])).to_numpy(float)
            with np.errstate(invalid="ignore", divide="ignore"):
                mg.append(np.where(v > 0, np.log(v), np.nan))
        both = np.ones(len(d), bool)
        for a, b in zip(mc, mg):
            both &= np.isfinite(a) & np.isfinite(b)

        def gm(v):
            return la * dira * (np.exp(v[1] - v[0]) - 1) + lb * dirb * (np.exp(v[3] - v[2]) - 1)
        gs = d["gross_pnl"].to_numpy()
        gc, gg = gm(mc), gm(mg)
        diffs = np.concatenate([np.abs(np.exp(a[both] - b[both]) - 1) * 1e4 for a, b in zip(mc, mg)])
        sg = gs[both].sum()
        key = f"{side} open{mo} {fee}"
        fb = [np.where(np.isfinite(a), a, b) for a, b in zip(mc, mg)]
        have_f = np.ones(len(d), bool)
        for a in fb:
            have_f &= np.isfinite(a)
        allctx = np.ones(len(d), bool)
        for a in mc:
            allctx &= np.isfinite(a)
        gf = gm(fb)
        mon = pd.to_datetime(d["t0"], utc=True).dt.strftime("%Y-%m").to_numpy()
        monthly = {}
        for mth in sorted(set(mon)):
            m = have_f & (mon == mth)
            sgm = gs[m].sum()
            monthly[mth] = dict(n=int((mon == mth).sum()), n_matched=int(m.sum()), close_gross=float(sgm), mid_gross=float(gf[m].sum()), ratio=float(gf[m].sum() / sgm) if sgm > 0 else None,
                                share_all_ctxs=float(allctx[m].mean()) if m.any() else None, share_any_g8=float((~allctx[m]).mean()) if m.any() else None)
            mm_ = monthly[mth]
            print(f"[NOBOUNCE-SRC]   {side} open{mo} {fee} {mth}: trades {mm_['n']:,}, matched {mm_['n_matched']:,}; close gross ${mm_['close_gross']:,.2f}, mid gross ${mm_['mid_gross']:,.2f}, gross ratio {('n/m' if mm_['ratio'] is None else format(mm_['ratio'], '.1%'))}; all four mids from ctxs {format(mm_['share_all_ctxs'] or 0, '.1%')}, at least one stamp from G8 {format(mm_['share_any_g8'] or 0, '.1%')}", flush=True)
        r = dict(monthly=monthly, n=len(d), n_both=int(both.sum()), share=float(both.mean()), close_gross=float(sg), ctxs_gross=float(gc[both].sum()), g8_gross=float(gg[both].sum()),
                 ratio_ctxs=float(gc[both].sum() / sg) if sg > 0 else None, ratio_g8=float(gg[both].sum() / sg) if sg > 0 else None,
                 diff_median_bp=float(np.median(diffs)), diff_p90_bp=float(np.percentile(diffs, 90)))
        OUT[key] = r
        print(f"[NOBOUNCE-SRC] {key}: trades with both mids at all four stamps {r['n_both']:,} of {r['n']:,} ({r['share']:.1%}); close gross ${sg:,.2f}; mid-to-mid gross ctxs ${r['ctxs_gross']:,.2f} (ratio {r['ratio_ctxs']:.1%}) vs G8 ${r['g8_gross']:,.2f} (ratio {r['ratio_g8']:.1%}); |ctxs - G8| over the four stamps: median {r['diff_median_bp']:.3f} bp, p90 {r['diff_p90_bp']:.3f} bp", flush=True)
    del CL, ML, MS
json.dump(OUT, open(N.C1 + "costs_nobounce_sources.json", "w"), indent=1)
print(f"[NOBOUNCE-SRC] wrote logs/costs1/costs_nobounce_sources.json; total {time.time() - t00:.0f}s", flush=True)
