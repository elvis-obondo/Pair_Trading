"""A Gaussian copula on QTREE's marginals: MAE and MFE jointly.

    .venv/bin/python research/dislocation_model/copula.py 2>&1 \
        | tee research/dislocation_model/logs/copula.log

A SEPARATE DELIVERABLE, NOT A SCOREBOARD ROW. A copula preserves the marginals
by construction, so it cannot move any coverage, gap or skill number on the
calibration tables -- by exactly nothing. What it adds is the JOINT
distribution: how often both excursions are large on the same path, which is
what setting a stop and a target together has to respect. It is scored on
joint questions only, against the one alternative a joint model has to beat:
treating MAE and MFE as independent.

WHY NOW. The dependence measurement (dependence.py, NUMBERS.md "MAE/MFE
dependence") cleared its pre-committed bar in 9 of 9 non-identity cells, PIT
Spearman -0.61 to -0.86, and the copula was built on the user's decision,
overriding an earlier deferral to the strategy phase.

THE MARGINALS are QTREE's, as cached by the matched 1-minute run, verified
against that cache bit for bit and against its fingerprint. Both target
sources. Population ALL.

THE COPULA. Gaussian, one correlation per (source, horizon), fitted on VAL:
the Spearman correlation of val's MAE and MFE PITs, converted to the Gaussian
parameter by rho = 2 sin(pi rho_s / 6), the exact relation for a Gaussian
copula. One parameter is the honest size: the dependence is a single strong
negative association, and a richer family would be fitting the coarseness of a
five-point PIT rather than the paths. The Gaussian copula has no tail
dependence, which is stated rather than hidden: if both-large events cluster
more than a Gaussian allows, the corner table below is where it shows.

THREE THINGS THAT BIAS IT, stated before any number:

  1. FIVE-POINT PIT TIES. ~10% of PITs sit exactly on 0 or 1 and ties
     attenuate a rank correlation, so the fitted rho is biased TOWARD ZERO --
     the copula is, if anything, too close to independence.
  2. VAL CHOSE QTREE'S ITERATION COUNT, so val's PITs are mildly in-sample.
     Not a new discipline exception; val is still never scored.
  3. HELD-OUT REUSE. These held-out rows have been scored before. The joint
     coverage levels are a later look at them; the copula-versus-independence
     difference is a within-row paired contrast and is the new measurement.

THE IDENTITY CELL IS SKIPPED. At 30m and k=1, MAE is exactly -MFE; the joint
law there is the countermonotone bound, known in closed form, and a fitted
copula would only rediscover arithmetic. It is detected from the data.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from scipy.stats import multivariate_normal, norm, spearmanr

import paths
from envelope import (DIRECTIONS, FP_KEY, HLABEL, HORIZONS, HO_BOUNDARY,
                      QUANTILES, assert_1m_dominates, build_context,
                      build_targets_1m, build_targets_30m, cache_fingerprint,
                      day_boot, enforce_two_pass, flat_targets, pit_positions,
                      qtree_val_test, scan_1m_coverage, select_1m_subset)

SOURCES = ("30m", "1m")
IDENTITY_TOL = 1e-9
RHO_CLIP = 0.9999          # keeps the bivariate normal CDF non-degenerate
CORNERS = ((3, 3), (4, 4))  # (q75, q75) and (q95, q95): "both large"


def gauss_copula_grid(rho, qs=QUANTILES):
    """C(a, b) = Phi2(Phi^-1(a), Phi^-1(b); rho) on the quantile grid, 5 x 5."""
    z = norm.ppf(np.asarray(qs))
    pts = np.array([[za, zb] for za in z for zb in z])
    mvn = multivariate_normal(mean=[0.0, 0.0], cov=[[1.0, rho], [rho, 1.0]])
    return np.asarray(mvn.cdf(pts)).reshape(len(qs), len(qs))


def main():
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    X = np.load(paths.ENVFEAT, allow_pickle=False)["X"].astype(np.float64)
    day = meta.day.to_numpy()
    y_entry = Y[:, 0]

    print("=" * 118)
    print("GAUSSIAN COPULA on QTREE marginals -- joint MAE/MFE, fitted on val")
    print("=" * 118)
    print("  A separate deliverable. It cannot move any marginal number, so it is")
    print("  scored only on JOINT questions, against independence.")
    print()

    cache = paths.envelope_preds("match1m")
    if not os.path.exists(cache):
        raise SystemExit("[COP ] no match1m cache -- run envelope.py --stage match1m")
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

    fp = cache_fingerprint([rows], flat_targets(TGT), Xs)
    if FP_KEY not in cached.files or str(cached[FP_KEY]) != fp:
        raise SystemExit(
            f"[COP ] ABORT -- {os.path.basename(cache)} is unstamped or was written "
            f"for different inputs.\n        Run envelope.py --stage match1m first.")
    print(f"  cache fingerprint matches ({fp[:16]}...).")

    dte = ctx["day_test"]
    blocks = {"ALL": np.ones(len(dte), bool), "HO1": dte < HO_BOUNDARY,
              "HO2": dte >= HO_BOUNDARY}
    boots = {b: day_boot(dte[m]) for b, m in blocks.items()}
    print(f"  val {int(ctx['val'].sum()):,} rows (copula fit); held out "
          f"{len(dte):,} rows -- HO1 {int(blocks['HO1'].sum()):,}, "
          f"HO2 {int(blocks['HO2'].sum()):,}")
    print()

    # ---- QTREE marginals on val and held-out, verified against the cache ----
    print("=" * 118)
    print("MARGINALS -- QTREE refitted for its val predictions, checked vs cache")
    print("=" * 118)
    VA, TE = {}, {}
    worst = 0.0
    for src in SOURCES:
        for d in DIRECTIONS:
            vas, tes = [], []
            for k in HORIZONS:
                va, te, _ = qtree_val_test(ctx, TGT[src][(d, k)])
                vas.append(va)
                tes.append(te)
            va_e, _, _ = enforce_two_pass(np.stack(vas))
            te_e, _, _ = enforce_two_pass(np.stack(tes))
            for i, k in enumerate(HORIZONS):
                VA[(src, d, k)], TE[(src, d, k)] = va_e[i], te_e[i]
                worst = max(worst, float(np.max(np.abs(
                    te_e[i] - cached[f"{src}|{d}|QTREE|{k}"]))))
            print(f"  {src}/{d}: refitted 5 horizons   [{time.time()-t0:.0f}s]",
                  flush=True)
    print(f"  worst |refit - cache| over 20 held-out cells: {worst:.3e}")
    if worst > 1e-12:
        raise SystemExit("[COP ] ABORT -- QTREE refit does not reproduce the cache.")
    print()

    # ---- fit the copula on val ----
    print("=" * 118)
    print("THE COPULA -- one Gaussian correlation per cell, fitted on val PITs")
    print("=" * 118)
    print("  rho = 2 sin(pi rho_s / 6) from val's PIT Spearman. The held-out PIT")
    print("  Spearman is printed for comparison only; it plays no part in the fit.")
    print()
    print(f"  {'src':<5}{'h':>6}{'val rho_s':>11}{'gauss rho':>11}"
          f"{'held-out rho_s':>16}{'':>12}")
    FIT, IDENT = {}, {}
    for src in SOURCES:
        for k in HORIZONS:
            ya = TGT[src][("MAE", k)]
            yb = TGT[src][("MFE", k)]
            gap = float(np.max(np.abs(ya[ctx["test"]] + yb[ctx["test"]])))
            IDENT[(src, k)] = gap <= IDENTITY_TOL
            if IDENT[(src, k)]:
                print(f"  {src:<5}{HLABEL[k]:>6}{'':>11}{'':>11}{'':>16}"
                      f"{'IDENTITY -- skipped':>22}")
                continue
            ua = pit_positions(ya[ctx["val"]], VA[(src, "MAE", k)])
            ub = pit_positions(yb[ctx["val"]], VA[(src, "MFE", k)])
            rs = float(spearmanr(ua, ub).statistic)
            rho = float(np.clip(2.0 * np.sin(np.pi * rs / 6.0), -RHO_CLIP, RHO_CLIP))
            ta = pit_positions(ya[ctx["test"]], TE[(src, "MAE", k)])
            tb = pit_positions(yb[ctx["test"]], TE[(src, "MFE", k)])
            rs_te = float(spearmanr(ta, tb).statistic)
            FIT[(src, k)] = dict(rho_s=rs, rho=rho, grid=gauss_copula_grid(rho))
            print(f"  {src:<5}{HLABEL[k]:>6}{rs:>+11.4f}{rho:>+11.4f}{rs_te:>+16.4f}")
    print()

    # ---- joint calibration on held-out ----
    print("=" * 118)
    print("JOINT CALIBRATION -- held out, copula against independence")
    print("=" * 118)
    print("  For every pair of levels (a, b) on the 5 x 5 grid, the event")
    print("  {MAE <= Q_MAE(a) and MFE <= Q_MFE(b)}. Actual frequency against the")
    print("  copula's C(a,b) and independence's a*b. gap = mean |actual - predicted|")
    print("  over the 25 pairs, in pp. cop-ind is PAIRED on identical rows and day")
    print("  resamples: negative = the copula describes the joint law better.")
    print("  'dep only' plugs the ACTUAL held-out marginal frequencies into the")
    print("  copula -- a diagnostic that removes marginal miscalibration and scores")
    print("  the dependence structure alone. Point estimate only; it uses held-out")
    print("  marginals, so it is not a forecast.")
    print()
    q = np.asarray(QUANTILES)
    IND = np.outer(q, q)
    print(f"  {'src':<5}{'h':>6}{'block':>6}{'ind gap':>9}{'cop gap':>9}"
          f"{'cop-ind':>9}{'[95% CI]':>18}{'dep only':>10}{'':>10}")
    res = []
    CORN = {}
    for src in SOURCES:
        for k in HORIZONS:
            if IDENT[(src, k)]:
                continue
            f = FIT[(src, k)]
            ya = TGT[src][("MAE", k)][ctx["test"]]
            yb = TGT[src][("MFE", k)][ctx["test"]]
            ha = ya[:, None] <= TE[(src, "MAE", k)]
            hb = yb[:, None] <= TE[(src, "MFE", k)]
            J = ha[:, :, None] & hb[:, None, :]          # rows x 5 x 5
            mvn = multivariate_normal(mean=[0.0, 0.0],
                                      cov=[[1.0, f["rho"]], [f["rho"], 1.0]])
            for blk, m in blocks.items():
                Jm, ham, hbm = J[m], ha[m], hb[m]
                freq = Jm.mean(0)
                g_ind = 100 * float(np.abs(freq - IND).mean())
                g_cop = 100 * float(np.abs(freq - f["grid"]).mean())
                draws = np.empty(len(boots[blk]))
                for r, ix in enumerate(boots[blk]):
                    fr = Jm[ix].mean(0)
                    draws[r] = 100 * (np.abs(fr - f["grid"]).mean()
                                      - np.abs(fr - IND).mean())
                lo, hi = np.percentile(draws, [2.5, 97.5])
                # dependence structure only: actual marginals into the copula
                ma, mb = ham.mean(0), hbm.mean(0)
                za = norm.ppf(np.clip(ma, 1e-6, 1 - 1e-6))
                zb = norm.ppf(np.clip(mb, 1e-6, 1 - 1e-6))
                pts = np.array([[x1, x2] for x1 in za for x2 in zb])
                adj = np.asarray(mvn.cdf(pts)).reshape(5, 5)
                g_dep = 100 * float(np.abs(freq - adj).mean())
                tag = ("COPULA" if hi < 0 else "indep" if lo > 0 else "")
                res.append(dict(src=src, k=k, blk=blk, better=hi < 0, worse=lo > 0))
                print(f"  {src:<5}{HLABEL[k]:>6}{blk:>6}{g_ind:>9.2f}{g_cop:>9.2f}"
                      f"{g_cop-g_ind:>+9.2f}{f'[{lo:+.2f},{hi:+.2f}]':>18}"
                      f"{g_dep:>10.2f}{tag:>10}")
                if blk == "ALL":
                    for (ia, ib) in CORNERS:
                        act = float(1 - ham[:, ia].mean() - hbm[:, ib].mean()
                                    + Jm[:, ia, ib].mean())
                        cop = float(1 - q[ia] - q[ib] + f["grid"][ia, ib])
                        ind = float((1 - q[ia]) * (1 - q[ib]))
                        CORN[(src, k, ia, ib)] = (act, cop, ind)
    print()

    # ---- the joint question a stop and target need ----
    print("=" * 118)
    print("BOTH LARGE -- P(MAE above its q and MFE above its q), held out")
    print("=" * 118)
    print("  The stop-and-target question: how often does a path run far against")
    print("  you AND far for you. Independence predicts (1-a)(1-b). A Gaussian")
    print("  copula has no tail dependence, so if both-large clusters more than it")
    print("  allows, this is where it shows.")
    print()
    print(f"  {'src':<5}{'h':>6}{'corner':>12}{'actual':>9}{'copula':>9}"
          f"{'indep':>9}")
    for (src, k, ia, ib), (act, cop, ind) in CORN.items():
        print(f"  {src:<5}{HLABEL[k]:>6}"
              f"{'q'+str(int(100*q[ia]))+'/q'+str(int(100*q[ib])):>12}"
              f"{100*act:>8.2f}%{100*cop:>8.2f}%{100*ind:>8.2f}%")
    print()

    # ---- persist ----
    out = paths.envelope_preds("copula")
    np.savez_compressed(out, **{FP_KEY: np.array(fp)},
                        **{f"rho|{s_}|{k_}": np.array(FIT[(s_, k_)]["rho"])
                           for (s_, k_) in FIT})
    print(f"  [CACHE] wrote {os.path.basename(out)}: one Gaussian rho per cell, "
          f"fingerprinted.")
    print()

    # ---- verdict ----
    print("=" * 118)
    print("VERDICT")
    print("=" * 118)
    allr = [r for r in res if r["blk"] == "ALL"]
    print(f"  {len(allr)} non-identity cells on the full held-out block. The copula")
    print(f"  describes the joint law better than independence, by a paired interval")
    print(f"  excluding zero, in {sum(r['better'] for r in allr)} of {len(allr)}; "
          f"worse in {sum(r['worse'] for r in allr)}.")
    for blk in ("HO1", "HO2"):
        rr = [r for r in res if r["blk"] == blk]
        print(f"  {blk}: better {sum(r['better'] for r in rr)}, worse "
              f"{sum(r['worse'] for r in rr)}, of {len(rr)}.")
    print()
    print("  THIS DOES NOT TOUCH THE CALIBRATION SCOREBOARD. The marginals are")
    print("  QTREE's, unchanged. The copula only says how the two marginals")
    print("  combine on the same path -- the input a joint stop-and-target rule")
    print("  needs. Whether to set them jointly is a strategy-phase decision.")
    print()
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 118)


if __name__ == "__main__":
    main()
