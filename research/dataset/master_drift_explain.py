"""HL-MASTER1 integrity item 6 (the explanation): every flagged (column, month) of the drift table gets a CAUSE from the known seams and gaps, in this order of precedence; the rest are listed as unexplained.

    python -u research/dataset/master_drift_explain.py UNIT > research/dataset/logs/master_drift_explain_UNIT.log

Input: work/{unit}/reports/colreport_drift_flags.csv (column, jump_ratio, flagged_months: the months where |mean_m - mean_(m-1)| > 3 sd of the column's monthly means, rule tagged A) and colreport_partz.csv (column -> group file only).
CAUSES (a flagged month is assigned the first cause that applies; the months are those the log of master_seams / the dictionary's "Seams and gaps" documents):
  1 orderbook_rate     group g8, month 2026-06 or 2026-07: the snapshot rate drops from about 6,500 to 1,668 to 670 per coin-hour (the as-of row is staler)
  2 orderbook_gap      group g8, months 2025-10, 2025-11, 2026-07: archive days entirely missing or partial (2025-10-16 to 22, 2025-11-17 to 25, 2026-07-08 to 17)
  3 ctx_gap            group g7, months 2026-08, 2026-09, 2026-10: asset_ctxs snapshot minutes missing (6% / 28% / 64% of the minutes)
  4 archive_seam       flow-based groups (g2, g2b, g3, g4, g5_*, g6_*, g9a, events) in months 2025-06, 2025-07, 2025-09 (seams 06-08, 07-19, 07-27, 09-27)
  5 crash_month        any group in 2025-10 (the 2025-10-10 crash and its aftermath: volumes, volatility, forced liquidations, funding spikes)
  5b after_crash       month 2025-11 for a column that is ALSO flagged in 2025-10 AND whose 2025-11 change (mean_11 - mean_10) has the OPPOSITE sign to its 2025-10 change (mean_10 - mean_09): a true reversal of the crash level; same-sign cases stay unexplained
  5c seam_normaliser   groups g5 / g6, month 2025-08, volume_ratio / wallets_per_musd columns: their trailing 7-day median normaliser is rebuilt after the 2025-07-19 and 07-27 seams (needs about 7 days of clean data)
  6 listings           group g4 columns about listing age, liquidity rank or coin code; any group in a month with 5 or more new listings is NOT assumed (listing counts are not used)
  7 unexplained        everything else: listed with the largest jump ratio first (candidate genuine regime change; no cause is claimed)
OUTPUT: work/{unit}/reports/drift_explained.csv (column, group, month, cause) and the log: counts per cause and per group, the number of flagged columns fully explained / partly / not, the 30 largest unexplained.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths

WORK = os.path.join(paths.DATASETS, "master", "work")
FLOW_GROUPS = ("events", "g2", "g2b", "g3", "g4", "g5_a", "g5_b", "g5_net", "g5_shape", "g6_a", "g6_b", "g6_net", "g9a")


def cause(group, col, month, flagged_all=(), opposite=False):
    if group == "g8" and month in ("202606", "202607"):
        return "orderbook_rate"
    if group == "g8" and month in ("202510", "202511", "202607"):
        return "orderbook_gap"
    if group == "g7" and month in ("202608", "202609", "202610"):
        return "ctx_gap"
    if group in FLOW_GROUPS and month in ("202506", "202507", "202509"):
        return "archive_seam"
    if month == "202510":
        return "crash_month"
    if month == "202511" and "202510" in flagged_all and opposite:
        return "after_crash"
    if group.startswith(("g5", "g6")) and month == "202508" and any(k in col for k in ("volume_ratio", "wallets_per_musd")):
        return "seam_normaliser"
    if group == "g4" and any(k in col for k in ("listing", "liq_rank", "liq_7d", "liq_30d", "coin_code")):
        return "listings"
    return "unexplained"


def main():
    unit = sys.argv[1]
    d = os.path.join(WORK, unit, "reports")
    F = pd.read_csv(os.path.join(d, "colreport_drift_flags.csv"))
    P = pd.read_csv(os.path.join(d, "colreport_partz.csv"), usecols=["column", "file"])
    P["group"] = P["file"].str.replace(".parquet", "", regex=False)
    grp = dict(zip(P.column, P.group))
    F = F[F.jump_ratio > 3].copy()
    M = pd.read_parquet(os.path.join(d, "colreport_drift_monthly.parquet")).sort_values(["column", "month"])
    M["chg"] = M.groupby("column")["mean"].diff()
    chg = {(c, m): v for c, m, v in zip(M["column"], M["month"], M["chg"])}
    rows = []
    for _, r in F.iterrows():
        for m in str(r.flagged_months).split():
            g = grp.get(r["column"], "?")
            rows.append((r["column"], g, m, cause(g, r["column"], m, str(r.flagged_months).split(), bool(np.isfinite(chg.get((r["column"], "202510"), np.nan)) and np.isfinite(chg.get((r["column"], "202511"), np.nan)) and chg[(r["column"], "202510")] * chg[(r["column"], "202511")] < 0)), r.jump_ratio))
    E = pd.DataFrame(rows, columns=["column", "group", "month", "cause", "jump_ratio"])
    E.to_csv(os.path.join(d, "drift_explained.csv"), index=False)
    nc = E.column.nunique()
    full = E.groupby("column").cause.apply(lambda s: (s != "unexplained").all())
    part = E.groupby("column").cause.apply(lambda s: (s != "unexplained").any() and (s == "unexplained").any())
    print(f"[DRIFT EXPLAIN {unit}] {nc} flagged columns ({len(E)} flagged column-months): fully explained {int(full.sum())}, partly {int(part.sum())}, none {int((~full & ~part).sum())}")
    print("   flagged column-months by cause:")
    for k, v in E.cause.value_counts().items():
        print(f"     {k:<16} {v}")
    print("   flagged column-months by group x cause:")
    print(E.pivot_table(index="group", columns="cause", values="column", aggfunc="count", fill_value=0).to_string())
    U = E[E.cause == "unexplained"].sort_values("jump_ratio", ascending=False)
    print(f"\n   UNEXPLAINED: {U.column.nunique()} columns, {len(U)} column-months; months: " + ", ".join(f"{k} {v}" for k, v in U.month.value_counts().sort_index().items()))
    print("   the 30 largest unexplained jumps (column, group, month, ratio):")
    for _, r in U.drop_duplicates("column").head(30).iterrows():
        print(f"     {r['column']:<44} {r.group:<9} {r.month}  {r.jump_ratio:.1f} sd")


if __name__ == "__main__":
    main()
