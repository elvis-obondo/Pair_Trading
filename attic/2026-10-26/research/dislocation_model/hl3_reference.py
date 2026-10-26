"""HL-FLOW1 Part 1: target, chance bar and the position reference. No flow feature.

    python -u research/dislocation_model/hl3_reference.py --stage paths
    python -u research/dislocation_model/hl3_reference.py --stage reference

PATHS: reachmu.stage_paths on the Hyperliquid 1-minute bars. Population = the
dislocations whose 1-minute window is finite for both legs (matched count and the
share lost to archive holes are printed). reach = depth >= |z_at_entry| on
1-minute closes, mu frozen at entry, no stop, 10h; asserted equal to the 10h MFE
target. chance = the same path's 1-minute steps with random signs, 50 seeds.
The 30-minute-grid reach is the secondary target (below).

REFERENCE ("position", the bar every flow group must beat): logistic regression,
unpenalised, standardised on train, on log(vol_48), log(vol_48_1m), log(sigma) and
|z_at_entry| (REACH-MU's transforms). vol_48 = the mean absolute 30-minute change of
the entry-frozen spread over the last 24h; vol_48_1m = the same quantity from the
1-minute path (vol1m.trailing_features, its reproduction checks asserted here).
Fitted on train; held-out touched once, at scoring.

Reported on each held-out half: flag share at 50/80/90% catch, top-20% hit rate,
beyond-chance gap (reach rate - mean chance probability over the flagged set),
all with day-clustered 95% intervals. Also the reach rate and mean chance
probability overall and by |z_at_entry| band (< 2, 2-3, >= 3).

GATE (prominent if it trips): the beyond-chance gap of the episodes flagged at 80% catch
wholly above zero in BOTH halves would contradict the OKX result. The top-20% gap is
printed beside it as a diagnostic.
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import paths
from envelope import HO_BOUNDARY
from hl3_common import CATCH, Pop, half_measure
from reachmu import auc, flag_share, logloss_rows, stage_paths

REF_OUT = os.path.join(paths.DATASETS, "hl3_reference.npz")


def vol_features(P):
    """vol_48 (from the 30-minute windows) and vol_48_1m (the 1-minute path), on P.rows."""
    import vol1m
    W = P.W[P.rows].astype(np.float64)
    vol48 = np.abs(np.diff(W[:, -49:], axis=1)).mean(1)
    out = vol1m.trailing_features(P.meta_all, P.rows, P.W, vol48)
    # the carried-over correctness checks of vol1m, asserted
    assert out["max_off"] == 29, f"last minute read is entry+{out['max_off']}, not +29"
    assert out["rep_ratio"] <= 1.0, f"1-minute path does not reproduce the 30-minute window ({out['rep_ratio']:.2f} ulps-budgets)"
    assert out["recomp"] < 1e-6, f"vol_48 from the 1-minute marks differs from the window's by {out['recomp']:.2e}"
    print(f"  [vol] last minute read entry+{out['max_off']}; reproduction {out['rep_ratio']:.3f} of budget; "
          f"vol_48 recomputed from the marks max diff {out['recomp']:.2e}; missing minutes per episode: "
          f"median {np.median(out['nmiss']):.0f}, max {int(out['nmiss'].max())}")
    return vol48, out["vol"], out


def stage_reference():
    t0 = time.time()
    P = Pop()
    print("=" * 110)
    print("HL-FLOW1 PART 1 -- target, chance bar, reference")
    print("=" * 110)
    print(f"  {P.sp.describe()}")
    print(f"  HO_BOUNDARY (first HO2 day, from the meta only): {pd.Timestamp(HO_BOUNDARY).date()}")
    print(f"  matched population {P.n:,} of {len(P.meta_all):,} dislocations "
          f"(lost {len(P.meta_all) - P.n:,}, {100 * (1 - P.n / len(P.meta_all)):.2f}%)")
    print(f"  train {int(P.tr.sum()):,}  val {int(P.va.sum()):,}  held out {int(P.te.sum()):,}  "
          f"HO1 {len(P.halves['HO1']):,}  HO2 {len(P.halves['HO2']):,}")
    # ---- descriptives
    print()
    print("  REACH RATE vs CHANCE (reading tool; chance uses future step sizes)")
    print(f"    {'':<14}{'n':>8}{'reach rate':>12}{'mean chance':>13}{'gap':>9}")
    bands = P.band()
    for lbl, m in (("all", np.ones(P.n, bool)), ("train", P.tr), ("val", P.va), ("HO1", P.te & (P.day < HO_BOUNDARY)),
                   ("HO2", P.te & (P.day >= HO_BOUNDARY)), ("|z| < 2", bands == "<2"),
                   ("|z| 2-3", bands == "2-3"), ("|z| >= 3", bands == ">=3")):
        print(f"    {lbl:<14}{int(m.sum()):>8,}{P.y[m].mean():>12.4f}{P.chance[m].mean():>13.4f}"
              f"{P.y[m].mean() - P.chance[m].mean():>+9.4f}")
    # ---- secondary target: reach on the 30-minute grid
    e, s = P.e, np.where(P.e >= 0, 1.0, -1.0)
    Yk = P.Y[P.rows]
    move30 = -(Yk[:, 1:] - e[:, None]) * s[:, None]            # toward mu on the 30m grid, bars 1..20
    reach30 = np.nanmax(move30, axis=1) >= np.abs(e)
    print(f"  30-minute-grid reach (secondary target): rate {reach30.mean():.4f} (1-minute {P.y.mean():.4f}); "
          f"1m reach but not 30m {int((P.y.astype(bool) & ~reach30).sum()):,}; 30m reach but not 1m "
          f"{int((~P.y.astype(bool) & reach30).sum()):,}")
    # ---- reference features and model
    print()
    t1 = time.time()
    vol48, vol48_1m, vout = vol_features(P)
    print(f"  [{time.time() - t1:.0f}s]")
    cols = np.column_stack([vol48, vol48_1m, P.meta.sigma.to_numpy(float), np.abs(P.e)])
    bad = ~np.isfinite(cols[:, :3]) | (cols[:, :3] <= 0)
    print(f"  non-positive or missing vol_48 / vol_48_1m / sigma rows: {int(bad.any(1).sum())} "
          f"(set to the TRAIN median after the log, as REACH-MU)")
    with np.errstate(divide="ignore", invalid="ignore"):
        X = np.column_stack([np.where(cols[:, j] > 0, np.log(cols[:, j]), np.nan) for j in range(3)] + [cols[:, 3]])
    for j in range(X.shape[1]):
        m_ = ~np.isfinite(X[:, j])
        if m_.any():
            X[m_, j] = np.nanmedian(X[P.tr, j])
    mu_, sd_ = X[P.tr].mean(0), X[P.tr].std(0)
    Z = (X - mu_) / sd_
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(penalty=None, max_iter=5000).fit(Z[P.tr], P.y[P.tr])
    ref = lr.predict_proba(Z)[:, 1]
    print(f"  reference logistic on log(vol_48), log(vol_48_1m), log(sigma), |z|: coefficients "
          f"{np.round(lr.coef_[0], 3).tolist()}; val log loss {logloss_rows(P.y[P.va], ref[P.va]).mean():.5f} "
          f"(base-rate {logloss_rows(P.y[P.va], np.full(int(P.va.sum()), P.y[P.tr].mean())).mean():.5f})")
    np.savez_compressed(REF_OUT, rows=P.rows, vol_48=vol48, vol_48_1m=vol48_1m, ref=ref, X=X)
    print(f"  [WROTE] {os.path.relpath(REF_OUT, paths.RESEARCH)}")
    # ---- held-out scoring
    print()
    print("=" * 110)
    print("SCORING, held out only, HO1 and HO2 separately (day-clustered 95%)")
    print("=" * 110)
    gaps = {}
    for hn, ix in P.halves.items():
        yh, ch, sc = P.y[ix], P.chance[ix], ref[ix]
        print(f"  {hn}: n {len(ix):,}, reach rate {yh.mean():.4f}, mean chance {ch.mean():.4f}; AUC {auc(yh, sc):.4f}")
        for c in CATCH:
            fs, hr, fx = flag_share(sc, yh, c)
            print(f"    catch {int(100 * c)}%: flag share {fs:.3f}, hit rate {hr:.3f}  "
                  f"(random: {c:.3f} / {yh.mean():.3f}); flagged chance {ch[fx].mean():.3f}")
        for kind, lbl in (("flag80", "flag share at 80% catch"), ("top20", "top-20% hit rate"),
                          ("gap80", "beyond-chance gap, flagged at 80% catch"),
                          ("gap20", "beyond-chance gap, top 20%")):
            r = half_measure(P, kind, ref, hn)
            gaps[(hn, kind)] = r
            print(f"    {lbl:<44}{r[0]:+.4f}  [{r[1]:+.4f}, {r[2]:+.4f}]")
    print()
    both = all(gaps[(hn, "gap80")][1] > 0 for hn in P.halves)
    one = [hn for hn in P.halves if gaps[(hn, "gap80")][1] > 0]
    print("  GATE: the reference's beyond-chance gap of the flagged set (80% catch) wholly above zero in both halves: "
          f"{'**YES -- this CONTRADICTS the OKX result**' if both else 'NO'}"
          + (f"   (clears in {', '.join(one)} only)" if (one and not both) else ""))
    print("  diagnostic, not the gate: top-20% gap wholly above zero in "
          + (", ".join(hn for hn in P.halves if gaps[(hn, 'gap20')][1] > 0) or "neither half"))
    print(f"  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["paths", "reference"], required=True)
    a = ap.parse_args()
    {"paths": stage_paths, "reference": stage_reference}[a.stage]()
