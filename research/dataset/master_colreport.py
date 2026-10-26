"""HL-MASTER1 Part Z (side-by-side) and integrity item 6 (drift by month), one pass over every numeric column of the master table. Descriptive: nothing is fitted, no split, no selection.

    python -u research/dataset/master_colreport.py UNIT   (UNIT = pair | coin)  > research/dataset/logs/master_colreport_UNIT.log
    NPROC=7  controls the pool.

READING THE REPORT. AUC direction: > 0.5 means higher values of the column go with reaching mu (reach_10h = 1). Rows are NOT independent (the pair unit has many overlapping events of one pair on nearby bars), so every number is
descriptive and NO interval is attached. The table is for orientation, not selection. Drift rule: tagged A (assumed reading of "more than 3 monthly standard deviations": a month-to-month jump in the monthly mean above 3 x the sd of the
column's monthly means). Labels and anything that uses the future are NOT columns here: labels.parquet is the target and is never ranked; the key columns (KEYS below) are dropped; categorical columns (codes, sectors, hour, weekday) get a
reach rate per category instead of an AUC and stay out of the chart. DATE-LIKE columns (listing age / listing date, date_like = 1 in the table and marked "(date-like)" in the log): a calendar date or an age since a calendar date, so its AUC partly
measures WHEN a coin listed, i.e. time, not a coin trait (cos / sin of the hour are numeric and stay).

Rows: every event of the unit with label_gap == 0 (reach_10h is defined). Month = the entry month of the bar (UTC).
PER COLUMN (all group files except labels; id columns, text and the labels are skipped; the label table is the target, never a column):
  n, nan_share (over all events), const (1 if the column has one value)
  Missingness (checker): nan_reach, nan_non = NaN share among reachers / non-reachers over the label_gap = 0 events; nan_gap_flag = 1 when they differ by more than 0.05 (the AUC uses finite values only and would hide it).
  Part Z:  median, q25, q75 of reachers (reach_10h = 1) and of non-reachers; std_diff = (mean_reach - mean_non) / pooled sd; auc = P(col(reacher) > col(non-reacher)) + 0.5 P(tie) over rows where the column is finite
           (rank method: average ranks); auc_by_month = the same AUC per month with >= 500 usable rows and at least 50 of each class (NaN otherwise); the series is kept as columns auc_YYYYMM;
           n_months, n_pos_months (AUC > 0.5), n_neg_months (AUC < 0.5), maj_share = max(n_pos, n_neg) / n_months (near-misses), stable_sign = 1 when n_months >= 6 and all months are on the same side of 0.5.
  Drift:   per month the mean, q25, median, q75 and NaN share (all label_gap == 0 events, not only usable ones are not needed: the whole unit by month, so the table also shows seams) -> columns m_mean_YYYYMM etc. in the
           second output; jump_ratio = max over months of |mean_m - mean_{m-1}| / sd(monthly means) (months with >= 200 usable rows); flagged_months = months where that ratio exceeds 3.
OUTPUT (all under research/datasets/master/work/{unit}/reports/, which the group-file globs do not see): colreport_partz.csv, colreport_drift_monthly.parquet (column, month, mean, q25, median, q75, nan_share, n), colreport_drift_flags.csv
LOG: counts, the stable-sign column count, the 30 largest |AUC - 0.5| columns, the columns with flagged jumps (top 40 by ratio).
PNG: research/dataset/logs/partz_{unit}_top_auc.png (plain matplotlib bar chart of the 30 largest |AUC - 0.5|).
The report says the table is for orientation, not selection.
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

WORK = os.path.join(paths.DATASETS, "master", "work")
SKIP_FILES = {"labels.parquet"}
KEYS = {"event_id", "bar_index", "pair_index", "seg_start_bar", "seg_end_bar", "entry_time", "pair_triggers_true"}       # keys and a column that counts the future: never ranked
CAT_SUFFIX = ("_coin_code", "_listing_src", "_margin_table_id", "_sector", "_cg_status")
CAT_NAMES = {"utc_hour", "weekday"}


def is_cat(name, typ):
    return name.endswith(CAT_SUFFIX) or name in CAT_NAMES or str(typ).startswith(("string", "large_string"))
MIN_MONTH, MIN_CLASS, MIN_DRIFT = 500, 50, 200
G = {}


def init(unit):
    E = pd.read_parquet(os.path.join(WORK, unit, "events.parquet"), columns=["event_id", "entry_time"])
    L = pd.read_parquet(os.path.join(WORK, unit, "labels.parquet"), columns=["event_id", "label_gap", "reach_10h"])
    assert (E.event_id.to_numpy() == L.event_id.to_numpy()).all()
    G["unit"] = unit
    G["ok"] = (L.label_gap.to_numpy() == 0) & np.isfinite(L.reach_10h.to_numpy(float))
    G["y"] = L.reach_10h.to_numpy(float) > 0.5
    G["month"] = pd.to_datetime(E.entry_time).dt.strftime("%Y%m").astype("category")
    G["mcodes"] = G["month"].cat.codes.to_numpy()
    G["months"] = list(G["month"].cat.categories)
    G["event_id"] = E.event_id.to_numpy()


def auc_rank(x, y):
    """AUC of x against y (True = positive) on finite x, average ranks; (auc, n_pos, n_neg)."""
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan, n1, n0
    r = pd.Series(x).rank(method="average").to_numpy()
    return (r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0), n1, n0


def one_column(args):
    path, col = args
    ev = pq.read_table(path, columns=["event_id", col]).to_pandas()
    assert (ev.event_id.to_numpy() == G["event_id"]).all(), (path, "row order differs from events")
    x = ev[col].to_numpy(np.float64)
    ok, y, mc, months = G["ok"], G["y"], G["mcodes"], G["months"]
    fin = np.isfinite(x)
    use = ok & fin
    row = {"column": col, "file": os.path.basename(path), "date_like": int(("listing_age" in col) or ("listing_date" in col) or col.endswith("_date")), "n": int(use.sum()), "nan_share": float(1 - fin.mean())}
    xs, ys = x[use], y[use]
    row["const"] = int(use.sum() > 0 and np.nanmin(xs) == np.nanmax(xs))
    yy = y[ok]
    nanv = ~fin[ok]
    row["nan_reach"] = float(nanv[yy].mean()) if yy.any() else np.nan
    row["nan_non"] = float(nanv[~yy].mean()) if (~yy).any() else np.nan
    row["nan_gap_flag"] = int(abs(row["nan_reach"] - row["nan_non"]) > 0.05) if np.isfinite(row["nan_reach"]) and np.isfinite(row["nan_non"]) else 0
    drift = []
    for k, mname in enumerate(months):                                         # drift: all events of the month, label_gap or not
        sel = mc == k
        v = x[sel & fin]
        drift.append((col, mname, float(v.mean()) if len(v) else np.nan, *(np.percentile(v, [25, 50, 75]) if len(v) else (np.nan,) * 3), float(1 - fin[sel].mean()) if sel.any() else np.nan, int(len(v))))
    if row["const"] or len(xs) < 1000 or ys.sum() == 0 or ys.all():
        return row, drift
    a, n1, n0 = auc_rank(xs, ys)
    row["auc"] = a
    for nm, v in (("reach", xs[ys]), ("non", xs[~ys])):
        q = np.percentile(v, [25, 50, 75])
        row[f"q25_{nm}"], row[f"median_{nm}"], row[f"q75_{nm}"] = q
        row[f"mean_{nm}"] = float(v.mean())
    sd = np.sqrt(((n1 - 1) * xs[ys].var(ddof=1) + (n0 - 1) * xs[~ys].var(ddof=1)) / (n1 + n0 - 2)) if n1 > 1 and n0 > 1 else np.nan
    row["std_diff"] = (row["mean_reach"] - row["mean_non"]) / sd if sd and sd > 0 else np.nan
    mm = mc[use]
    aucs = []
    for k, mname in enumerate(months):
        s = mm == k
        if s.sum() >= MIN_MONTH and ys[s].sum() >= MIN_CLASS and (~ys[s]).sum() >= MIN_CLASS:
            av, _, _ = auc_rank(xs[s], ys[s])
        else:
            av = np.nan
        row[f"auc_{mname}"] = av
        aucs.append(av)
    aucs = np.array(aucs, float)
    f = aucs[np.isfinite(aucs)]
    row["n_months"], row["n_pos_months"], row["n_neg_months"] = len(f), int((f > 0.5).sum()), int((f < 0.5).sum())
    row["maj_share"] = max(row["n_pos_months"], row["n_neg_months"]) / len(f) if len(f) else np.nan
    row["stable_sign"] = int(len(f) >= 6 and ((f > 0.5).all() or (f < 0.5).all()))
    return row, drift


def numeric_columns(unit):
    num, cat = [], []
    for p in sorted(glob.glob(os.path.join(WORK, unit, "*.parquet"))):
        if os.path.basename(p) in SKIP_FILES:
            continue
        sch = pq.ParquetFile(p).schema_arrow
        for f in sch:
            if f.name in KEYS:
                continue
            if is_cat(f.name, f.type):
                cat.append((p, f.name))
            elif str(f.type).startswith(("float", "int", "double", "bool", "uint")):
                num.append((p, f.name))
    return num, cat


def cat_column(args):
    path, col = args
    ev = pq.read_table(path, columns=["event_id", col]).to_pandas()
    assert (ev.event_id.to_numpy() == G["event_id"]).all()
    v = ev[col].astype(str).to_numpy()
    ok, y = G["ok"], G["y"]
    df = pd.DataFrame({"v": v[ok], "y": y[ok]})
    t = df.groupby("v").y.agg(["size", "mean"]).reset_index()
    t.insert(0, "column", col)
    t.columns = ["column", "category", "n", "reach_rate"]
    return t


def main():
    unit = sys.argv[1]
    t0 = time.time()
    os.makedirs(os.path.join(WORK, unit, "reports"), exist_ok=True)
    init(unit)
    cols, cats = numeric_columns(unit)
    print(f"[COLREPORT {unit}] events {len(G['ok']):,}, usable (label_gap = 0) {int(G['ok'].sum()):,}, reach_10h share {100 * G['y'][G['ok']].mean():.2f}%; {len(cols):,} numeric columns and {len(cats)} categorical columns in {len(set(c[0] for c in cols))} group files; months {G['months'][0]}..{G['months'][-1]}  [{time.time() - t0:.0f}s]", flush=True)
    print("   AUC direction: > 0.5 = higher values go with reaching mu. Rows are not independent (overlapping events of one pair), so no interval is attached. For orientation, not selection. Drift rule tagged A.")
    rows, drift = [], []
    with Pool(int(os.environ.get("NPROC", 7)), initializer=init, initargs=(unit,)) as pool:
        for q, (r, d) in enumerate(pool.imap_unordered(one_column, cols, chunksize=2)):
            rows.append(r)
            drift += d
            if (q + 1) % 200 == 0:
                print(f"  {q + 1}/{len(cols)} columns  [{time.time() - t0:.0f}s]", flush=True)
        CT = pd.concat(pool.map(cat_column, cats), ignore_index=True) if cats else pd.DataFrame()
    CT.to_csv(os.path.join(WORK, unit, "reports", "colreport_categorical.csv"), index=False)
    R = pd.DataFrame(rows).sort_values(["file", "column"]).reset_index(drop=True)
    R.to_csv(os.path.join(WORK, unit, "reports", "colreport_partz.csv"), index=False)
    D = pd.DataFrame(drift, columns=["column", "month", "mean", "q25", "median", "q75", "nan_share", "n"])
    D.to_parquet(os.path.join(WORK, unit, "reports", "colreport_drift_monthly.parquet"), index=False)
    # drift flags
    fl = []
    for c, g in D.groupby("column", sort=False):
        g = g[(g.n >= MIN_DRIFT) & g["mean"].notna()].sort_values("month")
        if len(g) < 4:
            continue
        sd = g["mean"].std(ddof=1)
        if not sd or sd == 0:
            continue
        j = g["mean"].diff().abs() / sd
        fl.append((c, float(j.max()), " ".join(g.month[j > 3])))
    F = pd.DataFrame(fl, columns=["column", "jump_ratio", "flagged_months"]).sort_values("jump_ratio", ascending=False)
    F.to_csv(os.path.join(WORK, unit, "reports", "colreport_drift_flags.csv"), index=False)
    # log
    A = R[R.auc.notna()].copy()
    A["dev"] = (A.auc - 0.5).abs()
    print(f"\n[PART Z {unit}] columns with an AUC: {len(A):,}; constant columns: {int(R.const.sum())}; columns with a stable sign across months (>= 6 months, all on one side of 0.5): {int(A.stable_sign.sum())}")
    print(f"   |AUC - 0.5| quantiles over columns 50/90/99/max: " + " / ".join(f"{A.dev.quantile(q):.4f}" for q in (.5, .9, .99, 1)))
    print(f"   columns with NaN shares among reachers and non-reachers differing by more than 5 points: {int(R.nan_gap_flag.sum())}" + (" -> " + ", ".join(R[R.nan_gap_flag == 1].column.head(15)) if R.nan_gap_flag.sum() else ""))
    print(f"   near-misses: columns whose qualifying months lean one way in >= 80% of months but not all: {int(((A.maj_share >= 0.8) & (A.stable_sign == 0) & (A.n_months >= 6)).sum())}")
    if len(CT):
        big = CT[CT.n >= 500]
        print(f"   categorical columns ({CT.column.nunique()}): reach rate by category (categories with >= 500 events), range per column:")
        for c, g in big.groupby("column"):
            print(f"     {c:<28} {len(g)} categories, reach rate {g.reach_rate.min():.3f} .. {g.reach_rate.max():.3f}")
    print("   the 30 largest |AUC - 0.5| (column, auc, std_diff, stable_sign, months pos/neg):")
    for _, r in A.sort_values("dev", ascending=False).head(30).iterrows():
        print(f"     {r.column + (' (date-like)' if r.date_like else ''):<44} auc {r.auc:.4f}  sd_diff {r.std_diff:+.3f}  stable {int(r.stable_sign)}  {int(r.n_pos_months)}/{int(r.n_neg_months)}")
    print(f"\n[DRIFT {unit}] columns with a month-to-month jump above 3 sd of their monthly means: {int((F.jump_ratio > 3).sum())} of {len(F):,}")
    for _, r in F[F.jump_ratio > 3].head(40).iterrows():
        print(f"     {r.column:<44} max jump {r.jump_ratio:.1f} sd  months {r.flagged_months}")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        T = A.sort_values("dev", ascending=False).head(30).iloc[::-1]
        plt.figure(figsize=(8, 8))
        plt.barh(T.column, T.auc - 0.5)
        plt.axvline(0, color="k", lw=0.5)
        plt.xlabel("AUC - 0.5 against reach_10h (orientation only, not selection)")
        plt.title(f"{unit}: 30 largest single-column AUCs")
        plt.tight_layout()
        out = os.path.join(HERE, "logs", f"partz_{unit}_top_auc.png")
        plt.savefig(out, dpi=110)
        print(f"   PNG {out}")
    except Exception as e:
        print("   PNG failed:", e)
    print(f"[COLREPORT {unit}] done  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
