"""HL-FLOW1 Part 3: do flow features beat position? H1 / H2 / H3 and the market block.

    python -u research/dislocation_model/hl3_tests.py > research/dislocation_model/logs/hl3_tests.log

Everything below is FIXED before any model is fitted. Held out is touched once, at
scoring. Nothing is chosen on held out.

POPULATION, TARGET, SPLIT: hl3_common.Pop (the dislocations with a finite 1-minute
window; reach = depth >= |z_at_entry| on 1-minute closes, mu frozen, no stop, 10h;
chance = 50 sign-flip seeds; CUT 2026-05-25; validation = last 20% of the fit days;
HO1 / HO2 = held-out days before / from 2026-08-15).

SETS (all fitted on train, every setting on validation by log loss):
  reference  log vol_48, log vol_48_1m, log sigma, |z_at_entry|  (hl3_reference.npz)
  H1, H2, H3, MARKET   reference + that group's columns (H3 = top3 and wallets_per_musd,
             4 columns; the two TWAP columns are NOT in H3 or ALL: TWAP is tested only
             on the rows where it exists; MARKET is two-sided, no sign assumed)
  ALL        reference + H1 + H2 + H3 (no TWAP) + MARKET
  H3-TWAP    reference + the two twap_share columns, on the rows where TWAP exists
             (the reference is refitted on the same rows for its comparison)
  KEPT       reference + the groups that survive the pruning rule below
A group's NaNs are filled with the TRAIN median of each column and ONE indicator
column per group (1 if any column of the group was NaN) is added; the counts are
printed. Nothing else is zero-filled.
MODELS per set: logistic L1 (C over {0.001 .. 3}, standardised on train) and LightGBM
gbdt at max_depth 1, 2, 3, 4 (num_leaves 2^d, min_data_in_leaf over {100, 400, 1000,
2000}, lr 0.05, rounds by early stopping on validation log loss, patience 100).
The set's representative = its lowest-validation-log-loss model.
PRUNING (validation only, before scoring): the ALL set's logistic L1 and depth-2 tree;
grouped permutation importance of each flow group, 20 shuffles, log-loss skill points
lost, day-clustered 95% over validation days. A group is DROPPED unless some model's
interval is wholly above zero (pruning rule, user 2026-10-13).

SCORING (held out, HO1 and HO2 separately, ranked within the half): flag share at 50 /
80 / 90% catch, top-20% hit rate, beyond-chance gap (reach rate - mean chance
probability) of the episodes flagged at 80% catch. Paired day-clustered 95% intervals
(hl3_common, ranks recomputed in each resample) of every set's every model MINUS the
Part 1 reference logistic, on flag80 (primary), top20 and gap80. Same-learner diagnostics
(set's L1 minus the reference set's L1; set's best tree minus the reference set's best
tree) are printed beside the gating test; a disagreement is flagged.
PERMUTATION NULL: for each set's representative, refit the same learner and settings with
that set's flow block row-permuted (train and held-out each permuted), 20 seeds; the
observed delta (representative minus the reference logistic, flag80) is printed against
the null's range.

READING RULES ("clears" = the 95% interval excludes zero; sign folding is the primary
reading):
  HELP               representative's flag80 minus reference wholly below zero in BOTH halves
  REGIME-DEPENDENT   exactly one half; not a pass
  HARMS              wholly above zero in either half (printed, not a pass)
  DIRECTION CHECK    per flow feature with an expected sign: the held-out correlation of
                     the feature with the reference's residual (reach - predicted
                     probability), day-clustered 95% per half, against the expected sign;
                     wholly on the wrong side in a half = "WRONG DIRECTION" (a finding).
CELLS: 7 scored sets x 5 models x 2 halves x 3 measures = 210. At 95% two-sided the
expected number of cells whose interval excludes zero by chance is 10.5 (5.3 in the good
direction); read the hits against that.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import paths
import reachmu2
from hl3_common import CATCH, Pop, measure
from envelope import day_boot
from reachmu import auc, flag_share, logloss_rows, tree_shape

reachmu2.THREADS = 8
FLOWFEAT = os.path.join(paths.DATASETS, "flowfeat.npz")
REF = os.path.join(paths.DATASETS, "hl3_reference.npz")
DEPTHS = (1, 2, 3, 4)
N_SHUF = reachmu2.N_SHUF
N_NULL = 20
MEASURES = ("flag80", "top20", "gap80")
PAIR_GROUPS = ("H1", "H2", "H3", "MARKET")


def prep_block(Xg, tr):
    """Fill a group's NaNs with the train median per column; add one any-NaN indicator."""
    nanm = ~np.isfinite(Xg)
    out = Xg.astype(float).copy()
    for j in range(out.shape[1]):
        out[nanm[:, j], j] = np.nanmedian(Xg[tr, j])
    return np.column_stack([out, nanm.any(1).astype(float)]), nanm


def fit_set(Xs, names, y, tr, va, mask=None):
    """L1 + trees d1..d4 on a matrix; returns {model: score on every row}, val log loss, fns."""
    import lightgbm as lgb
    m = np.ones(len(y), bool) if mask is None else mask
    trm, vam = tr & m, va & m
    mu_, sd_ = Xs[trm].mean(0), Xs[trm].std(0)
    sd_[sd_ == 0] = 1.0
    Z = (Xs - mu_) / sd_
    score, vll, fns, info = {}, {}, {}, {}
    ll, mdl, C = reachmu2.fit_l1(Z, y, trm, vam)
    score["L1"], vll["L1"] = mdl.predict_proba(Z)[:, 1], ll
    fns["L1"] = (lambda M_, m_=mdl, a=mu_, b=sd_: m_.predict_proba((M_ - a) / b)[:, 1])
    info["L1"] = f"C {C}, nonzero {int((mdl.coef_ != 0).sum())} of {len(names)}"
    for d in DEPTHS:
        ll, bst, it, md = reachmu2.fit_tree(Xs, y, trm, vam, d, names)
        k = f"d{d}"
        score[k], vll[k] = bst.predict(Xs, num_iteration=it), ll
        fns[k] = (lambda M_, b=bst, i=it: b.predict(M_, num_iteration=i))
        nt, dmax, dmean, lmax, lmean = tree_shape(lgb.Booster(model_str=bst.model_to_string(num_iteration=it)))
        info[k] = f"min_data_in_leaf {md}, rounds {it}, depth max {dmax}, leaves max {lmax}"
    rep = min(vll, key=vll.get)
    return score, vll, fns, info, rep


def run(P, D):
    """The build 3 test design on any population P (hl3_common.Pop-like) and any design D.

    D: title; ref_X, ref_p, rnames (the reference set and its Part 1 scores); FX (rows x features, raw,
    NaN allowed), names, expect; groups (ordered tuple), cols_of {group: column indices}; extra =
    (name, columns): a sub-group tested ONLY on the rows where it exists (build 3's TWAP).
    """
    t0 = time.time()
    y, tr, va, te = P.y, P.tr, P.va, P.te
    day = P.day
    ref_X, ref_p, rnames = D["ref_X"], D["ref_p"], D["rnames"]
    FX, names, expect = D["FX"], D["names"], D["expect"]
    GROUPS, cols_of = tuple(D["groups"]), D["cols_of"]
    XN, twap_cols = D["extra"]
    twap_ok = np.isfinite(FX[:, twap_cols]).all(1)
    print("=" * 118)
    print(D["title"])
    print("=" * 118)
    print(f"  {P.sp.describe()}")
    print(f"  matched {P.n:,}; HO1 {len(P.halves['HO1']):,}  HO2 {len(P.halves['HO2']):,}")
    print(f"  features {len(names)} (groups: " + ", ".join(f"{g} {len(c)}" for g, c in cols_of.items())
          + f"; {XN} {len(twap_cols)}); {XN} exists on {int(twap_ok.sum()):,} of {P.n:,} rows")
    blocks, nanmask = {}, {}
    print("  group NaN fill counts (rows with any NaN in the group -> train-median fill + indicator):")
    for g, c in cols_of.items():
        blocks[g], nanmask[g] = prep_block(FX[:, c], tr)
        print(f"    {g:<13}{int(nanmask[g].any(1).sum()):>8,} of {P.n:,} rows"
              + "   per column max " + f"{int(nanmask[g].sum(0).max()):,}")
    nsets = len(GROUPS) + 3
    print(f"  CELLS: {nsets} sets x 5 models x 2 halves x {len(MEASURES)} measures = {nsets * 5 * 2 * len(MEASURES)}; "
          f"expected by chance at 95% two-sided: {0.05 * nsets * 5 * 2 * len(MEASURES):.1f} "
          f"({0.025 * nsets * 5 * 2 * len(MEASURES):.1f} in the good direction)")

    # ------------------------------------------------------------ sets
    sets = {"reference": (ref_X, rnames)}
    for g in GROUPS:
        sets[g] = (np.column_stack([ref_X, blocks[g]]), rnames + [names[j] for j in cols_of[g]] + [f"{g}_nan"])
    sets["ALL"] = (np.column_stack([ref_X] + [blocks[g] for g in GROUPS]),
                   rnames + sum(([names[j] for j in cols_of[g]] + [f"{g}_nan"] for g in GROUPS), []))
    tw_block = FX[:, twap_cols].copy()
    sets[XN] = (np.column_stack([ref_X, np.where(np.isfinite(tw_block), tw_block, 0.0)]),
                       rnames + [names[j] for j in twap_cols])
    print()
    print("=" * 118)
    print("STEP 1 -- PRUNE on VALIDATION (held out not read)")
    print("=" * 118)
    Xall, nall = sets["ALL"]
    mu_, sd_ = Xall[tr].mean(0), Xall[tr].std(0); sd_[sd_ == 0] = 1.0
    Zall = (Xall - mu_) / sd_
    ll1, l1, C1 = reachmu2.fit_l1(Zall, y, tr, va)
    llt, bt2, it2, md2 = reachmu2.fit_tree(Xall, y, tr, va, 2, nall)
    print(f"  ALL: logistic L1 C {C1}, val log loss {ll1:.5f};  depth-2 tree: min_data_in_leaf {md2}, {it2} rounds, val log loss {llt:.5f}")
    gcols = {}
    for j, nm in enumerate(nall):
        for g in GROUPS:
            if nm in [names[c] for c in cols_of[g]] or nm == f"{g}_nan":
                gcols.setdefault(g, []).append(j)
    vix = np.flatnonzero(va)
    lc_va = logloss_rows(y[vix], np.full(len(vix), y[tr].mean()))
    bva = {"val": (np.arange(len(vix)), day_boot(day[vix]))}
    impL = reachmu2.perm_importance(lambda M_: l1.predict_proba((M_ - mu_) / sd_)[:, 1], Xall, y, vix, gcols, bva, lc_va, 1)
    impT = reachmu2.perm_importance(lambda M_: bt2.predict(M_, num_iteration=it2), Xall, y, vix, gcols, bva, lc_va, 2)
    kept = []
    print(f"  {'group':<8}{'L1 val skill pts [95%]':>34}{'depth-2 val skill pts [95%]':>34}   decision")
    for g in GROUPS:
        a, b = impL[g]["val"], impT[g]["val"]
        keep = a[1] > 0 or b[1] > 0
        if keep:
            kept.append(g)
        print(f"  {g:<8}{f'{a[0]:+.4f} [{a[1]:+.4f},{a[2]:+.4f}]':>34}{f'{b[0]:+.4f} [{b[1]:+.4f},{b[2]:+.4f}]':>34}   "
              f"{'keep' if keep else 'DROP'}")
    print(f"  KEPT groups: {', '.join(kept) if kept else 'none (KEPT set = reference)'}")
    sets["KEPT"] = (np.column_stack([ref_X] + [blocks[g] for g in kept]) if kept else ref_X,
                    rnames + sum(([names[j] for j in cols_of[g]] + [f"{g}_nan"] for g in kept), []))
    print(f"  [{time.time() - t0:.0f}s]", flush=True)

    # ------------------------------------------------------------ models
    print()
    print("=" * 118)
    print("STEP 2 -- MODELS (train; every setting on validation by log loss)")
    print("=" * 118)
    SC, VL, FN, REP = {}, {}, {}, {}
    for sn, (Xs, ns) in sets.items():
        mask = twap_ok if sn == XN else None
        score, vll, fns, info, rep = fit_set(Xs, ns, y, tr, va, mask)
        SC[sn], VL[sn], FN[sn], REP[sn] = score, vll, fns, rep
        print(f"  {sn:<10}" + "   ".join(f"{k} {vll[k]:.5f}" for k in vll) + f"   -> representative {rep}")
        for k, v in info.items():
            print(f"      {k:<4}{v}")
        print(f"  [{time.time() - t0:.0f}s]", flush=True)
    # the TWAP set is compared with the reference refitted on the SAME rows
    sc_tw_ref, vl_tw_ref, fn_tw_ref, _, rep_tw_ref = fit_set(ref_X, rnames, y, tr, va, twap_ok)
    print(f"  reference refitted on the {XN} rows: " + "   ".join(f"{k} {vl_tw_ref[k]:.5f}" for k in vl_tw_ref)
          + f"   -> representative {rep_tw_ref}")

    # ------------------------------------------------------------ scoring
    print()
    print("=" * 118)
    print("STEP 3 -- SCORING, held out only, HO1 and HO2 separately (day-clustered 95%)")
    print("=" * 118)
    tw_halves = {hn: ix[twap_ok[ix]] for hn, ix in P.halves.items()}
    tw_boot = {hn: day_boot(day[ix]) for hn, ix in tw_halves.items()}
    for hn, ix in P.halves.items():
        yh = y[ix]
        print(f"  {hn}: n {len(ix):,}, reverters {int(yh.sum()):,} ({yh.mean():.4f}), mean chance {P.chance[ix].mean():.4f}")
        print(f"    {'set / model':<22}" + "".join(f"{f'catch {int(100 * c)}%: flag / hit':>26}" for c in CATCH)
              + f"{'top20':>8}{'gap80':>9}{'AUC':>8}")
        rows_ = [("reference logistic", ref_p)] + [(f"{sn} {k}", SC[sn][k]) for sn in sets for k in SC[sn]]
        for lbl, sc in rows_:
            s_ = sc[ix]
            cat = [flag_share(s_, yh, c)[:2] for c in CATCH]
            print(f"    {lbl:<22}" + "".join(f"{f'{a:.3f} / {b:.3f}':>26}" for a, b in cat)
                  + f"{measure('top20', s_, yh, P.chance[ix]):>8.3f}{measure('gap80', s_, yh, P.chance[ix]):>+9.4f}{auc(yh, s_):>8.4f}")
        print()
    print("  PAIRED, every model minus the Part 1 reference logistic. flag80: - = better; top20, gap80: + = better.")
    print("  * = wholly on the good side, ! = wholly on the bad side. (TWAP rows: against the reference logistic's scores on those rows.)")
    D = {}
    for sn in sets:
        if sn == "reference":
            continue
        for k in SC[sn]:
            cells = []
            for hn in P.halves:
                for what in MEASURES:
                    ixh = P.halves[hn]
                    if sn == XN:
                        ixh = tw_halves[hn]
                    sa, sb = SC[sn][k][ixh], ref_p[ixh]
                    yy, cc = y[ixh], P.chance[ixh]
                    pt = measure(what, sa, yy, cc) - measure(what, sb, yy, cc)
                    boots = tw_boot[hn] if sn == XN else P.hboot[hn]
                    dr = [measure(what, sa[b], yy[b], cc[b]) - measure(what, sb[b], yy[b], cc[b]) for b in boots]
                    lo, hi = np.percentile(dr, [2.5, 97.5])
                    D[(sn, k, hn, what)] = (pt, lo, hi)
                    good = hi < 0 if what == "flag80" else lo > 0
                    bad = lo > 0 if what == "flag80" else hi < 0
                    cells.append(f"{hn} {what} {pt:+.4f} [{lo:+.4f},{hi:+.4f}]{'*' if good else '!' if bad else ' '}")
            print(f"    {sn + ' ' + k:<14}" + "  ".join(cells))
    nhit = sum(1 for (sn, k, hn, w), (pt, lo, hi) in D.items()
               if (hi < 0 if w == "flag80" else lo > 0))
    nbad = sum(1 for (sn, k, hn, w), (pt, lo, hi) in D.items()
               if (lo > 0 if w == "flag80" else hi < 0))
    print(f"  CELLS scored {len(D)}: good-side hits {nhit}, bad-side {nbad}  (expected by chance: "
          f"{0.025 * len(D):.1f} each side at 95% two-sided)")
    print()
    # same-learner diagnostics
    print("  SAME-LEARNER DIAGNOSTICS, flag80 (set's L1 minus reference-set L1; set's best tree minus reference-set best tree)")
    ref_tree = min((k for k in VL["reference"] if k != "L1"), key=lambda k: VL["reference"][k])
    dis = []
    for sn in sets:
        if sn in ("reference",):
            continue
        base = (SC["reference"], ref_tree) if sn != XN else (sc_tw_ref, min((k for k in vl_tw_ref if k != "L1"), key=lambda k: vl_tw_ref[k]))
        tree_k = min((k for k in VL[sn] if k != "L1"), key=lambda k: VL[sn][k])
        for lbl, a, b in (("L1 - L1", SC[sn]["L1"], base[0]["L1"]), (f"{tree_k} - {base[1]}", SC[sn][tree_k], base[0][base[1]])):
            res = []
            for hn in P.halves:
                ixh = tw_halves[hn] if sn == XN else P.halves[hn]
                boots = tw_boot[hn] if sn == XN else P.hboot[hn]
                sa, sb, yy, cc = a[ixh], b[ixh], y[ixh], P.chance[ixh]
                pt = measure("flag80", sa, yy, cc) - measure("flag80", sb, yy, cc)
                dr = [measure("flag80", sa[b_], yy[b_], cc[b_]) - measure("flag80", sb[b_], yy[b_], cc[b_]) for b_ in boots]
                lo, hi = np.percentile(dr, [2.5, 97.5])
                res.append((hn, pt, lo, hi))
            both = all(r[3] < 0 for r in res)
            gate_both = all(D[(sn, REP[sn], hn, "flag80")][2] < 0 for hn in P.halves)
            print(f"    {sn:<9}{lbl:<14}" + "  ".join(f"{h} {p:+.4f} [{lo:+.4f},{hi:+.4f}]" for h, p, lo, hi in res)
                  + f"   same-learner clears both: {'YES' if both else 'no '}")
            if both != gate_both:
                dis.append((sn, lbl, both, gate_both))
    print("  DISAGREEMENTS between the same-learner test and the gating test (representative vs reference logistic): "
          + (", ".join(f"{s} {l} (same-learner {a}, gating {b})" for s, l, a, b in dis) if dis else "none"))

    # ------------------------------------------------------------ permutation null
    print()
    print("=" * 118)
    print(f"PERMUTATION NULL -- representative refitted with the set's flow block row-permuted ({N_NULL} seeds)")
    print("=" * 118)
    for sn in list(GROUPS) + ["ALL", "KEPT"]:
        Xs, ns = sets[sn]
        k = REP[sn]
        nflow = Xs.shape[1] - 4
        if nflow == 0:
            print(f"  {sn}: no flow columns")
            continue
        nulls = {hn: [] for hn in P.halves}
        d_ = int(k[1]) if k != "L1" else None
        for sd in range(N_NULL):
            rng = np.random.default_rng([20261015, sd])
            Xp = Xs.copy()
            pf = np.flatnonzero(P.sp.fit)
            Xp[np.ix_(pf, np.arange(4, Xs.shape[1]))] = Xs[np.ix_(rng.permutation(pf), np.arange(4, Xs.shape[1]))]
            pt_ = np.flatnonzero(te)
            Xp[np.ix_(pt_, np.arange(4, Xs.shape[1]))] = Xs[np.ix_(rng.permutation(pt_), np.arange(4, Xs.shape[1]))]
            if k == "L1":
                mu2, sd2 = Xp[tr].mean(0), Xp[tr].std(0); sd2[sd2 == 0] = 1.0
                _, mdl, _ = reachmu2.fit_l1((Xp - mu2) / sd2, y, tr, va)
                s_ = mdl.predict_proba((Xp - mu2) / sd2)[:, 1]
            else:
                _, bst, it, _ = reachmu2.fit_tree(Xp, y, tr, va, d_, ns)
                s_ = bst.predict(Xp, num_iteration=it)
            for hn, ix in P.halves.items():
                nulls[hn].append(measure("flag80", s_[ix], y[ix], P.chance[ix]) - measure("flag80", ref_p[ix], y[ix], P.chance[ix]))
        for hn in P.halves:
            obs = D[(sn, k, hn, "flag80")][0]
            nu = np.array(nulls[hn])
            print(f"  {sn:<7}{k:<4}{hn}: observed {obs:+.4f}; null min {nu.min():+.4f} median {np.median(nu):+.4f} max {nu.max():+.4f}"
                  f"   observed below the null's min: {'YES' if obs < nu.min() else 'no'}")
        print(f"  [{time.time() - t0:.0f}s]", flush=True)

    # ------------------------------------------------------------ direction check
    print()
    print("=" * 118)
    print("DIRECTION CHECK -- held-out correlation of each flow feature with the reference's residual (reach - predicted)")
    print("=" * 118)
    resid = y - ref_p
    wrong = []
    print(f"  {'feature':<34}{'expect':>7}   HO1 corr [95%]            HO2 corr [95%]            verdict")
    for j, nm in enumerate(names):
        cells, verd = [], []
        for hn, ix in P.halves.items():
            x, r_ = FX[ix, j], resid[ix]
            def cor(sub):
                m = np.isfinite(x[sub])
                return float(np.corrcoef(x[sub][m], r_[sub][m])[0, 1]) if m.sum() > 50 else np.nan
            full = np.arange(len(ix))
            pt = cor(full)
            dr = [cor(b) for b in P.hboot[hn]]
            lo, hi = np.nanpercentile(dr, [2.5, 97.5])
            cells.append(f"{pt:+.4f} [{lo:+.4f},{hi:+.4f}]")
            e = expect[j]
            if e == "+":
                verd.append("ok" if lo > 0 else "WRONG" if hi < 0 else "-")
            elif e == "-":
                verd.append("ok" if hi < 0 else "WRONG" if lo > 0 else "-")
            else:
                verd.append("+" if lo > 0 else "neg" if hi < 0 else "-")
        if "WRONG" in verd:
            wrong.append(nm)
        print(f"  {nm:<34}{expect[j] or '2-sided':>7}   {cells[0]:<26}{cells[1]:<26}{'/'.join(verd)}")
    print(f"  WRONG DIRECTION in at least one half: {', '.join(wrong) if wrong else 'none'}")

    # ------------------------------------------------------------ reading rules
    print()
    print("=" * 118)
    print("READING RULES")
    print("=" * 118)
    for sn in list(GROUPS) + ["ALL", XN, "KEPT"]:
        k = REP[sn]
        c = [hn for hn in P.halves if D[(sn, k, hn, "flag80")][2] < 0]
        h = [hn for hn in P.halves if D[(sn, k, hn, "flag80")][1] > 0]
        verdict = ("HELP" if len(c) == 2 else f"REGIME-DEPENDENT (clears in {c[0]} only)" if len(c) == 1 else "no help")
        if h:
            verdict += f";  HARMS in {', '.join(h)}"
        print(f"  {sn:<8} representative {k:<3}: {verdict}")
    print("  Nothing written to the registry or the live system. No stop, no profit, no delayed features.")
    print(f"  [{time.time() - t0:.0f}s]")
    print("=" * 118)


def main():
    """Part 3 of HL-FLOW1: the pair-level design."""
    P = Pop()
    R = np.load(REF)
    assert np.array_equal(R["rows"], P.rows), "hl3_reference.npz rows differ"
    Fz = np.load(FLOWFEAT, allow_pickle=False)
    names = [str(x) for x in Fz["names"]]
    grp = [str(x) for x in Fz["groups"]]
    D = dict(title="HL-FLOW1 PART 3 -- flow features against position",
             ref_X=R["X"], ref_p=R["ref"], rnames=["log_vol_48", "log_vol_48_1m", "log_sigma", "abs_z"],
             FX=Fz["X"][P.rows].astype(float), names=names, expect=[str(x) for x in Fz["expect"]],
             groups=PAIR_GROUPS, cols_of={g: [j for j, gg in enumerate(grp) if gg == g] for g in PAIR_GROUPS},
             extra=("H3-TWAP", [j for j, gg in enumerate(grp) if gg == "H3-TWAP"]))
    run(P, D)


if __name__ == "__main__":
    main()
