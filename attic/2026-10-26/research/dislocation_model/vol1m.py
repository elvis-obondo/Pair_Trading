"""Sharpen vol_48: the same quantity, estimated from 1-minute data.

    .venv/bin/python research/dislocation_model/vol1m.py 2>&1 \
        | tee research/dislocation_model/logs/vol1m.log

ONE CHANGE. vol_48 is the mean absolute 30-minute change of the spread over the
last 48 bars -- 24 hours, 48 observations -- with the spread built under the
entry bar's FROZEN geometry (entry beta, alpha, mu) and divided by the entry
sigma. Recomputed from disloc.npz's windows it reproduces envfeat's column to
5.8e-08. vol_48_1m is the identical quantity at 1-minute resolution: the same
frozen spread, the same sigma, the same 24 hours ending at the entry bar's
close, the same absolute-not-squared convention -- 1,440 observations instead
of 48. Only the resolution changes, so this tests resolution and nothing else.
vratio, vol_slope, sandwich and off_mark are untouched.

THE WINDOW, IN 1-MINUTE LABELS. Bars are labelled by OPEN time; the 30-minute
bar labelled T closes at the 1-minute bar labelled T+29. The entry bar is
labelled entry_time, so its close is the minute labelled entry+29, and bar
i-48's close is the minute labelled entry+29-1440. The path runs over those
1,441 minutes and yields 1,440 one-minute changes.

CORRECTNESS, carried over from every 1-minute build:
  1. NO INFORMATION PAST THE ENTRY BAR. The last minute read is entry+29, the
     entry bar's own close, which is Y[:, 0]; the maximum minute offset
     touched relative to entry_time is asserted to be exactly +29.
  2. REPRODUCTION. The 1-minute path at every 30th minute must reproduce the
     stored 30-minute window W[:, -49:] at all 49 marks, to the stored
     float32 window's own precision -- so the 1-minute feature is provably the
     same series at a finer grain, not a different one.
  3. THE OLD FEATURE FROM THE NEW PATH. vol_48 recomputed from those 49 marks
     must equal envfeat's vol_48.
  4. MISSING MINUTES are counted per episode and never forward-filled. A
     one-minute change is used only when BOTH of its minutes traded; a change
     across a gap is excluded rather than credited as one big move.

THE COMPARISON. QTREE only, the two cells of the importance check: 1-minute
target, ALL, MFE 10h and MAE 10h, the matched 53,757-episode set, the usual
split. Old = the cached QTREE (fingerprint-verified). New = QTREE refitted with
vol_48 replaced by vol_48_1m, all five horizons, the same two-pass enforcement.
Skill and calibration gap are compared PAIRED -- identical rows and day
resamples, only the feature changing -- so the old-versus-new difference is a
within-row contrast, the new measurement here. Levels are a later look at
already-scored rows.

THE DECISION RULE, FIXED BEFORE THE NUMBERS:
  MEANINGFUL  in at least one of the two cells, the paired skill difference
              (new - old) has a 95% interval entirely above zero, OR the paired
              gap difference has one entirely below zero; AND in neither cell
              is either measure significantly worse.
  MARGINAL    anything else. Say so plainly and stop.
No size threshold was given, so the rule is significance-based and the
magnitudes are printed beside it for the reader to weigh.

AN EXPECTED DIFFERENCE, stated so it is not mistaken for a bug. 1-minute
changes carry microstructure noise -- bid-ask bounce -- that 30-minute changes
average away, so vol_48_1m is not vol_48 scaled by any constant and partly
measures how noisy the spread's prints are. A tree is invariant to monotone
rescaling, so scale does not matter; whether the bounce component helps or
hurts is part of what the comparison measures.
"""
import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import harness
import paths
from envelope import (FP_KEY, HLABEL, HORIZONS, REGISTRY_UNTIL_2026_10_12,
                      REP_ULPS, ULP_FLOOR,
                      load_or_fit, save_cache,
                      _pinball_rows, _window, assert_1m_dominates, build_context,
                      build_targets_1m, build_targets_30m, cache_fingerprint,
                      day_boot, enforce_two_pass, fit_qtree, flat_targets,
                      gap_ci, gap_paired_ci, load_1m_series, scan_1m_coverage,
                      select_1m_subset, skill_ci)
from importance import importance, qtree_predict

NMIN = 1440                 # 24 hours, the window vol_48 covers
MARK = 30                   # minutes per 30m bar
CELLS = (("MFE", 20), ("MAE", 20))
CHUNK = 5000
SEED = 20261011


FAST_MIN, SLOW_MIN = 480, 960      # vol_slope's 8h and 16h windows, in minutes
FAST_BARS, SLOW_BARS = 16, 32      # the same windows in 30-minute bars


def trailing_features(meta, rows, W, vol_old, slope_old=None):
    """vol_48_1m and vol_slope_1m for every row, from ONE set of 1-minute paths.

    Both features read the same trailing 1,441 minutes, ending at the entry
    bar's close (minute entry+29): vol_48 covers 24 hours, and vol_slope's 8h +
    16h windows tile the same 24 hours exactly. So one path per episode feeds
    both, and every correctness check runs once for both.

    Built in chunks so the 1,441-minute paths (620MB for all rows) never sit in
    memory at once.

    vol_slope_1m keeps vol_slope's statistic exactly: the population standard
    deviation (numpy's default, ddof=0, mean-centred) of the step changes over
    the last 8 hours, divided by the same over the 16 hours before, with the
    denominator clipped at 1e-12. Only the resolution changes: 480 and 960
    one-minute steps instead of 16 and 32 thirty-minute steps. Steps across a
    missing minute are excluded, never filled.
    """
    sub = meta.iloc[rows]
    series = load_1m_series(sorted(set(sub.ticker_a) | set(sub.ticker_b)), True)
    entry = pd.to_datetime(meta.entry_time).to_numpy().astype("datetime64[m]")
    be, al = meta.beta.to_numpy(float), meta.alpha.to_numpy(float)
    mu, sg = meta.mu.to_numpy(float), meta.sigma.to_numpy(float)
    ta, tb = meta.ticker_a.to_numpy(), meta.ticker_b.to_numpy()
    n = len(rows)
    out = {k_: np.empty(n) for k_ in ("vol", "half_a", "half_b", "slope",
                                       "slope_a", "slope_b")}
    for k_ in ("nvalid", "nmiss", "nfast", "nslow"):
        out[k_] = np.empty(n, int)
    rep_ratio = rep_err = recomp = recomp_s = 0.0
    max_off = -10**9
    for c0 in range(0, n, CHUNK):
        idx = rows[c0:c0 + CHUNK]
        sl = slice(c0, c0 + len(idx))
        P = np.empty((len(idx), NMIN + 1))
        for j_, i_ in enumerate(idx):
            t0a, aa = series[ta[i_]]
            t0b, ab = series[tb[i_]]
            # the last minute read is entry+29: the entry bar's own close
            start = entry[i_] + np.timedelta64(MARK - 1 - NMIN, "m")
            last_off = int((start + np.timedelta64(NMIN, "m") - entry[i_])
                           / np.timedelta64(1, "m"))
            max_off = max(max_off, last_off)
            va = _window(aa, int((start - t0a) / np.timedelta64(1, "m")), NMIN + 1)
            vb = _window(ab, int((start - t0b) / np.timedelta64(1, "m")), NMIN + 1)
            P[j_] = (va - be[i_] * vb - al[i_] - mu[i_]) / sg[i_]
        # reproduction at the 49 thirty-minute marks, ulp-scaled to W's float32
        marks = P[:, ::MARK]
        ref = W[idx][:, -(NMIN // MARK + 1):].astype(np.float64)
        fin = np.isfinite(marks)
        ulp = np.spacing(np.abs(ref).astype(np.float32)).astype(np.float64)
        tol = np.maximum(REP_ULPS * ulp, ULP_FLOOR)
        if fin.any():
            rep_err = max(rep_err, float(np.max(np.abs(marks - ref)[fin])))
            rep_ratio = max(rep_ratio, float(np.max((np.abs(marks - ref) / tol)[fin])))
        # the OLD features from the new path's marks
        full = fin.all(axis=1)
        if full.any():
            dm = np.diff(marks[full], axis=1)                  # 48 thirty-minute steps
            recomp = max(recomp, float(np.max(np.abs(
                np.abs(dm).mean(1) - vol_old[sl][full]))))
            if slope_old is not None:
                s_re = (dm[:, -FAST_BARS:].std(1)
                        / np.clip(dm[:, -(FAST_BARS + SLOW_BARS):-FAST_BARS].std(1),
                                  1e-12, None))
                recomp_s = max(recomp_s, float(np.max(np.abs(s_re - slope_old[sl][full]))))
        # one-minute steps, only between two traded minutes
        dS = np.diff(P, axis=1)                                # NaN across gaps
        ok = np.isfinite(dS)
        aS = np.where(ok, np.abs(dS), np.nan)
        out["nvalid"][sl] = ok.sum(1)
        out["nmiss"][sl] = (~np.isfinite(P)).sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out["vol"][sl] = np.nanmean(aS, axis=1)
            out["half_a"][sl] = np.nanmean(aS[:, 0::2], axis=1)
            out["half_b"][sl] = np.nanmean(aS[:, 1::2], axis=1)
            fw, sw = dS[:, -FAST_MIN:], dS[:, -(FAST_MIN + SLOW_MIN):-FAST_MIN]
            out["nfast"][sl] = np.isfinite(fw).sum(1)
            out["nslow"][sl] = np.isfinite(sw).sum(1)
            out["slope"][sl] = (np.nanstd(fw, axis=1)
                                / np.clip(np.nanstd(sw, axis=1), 1e-12, None))
            out["slope_a"][sl] = (np.nanstd(fw[:, 0::2], axis=1)
                                  / np.clip(np.nanstd(sw[:, 0::2], axis=1), 1e-12, None))
            out["slope_b"][sl] = (np.nanstd(fw[:, 1::2], axis=1)
                                  / np.clip(np.nanstd(sw[:, 1::2], axis=1), 1e-12, None))
        print(f"  [1m-feat] rows {c0+len(idx):>6,} of {n:,}", flush=True)
    del series
    out.update(rep_ratio=rep_ratio, rep_err=rep_err, recomp=recomp,
               recomp_s=recomp_s, max_off=max_off)
    return out


def paired_skill_ci(y, old, new, clim, boot):
    """(skill_new - skill_old) in skill points = 100 (pin_old - pin_new)/pin_clim."""
    po, pn, pc = _pinball_rows(y, old), _pinball_rows(y, new), _pinball_rows(y, clim)
    pt = 100.0 * (po.mean() - pn.mean()) / pc.mean()
    draws = np.array([100.0 * (po[ix].mean() - pn[ix].mean()) / pc[ix].mean()
                      for ix in boot])
    return float(pt), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def spearman_brown(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    r = float(np.corrcoef(a[m], b[m])[0, 1])
    return r, 2 * r / (1 + r)


def main():
    t0 = time.time()
    z = np.load(paths.DISLOC)
    W = z["windows"]
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    iv = names.index("vol_48")
    day = meta.day.to_numpy()

    print("=" * 112)
    print("SHARPEN vol_48 -- the same 24-hour quantity at 1-minute resolution")
    print("=" * 112)
    cache = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    print(f"  population: the matched {len(rows):,}-episode set (rule B)")
    print()

    # ---- build the feature ----
    print("=" * 112)
    print("BUILD -- vol_48_1m, with the carried-over correctness checks")
    print("=" * 112)
    R = trailing_features(meta, rows, W, X[rows, iv])
    print()
    print(f"  1. max minute offset touched, relative to entry_time: +{R['max_off']} "
          f"(must be +{MARK-1}: the entry bar's own close)")
    if R["max_off"] != MARK - 1:
        raise SystemExit("[VOL1M] ABORT -- the window reads past the entry bar's close.")
    print(f"  2. 1-minute path vs stored 30m window at the 49 marks: max error "
          f"{R['rep_err']:.3e}, {R['rep_ratio']:.3f} of the float32 budget "
          f"(must be < 1)")
    if not R["rep_ratio"] < 1.0:
        raise SystemExit("[VOL1M] ABORT -- the 1-minute path does not reproduce the "
                         "30-minute window. Suspect the T+29 bar-label offset first.")
    print(f"  3. vol_48 recomputed from the new path's marks vs envfeat: max diff "
          f"{R['recomp']:.3e}")
    if not R["recomp"] < 1e-4:
        raise SystemExit("[VOL1M] ABORT -- the old feature does not come back from the "
                         "new path, so the window or normalisation differs.")
    nv, nm = R["nvalid"], R["nmiss"]
    print(f"  4. valid one-minute changes per episode (of {NMIN}): "
          f"min {nv.min()}  p1 {np.percentile(nv,1):.0f}  median {np.median(nv):.0f}")
    print(f"     episodes with the full {NMIN}: {int((nv==NMIN).sum()):,} of {len(rows):,}"
          f"   missing minutes per episode: mean {nm.mean():.2f}  max {nm.max()}")
    print(f"     episodes below {NMIN//2} valid changes: {int((nv < NMIN//2).sum()):,}")
    if (nv == 0).any():
        raise SystemExit(f"[VOL1M] ABORT -- {int((nv==0).sum())} episodes have no valid "
                         f"one-minute change in the window. Not forward-filling them.")
    v_old = X[rows, iv]
    v_new = R["vol"]
    print()

    # ---- is it less noisy? ----
    print("=" * 112)
    print("THE PREMISE -- is the 1-minute estimate less noisy?")
    print("=" * 112)
    print("  Split-half reliability: the window's changes split into interleaved")
    print("  odd and even steps, each half estimating the same quantity at the same")
    print("  time. Spearman-Brown corrects the half-length correlation up to full")
    print("  length. 1 - reliability is the estimator's noise share. A diagnostic,")
    print("  not a gate.")
    dW = np.abs(np.diff(W[rows][:, -(NMIN // MARK + 1):].astype(np.float64), axis=1))
    r30, sb30 = spearman_brown(dW[:, 0::2].mean(1), dW[:, 1::2].mean(1))
    r1, sb1 = spearman_brown(R["half_a"], R["half_b"])
    print(f"    vol_48    (48 steps)   half-correlation {r30:.4f}   reliability "
          f"{sb30:.4f}   noise share {100*(1-sb30):.1f}%")
    print(f"    vol_48_1m (1,440 steps) half-correlation {r1:.4f}   reliability "
          f"{sb1:.4f}   noise share {100*(1-sb1):.1f}%")
    rs = float(spearmanr(v_old, v_new).statistic)
    print(f"    Spearman(vol_48, vol_48_1m) = {rs:.4f};  median ratio "
          f"vol_48_1m / vol_48 = {np.median(v_new / v_old):.4f}")
    print(f"    (a random walk would give 1/sqrt(30) = {1/np.sqrt(30):.4f}; a "
          f"higher ratio is microstructure noise in the 1-minute prints)")
    print()

    # ---- targets, contexts, cache check ----
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    Xs_old = X[rows]
    fp = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), Xs_old)
    if FP_KEY not in cache.files or str(cache[FP_KEY]) != fp:
        raise SystemExit("[VOL1M] match1m cache fingerprint mismatch -- old numbers "
                         "would not be the published ones.")
    print(f"  cache fingerprint matches ({fp[:16]}...): 'old' is the published QTREE.")
    Xs_new = Xs_old.copy()
    Xs_new[:, iv] = v_new
    names_new = list(names)
    names_new[iv] = "vol_48_1m"
    ctx_o = build_context(np.ones(len(rows), bool), Xs_old, day[rows], Y[rows, 0],
                          verbose=False)
    ctx_n = build_context(np.ones(len(rows), bool), Xs_new, day[rows], Y[rows, 0],
                          verbose=True)
    boot = day_boot(ctx_n["day_test"])
    rng = np.random.default_rng(SEED)
    print()

    out = {}
    for d, k in CELLS:
        tag = f"1m/{d}/{HLABEL[k]}"
        y = T1M[(d, k)][ctx_n["test"]]
        clim = cache[f"1m|{d}|Climatology|{k}"]
        old = cache[f"1m|{d}|QTREE|{k}"]
        # new QTREE, all five horizons, same two-pass enforcement as the cache
        tes, mods_n = [], None
        for kk in HORIZONS:
            ms = [] if kk == k else None
            tes.append(fit_qtree(ctx_n, T1M[(d, kk)], models=ms))
            if kk == k:
                mods_n = ms
        enf, _, _ = enforce_two_pass(np.stack(tes))
        new = enf[HORIZONS.index(k)]
        mods_o = []
        fit_qtree(ctx_o, T1M[(d, k)], models=mods_o)        # old models, for importance
        so = skill_ci(y, old, clim, boot)
        sn = skill_ci(y, new, clim, boot)
        ds = paired_skill_ci(y, old, new, clim, boot)
        go = gap_ci(y, old, boot)
        gn = gap_ci(y, new, boot)
        dg = gap_paired_ci(y, old, y, new, boot)
        pc = _pinball_rows(y, clim)
        imp_o, imp_n = {}, {}
        for j in range(len(names)):
            imp_o[j] = importance(lambda Xp: qtree_predict(mods_o, Xp), ctx_o["Xte"],
                                  [j], y, pc, boot, rng)
            imp_n[j] = importance(lambda Xp: qtree_predict(mods_n, Xp), ctx_n["Xte"],
                                  [j], y, pc, boot, rng)
        out[(d, k)] = dict(so=so, sn=sn, ds=ds, go=go, gn=gn, dg=dg,
                           imp_o=imp_o, imp_n=imp_n)
        print(f"  fitted and scored {tag}   [{time.time()-t0:.0f}s]", flush=True)
    print()

    # ---- the comparison ----
    print("=" * 112)
    print("OLD vol_48 vs NEW vol_48_1m -- QTREE, paired on identical rows")
    print("=" * 112)
    print(f"  {'cell':<12}{'measure':<10}{'old':>9}{'new':>9}{'new - old':>11}"
          f"{'[95% CI]':>18}{'':>12}")
    better = worse = 0
    for d, k in CELLS:
        r = out[(d, k)]
        tag = f"{d} {HLABEL[k]}"
        s_tag = ("BETTER" if r["ds"][1] > 0 else "WORSE" if r["ds"][2] < 0 else "")
        g_tag = ("BETTER" if r["dg"][2] < 0 else "WORSE" if r["dg"][1] > 0 else "")
        better += (s_tag == "BETTER") + (g_tag == "BETTER")
        worse += (s_tag == "WORSE") + (g_tag == "WORSE")
        ds, dg = r["ds"], r["dg"]
        ci_s = f"[{ds[1]:+.3f},{ds[2]:+.3f}]"
        ci_g = f"[{dg[1]:+.3f},{dg[2]:+.3f}]"
        print(f"  {tag:<12}{'skill %':<10}{r['so'][0]:>+9.2f}{r['sn'][0]:>+9.2f}"
              f"{ds[0]:>+11.3f}{ci_s:>18}{s_tag:>12}")
        print(f"  {'':<12}{'gap pp':<10}{r['go'][0]:>9.2f}{r['gn'][0]:>9.2f}"
              f"{dg[0]:>+11.3f}{ci_g:>18}{g_tag:>12}")
    print("  skill: positive new-old = the new feature helps. gap: negative = better")
    print("  calibrated. BETTER/WORSE = the paired interval excludes zero.")
    print()

    print("=" * 112)
    print("PERMUTATION IMPORTANCE -- does the sharper feature still carry the load?")
    print("=" * 112)
    print("  Skill points lost when a column is shuffled, 20 shuffles, day-clustered")
    print("  intervals. Old model with vol_48, new model with vol_48_1m in its place.")
    print()
    for d, k in CELLS:
        r = out[(d, k)]
        print(f"  {d} {HLABEL[k]}")
        print(f"    {'feature':<20}{'old model':>12}{'[95% CI]':>18}"
              f"{'new model':>12}{'[95% CI]':>18}")
        for j in range(len(names)):
            a, b = r["imp_o"][j], r["imp_n"][j]
            lab = names[j] if j != iv else "vol_48 -> vol_48_1m"
            print(f"    {lab:<20}{a[0]:>+12.3f}{f'[{a[1]:+.3f},{a[2]:+.3f}]':>18}"
                  f"{b[0]:>+12.3f}{f'[{b[1]:+.3f},{b[2]:+.3f}]':>18}")
        print()

    # ---- decision ----
    print("=" * 112)
    print("DECISION -- rule fixed in the module docstring before the run")
    print("=" * 112)
    meaningful = better >= 1 and worse == 0
    print(f"  paired measures significantly BETTER: {better} of 4;  significantly "
          f"WORSE: {worse} of 4.")
    if meaningful:
        print("  VERDICT: MEANINGFUL. At least one cell improves with an interval clear")
        print("  of zero and nothing gets worse. Per the brief, vol_48_1m is to be")
        print("  propagated into the full registry -- a separate run, with its own")
        print("  feature matrix and cache, because every model's inputs change.")
    else:
        print("  VERDICT: MARGINAL. Per the brief: say so plainly and stop. vol_48_1m")
        print("  is not propagated, and nothing further is chased in this pass.")
    print()
    np.savez_compressed(os.path.join(paths.DATASETS, "vol48_1m.npz"),
                        rows=rows, vol_48_1m=v_new.astype(np.float64),
                        nvalid=R["nvalid"], nmiss=R["nmiss"])
    print(f"  [WROTE] research/datasets/vol48_1m.npz -- the feature for the "
          f"{len(rows):,} rows, with its per-episode valid-change and missing-minute counts.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------- MAE at the other horizons
REMAINING = (1, 2, 4, 10)          # 0.5h 1h 2h 5h; 10h (=20) is re-scored as a check
PUBLISHED_10H = dict(skill=2.77, gap=2.86)   # NUMBERS.md, VOL48-1M, MAE 10h new


def mae_horizons():
    """Does the MAE win at 10h hold at 0.5h / 1h / 2h / 5h? Scoring, not building.

    vol48_1m.npz already covers all 53,757 episodes and is reloaded, not rebuilt;
    its rows must match the current population exactly. The new QTREE is refitted
    for all five MAE horizons with the same two-pass enforcement as the cache --
    exactly the fit the cells run made, of which only 10h was scored. 10h is
    scored again here as a REPRODUCTION CHECK: it must return the published
    +2.77% skill and 2.86pp gap.

    THE DECISION RULE, stated by the brief and fixed before the run. Per horizon:
      LOSS  either paired measure (skill, gap) is significantly worse
      WIN   a measure is significantly better and neither is worse
      TIE   anything else -- overlapping intervals, no clear loss
    ADOPT vol_48_1m for MAE if WIN or TIE at a majority -- 3 or more -- of the
    four remaining horizons. Otherwise the 10h result was horizon-specific and
    the MARGINAL verdict stands. A 2-2 split does not meet the adoption
    majority, so it does not adopt: the status quo holds unless the evidence
    clears the bar. This fills a gap the brief's wording left open.
    """
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    iv = names.index("vol_48")
    day = meta.day.to_numpy()

    print("=" * 112)
    print("vol_48_1m FOR MAE AT THE REMAINING HORIZONS -- scoring, no feature build")
    print("=" * 112)
    cache = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v["rows"], rows):
        raise SystemExit("[VOL1M] vol48_1m.npz was built for different rows -- rebuild "
                         "it with the default stage before scoring.")
    v_new = v["vol_48_1m"]
    print(f"  feature reloaded: {len(rows):,} rows, identical to the population; "
          f"sha256 {hashlib.sha256(v_new.tobytes()).hexdigest()[:12]}")

    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    Xs_old = X[rows]
    fp = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), Xs_old)
    if FP_KEY not in cache.files or str(cache[FP_KEY]) != fp:
        raise SystemExit("[VOL1M] match1m cache fingerprint mismatch.")
    print(f"  cache fingerprint matches ({fp[:16]}...): 'old' is the published QTREE.")
    Xs_new = Xs_old.copy()
    Xs_new[:, iv] = v_new
    ctx_n = build_context(np.ones(len(rows), bool), Xs_new, day[rows], Y[rows, 0],
                          verbose=True)
    boot = day_boot(ctx_n["day_test"])

    tes = [fit_qtree(ctx_n, T1M[("MAE", kk)]) for kk in HORIZONS]
    enf, _, _ = enforce_two_pass(np.stack(tes))
    print(f"  new QTREE refitted, MAE, all five horizons, two-pass enforced   "
          f"[{time.time()-t0:.0f}s]")
    print()

    rowsout = {}
    for k in REMAINING + (20,):
        y = T1M[("MAE", k)][ctx_n["test"]]
        clim = cache[f"1m|MAE|Climatology|{k}"]
        old = cache[f"1m|MAE|QTREE|{k}"]
        new = enf[HORIZONS.index(k)]
        rowsout[k] = dict(so=skill_ci(y, old, clim, boot), sn=skill_ci(y, new, clim, boot),
                          ds=paired_skill_ci(y, old, new, clim, boot),
                          go=gap_ci(y, old, boot), gn=gap_ci(y, new, boot),
                          dg=gap_paired_ci(y, old, y, new, boot))

    r10 = rowsout[20]
    print("=" * 112)
    print("REPRODUCTION -- 10h must return the published new-feature numbers")
    print("=" * 112)
    print(f"  skill {r10['sn'][0]:+.2f}% (published {PUBLISHED_10H['skill']:+.2f}%)   "
          f"gap {r10['gn'][0]:.2f}pp (published {PUBLISHED_10H['gap']:.2f}pp)")
    if (abs(round(r10["sn"][0], 2) - PUBLISHED_10H["skill"]) > 1e-9
            or abs(round(r10["gn"][0], 2) - PUBLISHED_10H["gap"]) > 1e-9):
        raise SystemExit("[VOL1M] ABORT -- 10h does not reproduce the cells run.")
    print("  Reproduced.")
    print()

    print("=" * 112)
    print("MAE: OLD vol_48 vs NEW vol_48_1m -- QTREE, paired on identical rows")
    print("=" * 112)
    print(f"  {'h':<6}{'measure':<9}{'old':>8}{'new':>8}{'new - old':>11}"
          f"{'[95% CI]':>18}{'':>9}{'horizon':>10}")
    outcome = {}
    for k in REMAINING + (20,):
        r = rowsout[k]
        ds, dg = r["ds"], r["dg"]
        s_t = "better" if ds[1] > 0 else "WORSE" if ds[2] < 0 else ""
        g_t = "better" if dg[2] < 0 else "WORSE" if dg[1] > 0 else ""
        if "WORSE" in (s_t, g_t):
            oc = "LOSS"
        elif "better" in (s_t, g_t):
            oc = "WIN"
        else:
            oc = "TIE"
        outcome[k] = oc
        lab = HLABEL[k] + ("*" if k == 20 else "")
        print(f"  {lab:<6}{'skill %':<9}{r['so'][0]:>+8.2f}{r['sn'][0]:>+8.2f}"
              f"{ds[0]:>+11.3f}{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{s_t:>9}{oc:>10}")
        print(f"  {'':<6}{'gap pp':<9}{r['go'][0]:>8.2f}{r['gn'][0]:>8.2f}"
              f"{dg[0]:>+11.3f}{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{g_t:>9}")
    print("  * 10h is the horizon already scored, shown for reference; it does not")
    print("    count toward the decision, which is about the OTHER four.")
    print()

    print("=" * 112)
    print("DECISION -- rule fixed in mae_horizons' docstring before the run")
    print("=" * 112)
    n_ok = sum(outcome[k] in ("WIN", "TIE") for k in REMAINING)
    n_loss = sum(outcome[k] == "LOSS" for k in REMAINING)
    print(f"  remaining four horizons: " + ", ".join(
        f"{HLABEL[k]} {outcome[k]}" for k in REMAINING))
    print(f"  WIN or TIE {n_ok} of 4;  LOSS {n_loss} of 4.")
    if n_ok >= 3:
        print("  VERDICT: ADOPT vol_48_1m FOR MAE. It holds at a majority of the other")
        print("  horizons. Keep vol_48 for MFE. Propagating it into the registry is a")
        print("  separate build: every MAE model's inputs change, so it needs its own")
        print("  feature matrix and cache.")
    else:
        print("  VERDICT: DO NOT ADOPT. The 10h win does not hold at a majority of the")
        print("  other horizons, so it was horizon-specific. The MARGINAL verdict from")
        print("  the cells run stands; no split feature set on one data point.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------- MAE registry on vol_48_1m
MAE_CACHE = "match1m_mae_vol1m"     # paths.envelope_preds(...) -> its own file
QTREE_REF = {20: (2.77, 2.86)}       # VOL48-1M-MAE, new QTREE at 10h: skill, gap


def mae_registry():
    """Rebuild the MAE side of the registry on vol_48_1m. MFE is not touched.

    1-minute target, ALL, the matched 53,757-episode set, the usual split. All
    five registry models on MAE at all five horizons, with vol_48 replaced by
    vol_48_1m. Old = the published MAE predictions in the match1m cache. New =
    refitted here into their OWN cache file with their OWN fingerprint, because
    the match1m fingerprint covers the old features and correctly refuses
    reuse; it is not forced. The match1m cache is read, never written, so every
    MFE prediction stays exactly as published.

    CQR IS REFITTED, NOT REUSED. It wraps a fitted QTREE plus a correction
    calibrated on val, so new MAE inputs mean a new QTREE inside it and new
    widths and median shift. That is checked, not assumed: the stage confirms
    the new CQR predictions differ from the cached ones.

    CLIMATOLOGY USES NO FEATURES, so its new predictions must equal the old ones
    exactly. That is asserted: it is both a pipeline check and the guarantee
    that old and new skill share the same denominator.

    QTREE must reproduce the mae_horizons run: +2.77% skill and 2.86pp gap at 10h.

    PER-MODEL VERDICT, fixed before the run. Per horizon, each paired measure is
    'confirmed' if its 95% interval clears zero in the new feature's favour,
    'directional' if the point estimate favours it but the interval touches
    zero, and 'worse' if the interval clears zero against it.
      REVERSES  any measure significantly worse at any horizon
      HOLDS     no reversal, and the gap improvement confirmed at >= 3 of 5
      WEAKER    no reversal, gap confirmed at 1-2 horizons, or only skill
      ABSENT    no reversal, nothing confirmed
    QTREE's benchmark from VOL48-1M-MAE: gap confirmed at 5 of 5, skill
    confirmed at 2h/5h/10h and directional at 0.5h/1h.
    """
    # Pinned to the five-model registry this stage published on: since
    # REGISTRY-CONSOLIDATED, MODELS is three, and re-running this stage must
    # still reproduce VOL48-1M-REGISTRY.
    REG5 = REGISTRY_UNTIL_2026_10_12
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    iv = names.index("vol_48")
    day = meta.day.to_numpy()

    print("=" * 112)
    print("MAE REGISTRY ON vol_48_1m -- five models, five horizons, MFE untouched")
    print("=" * 112)
    old_cache = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v["rows"], rows):
        raise SystemExit("[VOL1M] vol48_1m.npz rows differ from the population.")
    print(f"  vol_48_1m reloaded for {len(rows):,} rows "
          f"(sha256 {hashlib.sha256(v['vol_48_1m'].tobytes()).hexdigest()[:12]})")
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    Xs_old = X[rows]
    fp_old = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), Xs_old)
    if FP_KEY not in old_cache.files or str(old_cache[FP_KEY]) != fp_old:
        raise SystemExit("[VOL1M] match1m cache fingerprint mismatch.")
    print(f"  old MAE predictions: match1m cache, fingerprint {fp_old[:16]}... "
          f"(read only)")
    Xs_new = Xs_old.copy()
    Xs_new[:, iv] = v["vol_48_1m"]
    ctx = build_context(np.ones(len(rows), bool), Xs_new, day[rows], Y[rows, 0],
                        verbose=True)
    TM = {("MAE", k): T1M[("MAE", k)] for k in HORIZONS}
    fp_new = cache_fingerprint([rows], flat_targets(TM), Xs_new)
    print(f"  new MAE cache: {MAE_CACHE}, fingerprint {fp_new[:16]}... "
          f"(vol_48_1m features, 1m MAE targets)")
    print()

    FN = dict(REG5)
    keys = [("1m", "MAE", mn, k) for mn, _ in REG5 for k in HORIZONS]

    def _fit_one(key):
        _, d, mn, k = key
        return FN[mn](ctx, T1M[(d, k)], f"1m/{d}/{HLABEL[k]}/vol_48_1m")

    cache_path = paths.envelope_preds(MAE_CACHE)
    P, n_loaded, n_fitted, needs_save = load_or_fit(cache_path, keys, _fit_one, fp_new)
    print()
    print(f"  {'model':<13}{'quantile enforce':>17}{'horizon enforce':>19}")
    for mn, _ in REG5:
        stack = np.stack([P[("1m", "MAE", mn, k)] for k in HORIZONS])
        s2, rq, rk = enforce_two_pass(stack)
        for i, k in enumerate(HORIZONS):
            P[("1m", "MAE", mn, k)] = s2[i]
        print(f"  {mn:<13}{100*rq:>16.3f}%{100*rk:>18.3f}%")
    if needs_save:
        carried = save_cache(cache_path, fp_new, P, keys)
        print(f"  [CACHE] wrote {os.path.basename(cache_path)} -- {n_fitted} fitted, "
              f"{n_loaded} reloaded, {carried} carried, post-enforcement, fingerprinted.")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- the three checks ----
    print("=" * 112)
    print("CHECKS")
    print("=" * 112)
    ce = max(float(np.max(np.abs(P[("1m", "MAE", "Climatology", k)]
                                 - old_cache[f"1m|MAE|Climatology|{k}"])))
             for k in HORIZONS)
    print(f"  Climatology new vs old (uses no features, must be identical): {ce:.3e}")
    if ce > 1e-12:
        raise SystemExit("[VOL1M] ABORT -- climatology changed; the denominators differ.")
    cq = [float(np.max(np.abs(P[("1m", "MAE", "CQR", k)]
                              - old_cache[f"1m|MAE|CQR|{k}"]))) for k in HORIZONS]
    print(f"  CQR new vs old, max |diff| per horizon: "
          + "  ".join(f"{HLABEL[k]} {c:.3f}" for k, c in zip(HORIZONS, cq)))
    if min(cq) == 0.0:
        raise SystemExit("[VOL1M] ABORT -- a CQR cell is identical to the old one, so "
                         "it was reused rather than refitted on the new QTREE.")
    print("  CQR refitted on the new QTREE: every horizon differs from the cached CQR.")
    boot = day_boot(ctx["day_test"])
    y20 = T1M[("MAE", 20)][ctx["test"]]
    clim20 = old_cache["1m|MAE|Climatology|20"]
    sq = skill_ci(y20, P[("1m", "MAE", "QTREE", 20)], clim20, boot)[0]
    gq = gap_ci(y20, P[("1m", "MAE", "QTREE", 20)], boot)[0]
    print(f"  QTREE 10h reproduces mae_horizons: skill {sq:+.2f}% (ref "
          f"{QTREE_REF[20][0]:+.2f})  gap {gq:.2f}pp (ref {QTREE_REF[20][1]:.2f})")
    if abs(round(sq, 2) - QTREE_REF[20][0]) > 1e-9 or abs(round(gq, 2) - QTREE_REF[20][1]) > 1e-9:
        raise SystemExit("[VOL1M] ABORT -- QTREE does not reproduce the mae_horizons run.")
    print()

    # ---- per-model comparison ----
    print("=" * 112)
    print("PER MODEL -- old vol_48 vs new vol_48_1m, MAE, paired on identical rows")
    print("=" * 112)
    print("  skill: + = new helps. gap: - = better calibrated. conf = interval clears")
    print("  zero in the new feature's favour; dir = favourable point estimate, interval")
    print("  touches zero; WORSE = interval clears zero against it.")
    print()
    verdicts = {}
    for mn, _ in REG5:
        print(f"  {mn}")
        print(f"    {'h':<6}{'skill old':>10}{'new':>8}{'new-old':>9}{'[95% CI]':>18}{'':>7}"
              f"{'gap old':>9}{'new':>7}{'new-old':>9}{'[95% CI]':>18}{'':>7}")
        g_conf = s_conf = s_dir = g_dir = worse = 0
        for k in HORIZONS:
            y = T1M[("MAE", k)][ctx["test"]]
            clim = old_cache[f"1m|MAE|Climatology|{k}"]
            old = old_cache[f"1m|MAE|{mn}|{k}"]
            new = P[("1m", "MAE", mn, k)]
            go, gn = gap_ci(y, old, boot)[0], gap_ci(y, new, boot)[0]
            dg = gap_paired_ci(y, old, y, new, boot)
            gt = ("conf" if dg[2] < 0 else "WORSE" if dg[1] > 0
                  else "dir" if dg[0] < 0 else "")
            g_conf += gt == "conf"; g_dir += gt == "dir"; worse += gt == "WORSE"
            if mn == "Climatology":
                st, sline = "", f"{'(denominator)':>45}"
            else:
                so, sn = skill_ci(y, old, clim, boot)[0], skill_ci(y, new, clim, boot)[0]
                ds = paired_skill_ci(y, old, new, clim, boot)
                st = ("conf" if ds[1] > 0 else "WORSE" if ds[2] < 0
                      else "dir" if ds[0] > 0 else "")
                s_conf += st == "conf"; s_dir += st == "dir"; worse += st == "WORSE"
                sline = (f"{so:>+10.2f}{sn:>+8.2f}{ds[0]:>+9.3f}"
                         f"{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{st:>7}")
            print(f"    {HLABEL[k]:<6}{sline}{go:>9.2f}{gn:>7.2f}{dg[0]:>+9.3f}"
                  f"{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{gt:>7}")
        if worse:
            vd = "REVERSES"
        elif g_conf >= 3:
            vd = "HOLDS"
        elif g_conf >= 1 or s_conf >= 1:
            vd = "WEAKER"
        else:
            vd = "ABSENT"
        if mn == "Climatology":
            vd = "n/a -- uses no features"
        verdicts[mn] = (vd, g_conf, g_dir, s_conf, s_dir, worse)
        print(f"    -> gap confirmed {g_conf}/5, directional {g_dir}/5;  skill confirmed "
              f"{s_conf}/5, directional {s_dir}/5;  worse {worse}.  VERDICT: {vd}")
        print()

    print("=" * 112)
    print("SUMMARY -- does the QTREE-measured win generalise?")
    print("=" * 112)
    print(f"  {'model':<13}{'verdict':<26}{'gap conf':>9}{'gap dir':>9}"
          f"{'skill conf':>12}{'skill dir':>11}{'worse':>7}")
    for mn, (vd, gc, gd, sc, sd, w) in verdicts.items():
        print(f"  {mn:<13}{vd:<26}{gc:>9}{gd:>9}{sc:>12}{sd:>11}{w:>7}")
    print()
    print("  MFE SIDE UNCHANGED: every MFE prediction is still the published one in")
    print("  the match1m cache, on vol_48. Nothing on the MFE side was refitted.")
    print("  Levels are a later look at already-scored rows; the old-versus-new")
    print("  differences are within-row paired contrasts and are the new measurement.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------- vol_slope at 1-minute
def slope_cells():
    """vol_slope_1m on the two importance cells, QTREE, against the CURRENT registry.

    vol_slope (envfeat.py) is the population sd of the last 16 thirty-minute
    steps (8h) over the sd of the 32 before (16h). vol_slope_1m is the same
    statistic on the same two calendar windows at 1-minute resolution: 480
    steps over 960. Only the resolution changes; vol_48, vratio, sandwich and
    off_mark are untouched.

    THE BASELINE IS THE CURRENT REGISTRY, PER DIRECTION, so this is one change
    against what is actually in use. MAE now runs on vol_48_1m (VOL48-1M-
    REGISTRY), so MAE's baseline is that feature set and its predictions come
    from the match1m_mae_vol1m cache. MFE runs on the original features, so its
    baseline is the match1m cache. Both caches are fingerprint-checked.

    CORRECTNESS, carried over: no read past minute entry+29; the 1-minute path
    reproduces the stored 30-minute window at all 49 marks; the OLD vol_slope
    is recomputed from those marks and must equal envfeat's; missing minutes
    counted, never filled. Plus a regression check on the shared path code:
    vol_48_1m recomputed here must equal the saved vol48_1m.npz exactly.

    THE RULE, fixed before the run. Per cell: IMPROVES if a paired measure
    (skill, gap) is significantly better and neither is worse; LOSES if either
    is significantly worse; HOLDS otherwise.
      PROPAGATE  neither cell loses and at least one improves
      SPLIT      one cell improves and the other loses -> chase only the
                 winning side across the other four horizons, before any
                 registry change
      MARGINAL   no cell improves -- stop and report. Both cells merely
                 holding is marginal: there is nothing to propagate.
    """
    t0 = time.time()
    z = np.load(paths.DISLOC)
    W = z["windows"]
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    iv, isl = names.index("vol_48"), names.index("vol_slope")
    day = meta.day.to_numpy()

    print("=" * 112)
    print("vol_slope_1m -- the same 8h/16h ratio of step sd, at 1-minute resolution")
    print("=" * 112)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], rows):
        raise SystemExit("[VOL1M] vol48_1m.npz rows differ from the population.")
    print(f"  population: the matched {len(rows):,}-episode set")
    print()

    print("=" * 112)
    print("BUILD -- vol_slope_1m, with the carried-over correctness checks")
    print("=" * 112)
    R = trailing_features(meta, rows, W, X[rows, iv], X[rows, isl])
    print()
    print(f"  1. max minute offset read, relative to entry_time: +{R['max_off']} "
          f"(must be +{MARK-1})")
    if R["max_off"] != MARK - 1:
        raise SystemExit("[VOL1M] ABORT -- the window reads past the entry bar's close.")
    print(f"  2. 1-minute path vs stored 30m window at the 49 marks: max error "
          f"{R['rep_err']:.3e}, {R['rep_ratio']:.3f} of the float32 budget")
    if not R["rep_ratio"] < 1.0:
        raise SystemExit("[VOL1M] ABORT -- the path does not reproduce the 30m window.")
    print(f"  3. OLD vol_slope recomputed from the new path's marks vs envfeat: "
          f"max diff {R['recomp_s']:.3e}")
    if not R["recomp_s"] < 1e-4:
        raise SystemExit("[VOL1M] ABORT -- the old vol_slope does not come back from "
                         "the new path: window or statistic differs.")
    dv = float(np.max(np.abs(R["vol"] - v48["vol_48_1m"])))
    print(f"  4. regression: vol_48_1m from the shared path code vs saved "
          f"vol48_1m.npz: max diff {dv:.3e}")
    if dv > 0.0:
        raise SystemExit("[VOL1M] ABORT -- the refactored path code changed vol_48_1m.")
    nf, ns = R["nfast"], R["nslow"]
    print(f"  5. valid one-minute steps: fast window (of {FAST_MIN}) min {nf.min()}, "
          f"median {np.median(nf):.0f};  slow window (of {SLOW_MIN}) min {ns.min()}, "
          f"median {np.median(ns):.0f}")
    print(f"     episodes with both windows complete: "
          f"{int(((nf==FAST_MIN)&(ns==SLOW_MIN)).sum()):,} of {len(rows):,};  "
          f"below half in either: {int(((nf<FAST_MIN//2)|(ns<SLOW_MIN//2)).sum()):,}")
    # EPISODES THAT CANNOT FORM THE RATIO. On the first two days after the
    # 2025-06-26/27 backfill wall, an episode's 16-hour window falls before any
    # 1-minute data exists, so the slow-window sd is undefined. Measured: 6
    # episodes, all in TRAIN, none in val or held out. For exactly those, the
    # 30-minute vol_slope is used -- the same quantity at the old resolution,
    # where the new one is impossible. That is not forward-filling a price; it
    # is a counted, flagged substitution of one estimate for another, confined
    # to rows that are never scored. If it ever touches val or held out, this
    # aborts, because there it would change a scored number.
    sp_ = harness.Split(day[rows], Y[rows, 0])
    bad = ~np.isfinite(R["slope"]) | (nf < 2) | (ns < 2)
    s_old = X[rows, isl]
    s_new = R["slope"].copy()
    if (bad & ~sp_.train).any():
        raise SystemExit(f"[VOL1M] ABORT -- {int((bad & ~sp_.train).sum())} episodes "
                         f"outside TRAIN cannot form vol_slope_1m. A substitution "
                         f"there would change a scored number.")
    s_new[bad] = s_old[bad]
    print(f"  6. cannot form the ratio (fewer than 2 valid steps in a window): "
          f"{int(bad.sum())} episodes, all in TRAIN "
          f"({int((bad & sp_.train).sum())} train, 0 val, 0 held out).")
    print(f"     For these only, vol_slope_1m := the 30-minute vol_slope. Flagged "
          f"per row in vol_slope_1m.npz.")
    print()

    print("=" * 112)
    print("THE PREMISE -- is the 1-minute vol_slope less noisy?")
    print("=" * 112)
    print("  Split-half: each window's steps split into interleaved odd and even")
    print("  steps; the ratio is formed from each half; Spearman-Brown corrects the")
    print("  half-length correlation to full length. A diagnostic, not a gate.")
    dW = np.diff(W[rows][:, -(NMIN // MARK + 1):].astype(np.float64), axis=1)
    fw, sw = dW[:, -FAST_BARS:], dW[:, -(FAST_BARS + SLOW_BARS):-FAST_BARS]
    a30 = fw[:, 0::2].std(1) / np.clip(sw[:, 0::2].std(1), 1e-12, None)
    b30 = fw[:, 1::2].std(1) / np.clip(sw[:, 1::2].std(1), 1e-12, None)
    r30, sb30 = spearman_brown(np.log(a30), np.log(b30))
    r1, sb1 = spearman_brown(np.log(R["slope_a"]), np.log(R["slope_b"]))
    print(f"    vol_slope    (16/32 steps)   half-r {r30:.4f}  reliability {sb30:.4f}"
          f"  noise share {100*(1-sb30):.1f}%")
    print(f"    vol_slope_1m (480/960 steps) half-r {r1:.4f}  reliability {sb1:.4f}"
          f"  noise share {100*(1-sb1):.1f}%")
    print("    (correlations on log-ratios: a ratio of sds is right-skewed and the")
    print("     log makes the Pearson correlation measure what it should)")
    rs = float(spearmanr(s_old, s_new).statistic)
    print(f"    Spearman(vol_slope, vol_slope_1m) = {rs:.4f};  median old "
          f"{np.median(s_old):.4f}, new {np.median(s_new):.4f}")
    print()

    # ---- baselines, fingerprint-checked ----
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    c_mfe = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    c_mae = np.load(paths.envelope_preds(MAE_CACHE), allow_pickle=False)
    X_mfe = X[rows].copy()
    X_mae = X[rows].copy()
    X_mae[:, iv] = v48["vol_48_1m"]
    fp_mfe = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), X_mfe)
    fp_mae = cache_fingerprint([rows], flat_targets(
        {("MAE", k): T1M[("MAE", k)] for k in HORIZONS}), X_mae)
    if str(c_mfe[FP_KEY]) != fp_mfe or str(c_mae[FP_KEY]) != fp_mae:
        raise SystemExit("[VOL1M] a baseline cache fingerprint does not match.")
    print(f"  baselines: MFE match1m {fp_mfe[:12]} (vol_48), MAE {MAE_CACHE} "
          f"{fp_mae[:12]} (vol_48_1m) -- both match")
    base = {"MFE": (X_mfe, c_mfe), "MAE": (X_mae, c_mae)}
    print()

    res = {}
    for d, k in CELLS:
        Xb, cb = base[d]
        Xn = Xb.copy()
        Xn[:, isl] = s_new
        ctx = build_context(np.ones(len(rows), bool), Xn, day[rows], Y[rows, 0],
                            verbose=(d == "MFE"))
        boot = day_boot(ctx["day_test"])
        tes = [fit_qtree(ctx, T1M[(d, kk)]) for kk in HORIZONS]
        enf, _, _ = enforce_two_pass(np.stack(tes))
        new = enf[HORIZONS.index(k)]
        y = T1M[(d, k)][ctx["test"]]
        old = cb[f"1m|{d}|QTREE|{k}"]
        clim = cb[f"1m|{d}|Climatology|{k}"]
        res[d] = dict(so=skill_ci(y, old, clim, boot)[0], sn=skill_ci(y, new, clim, boot)[0],
                      ds=paired_skill_ci(y, old, new, clim, boot),
                      go=gap_ci(y, old, boot)[0], gn=gap_ci(y, new, boot)[0],
                      dg=gap_paired_ci(y, old, y, new, boot))
        print(f"  refitted QTREE {d}, five horizons, vol_slope -> vol_slope_1m   "
              f"[{time.time()-t0:.0f}s]", flush=True)
    print()

    print("=" * 112)
    print("OLD vol_slope vs NEW vol_slope_1m -- QTREE, 10h, paired on identical rows")
    print("=" * 112)
    print("  baseline per direction = the current registry (MAE on vol_48_1m, MFE on")
    print("  vol_48). skill: + = new helps. gap: - = better calibrated.")
    print()
    print(f"  {'cell':<10}{'measure':<9}{'old':>8}{'new':>8}{'new - old':>11}"
          f"{'[95% CI]':>18}{'':>9}{'cell':>10}")
    outcome = {}
    for d, k in CELLS:
        r = res[d]
        ds, dg = r["ds"], r["dg"]
        s_t = "better" if ds[1] > 0 else "WORSE" if ds[2] < 0 else ""
        g_t = "better" if dg[2] < 0 else "WORSE" if dg[1] > 0 else ""
        oc = ("LOSES" if "WORSE" in (s_t, g_t)
              else "IMPROVES" if "better" in (s_t, g_t) else "HOLDS")
        outcome[d] = oc
        print(f"  {d+' 10h':<10}{'skill %':<9}{r['so']:>+8.2f}{r['sn']:>+8.2f}"
              f"{ds[0]:>+11.3f}{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{s_t:>9}{oc:>10}")
        print(f"  {'':<10}{'gap pp':<9}{r['go']:>8.2f}{r['gn']:>8.2f}"
              f"{dg[0]:>+11.3f}{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{g_t:>9}")
    print()

    print("=" * 112)
    print("DECISION -- rule fixed in slope_cells' docstring before the run")
    print("=" * 112)
    oc = list(outcome.values())
    print(f"  MFE {outcome['MFE']}, MAE {outcome['MAE']}")
    if "IMPROVES" not in oc:
        print("  VERDICT: MARGINAL. Neither direction shows a real improvement. Stop.")
    elif "LOSES" not in oc:
        print("  VERDICT: PROPAGATE. Neither cell loses and at least one improves.")
        print("  The registry rebuild is a separate build.")
    else:
        win = [d for d in outcome if outcome[d] == "IMPROVES"][0]
        print(f"  VERDICT: SPLIT. {win} improves and the other side loses. Next per the")
        print(f"  rule: chase {win} only, across the other four horizons, before any")
        print(f"  registry change. Not done in this run.")
    np.savez_compressed(os.path.join(paths.DATASETS, "vol_slope_1m.npz"),
                        rows=rows, vol_slope_1m=s_new, nfast=nf, nslow=ns,
                        fallback_30m=bad)
    print(f"  [WROTE] research/datasets/vol_slope_1m.npz -- the feature for "
          f"{len(rows):,} rows, with per-window valid-step counts and the "
          f"fallback flag.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("cells", "mae_horizons", "mae_registry",
                                        "slope_cells"),
                    default="cells",
                    help="cells = build vol_48_1m and compare on MFE/MAE 10h. "
                         "mae_horizons = reload the built feature and score MAE at "
                         "0.5h/1h/2h/5h, re-scoring 10h as a reproduction check.")
    stg = ap.parse_args().stage
    if stg == "mae_horizons":
        mae_horizons()
    elif stg == "mae_registry":
        mae_registry()
    elif stg == "slope_cells":
        slope_cells()
    else:
        main()
