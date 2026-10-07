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
  5. the harness reproduces a published cell: WINDOW / regression / 10h
     = -0.0104, CI [-0.0288, -0.0022] from extscore.log

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

    print("\n=== reproduces a published cell (extscore.log) ===")
    if not os.path.exists(paths.EXTFEAT):
        skip("WINDOW regression 10h", "extfeat.npz absent")
    else:
        f = np.load(paths.EXTFEAT)
        WIN = f["WIN"]
        yv = (Y[:, 20] - Y[:, 0]) * sp.sign
        score, pr, _ = harness.fit_predict(WIN, yv, sp, classify=False)
        lo, hi = harness.ci(sp, pr, yv[sp.test], classify=False)
        check("WINDOW / regression / 10h score = -0.0104", abs(score - (-0.0104)) < 5e-4,
              f"{score:+.4f}")
        check("its CI = [-0.0288, -0.0022]",
              abs(lo - (-0.0288)) < 2e-3 and abs(hi - (-0.0022)) < 2e-3,
              f"[{lo:+.4f}, {hi:+.4f}]")
        check("the cell does not clear the gates", not harness.passes(score, lo, False),
              "direction is closed; a PASS here means the gates drifted")

print()
print("=" * 60)
if fails:
    print(f"FAILED {len(fails)}: {', '.join(fails)}")
elif skips:
    print(f"ALL RUN CHECKS PASS; {len(skips)} skipped: {', '.join(skips)}")
else:
    print("ALL PASS")
sys.exit(1 if fails else 0)
