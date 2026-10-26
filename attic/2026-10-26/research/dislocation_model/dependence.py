"""Do MAE and MFE move together on the same path? Measure first, build nothing.

    .venv/bin/python research/dislocation_model/dependence.py 2>&1 \
        | tee research/dislocation_model/logs/dependence.log

THE QUESTION. MAE and MFE are measured on the same episode: how far the spread
went against you, and how far it went for you. If they are dependent AFTER the
features have had their say, a stop and a target cannot be set independently
and a joint model is worth building. If not, the correlation is the finding.

NO FITTING HAPPENS HERE. Every prediction is read from the cache the matched
1-minute run wrote. Nothing is refitted and no row is looked at that has not
already been scored.

THE MEASUREMENT. For each held-out episode, where did its realised MAE fall
inside its OWN predicted distribution -- its PIT, in [0, 1] -- and the same for
MFE. One Spearman correlation between the two series per cell, with a
day-clustered interval.

BESIDE IT, THE RAW SPEARMAN OF MAE AGAINST MFE, and the pair is the point. The
raw number is the path's own arithmetic; the PIT number is what is left after
conditioning on the features. Climatology's PITs reproduce the raw ranks up to
the boundary ties, which is why the raw column needs no separate model. A large
PIT correlation that merely echoes a large raw one says the features did not
explain the link; a PIT correlation near zero against a large raw one says
they did.

ONE CELL IS AN IDENTITY AND IS EXCLUDED FROM THE DECISION. At 30-minute
resolution and k=1 the target is a single step, so MAE is exactly -MFE:
max|MAE + MFE| = 0.00e+00 on every row. Their PITs correlate near -1, the
interval excludes zero, and the cell would print CLEARS BAR on arithmetic alone
-- the unfolded-AUC failure again, a number that passes every gate because of
how the target is built. Identities are DETECTED from the data, not hard-coded,
and excluded wherever max|MAE + MFE| is zero. The 1-minute target has none:
its k=1 window holds thirty steps.

TWO MECHANISMS WITH OPPOSITE SIGNS, so a near-zero is NOT independence. MAE and
MFE of the same path share an ENDPOINT, which makes them trade off: a path that
ends far toward mu cannot also have had its worst point far away, all else
equal. That pushes the correlation NEGATIVE, and it dominates at short
horizons. They also share REALISED VOLATILITY: a path that moves a lot moves a
lot both ways. That pushes it POSITIVE. At long horizons the two can cancel. So
a correlation near zero means "no net monotone association", not "independent",
and the statistic here cannot tell those apart.

THAT ALSO RETIRES A CLAIM AN EARLIER VERSION MADE. It called every number a
"lower bound" on the true dependence because the five-point PIT puts ~10% of
episodes on exact ties at 0 and 1, and ties attenuate a correlation. That is
true of a single monotone association. It is not true of a net of two opposing
ones: attenuation shrinks the net toward zero without saying which side of it
the truth is on. The boundary mass is still printed per cell as the measure of
how coarse the PIT is.

THE DECISION RULE, STATED BEFORE THE NUMBERS. Over the NON-IDENTITY cells on the
full held-out block, build a copula only if a majority have a PIT interval
excluding zero AND |rho| above BUILD_BAR. Otherwise the correlation is the
deliverable and this script is the whole analysis.

WHAT A COPULA WOULD AND WOULD NOT DO. A copula PRESERVES THE MARGINALS BY
CONSTRUCTION. It cannot move any calibration gap, coverage number or pinball
skill already tracked -- by exactly nothing, not merely a little. Its value is
joint questions: how often both excursions are large on the same path, which
setting a stop and a target TOGETHER requires. That is a strategy-phase
deliverable and must never appear as a sixth row on the calibration scoreboard.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import paths
from envelope import (DIRECTIONS, FP_KEY, HLABEL, HORIZONS, HO_BOUNDARY,
                      REGISTRY_UNTIL_2026_10_12,
                      assert_1m_dominates, build_context, build_targets_1m,
                      build_targets_30m, cache_fingerprint, day_boot,
                      flat_targets, pit_positions, scan_1m_coverage,
                      select_1m_subset)

BUILD_BAR = 0.125       # midpoint of the brief's 0.10-0.15 range, fixed in advance
IDENTITY_TOL = 1e-9     # max|MAE + MFE| at or below this is an identity, not data
SOURCES = ("30m", "1m")


def spearman_ci(u, v, boot):
    """Spearman with a day-clustered 95% interval.

    Resamples DAYS, not episodes: episodes share days and move together on
    market-wide news. A resampled block that is constant in either series has
    an undefined correlation and is dropped, never read as zero; the count of
    dropped draws is returned so a thin interval is visible.
    """
    pt = float(spearmanr(u, v).statistic)
    draws = np.empty(len(boot))
    for r, ix in enumerate(boot):
        a, b = u[ix], v[ix]
        draws[r] = (np.nan if (np.ptp(a) == 0 or np.ptp(b) == 0)
                    else float(spearmanr(a, b).statistic))
    return (pt, float(np.nanpercentile(draws, 2.5)),
            float(np.nanpercentile(draws, 97.5)), int(np.isnan(draws).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="QTREE",
                    choices=[m for m, _ in REGISTRY_UNTIL_2026_10_12],
                    help="whose predicted distribution the PIT is taken in. "
                         "The dependence is a property of the PATHS given the "
                         "features, so a result that moves a lot across this "
                         "flag is a warning, not a finding.")
    args = ap.parse_args()
    t0 = time.time()

    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    day = meta.day.to_numpy()
    y_entry = Y[:, 0]

    print("=" * 118)
    print(f"MAE / MFE DEPENDENCE -- PIT correlation, model {args.model}, no fitting")
    print("=" * 118)
    print("  Reads the cache the matched 1-minute run wrote. Nothing is refitted.")
    print("  A copula is NOT built here and will not be unless a majority of")
    print(f"  non-identity cells clear both bars: interval excluding zero AND")
    print(f"  |rho| > {BUILD_BAR}. A copula preserves the marginals by construction")
    print("  and could never move a number on the calibration scoreboard.")
    print()

    cache = paths.envelope_preds("match1m")
    if not os.path.exists(cache):
        raise SystemExit(
            f"[DEP ] ABORT -- no cached predictions at {cache}. This analysis "
            f"refits nothing,\n        so it needs the matched run's output: "
            f"envelope.py --stage match1m")
    cached = np.load(cache, allow_pickle=False)

    cov = scan_1m_coverage(meta, verbose=False)
    mask_used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(mask_used)
    Xs = X[rows]
    ctx = build_context(np.ones(len(rows), bool), Xs, day[rows],
                        y_entry[rows], verbose=True)
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    TGT = {"30m": T30, "1m": T1M}

    # the cached predictions must belong to THESE inputs
    fp = cache_fingerprint([rows], flat_targets(TGT), Xs)
    if FP_KEY in cached.files:
        if str(cached[FP_KEY]) != fp:
            raise SystemExit(
                f"[DEP ] ABORT -- {os.path.basename(cache)} was written for "
                f"different inputs (fingerprint\n        mismatch). Its PITs would "
                f"be computed against the wrong targets. Rerun --stage match1m.")
        print(f"  cache fingerprint matches ({fp[:16]}...).")
    else:
        print("  LEGACY cache with no fingerprint -- run --stage match1m once to")
        print("  verify and stamp it. Proceeding, but this check did not run.")

    dte = ctx["day_test"]
    blocks = {"ALL": np.ones(len(dte), bool),
              "HO1": dte < HO_BOUNDARY,
              "HO2": dte >= HO_BOUNDARY}
    boots = {b: day_boot(dte[m]) for b, m in blocks.items()}
    print(f"  held out {len(dte):,} rows / {len(np.unique(dte)):,} days;  "
          f"HO1 {int(blocks['HO1'].sum()):,}  HO2 {int(blocks['HO2'].sum()):,}")
    print()

    # ---- identities and PIT coarseness ----
    print("=" * 118)
    print("IDENTITIES AND PIT COARSENESS")
    print("=" * 118)
    print("  max|MAE+MFE| = 0 marks a cell where MAE is exactly -MFE by")
    print("  construction. Such a cell is printed but EXCLUDED from the decision.")
    print("  Boundary mass: share of episodes whose PIT is exactly 0 or 1 (outside")
    print("  the five stored quantiles), ~10% on a calibrated model. It measures")
    print("  how coarse the PIT is; it does not make any number a bound.")
    print()
    print(f"  {'src':<5}{'h':>6}{'max|MAE+MFE|':>14}{'identity':>10}"
          f"{'MAE tied':>10}{'MFE tied':>10}")
    U, RAW, IDENT = {}, {}, {}
    for src in SOURCES:
        for k in HORIZONS:
            yy = {d: TGT[src][(d, k)][ctx["test"]] for d in DIRECTIONS}
            gap = float(np.max(np.abs(yy["MAE"] + yy["MFE"])))
            IDENT[(src, k)] = gap <= IDENTITY_TOL
            RAW[(src, k)] = yy
            us = {}
            for d in DIRECTIONS:
                name = f"{src}|{d}|{args.model}|{k}"
                if name not in cached.files:
                    raise SystemExit(
                        f"[DEP ] ABORT -- {name} is not in "
                        f"{os.path.basename(cache)}. Rerun --stage match1m.")
                us[d] = pit_positions(yy[d], cached[name])
            U[(src, k)] = us
            tie = {d: float(((us[d] <= 0) | (us[d] >= 1)).mean()) for d in DIRECTIONS}
            print(f"  {src:<5}{HLABEL[k]:>6}{gap:>14.2e}"
                  f"{('YES' if IDENT[(src, k)] else 'no'):>10}"
                  f"{100*tie['MAE']:>9.1f}%{100*tie['MFE']:>9.1f}%")
    print()

    # ---- the correlations ----
    print("=" * 118)
    print("RAW vs CONDITIONAL -- Spearman of MAE against MFE")
    print("=" * 118)
    print("  raw  = ranks of the realised MAE and MFE themselves: the path's")
    print("         arithmetic, before any feature.")
    print(f"  PIT  = ranks of each episode's position in its own {args.model}")
    print("         distribution: what is left after the features.")
    print("  Negative = the excursions trade off (shared endpoint). Positive =")
    print("  they move together (shared volatility). Near zero can be cancellation")
    print("  of the two, so it is not evidence of independence.")
    print()
    print(f"  {'src':<5}{'h':>6}{'block':>6}{'raw':>9}{'[95% CI]':>18}"
          f"{'PIT':>9}{'[95% CI]':>18}{'n':>8}{'':>14}")
    out = []
    for src in SOURCES:
        for k in HORIZONS:
            for blk, m in blocks.items():
                bt = boots[blk]
                r_pt, r_lo, r_hi, _ = spearman_ci(RAW[(src, k)]["MAE"][m],
                                                  RAW[(src, k)]["MFE"][m], bt)
                p_pt, p_lo, p_hi, _ = spearman_ci(U[(src, k)]["MAE"][m],
                                                  U[(src, k)]["MFE"][m], bt)
                excl = (p_lo > 0) or (p_hi < 0)
                ident = IDENT[(src, k)]
                clears = (not ident) and excl and abs(p_pt) > BUILD_BAR
                out.append(dict(src=src, k=k, blk=blk, pit=p_pt, lo=p_lo,
                                hi=p_hi, raw=r_pt, excl=excl, clears=clears,
                                ident=ident))
                tag = ("IDENTITY" if ident else
                       "CLEARS BAR" if clears else "excl 0" if excl else "")
                print(f"  {src:<5}{HLABEL[k]:>6}{blk:>6}{r_pt:>+9.4f}"
                      f"{f'[{r_lo:+.3f},{r_hi:+.3f}]':>18}{p_pt:>+9.4f}"
                      f"{f'[{p_lo:+.3f},{p_hi:+.3f}]':>18}{int(m.sum()):>8,}"
                      f"{tag:>14}")
    print()

    # ---- the decision ----
    print("=" * 118)
    print("THE DECISION")
    print("=" * 118)
    print(f"  Rule, fixed before the run: over the NON-IDENTITY cells on the full")
    print(f"  held-out block, build a copula only if a MAJORITY have a PIT interval")
    print(f"  excluding zero AND |PIT spearman| > {BUILD_BAR}.")
    print()
    dec = [r for r in out if r["blk"] == "ALL" and not r["ident"]]
    excluded = [r for r in out if r["blk"] == "ALL" and r["ident"]]
    n_excl = sum(r["excl"] for r in dec)
    n_clear = sum(r["clears"] for r in dec)
    for r in excluded:
        print(f"  EXCLUDED as an identity: {r['src']}/{HLABEL[r['k']]} "
              f"(PIT {r['pit']:+.4f}, raw {r['raw']:+.4f}) -- arithmetic, not data.")
    print(f"  {len(dec)} cells decide. {n_excl} PIT intervals exclude zero; "
          f"{n_clear} also clear |rho| > {BUILD_BAR}.")
    if dec:
        big = max(dec, key=lambda r: abs(r["pit"]))
        print(f"  Largest |PIT spearman|: {big['pit']:+.4f} at {big['src']}/"
              f"{HLABEL[big['k']]} [{big['lo']:+.3f}, {big['hi']:+.3f}], "
              f"raw {big['raw']:+.4f} at the same cell.")
    print()
    if dec and n_clear > len(dec) / 2:
        print("  VERDICT: CONDITIONAL DEPENDENCE IS THERE. A majority of cells clear")
        print("  both bars after the features, so a copula on the EXISTING marginals")
        print("  is worth building -- as its own strategy-phase deliverable. It will")
        print("  not move one number on the calibration scoreboard.")
    elif n_clear:
        print("  VERDICT: MIXED. Some cells clear both bars and most do not, so the")
        print("  dependence is not a stable property of the paths. Report the")
        print("  correlations as the finding; do not build a copula on a minority.")
    else:
        print("  VERDICT: NO NET CONDITIONAL DEPENDENCE DETECTED. No non-identity")
        print("  cell clears both bars, so the correlation IS the finding. Read it")
        print("  carefully: MAE and MFE are linked by two mechanisms of opposite sign,")
        print("  and a near-zero net can be their cancellation. This says a stop and")
        print("  a target show no net monotone link after the features -- not that")
        print("  they are independent. Compare the raw column to see how much the")
        print("  features absorbed.")
    print()
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 118)


if __name__ == "__main__":
    main()
