"""DELAYED DECISION: who reverts, given the first 30-60 minutes after initial detection?

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/delayed.py --stage paths > .../logs/delayed_paths.log 2>&1
    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/delayed.py --stage models > .../logs/delayed.log 2>&1

VOCABULARY. Initial detection (t0) = the bar where the episode first crosses 3
sigma (earlier work's "entry"). Decision point d = t0 + 30 or t0 + 60
minutes. Minute k = k minutes after t0's close; seg[:, k-1] is the signed move
toward mu at minute k in frozen-sigma units (reachmu.stage_paths' seg, mu and
sigma frozen at t0). need = |z at t0|.

POPULATION at each d (the matched 53,757, harness.Split by t0):
  already reverted  reached mu at or before minute d (t_reach <= d). Counted,
                    set aside.
  dropped           any missing path minute in 1..d. Counted, set aside.
  still open        the rest. Target reach_d = reaches mu at some minute in
                    (d, 600]. Base rate and median minutes to mu (from t0 and
                    from d) per split.

FEATURES AT d (nothing past minute d; audited per row):
  t0      the REACH-MU-V2 kept set, unchanged (14 groups, 24 columns, read
          from reachmu.assemble_features by the logged group list; asserted
          24).
  path    over minutes 1..d:
    dist_now          need - seg[d]
    worst_so_far      max(-seg)
    best_so_far       max(seg)
    mins_since_worst  d - the minute worst_so_far was set (first occurrence)
    bounce_from_worst seg[d] + worst_so_far
    slope_10          seg[d] - seg[d-10]
    path_vol          sd (ddof 1) of the 1-minute changes of seg within 1..d
    new_lows          minutes k in 1..d where -seg[k] exceeds every earlier
                      value, starting from 0 at t0's close (a new adverse
                      extreme beyond the t0 close)
    new_lows_late     the same count for k in the last third (k > 2d/3)
  volume since t0, each leg: log( summed 1-minute volume over minutes 1..d /
          the median d-minute block sum over the 7 days before t0's close ).
          Blocks need 80% finite minutes; the window needs 80% too, else
          missing. vol_since_dom, vol_since_oth (whyfeat's 12-bar dominant
          leg, market factor recomputed) and vol_since_ratio = dom - oth.
  Gap filled, fixed, not tuned (logistic heavy tails, as before): log on
  path_vol, log1p on new_lows and new_lows_late. Missing -> TRAIN median,
  counted. Spearman of each path feature with dist_now and vol_48_1m.

MODELS at each d (fitted on train of the still-open; every setting on val by
log loss): random (analytic); vol-only (vol_48, vol_48_1m, sigma); position
(vol-only + dist_now, THE BAR); t0 model (kept set); full (kept + dist_now +
path + volume since t0). Each as logistic L1 (C over reachmu.C_GRID); full
also as LightGBM gbdt at depths 1, 2, 3, 4, 6, num_leaves 2^d,
min_data_in_leaf over {20, 50, 100, 400, 1000}, lr 0.05, rounds by early
stopping on val. Gap filled: "the full model" in the tests, importance,
profile and chance bar is the full model with the lowest val log loss among
its L1 and five trees (one comparison per test).

SCORING, held out only, HO1 and HO2 separately, each d: flag share and hit rate
at 50/80/90% catch of still-open reverters and the top-20% hit rate, every
model. Paired day-clustered 95% intervals on flag share at 80% catch: full -
position (THE TEST), full - t0, and position - vol-only (how much is
dist_now alone). CHANCE BAR (reading only; never a feature): each still-open
episode's 1-minute increments from minute d on get random signs (whyscreen's
construction, missing minutes bridged), 50 seeds (1000..1049); share
reaching mu in (d, 600]. Mean vs real reach_d in total and in the full
model's top 20%; the top-20% beyond-chance gap gets a day-clustered interval.
Grouped permutation importance (held out, 20 shuffles, log-loss skill points,
per-half intervals) for the full model; groups: t0 features, dist_now, path
shape (worst, best, bounce, mins_since_worst), path momentum (slope_10,
new_lows, new_lows_late), path_vol, volume since t0. PROFILE: medians of each
path and volume feature (untransformed) in the full model's top 20% against
its bottom 50%, per half.

SAME-LEARNER DIAGNOSTICS (added after review; reported, NOT gating). The brief
fits position and the t0 model as logistic L1 only, while "full" may be
represented by a tree, so THE TEST could credit the path with what a tree gets
from vol + dist_now alone (reach_d is plausibly a nonlinear function of
dist_now / vol). Keeping the brief's test as written, the script also fits
position and the t0 model with the same tree grid (reporting only), and
prints: full L1 - position L1, best full tree - best position tree, and the
same for the t0 model. If the gating test and these disagree, it goes to the
user. Chosen min_data_in_leaf at the grid edge (20 or 1000) is flagged.

READING RULES (the brief's, fixed; "clears" = the 95% interval excludes zero):
  FOUND SOMETHING: full - position on flag share at 80% catch, interval wholly
    below zero in BOTH HO1 and HO2, at d = 30 or d = 60.
  STRONG: the full model's flag-share interval at 80% catch wholly below 0.5
    AND its top-20% beyond-chance gap interval wholly above zero, both halves.
  REGIME-DEPENDENT: FOUND SOMETHING's test clears in exactly one half at a d;
    reported, not a pass.
Pruning rule going forward (recorded, not applied here): drop a group unless
some model's interval is wholly above zero. Nothing is re-pruned.
No stop. Nothing written to the registry or the live system.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import harness
import paths
from envelope import HO_BOUNDARY, day_boot, load_1m_series, one_min_paths
from reachmu import (C_GRID, PATHS_OUT, assemble_features, flag_share, logloss_rows, population,
                     reach_group, top_set, tree_shape)

DS = (30, 60)
OUT = os.path.join(paths.DATASETS, "delayed_paths.npz")
KEPT = ("vol_48", "vratio", "vol_slope", "sandwich", "off_mark", "common_share", "vol_spike_mover",
        "vol_spike_ratio", "lagger_spread", "abs_z", "beta", "r2", "sigma", "weekday")
PATH_F = ("dist_now", "worst_so_far", "best_so_far", "mins_since_worst", "bounce_from_worst",
          "slope_10", "path_vol", "new_lows", "new_lows_late")
VOL_F = ("vol_since_dom", "vol_since_oth", "vol_since_ratio")
GROUPS = {"dist_now": ("dist_now",),
          "path shape": ("worst_so_far", "best_so_far", "bounce_from_worst", "mins_since_worst"),
          "path momentum": ("slope_10", "new_lows", "new_lows_late"),
          "path_vol": ("path_vol",), "volume since t0": VOL_F}
MIN7 = 7 * 24 * 60
SEEDS = range(1000, 1050)
MDL = (20, 50, 100, 400, 1000)
DEPTHS = (1, 2, 3, 4, 6)
LR = 0.05
THREADS = 6
N_SHUF = 20
SEED = 20261013
CATCH = (0.5, 0.8, 0.9)


# ====================================================================== paths
def stage_paths():
    from whyfeat import LOOKS, load_1m_volume, market_factor
    import universe_panel
    t0 = time.time()
    Y, meta, rows = population()
    PZ = np.load(PATHS_OUT)
    if not np.array_equal(PZ["rows"], rows):
        raise SystemExit("[DELAY] reach_paths.npz rows differ.")
    reach, t_reach = PZ["reach"], PZ["t_reach"]
    e = Y[rows, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    need = np.abs(e)
    series = load_1m_series(sorted(set(meta.ticker_a.iloc[rows]) | set(meta.ticker_b.iloc[rows])), False)
    P, _ = one_min_paths(meta, rows, series)
    del series
    move = -(P - e[:, None]) * s[:, None]
    del P
    seg = move[:, 1:601]
    # reproduce the saved target exactly
    depth = np.nanmax(seg, 1)
    if not (np.array_equal(depth >= need, reach) and np.array_equal(depth, PZ["depth"])):
        raise SystemExit("[DELAY] the path does not reproduce reach_paths.npz.")
    print(f"  paths rebuilt; reach and depth reproduce reach_paths.npz exactly   [{time.time()-t0:.0f}s]", flush=True)
    out = {"rows": rows}
    fin = np.isfinite(move)
    last = pd.DataFrame(move).ffill(axis=1).to_numpy()
    prevv = np.concatenate([np.zeros((len(move), 1)), last[:, :-1]], axis=1)
    inc = np.where(fin, move - prevv, 0.0)
    inc[:, 0] = 0.0
    del last, prevv
    for d in DS:
        S = seg[:, :d]
        rev = reach & (t_reach <= d)
        miss = ~np.isfinite(S).all(1)
        openm = ~rev & ~miss
        reach_d = reach & (t_reach > d)
        k = np.arange(1, d + 1)
        adv = -S
        F = {}
        F["dist_now"] = need - S[:, d - 1]
        F["worst_so_far"] = adv.max(1)
        F["best_so_far"] = S.max(1)
        F["mins_since_worst"] = (d - (adv.argmax(1) + 1)).astype(float)
        F["bounce_from_worst"] = S[:, d - 1] + F["worst_so_far"]
        F["slope_10"] = S[:, d - 1] - S[:, d - 11]
        F["path_vol"] = np.std(np.diff(S, axis=1), axis=1, ddof=1)
        run = np.maximum.accumulate(np.concatenate([np.zeros((len(S), 1)), adv], 1), 1)
        newlow = adv > run[:, :-1]
        F["new_lows"] = newlow.sum(1).astype(float)
        F["new_lows_late"] = newlow[:, k > 2 * d / 3].sum(1).astype(float)
        for nm, v in F.items():
            out[f"{nm}_{d}"] = np.where(openm, v, np.nan)
        out[f"open_{d}"] = openm
        out[f"rev_{d}"] = rev
        out[f"miss_{d}"] = miss
        out[f"reach_{d}"] = reach_d
        # chance bar from minute d on
        hits = np.zeros(len(rows))
        base = S[:, d - 1]
        incd = inc[:, d + 1:601]
        find = fin[:, d + 1:601]
        for sd in SEEDS:
            sg = np.random.default_rng(sd).choice([-1.0, 1.0], size=incd.shape)
            pth = base[:, None] + np.cumsum(sg * incd, axis=1)
            pth[~find] = np.nan
            hits += np.nanmax(np.where(np.isfinite(pth), pth, -np.inf), 1) >= need
            del sg, pth
        out[f"chance_{d}"] = np.where(openm, hits / len(SEEDS), np.nan)
        print(f"  d={d}: reverted by d {int(rev.sum()):,}, dropped (missing minutes) {int((miss & ~rev).sum()):,}, "
              f"still open {int(openm.sum()):,}, reach_d {int((reach_d & openm).sum()):,}; chance mean "
              f"{np.nanmean(out[f'chance_{d}']):.4f}   [{time.time()-t0:.0f}s]", flush=True)
    out["audit_path_max_minute"] = np.array(max(DS))        # S = seg[:, :d] -> minute d at most
    del S, adv, run, newlow, incd, find, move, seg, inc, fin    # S is a view of move: free both

    # volume since t0, per leg, then dominant / other
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    cols = list(panel.columns)
    ixc = {c: k_ for k_, c in enumerate(cols)}
    LC = panel.to_numpy(float)
    _, resid, _, _, _, _ = market_factor(LC)
    J = meta.bar_index.to_numpy(int)[rows]
    ja = meta.ticker_a.map(ixc).to_numpy(int)[rows]
    jb = meta.ticker_b.map(ixc).to_numpy(int)[rows]
    beta = meta.beta.to_numpy(float)[rows]
    L = 12
    I = J[:, None] + np.arange(-L + 1, 1)[None, :]
    ra, rb = resid[I, ja[:, None]], resid[I, jb[:, None]]
    domA = np.abs(ra.sum(1)) >= np.abs(-beta * rb.sum(1))
    undef = ~(np.isfinite(ra).all(1) & np.isfinite(rb).all(1))
    del resid
    print(f"  dominance (whyfeat, 12-bar) recomputed; undefined {int(undef.sum()):,}   [{time.time()-t0:.0f}s]", flush=True)
    lastm = pd.to_datetime(meta.entry_time.to_numpy()[rows]).to_numpy().astype("datetime64[m]") + np.timedelta64(29, "m")
    VS = {(leg, d): np.full(len(rows), np.nan) for leg in ("a", "b") for d in DS}
    maxread = -10 ** 9
    ta, tb = meta.ticker_a.to_numpy()[rows], meta.ticker_b.to_numpy()[rows]
    for tk in sorted(set(ta) | set(tb)):
        tz, vol, _ = load_1m_volume(tk)
        for leg, tt in (("a", ta), ("b", tb)):
            rr = np.flatnonzero(tt == tk)
            if not len(rr):
                continue
            endo = ((lastm[rr] - tz) / np.timedelta64(1, "m")).astype(np.int64)   # t0's close minute
            Bi = endo[:, None] + np.arange(-MIN7 + 1, 1)[None, :]
            okb = (Bi >= 0) & (Bi < len(vol))
            vb = np.where(okb, vol[np.clip(Bi, 0, len(vol) - 1)], np.nan)
            for d in DS:
                Wi = endo[:, None] + np.arange(1, d + 1)[None, :]
                okw = (Wi >= 0) & (Wi < len(vol))
                vw = np.where(okw, vol[np.clip(Wi, 0, len(vol) - 1)], np.nan)
                maxread = max(maxread, int((Wi.max(1) - endo).max()))
                blk = vb.reshape(len(rr), MIN7 // d, d)
                bs = np.where(np.isfinite(blk).sum(2) >= 0.8 * d, np.nansum(blk, 2), np.nan)
                with np.errstate(invalid="ignore", divide="ignore"):
                    med = np.nanmedian(bs, 1)
                    ws = np.where(np.isfinite(vw).sum(1) >= 0.8 * d, np.nansum(vw, 1), np.nan)
                    r_ = ws / med
                    VS[(leg, d)][rr] = np.where(r_ > 0, np.log(r_), np.nan)
    print(f"  volume since t0 built; latest minute read = t0 close + {maxread} (must be <= max d = {max(DS)})   "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if maxread > max(DS):
        raise SystemExit("[DELAY] volume since t0 reads past d.")
    for d in DS:
        a, b = VS[("a", d)], VS[("b", d)]
        dv, ov = np.where(domA, a, b), np.where(domA, b, a)
        dv[undef], ov[undef] = np.nan, np.nan
        openm = out[f"open_{d}"]
        out[f"vol_since_dom_{d}"] = np.where(openm, dv, np.nan)
        out[f"vol_since_oth_{d}"] = np.where(openm, ov, np.nan)
        out[f"vol_since_ratio_{d}"] = np.where(openm, dv - ov, np.nan)
    out["audit_vol_max_minute"] = np.array(maxread)
    np.savez_compressed(OUT, **out)
    print(f"  [WROTE] {os.path.relpath(OUT, paths.RESEARCH)}   [{time.time()-t0:.0f}s]")


# ===================================================================== models
def path_features(D, d, rr, tr):
    """The path and volume-since-t0 features at d on rows rr: (raw, transformed and
    TRAIN-median filled, missing-count message). One definition, shared with
    delayed2.py. Transforms: log path_vol, log1p new_lows and new_lows_late."""
    raw = {nm: D[f"{nm}_{d}"][rr].astype(float) for nm in PATH_F + VOL_F}
    tf = {}
    for nm, v in raw.items():
        v = v.copy()
        if nm == "path_vol":
            v = np.where(v > 0, np.log(v), np.nan)
        elif nm in ("new_lows", "new_lows_late"):
            v = np.log1p(v)
        tf[nm] = v
    mc = ";  ".join(f"{nm} {int((~np.isfinite(v)).sum())}" for nm, v in tf.items() if (~np.isfinite(v)).any())
    for nm, v in tf.items():
        v[~np.isfinite(v)] = np.nanmedian(v[tr])
    return raw, tf, mc


def fit_l1(Z, y, tr, va):
    from sklearn.linear_model import LogisticRegression
    best = None
    for C in C_GRID:
        # seeded from 2026-10-13 (user-approved): unseeded liblinear shuffles randomly, ~1e-5 wobble
        m = LogisticRegression(penalty="l1", C=C, solver="liblinear", max_iter=5000,
                               random_state=0).fit(Z[tr], y[tr])
        ll = logloss_rows(y[va], m.predict_proba(Z[va])[:, 1]).mean()
        if best is None or ll < best[0]:
            best = (ll, m, C)
    return best


def stage_models():
    import lightgbm as lgb
    t0 = time.time()
    Y, meta, rows = population()
    D = np.load(OUT)
    if not np.array_equal(D["rows"], rows):
        raise SystemExit("[DELAY] delayed_paths.npz rows differ.")
    PZ = np.load(PATHS_OUT)
    t_reach = PZ["t_reach"]
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    sp = harness.Split(day, e)
    names, X0, _ = assemble_features(meta, rows, e, sp.train)
    kcols = [j for j, nm in enumerate(names) if reach_group(nm) in KEPT]
    if len(kcols) != 24:
        raise SystemExit(f"[DELAY] kept set has {len(kcols)} columns, expected 24.")
    kn = [names[j] for j in kcols]
    ix0 = {nm: j for j, nm in enumerate(names)}
    v48_1m_raw = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))["vol_48_1m"]
    print("=" * 120)
    print("DELAYED DECISION -- who reverts, given the first 30-60 minutes after initial detection (t0)?")
    print("=" * 120)
    print(f"  {sp.describe()}")
    print(f"  path audit: path features read minutes 1..d only (max minute {int(D['audit_path_max_minute'])} at d=60); "
          f"volume since t0 reads up to t0 close + {int(D['audit_vol_max_minute'])} min")
    allsplits = (("train", sp.train), ("val", sp.val), ("HO1", sp.test & (day < HO_BOUNDARY)),
                 ("HO2", sp.test & (day >= HO_BOUNDARY)))
    verdicts = {}
    for d in DS:
        print()
        print("#" * 120)
        print(f"DECISION POINT d = t0 + {d} min")
        print("#" * 120)
        openm, rev, miss = D[f"open_{d}"], D[f"rev_{d}"], D[f"miss_{d}"]
        y_all = D[f"reach_{d}"].astype(int)
        print("  STEP 0 -- populations")
        for lbl, m in allsplits:
            o = m & openm
            yy = y_all[o]
            tr_ = t_reach[o & (y_all == 1)]
            print(f"    {lbl:<6} episodes {int(m.sum()):>6,}  already reverted {int((m & rev).sum()):>4,}  "
                  f"dropped (missing minutes) {int((m & miss & ~rev).sum()):>3,}  still open {int(o.sum()):>6,}  "
                  f"reach_d {yy.mean():.4f}  median minutes to mu: from t0 {np.median(tr_):.0f}, from d {np.median(tr_) - d:.0f}")
        rr = np.flatnonzero(openm)
        y = y_all[rr]
        tr, va, te = sp.train[rr], sp.val[rr], sp.test[rr]
        dd = day[rr]
        halves = {"HO1": np.flatnonzero(te & (dd < HO_BOUNDARY)), "HO2": np.flatnonzero(te & (dd >= HO_BOUNDARY))}
        # features
        raw, tf, mc = path_features(D, d, rr, tr)
        print("  STEP 1 -- features at d; missing -> TRAIN median: " + (mc or "none"))
        print("    Spearman (still open) with dist_now / vol_48_1m:")
        for nm in PATH_F + VOL_F:
            a = pd.Series(raw[nm]).corr(pd.Series(raw["dist_now"]), method="spearman")
            b = pd.Series(raw[nm]).corr(pd.Series(v48_1m_raw[rr]), method="spearman")
            print(f"      {nm:<18} {a:+.3f} / {b:+.3f}")
        XK = X0[rr][:, kcols]
        vol3 = X0[rr][:, [ix0["vol_48"], ix0["vol_48_1m"], ix0["sigma"]]]
        sets = {"vol-only": (vol3, ["vol_48", "vol_48_1m", "sigma"]),
                "position": (np.column_stack([vol3, tf["dist_now"]]), ["vol_48", "vol_48_1m", "sigma", "dist_now"]),
                "t0 model": (XK, kn),
                "full": (np.column_stack([XK] + [tf[nm] for nm in PATH_F + VOL_F]), kn + list(PATH_F + VOL_F))}
        # models
        print("  STEP 2 -- models (train; settings on val by log loss)")
        score, vll, fns = {}, {}, {}
        for sn, (Xs, ns) in sets.items():
            mu_, sd_ = Xs[tr].mean(0), Xs[tr].std(0)
            sd_[sd_ == 0] = 1.0
            Zs = (Xs - mu_) / sd_
            ll_, m_, C_ = fit_l1(Zs, y, tr, va)
            k_ = f"{sn} L1"
            score[k_], vll[k_] = m_.predict_proba(Zs)[:, 1], ll_
            fns[k_] = (lambda M_, m=m_, a=mu_, b=sd_: m.predict_proba((M_ - a) / b)[:, 1])
            print(f"    {k_:<14} val log loss {ll_:.5f}  C {C_}, nonzero {int((m_.coef_ != 0).sum())} of {len(ns)}")
        Xf, nf = sets["full"]
        for sn_ in ("position", "t0 model", "full"):
            Xt_, nt_ = sets[sn_]
            for dep in DEPTHS:
                best = None
                for mdl in MDL:
                    p = dict(objective="binary", metric="binary_logloss", seed=0, deterministic=True,
                             force_row_wise=True, num_threads=THREADS, verbosity=-1, boosting="gbdt",
                             max_depth=dep, num_leaves=2 ** dep, min_data_in_leaf=mdl, learning_rate=LR)
                    dtr = lgb.Dataset(Xt_[tr], y[tr], feature_name=nt_)
                    dva = lgb.Dataset(Xt_[va], y[va], reference=dtr)
                    bst = lgb.train(p, dtr, 5000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
                    it = bst.best_iteration
                    ll_ = logloss_rows(y[va], bst.predict(Xt_[va], num_iteration=it)).mean()
                    if best is None or ll_ < best[0]:
                        best = (ll_, bst, it, mdl)
                ll_, bst, it, mdl = best
                k_ = f"{sn_} d{dep}"
                score[k_], vll[k_] = bst.predict(Xt_, num_iteration=it), ll_
                fns[k_] = (lambda M_, b=bst, i=it: b.predict(M_, num_iteration=i))
                nt, dm, dmean, lm, lmean = tree_shape(lgb.Booster(model_str=bst.model_to_string(num_iteration=it)))
                edge = "   <- GRID EDGE" if mdl in (MDL[0], MDL[-1]) else ""
                print(f"    {k_:<16} val log loss {ll_:.5f}  min_data_in_leaf {mdl}, rounds {it}; depth max {dm} "
                      f"(mean {dmean:.2f}), leaves max {lm} (mean {lmean:.1f}){edge}   [{time.time()-t0:.0f}s]", flush=True)
        full = min([k for k in vll if k.startswith("full")], key=lambda k: vll[k])
        btree = {sn_: min([k for k in vll if k.startswith(sn_ + " d")], key=lambda k: vll[k])
                 for sn_ in ("position", "t0 model", "full")}
        print(f"    -> the full model at d={d} is {full} (lowest val log loss); best trees (diagnostics): "
              + ", ".join(f"{k} {v}" for k, v in btree.items()))

        # scoring
        print("  STEP 3 -- scoring, held out only")
        order = (["vol-only L1", "position L1", "t0 model L1"] + [k for k in score if k.startswith("full")]
                 + [btree["position"], btree["t0 model"]])
        res = {}
        for hn, ixh in halves.items():
            yh = y[ixh]
            print(f"    {hn}: still open {len(ixh):,}, reverters {int(yh.sum()):,} ({yh.mean():.4f})")
            print(f"      {'model':<16}" + "".join(f"{f'catch {int(100*c)}%: flag / hit':>28}" for c in CATCH) + f"{'top20 hit':>11}")
            print(f"      {'random':<16}" + "".join(f"{f'{c:.3f} / {yh.mean():.3f}':>28}" for c in CATCH) + f"{yh.mean():>11.3f}")
            for mn in order:
                sc = score[mn][ixh]
                cat = [flag_share(sc, yh, c)[:2] for c in CATCH]
                th = yh[top_set(sc, 0.2)].mean()
                res[(hn, mn)] = (cat, th)
                print(f"      {mn:<16}" + "".join(f"{f'{a:.3f} / {b:.3f}':>28}" for a, b in cat) + f"{th:>11.3f}"
                      + ("   <- full" if mn == full else ""))
        hboot = {hn: day_boot(dd[ixh]) for hn, ixh in halves.items()}

        def paired(a, b, hn):
            ixh = halves[hn]
            yh, sa, sb = y[ixh], score[a][ixh], score[b][ixh]
            f = lambda sc, yy: flag_share(sc, yy, 0.8)[0]
            dr = [f(sa[i_], yh[i_]) - f(sb[i_], yh[i_]) for i_ in hboot[hn]]
            return (f(sa, yh) - f(sb, yh), *np.percentile(dr, [2.5, 97.5]))
        print("    PAIRED flag share at 80% catch, day-clustered 95% (A minus B; - = A needs fewer flags)")
        P_ = {}
        for lbl, a, b in (("full - position  [THE TEST]", full, "position L1"),
                          ("full - t0 model", full, "t0 model L1"),
                          ("position - vol-only  [dist_now alone]", "position L1", "vol-only L1"),
                          ("full - vol-only", full, "vol-only L1"),
                          ("full L1 - position L1  [diag]", "full L1", "position L1"),
                          ("best full tree - best position tree  [diag]", btree["full"], btree["position"]),
                          ("full L1 - t0 model L1  [diag]", "full L1", "t0 model L1"),
                          ("best full tree - best t0 tree  [diag]", btree["full"], btree["t0 model"])):
            cells = []
            for hn in halves:
                r_ = paired(a, b, hn)
                P_[(lbl, hn)] = r_
                cells.append(f"{hn} {r_[0]:+.4f} [{r_[1]:+.4f},{r_[2]:+.4f}]"
                             + ("*" if r_[2] < 0 else "!" if r_[1] > 0 else " "))
            print(f"      {lbl:<46}" + "   ".join(cells))
        # chance bar
        ch = D[f"chance_{d}"][rr]
        print("    CHANCE BAR (reading only): real reach_d vs mean sign-flip probability from minute d")
        lev = {}
        for hn, ixh in halves.items():
            yh, chh, sc = y[ixh], ch[ixh], score[full][ixh]
            tp = top_set(sc, 0.2)
            fs80 = lambda s_, y_, c_: (flag_share(s_, y_, 0.8)[0],
                                       y_[top_set(s_, 0.2)].mean() - c_[top_set(s_, 0.2)].mean())
            pt = fs80(sc, yh, chh)
            dr = np.array([fs80(sc[i_], yh[i_], chh[i_]) for i_ in hboot[hn]])
            ci = np.percentile(dr, [2.5, 97.5], axis=0)
            lev[hn] = (pt, ci)
            print(f"      {hn}: all still open real {yh.mean():.4f} vs chance {chh.mean():.4f} (gap {yh.mean()-chh.mean():+.4f});"
                  f"  full top 20% real {yh[tp].mean():.4f} vs chance {chh[tp].mean():.4f} "
                  f"(gap {pt[1]:+.4f} [{ci[0][1]:+.4f}, {ci[1][1]:+.4f}]);  full flag share at 80% catch "
                  f"{pt[0]:.4f} [{ci[0][0]:.4f}, {ci[1][0]:.4f}]")
        # importance
        print(f"    IMPORTANCE, held out, {full}; {N_SHUF} shuffles; log-loss skill points lost; per-half 95%")
        gidx = {"t0 features": list(range(len(kn)))}
        for g, mem in GROUPS.items():
            gidx[g] = [nf.index(m) for m in mem]
        teix = np.flatnonzero(te)
        lc = logloss_rows(y[teix], np.full(len(teix), y[tr].mean()))
        fn = fns[full]
        base_l = logloss_rows(y[teix], fn(Xf[teix]))
        pos = {"held out": np.arange(len(teix))}
        for hn, ixh in halves.items():
            pos[hn] = np.flatnonzero(np.isin(teix, ixh))
        for gi, (g, js) in enumerate(gidx.items()):
            acc = np.zeros(len(teix))
            for s_ in range(N_SHUF):
                perm = np.random.default_rng([SEED, d, gi, s_]).permutation(len(teix))
                Xp = Xf[teix].copy()
                Xp[:, js] = Xf[teix][perm][:, js]
                acc += logloss_rows(y[teix], fn(Xp)) - base_l
            acc /= N_SHUF
            cells = []
            for bn, p_ in pos.items():
                bt = day_boot(dd[teix][p_])
                a_, c_ = acc[p_], lc[p_]
                dr = [100 * a_[i_].mean() / c_[i_].mean() for i_ in bt]
                lo, hi = np.percentile(dr, [2.5, 97.5])
                cells.append(f"{bn} {100*a_.mean()/c_.mean():+.4f} [{lo:+.4f},{hi:+.4f}]{'+' if lo > 0 else ' '}")
            print(f"      {g:<18}" + "   ".join(cells))
        # profile
        print("    PROFILE -- medians, full model's top 20% vs bottom 50% (untransformed)")
        for hn, ixh in halves.items():
            sc = score[full][ixh]
            o = np.argsort(-sc, kind="stable")
            top, bot = ixh[o[: int(round(0.2 * len(o)))]], ixh[o[int(round(0.5 * len(o))):]]
            print(f"      {hn}: reach_d top 20% {y[top].mean():.3f} / bottom 50% {y[bot].mean():.3f}")
            for nm in PATH_F + VOL_F:
                print(f"        {nm:<18} {np.nanmedian(raw[nm][top]):+10.4f}  vs  {np.nanmedian(raw[nm][bot]):+10.4f}")
        # verdicts
        test_h = [hn for hn in halves if P_[("full - position  [THE TEST]", hn)][2] < 0]
        strong = all(lev[hn][1][1][0] < 0.5 and lev[hn][1][0][1] > 0 for hn in halves)
        verdicts[d] = (test_h, strong)
        diag_h = {lbl: [hn for hn in halves if P_[(lbl, hn)][2] < 0] for lbl in
                  ("full L1 - position L1  [diag]", "best full tree - best position tree  [diag]")}
        agree = all((len(v) == 2) == (len(test_h) == 2) for v in diag_h.values())
        print(f"  d={d}: same-learner diagnostics clear in: "
              + "; ".join(f"{k.replace('  [diag]', '')}: {', '.join(v) or 'neither'}" for k, v in diag_h.items())
              + ("" if agree else "   <- DISAGREES with the gating test: goes to the user"))
        print(f"  d={d}: full - position clears in: {', '.join(test_h) or 'neither'};  STRONG: {'YES' if strong else 'NO'}"
              f"   [{time.time()-t0:.0f}s]", flush=True)

    print()
    print("=" * 120)
    print("READING RULES")
    print("=" * 120)
    found = [d for d, (h, _) in verdicts.items() if len(h) == 2]
    regime = [f"d={d} ({h[0]} only)" for d, (h, _) in verdicts.items() if len(h) == 1]
    print(f"  FOUND SOMETHING (full - position clears in both halves at d=30 or d=60): "
          f"{'YES at d=' + ', '.join(map(str, found)) if found else 'NO'}")
    print(f"  STRONG: {', '.join(f'd={d}' for d, (_, s_) in verdicts.items() if s_) or 'none'}")
    print(f"  REGIME-DEPENDENT: {', '.join(regime) if regime else 'none'}")
    print("  No stop. Chance bar never a feature. Nothing written to the registry or the live system.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 120)


if __name__ == "__main__":
    st = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "models"
    {"paths": stage_paths, "models": stage_models}[st]()
