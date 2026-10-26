"""The tail classifier: is this episode likely to be violent?

    .venv/bin/python research/dislocation_model/tail_classifier.py 2>&1 \
        | tee research/dislocation_model/logs/tail_classifier.log

THE QUESTION. The envelope registry handles the bulk of the distribution;
nothing has worked on the extreme decile. This is the "complex model" test,
aimed at the one place complexity is supposed to pay: can a classifier flag the
episodes whose spread makes an outsized move, and does a gradient-boosted
classifier beat a logistic one at it?

THE TARGET -- A MAGNITUDE TARGET. Different in kind from the envelope quantiles
(how far, as a distribution) and from the separately planned direction target
(which way). Binary, per horizon k:

    violent_k = (up_k > p90 of up_k)  OR  (down_k > p90 of down_k)

up_k / down_k are the largest upward / downward moves of the spread from its
entry level within k bars, in entry sigma, UNCLAMPED, from 1-minute closes --
the same running maxima as MAE/MFE but NOT sign-folded. MAE and MFE are those
two excursions relabelled by the direction of the dislocation (MFE = the one
toward mu). The brief asks for "either excursion above its own 90th
percentile" AND "no direction fold"; the unfolded pair satisfies both, and is
the reading used: each SIDE of the market (up, down) is held to its own
threshold, so violence is scored symmetrically and the entry sign plays no
part in the label. The unfold is asserted exactly on the 30-minute grid, where
up and down can be read straight off the raw outcome path.

THRESHOLDS come from TRAIN rows only, per horizon and side, so nothing about
val or held out leaks into the label. With two sides the base rate is near 20%,
not 10%; it is printed per block, since held-out drift moves it.

POPULATION AND SPLIT. The matched 53,757-episode set (1-minute data spans the
window), harness.Split unchanged: train < 2026-05-01, val, held out >= CUT
2026-07-18, touched once. Day-clustered intervals throughout.

FEATURES -- the current confirmed set only: vratio, vol_slope, sandwich,
off_mark, and the volatility level. The registry matches the volatility column
to the direction (vol_48_1m for MAE, vol_48 for MFE); this target spans BOTH
directions, so it gets BOTH confirmed columns, vol_48 and vol_48_1m -- six in
all. That is the direction-matched set carried to a two-sided target, not a
new feature. market_vol is not used (not in the confirmed set for this scope).

THE MODELS, side by side, identical inputs:
  LOGISTIC  sklearn LogisticRegression, features standardised on train, fit on
            train. Default L2 (C=1.0): negligible shrinkage at n=17,000+ on six
            standardised columns, and it keeps the solver stable under the
            vol_48 / vol_48_1m collinearity (Spearman 0.87). Nothing to tune, so
            val is unused.
  GBDT      harness.fit_predict(classify=True): HistGradientBoostingClassifier
            with harness.TREE, iteration count chosen on val by AUC. The
            project's existing tree-classification machinery, unmodified.

RIGOUR, the project's classification bar (harness.passes), per cell:
  1. held-out AUC > GATE_AUC = 0.55 (reused, not re-derived);
  2. its day-clustered 95% CI lower bound > 0.50;
  3. AUC above the WHOLE permutation null -- harness.permutation_null, 15
     row-shuffles and 15 whole-day shuffles of the fit-block labels, the same
     pipeline refitted identically each time (the logistic model through the
     null's `fitter` hook, so both models face the same shuffles).
Also printed: sign(z_entry) alone, as harness asks of any unfolded target. The
label does not depend on the sign by construction, so it should sit near 0.5;
if it does not, the sides behave differently by entry direction and that is
reported, not hidden.

THE RULE, fixed before the run. Five horizons x two models = 10 cells.
  A model CLEARS if it passes all three conditions at 3 or more of the 5
  horizons. Gap filled: the brief says "if either model clears the gate"
  without saying across how many horizons; majority-of-horizons is the bar
  this project has used for every multi-horizon decision, and a single
  passing horizon is reported but not acted on.
  Either model clears -> name it (both, if both); building the tail-specific
      quantile refinement for the flagged subset is the NEXT prompt.
  Neither clears -> a clean negative: the tail problem stays unsolved.
  "Does complexity help" is answered beside the gate, not by it: the paired
  held-out AUC difference GBDT - logistic per horizon, day-clustered.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

import harness
import paths
from envelope import (HLABEL, HORIZONS, HO_BOUNDARY, assert_1m_dominates,
                      build_targets_1m, build_targets_30m, scan_1m_coverage,
                      select_1m_subset)

TAIL_Q = 0.90
FEATURES = ("vol_48", "vol_48_1m", "vratio", "vol_slope", "sandwich", "off_mark")


def unfold(T, s, k):
    """(up, down) from sign-folded MAE/MFE. move = -(Y - e) * s, so for s = +1
    MFE is the largest DOWNWARD move and MAE the largest UPWARD one; s = -1
    swaps them."""
    mae, mfe = T[("MAE", k)], T[("MFE", k)]
    return np.where(s > 0, mae, mfe), np.where(s > 0, mfe, mae)


def logit_model(X, y, sp):
    """The logistic classifier, fitted on train with train standardisation.
    Returns (model, mu, sd); score new rows as model.decision_function((X-mu)/sd)."""
    X = np.asarray(X, float)
    y = np.asarray(y)
    mu = X[sp.train].mean(0)
    sd = X[sp.train].std(0)
    sd[sd == 0] = 1.0
    m = LogisticRegression(C=1.0, max_iter=2000).fit((X[sp.train] - mu) / sd, y[sp.train])
    return m, mu, sd


def fit_logit(X, y, sp, seed=0):
    """Logistic baseline with harness.fit_predict's contract: fit on train,
    predict held out once, return (AUC, held-out scores, None)."""
    m, mu, sd = logit_model(X, y, sp)
    pred = m.decision_function((np.asarray(X, float)[sp.test] - mu) / sd)
    return roc_auc_score(np.asarray(y)[sp.test], pred), pred, None


def paired_auc_diff(sp, a, b, y_test):
    """AUC(a) - AUC(b) on identical held-out rows and day resamples."""
    pt = roc_auc_score(y_test, a) - roc_auc_score(y_test, b)
    d = []
    for ix in sp.boot:
        yi = y_test[ix]
        if yi.min() == yi.max():
            continue
        d.append(roc_auc_score(yi, a[ix]) - roc_auc_score(yi, b[ix]))
    return float(pt), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def setup(t0, title):
    """Population, features, split, targets and labels, with every check.
    Shared by every stage so all of them score the identical labels."""
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    names = [str(x) for x in f["names"]]
    X5 = f["X"].astype(np.float64)

    print("=" * 112)
    print(title)
    print("=" * 112)
    print("  A MAGNITUDE TARGET: does the spread make an outsized move EITHER way.")
    print("  Not the envelope quantiles (how far, as a distribution) and not the")
    print("  direction target (which way). Not sign-folded: up and down are each held")
    print("  to their own train 90th percentile, and either crossing it is 'violent'.")
    print()
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], rows):
        raise SystemExit("[TAIL] vol48_1m.npz rows differ from the population.")
    cols = {n: X5[rows, names.index(n)] for n in names}
    cols["vol_48_1m"] = v48["vol_48_1m"]
    X = np.column_stack([cols[n] for n in FEATURES])
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    sp = harness.Split(day, e)
    print(f"  population: the matched {len(rows):,}-episode set")
    print(f"  {sp.describe()}")
    print(f"  features: {', '.join(FEATURES)}")
    print()

    # ---- targets, with the unfold asserted on the 30-minute grid ----
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    worst = 0.0
    for k in HORIZONS:
        up30, dn30 = unfold(T30, s, k)
        seg = Y[rows][:, 1:k + 1] - e[:, None]
        worst = max(worst, float(np.max(np.abs(up30 - seg.max(1)))),
                    float(np.max(np.abs(dn30 - (-seg).max(1)))))
    print(f"  unfold check: up/down from MAE/MFE vs read straight off the raw 30m path,"
          f" max diff {worst:.1e}")
    if worst > 1e-12:
        raise SystemExit("[TAIL] the unfold does not recover up/down moves.")

    labels, thr = {}, {}
    print()
    print(f"  {'h':<6}{'up p90':>9}{'down p90':>10}{'train':>9}{'val':>8}{'held out':>10}"
          f"{'HO1':>8}{'HO2':>8}   base rate, share violent")
    h1 = day[sp.test] < HO_BOUNDARY
    for k in HORIZONS:
        up, dn = unfold(T1M, s, k)
        tu = float(np.quantile(up[sp.train], TAIL_Q))
        td = float(np.quantile(dn[sp.train], TAIL_Q))
        lab = ((up > tu) | (dn > td)).astype(int)
        labels[k], thr[k] = lab, (tu, td)
        yt = lab[sp.test]
        print(f"  {HLABEL[k]:<6}{tu:>9.3f}{td:>10.3f}{lab[sp.train].mean():>9.3f}"
              f"{lab[sp.val].mean():>8.3f}{yt.mean():>10.3f}{yt[h1].mean():>8.3f}"
              f"{yt[~h1].mean():>8.3f}")
    print(f"  [{time.time()-t0:.0f}s]")
    print()
    return dict(Y=Y, meta=meta, rows=rows, X=X, day=day, e=e, s=s, sp=sp,
                T1M=T1M, T30=T30, labels=labels, thr=thr, h1=h1, X5r=X5[rows],
                names=names, v48_1m=v48["vol_48_1m"])


def main():
    t0 = time.time()
    S = setup(t0, "TAIL CLASSIFIER -- is this episode likely to be violent?")
    X, sp, s, labels = S["X"], S["sp"], S["s"], S["labels"]

    # ---- the ten cells ----
    print("=" * 112)
    print("HELD-OUT AUC -- gate: > 0.55, CI lower > 0.50, above the whole permutation null")
    print("=" * 112)
    res = {}
    for k in HORIZONS:
        y = labels[k]
        yt = y[sp.test]
        sign_auc = roc_auc_score(yt, s[sp.test])
        for mn in ("logistic", "GBDT"):
            if mn == "logistic":
                score, pred, it = fit_logit(X, y, sp)
                null = harness.permutation_null(X, y, sp, True, fitter=fit_logit)
            else:
                score, pred, it = harness.fit_predict(X, y, sp, True)
                null = harness.permutation_null(X, y, sp, True)
            lo, hi = harness.ci(sp, pred, yt, True)
            nmax = max(null["row"].max(), null["day"].max())
            hit = harness.passes(score, lo, True, null)
            res[(mn, k)] = dict(score=score, lo=lo, hi=hi, pred=pred, nmax=nmax,
                                nday=null["day"], nrow=null["row"], hit=hit, it=it)
            print(f"  {HLABEL[k]:<5}{mn:<10} AUC {score:.4f} [{lo:.4f},{hi:.4f}]  null max "
                  f"{nmax:.4f} (day-shuffle {null['day'].min():.4f}-{null['day'].max():.4f})"
                  f"{'' if it is None else f'  iters {it}'}  "
                  f"{'PASS' if hit else 'fail'}   [{time.time()-t0:.0f}s]", flush=True)
        res[("sign", k)] = sign_auc
        print(f"  {HLABEL[k]:<5}{'sign only':<10} AUC {sign_auc:.4f}  (diagnostic; label is "
              f"sign-free by construction)")
    print()

    print("=" * 112)
    print("DOES COMPLEXITY HELP? -- paired held-out AUC, GBDT - logistic, day-clustered")
    print("=" * 112)
    for k in HORIZONS:
        yt = labels[k][sp.test]
        d = paired_auc_diff(sp, res[("GBDT", k)]["pred"], res[("logistic", k)]["pred"], yt)
        res[("diff", k)] = d
        tag = "GBDT better" if d[1] > 0 else "logistic better" if d[2] < 0 else "no difference"
        print(f"  {HLABEL[k]:<6}{d[0]:+.4f} [{d[1]:+.4f},{d[2]:+.4f}]  {tag}")
    print()

    print("=" * 112)
    print("DECISION -- rule fixed in the module docstring before the run")
    print("=" * 112)
    clears = []
    for mn in ("logistic", "GBDT"):
        n = sum(res[(mn, k)]["hit"] for k in HORIZONS)
        passed = [HLABEL[k] for k in HORIZONS if res[(mn, k)]["hit"]]
        ok = n >= 3
        if ok:
            clears.append(mn)
        print(f"  {mn:<9} passes at {n} of 5 horizons"
              f"{' (' + ', '.join(passed) + ')' if passed else ''} -> "
              f"{'CLEARS' if ok else 'does not clear'}")
    if clears:
        print(f"  VERDICT: {' and '.join(clears)} CLEARS. Next prompt: the tail-specific "
              f"quantile refinement for the flagged subset.")
    else:
        print("  VERDICT: NEITHER CLEARS. A clean negative -- the tail problem stays "
              "unsolved.")
    print("  Held out touched once, here. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------ TAIL-REFINE, step 1
LOGIT_PUBLISHED = {1: 0.7150, 2: 0.7125, 4: 0.7086, 10: 0.7063, 20: 0.7144}  # TAIL-CLASSIFIER
N_SHUF = 10


def incremental():
    """TAIL-REFINE step 1: does the classifier know anything the volatility
    columns and the quantile registry do not already know?

    THE WORRY. The quantile models already condition on recent volatility and
    still could not identify the extreme decile. If the classifier's 0.71 is
    mostly vol_48, a tail refinement built on it restates known information.

    FOUR SCORES on the identical held-out rows and the same "violent" labels,
    at all five horizons:
      1. the logistic classifier, refitted (deterministic; must reproduce the
         published TAIL-CLASSIFIER AUCs to 4 decimals);
      2. vol_48 alone and vol_48_1m alone, as raw scores;
      3. the registry's own predicted upper quantile, Linear QR and CQR, as raw
         scores;
      4. the logistic classifier's permutation importance per feature.

    GAPS FILLED, stated before the run:
      - The registry predicts q5/q25/q50/q75/q95; it has no 90th percentile.
        q95 is used: the nearest quantile it actually fits. Interpolating a q90
        would add an assumption about the shape between q75 and q95.
      - The registry forecasts MAE and MFE separately; the target is either
        side. The score is the LARGER of the predicted MAE q95 and MFE q95:
        the episode's own predicted worst-side upper tail.
      - Registry predictions are the cached ones, fingerprint-checked: MAE on
        vol_48_1m (match1m_mae_vol1m), MFE on vol_48 (match1m). market_vol was
        adopted for Linear QR / MAE but that rebuild has not been done, so it
        is not in the cache and not in this comparison.
      - "Beats both #2 and #3" = beats ALL FOUR comparators (vol_48,
        vol_48_1m, Linear QR q95, CQR q95) at that horizon, each by a paired
        day-clustered AUC difference whose interval clears zero.

    THE RULE, fixed before the run: NEW TAIL INFORMATION if the classifier
    beats all four comparators at a majority (3 or more) of the 5 horizons ->
    Step 2 is justified. Otherwise: the volatility signal restated. Report and
    stop; the decile-10 problem stays open.

    IMPORTANCE: each feature's column shuffled across held-out rows
    (N_SHUF=10 shuffles), the drop in held-out AUC; day-clustered interval.
    Also jointly: the two volatility columns, and the other four.

    CARRY-FORWARD: the classifier's mean predicted probability on held out,
    beside the train and held-out violent base rates, overall and by half.
    """
    from envelope import FP_KEY, cache_fingerprint, flat_targets
    from vol1m import MAE_CACHE
    t0 = time.time()
    S = setup(t0, "TAIL-REFINE step 1 -- does the classifier know anything new?")
    X, sp, labels, rows, h1 = S["X"], S["sp"], S["labels"], S["rows"], S["h1"]
    T1M, T30 = S["T1M"], S["T30"]

    # ---- the registry caches, fingerprint-checked ----
    c_mfe = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    c_mae = np.load(paths.envelope_preds(MAE_CACHE), allow_pickle=False)
    X_mae = S["X5r"].copy()
    X_mae[:, S["names"].index("vol_48")] = S["v48_1m"]
    fp_mfe = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), S["X5r"])
    fp_mae = cache_fingerprint([rows], flat_targets(
        {("MAE", k): T1M[("MAE", k)] for k in HORIZONS}), X_mae)
    if str(c_mfe[FP_KEY]) != fp_mfe or str(c_mae[FP_KEY]) != fp_mae:
        raise SystemExit("[TAIL] a registry cache fingerprint does not match.")
    print(f"  registry caches: MFE match1m {fp_mfe[:12]}, MAE {MAE_CACHE} {fp_mae[:12]}"
          f" -- both match")
    print()

    iv, iv1 = FEATURES.index("vol_48"), FEATURES.index("vol_48_1m")
    rng = np.random.default_rng(20261012)
    verdict_h, imp_all = {}, {}
    for k in HORIZONS:
        y = labels[k]
        yt = y[sp.test]
        m, mu, sd = logit_model(X, y, sp)
        Zte = (X[sp.test] - mu) / sd
        clf = m.decision_function(Zte)
        auc = roc_auc_score(yt, clf)
        if round(auc, 4) != LOGIT_PUBLISHED[k]:
            raise SystemExit(f"[TAIL] logistic {HLABEL[k]} AUC {auc:.4f} does not "
                             f"reproduce TAIL-CLASSIFIER {LOGIT_PUBLISHED[k]:.4f}.")
        comps = {
            "vol_48": X[sp.test, iv],
            "vol_48_1m": X[sp.test, iv1],
            "Linear QR q95": np.maximum(c_mae[f"1m|MAE|Linear QR|{k}"][:, 4],
                                        c_mfe[f"1m|MFE|Linear QR|{k}"][:, 4]),
            "CQR q95": np.maximum(c_mae[f"1m|MAE|CQR|{k}"][:, 4],
                                  c_mfe[f"1m|MFE|CQR|{k}"][:, 4]),
        }
        print("=" * 112)
        print(f"{HLABEL[k]} -- held-out AUC for 'violent', and classifier minus each "
              f"comparator (paired, day-clustered)")
        print("=" * 112)
        lo, hi = harness.ci(sp, clf, yt, True)
        print(f"  {'logistic classifier':<22}AUC {auc:.4f} [{lo:.4f},{hi:.4f}]  "
              f"(reproduces TAIL-CLASSIFIER)")
        beats = []
        for nm, sc in comps.items():
            a = roc_auc_score(yt, sc)
            alo, ahi = harness.ci(sp, sc, yt, True)
            d = paired_auc_diff(sp, clf, sc, yt)
            b = d[1] > 0
            beats.append(b)
            print(f"  {nm:<22}AUC {a:.4f} [{alo:.4f},{ahi:.4f}]   classifier - this "
                  f"{d[0]:+.4f} [{d[1]:+.4f},{d[2]:+.4f}]  {'BEATS' if b else 'does not beat'}")
        verdict_h[k] = all(beats)
        print(f"  -> classifier beats all four: {'YES' if verdict_h[k] else 'no'}")

        # ---- importance ----
        sets = [(n, [j]) for j, n in enumerate(FEATURES)]
        sets += [("vol pair (vol_48 + vol_48_1m)", [iv, iv1]),
                 ("other four", [j for j in range(len(FEATURES)) if j not in (iv, iv1)])]
        base_b = np.array([roc_auc_score(yt[ix], clf[ix]) for ix in sp.boot])
        print(f"  logistic permutation importance, AUC points lost when shuffled "
              f"({N_SHUF} shuffles, day-clustered):")
        imp_all[k] = {}
        for nm, cols in sets:
            perm_b = np.zeros(len(sp.boot))
            pt = 0.0
            for _ in range(N_SHUF):
                Zp = Zte.copy()
                Zp[:, cols] = Zte[rng.permutation(len(yt))][:, cols]
                sp_ = m.decision_function(Zp)
                pt += auc - roc_auc_score(yt, sp_)
                perm_b += np.array([roc_auc_score(yt[ix], sp_[ix]) for ix in sp.boot])
            pt /= N_SHUF
            drop_b = base_b - perm_b / N_SHUF
            ilo, ihi = float(np.percentile(drop_b, 2.5)), float(np.percentile(drop_b, 97.5))
            imp_all[k][nm] = (pt, ilo, ihi)
            print(f"    {nm:<32}{pt:+.4f} [{ilo:+.4f},{ihi:+.4f}]")

        # ---- calibration in the large ----
        p = 1.0 / (1.0 + np.exp(-clf))
        print(f"  mean predicted probability, held out {p.mean():.3f} (HO1 {p[h1].mean():.3f},"
              f" HO2 {p[~h1].mean():.3f});  actual: train {y[sp.train].mean():.3f}, held out"
              f" {yt.mean():.3f} (HO1 {yt[h1].mean():.3f}, HO2 {yt[~h1].mean():.3f})")
        print(f"  [{time.time()-t0:.0f}s]", flush=True)
        print()

    print("=" * 112)
    print("DECISION -- rule fixed in incremental()' docstring before the run")
    print("=" * 112)
    n = sum(verdict_h.values())
    print(f"  classifier beats all four comparators at {n} of 5 horizons "
          f"({', '.join(HLABEL[k] for k in HORIZONS if verdict_h[k]) or 'none'}); need 3")
    if n >= 3:
        print("  VERDICT: NEW TAIL INFORMATION -- Step 2 (the flagged-subset quantile")
        print("  model) is justified. Not built in this run.")
    else:
        print("  VERDICT: THE VOLATILITY SIGNAL RESTATED. Stop. The decile-10 problem")
        print("  stays open.")
    print("  Held-out rows have been scored before (TAIL-CLASSIFIER); the paired")
    print("  differences are the new measurement. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------ TAIL-REFINE, step 2
FLAG_SHARE = 0.20          # flag the top 20% by classifier score; cut-off set on train


def refine():
    """TAIL-REFINE step 2: a Linear QR fitted on FLAGGED episodes only.

    Run because step 1 passed (4 of 5 horizons). Design choices made by the
    user before this was written: flag = top 20% by classifier score, the cut-off
    set on TRAIN; deciles = predicted-magnitude deciles (the counted slice family
    in envelope.py: deciles of the model's own predicted median over held-out
    rows).

    FLAG. Per horizon k, the logistic classifier from step 1 (deterministic
    refit) scores every row; the cut-off is the 80th percentile of its TRAIN
    scores; a row is flagged if its score is above it. The flagged share on val
    and held out is printed, not forced to 20%.

    THE SUBSET MODEL. Per direction and horizon, Linear QR with the registry's
    own features for that direction (MAE: vol_48_1m set; MFE: vol_48 set),
    fitted on FLAGGED TRAIN rows only, standardised on them, all five quantiles
    (q75 and q95 are the ones judged). q-axis enforcement only: flags differ by
    horizon, so the horizon pass has no common rows to run on. The registry's
    horizon pass moved 0.002% of Linear QR's predictions, so the comparison is
    not materially affected; stated rather than hidden.

    REFINED = the subset model's prediction on flagged held-out rows, the
    registry Linear QR's everywhere else. Unflagged rows are therefore identical
    in both, and every difference comes from the flagged rows.

    MEASURES, paired, day-clustered:
      on FLAGGED held-out rows: coverage at q75 / q95, calibration gap (all five
        levels, pp), skill against the cached Climatology;
      by predicted-magnitude decile over ALL held-out rows, the groups fixed by
        the REGISTRY Linear QR's predicted median so both versions are sliced
        identically: q75 / q95 coverage and the flagged share per decile. The
        q95 miss rate over its nominal 5% is reported as "x too narrow".

    THE RULE, fixed before the run, per direction and horizon (10 cells):
      DECILE 10 FIXED  in decile 10, refined |q95 coverage - 0.95| is smaller
                       than the registry's, paired interval clearing zero, AND on
                       the flagged rows neither the gap nor skill is
                       significantly worse
    Per direction: WORKS if fixed at 3 or more of 5 horizons; otherwise not.
    The "1.84x" baseline the brief cites could not be located; the registry's
    own decile-10 numbers printed here are the baseline instead.
    """
    from envelope import (FP_KEY, QUANTILES, cache_fingerprint, day_boot, deciles,
                          fit_linear, flat_targets, gap_ci, gap_paired_ci, skill_ci,
                          LINEAR_FALLBACKS)
    from vol1m import MAE_CACHE, paired_skill_ci
    t0 = time.time()
    S = setup(t0, "TAIL-REFINE step 2 -- a Linear QR on flagged episodes only")
    X, sp, labels, rows, h1 = S["X"], S["sp"], S["labels"], S["rows"], S["h1"]
    T1M, T30 = S["T1M"], S["T30"]
    c_mfe = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    c_mae = np.load(paths.envelope_preds(MAE_CACHE), allow_pickle=False)
    X_mae = S["X5r"].copy()
    X_mae[:, S["names"].index("vol_48")] = S["v48_1m"]
    fp_mfe = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), S["X5r"])
    fp_mae = cache_fingerprint([rows], flat_targets(
        {("MAE", k): T1M[("MAE", k)] for k in HORIZONS}), X_mae)
    if str(c_mfe[FP_KEY]) != fp_mfe or str(c_mae[FP_KEY]) != fp_mae:
        raise SystemExit("[TAIL] a registry cache fingerprint does not match.")
    print(f"  registry caches: MFE match1m {fp_mfe[:12]}, MAE {MAE_CACHE} {fp_mae[:12]}"
          f" -- both match")
    base = {"MFE": (S["X5r"], c_mfe), "MAE": (X_mae, c_mae)}
    j75, j95 = QUANTILES.index(0.75), QUANTILES.index(0.95)
    dte = S["day"][sp.test]
    print()

    out = {}
    for k in HORIZONS:
        y_lab = labels[k]
        m, mu, sd = logit_model(X, y_lab, sp)
        score = m.decision_function((X - mu) / sd)
        if round(roc_auc_score(y_lab[sp.test], score[sp.test]), 4) != LOGIT_PUBLISHED[k]:
            raise SystemExit(f"[TAIL] logistic {HLABEL[k]} does not reproduce TAIL-CLASSIFIER.")
        cut = float(np.quantile(score[sp.train], 1 - FLAG_SHARE))
        flag = score > cut
        ft = flag[sp.test]
        print("=" * 112)
        print(f"{HLABEL[k]} -- flagged: train {flag[sp.train].mean():.3f}, val "
              f"{flag[sp.val].mean():.3f}, held out {ft.mean():.3f} ({int(ft.sum()):,} rows);"
              f"  violent among flagged held out {y_lab[sp.test][ft].mean():.3f} "
              f"vs {y_lab[sp.test][~ft].mean():.3f} unflagged")
        print("=" * 112)
        bflag = day_boot(dte[ft])
        bfull = day_boot(dte)
        for d in ("MFE", "MAE"):
            Xb, cb = base[d]
            tr = sp.train & flag
            mu_ = Xb[tr].mean(0)
            sd_ = Xb[tr].std(0)
            sd_[sd_ == 0] = 1.0
            ctx = dict(train=tr, Ztr=(Xb[tr] - mu_) / sd_,
                       Zte=(Xb[sp.test] - mu_) / sd_, n_test=sp.n_test)
            y = T1M[(d, k)]
            sub = np.maximum.accumulate(
                fit_linear(ctx, y, f"1m/{d}/{HLABEL[k]}/flagged"), axis=1)
            reg = cb[f"1m|{d}|Linear QR|{k}"]
            clim = cb[f"1m|{d}|Climatology|{k}"]
            refined = reg.copy()
            refined[ft] = sub[ft]
            yt = y[sp.test]

            # ---- on the flagged rows ----
            yf, rf, sf, cf = yt[ft], reg[ft], sub[ft], clim[ft]
            cov = lambda p_, yy, j: float((yy <= p_[:, j]).mean())
            dg = gap_paired_ci(yf, rf, yf, sf, bflag)
            ds = paired_skill_ci(yf, rf, sf, cf, bflag)
            g_worse = dg[1] > 0
            s_worse = ds[2] < 0
            print(f"  {d} flagged rows: q75 cover registry {cov(rf, yf, j75):.3f} -> subset "
                  f"{cov(sf, yf, j75):.3f};  q95 cover {cov(rf, yf, j95):.3f} -> "
                  f"{cov(sf, yf, j95):.3f}")
            print(f"  {'':<4}gap {gap_ci(yf, rf, bflag)[0]:.2f} -> {gap_ci(yf, sf, bflag)[0]:.2f}"
                  f" pp, diff {dg[0]:+.3f} [{dg[1]:+.3f},{dg[2]:+.3f}]"
                  f"{'  WORSE' if g_worse else ''};  skill {skill_ci(yf, rf, cf, bflag)[0]:+.2f}"
                  f" -> {skill_ci(yf, sf, cf, bflag)[0]:+.2f}, diff {ds[0]:+.3f} "
                  f"[{ds[1]:+.3f},{ds[2]:+.3f}]{'  WORSE' if s_worse else ''}")

            # ---- by predicted-magnitude decile, all held-out rows ----
            grp, ng = deciles(reg[:, QUANTILES.index(0.5)])
            print(f"  {'':<4}{'decile':<8}{'rows':>6}{'flagged':>9}{'q75 reg':>9}{'q75 ref':>9}"
                  f"{'q95 reg':>9}{'q95 ref':>9}{'x narrow reg':>14}{'x narrow ref':>14}")
            for g in range(ng):
                mg = grp == g
                c75r, c75n = cov(reg[mg], yt[mg], j75), cov(refined[mg], yt[mg], j75)
                c95r, c95n = cov(reg[mg], yt[mg], j95), cov(refined[mg], yt[mg], j95)
                print(f"  {'':<4}{g+1:<8}{int(mg.sum()):>6}{ft[mg].mean():>9.3f}{c75r:>9.3f}"
                      f"{c75n:>9.3f}{c95r:>9.3f}{c95n:>9.3f}{(1-c95r)/0.05:>13.2f}x"
                      f"{(1-c95n)/0.05:>13.2f}x")
            m10 = grp == ng - 1
            i10 = np.flatnonzero(m10)
            b10 = day_boot(dte[m10])
            hr = (yt[i10] <= reg[i10, j95]).astype(float)
            hn = (yt[i10] <= refined[i10, j95]).astype(float)
            dev = lambda h, ix: abs(h[ix].mean() - 0.95)
            pt = dev(hn, slice(None)) - dev(hr, slice(None))
            draws = np.array([dev(hn, ix) - dev(hr, ix) for ix in b10])
            lo, hi = float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
            fixed = hi < 0 and not g_worse and not s_worse
            out[(d, k)] = fixed
            print(f"  {'':<4}decile 10, |q95 cover - 0.95|: registry {dev(hr, slice(None)):.4f},"
                  f" refined {dev(hn, slice(None)):.4f}, diff {pt:+.4f} [{lo:+.4f},{hi:+.4f}]"
                  f"  -> {'FIXED' if fixed else 'not fixed'}   [{time.time()-t0:.0f}s]",
                  flush=True)
        print()

    print("=" * 112)
    print("DECISION -- rule fixed in refine()' docstring before the run")
    print("=" * 112)
    for d in ("MFE", "MAE"):
        n = sum(out[(d, k)] for k in HORIZONS)
        hz = [HLABEL[k] for k in HORIZONS if out[(d, k)]]
        print(f"  {d}: decile 10 fixed at {n} of 5 horizons"
              f"{' (' + ', '.join(hz) + ')' if hz else ''} -> "
              f"{'WORKS' if n >= 3 else 'does not work'}")
    print(f"  Linear QR LP fallbacks (alpha > 0): {len(LINEAR_FALLBACKS)}")
    print("  Held-out rows have been scored before; the paired differences are the")
    print("  new measurement. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("classify", "incremental", "refine"),
                    default="classify",
                    help="classify = TAIL-CLASSIFIER. incremental = TAIL-REFINE step 1, "
                         "the classifier against vol alone and the registry's q95. "
                         "refine = TAIL-REFINE step 2, Linear QR on flagged episodes.")
    stg = ap.parse_args().stage
    if stg == "incremental":
        incremental()
    elif stg == "refine":
        refine()
    else:
        main()
