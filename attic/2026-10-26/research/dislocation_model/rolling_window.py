"""One recency test: a trailing-window refit against the full-history fit.

    .venv/bin/python research/dislocation_model/rolling_window.py 2>&1 \
        | tee research/dislocation_model/logs/rolling_window.log

THE QUESTION. Before building a walk-forward system: does a model trained on
less, more recent data calibrate tighter on the held-out block than one trained
on all of it? Especially on HO2 (>= 2026-08-26), where the drift was worst.

THE WINDOW, AND A CORRECTED PREMISE. The brief assumed a ~667-day fit block. On
the matched 53,757-episode population the 1-minute backfill wall sets the start:
train is 2025-06-26 -> 2026-04-30 (22,645 rows), val 2026-05-01 -> 2026-07-17,
and the whole fit block spans 386 days. A 12-month window would drop ~3% of
train and test nearly nothing. So the window is the SHORTEST the brief allows:
9 months immediately preceding the held-out start (2026-07-18), i.e. training
rows on or after 2025-10-18. That drops the oldest ~21% of train (June to mid-
October 2025). It is still a mild contrast, and a "same" result is weak
evidence against recency for that reason.

ONLY THE TRAINING SPAN CHANGES. Val is untouched (2026-05-01 -> 07-17: QTREE's
iteration count and CQR's calibration, as always). Held out is untouched. Every
hyperparameter is untouched. What follows from a smaller train, stated rather
than hidden: Climatology's quantiles come from the window; Linear QR and kNN
standardise on the window's train rows; kNN draws its 200 neighbours from the
smaller pool.

SCOPE. The full registry, as standing instruction: all five models, five
horizons, both directions, on the current best config (MAE on vol_48_1m, MFE on
vol_48, rest unchanged). 50 cells, each scored on HO1 and HO2 separately: 100.
Full-history predictions are the cached registry (fingerprint-checked). The
pipeline is checked by rebuilding the full-history context through this
script's own builder and requiring QTREE to reproduce the cache exactly.

METRICS, per cell and half, PAIRED (window - full) on identical rows and day
resamples, day-clustered within each half: calibration gap (pp, - = tighter)
and skill (points). Skill uses ONE fixed denominator for both versions: the
cached full-history Climatology. So the window's Climatology is scored as a
model like any other, and its row says whether the unconditional envelope alone
gains from recency.

THE RULE, fixed before the run. Per cell and half: TIGHTER if the paired gap
difference's interval is entirely below zero; LOOSER if entirely above; SAME
otherwise.
  RECENCY MATTERS  on HO2, TIGHTER in a majority of the 50 cells (26 or more)
                   AND LOOSER in at most 2 (chance alone gives ~1.25 at 2.5%)
                   -> the full walk-forward build is justified next
  SAME OR WORSE    anything else -> recency alone does not fix this; the
                   earlier inconclusive recurrence result stands
Gaps filled: the brief's "meaningfully tighter, especially on HO2" is read as
the HO2 gate above; HO1 and skill are reported beside it, not gated. The
walk-forward build is the next item, not done here.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

import harness
import paths
from envelope import (HLABEL, HORIZONS, HO_BOUNDARY, KNN_K, LINEAR_FALLBACKS,
                      REGISTRY_UNTIL_2026_10_12, day_boot, enforce_two_pass, fit_qtree, gap_ci,
                      gap_paired_ci, scan_1m_coverage, select_1m_subset, skill_ci)
from newfeat import load_baselines
from vol1m import paired_skill_ci

WSTART = np.datetime64("2025-10-18")      # 9 months before harness.CUT (2026-07-18)
# Pinned to the five-model registry ROLLING-WINDOW was published on, so a rerun
# reproduces it after REGISTRY-CONSOLIDATED cut the standing registry to three.
MODELS = REGISTRY_UNTIL_2026_10_12


def window_context(X, day, y_entry, start):
    """build_context's split and outputs, with TRAIN restricted to day >= start.

    harness.Split is built on the full population exactly as build_context
    does, so val and held out are identical; only the train mask is cut.
    start=None reproduces build_context.
    """
    sp = harness.Split(day, y_entry)
    train = sp.train & (day >= start) if start is not None else sp.train.copy()
    mu = X[train].mean(0)
    sd = X[train].std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    nn = NearestNeighbors(n_neighbors=KNN_K).fit(Z[train])
    knn = nn.kneighbors(Z[sp.test], return_distance=False)
    return dict(sub=np.arange(len(day)), sp=sp, fit=sp.fit, train=train, val=sp.val,
                test=sp.test, Xtr=X[train], Xva=X[sp.val], Xte=X[sp.test],
                Ztr=Z[train], Zva=Z[sp.val], Zte=Z[sp.test], n_test=sp.n_test,
                knn=knn, day_test=day[sp.test])


def main():
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    day_all = meta.day.to_numpy()

    print("=" * 112)
    print("ROLLING-WINDOW -- trailing 9-month train vs full history, full registry, HO1/HO2")
    print("=" * 112)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], rows):
        raise SystemExit("[ROLL] vol48_1m.npz rows differ from the population.")
    T1M, base = load_baselines(Y, meta, X, names, rows, v48)
    day = day_all[rows]
    ye = Y[rows, 0]

    # ---- spans ----
    sp = harness.Split(day, ye)
    win = sp.train & (day >= WSTART)
    span = lambda m: (f"{str(day[m].min())[:10]} -> {str(day[m].max())[:10]}, "
                      f"{int(m.sum()):,} rows, {len(np.unique(day[m]))} days")
    print(f"  full train   {span(sp.train)}")
    print(f"  window train {span(win)}  ({100*win.sum()/sp.train.sum():.1f}% of full train)")
    print(f"  dropped      {span(sp.train & ~win)}")
    print(f"  val          {span(sp.val)}  (unchanged)")
    print(f"  held out     {span(sp.test)}  (unchanged)")
    fit_days = (pd.Timestamp(day[sp.fit].max()) - pd.Timestamp(day[sp.fit].min())).days
    print(f"  full fit block spans {fit_days} days (the brief assumed ~667)")
    print()

    # ---- pipeline check: this builder at full history reproduces the cache ----
    for d in ("MFE", "MAE"):
        Xb, cb, _ = base[d]
        ctx = window_context(Xb, day, ye, None)
        enf, _, _ = enforce_two_pass(np.stack([fit_qtree(ctx, T1M[(d, k)]) for k in HORIZONS]))
        err = max(float(np.max(np.abs(enf[i] - cb[f"1m|{d}|QTREE|{k}"])))
                  for i, k in enumerate(HORIZONS))
        print(f"  check: full-history QTREE {d} via this builder vs cache, worst {err:.1e}")
        if err > 1e-12:
            raise SystemExit("[ROLL] the builder does not reproduce the registry.")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- window refit, all five models ----
    res = {}
    for d in ("MFE", "MAE"):
        Xb, cb, _ = base[d]
        ctx = window_context(Xb, day, ye, WSTART)
        dte = ctx["day_test"]
        h1 = dte < HO_BOUNDARY
        halves = {"HO1": (np.flatnonzero(h1), day_boot(dte[h1])),
                  "HO2": (np.flatnonzero(~h1), day_boot(dte[~h1]))}
        for mn, fn in MODELS:
            enf, _, _ = enforce_two_pass(np.stack(
                [fn(ctx, T1M[(d, k)], f"1m/{d}/{HLABEL[k]}/window") for k in HORIZONS]))
            for i, k in enumerate(HORIZONS):
                yt = T1M[(d, k)][ctx["test"]]
                old = cb[f"1m|{d}|{mn}|{k}"]
                clim = cb[f"1m|{d}|Climatology|{k}"]
                for hn, (ix, bt) in halves.items():
                    y, o, n, c = yt[ix], old[ix], enf[i][ix], clim[ix]
                    dg = gap_paired_ci(y, o, y, n, bt)
                    res[(mn, d, k, hn)] = dict(
                        go=gap_ci(y, o, bt)[0], gn=gap_ci(y, n, bt)[0], dg=dg,
                        so=skill_ci(y, o, c, bt)[0], sn=skill_ci(y, n, c, bt)[0],
                        ds=paired_skill_ci(y, o, n, c, bt),
                        tag="TIGHTER" if dg[2] < 0 else "LOOSER" if dg[1] > 0 else "SAME")
            print(f"  refitted {mn:<12}{d} on the window, five horizons   "
                  f"[{time.time()-t0:.0f}s]", flush=True)
        if d == "MFE":
            for hn, (ix, _) in halves.items():
                print(f"    {hn}: {len(ix):,} held-out rows, {len(np.unique(dte[ix]))} days")
    print(f"  Linear QR LP fallbacks (alpha > 0): {len(LINEAR_FALLBACKS)}")
    print()

    print("=" * 112)
    print("PAIRED, window - full -- gap: - = window tighter; skill: + = window better")
    print("(skill denominator: cached full-history Climatology, the same for both)")
    print("=" * 112)
    for hn in ("HO1", "HO2"):
        print(f"  ---- {hn} ----")
        print(f"  {'model':<12}{'cell':<10}{'gap full':>9}{'window':>8}{'w - f':>8}"
              f"{'[95% CI]':>18}{'':>9}{'skill full':>11}{'window':>8}{'w - f':>8}"
              f"{'[95% CI]':>18}")
        for mn, _ in MODELS:
            for d in ("MFE", "MAE"):
                for k in HORIZONS:
                    r = res[(mn, d, k, hn)]
                    dg, ds = r["dg"], r["ds"]
                    print(f"  {mn:<12}{d+' '+HLABEL[k]:<10}{r['go']:>9.2f}{r['gn']:>8.2f}"
                          f"{dg[0]:>+8.3f}{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}"
                          f"{r['tag']:>9}{r['so']:>+11.2f}{r['sn']:>+8.2f}{ds[0]:>+8.3f}"
                          f"{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}")
        print()

    print("=" * 112)
    print("COUNTS -- gap, per half")
    print("=" * 112)
    print(f"  {'model':<12}{'dir':<5}" + "".join(f"{h+' '+t:>12}" for h in ("HO1", "HO2")
                                                for t in ("tighter", "looser")))
    for mn, _ in MODELS:
        for d in ("MFE", "MAE"):
            cs = [sum(res[(mn, d, k, h)]["tag"] == t for k in HORIZONS)
                  for h in ("HO1", "HO2") for t in ("TIGHTER", "LOOSER")]
            print(f"  {mn:<12}{d:<5}" + "".join(f"{c:>12}" for c in cs))
    tot = {(h, t): sum(r["tag"] == t for (mn, d, k, hh), r in res.items() if hh == h)
           for h in ("HO1", "HO2") for t in ("TIGHTER", "LOOSER", "SAME")}
    for h in ("HO1", "HO2"):
        sk = [r["ds"] for (mn, d, k, hh), r in res.items() if hh == h]
        print(f"  {h} all 50: TIGHTER {tot[(h,'TIGHTER')]}, LOOSER {tot[(h,'LOOSER')]}, "
              f"SAME {tot[(h,'SAME')]};  skill sig. better {sum(s[1] > 0 for s in sk)}, "
              f"sig. worse {sum(s[2] < 0 for s in sk)}")
    print()

    print("=" * 112)
    print("DECISION -- rule fixed in the module docstring before the run")
    print("=" * 112)
    t2, l2 = tot[("HO2", "TIGHTER")], tot[("HO2", "LOOSER")]
    ok = t2 >= 26 and l2 <= 2
    print(f"  HO2: TIGHTER {t2} of 50 (need 26), LOOSER {l2} (allowed 2)")
    print(f"  VERDICT: {'RECENCY MATTERS -- the walk-forward build is justified next' if ok else 'SAME OR WORSE -- recency alone does not fix this'}")
    print("  The window drops only the oldest ~21% of train: a mild contrast.")
    print("  Levels are a later look at already-scored rows; paired differences are")
    print("  the measurement. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    main()
