"""REACH-MU v2: prune on validation, then test three new feature families.

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/reachmu2.py > research/dislocation_model/logs/reachmu2.log 2>&1

Same target, population and split as REACH-MU (reachmu.py): reach = depth >=
|z_at_entry| on 1-minute closes, mu frozen at entry, no stop; matched 53,757;
train < 2026-05-01, val to 2026-07-17 (every choice), held out from
2026-07-18, HO1 to 2026-08-25, HO2 from 2026-08-26. Reuses reach_paths.npz,
reachmu.assemble_features (the 44 REACH-MU features), reachmu.reach_group (its
groups) and reachfeat2.npz (Step 2). No funding data. Nothing written to the
registry or the live system.

STEP 1 -- PRUNE, VALIDATION ONLY. On the 44 features, fit on train: logistic L1
(C on val over {0.001 .. 3}, as REACH-MU) and a depth-2 LightGBM tree
(num_leaves 4; settings on val, below). Grouped permutation importance on VAL,
REACH-MU's groups, 20 shuffles, log-loss skill points lost, day-clustered 95%
over val days. DROP RULE (the brief's): drop a group if its val interval
includes zero in BOTH models. vol_48 (with vol_48_1m) and abs_z are always
kept. Held out is not read in this step.

STEP 3 -- MODELS (fitted on train; every setting on val by log loss):
  vol-only   logistic, unpenalised: vol_48, vol_48_1m, sigma (as REACH-MU)
  kept       the Step 1 kept set
  kept+new   the kept set plus the Step 2 features (train-median fill;
             counts reported). Gap filled: basis_rel_move_diff_2 and _6 are
             DROPPED at load (reachfeat2.npz keeps them). They are identical to
             basis_move_diff_2 and _6: (dom - med) - (oth - med) = dom - oth, the
             hourly median cancels, so basis_move_diff already is the relative
             diff. Identical columns add nothing and would split member-level
             importance and L1 coefficients arbitrarily. 26 features enter.
Each of kept and kept+new: logistic L1 (C grid as above) and LightGBM gbdt at
max_depth 1, 2, 3, 4, 6, num_leaves = 2^d. Gap filled:
  - min_data_in_leaf over {100, 400, 1000, 2000}. REACH-MU's grid
    {20, 100, 400} chose its top value in all 14 configurations (a grid
    boundary, flagged by review), so the grid is extended upward.
  - learning rate fixed at 0.05 (the brief names min_data_in_leaf and rounds
    as the tuned settings); rounds by early stopping on val log loss
    (patience 100, cap 5000). The prune's depth-2 tree uses the same grid.
  - The model that REPRESENTS a set (headline, paired tests, importance) is
    the set's lowest-val-log-loss model among its L1 and its five trees.

STEP 4 -- SCORING, held out only, HO1 and HO2 separately: flag share and hit
rate at 50/80/90% catch, top-20% hit rate (reachmu.flag_share / top_set), for
vol-only, kept and kept+new (every fitted model in the log). Paired
day-clustered 95% intervals (envelope.day_boot within the half, ranks
recomputed per resample) on flag share at 80% catch and top-20% hit rate:
kept+new minus kept, and kept+new minus vol-only. Depth curve for kept+new.
Importance on held out for the kept+new representative: grouped permutation
(kept groups as in REACH-MU, each Step 2 family as ONE group), and each Step 2
member alone; 20 shuffles; log-loss skill points; intervals per half.

READING RULES (the brief's, fixed; "clears" = the 95% interval excludes zero):
  NEW FEATURES HELP: kept+new minus kept on flag share at 80% catch has its
    interval wholly below zero in BOTH HO1 and HO2.
  SIGNAL OVERALL: kept+new minus vol-only, same measure, both halves.
  REGIME-DEPENDENT: either clears in exactly one half; reported, not a pass.
  PER FAMILY: whether its grouped importance interval lies wholly above zero
    in both halves; families clearing in neither are listed "did not help".
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
from reachmu import (C_GRID, PATHS_OUT, assemble_features, auc, flag_share, logloss_rows,
                     population, reach_group, top_set, tree_shape)

N_SHUF = 20
SEED = 20261013
THREADS = 6
DEPTHS = (1, 2, 3, 4, 6)
MDL = (100, 400, 1000, 2000)
LR = 0.05
CATCH = (0.5, 0.8, 0.9)
TOP = 0.2
ALWAYS = ("vol_48", "abs_z")
NEW = os.path.join(paths.DATASETS, "reachfeat2.npz")


def fit_l1(Z, y, tr, va):
    from sklearn.linear_model import LogisticRegression
    best = None
    for C in C_GRID:
        m = LogisticRegression(penalty="l1", C=C, solver="liblinear", max_iter=5000, random_state=0).fit(Z[tr], y[tr])
        ll = logloss_rows(y[va], m.predict_proba(Z[va])[:, 1]).mean()
        if best is None or ll < best[0]:
            best = (ll, m, C)
    return best


def fit_tree(X, y, tr, va, d, names):
    import lightgbm as lgb
    best = None
    for mdl in MDL:
        p = dict(objective="binary", metric="binary_logloss", seed=0, deterministic=True,
                 force_row_wise=True, num_threads=THREADS, verbosity=-1, boosting="gbdt",
                 max_depth=d, num_leaves=2 ** d, min_data_in_leaf=mdl, learning_rate=LR)
        dtr = lgb.Dataset(X[tr], y[tr], feature_name=names)
        dva = lgb.Dataset(X[va], y[va], reference=dtr)
        bst = lgb.train(p, dtr, 5000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        it = bst.best_iteration
        ll = logloss_rows(y[va], bst.predict(X[va], num_iteration=it)).mean()
        if best is None or ll < best[0]:
            best = (ll, bst, it, mdl)
    return best


def perm_importance(fn, X, y, rows_, groups, boots, lc, tag):
    """Grouped permutation on `rows_`: skill points lost per group, with an
    interval per bootstrap set in `boots` ({name: (positions, resamples)})."""
    base = logloss_rows(y[rows_], fn(X[rows_]))
    out = {}
    for gi, (g, js) in enumerate(groups.items()):
        acc = np.zeros(len(rows_))
        for s_ in range(N_SHUF):
            perm = np.random.default_rng([SEED, tag, gi, s_]).permutation(len(rows_))
            Xp = X[rows_].copy()
            Xp[:, js] = X[rows_][perm][:, js]
            acc += logloss_rows(y[rows_], fn(Xp)) - base
        acc /= N_SHUF
        res = {}
        for bn, (pos, bt) in boots.items():
            a, c = acc[pos], lc[pos]
            dr = [100 * a[i_].mean() / c[i_].mean() for i_ in bt]
            res[bn] = (100 * a.mean() / c.mean(), *np.percentile(dr, [2.5, 97.5]))
        out[g] = res
    return out


def main():
    import lightgbm as lgb
    t0 = time.time()
    Y, meta, rows = population()
    PZ = np.load(PATHS_OUT)
    if not np.array_equal(PZ["rows"], rows):
        raise SystemExit("[REACH2] reach_paths.npz rows differ.")
    y = PZ["reach"].astype(int)
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    sp = harness.Split(day, e)
    tr, va, te = sp.train, sp.val, sp.test
    h1, h2 = te & (day < HO_BOUNDARY), te & (day >= HO_BOUNDARY)
    halves = {"HO1": np.flatnonzero(h1), "HO2": np.flatnonzero(h2)}
    print("=" * 120)
    print("REACH-MU v2 -- prune on val, then perp vs index, spike detail, signed breadth")
    print("=" * 120)
    print(f"  {sp.describe()}")
    print(f"  HO1 {len(halves['HO1']):,}   HO2 {len(halves['HO2']):,}")
    names, X, _ = assemble_features(meta, rows, e, tr)
    ix = {nm: j for j, nm in enumerate(names)}
    groups = {}
    for j, nm in enumerate(names):
        groups.setdefault(reach_group(nm), []).append(j)

    # ---------------- STEP 1: prune ----------------
    print()
    print("=" * 120)
    print("STEP 1 -- PRUNE on VALIDATION (held out not read)")
    print("=" * 120)
    mu_, sd_ = X[tr].mean(0), X[tr].std(0)
    sd_[sd_ == 0] = 1.0
    Z = (X - mu_) / sd_
    ll1, l1, C1 = fit_l1(Z, y, tr, va)
    llt, bt2, it2, md2 = fit_tree(X, y, tr, va, 2, names)
    print(f"  logistic L1: C {C1}, val log loss {ll1:.5f};  depth-2 tree: min_data_in_leaf {md2}, "
          f"{it2} rounds, val log loss {llt:.5f}")
    vix = np.flatnonzero(va)
    lc_va = logloss_rows(y[vix], np.full(len(vix), y[tr].mean()))
    bva = {"val": (np.arange(len(vix)), day_boot(day[vix]))}
    impL = perm_importance(lambda M_: l1.predict_proba((M_ - mu_) / sd_)[:, 1], X, y, vix, groups, bva, lc_va, 1)
    impT = perm_importance(lambda M_: bt2.predict(M_, num_iteration=it2), X, y, vix, groups, bva, lc_va, 2)
    kept, dropped = [], []
    print(f"  {'group':<24}{'L1 val [95%]':>32}{'depth-2 val [95%]':>32}   decision")
    for g in groups:
        a, b = impL[g]["val"], impT[g]["val"]
        inc0 = lambda r: r[1] <= 0 <= r[2]
        drop = inc0(a) and inc0(b) and g not in ALWAYS
        (dropped if drop else kept).append(g)
        print(f"  {g:<24}{f'{a[0]:+.4f} [{a[1]:+.4f},{a[2]:+.4f}]':>32}{f'{b[0]:+.4f} [{b[1]:+.4f},{b[2]:+.4f}]':>32}"
              f"   {'DROP' if drop else 'keep' + (' (always)' if g in ALWAYS else '')}")
    kcols = sorted(j for g in kept for j in groups[g])
    print(f"  KEPT {len(kept)} groups ({len(kcols)} columns): {', '.join(kept)}")
    print(f"  DROPPED {len(dropped)} groups: {', '.join(dropped) if dropped else 'none'}")
    print(f"  [{time.time()-t0:.0f}s]", flush=True)

    # ---------------- new features ----------------
    NZ = np.load(NEW, allow_pickle=False)
    et = pd.to_datetime(meta.entry_time).to_numpy("datetime64[ns]")
    if not ((NZ["ticker_a"] == meta.ticker_a.to_numpy(str)).all() and (NZ["entry_time"] == et).all()):
        raise SystemExit("[REACH2] reachfeat2.npz is not aligned to disloc_meta.")
    nn_all = [str(x) for x in NZ["names"]]
    keep_new = [j for j, nm in enumerate(nn_all) if not nm.startswith("basis_rel_move_diff_")]
    XN_all = NZ["X"][rows].astype(float)
    for L_ in (2, 6):
        a_, b_ = nn_all.index(f"basis_rel_move_diff_{L_}"), nn_all.index(f"basis_move_diff_{L_}")
        same = np.allclose(XN_all[:, a_], XN_all[:, b_], equal_nan=True, atol=1e-12)
        print(f"  basis_rel_move_diff_{L_} identical to basis_move_diff_{L_}: {same} -> dropped")
        if not same:
            raise SystemExit("[REACH2] the rel diff is not an identity; do not drop it.")
    nn = [nn_all[j] for j in keep_new]
    fam = dict(zip(nn, [str(NZ["family"][j]) for j in keep_new]))
    XN = XN_all[:, keep_new]
    print()
    print("  Step 2 features missing -> TRAIN median: " + ";  ".join(
        f"{nm} {int((~np.isfinite(XN[:, j])).sum())}" for j, nm in enumerate(nn) if (~np.isfinite(XN[:, j])).any()))
    for j in range(XN.shape[1]):
        bad = ~np.isfinite(XN[:, j])
        XN[bad, j] = np.nanmedian(XN[tr, j])
    sets = {"kept": (X[:, kcols], [names[j] for j in kcols]),
            "kept+new": (np.column_stack([X[:, kcols], XN]), [names[j] for j in kcols] + nn)}

    # ---------------- STEP 3: models ----------------
    print()
    print("=" * 120)
    print(f"STEP 3 -- MODELS (train; every setting on val by log loss; trees gbdt, lr {LR}, "
          f"min_data_in_leaf over {MDL})")
    print("=" * 120)
    from sklearn.linear_model import LogisticRegression
    vc = [ix["vol_48"], ix["vol_48_1m"], ix["sigma"]]
    lrv = LogisticRegression(penalty=None, max_iter=5000).fit(Z[tr][:, vc], y[tr])
    score = {"vol-only": lrv.predict_proba(Z[:, vc])[:, 1]}
    vll = {"vol-only": logloss_rows(y[va], score["vol-only"][va]).mean()}
    fns = {}
    rep = {}
    for sn, (Xs, ns) in sets.items():
        m_, s_ = Xs[tr].mean(0), Xs[tr].std(0)
        s_[s_ == 0] = 1.0
        Zs = (Xs - m_) / s_
        ll_, mdl_, C_ = fit_l1(Zs, y, tr, va)
        k = f"{sn} L1"
        score[k], vll[k] = mdl_.predict_proba(Zs)[:, 1], ll_
        fns[k] = (lambda M_, m=mdl_, a=m_, b=s_: m.predict_proba((M_ - a) / b)[:, 1])
        print(f"  {k:<18} val log loss {ll_:.5f}   C {C_}, nonzero {int((mdl_.coef_ != 0).sum())} of {len(ns)}")
        for d in DEPTHS:
            ll_, bst, it, md = fit_tree(Xs, y, tr, va, d, ns)
            k = f"{sn} d{d}"
            score[k], vll[k] = bst.predict(Xs, num_iteration=it), ll_
            fns[k] = (lambda M_, b=bst, i=it: b.predict(M_, num_iteration=i))
            nt, dmax, dmean, lmax, lmean = tree_shape(lgb.Booster(model_str=bst.model_to_string(num_iteration=it)))
            print(f"  {k:<18} val log loss {ll_:.5f}   min_data_in_leaf {md}, rounds {it}; trees {nt}, "
                  f"depth max {dmax} (mean {dmean:.2f}), leaves max {lmax} (mean {lmean:.1f})   "
                  f"[{time.time()-t0:.0f}s]", flush=True)
        cand = [k for k in vll if k.startswith(sn + " ")]
        rep[sn] = min(cand, key=lambda k: vll[k])
        print(f"  -> {sn} is represented by {rep[sn]} (lowest val log loss)")
    print()

    # ---------------- STEP 4: scoring ----------------
    print("=" * 120)
    print("STEP 4 -- SCORING, held out only")
    print("=" * 120)
    order = ["vol-only"] + [k for k in score if k != "vol-only"]
    res = {}
    for hn, ixh in halves.items():
        yh = y[ixh]
        print(f"  {hn}: n {len(ixh):,}, reverters {int(yh.sum()):,} ({yh.mean():.4f})")
        print(f"    {'model':<18}" + "".join(f"{f'catch {int(100*c)}%: flag / hit':>28}" for c in CATCH)
              + f"{'top20 hit':>11}{'AUC':>8}")
        print(f"    {'random':<18}" + "".join(f"{f'{c:.3f} / {yh.mean():.3f}':>28}" for c in CATCH)
              + f"{yh.mean():>11.3f}{0.5:>8.3f}")
        for mn in order:
            sc = score[mn][ixh]
            cat = [flag_share(sc, yh, c)[:2] for c in CATCH]
            th = yh[top_set(sc, TOP)].mean()
            res[(hn, mn)] = (cat, th)
            tag = "  <- " + [k for k, v in rep.items() if v == mn][0] if mn in rep.values() else ""
            print(f"    {mn:<18}" + "".join(f"{f'{a:.3f} / {b:.3f}':>28}" for a, b in cat)
                  + f"{th:>11.3f}{auc(yh, sc):>8.4f}{tag}")
        print()
    hboot = {hn: day_boot(day[ixh]) for hn, ixh in halves.items()}

    def paired(a, b, hn, what):
        ixh = halves[hn]
        yh, sa, sb = y[ixh], score[a][ixh], score[b][ixh]
        f = ((lambda sc, yy: flag_share(sc, yy, 0.8)[0]) if what == "flag80"
             else (lambda sc, yy: yy[top_set(sc, TOP)].mean()))
        pt = f(sa, yh) - f(sb, yh)
        dr = [f(sa[i_], yh[i_]) - f(sb[i_], yh[i_]) for i_ in hboot[hn]]
        return (pt, *np.percentile(dr, [2.5, 97.5]))

    print("  PAIRED, day-clustered 95% (A minus B). flag80: - = A needs fewer flags; top20: + = A better")
    D = {}
    for lbl, a, b in (("kept+new - kept", rep["kept+new"], rep["kept"]),
                      ("kept+new - vol-only", rep["kept+new"], "vol-only"),
                      ("kept - vol-only", rep["kept"], "vol-only")):
        cells = []
        for hn in halves:
            for what in ("flag80", "top20"):
                r_ = paired(a, b, hn, what)
                D[(lbl, hn, what)] = r_
                star = ("*" if (r_[2] < 0 if what == "flag80" else r_[1] > 0) else
                        "!" if (r_[1] > 0 if what == "flag80" else r_[2] < 0) else " ")
                cells.append(f"{hn} {what} {r_[0]:+.4f} [{r_[1]:+.4f},{r_[2]:+.4f}]{star}")
        print(f"    {lbl:<22}({a} vs {b})")
        print("      " + "  ".join(cells), flush=True)
    print("    (* = A significantly better, ! = A significantly worse)")
    print()
    print("  DEPTH CURVE, kept+new (flag share for an 80% catch / top-20% hit rate)")
    for hn in halves:
        print(f"    {hn}  L1 {res[(hn, 'kept+new L1')][0][1][0]:.3f}/{res[(hn, 'kept+new L1')][1]:.3f}   " +
              "   ".join(f"d{d} {res[(hn, f'kept+new d{d}')][0][1][0]:.3f}/{res[(hn, f'kept+new d{d}')][1]:.3f}"
                         for d in DEPTHS))
    print()

    # ---------------- importance ----------------
    print("=" * 120)
    print(f"IMPORTANCE, held out, the kept+new representative ({rep['kept+new']}); {N_SHUF} shuffles; "
          "log-loss skill points lost; day-clustered 95% per half")
    print("=" * 120)
    Xs, ns = sets["kept+new"]
    gK = {}
    for j, nm in enumerate(ns):
        gK.setdefault(fam[nm] if nm in fam else reach_group(nm), []).append(j)
    gM = {nm: [j] for j, nm in enumerate(ns) if nm in fam}
    teix = np.flatnonzero(te)
    lc_te = logloss_rows(y[teix], np.full(len(teix), y[tr].mean()))
    pos = {hn: np.flatnonzero(np.isin(teix, ixh)) for hn, ixh in halves.items()}
    bts = {"held out": (np.arange(len(teix)), day_boot(day[teix]))}
    for hn in halves:
        bts[hn] = (pos[hn], day_boot(day[teix][pos[hn]]))
    fn = fns[rep["kept+new"]]
    I_g = perm_importance(fn, Xs, y, teix, gK, bts, lc_te, 3)
    I_m = perm_importance(fn, Xs, y, teix, gM, bts, lc_te, 4)

    def line(lbl, r):
        return (f"    {lbl:<26}" + "   ".join(
            f"{bn} {r[bn][0]:+.4f} [{r[bn][1]:+.4f},{r[bn][2]:+.4f}]{'+' if r[bn][1] > 0 else ' '}"
            for bn in ("held out", "HO1", "HO2")))
    print("  GROUPS (Step 2 families as one group each; + = interval wholly above zero)")
    for g in sorted(gK, key=lambda k: -I_g[k]["held out"][0]):
        print(line(g + (" [NEW]" if g in ("perp_index", "spike_detail", "signed_breadth") else ""), I_g[g]))
    print("  STEP 2 MEMBERS, each alone")
    for f_ in ("perp_index", "spike_detail", "signed_breadth"):
        print(f"   {f_}")
        for nm in [k for k in gM if fam[k] == f_]:
            print(line(nm, I_m[nm]))
    print()

    # ---------------- reading rules ----------------
    print("=" * 120)
    print("READING RULES")
    print("=" * 120)

    print(f"  representatives: kept = {rep['kept']}, kept+new = {rep['kept+new']}"
          + ("" if rep['kept'].split()[-1] == rep['kept+new'].split()[-1] else
             "  (DIFFERENT learners: kept+new - kept mixes a learner change with the new features)"))
    l1d = {hn: paired("kept+new L1", "kept L1", hn, "flag80") for hn in halves}
    print("  same-learner, reported, not gating: kept+new L1 - kept L1, flag80   "
          + "   ".join(f"{hn} {r_[0]:+.4f} [{r_[1]:+.4f},{r_[2]:+.4f}]" for hn, r_ in l1d.items()))
    print(f"  sigma survived the prune: {'sigma' in kept} "
          + ("" if "sigma" in kept else "(kept+new does not contain all vol-only inputs; SIGNAL compares "
             "non-nested sets, which is conservative)"))

    def clears(lbl):
        return [hn for hn in halves if D[(lbl, hn, "flag80")][2] < 0]
    hn_new, hn_sig = clears("kept+new - kept"), clears("kept+new - vol-only")
    print(f"  NEW FEATURES HELP (kept+new - kept, flag80 below zero in both halves): "
          f"{'YES' if len(hn_new) == 2 else 'NO'}  (clears in: {', '.join(hn_new) or 'neither'})")
    print(f"  SIGNAL OVERALL (kept+new - vol-only, both halves): "
          f"{'YES' if len(hn_sig) == 2 else 'NO'}  (clears in: {', '.join(hn_sig) or 'neither'})")
    reg = [n_ for n_, h_ in (("new features help", hn_new), ("signal overall", hn_sig)) if len(h_) == 1]
    print(f"  REGIME-DEPENDENT: {', '.join(reg) if reg else 'none'}")
    for f_ in ("perp_index", "spike_detail", "signed_breadth"):
        c_ = [hn for hn in halves if I_g[f_][hn][1] > 0]
        verdict = ("helped in both halves" if len(c_) == 2 else
                   f"clears in {c_[0]} only (regime-dependent)" if len(c_) == 1 else "did not help")
        print(f"  FAMILY {f_:<15} {verdict}")
    print("  Nothing written to the registry or the live system. No stop. No funding data.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 120)


if __name__ == "__main__":
    main()
