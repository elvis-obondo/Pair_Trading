"""HL-MASTER1 integrity item 6 (second half): event counts and NaN shares around the archive seams, the order-book gaps and the Sep/Oct 2026 ctx gaps.

    python -u research/dataset/master_seams.py UNIT > research/dataset/logs/master_seams_UNIT.log      (UNIT = pair | coin)

PER DAY (UTC day of entry_time): n_events and, for every group file, the mean NaN share over that file's numeric columns (key and categorical columns excluded as in master_colreport). Output
research/datasets/master/work/{unit}/seams_daily.parquet (day, n_events, one column per group file).
LOG:
  1. the five archive seams (flowfeat.SEAM_BARS: 2025-06-08 09:30, 2025-06-08 10:00, 2025-07-19 09:30, 2025-07-27 11:30, 2025-09-27 09:00): events in the 24 h before and the 24 h from the seam bar, and the
     per-group mean NaN share in the same two windows, and the day-level median over all days for scale;
  2. ORDER-BOOK GAPS from the SOURCE coverage: the extractor's per-day index files (research/datasets/l2/{day}_l2_index.parquet: every (coin, hour) file found): per day coin-hours present / expected
     (expected = 24 x the day's coin count, taken as the larger of that day's own coin count and the median of the neighbouring 7 days'), listed for every day with present < expected (entirely missing days
     included, present = 0), and next to it the effect: the day's events and the g8 mean NaN share;
  3. CTX GAPS from the SOURCE coverage: asset_ctxs minutes present per coin-day (research/datasets/ctxs/{day}.parquet: distinct snapshot minutes of each coin, over 1,440); per month the mean missing share over coin-days
     (the planner quoted 6% / 28% / 64% for Aug / Sep / Oct 2026: reproduced here from the source) and the days from 2026-08-15 with their missing share, next to the g7 mean NaN share and the g7 maximum NaN share;
  4. each group's day-level NaN share by month (mean of the daily values) so level changes are visible next to the column drift table.
Descriptive; nothing is fitted. Every threshold in 2 and 3 is a reporting aid (tag A), not a gate.
"""
import os, sys, time, glob
from multiprocessing import Pool
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths
import flowfeat as ff
import master_colreport as CR

WORK = CR.WORK
G = {}


def init(unit):
    E = pd.read_parquet(os.path.join(WORK, unit, "events.parquet"), columns=["event_id", "entry_time"])
    day = pd.to_datetime(E.entry_time).dt.floor("D")
    codes, days = pd.factorize(day, sort=True)
    G["codes"], G["days"], G["event_id"] = codes.astype(np.int64), days, E.event_id.to_numpy()
    G["cnt"] = np.bincount(codes, minlength=len(days)).astype(float)


def one_file(args):
    path, cols = args
    acc = np.zeros(len(G["days"]))
    mx = np.zeros(len(G["days"]))
    mxn = np.full(len(G["days"]), "", dtype=object)
    n = 0
    for c in cols:
        t = pq.read_table(path, columns=["event_id", c]).to_pandas()
        assert (t.event_id.to_numpy() == G["event_id"]).all()
        x = t[c].to_numpy(np.float64)
        sh = np.bincount(G["codes"], weights=(~np.isfinite(x)).astype(float), minlength=len(G["days"])) / np.maximum(G["cnt"], 1)
        acc += sh
        better = sh > mx
        mx = np.where(better, sh, mx)
        mxn[better] = c
        n += 1
    return os.path.basename(path)[:-8], acc / max(n, 1), n, mx, mxn


def main():
    unit = sys.argv[1]
    t0 = time.time()
    os.makedirs(os.path.join(WORK, unit, "reports"), exist_ok=True)
    init(unit)
    num, _ = CR.numeric_columns(unit)
    byfile = {}
    for p, c in num:
        byfile.setdefault(p, []).append(c)
    with Pool(int(os.environ.get("NPROC", 7)), initializer=init, initargs=(unit,)) as pool:
        res = pool.map(one_file, list(byfile.items()), chunksize=1)
    days = G["days"]
    D = pd.DataFrame({"day": days, "n_events": G["cnt"].astype(int)})
    for name, share, n, mx, mxn in res:
        D[name] = share
        D[name + "_max"] = mx
        D[name + "_maxcol"] = mxn
        print(f"[SEAMS {unit}] {name}: {n} columns  [{time.time() - t0:.0f}s]")
    D.to_parquet(os.path.join(WORK, unit, "reports", "seams_daily.parquet"), index=False)
    groups = [r[0] for r in res]
    print("   per group and day the table also holds the MAXIMUM NaN share over the group's columns and that column's name (columns <group>_max, <group>_maxcol in seams_daily.parquet)")
    print(f"\n[SEAMS {unit}] days {len(D)}; events {int(D.n_events.sum()):,}; median events per day {D.n_events.median():.0f}")
    med = D[groups].median()
    print("   median daily NaN share per group: " + ", ".join(f"{g} {100 * med[g]:.1f}%" for g in groups))
    # events (not days) for the two windows: use per-event timestamps
    E = pd.read_parquet(os.path.join(WORK, unit, "events.parquet"), columns=["entry_time"])
    t = pd.to_datetime(E.entry_time)
    print("\n1. ARCHIVE SEAMS (events and mean NaN share by group, 24 h before | 24 h from the seam bar; day-level approximation for the NaN shares: the UTC day before | the UTC day of the seam)")
    for S in ff.SEAM_BARS:
        nb = int(((t >= S - pd.Timedelta(hours=24)) & (t < S)).sum())
        na = int(((t >= S) & (t < S + pd.Timedelta(hours=24))).sum())
        d0, d1 = S.floor("D") - pd.Timedelta(days=1), S.floor("D")
        rb, ra = D[D.day == d0], D[D.day == d1]
        sb = {g: (100 * float(rb[g].iloc[0]) if len(rb) else np.nan) for g in groups}
        sa = {g: (100 * float(ra[g].iloc[0]) if len(ra) else np.nan) for g in groups}
        print(f"   {S}: events {nb:,} | {na:,}")
        print("      NaN % before: " + ", ".join(f"{g} {sb[g]:.1f}" for g in groups))
        print("      NaN % after : " + ", ".join(f"{g} {sa[g]:.1f}" for g in groups))
    print("\n2. ORDER-BOOK COVERAGE FROM THE SOURCE (extractor index files): days with coin-hours present < expected")
    l2dir = os.path.join(paths.DATASETS, "l2")
    rows = []
    for f in sorted(glob.glob(os.path.join(l2dir, "*_l2_index.parquet"))):
        I = pd.read_parquet(f, columns=["coin", "hour", "n_snapshots"])
        rows.append((pd.Timestamp(os.path.basename(f)[:8]), int((I.n_snapshots >= 0).sum()), I.coin.nunique()))
    C = pd.DataFrame(rows, columns=["day", "present", "coins"])
    if len(C):
        C["exp_coins"] = np.maximum(C.coins, C.coins.rolling(15, center=True, min_periods=3).median().round())
        C["expected"] = 24 * C.exp_coins
        C = C.merge(D[["day", "n_events"] + (["g8"] if "g8" in groups else [])], on="day", how="left")
        bad = C[C.present < C.expected]
        print(f"   {len(C)} days in the index; {len(bad)} with coin-hours present < expected (present = 0 for days entirely missing); coin-hours missing in total {int((bad.expected - bad.present).sum()):,} of {int(C.expected.sum()):,}")
        for _, r_ in bad.iterrows():
            print(f"     {r_.day:%Y-%m-%d}  present {int(r_.present):,} / expected {int(r_.expected):,} ({100 * r_.present / r_.expected:.1f}%)  events that day {0 if pd.isna(r_.n_events) else int(r_.n_events):,}  g8 mean NaN {('%.1f%%' % (100 * r_.g8)) if 'g8' in C and pd.notna(r_.get('g8')) else 'n/a'}")
    else:
        print("   no l2 index files on this machine")
    print("\n3. CTX COVERAGE FROM THE SOURCE (asset_ctxs distinct snapshot minutes per coin-day, of 1,440)")
    ctxdir = os.path.join(paths.DATASETS, "ctxs")
    cr = []
    for f in sorted(glob.glob(os.path.join(ctxdir, "2025*.parquet")) + glob.glob(os.path.join(ctxdir, "2026*.parquet"))):
        t = pd.read_parquet(f, columns=["time", "coin"])
        m = t.time.dt.floor("min")
        per = pd.DataFrame({"coin": t.coin.astype(str).to_numpy(), "m": m.to_numpy()}).drop_duplicates().groupby("coin").size()
        cr.append((pd.Timestamp(os.path.basename(f)[:8]), len(per), float(per.mean()), float(1 - per.mean() / 1440)))
    X = pd.DataFrame(cr, columns=["day", "coins", "minutes_per_coin_mean", "missing_share"])
    if len(X):
        X["month"] = X.day.dt.strftime("%Y-%m")
        print("   missing share by month (mean over days of 1 - mean minutes per coin / 1,440): " + ", ".join(f"{m} {100 * v:.1f}%" for m, v in X.groupby("month").missing_share.mean().items()))
        X = X.merge(D[["day"] + (["g7", "g7_max", "g7_maxcol"] if "g7" in groups else [])], on="day", how="left")
        late = X[X.day >= "2026-08-15"]
        for _, r_ in late.iterrows():
            print(f"     {r_.day:%Y-%m-%d}  ctx missing {100 * r_.missing_share:5.1f}%  g7 mean NaN {('%.1f%%' % (100 * r_.g7)) if 'g7' in X and pd.notna(r_.g7) else 'n/a'}  g7 max NaN {('%.1f%% (%s)' % (100 * r_.g7_max, r_.g7_maxcol)) if 'g7' in X and pd.notna(r_.g7) else 'n/a'}")
    else:
        print("   no ctx day files on this machine")
    print("\n4. DAILY NaN SHARE BY MONTH (mean over days), per group")
    D["month"] = D.day.dt.strftime("%Y-%m")
    M = D.groupby("month")[groups].mean() * 100
    print("   month    " + " ".join(f"{g:>9}" for g in groups))
    for m, r in M.iterrows():
        print(f"   {m}  " + " ".join(f"{r[g]:9.1f}" for g in groups))
    print(f"[SEAMS {unit}] done  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
