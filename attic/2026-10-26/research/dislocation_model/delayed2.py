"""DELAYED DECISION v2: refresh the detection features at the decision point.

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/delayed2.py --stage refresh > .../logs/delayed2_refresh.log 2>&1
    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/delayed2.py --stage models > .../logs/delayed2.log 2>&1

Same question, populations, target (reach_d), path features, volume since t0,
split and chance bar as DELAYED (delayed.py, datasets/delayed_paths.npz).
Initial detection t0 = the first 3-sigma crossing; decision point d = t0 + 30
or t0 + 60 minutes. mu and sigma stay frozen at t0 for the target.

STEP 1 -- REFRESHED DETECTION FEATURES. The REACH-MU-V2 kept set, minus sigma,
abs_z and weekday (not refreshed, by the brief), recomputed through the SAME
code with the anchor shifted k = d/30 bars: the 30-minute bar whose close is
t0's close + d (index J+k, label entry + 30k).
  envfeat.build(W=W_k, M=M_k)       vol_48, vratio, vol_slope, sandwich, off_mark
  vol1m.trailing_features(M_k, ...) vol_48_1m (ends at minute d)
  whyfeat.compute(M_k, ...)         common_share_4/12, vol_spike_mover_4/12/_1m_4/_1m_12,
                                    vol_spike_ratio_4/12/_1m_4/_1m_12, lagger_spread_4/12
  rolling_spread_stats at J+k       beta, r2 (the rolling window at d)
M_k is disloc_meta with bar_index J+k and entry_time + 30k minutes; beta,
alpha, mu, sigma and the sign of z stay at t0 (the frozen geometry every one of
these features is defined on). W_k is the 336-bar sigma-unit window ending at
J+k under that frozen geometry, built exactly as mkdisloc builds W (float64,
then float32). The dominant leg is re-derived at the new anchor (it is part of
each feature's definition). The 1-minute features use the original matched
53,757 (no new coverage selection).
  Gap filled: vol_slope_1m is not in the kept set, so it is not refreshed.
For each refreshed feature f: f_at_d, and f_chg = f_at_d - f_t0, both after the
REACH-MU transform (log on vol_48, vol_48_1m, vol_spike_mover*,
vol_spike_ratio*, lagger_spread*; so _chg is a difference of logs there), then
TRAIN-median fill.
  z_roll_at_d    the spread's z at bar J+k on its OWN rolling geometry
                 (rolling_spread_stats, as mkdisloc), folded by sign(z at t0):
                 positive = still on the dislocated side. Minute d is the close
                 of bar J+k, so this is exactly z at minute d.
  dist_in_moves  dist_now / (vol_48_1m_at_d * sqrt(600 - d)). Gap filled: the
                 brief multiplies dist_now by sigma_t0, but dist_now AND
                 vol_48_1m are both already in frozen-sigma units, so sigma_t0
                 cancels; multiplying by it alone would mix units. The quantity
                 is the brief's: distance to mu over the typical move left.
GATE: with k = 0 every refreshed feature must reproduce its stored t0 value
exactly, NaN pattern included, on all 53,757 (envfeat.npz, vol48_1m.npz,
whyfeat.npz, meta.beta, meta.r2), and z_roll at k = 0 must equal z_at_entry;
the rebuilt W_0 must equal disloc.npz's windows. Any difference: STOP.
LOOK-AHEAD: every family's maximum index read is reported against J+k (and
minute t0 close + d for the 1-minute ones); STOP if any exceeds it.
Separation, on TRAIN still-open rows: median of each _at_d and _chg for
reverters vs non-reverters, and the single-feature AUC. Gap filled: no earlier
run defined a "separation score"; the univariate AUC is used and named.

STEP 2 -- MODELS at each d (train of the still-open; every setting on val by log
loss): vol-only; position (vol-only + dist_now, THE BAR); position+ (position +
dist_in_moves); full v1 (DELAYED's full: kept + path + volume since t0); full v2
(full v1 + all _at_d + all _chg + z_roll_at_d + dist_in_moves). Every set as
logistic L1 (C over reachmu.C_GRID) and LightGBM gbdt depths 1, 2, 3, 4, 6,
num_leaves 2^d, min_data_in_leaf over {20, 50, 100, 400, 1000, 2000}, lr 0.05,
early stopping on val. As in DELAYED: full v1 and full v2 are each represented
by their lowest-val-log-loss model among L1 and the five trees; position and
position+ by their L1 (the brief's bar). Same-learner diagnostics (L1 vs L1,
best tree vs best tree) are printed beside every test and any disagreement
with the gating test goes to the user.

DOWNTICK RULE: flag still-open episodes whose frozen |z| crossed back below 3 in
minutes 1..d and is below 3 at minute d. For a still-open episode frozen |z| at
minute d = need - seg[d] = dist_now (it has not reached mu), and |z| >= 3 at
t0, so the rule is exactly dist_now < 3. Its flag share, catch rate and hit
rate; full v2's (and position's) hit rate at the same flag share.

STEP 3 -- SCORING, held out, HO1 and HO2, each d: flag share / hit rate at
50/80/90% catch and top-20% hit, every model and the downtick rule. Paired
day-clustered 95% intervals on flag share at 80% catch: full v2 - position
(THE TEST), full v2 - full v1, position+ - position, plus diagnostics. Grouped
permutation importance (held out, 20 shuffles, log-loss skill points,
per-half intervals) for full v2: t0 frozen, refreshed _at_d, _chg, dist_now,
dist_in_moves, z_roll_at_d, path shape, path_vol, path momentum, volume since
t0; plus two COMBINED groups (added after review), "refreshed family" (_at_d +
_chg) and "position at d" (dist_now + dist_in_moves + z_roll_at_d), because
the split groups can rebuild each other; family conclusions come from the
combined ones. Chance bar for full v2's top 20% as in DELAYED.

READING RULES (the brief's, fixed; "clears" = the 95% interval excludes zero):
  FOUND SOMETHING: full v2 - position, flag share at 80% catch, interval wholly
    below zero in BOTH HO1 and HO2, at d = 30 or d = 60.
  REGIME-DEPENDENT: clears in exactly one half.
  Also stated with verdicts: full v2 - full v1, position+ - position.
No stop. Nothing after minute d. Nothing written to the registry or the live
system.
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
from envelope import HO_BOUNDARY, day_boot
from reachmu import (assemble_features, flag_share, logloss_rows, population,
                     reach_group, top_set, tree_shape)
from delayed import DS, GROUPS, OUT as DPATHS, PATH_F, VOL_F, fit_l1, path_features

REFRESH = os.path.join(paths.DATASETS, "delayed2_refresh.npz")
ENV5 = ("vol_48", "vratio", "vol_slope", "sandwich", "off_mark")
WHY = ("common_share_4", "common_share_12", "vol_spike_mover_4", "vol_spike_mover_12",
       "vol_spike_mover_1m_4", "vol_spike_mover_1m_12", "vol_spike_ratio_4", "vol_spike_ratio_12",
       "vol_spike_ratio_1m_4", "vol_spike_ratio_1m_12", "lagger_spread_4", "lagger_spread_12")
REFRESHED = ENV5 + ("vol_48_1m",) + WHY + ("beta", "r2")
LOGGED = ("vol_48", "vol_48_1m") + tuple(n for n in WHY if n.startswith(("vol_spike", "lagger")))
KEPT = ("vol_48", "vratio", "vol_slope", "sandwich", "off_mark", "common_share", "vol_spike_mover",
        "vol_spike_ratio", "lagger_spread", "abs_z", "beta", "r2", "sigma", "weekday")
MDL = (20, 50, 100, 400, 1000, 2000)
DEPTHS = (1, 2, 3, 4, 6)
LR = 0.05
THREADS = 6
N_SHUF = 20
SEED = 20261013
CATCH = (0.5, 0.8, 0.9)


# ==================================================================== refresh
def stage_refresh():
    import envfeat
    import rolling_spread as rs
    import universe_panel
    import vol1m
    import whyfeat
    t0 = time.time()
    Y, meta, rows = population()
    N = len(meta)
    used = np.zeros(N, bool)
    used[rows] = True
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    cols = list(panel.columns)
    ixc = {c: k for k, c in enumerate(cols)}
    LC = panel.to_numpy(float)
    J = meta.bar_index.to_numpy(int)
    ja = meta.ticker_a.map(ixc).to_numpy(int)
    jb = meta.ticker_b.map(ixc).to_numpy(int)
    be, al = meta.beta.to_numpy(float), meta.alpha.to_numpy(float)
    mu, sg = meta.mu.to_numpy(float), meta.sigma.to_numpy(float)
    W_store = np.load(paths.DISLOC)["windows"]
    E_store = np.load(paths.ENVFEAT, allow_pickle=False)["X"]
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    WZ = np.load(os.path.join(paths.DATASETS, "whyfeat.npz"), allow_pickle=False)
    wn = [str(x) for x in WZ["names"]]
    print("=" * 112)
    print("DELAYED DECISION v2 -- refreshed detection features at the decision point")
    print("=" * 112)
    out = {"rows": rows}
    bad = []
    touch_rows = []

    def gate(name, new, ref):
        new, ref = np.asarray(new, float), np.asarray(ref, float)
        same = np.array_equal(np.isnan(new), np.isnan(ref)) and np.array_equal(
            np.where(np.isnan(new), 0, new), np.where(np.isnan(ref), 0, ref))
        mx = float(np.nanmax(np.abs(new - ref))) if np.isfinite(new - ref).any() else 0.0
        print(f"    GATE {name:<24} reproduces t0 exactly: {same}   (max |diff| {mx:.3e})")
        if not same:
            bad.append(name)

    # ---- 30m windows and envfeat, 1m vol_48_1m, rolling beta/r2/z: per k
    off = np.arange(-335, 1)
    for k in (0,) + tuple(d // 30 for d in DS):
        Mk = meta.copy()
        Mk["bar_index"] = J + k
        Mk["entry_time"] = pd.to_datetime(meta.entry_time) + pd.Timedelta(minutes=30 * k)
        I = (J + k)[:, None] + off[None, :]
        Wk = ((LC[I, ja[:, None]] - be[:, None] * LC[I, jb[:, None]] - al[:, None] - mu[:, None])
              / sg[:, None]).astype(np.float32)
        if k == 0:
            same = np.array_equal(Wk, W_store)
            print(f"  k=0: rebuilt W equals disloc.npz windows exactly: {same}")
            if not same:
                raise SystemExit("[DELAY2] STOP -- the window rebuild is not mkdisloc's.")
        Xk, _, aud = envfeat.build(verbose=False, W=Wk, M=Mk)
        touch_rows.append((f"envfeat k={k}", int((aud["touch"] - (J + k)).max())))
        tf = vol1m.trailing_features(Mk, rows, Wk.astype(np.float64), Xk[rows, 0].astype(np.float64))
        touch_rows.append((f"vol_48_1m k={k} (min vs bar label)", int(tf["max_off"]) - 29))
        vk = tf["vol"]
        print(f"  k={k}: envfeat + vol_48_1m rebuilt; reproduction ratio {tf['rep_ratio']:.3f}, "
              f"vol_48 recomputation {tf['recomp']:.2e}   [{time.time()-t0:.0f}s]", flush=True)
        if k == 0:
            for j, nm in enumerate(ENV5):
                gate(nm, Xk[rows, j], E_store[rows, j])
            gate("vol_48_1m", vk, v48["vol_48_1m"])
        for j, nm in enumerate(ENV5):
            out[f"{nm}_k{k}"] = Xk[rows, j].astype(float)
        out[f"vol_48_1m_k{k}"] = vk
    # rolling beta, r2, z at J+k for the episode pairs
    key = meta.ticker_a + "|" + meta.ticker_b
    ep_of = key.groupby(key).indices
    V = panel.to_numpy(float)
    first = np.array([np.isfinite(V[:, j]).argmax() for j in range(V.shape[1])])
    RB = {k: np.full((3, N), np.nan) for k in (0, 1, 2)}
    for kk, eps in ep_of.items():
        a, b = kk.split("|")
        xa, xb = ixc[a], ixc[b]
        f = max(first[xa], first[xb])
        r = rs.rolling_spread_stats(V[f:, xa], V[f:, xb], 0.5)
        for k in (0, 1, 2):
            li = J[eps] + k - f
            RB[k][0, eps], RB[k][1, eps], RB[k][2, eps] = r.beta[li], r.r2[li], r.z[li]
    s = np.sign(meta.z_at_entry.to_numpy(float))
    s[s == 0] = 1.0
    gate("beta", RB[0][0, rows], be[rows])
    gate("r2", RB[0][1, rows], meta.r2.to_numpy(float)[rows])
    gate("z_roll (vs z_at_entry)", RB[0][2, rows], meta.z_at_entry.to_numpy(float)[rows])
    for k in (0, 1, 2):
        out[f"beta_k{k}"], out[f"r2_k{k}"] = RB[k][0, rows], RB[k][1, rows]
        out[f"z_roll_k{k}"] = s[rows] * RB[k][2, rows]
        touch_rows.append((f"rolling beta/r2/z k={k}", 0))     # index J+k read, by construction
    print(f"  rolling beta, r2, z at J+k   [{time.time()-t0:.0f}s]", flush=True)
    del V

    # ---- whyfeat at each anchor
    P = whyfeat.prepare()
    print(f"  whyfeat.prepare done   [{time.time()-t0:.0f}s]", flush=True)
    for k in (0,) + tuple(d // 30 for d in DS):
        Mk = meta.copy()
        Mk["bar_index"] = J + k
        Mk["entry_time"] = pd.to_datetime(meta.entry_time) + pd.Timedelta(minutes=30 * k)
        C = whyfeat.compute(Mk, P, used, t0)
        for nm_, v in C["touch"].items():
            touch_rows.append((f"whyfeat {nm_} k={k}", int((v - (J + k)).max())))
        touch_rows.append((f"whyfeat 1m k={k} (min vs bar label)", int(C["max_off"]) - 29))
        if k == 0:
            for nm in WHY:
                gate(nm, C["feats"][nm][rows], WZ["X"][rows, wn.index(nm)])
        for nm in WHY:
            out[f"{nm}_k{k}"] = C["feats"][nm][rows]
        print(f"  whyfeat.compute k={k}   [{time.time()-t0:.0f}s]", flush=True)
    print()
    print("  LOOK-AHEAD -- max index read minus the anchor J+k (1-minute: minutes past the anchor bar's close)")
    worst = 0
    for nm_, v in touch_rows:
        print(f"    {nm_:<52} {v:+d}")
        worst = max(worst, v)
    if worst > 0:
        raise SystemExit("[DELAY2] STOP -- a refreshed feature reads past minute d.")
    if bad:
        raise SystemExit(f"[DELAY2] STOP -- t0 reproduction failed for: {', '.join(bad)}")
    print("    -> PASS;  every refreshed feature reproduces t0 exactly at k = 0")
    np.savez_compressed(REFRESH, **out)
    print(f"  [WROTE] {os.path.relpath(REFRESH, paths.RESEARCH)}   [{time.time()-t0:.0f}s]")


# ===================================================================== models
def build_sets(D, R, X0, kcols, kn, ix0, d, rr, tr, y):
    """DELAYED / DELAYED-V2 feature sets at d on the still-open rows rr: vol-only,
    position, position+, full v1, full v2, with their raw values and fill counts.
    One definition, shared with delayed3.py."""
    k = d // 30
    raw, tfp, mc = path_features(D, d, rr, tr)
    # refreshed features
    AT, CH, rawAT, rawCH = {}, {}, {}, {}
    for nm in REFRESHED:
        a_ = tf_feature(nm, R[f"{nm}_k{k}"][rr])
        b_ = tf_feature(nm, R[f"{nm}_k0"][rr])
        rawAT[nm], rawCH[nm] = a_.copy(), a_ - b_
        AT[nm], CH[nm] = a_.copy(), a_ - b_
    zr = R[f"z_roll_k{k}"][rr].astype(float)
    dim = raw["dist_now"] / (R[f"vol_48_1m_k{k}"][rr] * np.sqrt(600 - d))
    miss = {f"{nm}_at_d": int((~np.isfinite(v)).sum()) for nm, v in AT.items()}
    miss.update({f"{nm}_chg": int((~np.isfinite(v)).sum()) for nm, v in CH.items()})
    miss["z_roll_at_d"], miss["dist_in_moves"] = int((~np.isfinite(zr)).sum()), int((~np.isfinite(dim)).sum())
    for dct in (AT, CH):
        for nm, v in dct.items():
            v[~np.isfinite(v)] = np.nanmedian(v[tr])
    zr_f, dim_f = zr.copy(), dim.copy()
    zr_f[~np.isfinite(zr_f)] = np.nanmedian(zr[tr])
    dim_f[~np.isfinite(dim_f)] = np.nanmedian(dim[tr])
    sep_rows = [(f"{nm}_at_d", rawAT[nm]) for nm in REFRESHED] + [(f"{nm}_chg", rawCH[nm]) for nm in REFRESHED] \
        + [("z_roll_at_d", zr), ("dist_in_moves", dim), ("dist_now", raw["dist_now"])]
    kn = list(kn)
    XK = X0[rr][:, kcols]
    vol3 = X0[rr][:, [ix0["vol_48"], ix0["vol_48_1m"], ix0["sigma"]]]
    PF = np.column_stack([tfp[nm] for nm in PATH_F + VOL_F])
    ATm = np.column_stack([AT[nm] for nm in REFRESHED])
    CHm = np.column_stack([CH[nm] for nm in REFRESHED])
    v1n = kn + list(PATH_F + VOL_F)
    v2n = v1n + [f"{nm}_at_d" for nm in REFRESHED] + [f"{nm}_chg" for nm in REFRESHED] + ["z_roll_at_d", "dist_in_moves"]
    sets = {"vol-only": (vol3, ["vol_48", "vol_48_1m", "sigma"]),
            "position": (np.column_stack([vol3, tfp["dist_now"]]), ["vol_48", "vol_48_1m", "sigma", "dist_now"]),
            "position+": (np.column_stack([vol3, tfp["dist_now"], dim_f]),
                          ["vol_48", "vol_48_1m", "sigma", "dist_now", "dist_in_moves"]),
            "full v1": (np.column_stack([XK, PF]), v1n),
            "full v2": (np.column_stack([XK, PF, ATm, CHm, zr_f, dim_f]), v2n)}
    return dict(sets=sets, raw=raw, tfp=tfp, mc=mc, miss=miss, sep_rows=sep_rows)


def fit_sets(sets, y, tr, va, t0, no_trees=("vol-only",)):
    """Logistic L1 for every set and the LightGBM depth grid for every set not in
    no_trees; every setting on val by log loss. Returns (score, vll, fns).
    One definition, shared with delayed3.py."""
    import lightgbm as lgb
    score, vll, fns = {}, {}, {}
    for sn, (Xs, ns) in sets.items():
        m_, s_ = Xs[tr].mean(0), Xs[tr].std(0)
        s_[s_ == 0] = 1.0
        Zs = (Xs - m_) / s_
        ll_, mdl_, C_ = fit_l1(Zs, y, tr, va)
        key = f"{sn} L1"
        score[key], vll[key] = mdl_.predict_proba(Zs)[:, 1], ll_
        fns[key] = (lambda M_, m=mdl_, a=m_, b=s_: m.predict_proba((M_ - a) / b)[:, 1])
        print(f"    {key:<15} val log loss {ll_:.5f}  C {C_}, nonzero {int((mdl_.coef_ != 0).sum())} of {len(ns)}")
        if sn in no_trees:
            continue
        for dep in DEPTHS:
            best = None
            for mdl in MDL:
                p = dict(objective="binary", metric="binary_logloss", seed=0, deterministic=True,
                         force_row_wise=True, num_threads=THREADS, verbosity=-1, boosting="gbdt",
                         max_depth=dep, num_leaves=2 ** dep, min_data_in_leaf=mdl, learning_rate=LR)
                dtr = lgb.Dataset(Xs[tr], y[tr], feature_name=ns)
                dva = lgb.Dataset(Xs[va], y[va], reference=dtr)
                bst = lgb.train(p, dtr, 5000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
                it = bst.best_iteration
                l_ = logloss_rows(y[va], bst.predict(Xs[va], num_iteration=it)).mean()
                if best is None or l_ < best[0]:
                    best = (l_, bst, it, mdl)
            l_, bst, it, mdl = best
            key = f"{sn} d{dep}"
            score[key], vll[key] = bst.predict(Xs, num_iteration=it), l_
            fns[key] = (lambda M_, b=bst, i=it: b.predict(M_, num_iteration=i))
            nt, dm, dmean, lm, lmean = tree_shape(lgb.Booster(model_str=bst.model_to_string(num_iteration=it)))
            edge = "   <- GRID EDGE" if mdl in (MDL[0], MDL[-1]) else ""
            print(f"    {key:<15} val log loss {l_:.5f}  min_data_in_leaf {mdl}, rounds {it}; depth max {dm} "
                  f"(mean {dmean:.2f}), leaves max {lm} (mean {lmean:.1f}){edge}   [{time.time()-t0:.0f}s]", flush=True)
    return score, vll, fns


def tf_feature(nm, v):
    v = np.asarray(v, float)
    if nm in LOGGED:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(v > 0, np.log(v), np.nan)
    return v.copy()


def auc1(y, x):
    from sklearn.metrics import roc_auc_score
    m = np.isfinite(x)
    return float(roc_auc_score(y[m], x[m]))


def stage_models():
    t0 = time.time()
    Y, meta, rows = population()
    D = np.load(DPATHS)
    R = np.load(REFRESH)
    if not (np.array_equal(D["rows"], rows) and np.array_equal(R["rows"], rows)):
        raise SystemExit("[DELAY2] row alignment differs.")
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    sp = harness.Split(day, e)
    names, X0, _ = assemble_features(meta, rows, e, sp.train)
    kcols = [j for j, nm in enumerate(names) if reach_group(nm) in KEPT]
    if len(kcols) != 24:
        raise SystemExit(f"[DELAY2] kept set has {len(kcols)} columns, expected 24.")
    kn = [names[j] for j in kcols]
    ix0 = {nm: j for j, nm in enumerate(names)}
    print("=" * 120)
    print("DELAYED DECISION v2 -- refreshed detection features at d (t0 = initial detection, d = decision point)")
    print("=" * 120)
    print(f"  {sp.describe()}")
    verdicts = {}
    for d in DS:
        k = d // 30
        print()
        print("#" * 120)
        print(f"DECISION POINT d = t0 + {d} min (refreshed on bar J+{k})")
        print("#" * 120)
        openm = D[f"open_{d}"]
        rr = np.flatnonzero(openm)
        y = D[f"reach_{d}"].astype(int)[rr]
        tr, va, te = sp.train[rr], sp.val[rr], sp.test[rr]
        dd = day[rr]
        halves = {"HO1": np.flatnonzero(te & (dd < HO_BOUNDARY)), "HO2": np.flatnonzero(te & (dd >= HO_BOUNDARY))}
        B_ = build_sets(D, R, X0, kcols, kn, ix0, d, rr, tr, y)
        sets, raw, mc, miss, sep_rows = B_["sets"], B_["raw"], B_["mc"], B_["miss"], B_["sep_rows"]
        yt = y[tr]
        print(f"  STEP 1 -- still open {len(rr):,}; path/volume missing -> train median: {mc or 'none'}")
        print("    refreshed missing -> train median: " + (";  ".join(f"{k_} {v}" for k_, v in miss.items() if v) or "none"))
        print("    SEPARATION on TRAIN still-open: median for reverters vs non-reverters, and single-feature AUC")
        for nm, v in sep_rows:
            vt = v[tr]
            print(f"      {nm:<30} reverters {np.nanmedian(vt[yt == 1]):+11.5g}   non {np.nanmedian(vt[yt == 0]):+11.5g}"
                  f"   AUC {auc1(yt, vt):.4f}")
        print("  STEP 2 -- models (train; settings on val by log loss)")
        score, vll, fns = fit_sets(sets, y, tr, va, t0)
        rep = {sn: min([k_ for k_ in vll if k_.startswith(sn + " ")], key=lambda k_: vll[k_]) for sn in ("full v1", "full v2")}
        rep["position"], rep["position+"], rep["vol-only"] = "position L1", "position+ L1", "vol-only L1"
        btree = {sn: min([k_ for k_ in vll if k_.startswith(sn + " d")], key=lambda k_: vll[k_])
                 for sn in ("position", "position+", "full v1", "full v2")}
        print(f"    -> representatives: full v1 = {rep['full v1']}, full v2 = {rep['full v2']} (lowest val log loss); "
              f"position and position+ = their L1 (the brief's bar); best trees (diagnostics): "
              + ", ".join(f"{k_} {v}" for k_, v in btree.items()))

        # ---- scoring
        print("  STEP 3 -- scoring, held out only")
        order = ["vol-only L1", "position L1", "position+ L1"] + [rep["full v1"], rep["full v2"]] + \
            [k_ for k_ in score if k_.startswith("full v2") and k_ != rep["full v2"]] + \
            [btree["position"], btree["position+"]]
        hboot = {hn: day_boot(dd[ixh]) for hn, ixh in halves.items()}
        down = raw["dist_now"] < 3.0
        for hn, ixh in halves.items():
            yh = y[ixh]
            print(f"    {hn}: still open {len(ixh):,}, reverters {int(yh.sum()):,} ({yh.mean():.4f})")
            print(f"      {'model':<16}" + "".join(f"{f'catch {int(100*c)}%: flag / hit':>28}" for c in CATCH) + f"{'top20 hit':>11}")
            print(f"      {'random':<16}" + "".join(f"{f'{c:.3f} / {yh.mean():.3f}':>28}" for c in CATCH) + f"{yh.mean():>11.3f}")
            for mn in order:
                sc = score[mn][ixh]
                cat = [flag_share(sc, yh, c)[:2] for c in CATCH]
                th = yh[top_set(sc, 0.2)].mean()
                tag = "   <- " + [k_ for k_, v in rep.items() if v == mn][0] if mn in rep.values() else ""
                print(f"      {mn:<16}" + "".join(f"{f'{a:.3f} / {b:.3f}':>28}" for a, b in cat) + f"{th:>11.3f}{tag}")
            dh = down[ixh]
            fs, cr = dh.mean(), yh[dh].sum() / max(yh.sum(), 1)
            hr = yh[dh].mean() if dh.any() else np.nan
            kk = int(dh.sum())
            hv2 = yh[np.argsort(-score[rep["full v2"]][ixh], kind="stable")[:kk]].mean() if kk else np.nan
            hp = yh[np.argsort(-score["position L1"][ixh], kind="stable")[:kk]].mean() if kk else np.nan
            print(f"      DOWNTICK RULE (dist_now < 3): flag share {fs:.3f}, catch {cr:.3f}, hit {hr:.3f};  "
                  f"at the same flag share: full v2 hit {hv2:.3f}, position hit {hp:.3f}")

        def paired(a, b, hn):
            ixh = halves[hn]
            yh, sa, sb = y[ixh], score[a][ixh], score[b][ixh]
            f = lambda sc, yy: flag_share(sc, yy, 0.8)[0]
            dr = [f(sa[i_], yh[i_]) - f(sb[i_], yh[i_]) for i_ in hboot[hn]]
            return (f(sa, yh) - f(sb, yh), *np.percentile(dr, [2.5, 97.5]))
        print("    PAIRED flag share at 80% catch, day-clustered 95% (A minus B; - = A needs fewer flags)")
        tests = (("full v2 - position  [THE TEST]", rep["full v2"], "position L1"),
                 ("full v2 - full v1", rep["full v2"], rep["full v1"]),
                 ("position+ - position", "position+ L1", "position L1"),
                 ("full v2 L1 - position L1  [diag]", "full v2 L1", "position L1"),
                 ("best v2 tree - best position tree  [diag]", btree["full v2"], btree["position"]),
                 ("full v2 L1 - full v1 L1  [diag]", "full v2 L1", "full v1 L1"),
                 ("best v2 tree - best v1 tree  [diag]", btree["full v2"], btree["full v1"]),
                 ("best position+ tree - best position tree  [diag]", btree["position+"], btree["position"]),
                 ("position - vol-only  [dist_now alone]", "position L1", "vol-only L1"))
        P_ = {}
        for lbl, a, b in tests:
            cells = []
            for hn in halves:
                r_ = paired(a, b, hn)
                P_[(lbl, hn)] = r_
                cells.append(f"{hn} {r_[0]:+.4f} [{r_[1]:+.4f},{r_[2]:+.4f}]" + ("*" if r_[2] < 0 else "!" if r_[1] > 0 else " "))
            print(f"      {lbl:<50}" + "   ".join(cells))
        clr = {lbl: [hn for hn in halves if P_[(lbl, hn)][2] < 0] for lbl, _, _ in tests}
        pairs_diag = {"full v2 - position  [THE TEST]": ("full v2 L1 - position L1  [diag]", "best v2 tree - best position tree  [diag]"),
                      "full v2 - full v1": ("full v2 L1 - full v1 L1  [diag]", "best v2 tree - best v1 tree  [diag]"),
                      "position+ - position": ("best position+ tree - best position tree  [diag]",)}
        for g_, dg in pairs_diag.items():
            agree = all((len(clr[x]) == 2) == (len(clr[g_]) == 2) for x in dg)
            print(f"      {g_:<30} clears in: {', '.join(clr[g_]) or 'neither'};  diagnostics: "
                  + "; ".join(f"{x.replace('  [diag]', '')}: {', '.join(clr[x]) or 'neither'}" for x in dg)
                  + ("" if agree else "   <- DISAGREES with the gating test: goes to the user"))
        # chance bar
        ch = D[f"chance_{d}"][rr]
        print("    CHANCE BAR (reading only), full v2's top 20%")
        for hn, ixh in halves.items():
            yh, chh, sc = y[ixh], ch[ixh], score[rep["full v2"]][ixh]
            g_ = lambda s_, y_, c_: y_[top_set(s_, 0.2)].mean() - c_[top_set(s_, 0.2)].mean()
            pt = g_(sc, yh, chh)
            lo, hi = np.percentile([g_(sc[i_], yh[i_], chh[i_]) for i_ in hboot[hn]], [2.5, 97.5])
            tp = top_set(sc, 0.2)
            print(f"      {hn}: still open real {yh.mean():.4f} vs chance {chh.mean():.4f};  top 20% real "
                  f"{yh[tp].mean():.4f} vs chance {chh[tp].mean():.4f}, gap {pt:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        # importance
        Xf, nf = sets["full v2"]
        gidx = {"t0 frozen": list(range(len(kn))),
                "refreshed _at_d": [nf.index(f"{nm}_at_d") for nm in REFRESHED],
                "changes _chg": [nf.index(f"{nm}_chg") for nm in REFRESHED],
                "dist_now": [nf.index("dist_now")], "dist_in_moves": [nf.index("dist_in_moves")],
                "z_roll_at_d": [nf.index("z_roll_at_d")]}
        for g_ in ("path shape", "path_vol", "path momentum", "volume since t0"):
            gidx[g_] = [nf.index(m) for m in GROUPS[g_]]
        # combined groups (review): any two of t0 / _at_d / _chg rebuild the third, and
        # dist_now / dist_in_moves / z_roll_at_d all say where the spread sits at d, so the
        # split groups understate; family conclusions are read off these
        gidx["COMBINED refreshed family (_at_d + _chg)"] = gidx["refreshed _at_d"] + gidx["changes _chg"]
        gidx["COMBINED position at d (dist_now + dist_in_moves + z_roll)"] = (
            gidx["dist_now"] + gidx["dist_in_moves"] + gidx["z_roll_at_d"])
        print(f"    IMPORTANCE, held out, {rep['full v2']}; {N_SHUF} shuffles; log-loss skill points lost; per-half 95%")
        teix = np.flatnonzero(te)
        lc = logloss_rows(y[teix], np.full(len(teix), y[tr].mean()))
        fn = fns[rep["full v2"]]
        base_l = logloss_rows(y[teix], fn(Xf[teix]))
        pos = {"held out": np.arange(len(teix))}
        for hn, ixh in halves.items():
            pos[hn] = np.flatnonzero(np.isin(teix, ixh))
        for gi, (g_, js) in enumerate(gidx.items()):
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
                lo, hi = np.percentile([100 * a_[i_].mean() / c_[i_].mean() for i_ in bt], [2.5, 97.5])
                cells.append(f"{bn} {100*a_.mean()/c_.mean():+.4f} [{lo:+.4f},{hi:+.4f}]{'+' if lo > 0 else ' '}")
            print(f"      {g_:<58}" + "   ".join(cells))
        verdicts[d] = clr
        print(f"  [{time.time()-t0:.0f}s]", flush=True)

    print()
    print("=" * 120)
    print("READING RULES")
    print("=" * 120)
    for lbl, nm in (("full v2 - position  [THE TEST]", "FOUND SOMETHING (full v2 - position, both halves, d=30 or 60)"),
                    ("full v2 - full v1", "REFRESHING ADDS (full v2 - full v1, both halves)"),
                    ("position+ - position", "DIST_IN_MOVES ADDS (position+ - position, both halves)")):
        both = [d for d in DS if len(verdicts[d][lbl]) == 2]
        one = [f"d={d} ({verdicts[d][lbl][0]} only)" for d in DS if len(verdicts[d][lbl]) == 1]
        print(f"  {nm}: {'YES at d=' + ', '.join(map(str, both)) if both else 'NO'}"
              + (f";  regime-dependent: {', '.join(one)}" if one else ""))
    print("  No stop. Nothing after minute d. Nothing written to the registry or the live system.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 120)


if __name__ == "__main__":
    st = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "models"
    {"refresh": stage_refresh, "models": stage_models}[st]()
