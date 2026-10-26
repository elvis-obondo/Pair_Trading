"""HL-WALLET1 Part 3: do exact wallet concentration (H3), wallet skill (H4) and the backstop wallets predict the return to mu? Rolling walk-forward.

    python -u research/dislocation_model/hl5_tests.py > research/dislocation_model/logs/hl5_tests.log

THE DESIGN IS HL-EVENT1's (hl4_tests / hl3_tests) scored by rolling.py (docs/prompts/HL_BUILD6_FULL_POPULATION.md, "Rolling (walk-forward) test"),
fixed before any fit. POPULATION and TARGET as hl4_tests.CoinPop (events with a finite 1-minute window and a 10h outcome; reach = depth >= |z| on the
1-minute closes, mu frozen, no stop; chance = 50 sign-flip seeds). REFERENCE: unpenalised logistic on log vol_48, log vol_48_1m, log sigma, |z|,
refitted per fold. FEATURES AT t = 0 (hl5_features.py, windows P1, C6, C24 = 33 model inputs, signed by the push d):
  CONC_EXACT  top1_share (+), top3_share (+), hhi (+), n_wallets (-), persistent_share (+), twap_share (+)     6 x 3 = 18
              [expected: higher concentration or TWAP -> reaches mu MORE (+); more wallets -> LESS (-)]
  SKILL       skill_mean (-), bottom_decile_share (+), top_decile_share (-), prior_forced_share (+)             4 x 3 = 12
              [expected: pushing by weak wallets -> reaches mu MORE; by strong -> LESS]
  BACKSTOP    backstop_share (two-sided)                                                                       1 x 3 = 3
  The proxy H3 group of builds 3 and 4 (top3 proxy, wallets per $M) is retired from the tests. IMPACT is not part of this build.
SETS: reference, CONC_EXACT, SKILL, BACKSTOP, ALL, KEPT (reference + the groups that survive the pruning rule on that fold's validation).
MODELS: logistic L1, LightGBM d1-d4, and "rep" = the fold's lowest-validation-log-loss model. NaN handling: that fold's train median + one
any-NaN indicator per group.
CELLS (counted before running): Part 3 pooled cells = 5 sets x (5 models + rep) x 3 measures = 90; strong-event row (|z| >= 3 OR forced share P1 > 0):
(3 groups + ALL) x rep x 3 measures = 12; Q1 event-time comparison: 5 series x 5 windows x 2 control sets = 50. Total 152. Expected pooled-interval
hits by chance at 95%: 7.6 (3.8 per sign); a FINDING also needs the same sign in >= 2/3 of the folds (rolling.verdict).
Q1: events minus matched controls (build 4's two control sets) for top1_share, hhi, n_wallets, persistent_share, bottom_decile_share over P1, P2, P3,
C6, C24 on all events in the test blocks (>= first test block start); pooled day-clustered interval and the share of folds with the pooled sign.
Single cut (CUT 2026-05-25, one fold to the end, embargo applied) is printed as ONE like-for-like row of each set's rep, not counted as cells.
Permutation null: rolling.shuffle_days, 20 seeds, the whole rolling pipeline.
"""
import os, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import harness
import paths
import coinevents as ce
import eventflow as ef
import hl3_tests as h3
import hl4_tests as h4
import hl5_features as H
import reachmu2
import rolling as R
from envelope import day_boot
from hl3_common import measure
from reachmu import auc

GROUPS = ("CONC_EXACT", "SKILL", "BACKSTOP")
WIN3 = ("P1", "C6", "C24")
SPEC = {"CONC_EXACT": [("top1", "+"), ("top3", "+"), ("hhi", "+"), ("nw", "-"), ("pers", "+"), ("twap", "+")],
        "SKILL": [("skill_mean", "-"), ("bot", "+"), ("topd", "-"), ("prior_forced", "+")],
        "BACKSTOP": [("backstop", "")]}
Q1_SERIES = ("top1", "hhi", "nw", "pers", "bot")
SETS_SCORED = ("CONC_EXACT", "SKILL", "BACKSTOP", "ALL", "KEPT")
FEAT_NPZ = H.OUT


def design(P):
    Z = np.load(FEAT_NPZ)
    ev = Z["ev"][P.rows].astype(float)
    feats, wn = [str(x) for x in Z["feats"]], [str(x) for x in Z["windows"]]
    cols, names, expect, grp = [], [], [], []
    for g in GROUPS:
        for f, e in SPEC[g]:
            for w in WIN3:
                cols.append(ev[:, wn.index(w), feats.index(f)]); names.append(f"{f}_{w}"); expect.append(e); grp.append(g)
    FX = np.column_stack(cols)
    cols_of = {g: [j for j, gg in enumerate(grp) if gg == g] for g in GROUPS}
    raw = np.column_stack([P.vol48, P.vol48m, P.meta["sigma"].to_numpy(float)])
    with np.errstate(divide="ignore", invalid="ignore"):
        lg = np.where(raw > 0, np.log(raw), np.nan)
    ref_X = np.column_stack([lg, np.abs(P.e)])          # NaNs kept: rolling.py fills them per fold from that fold's train rows
    return ref_X, FX, names, expect, cols_of


class Sub:
    """A restricted copy of a population (rows kept by a mask), with the attributes rolling.py reads."""

    def __init__(self, P, m):
        self.n = int(m.sum()); self.day = P.day[m]; self.e = P.e[m]; self.y = P.y[m]; self.chance = P.chance[m]
        self.m = m


def _null_job(seed):
    reachmu2.THREADS = 1
    P, D = _G["P"], _G["D"]
    rng = np.random.default_rng([20261016, seed])
    y2, c2 = R.shuffle_days(P.day, P.y, P.chance, rng)
    Rn = R.run_pipeline(P, D, y2, c2)
    return {k: v[:3] for k, v in R.cells(P, y2, c2, Rn, SETS_SCORED).items() if k[1] == "rep"}


_G = {}


def fmt(c):
    return f"{c[0]:+.4f} [{c[1]:+.4f},{c[2]:+.4f}]"


def main():
    t0 = time.time()
    P = h4.CoinPop()
    ref_X, FX, names, expect, cols_of = design(P)
    D = dict(ref_X=ref_X, rnames=["log_vol_48", "log_vol_48_1m", "log_sigma", "abs_z"], FX=FX, names=names, groups=GROUPS, cols_of=cols_of)
    y, chance = P.y, P.chance
    reachmu2.THREADS = 8
    folds = R.make_folds(P.day)
    print("=" * 118)
    print("HL-WALLET1 PART 3 -- wallet concentration, skill and backstop, rolling walk-forward")
    print("=" * 118)
    print(f"  events {len(P.EV_all):,}; matched population {P.n:,}; days {pd.Timestamp(P.day.min()).date()}..{pd.Timestamp(P.day.max()).date()}; "
          f"reach {y.mean():.4f}, mean chance {chance.mean():.4f}")
    print(f"  features {len(names)} (" + ", ".join(f"{g} {len(c)}" for g, c in cols_of.items()) + ")")
    for g in GROUPS:
        print(f"    {g:<11} finite share per column: " + ", ".join(f"{names[j]} {np.isfinite(FX[:, j]).mean():.3f}" for j in cols_of[g][:6]) + " ...")
    print(f"  folds: first test block {pd.Timestamp(folds[0][0]).date()}, blocks of {R.BLOCK_DAYS} days, {len(folds)} folds, embargo 1 day; "
          f"cells: 90 + 12 + 50 = 152; expected by chance 7.6 (3.8 per sign)")
    print()
    print("ROLLING PIPELINE (per fold: train, val, test; kept groups; each set's rep model)")
    Rr = R.run_pipeline(P, D, y, chance, verbose=True)
    print("  reference-column NaN fills per fold (rows filled with that fold's train median; columns log vol_48, log vol_48_1m, log sigma, |z|): "
          + "; ".join(f"{k}: {n}" for k, n in Rr["ref_fill"]))
    te = np.flatnonzero(Rr["fold_of"] >= 0)
    nfold = len(np.unique(Rr["fold_of"][te]))
    boots = day_boot(P.day[te])
    print(f"  pooled test rows {len(te):,} over {nfold} folds; {len(np.unique(P.day[te]))} test days (the effective independent sample for the intervals)")
    # ------------------------------------------------------------ reference
    ref = Rr["ref"]
    print()
    print("REFERENCE (unpenalised logistic, refitted per fold)")
    for w in R.MEASURES:
        pt = measure(w, ref[te], y[te], chance[te])
        dr = [measure(w, ref[te][b], y[te][b], chance[te][b]) for b in boots]
        lo, hi = np.percentile(dr, [2.5, 97.5])
        print(f"  pooled {w:<7}{pt:+.4f} [{lo:+.4f},{hi:+.4f}]")
    print(f"  pooled AUC {auc(y[te], ref[te]):.4f}")
    print("  by fold (gap80, flag80): " + "; ".join(
        f"{k}: {measure('gap80', ref[Rr['fold_of'] == k], y[Rr['fold_of'] == k], chance[Rr['fold_of'] == k]):+.3f}, "
        f"{measure('flag80', ref[Rr['fold_of'] == k], y[Rr['fold_of'] == k], chance[Rr['fold_of'] == k]):.3f}" for k in np.unique(Rr['fold_of'][te])))
    g80 = np.percentile([measure("gap80", ref[te][b], y[te][b], chance[te][b]) for b in boots], [2.5, 97.5])
    print(f"  REFERENCE GATE (pooled gap80 wholly above zero): {'**YES**' if g80[0] > 0 else 'NO'}")
    # ------------------------------------------------------------ cells
    C = R.cells(P, y, chance, Rr, SETS_SCORED)
    print()
    print("PAIRED, every set/model minus the reference logistic, pooled (point [95% day-clustered]; share of folds on the good side). "
          "flag80: - better; top20, gap80: + better. * finding, r regime-dependent, ! harms")
    print(f"  {'set':<11}{'model':<5}" + "".join(f"{w:>40}" for w in R.MEASURES))
    nhit = nbad = 0
    for sn in SETS_SCORED:
        for m in ("L1", "d1", "d2", "d3", "d4", "rep"):
            cs = []
            for w in R.MEASURES:
                c = C[(sn, m, w)]
                v = R.verdict(w, c)
                nhit += int(R.good_side(w, c[1], c[2])); nbad += int(R.bad_side(w, c[1], c[2]))
                cs.append(f"{fmt(c)} {c[3]:.2f}{'*' if v == 'FINDING' else 'r' if v.startswith('REG') else '!' if v == 'HARMS' else ' '}")
            print(f"  {sn:<11}{m:<5}" + "".join(f"{x:>40}" for x in cs))
    nfind = sum(1 for (sn, m, w), c in C.items() if R.verdict(w, c) == "FINDING")
    print(f"  CELLS {len(C)}: pooled good-side {nhit}, bad-side {nbad} (expected by chance {0.025 * len(C):.1f} each side); FINDINGS (also >= 2/3 of folds): {nfind}")
    print()
    print("  KEPT groups per fold: " + "; ".join(f"{k}: {','.join(g) if g else 'none'}" for k, g in Rr["kept"]))
    print("  rep model per fold per set: " + "; ".join(f"{k}: " + " ".join(f"{s}={m}" for s, m in rp.items()) for k, rp in Rr["reps"]))
    print("  ALL rep gain (flag80, ALL rep minus reference) by fold: " + ", ".join(
        f"{k}: {measure('flag80', Rr['sc']['ALL']['rep'][Rr['fold_of'] == k], y[Rr['fold_of'] == k], chance[Rr['fold_of'] == k]) - measure('flag80', ref[Rr['fold_of'] == k], y[Rr['fold_of'] == k], chance[Rr['fold_of'] == k]):+.3f}"
        for k in np.unique(Rr['fold_of'][te])))
    # ------------------------------------------------------------ same-learner
    print()
    print("SAME-LEARNER DIAGNOSTICS, pooled flag80: set's model minus the reference set's SAME model (diagnostic, not cells)")
    for sn in SETS_SCORED:
        res = []
        for m in ("L1", "d1", "d2", "d3", "d4"):
            a, b_ = Rr["sc"][sn][m][te], Rr["sc"]["reference"][m][te]
            pt = measure("flag80", a, y[te], chance[te]) - measure("flag80", b_, y[te], chance[te])
            dr = [measure("flag80", a[b], y[te][b], chance[te][b]) - measure("flag80", b_[b], y[te][b], chance[te][b]) for b in boots]
            lo, hi = np.percentile(dr, [2.5, 97.5])
            res.append(f"{m} {pt:+.4f} [{lo:+.4f},{hi:+.4f}]{'*' if hi < 0 else ''}")
        print(f"  {sn:<11}" + "   ".join(res))
    # ------------------------------------------------------------ direction check
    print()
    print("DIRECTION CHECK -- pooled test correlation of each feature with the reference's residual (reach - predicted); share of folds with the pooled sign")
    resid = y - ref
    wrong = []
    print(f"  {'feature':<26}{'expect':>7}   corr [95%]                share   verdict")
    for j, nm in enumerate(names):
        x = FX[te, j]; r_ = resid[te]
        def cor(ix):
            mk = np.isfinite(x[ix])
            return float(np.corrcoef(x[ix][mk], r_[ix][mk])[0, 1]) if mk.sum() > 50 else np.nan
        pt = cor(np.arange(len(te)))
        lo, hi = np.nanpercentile([cor(b) for b in boots], [2.5, 97.5])
        sg = []
        for k in np.unique(Rr["fold_of"][te]):
            ix = np.flatnonzero(Rr["fold_of"][te] == k)
            c_ = cor(ix)
            if np.isfinite(c_):
                sg.append(np.sign(c_) == np.sign(pt))
        share = float(np.mean(sg)) if sg else np.nan
        e = expect[j]
        v = ("ok" if (lo > 0 if e == "+" else hi < 0) else "WRONG" if (hi < 0 if e == "+" else lo > 0) else "-") if e else ("+" if lo > 0 else "neg" if hi < 0 else "-")
        if v == "WRONG":
            wrong.append(nm)
        print(f"  {nm:<26}{e or '2-sided':>7}   {pt:+.4f} [{lo:+.4f},{hi:+.4f}]   {share:.2f}   {v}")
    print(f"  WRONG DIRECTION (pooled interval wholly on the wrong side): {', '.join(wrong) if wrong else 'none'}")
    # ------------------------------------------------------------ strong-event row
    print()
    print("STRONG-EVENT ROW -- (|z| >= 3) OR (forced share P1 > 0); the rolling pipeline on the restricted rows")
    Zs = np.load(ef.OUT_SERIES)
    forced_p1 = Zs["ev"][P.rows][:, [str(x) for x in Zs["series"]].index("forced"), [str(x) for x in Zs["windows"]].index("P1")].astype(float)
    m = (np.abs(P.e) >= 3) | (np.nan_to_num(forced_p1) > 0)
    Ps = Sub(P, m)
    Ds = dict(D); Ds["FX"] = FX[m]; Ds["ref_X"] = ref_X[m]
    Rs = R.run_pipeline(Ps, Ds, y[m], chance[m], verbose=False)
    Cs = R.cells(Ps, y[m], chance[m], Rs, ("CONC_EXACT", "SKILL", "BACKSTOP", "ALL"))
    print(f"  restricted n {int(m.sum()):,} of {P.n:,}; reach {y[m].mean():.4f}; test rows {int((Rs['fold_of'] >= 0).sum()):,}")
    nb4 = 0
    for sn in ("CONC_EXACT", "SKILL", "BACKSTOP", "ALL"):
        cs = []
        for w in R.MEASURES:
            c = Cs[(sn, "rep", w)]
            v = R.verdict(w, c)
            nb4 += int(v == "FINDING")
            cs.append(f"{fmt(c)} {c[3]:.2f}{'*' if v == 'FINDING' else 'r' if v.startswith('REG') else '!' if v == 'HARMS' else ' '}")
        print(f"  {sn:<11}rep " + "".join(f"{x:>40}" for x in cs))
    print(f"  strong-event FINDINGS: {nb4} of 12 cells (expected pooled-interval hits by chance 0.3 per sign)")
    # ------------------------------------------------------------ single cut, one row
    print()
    print("SINGLE CUT (like-for-like row against build 4; CUT 2026-05-25, one fold, embargo applied; not counted as cells): rep minus reference, pooled HO")
    last = P.day.max() + np.timedelta64(1, "D")
    R1 = R.run_pipeline(P, D, y, chance, folds=[(np.datetime64(harness.CUT), last)])
    C1 = R.cells(P, y, chance, R1, SETS_SCORED)
    for sn in SETS_SCORED:
        print(f"  {sn:<11}rep " + "   ".join(f"{w} {fmt(C1[(sn, 'rep', w)])}" for w in R.MEASURES))
    # ------------------------------------------------------------ Q1
    print()
    print("Q1 -- do exact wallet features differ BEFORE triggers? events minus matched controls, test blocks only; pooled day-clustered interval; share of folds with the pooled sign")
    PR = pd.read_parquet(ce.PAIRS)
    Zf = np.load(FEAT_NPZ)
    fv, wnames = [str(x) for x in Zf["feats"]], [str(x) for x in Zf["windows"]]
    EV = pd.read_parquet(ce.EVENTS)
    eday = pd.to_datetime(EV["T"]).dt.floor("D").dt.tz_localize(None).to_numpy() if pd.to_datetime(EV["T"]).dt.tz is not None else pd.to_datetime(EV["T"]).dt.floor("D").to_numpy()
    first_test = folds[0][0]
    fold_ev = np.full(len(EV), -1, int)
    for k, (s, e_) in enumerate(folds):
        fold_ev[(eday >= s) & (eday < e_)] = k
    rng = np.random.default_rng(20261016)
    ev_of_link = PR["event"].to_numpy(int)
    nq = nqf = 0
    print(f"  {'series':<7}{'win':<5}{'set':<4}{'pooled mean diff [95%]':>34}{'folds same sign':>18}   verdict")
    for sname in Q1_SERIES:
        fi = fv.index(sname)
        for w in wnames:
            wi = wnames.index(w)
            for kset in (1, 2):
                mk = (PR["set"].to_numpy() == kset)
                x_pr = np.full(len(PR), np.nan); x_pr[mk] = Zf["pr"][mk, wi, fi]
                diff = Zf["ev"][:, wi, fi].astype(float)
                fin = np.isfinite(x_pr)
                s_ = np.bincount(ev_of_link[fin], weights=x_pr[fin], minlength=len(EV)); n_ = np.bincount(ev_of_link[fin], minlength=len(EV))
                with np.errstate(invalid="ignore", divide="ignore"):
                    diff = diff - np.where(n_ > 0, s_ / n_, np.nan)
                ok = np.isfinite(diff) & (fold_ev >= 0)
                d, v = eday[ok], diff[ok]
                ud, inv = np.unique(d, return_inverse=True)
                sm = np.bincount(inv, weights=v); ct = np.bincount(inv).astype(float)
                pick = rng.integers(0, len(ud), size=(300, len(ud)))
                bm = sm[pick].sum(1) / ct[pick].sum(1)
                lo, hi = np.percentile(bm, [2.5, 97.5]); pt = float(v.mean())
                fs = [np.sign(diff[ok & (fold_ev == k)].mean()) == np.sign(pt) for k in range(len(folds)) if (ok & (fold_ev == k)).sum() > 30]
                share = float(np.mean(fs)) if fs else np.nan
                excl = lo > 0 or hi < 0
                tag = "FINDING" if excl and share >= 2 / 3 else "regime-dependent" if excl else ""
                nq += 1; nqf += int(tag == "FINDING")
                print(f"  {sname:<7}{w:<5}{kset:<4}{f'{pt:+.4f} [{lo:+.4f},{hi:+.4f}]':>34}{share:>18.2f}   {tag}")
    print(f"  Q1 cells {nq}: FINDINGS {nqf} (expected pooled hits by chance {0.05 * nq:.1f})")
    # ------------------------------------------------------------ permutation null
    print()
    print(f"PERMUTATION NULL -- the whole rolling pipeline on targets moved between whole days, {R.N_NULL} seeds (pooled rep minus reference)")
    _G["P"], _G["D"] = P, D
    with Pool(min(R.N_NULL, int(os.environ.get("NPROC", 8)))) as pool:
        nulls = pool.map(_null_job, range(R.N_NULL))
    for sn in SETS_SCORED:
        for w in R.MEASURES:
            nu = np.array([n_[(sn, "rep", w)][0] for n_ in nulls])
            obs = C[(sn, "rep", w)][0]
            below = obs <= nu.min() if w == "flag80" else obs >= nu.max()
            print(f"  {sn:<11}{w:<7} observed {obs:+.4f}; null min {nu.min():+.4f} median {np.median(nu):+.4f} max {nu.max():+.4f}   outside the null on the good side: {'YES' if below else 'no'}")
    # ------------------------------------------------------------ reading rules
    print()
    print("READING RULES (rep model, flag80; HELP = pooled interval wholly below zero AND >= 2/3 of folds)")
    for sn in SETS_SCORED:
        c = C[(sn, "rep", "flag80")]
        v = R.verdict("flag80", c)
        print(f"  {sn:<11}{'HELP' if v == 'FINDING' else v if v else 'no help'}   (pooled {fmt(c)}; folds on the good side {c[3]:.2f} of {c[4]})")
    print("  Nothing written to the registry or the live system. No stop, no profit, no delayed features.")
    print(f"  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
