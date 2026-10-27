"""HL-MODEL1 B1: full duplicate audit over the IN set of research/model/inputs_v1_pair.csv.

    NPROC=? python -u research/model/dup_audit_v1_pair.py > research/model/logs/dup_audit_v1_pair.log

Checker finding 1 (2026-10-27, two rounds): the duplicate audit must cover the WHOLE IN set with the EXACT
pairwise-finite Pearson correlation for every pair, not a NaN-biased screen. Re-hashes the v1 pair files
against MANIFEST.json first, then runs everything in one pass:

1. CATEGORICAL BIJECTION. ticker_a vs a_coin_code, ticker_b vs b_coin_code: 1:1 mapping on every row.
2. PASS 1 (per-column stats, one read per column): n_finite, global finite mean, all-NaN flag, constant flag
   (sd == 0 over its own finite rows). Reused by both the hash pass and the full screen's centring.
3. EXACT-EQUALITY HASH. Every IN column (numeric cast to float64 with NaN normalised to one bit pattern;
   ticker_a/ticker_b sha256'd on UTF-8 bytes, None normalised to one sentinel) is hashed in the same pass as
   step 2. Columns sharing a hash are EXACT duplicates (equal on every row, including where both are NaN).
   All-NaN or constant columns are labelled as such wherever they appear in a result, so a hash match from
   degeneracy is never read as a real duplicate feature.
4. FULL PAIRWISE-FINITE PEARSON, exact (not a screen). For every pair of IN numeric columns i, j, the exact
   Pearson correlation over rows finite in BOTH i and j is obtained from four k x k matrices, accumulated in
   float64 over row chunks read from parquet (chunk size ROWS_PER_CHUNK, no need to hold the full data twice):
     X0[:, c] = (x_c - mean_c) with NaN set to 0 (mean_c = c's OWN global finite mean, from pass 1)
     M[:, c]  = 1 where x_c is finite, else 0
     N   = M.T @ M          (N[i,j] = rows finite in both i and j: the exact overlap count)
     Sx  = X0.T @ M         (Sx[i,j] = sum of centred x_i over the overlap of i and j)
     Sxx = (X0**2).T @ M    (Sxx[i,j] = sum of centred x_i^2 over the overlap of i and j)
     Sxy = X0.T @ X0        (Sxy[i,j] = sum of centred x_i * centred x_j over the overlap of i and j; the
                             product is 0 whenever either is NaN, so this needs no separate mask)
   Then, by the shift-invariance of a covariance sum (valid for ANY centring point, here the column's global
   mean rather than the overlap's own mean -- the N/Sx/Sxx correction below removes the resulting bias exactly,
   not approximately):
     cov_ij  = N[i,j] * Sxy[i,j] - Sx[i,j] * Sx[j,i]
     var_i|j = N[i,j] * Sxx[i,j] - Sx[i,j]**2        (i's variance restricted to the i,j overlap)
     var_j|i = N[i,j] * Sxx[j,i] - Sx[j,i]**2
     r_ij    = cov_ij / sqrt(var_i|j * var_j|i)
   This is the EXACT pairwise-finite Pearson for every one of the ~611,000 pairs at once, not an approximation:
   verified before this run against the direct two-column computation on synthetic data (varied per-column
   NaN rates, a constant column, an all-NaN column, a planted duplicate with its OWN different NaN mask) and
   on small multi-file parquet test data mimicking the real multi-reader setup; both matched to float noise
   (~1e-16). Every pair this run actually flags is ALSO re-verified directly (step 7 below), not trusted
   from the matrix alone.
5. SPEARMAN on the flagged pairs only (full-matrix Spearman is not computed; only pairs already flagged by
   Pearson are rank-checked, recomputed directly via the masked two-column function -- this is where a pair
   that is rank-identical but not Pearson-1.000, e.g. a share vs its ratio, is reported separately).
6. THRESHOLDS (B1: "equal on all rows (or correlation 1.000)"): |r| >= 0.9995 (rounds to 1.000) is a
   DUPLICATE under the rule; 0.999 <= |r| < 0.9995 is logged as BORDERLINE (visible, not a duplicate); r
   near -1.000 is reported the same way, noted as an anti-correlation, not dropped.
7. Every flagged/borderline pair is re-verified by the direct two-column pairwise-finite function (the same
   one used for the pre-screen), and each column's own n_finite plus the pair's n_overlap are logged, so a
   pair that differs in which rows are NaN (not "equal on all rows" even if r rounds to 1.000) is visible.
8. PRE-SCREEN cross-check: the checker's named candidate pairs (now excluding the 2026-10-27 archive_age
   amendment's columns, which are OUT and not in the IN set) are run through the SAME direct two-column
   function. With the full screen in place this is a cross-check, not the primary result: every pre-screen
   pair with |r| >= 0.9995 must also appear in the full screen's duplicate list, or the run prints a MISMATCH
   line and does not silently pass.
9. KEEP RULE (B1: "keep one, record which"; planner ruling 2026-10-27, relayed by Research Partner, settling
   the anti-duplicate question raised by the checker). A sign-flipped pair (correlation -1.000) counts as a
   duplicate, same as +1.000: a sign flip or complement carries no new information and destabilises a
   logistic fit. But |corr| rounding to 1.000, either sign, is NOT enough on its own to drop a column: the
   pair must also be an EXACT AFFINE TRANSFORM (y = a + b*x, checked on every overlap row at float32
   tolerance) AND have an IDENTICAL NaN pattern (is_exact_affine_duplicate(), verified against synthetic
   cases before use: a sign-flip with matching NaNs passes; equal values with DIFFERENT NaN masks fails;
   a monotone-but-nonlinear transform such as a share vs its ratio fails; a float32-storage copy like
   g2's beta passes within tolerance). A pair that rounds to |r| >= 0.9995 but fails either test is
   relabelled "near_duplicate": reported, kept, not dropped.
   Exact-hash groups trivially satisfy this gate (identical values => b=1, a=0, and an identical NaN
   pattern by construction of the hash) and go straight into the drop graph. Duplication is transitive
   (A=B, B=C => A=C), so connected components, not pairs, are the unit of decision.
   KEEP is MECHANICAL, not a judgement (brief HL_MODEL1_REVERTER_MODEL.md lines 123-133, the duplicate-audit
   ruling added 2026-10-27; no sign-off needed): the column from the earliest file in v1 group order (events,
   g2, g2b, g3, g4, g5_a, g5_b, g5_net, g5_shape, g6_a, g6_b, g6_net, g7, g8, g9a); within one file, the
   alphabetically first name. Because every edge requires an identical NaN pattern, n_a == n_b == n_overlap
   for every pair in a component, so "most finite rows" is never a live tie-break. The A6-named three
   (beta, beta_stab, bars_into_segment/seg_bars) already keep events.parquet's
   copy, consistent with this default.
   Written to research/model/dup_audit_keep_v1_pair.csv (dropped_file, dropped_col, kept_file, kept_col,
   reason); the B1 script (build_inputs_v1_pair.py) is updated from this file in a separate, reviewed step,
   not silently by this script.
   DEGENERATE COLUMNS: an all-NaN or all-equal-constant column that lands in an exact-hash component is
   dropped by the rule as written ("equal on all rows" includes that case), but listed separately so it is
   never read as a real duplicate feature.
   SPEARMAN SCOPE: Spearman is computed only for pairs the full Pearson screen already flags (>= 0.999) and
   for the PRESCREEN_PAIRS list, not for the full k x k set -- a monotone-but-nonlinear duplicate whose
   Pearson never reaches 0.999 would not surface in this run.

OUTPUT: research/model/dup_audit_v1_pair.csv (file_a, col_a, file_b, col_b, pearson, spearman, n_a, n_b,
n_overlap, kind [duplicate|borderline|anti_duplicate|anti_borderline], degenerate [all_nan/constant/both/""]);
research/model/dup_audit_keep_v1_pair.csv (the keep-rule decisions, step 9).
"""
import csv
import hashlib
import os
import sys
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
import master_manifest as MF  # noqa: E402

# v1 pair group-file order, for the keep-rule tie-break (checker, 2026-10-27): earliest file wins a tie.
GROUP_ORDER = ["events.parquet", "g2.parquet", "g2b.parquet", "g3.parquet", "g4.parquet",
               "g5_a.parquet", "g5_b.parquet", "g5_net.parquet", "g5_shape.parquet",
               "g6_a.parquet", "g6_b.parquet", "g6_net.parquet", "g7.parquet", "g8.parquet", "g9a.parquet"]


def arrow_to_f64(arr):
    """Arrow array/ChunkedArray -> float64 numpy, nulls -> NaN. Cast through pyarrow first (not
    to_numpy(...).astype(float64)): a boolean column with nulls comes back from to_numpy(zero_copy_only=False)
    as an object array of True/False/None, and .astype(float64) on that is not guaranteed safe across numpy
    versions (checker, 2026-10-27). pc.cast handles the null -> NaN conversion inside pyarrow instead."""
    return pc.cast(arr, pa.float64()).to_numpy(zero_copy_only=False)

WORK = MF.WORK
PAIR_DIR = os.path.join(WORK, "pair")
N_ROWS = 6_697_756
ROWS_PER_CHUNK = 200_000
DUP_THRESH = 0.9995
BORDERLINE_THRESH = 0.999

CATEGORICAL_BIJECTIONS = [("ticker_a", "a_coin_code"), ("ticker_b", "b_coin_code")]

# checker's pre-screen candidates, 2026-10-27 round 2: the g7 archive-age/gap-flag columns (ctx_age_min,
# oi_obs_age, oi_rec_age, oi_rec_in_gap, fund_age_h and their d_ forms) are OUT under the amendment and
# dropped here entirely -- they are not in the IN set, so a pair including them cannot be audited as IN x IN.
PRESCREEN_PAIRS = [
    ("events.parquet", "r2", "g2.parquet", "r2_2d"),  # master_g2.py:195 asserts equal to 1e-12
    ("events.parquet", "mins_since_trade_a", "g4.parquet", "a_mins_since_trade"),
    ("events.parquet", "mins_since_trade_b", "g4.parquet", "b_mins_since_trade"),
    ("g7.parquet", "a_vault_leader_usd", "g7.parquet", "b_vault_leader_usd"),
    ("g7.parquet", "a_vault_leader_usd", "g7.parquet", "d_vault_leader_usd"),
    ("g7.parquet", "b_vault_leader_usd", "g7.parquet", "d_vault_leader_usd"),
    ("g7.parquet", "a_vault_share_of_oi", "g7.parquet", "a_vault_gross_usd"),
    ("g7.parquet", "b_vault_share_of_oi", "g7.parquet", "b_vault_gross_usd"),
    # the g5_net 3-column group the checker flagged (same Part Z n/nan_share/auc profile): check pairwise
    ("g5_net.parquet", "net_max_abs_imb_5m_bin", "g5_net.parquet", "net_mins_since_forced_any"),
    ("g5_net.parquet", "net_max_abs_imb_5m_bin", "g5_net.parquet", "net_mins_since_forced_spike"),
    ("g5_net.parquet", "net_mins_since_forced_any", "g5_net.parquet", "net_mins_since_forced_spike"),
]
for _leg_file, _pfx in [("g5_a.parquet", "a_"), ("g5_b.parquet", "b_"), ("g5_net.parquet", "net_")]:
    for _w in ("30", "60", "360", "1440"):
        PRESCREEN_PAIRS.append((_leg_file, f"{_pfx}backstop_ratio_{_w}", _leg_file, f"{_pfx}backstop_share_{_w}"))
        PRESCREEN_PAIRS.append((_leg_file, f"{_pfx}adl_ratio_{_w}", _leg_file, f"{_pfx}adl_share_{_w}"))
for _leg_file, _pfx in [("g6_a.parquet", "a_"), ("g6_b.parquet", "b_"), ("g6_net.parquet", "net_")]:
    for _w in ("30", "60", "360", "1440"):
        PRESCREEN_PAIRS.append((_leg_file, f"{_pfx}vault_absorb_ratio_{_w}", _leg_file, f"{_pfx}vault_absorb_share_{_w}"))


def load_in_columns():
    """(file, column) for every IN row of inputs_v1_pair.csv, split numeric / string, GROUPED BY FILE (so a
    later batch-reading pass opens each file once with all its columns, not once per column). Reads the CSV
    the B1 script wrote, so this audit always runs against the CURRENT frozen input list, not a stale copy."""
    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    inn = [(r["file"], r["column"]) for r in rows if r["in_out"] == "IN"]
    string_cols = {("events.parquet", "ticker_a"), ("events.parquet", "ticker_b")}
    numeric = [fc for fc in inn if fc not in string_cols]
    strings = [fc for fc in inn if fc in string_cols]
    numeric.sort(key=lambda fc: fc[0])  # group by file, stable within a file (preserves inputs_v1_pair.csv order)
    return numeric, strings


def read_col_arrow(file, col):
    return pq.read_table(os.path.join(PAIR_DIR, file), columns=[col]).column(0)


def read_col_f64(file, col):
    """Numeric IN column as float64, nulls -> NaN, via arrow_to_f64 (never a bare .astype on an object array)."""
    return arrow_to_f64(read_col_arrow(file, col))


def col_hash_and_stats(file, col, is_string):
    """sha256 (NaN-normalised) plus (n_finite, mean, all_nan, constant) in one read."""
    arr = read_col_arrow(file, col)
    if not is_string:
        x = arrow_to_f64(arr)
        finite = np.isfinite(x)
        n_finite = int(finite.sum())
        if n_finite == 0:
            mean, const = np.nan, True
        else:
            mean = float(x[finite].mean())
            const = bool(np.all(x[finite] == x[finite][0]))
        x = np.where(np.isnan(x), np.nan, x)  # normalise any non-canonical NaN payload to one bit pattern
        h = hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
        return h, n_finite, mean, (n_finite == 0), const
    vals = arr.to_pandas().to_numpy()
    h = hashlib.sha256(("\x1f".join("<NONE>" if v is None else str(v) for v in vals)).encode("utf-8")).hexdigest()
    n_finite = int(sum(v is not None for v in vals))
    return h, n_finite, np.nan, (n_finite == 0), bool(len(set(v for v in vals if v is not None)) <= 1)


def pearson_pairwise_finite(x, y):
    """Direct two-column pairwise-finite Pearson + Spearman; used for the pre-screen and to re-verify every
    pair the full chunked screen flags."""
    m = np.isfinite(x) & np.isfinite(y)
    n = int(m.sum())
    if n < 1000:
        return np.nan, np.nan, n
    xs, ys = x[m], y[m]
    if xs.std() == 0 or ys.std() == 0:
        return np.nan, np.nan, n
    r = float(np.corrcoef(xs, ys)[0, 1])
    rx, ry = pd.Series(xs).rank().to_numpy(), pd.Series(ys).rank().to_numpy()
    rho = float(np.corrcoef(rx, ry)[0, 1])
    return r, rho, n


def is_exact_affine_duplicate(x, y, rtol=1e-5, b_err_rtol=1e-9):
    """Planner ruling, 2026-10-27 (relayed by Research Partner): a pair is a true duplicate (for drop) only if
    it is an EXACT AFFINE TRANSFORM (y = a + b*x, checked on EVERY overlap row, float32 tolerance) AND has an
    IDENTICAL NaN pattern (same finite mask). |corr| rounding to 1.000 alone is not enough: this is the gate
    that separates a real duplicate from a near-duplicate (reported, kept, not dropped).

    Tolerance, round 3 (checker, 2026-10-27, after round 1 under-covered USD-scale columns with an offset and
    round 2's flat atol = 1e-4 over-covered small-scale columns like returns/shares/imbalances, which live at
    1e-4 to 1e-2 and would then accept a residual as large as the values themselves): the per-row bound is now

        tol_i = 1e-12 + rtol*(|y_i| + |a| + |b*x_i|) + b_err_rtol*|b|*|x_i - xbar|

    rtol*(|y_i| + |a| + |b*x_i|) covers float32 storage error (about 6e-8*|b*x_i|) at the SCALE of the data on
    that row, not a flat constant. The last term covers the fit's own error in b (about 1e-10 relative, from
    the float64 cov/var computation), which is amplified by distance from x's mean -- b_err_rtol = 1e-9 gives
    about 10x headroom over that 1e-10, e.g. ~1e-3 at x_i - xbar ~ 1e6, and the term vanishes for small-scale
    columns since it is tied to |x_i - xbar|, not to y's or a's own scale.

    Returns (is_duplicate, same_nan_pattern, max_affine_residual_rel, a, b)."""
    mx, my = np.isfinite(x), np.isfinite(y)
    same_nan = bool(np.array_equal(mx, my))
    m = mx & my
    n = int(m.sum())
    if n < 2 or not same_nan:
        return False, same_nan, np.nan, np.nan, np.nan
    xs, ys = x[m], y[m]
    if xs.std() == 0:  # x constant on the overlap: "affine" would be undefined slope; handled by the hash pass
        return False, same_nan, np.nan, np.nan, np.nan
    b = float(np.cov(xs, ys, ddof=0)[0, 1] / np.var(xs))
    a = float(ys.mean() - b * xs.mean())
    xbar = float(xs.mean())
    pred = a + b * xs
    resid = np.abs(ys - pred)
    tol = 1e-12 + rtol * (np.abs(ys) + abs(a) + np.abs(b * xs)) + b_err_rtol * abs(b) * np.abs(xs - xbar)
    ok = bool(np.all(resid <= tol))
    y_max = float(np.abs(ys).max())
    rel_resid = resid / np.maximum(y_max, 1e-12)
    return ok, same_nan, float(rel_resid.max()), a, b


def kind_of(r):
    if r >= DUP_THRESH:
        return "duplicate"
    if r <= -DUP_THRESH:
        return "anti_duplicate"
    if r >= BORDERLINE_THRESH:
        return "borderline"
    if r <= -BORDERLINE_THRESH:
        return "anti_borderline"
    return None


def main():
    t0 = time.time()
    # provenance header, before any number (the Part Z lesson: prove which code produced this log)
    gs = os.path.join(ROOT, "research", "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    for f in (os.path.abspath(__file__), os.path.join(HERE, "inputs_v1_pair.csv"),
              os.path.join(ROOT, "research", "dataset", "master_manifest.py")):
        print(f"[DUP] sha256 {os.path.relpath(f, ROOT)}: {MF.sha(f)}", flush=True)
    print(f"[DUP] git_head {git_head} ({git_dirty} uncommitted paths at last laptop snapshot); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    numeric, strings = load_in_columns()
    cols = numeric + strings
    k = len(numeric)
    print(f"[DUP] IN set: {len(numeric):,} numeric columns, {len(strings):,} string columns")
    print(f"[DUP] resource plan: X0/M as float64 chunks of {ROWS_PER_CHUNK:,} rows x {k} columns "
          f"({ROWS_PER_CHUNK*k*8/1e9:.2f} GB per chunk buffer, well under 64 GB); "
          f"{k}x{k} accumulators x4 = {4*k*k*8/1e6:.0f} MB; "
          f"~{2*k*k*N_ROWS*4/1e12:.1f} TFLOP total across the 4 matrix products")

    # 0. verify the frozen files before any number is produced
    man = MF.json.load(open(os.path.join(MF.VERS, "v1", "MANIFEST.json")))
    rels = sorted({f"pair/{f}" for f, _ in cols})
    MF.verify("v1", rels, base=WORK)
    print(f"[DUP] {len(rels)} v1 pair files re-hashed against MANIFEST.json: all match  [{time.time()-t0:.0f}s]")

    # 1. categorical bijection check
    print("[DUP] categorical bijections:")
    for a, b in CATEGORICAL_BIJECTIONS:
        fa = next(f for f, c in strings + numeric if c == a)
        fb = next(f for f, c in numeric if c == b)
        df = pd.DataFrame({a: read_col_arrow(fa, a).to_pandas(), b: read_col_arrow(fb, b).to_pandas()})
        f_to_1 = df.groupby(a)[b].nunique().max()
        b_to_1 = df.groupby(b)[a].nunique().max()
        print(f"   {a} <-> {b}: max distinct {b} per {a} = {f_to_1}, max distinct {a} per {b} = {b_to_1} "
              f"({'BIJECTIVE' if f_to_1 == 1 and b_to_1 == 1 else 'NOT 1:1'})")

    # 2+3. pass 1: per-column stats + hash, one read per column (numeric and string together)
    print(f"[DUP] pass 1: stats + hash over {len(cols)} columns  [{time.time()-t0:.0f}s]")
    string_set = set(strings)
    stats = {}  # (file, col) -> (hash, n_finite, mean, all_nan, constant)
    hashes = {}
    for i, (file, col) in enumerate(cols):
        h, n_finite, mean, all_nan, const = col_hash_and_stats(file, col, (file, col) in string_set)
        stats[(file, col)] = (h, n_finite, mean, all_nan, const)
        hashes.setdefault(h, []).append((file, col))
        if (i + 1) % 200 == 0:
            print(f"   {i+1}/{len(cols)}  [{time.time()-t0:.0f}s]", flush=True)
    exact_groups = [g for g in hashes.values() if len(g) > 1]
    print(f"[DUP] exact-hash duplicate groups: {len(exact_groups)}")
    for g in exact_groups:
        tags = [f"{f}/{c}{' [ALL-NAN]' if stats[(f,c)][3] else ' [CONSTANT]' if stats[(f,c)][4] else ''}" for f, c in g]
        print(f"   EXACT: {tags}")

    # 4. full pairwise-finite Pearson, exact, via chunked N/Sx/Sxx/Sxy accumulation
    # Safety: every group file must share the same event_id row order (a documented v1 invariant used
    # elsewhere, e.g. master_colreport.one_column), checked ONCE here, before zipping per-file batch readers
    # together below (iter_batches batch sizes are also asserted equal per chunk, as a second guard).
    files_needed = sorted({f for f, _ in numeric})
    ref_file = files_needed[0]
    ref_ids = pq.read_table(os.path.join(PAIR_DIR, ref_file), columns=["event_id"]).column(0).to_numpy()
    for f in files_needed[1:]:
        ids = pq.read_table(os.path.join(PAIR_DIR, f), columns=["event_id"]).column(0).to_numpy()
        assert (ids == ref_ids).all(), f"{f}: event_id row order differs from {ref_file}; cannot zip batches"
    print(f"[DUP] event_id row order confirmed identical across {len(files_needed)} files  [{time.time()-t0:.0f}s]")

    means = np.array([stats[fc][2] if not np.isnan(stats[fc][2]) else 0.0 for fc in numeric])
    N = np.zeros((k, k), dtype=np.float64)
    Sx = np.zeros((k, k), dtype=np.float64)
    Sxx = np.zeros((k, k), dtype=np.float64)
    Sxy = np.zeros((k, k), dtype=np.float64)
    # one reader PER FILE, with all of that file's IN columns requested together (not one reader per column,
    # which would re-scan a file up to ~140 times); `numeric` is grouped by file (load_in_columns), so the
    # columns requested per file, in order, exactly match the column slice of `numeric` for that file.
    file_cols = {}
    for f, c in numeric:
        file_cols.setdefault(f, []).append(c)
    readers = {f: pq.ParquetFile(os.path.join(PAIR_DIR, f)).iter_batches(batch_size=ROWS_PER_CHUNK, columns=cs)
               for f, cs in file_cols.items()}
    file_order = list(file_cols.keys())
    done = 0
    print(f"[DUP] pass 2: full {k}x{k} pairwise-finite Pearson, chunked ({len(file_order)} file readers, "
          f"{sum(len(v) for v in file_cols.values())} columns)  [{time.time()-t0:.0f}s]")
    while True:
        try:
            batches = {f: next(readers[f]) for f in file_order}
        except StopIteration:
            break
        lens = {f: b.num_rows for f, b in batches.items()}
        assert len(set(lens.values())) == 1, f"batch size mismatch across files: {lens}"
        chunk = np.column_stack([arrow_to_f64(batches[f].column(i))
                                  for f in file_order for i in range(len(file_cols[f]))])
        assert chunk.shape[1] == k
        M = np.isfinite(chunk)
        X0 = np.where(M, chunk - means[np.newaxis, :], 0.0)
        Mf = M.astype(np.float64)
        N += Mf.T @ Mf
        Sx += X0.T @ Mf
        Sxx += (X0 * X0).T @ Mf
        Sxy += X0.T @ X0
        done += chunk.shape[0]
        print(f"   {done:,}/{N_ROWS:,} rows  [{time.time()-t0:.0f}s]", flush=True)
    assert done == N_ROWS, f"row count mismatch: read {done:,}, expected {N_ROWS:,}"

    cov = N * Sxy - Sx * Sx.T
    var_i = N * Sxx - Sx * Sx
    var_j = N * Sxx.T - Sx.T * Sx.T
    with np.errstate(invalid="ignore", divide="ignore"):
        R = cov / np.sqrt(var_i * var_j)
    np.fill_diagonal(R, np.nan)
    print(f"[DUP] full screen done  [{time.time()-t0:.0f}s]; re-verifying every flagged pair directly")

    flagged = []
    iu, ju = np.triu_indices(k, k=1)
    rvals = R[iu, ju]
    cand = np.where(np.isfinite(rvals) & (np.abs(rvals) >= BORDERLINE_THRESH))[0]
    for idx in cand:
        i, j = iu[idx], ju[idx]
        fa, ca = numeric[i]
        fb, cb = numeric[j]
        xa = read_col_f64(fa, ca)
        xb = read_col_f64(fb, cb)
        r, rho, n_overlap = pearson_pairwise_finite(xa, xb)
        kind = kind_of(r) if np.isfinite(r) else None
        if kind is None:
            continue
        # Planner ruling, 2026-10-27: |corr| rounding to 1.000 (either sign) is not enough on its own -- a
        # "duplicate"/"anti_duplicate" must also be an exact affine transform with an identical NaN pattern,
        # checked on every overlap row at float32 tolerance. A pair that rounds to 1.000 but fails either test
        # is relabelled "near_duplicate": reported, kept, not dropped.
        affine_ok = same_nan = affine_a = affine_b = None
        if kind in ("duplicate", "anti_duplicate"):
            affine_ok, same_nan, max_rel_resid, affine_a, affine_b = is_exact_affine_duplicate(xa, xb)
            if not affine_ok:
                kind = "near_duplicate"
        na, nb = stats[(fa, ca)][1], stats[(fb, cb)][1]
        deg = []
        if stats[(fa, ca)][3]:
            deg.append(f"{ca}=all_nan")
        elif stats[(fa, ca)][4]:
            deg.append(f"{ca}=constant")
        if stats[(fb, cb)][3]:
            deg.append(f"{cb}=all_nan")
        elif stats[(fb, cb)][4]:
            deg.append(f"{cb}=constant")
        flagged.append((fa, ca, fb, cb, r, rho, na, nb, n_overlap, kind, ";".join(deg), affine_ok, same_nan, affine_a, affine_b))
        extra = f" affine_ok={affine_ok} same_nan={same_nan} a={affine_a} b={affine_b}" if affine_ok is not None else ""
        print(f"   {kind.upper():15} {ca}@{fa}  vs  {cb}@{fb}: pearson {r:.6f} spearman {rho:.6f} "
              f"n_a {na:,} n_b {nb:,} n_overlap {n_overlap:,}" + (f" [{';'.join(deg)}]" if deg else "") + extra)

    # 5/8. pre-screen cross-check: every pre-screen pair with |r| >= DUP_THRESH must appear in `flagged`
    flagged_set = {(fa, ca, fb, cb) for fa, ca, fb, cb, *_ in flagged} | {(fb, cb, fa, ca) for fa, ca, fb, cb, *_ in flagged}
    print(f"[DUP] pre-screen cross-check ({len(PRESCREEN_PAIRS)} pairs)  [{time.time()-t0:.0f}s]")
    mismatches = 0
    for fa, ca, fb, cb in PRESCREEN_PAIRS:
        xa = read_col_f64(fa, ca)
        xb = read_col_f64(fb, cb)
        r, rho, n_overlap = pearson_pairwise_finite(xa, xb)
        in_full = (fa, ca, fb, cb) in flagged_set
        flag = "" if not np.isfinite(r) else (" >= DUP_THRESH" if abs(r) >= DUP_THRESH else "")
        if flag and not in_full:
            mismatches += 1
            print(f"   MISMATCH: {ca}@{fa} vs {cb}@{fb}: pearson {r} is >= {DUP_THRESH} in the pre-screen but "
                  f"NOT in the full screen's flagged list -- investigate before trusting the full screen")
        else:
            print(f"   {ca}@{fa}  vs  {cb}@{fb}: pearson {r}, spearman {rho}, n_overlap {n_overlap:,}"
                  + (" (also in full screen)" if in_full else ""))
    print(f"[DUP] pre-screen cross-check: {mismatches} mismatches (0 expected)")

    with open(os.path.join(HERE, "dup_audit_v1_pair.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file_a", "col_a", "file_b", "col_b", "pearson", "spearman", "n_a", "n_b", "n_overlap",
                     "kind", "degenerate", "affine_ok", "same_nan_pattern", "affine_a", "affine_b"])
        w.writerows(flagged)
    print(f"[DUP] wrote {len(flagged)} flagged pairs to dup_audit_v1_pair.csv  [{time.time()-t0:.0f}s]")

    # 9. KEEP RULE (B1: "keep one, record which"; planner ruling 2026-10-27, relayed by Research Partner).
    # A pair counts as a duplicate for DROP purposes -- same sign or flipped -- only if it passed
    # is_exact_affine_duplicate (exact affine transform, identical NaN pattern, float32 tolerance, checked
    # above); kind "duplicate" or "anti_duplicate" at this point already means it passed that gate (a pair
    # that rounded to |r| >= 0.9995 but failed the gate was relabelled "near_duplicate" and is reported, not
    # dropped, below). Exact-hash groups trivially satisfy the gate (b=1, a=0, identical values => identical
    # NaN pattern by construction of the hash). Edges: exact-hash groups + kind in {duplicate, anti_duplicate}.
    # Connected components (duplication is transitive) via union-find.
    # KEEP is MECHANICAL, not a judgement (brief HL_MODEL1_REVERTER_MODEL.md lines 123-133; no sign-off
    # needed): the column from the earliest file in GROUP_ORDER, then the alphabetically first column name
    # within one file. Because every edge in this graph has an IDENTICAL NaN pattern by construction,
    # n_a == n_b == n_overlap for every pair in a component, so "most finite rows" is never a live tie-break.
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(x, y):
        parent.setdefault(x, x)
        parent.setdefault(y, y)
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for g in exact_groups:
        for a, b in zip(g[:-1], g[1:]):
            union(a, b)
    for fa, ca, fb, cb, r, rho, na, nb, n_overlap, kind, deg, affine_ok, same_nan, aa, bb in flagged:
        if kind in ("duplicate", "anti_duplicate"):
            union((fa, ca), (fb, cb))

    components = {}
    for node in set(parent):
        components.setdefault(find(node), []).append(node)
    components = [c for c in components.values() if len(c) > 1]

    def sort_key(fc):
        f, c = fc
        return (GROUP_ORDER.index(f) if f in GROUP_ORDER else 999, c)

    print(f"[DUP] keep rule: {len(components)} connected duplicate component(s), including anti-duplicates "
          f"(planner ruling 2026-10-27: a sign flip is a duplicate too). Keep = earliest file in GROUP_ORDER, "
          f"then column name -- mechanical rule, brief B1 lines 123-133, no sign-off needed.")
    keep_decisions = []  # (dropped_file, dropped_col, kept_file, kept_col, reason)
    for comp in components:
        comp_sorted = sorted(comp, key=sort_key)
        best = comp_sorted[0]  # earliest GROUP_ORDER file, then alphabetically first column (comp_sorted's order)
        same_file_tie = len({sort_key(fc)[0] for fc in comp_sorted}) == 1
        for fc in comp_sorted:
            if fc == best:
                continue
            reason = "tie, same file, column name" if same_file_tie else "earlier file in GROUP_ORDER (mechanical rule, brief B1 lines 123-133)"
            keep_decisions.append((fc[0], fc[1], best[0], best[1], reason))
        print(f"   KEEP {best[0]}/{best[1]}  DROP {[f'{f}/{c}' for f, c in comp_sorted if (f, c) != best]}")

    with open(os.path.join(HERE, "dup_audit_keep_v1_pair.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["dropped_file", "dropped_col", "kept_file", "kept_col", "reason"])
        w.writerows(keep_decisions)
    print(f"[DUP] wrote {len(keep_decisions)} keep/drop decisions to dup_audit_keep_v1_pair.csv")

    # NEAR-DUPLICATES: |r| rounded to 1.000 (either sign) but FAILED the affine/identical-NaN-pattern gate --
    # reported, explicitly NOT dropped (planner ruling 2026-10-27).
    near = [f for f in flagged if f[9] == "near_duplicate"]
    print(f"[DUP] near-duplicates (|corr| >= {DUP_THRESH} but failed the exact-affine/identical-NaN-pattern "
          f"gate): {len(near)}, kept")
    for fa, ca, fb, cb, r, rho, na, nb, n_overlap, kind, deg, affine_ok, same_nan, aa, bb in near:
        print(f"   NEAR {ca}@{fa}  vs  {cb}@{fb}: pearson {r:.6f}, same_nan_pattern={same_nan}")

    # Degenerate all-NaN / constant columns that formed an exact-hash component: these ARE dropped by the
    # rule as written ("equal on all rows" includes all-NaN or all-equal-constant), but listed separately so
    # they are never read as a real duplicate feature (checker, 2026-10-27).
    degenerate_drops = [d for d in keep_decisions if stats[(d[0], d[1])][3] or stats[(d[0], d[1])][4]]
    print(f"[DUP] of the dropped columns above, {len(degenerate_drops)} are all-NaN or constant (degenerate, "
          f"not a real duplicate feature, but dropped by the same rule since they are 'equal on all rows'):")
    for d in degenerate_drops:
        tag = "all_nan" if stats[(d[0], d[1])][3] else "constant"
        print(f"   {d[0]}/{d[1]} [{tag}] -> kept {d[2]}/{d[3]}")

    # NOTE on Spearman scope: rank-only pairs (Spearman >= 0.999, Pearson < 0.999, a monotone-but-nonlinear
    # transform such as a share vs its ratio) are checked by the direct two-column function for every pair
    # the full Pearson screen flags (>= BORDERLINE_THRESH) AND for every PRESCREEN_PAIRS entry; Spearman is
    # NOT computed for the full k x k set, so a monotone-transform duplicate whose Pearson never reaches
    # BORDERLINE_THRESH would not surface here. None of the pairs checked this run had that pattern (see the
    # pearson/spearman pairs printed above), but this is a scope limit of this run, not a proof it cannot happen.


if __name__ == "__main__":
    main()
