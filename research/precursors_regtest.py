"""Regression check for coint_precursors.py changes.

Compares a candidate precursor extraction against a golden baseline produced
by an earlier version of the code, on the SAME event sample. Purpose: when a
new signal is added, prove the existing signals were not disturbed.

The contract being enforced: adding a signal is purely ADDITIVE. Every
pre-existing column must come back bit-identical (NaN-aware), for every event,
in the same per-event order. Anything else is a regression, even if the new
signal itself looks fine -- a changed baseline column means the new code
perturbed a shared code path (a frozen beta, a window boundary, a fit call)
and every downstream result computed from the old file is now incomparable.

Rows are matched on (ticker_a, ticker_b, detection_date), not row position,
so a reordering of the event loop is not itself flagged as a regression.

New columns are not asserted on -- they have no baseline to compare to -- but
their coverage is reported so an all-NaN or all-empty new signal is visible
immediately rather than silently surviving into the analysis stage.

Usage:
    python research/precursors_regtest.py GOLDEN.parquet CANDIDATE.parquet

Exit code 0 = no regression, 1 = regression found.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ["ticker_a", "ticker_b", "detection_date"]


def _values_equal(x, y) -> bool:
    """NaN-aware equality for both scalars and the object-dtype numpy arrays
    the trajectory columns hold. Two NaNs at the same position count as equal:
    a NaN is a real, reproducible outcome here (insufficient data for that
    window), not a missing value that happens to differ."""
    x_arr = isinstance(x, (np.ndarray, list))
    y_arr = isinstance(y, (np.ndarray, list))
    if x_arr != y_arr:
        return False
    if x_arr:
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        if x.shape != y.shape:
            return False
        return bool(np.array_equal(x, y, equal_nan=True))
    # scalars
    if pd.isna(x) and pd.isna(y):
        return True
    try:
        return bool(x == y)
    except Exception:
        return str(x) == str(y)


def _coverage(series: pd.Series) -> str:
    """One-line health summary for a column, shaped to the column's type."""
    n = len(series)
    first_valid = next((v for v in series if isinstance(v, (np.ndarray, list))), None)
    if first_valid is not None or series.map(lambda v: isinstance(v, (np.ndarray, list))).any():
        lengths = series.map(lambda v: len(v) if isinstance(v, (np.ndarray, list)) else 0)
        nonempty = int((lengths > 0).sum())
        finite_counts = series.map(
            lambda v: int(np.isfinite(np.asarray(v, dtype=float)).sum())
            if isinstance(v, (np.ndarray, list)) and len(v) else 0
        )
        all_vals = np.concatenate([
            np.asarray(v, dtype=float) for v in series
            if isinstance(v, (np.ndarray, list)) and len(v)
        ]) if nonempty else np.array([])
        finite = all_vals[np.isfinite(all_vals)] if all_vals.size else np.array([])
        if finite.size:
            q = np.percentile(finite, [5, 50, 95])
            rng = f"p5={q[0]:.4g} p50={q[1]:.4g} p95={q[2]:.4g}"
        else:
            rng = "no finite values"
        return (f"{nonempty}/{n} non-empty, "
                f"{int(finite_counts.sum())} finite points, mean len "
                f"{lengths[lengths > 0].mean():.1f}, {rng}" if nonempty else
                f"0/{n} non-empty  <-- EMPTY")
    # scalar column
    num = pd.to_numeric(series, errors="coerce")
    if num.notna().any():
        finite = num[np.isfinite(num)]
        if len(finite):
            q = np.percentile(finite, [5, 50, 95])
            return (f"{len(finite)}/{n} finite, "
                    f"p5={q[0]:.4g} p50={q[1]:.4g} p95={q[2]:.4g}")
    counts = series.value_counts(dropna=False).head(4).to_dict()
    return f"{n} rows, top values: {counts}"


def compare(golden_path: Path, candidate_path: Path) -> int:
    g = pd.read_parquet(golden_path)
    c = pd.read_parquet(candidate_path)
    for df in (g, c):
        df["detection_date"] = pd.to_datetime(df["detection_date"])

    print(f"golden    : {golden_path.name}  {g.shape}")
    print(f"candidate : {candidate_path.name}  {c.shape}")
    print()

    failures = []

    # --- row alignment ---
    g_keys = set(map(tuple, g[KEY].values))
    c_keys = set(map(tuple, c[KEY].values))
    missing = g_keys - c_keys
    added = c_keys - g_keys
    if missing:
        failures.append(f"{len(missing)} event(s) present in golden but MISSING from candidate")
        print(f"FAIL  {len(missing)} events dropped by candidate, e.g. {list(missing)[:3]}")
    if added:
        # Extra events are not automatically a regression (a sample could grow),
        # but on a fixed sample they mean the event loop changed which rows it
        # accepts -- worth surfacing loudly either way.
        print(f"WARN  {len(added)} events in candidate not in golden, e.g. {list(added)[:3]}")
    print(f"row alignment: {len(g_keys & c_keys)} shared events")
    print()

    gi = g.set_index(KEY).sort_index()
    ci = c.set_index(KEY).sort_index()
    shared = gi.index.intersection(ci.index)
    gi, ci = gi.loc[shared], ci.loc[shared]

    baseline_cols = [col for col in gi.columns]
    new_cols = [col for col in ci.columns if col not in gi.columns]

    # --- baseline columns must be identical ---
    print(f"--- baseline columns ({len(baseline_cols)}) must be bit-identical ---")
    for col in baseline_cols:
        if col not in ci.columns:
            failures.append(f"column '{col}' dropped by candidate")
            print(f"  FAIL  {col}: DROPPED")
            continue
        diffs = [
            idx for idx, (gv, cv) in enumerate(zip(gi[col].values, ci[col].values))
            if not _values_equal(gv, cv)
        ]
        if diffs:
            failures.append(f"column '{col}' differs on {len(diffs)} row(s)")
            ex = diffs[0]
            gv, cv = gi[col].values[ex], ci[col].values[ex]
            print(f"  FAIL  {col}: {len(diffs)}/{len(gi)} rows differ")
            print(f"          e.g. row {ex} key={shared[ex]}")
            # Print the first differing ELEMENT at full precision. Printing the
            # whole array rounds to display precision and can show two arrays
            # that look identical, which reads as a broken test rather than a
            # real (possibly tiny) numeric divergence.
            if isinstance(gv, (np.ndarray, list)) and isinstance(cv, (np.ndarray, list)):
                ga, ca = np.asarray(gv, dtype=float), np.asarray(cv, dtype=float)
                if ga.shape != ca.shape:
                    print(f"          shape {ga.shape} -> {ca.shape}")
                else:
                    bad = np.where(~((ga == ca) | (np.isnan(ga) & np.isnan(ca))))[0]
                    for j in bad[:3]:
                        print(f"          [{j}] golden={ga[j]!r}  candidate={ca[j]!r}  "
                              f"delta={ca[j] - ga[j]!r}")
            else:
                print(f"          golden   ={gv!r}")
                print(f"          candidate={cv!r}")
        else:
            print(f"  ok    {col}")
    print()

    # --- new columns: report only ---
    if new_cols:
        print(f"--- new columns ({len(new_cols)}) coverage report ---")
        for col in new_cols:
            cov = _coverage(ci[col])
            flag = "  <-- CHECK" if "EMPTY" in cov or "no finite" in cov else ""
            print(f"  {col}: {cov}{flag}")
        print()
    else:
        print("--- no new columns in candidate ---\n")

    if failures:
        print(f"REGRESSION: {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: all baseline columns identical, no events dropped.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(compare(Path(sys.argv[1]), Path(sys.argv[2])))
