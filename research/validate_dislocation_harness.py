"""PASS/FAIL checks on the dislocation modelling harness. Hand-run, not pytest.

    python research/validate_dislocation_harness.py

Checks, in order of what they protect:

  1. the split is the one every published number came from (41,936 / 18,064)
  2. the alignment invariant -- W[:,-1] and Y[:,0] both ARE z_at_entry, so an
     off-by-one bar in either window is impossible to miss
  3. THE CI INDEXING BUG CANNOT COME BACK. ci() must refuse a full-length
     target. This is the regression test for the bug that made
     `336 raw bars / reversion / 10h` print 0.5016 with a band of
     [0.4826, 0.5007] -- an interval excluding its own point estimate.
  4. the bootstrap is day-clustered, not row-clustered
  5. THE FEATURE MATRIX, envfeat.npz. With no target and no score, these checks
     ARE the quality bar -- nothing else makes the matrix trustworthy:
       join alignment, element-wise on (ticker_a, ticker_b, entry_time), all rows
       no lookahead: max panel index touched == entry index, per row
       the sandwich bound ordering, per bar of every row
       sign-folding consistency against a fully flipped rebuild
       finiteness counts and percentiles, REPORTED not repaired
       the vratio iid normaliser, checked by simulation

The old check 5 asserted WINDOW / regression / 10h = -0.0104. It was retired on
2026-10-09 with `harness.window_features`: it ran through a function that no
longer exists, and keeping a dead function alive to satisfy a test is not a trade
this project makes.

Needs research/datasets/. If the datasets are absent, REBUILD.md regenerates
them; this script reports SKIP rather than failing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dislocation_model"))

import numpy as np
import pandas as pd

fails = []
skips = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        fails.append(name)


def skip(name, why):
    print(f"SKIP  {name}  {why}")
    skips.append(name)


import paths
import harness

HAVE = os.path.exists(paths.DISLOC) and os.path.exists(paths.META)

print("=== split ===")
if not HAVE:
    skip("split", "research/datasets/disloc.npz absent -- see dislocation_model/REBUILD.md")
else:
    W, Y, meta, sp = harness.load()
    check("60,000 dislocations", len(meta) == 60_000, f"{len(meta):,}")
    check("held-out block is 18,064", sp.n_test == 18_064, f"{sp.n_test:,}")
    check("fit block is 41,936", int(sp.fit.sum()) == 41_936, f"{int(sp.fit.sum()):,}")
    check("79 held-out days", len(sp.test_days) == 79, f"{len(sp.test_days)}")
    check("667 fit days", len(sp.fit_days) == 667, f"{len(sp.fit_days)}")
    check("cut is 2026-07-18", str(harness.CUT) == "2026-07-18", str(harness.CUT))
    check("train and val partition the fit block",
          int(sp.train.sum()) + int(sp.val.sum()) == int(sp.fit.sum()),
          f"{int(sp.train.sum()):,} + {int(sp.val.sum()):,}")
    check("held-out never in train or val",
          not (sp.test & (sp.train | sp.val)).any())

    print("\n=== alignment invariant ===")
    e1 = float(np.abs(W[:, -1] - meta.z_at_entry.to_numpy(np.float32)).max())
    e2 = float(np.abs(Y[:, 0] - meta.z_at_entry.to_numpy(np.float64)).max())
    check("max |W[:,-1] - z_entry| < 1e-4", e1 < 1e-4, f"{e1:.3e}")
    check("max |Y[:,0] - z_entry| < 1e-4", e2 < 1e-4, f"{e2:.3e}")
    check("every trigger at or beyond 3 sigma",
          bool((np.abs(meta.z_at_entry) >= 3.0 - 1e-9).all()),
          f"min |z| {np.abs(meta.z_at_entry).min():.4f}")

    print("\n=== THE CI BUG CANNOT COME BACK ===")
    pred = np.zeros(sp.n_test)
    y_full = np.zeros(len(meta))
    raised = False
    try:
        harness.ci(sp, pred, y_full, classify=False)
    except ValueError:
        raised = True
    check("ci() refuses a FULL-length target", raised,
          "a full-length y is the exact shape of the original bug")

    raised2 = False
    try:
        harness.ci(sp, np.zeros(sp.n_test + 1), np.zeros(sp.n_test), classify=False)
    except ValueError:
        raised2 = True
    check("ci() refuses a mis-sized prediction", raised2)

    ok = True
    try:
        harness.ci(sp, pred, np.zeros(sp.n_test), classify=False)
    except Exception as exc:
        ok = False
        print("    ", exc)
    check("ci() accepts correctly subset arrays", ok)

    print("\n=== bootstrap is day-clustered ===")
    dte = sp.day[sp.test]
    b0 = sp.boot[0]
    check("every resample is held-out-relative", max(b.max() for b in sp.boot) < sp.n_test,
          f"max index {max(b.max() for b in sp.boot)} < {sp.n_test}")
    check("300 resamples", len(sp.boot) == harness.N_BOOT, f"{len(sp.boot)}")
    # a day-clustered resample draws whole days: every day present appears with
    # its full row count (times its multiplicity), never a partial slice
    counts = pd.Series(dte[b0]).value_counts()
    full = pd.Series(dte).value_counts()
    partial = [d for d, c in counts.items() if c % full[d] != 0]
    check("no day appears as a partial slice", not partial,
          f"{len(partial)} partial days" if partial else "whole days only")

    print("\n=== envfeat: the vratio iid normaliser, by simulation ===")
    import envfeat
    n = envfeat.RATIO_BARS
    rg = np.random.default_rng(11)
    steps = rg.standard_normal((4000, n - 1))
    lvl = np.concatenate([np.zeros((4000, 1)), np.cumsum(steps, axis=1)], axis=1)
    sim = (np.diff(lvl, axis=1).std(1) / lvl.std(1)) * envfeat.iid_vratio_norm(n)
    # fresh seed, so this is a genuine out-of-sample check on the stored constant
    check("iid vratio MEDIAN centres on 1.0 (+/- 0.02)",
          abs(float(np.median(sim)) - 1.0) < 0.02,
          f"median {float(np.median(sim)):.4f}  mean {sim.mean():.4f}  "
          f"divisor {envfeat.iid_vratio_norm(n):.6f}  n={n}")
    ana = np.sqrt((n * n - 1.0) / (6.0 * n))
    check("the shipped divisor is NOT the analytic one",
          abs(envfeat.iid_vratio_norm(n) - ana) > 0.1,
          f"analytic {ana:.6f} normalises the ratio of expectations and is "
          f"17.7% too large for the expectation of the ratio")

    print("\n=== envfeat: the matrix ===")
    if not os.path.exists(paths.ENVFEAT):
        skip("envfeat", "envfeat.npz absent -- run dislocation_model/envfeat.py")
    else:
        f = np.load(paths.ENVFEAT, allow_pickle=False)
        X = f["X"]
        names = [str(x) for x in f["names"]]
        check("shape is 60,000 x 5", X.shape == (60_000, 5), str(X.shape))
        check("dtype is float32", X.dtype == np.float32, str(X.dtype))
        check("names are the five, in order",
              names == ["vol_48", "vratio", "vol_slope", "sandwich", "off_mark"],
              ", ".join(names))
        check("len(features) == len(meta) == 60000",
              len(X) == len(meta) == 60_000, f"{len(X)} / {len(meta)}")

        print("\n--- join alignment, element-wise on every row ---")
        ka = np.array([str(x) for x in f["ticker_a"]])
        kb = np.array([str(x) for x in f["ticker_b"]])
        kt = f["entry_time"].astype("datetime64[ns]")
        ma = meta.ticker_a.to_numpy(str)
        mb = meta.ticker_b.to_numpy(str)
        mt = pd.to_datetime(meta.entry_time).to_numpy("datetime64[ns]")
        na = int((ka != ma).sum()); nb = int((kb != mb).sum()); nt = int((kt != mt).sum())
        check("ticker_a matches meta on all 60,000 rows", na == 0, f"{na} mismatches")
        check("ticker_b matches meta on all 60,000 rows", nb == 0, f"{nb} mismatches")
        check("entry_time matches meta on all 60,000 rows", nt == 0, f"{nt} mismatches")
        check("the join key is stored in the file at all",
              {"ticker_a", "ticker_b", "entry_time"} <= set(f.files),
              "a positional join with no key is how silent misalignment happens")

        print("\n--- the entry index still resolves against TODAY'S panel ---")
        import universe_panel
        pnl = universe_panel.drop_forming_bars(universe_panel.load_panel())
        pidx = pd.to_datetime(pnl.index)
        J = meta.bar_index.to_numpy(int)
        check("panel.index[bar_index] == entry_time on all 60,000 rows",
              bool((pidx[J] == pd.to_datetime(meta.entry_time)).all()),
              f"panel is {pnl.shape[0]:,} x {pnl.shape[1]} today")
        tset = set(meta.ticker_a) | set(meta.ticker_b)
        missing = sorted(tset - set(pnl.columns))
        check("every meta ticker is still in the panel", not missing,
              f"{len(tset)} tickers" if not missing else f"missing {missing}")

        print("\n--- finiteness, REPORTED not repaired ---")
        allfin = True
        for k, nm in enumerate(names):
            c = X[:, k]
            nan = int(np.isnan(c).sum()); inf = int(np.isinf(c).sum())
            fin = int(np.isfinite(c).sum())
            print(f"      {nm:<11} NaN {nan:>6,}   inf {inf:>6,}   finite {fin:>6,}"
                  f"  ({100*fin/len(c):.2f}%)")
            allfin &= (nan == 0 and inf == 0)
        check("no column contains NaN or inf", allfin,
              "the old pipeline nan_to_num'd silently and concealed broken columns")

        print("\n--- percentiles (a broken column is visible here and almost nowhere else) ---")
        qs = [1, 5, 25, 50, 75, 95, 99]
        print(f"      {'column':<11}" + "".join(f"{'p'+str(q):>11}" for q in qs))
        for k, nm in enumerate(names):
            c = X[:, k][np.isfinite(X[:, k])]
            print(f"      {nm:<11}" + "".join(f"{v:>11.5f}" for v in np.percentile(c, qs)))
        check("every column has non-zero spread",
              all(np.ptp(X[:, k][np.isfinite(X[:, k])]) > 0 for k in range(X.shape[1])))
        check("vratio is centred above 1 (spreads are choppier than iid)",
              float(np.median(X[:, 1])) > 1.0, f"median {float(np.median(X[:, 1])):.4f}")

        print("\n--- no lookahead, and the sandwich bound, recomputed from scratch ---")
        Xb, nmb, audit = envfeat.build(verbose=False)
        over = int((audit["touch"] > audit["entry"]).sum())
        check("max panel index touched never exceeds the entry index", over == 0,
              f"{over} rows over")
        check("max index touched EQUALS the entry index on every row",
              int((audit["touch"] == audit["entry"]).sum()) == 60_000,
              f"{int((audit['touch'] == audit['entry']).sum()):,} of 60,000")
        print(f"      max entry index {audit['entry'].max():,} of a "
              f"{audit['n_panel']:,}-bar panel; "
              f"{audit['n_panel'] - 1 - audit['entry'].max():,} later bars exist and are UNUSED")
        check("sandwich upper bound >= folded close on EVERY bar of every row",
              audit["bound_viol"] == 0,
              f"{audit['bound_viol']:,} violations (worst {audit['worst_viol']:.2e}); "
              f"a violation means the beta sign or the leg assignment is wrong")
        check("the rebuild reproduces the stored matrix",
              bool(np.array_equal(Xb, X)), "bit-identical")

        print("\n--- sign-folding consistency: a fully flipped rebuild ---")
        Xf, _, auditf = envfeat.build(verbose=False, flip=True)
        same = [bool(np.array_equal(Xf[:, k], X[:, k])) for k in range(X.shape[1])]
        for k, nm in enumerate(names):
            d = np.nanmax(np.abs(Xf[:, k].astype(np.float64) - X[:, k].astype(np.float64)))
            print(f"      {nm:<11} max |flipped - original| = {d:.3e}")
        check("every feature is identical on the sign-flipped twin", all(same),
              "negating the spread flips s and swaps the hi/lo bounds; "
              "folding must cancel both")
        check("the flipped rebuild also violates no sandwich bound",
              auditf["bound_viol"] == 0, f"{auditf['bound_viol']:,}")

print()
print("=" * 60)
if fails:
    print(f"FAILED {len(fails)}: {', '.join(fails)}")
elif skips:
    print(f"ALL RUN CHECKS PASS; {len(skips)} skipped: {', '.join(skips)}")
else:
    print("ALL PASS")
sys.exit(1 if fails else 0)
