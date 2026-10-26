"""Which of the five features carries the skill? Two cells, two models.

    .venv/bin/python research/dislocation_model/importance.py 2>&1 \
        | tee research/dislocation_model/logs/importance.log

THE QUESTION. The conditional models beat climatology by +3-4% pinball on the
1-minute MFE envelope. Does that come from the volatility features already
understood (vol_48, vratio, vol_slope) or from the two microstructure ones
(sandwich, off_mark)? If the microstructure pair carries real weight, basis --
the related, untried microstructure feature -- is worth building next. If the
skill is the volatility trio again, basis drops in priority.

SCOPE, AS BRIEFED. 1-minute target, ALL population, the matched 53,757-episode
set and its usual split. Two cells:
    MFE 10h -- the cell with confirmed skill
    MAE 10h -- where skill was only suggestive, for contrast
No new features, target, split, gate or model type.

WHAT IS MEASURED.
  Linear QR: the fitted coefficients. Features are standardised on train, so a
    coefficient is the change in that quantile, in sigma of the target, per
    one train-standard-deviation of the feature -- comparable across features.
    Reported at q50 (location) and as q95 minus q5 (how the feature widens or
    narrows the envelope), with all five quantiles in an appendix.
  QTREE: permutation importance on the HELD-OUT block. Each feature's column is
    shuffled across held-out rows (20 shuffles, averaged) and the rise in mean
    pinball loss is expressed in SKILL POINTS against climatology:
    100 x (pinball_shuffled - pinball_base) / pinball_climatology. So a feature
    worth 2.0 points is worth 2.0 of the model's skill percentage. The interval
    is day-clustered: per-row losses are resampled by held-out DAY.

TWO ADDITIONS, both aimed at the decision rather than at new findings:
  GROUPS. The decision is "volatility trio vs microstructure pair", so each
    group is also permuted JOINTLY (one row shuffle applied to all its
    columns, which keeps the group's own joint distribution intact). With
    correlated features, single-feature permutation spreads shared credit
    unpredictably; the group rows do not have that problem.
  COLLINEARITY CONTEXT. The train correlation matrix is printed, because
    multiple-regression coefficients are CONDITIONAL on the other features and
    can shrink or flip sign under collinearity without the feature being
    unimportant. A Linear QR permutation importance is printed beside the
    coefficients as the cross-check for exactly that.

MODELS ARE REFITTED, MINIMALLY. Only predictions were ever cached, never fitted
models. QTREE is refitted for all five horizons of each direction (cheap) so the
refit can be checked against the cache EXACTLY after the same two-pass
enforcement; Linear QR is refitted at 10h only (the LP is the expensive model)
and checked by the share of predictions that match -- the 10h value can be
lifted by horizon enforcement, which a single-horizon refit cannot reproduce.
Importance is computed on the per-horizon QTREE predictions, before horizon
enforcement, which moved 0.16-0.68% of QTREE's predictions.

HELD-OUT REUSE. These rows have been scored before; this is a later look at
them, for attribution rather than for a new skill claim.
"""
import itertools
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
from envelope import (FP_KEY, HLABEL, HORIZONS, QUANTILES, _pinball_rows,
                      build_context, build_targets_1m, build_targets_30m,
                      cache_fingerprint, day_boot, enforce_two_pass,
                      fit_linear, fit_qtree, flat_targets, scan_1m_coverage,
                      select_1m_subset, assert_1m_dominates)

CELLS = (("MFE", 20), ("MAE", 20))
SRC = "1m"
N_SHUFFLE = 20
SEED = 20261011
GROUPS = (("VOL TRIO (vol_48+vratio+vol_slope)", ("vol_48", "vratio", "vol_slope")),
          ("MICRO PAIR (sandwich+off_mark)", ("sandwich", "off_mark")),
          ("ALL FIVE", ("vol_48", "vratio", "vol_slope", "sandwich", "off_mark")))


def qtree_predict(models, X):
    """Re-predict with each fitted quantile tree at its val-chosen iteration."""
    out = np.empty((len(X), len(models)))
    for j, (q, m, best) in enumerate(models):
        out[:, j] = next(itertools.islice(m.staged_predict(X), best, None))
    return np.maximum.accumulate(out, axis=1)


def importance(predict, Xte, cols, y, pc_rows, boot, rng):
    """Skill points lost when `cols` are shuffled jointly; day-clustered CI."""
    base = _pinball_rows(y, predict(Xte))
    acc = np.zeros(len(y))
    for _ in range(N_SHUFFLE):
        Xp = Xte.copy()
        perm = rng.permutation(len(y))
        Xp[:, cols] = Xte[perm][:, cols]
        acc += _pinball_rows(y, predict(Xp)) - base
    d = acc / N_SHUFFLE
    pt = 100.0 * d.mean() / pc_rows.mean()
    draws = np.array([100.0 * d[ix].mean() / pc_rows[ix].mean() for ix in boot])
    return pt, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def main():
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    day = meta.day.to_numpy()

    print("=" * 112)
    print("FEATURE IMPORTANCE -- 1-minute target, ALL, MFE 10h and MAE 10h")
    print("=" * 112)
    cache_path = paths.envelope_preds("match1m")
    cached = np.load(cache_path, allow_pickle=False)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    Xs = X[rows]
    ctx = build_context(np.ones(len(rows), bool), Xs, day[rows], Y[rows, 0],
                        verbose=True)
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    fp = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), Xs)
    if FP_KEY not in cached.files or str(cached[FP_KEY]) != fp:
        raise SystemExit("[IMP ] cache fingerprint missing or mismatched -- "
                         "rerun envelope.py --stage match1m")
    print(f"  cache fingerprint matches ({fp[:16]}...).")
    boot = day_boot(ctx["day_test"])
    rng = np.random.default_rng(SEED)
    print(f"  held out {ctx['n_test']:,} rows / {len(np.unique(ctx['day_test']))} "
          f"days; {N_SHUFFLE} shuffles per feature, seed {SEED}")
    print()

    # ---- collinearity context ----
    print("=" * 112)
    print("TRAIN CORRELATIONS of the five features -- read before the coefficients")
    print("=" * 112)
    C = np.corrcoef(ctx["Ztr"].T)
    print("  " + " " * 11 + "".join(f"{n:>11}" for n in names))
    for i, n in enumerate(names):
        print(f"  {n:<11}" + "".join(f"{C[i, j]:>+11.3f}" for j in range(len(names))))
    print()

    results = {}
    for d, k in CELLS:
        y_all = T1M[(d, k)]
        y = y_all[ctx["test"]]
        tag = f"{SRC}/{d}/{HLABEL[k]}"
        print("=" * 112)
        print(f"CELL {tag}")
        print("=" * 112)

        # ---- QTREE: all five horizons, exact cache check ----
        tes, qmodels = [], None
        for kk in HORIZONS:
            ms = [] if kk == k else None
            tes.append(fit_qtree(ctx, T1M[(d, kk)], models=ms))
            if kk == k:
                qmodels = ms
        enf, _, _ = enforce_two_pass(np.stack(tes))
        qerr = max(float(np.max(np.abs(enf[i] - cached[f"{SRC}|{d}|QTREE|{kk}"])))
                   for i, kk in enumerate(HORIZONS))
        print(f"  QTREE refit, 5 horizons, vs cache after two-pass enforcement: "
              f"worst {qerr:.3e}   [{time.time()-t0:.0f}s]")
        if qerr > 1e-12:
            raise SystemExit("[IMP ] QTREE refit does not reproduce the cache.")

        # ---- Linear QR: 10h only, share-identical check ----
        lmodels = []
        lin = fit_linear(ctx, y_all, tag, models=lmodels)
        lin_q = np.maximum.accumulate(lin, axis=1)
        ref = cached[f"{SRC}|{d}|Linear QR|{k}"]
        same = float((np.abs(lin_q - ref) <= 1e-9).mean())
        print(f"  Linear QR refit at {HLABEL[k]}: {100*same:.4f}% of predictions "
              f"match the cache (the rest are horizon-enforcement lifts), max "
              f"diff {float(np.max(np.abs(lin_q-ref))):.3e}   [{time.time()-t0:.0f}s]")

        # ---- skill sanity ----
        pc = _pinball_rows(y, cached[f"{SRC}|{d}|Climatology|{k}"])
        qpred = qtree_predict(qmodels, ctx["Xte"])
        sk_q = 100 * (1 - _pinball_rows(y, qpred).mean() / pc.mean())
        sk_qc = 100 * (1 - _pinball_rows(y, cached[f"{SRC}|{d}|QTREE|{k}"]).mean()
                       / pc.mean())
        sk_l = 100 * (1 - _pinball_rows(y, lin_q).mean() / pc.mean())
        print(f"  skill vs climatology: QTREE {sk_q:+.2f}% (refit, pre-horizon "
              f"enforcement)  {sk_qc:+.2f}% (cache)   Linear QR {sk_l:+.2f}%")
        print()

        # ---- coefficients ----
        coef = np.array([m.coef_ for _, m in lmodels])        # 5 quantiles x 5 features
        def lin_predict(Z):
            return np.maximum.accumulate(
                np.column_stack([m.predict(Z) for _, m in lmodels]), axis=1)

        imp_q, imp_l = {}, {}
        for j, n in enumerate(names):
            imp_q[n] = importance(lambda Xp: qtree_predict(qmodels, Xp),
                                  ctx["Xte"], [j], y, pc, boot, rng)
            imp_l[n] = importance(lin_predict, ctx["Zte"], [j], y, pc, boot, rng)
        for gname, gcols in GROUPS:
            idx = [names.index(c) for c in gcols]
            imp_q[gname] = importance(lambda Xp: qtree_predict(qmodels, Xp),
                                      ctx["Xte"], idx, y, pc, boot, rng)
            imp_l[gname] = importance(lin_predict, ctx["Zte"], idx, y, pc, boot, rng)
        print(f"  [{time.time()-t0:.0f}s]")
        results[(d, k)] = dict(coef=coef, imp_q=imp_q, imp_l=imp_l,
                               sk_q=sk_q, sk_l=sk_l)

        print(f"  THE TABLE -- {tag}. Coefficients in target-sigma per train-SD of")
        print(f"  the feature. Importance in skill points (of QTREE's {sk_q:+.2f}%).")
        print()
        print(f"  {'feature':<36}{'LinQR q50':>10}{'LinQR q95-q5':>14}"
              f"{'QTREE perm. importance':>24}{'[95% CI, day-clustered]':>26}")
        for j, n in enumerate(names):
            p_, lo, hi = imp_q[n]
            print(f"  {n:<36}{coef[2, j]:>+10.4f}{coef[4, j]-coef[0, j]:>+14.4f}"
                  f"{p_:>+24.3f}{f'[{lo:+.3f},{hi:+.3f}]':>26}")
        for gname, _ in GROUPS:
            p_, lo, hi = imp_q[gname]
            print(f"  {gname:<36}{'':>10}{'':>14}{p_:>+24.3f}"
                  f"{f'[{lo:+.3f},{hi:+.3f}]':>26}")
        print()
        print(f"  Cross-check -- Linear QR permutation importance, same units "
              f"(of its {sk_l:+.2f}%):")
        for n in names + [g for g, _ in GROUPS]:
            p_, lo, hi = imp_l[n]
            print(f"    {n:<36}{p_:>+10.3f}  [{lo:+.3f},{hi:+.3f}]")
        print()
        print("  Appendix -- Linear QR coefficient at every quantile:")
        print(f"    {'feature':<12}" + "".join(f"{'q'+str(int(100*q)):>10}" for q in QUANTILES))
        for j, n in enumerate(names):
            print(f"    {n:<12}" + "".join(f"{coef[i, j]:>+10.4f}" for i in range(len(QUANTILES))))
        print()

    # ---- the decision ----
    print("=" * 112)
    print("WHAT IT DECIDES")
    print("=" * 112)
    for d, k in CELLS:
        r = results[(d, k)]
        v = r["imp_q"][GROUPS[0][0]]
        m_ = r["imp_q"][GROUPS[1][0]]
        print(f"  {SRC}/{d}/{HLABEL[k]}: QTREE skill {r['sk_q']:+.2f}%. Shuffling the "
              f"volatility trio costs {v[0]:+.2f} [{v[1]:+.2f},{v[2]:+.2f}] points;")
        print(f"  {'':<14}shuffling the microstructure pair costs {m_[0]:+.2f} "
              f"[{m_[1]:+.2f},{m_[2]:+.2f}] points.")
    print()
    print("  Read the group rows, not the single-feature rows, for the decision:")
    print("  the trio and the pair are correlated, and single-feature shuffles")
    print("  share their joint credit unpredictably. If the microstructure pair's")
    print("  interval sits clear of zero at a size comparable to the trio's, it is")
    print("  pulling real weight and basis is worth building. If it is near zero,")
    print("  the skill is the volatility features and basis drops in priority.")
    print("  No threshold was set in advance for 'comparable', so this is read,")
    print("  not gated.")
    print()
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    main()
