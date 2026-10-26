"""HL-MASTER1 G8 orchestration: the daily l2 tables (build8_l2.py, s3://pair-trading-hl-289869684922/build8/full/) -> cutoff-row dense tables per coin -> event columns of both units.

    python -u research/dataset/master_g8_run.py > research/dataset/logs/master_g8.log

Coverage table (log): snapshot rate by month (snapshots per coin-hour from the index files), coin-minutes with no snapshot, NaN shares of every column by month at the event rows.
"""
import os, sys, time, glob
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g8 as G8
import master_g5_run as R5
import flowfeat as ff
import paths

WORK = R5.WORK
L2DIR = os.path.join(paths.DATASETS, "l2")


def day_job(f):
    D = pd.read_parquet(f)
    return G8.cutoff_rows(D)


def main():
    t0 = time.time()
    files = sorted(glob.glob(os.path.join(L2DIR, "*_l2.parquet")))
    idx = sorted(glob.glob(os.path.join(L2DIR, "*_l2_index.parquet")))
    print(f"[G8] {len(files)} daily tables, {len(idx)} index files  [{time.time() - t0:.0f}s]", flush=True)
    with Pool(int(os.environ.get("NPROC", 7))) as pool:
        parts = pool.map(day_job, files, chunksize=4)
    print(f"[G8] cutoff rows read: {sum(len(p[1]) for p in parts):,}  [{time.time() - t0:.0f}s]", flush=True)
    I = pd.concat([pd.read_parquet(f).assign(day=os.path.basename(f)[:8]) for f in idx], ignore_index=True)
    I["month"] = I.day.str[:6]
    g = I[I.n_snapshots >= 0].groupby("month")
    print("[G8 COVERAGE] by month: coin-hour files, snapshots per coin-hour (median), median gap ms, coin-minutes present / (files x 60), non-monotone steps, crossed rows")
    for m, x in g:
        print(f"   {m}: {len(x):,} files, {x.n_snapshots.median():.0f} per file, gap {x.gap_median_ms.median():.0f} ms, minutes {100 * x.n_minutes.sum() / (60 * len(x)):.2f}%, nonmono {int(x.n_nonmonotone.sum())}, crossed {int(x.n_crossed.sum())}")
    ev = R5.event_tables()
    coins = sorted(set(ev["pair"][0].ticker_a) | set(ev["pair"][0].ticker_b) | set(ev["coin"][0].ticker_a))
    F = {}
    for c in coins:
        F[c] = G8.feature_matrix(G8.dense_table(parts, c))
    print(f"[G8] feature matrices for {len(F)} coins  [{time.time() - t0:.0f}s]", flush=True)
    for u, (E, o) in ev.items():
        j = ((o - ff.CUT_PHASE) // 30).astype(np.int64)
        legs = {"a": E.ticker_a.to_numpy()} | ({"b": E.ticker_b.to_numpy()} if u == "pair" else {})
        cols = {}
        mats = {}
        for lg, names in legs.items():
            M = np.full((len(E), len(G8.NAMES)), np.nan, np.float32)
            for c in np.unique(names):
                m = names == c
                if c in F:
                    M[m] = F[c][j[m]]
            mats[lg] = M
            for k, nm in enumerate(G8.NAMES):
                cols[f"{lg}_{nm}"] = M[:, k]
        if u == "pair":
            for k, nm in enumerate(G8.NAMES):
                if nm not in G8.NO_DIFF:
                    cols[f"d_{nm}"] = mats["a"][:, k] - mats["b"][:, k]
        df = pd.DataFrame(cols)
        df.insert(0, "event_id", E.event_id.to_numpy())
        df.to_parquet(os.path.join(WORK, u, "g8.parquet"), index=False)
        mon = pd.to_datetime(E.entry_time).dt.strftime("%Y-%m").to_numpy()
        print(f"[G8 {u}] {len(df):,} rows x {df.shape[1] - 1} columns written  [{time.time() - t0:.0f}s]")
        for nm in ("spread_bp", "bid_d10", "slip_buy_1k", "rel_bid_d10", "chg6h_spread_bp", "snapshot_age_s", "book_reach_bid_bp"):
            v = df[f"a_{nm}"].to_numpy()
            tab = pd.Series(np.isnan(v)).groupby(mon).mean() * 100
            print(f"   a_{nm}: NaN {100 * np.isnan(v).mean():.1f}%  median {np.nanmedian(v):+.4g}  by month NaN%: " + " ".join(f"{k[2:]} {x:.0f}" for k, x in tab.items()))


if __name__ == "__main__":
    main()
