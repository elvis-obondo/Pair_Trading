"""HL-MASTER1 Part Z (post-v1): the descriptive side-by-side on the FROZEN v1 files, with the chance-adjusted AUC. Orientation, not selection: nothing is fitted, no split, no model.

    python -u research/dataset/master_partz.py UNIT > research/dataset/logs/master_partz_UNIT.log        (UNIT = coin | pair; NPROC sets the pool)

INPUT. The v1 group files of work/{unit}/ (the bytes the version was frozen from). FIRST every v1 file of the unit is re-hashed against s3://.../master/versions/v1/MANIFEST.json (master_manifest.verify): any mismatch stops the run before a
number is produced. Rows: events with label_gap = 0 (reach_10h defined). Columns: every numeric column of every group file except the labels (target), the keys and the categorical columns (master_colreport.numeric_columns).
PER COLUMN (master_colreport.one_column, unchanged): n, NaN share, median / q25 / q75 of reachers and non-reachers, standardized difference, AUC against reach_10h (> 0.5 = higher values go with reaching mu), AUC per month, number of
months and the share on the majority side, stable_sign, NaN share among reachers and non-reachers (flag when they differ by more than 5 points), date-like label.
CHANCE-ADJUSTED AUC (the addition): the usable events are cut into 10 DECILES of chance_10h (the probability that a random-sign path reaches |z| within 10 h, a G0 label; strata cut BY VALUE: chance_10h has 51 levels and each level lies wholly in one stratum, so the strata are about 10% each, their sizes are printed); inside each decile the
column's AUC against reach_10h is computed; auc_adj = sum_d w_d AUC_d / sum_d w_d with w_d = n1_d x n0_d (reachers x non-reachers: the standard stratified AUC), deciles with fewer than 1,000 rows or fewer than 50 of a class skipped.
CAVEAT: chance_10h is a LABEL (computed from the event's own future 1-minute steps, sign-flipped), so stratifying on it conditions on the path's future choppiness: the figure answers "does the column separate reachers among paths of similar future
choppiness", it is NOT available at t = 0, and columns that proxy future volatility shrink most under the adjustment by construction (chance itself moves with 1-minute chop, CHOP-DRIFT). A column that only tells how easy the path is to reach (it moves with chance_10h) loses its AUC; one that ranks reachers inside every decile keeps it. The per-decile AUCs are kept (auc_dec0 .. auc_dec9), and so are the decile edges and the reach rate
per decile (printed once). Columns are RANKED by |auc_adj - 0.5|.
DRIFT FLAG. A column that has at least one 'unexplained' column-month in docs/release_v1/drift_explained_{unit}.csv (a jump of its monthly mean with no known cause, drift rule tagged A) is flagged drift_unexplained = 1 in the table and marked
"(drift?)" in the log. Rows are not independent (overlapping events of one pair), so no interval is attached.
OUTPUT: work/{unit}/reports/partz_v1.csv, partz_v1_categorical.csv, partz_v1_deciles.csv; the log; PNG logs/partz_{unit}_top_auc_adj.png (30 largest |auc_adj - 0.5|).
"""
import os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_colreport as CR
import master_manifest as MF

WORK = CR.WORK
DECILES = 10
MIN_DEC, MIN_CLASS_DEC = 1000, 50


def init(unit):
    CR.init(unit)
    L = pd.read_parquet(os.path.join(WORK, unit, "labels.parquet"), columns=["event_id", "label_gap", "chance_10h", "reach_10h"])
    ok = CR.G["ok"]
    ch = L.chance_10h.to_numpy(float)
    dec = np.full(len(L), -1, np.int8)
    idx = np.flatnonzero(ok & np.isfinite(ch))
    # strata cut BY VALUE: every distinct chance_10h level lies wholly in one stratum (events with the same chance are never split by row order); the
    # levels are walked in increasing order and a stratum closes at the first level where the cumulative share reaches k / 10, so the strata are about, not exactly, 10% each
    lv, inv, cnt = np.unique(ch[idx], return_inverse=True, return_counts=True)
    cum = np.cumsum(cnt) / cnt.sum()
    code = np.minimum(np.floor(cum * DECILES - 1e-9).astype(int), DECILES - 1)
    code = np.maximum.accumulate(code)
    dec[idx] = code[inv].astype(np.int8)
    CR.G["dec"], CR.G["chance"] = dec, ch


def column(args):
    row, drift = CR.one_column(args)
    path, col = args
    import pyarrow.parquet as pq
    x = pq.read_table(path, columns=[col]).column(0).to_numpy(zero_copy_only=False).astype(np.float64)
    ok, y, dec = CR.G["ok"], CR.G["y"], CR.G["dec"]
    use = ok & np.isfinite(x) & (dec >= 0)
    aucs, ws = [], []
    for d in range(DECILES):
        s = use & (dec == d)
        n1 = int((s & y).sum()); n0 = int((s & ~y).sum())
        if s.sum() >= MIN_DEC and n1 >= MIN_CLASS_DEC and n0 >= MIN_CLASS_DEC and np.nanmin(x[s]) != np.nanmax(x[s]):
            a, _, _ = CR.auc_rank(x[s], y[s])
        else:
            a = np.nan
        row[f"auc_dec{d}"] = a
        if np.isfinite(a):
            aucs.append(a); ws.append(float(n1) * float(n0))
    row["auc_adj"] = float(np.average(aucs, weights=ws)) if aucs else np.nan
    row["auc_adj_plainmean"] = float(np.mean(aucs)) if aucs else np.nan                # diagnostic: every stratum counts the same
    row["n_dec"] = len(aucs)
    return row


def main():
    unit = sys.argv[1]
    t0 = time.time()
    rep = os.path.join(WORK, unit, "reports")
    os.makedirs(rep, exist_ok=True)
    # 0. provenance receipt: which code produced this log (the stale-code failure this guards against)
    gs = os.path.join(HERE, "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    for f in ("master_partz.py", "master_colreport.py", "master_manifest.py"):
        print(f"[PART Z {unit}] sha256 {f}: {MF.sha(os.path.join(HERE, f))}", flush=True)
    print(f"[PART Z {unit}] git_head {git_head} ({git_dirty} uncommitted paths at last laptop snapshot); start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)
    # 1. verify the frozen files before any number is produced
    man = MF.json.load(open(os.path.join(MF.VERS, "v1", "MANIFEST.json")))
    rels = [k for k in man["files"] if k.startswith(unit + "/") and k.endswith(".parquet")]
    assert f"{unit}/labels.parquet" in rels, f"{unit}/labels.parquet missing from the v1 manifest file set; the strata and the target both come from it"
    MF.verify("v1", rels, base=WORK)
    print(f"[PART Z {unit}] {len(rels)} v1 files re-hashed against MANIFEST.json (sha256): all match  [{time.time() - t0:.0f}s]", flush=True)
    init(unit)
    num, cats = CR.numeric_columns(unit)
    ok, y, dec = CR.G["ok"], CR.G["y"], CR.G["dec"]
    n_nan_chance = int((ok & (dec == -1)).sum())
    print(f"[PART Z {unit}] events {len(ok):,}, usable {int(ok.sum()):,}, reach_10h share {100 * y[ok].mean():.2f}%; {len(num):,} numeric columns, {len(cats)} categorical; AUC > 0.5 = higher values go with reaching mu; rows are not independent, no interval attached; orientation, not selection")
    print(f"[PART Z {unit}] usable events with NaN chance_10h (excluded from every stratum and every adjusted AUC): {n_nan_chance:,}")
    ch = CR.G["chance"]
    tab = []
    for d in range(DECILES):
        s = ok & (dec == d)
        assert s.sum() > 0, f"decile {d} is empty: a single chance_10h level holds more than 10% of events, the value cut is degenerate"
        tab.append((d, float(np.nanmin(ch[s])), float(np.nanmax(ch[s])), int(s.sum()), float(y[s].mean())))
    T = pd.DataFrame(tab, columns=["decile", "chance_min", "chance_max", "n", "reach_rate"])
    T.to_csv(os.path.join(rep, "partz_v1_deciles.csv"), index=False)
    print("   chance_10h deciles (decile, chance range, events, reach rate): " + "; ".join(f"{int(r.decile)}: {r.chance_min:.2f}-{r.chance_max:.2f}, {r.n:,}, {r.reach_rate:.3f}" for r in T.itertuples()))
    with Pool(int(os.environ.get("NPROC", 7)), initializer=init, initargs=(unit,)) as pool:
        rows = []
        for q, r in enumerate(pool.imap_unordered(column, num, chunksize=2)):
            rows.append(r)
            if (q + 1) % 200 == 0:
                print(f"  {q + 1}/{len(num)} columns  [{time.time() - t0:.0f}s]", flush=True)
        CT = pd.concat(pool.map(CR.cat_column, cats), ignore_index=True) if cats else pd.DataFrame()
    R = pd.DataFrame(rows)
    D = pd.read_csv(os.path.join(HERE, "..", "..", "docs", "release_v1", f"drift_explained_{unit}.csv"))
    unexpl = set(D[D.cause == "unexplained"].column)
    R["drift_unexplained"] = R["column"].isin(unexpl).astype(int)
    R["dev_adj"] = (R.auc_adj - 0.5).abs()
    R["dev"] = (R.auc - 0.5).abs()
    R = R.sort_values("dev_adj", ascending=False)
    R.drop(columns=["dev", "dev_adj"]).to_csv(os.path.join(rep, "partz_v1.csv"), index=False)
    CT.to_csv(os.path.join(rep, "partz_v1_categorical.csv"), index=False)
    A = R[R.auc_adj.notna()]
    print(f"\n[PART Z {unit}] columns with a chance-adjusted AUC: {len(A):,} of {len(R):,}; constant columns {int(R.const.sum())}; stable sign across months (>= 6 months, all one side): {int(R.stable_sign.sum())}; NaN-gap flags (> 5 points): {int(R.nan_gap_flag.sum())}; unexplained-drift columns: {int(R.drift_unexplained.sum())}")
    # duplicate columns: the same column name appears in two group files (e.g. beta in events.parquet and g2.parquet) with identical values; every count
    # above and below (columns with an adjusted AUC, stable-sign, drift-unexplained, the "falls by more than half" count) counts each occurrence, so a duplicate is counted twice
    def _close(s, rtol=1e-6):     # every entry of a small float Series equal within rtol of the first; NaN counts as equal only to NaN
        v = s.to_numpy(float)
        ref = v[0]
        return bool(np.all(np.isnan(v))) if np.isnan(ref) else bool(np.all(~np.isnan(v)) and np.allclose(v, ref, rtol=rtol))
    def _is_dupe(g):              # same column stored in two group files: n exact, auc/auc_adj close (float roundoff differs between the two copies, ~1e-6 relative)
        return g["n"].nunique() == 1 and _close(g["auc"]) and _close(g["auc_adj"])
    dupe_names = sorted(n for n, g in R.groupby("column") if len(g) > 1 and _is_dupe(g))
    print(f"[PART Z {unit}] duplicate columns (same name in two group files; n exact, auc/auc_adj within 1e-6 -- the g2.parquet copy is stored as float32 against events.parquet's float64, which moves rank-AUC ties at about 1e-10; counted twice in every figure above and below): {len(dupe_names)} {dupe_names}")
    print(f"   |AUC - 0.5| quantiles over columns 50/90/99/max:  raw " + " / ".join(f"{R.dev.quantile(q):.4f}" for q in (.5, .9, .99, 1)) + "   adjusted " + " / ".join(f"{A.dev_adj.quantile(q):.4f}" for q in (.5, .9, .99, 1)))
    print(f"   correlation of the raw and the adjusted deviation over columns: {np.corrcoef(A.dev, A.dev_adj)[0, 1]:.3f}; columns whose AUC falls by more than half when adjusted: {int(((A.dev_adj < 0.5 * A.dev) & (A.dev > 0.02)).sum())} of {int((A.dev > 0.02).sum())} with a raw deviation above 0.02")
    print("   the 40 largest |auc_adj - 0.5| (column, auc raw, auc adjusted, deciles on the same side, stable sign, months pos/neg; (drift?) = unexplained jump in its monthly mean, (date-like) = listing age):")
    for _, r in A.head(40).iterrows():
        side = int(np.sum([(r[f"auc_dec{d}"] > 0.5) == (r.auc_adj > 0.5) for d in range(DECILES) if np.isfinite(r[f"auc_dec{d}"])]))
        tag = (" (drift?)" if r.drift_unexplained else "") + (" (date-like)" if r.date_like else "")
        label = f"{r['column']}@{r['file']}" + tag
        print(f"     {label:<58} raw {r.auc:.4f}  adj {r.auc_adj:.4f}  {side}/{int(r.n_dec)}  stable {int(r.stable_sign)}  {int(r.n_pos_months)}/{int(r.n_neg_months)}")
    if len(CT):
        big = CT[CT.n >= 500]
        print(f"   categorical columns ({CT.column.nunique()}): reach rate by category (categories with >= 500 events):")
        for c, g in big.groupby("column"):
            print(f"     {c:<28} {len(g)} categories, reach rate {g.reach_rate.min():.3f} .. {g.reach_rate.max():.3f}")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        B = A.head(30).iloc[::-1]
        plt.figure(figsize=(8, 8))
        plt.barh(B["column"], B.auc_adj - 0.5)
        plt.axvline(0, color="k", lw=0.5)
        plt.xlabel("chance-adjusted AUC - 0.5 against reach_10h (orientation, not selection)")
        plt.title(f"{unit}: 30 largest chance-adjusted single-column AUCs")
        plt.tight_layout()
        out = os.path.join(HERE, "logs", f"partz_{unit}_top_auc_adj.png")
        plt.savefig(out, dpi=110)
        print(f"   PNG {out}")
    except Exception as e:
        print("   PNG failed:", e)
    print(f"[PART Z {unit}] done  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
