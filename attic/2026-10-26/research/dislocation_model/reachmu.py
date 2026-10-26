"""REACH-MU Steps 1-3: which spreads come back to mu within 10 hours?

    # stage 1: per-episode path facts (reach, chance probability, liquidation)
    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/reachmu.py --stage paths > .../logs/reachmu_paths.log 2>&1
    # stage 2: descriptives, models, scoring, importance, SHAP, combinations
    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/reachmu.py --stage models > .../logs/reachmu.log 2>&1

The matched 53,757 episodes, harness.Split unchanged: train < 2026-05-01, val to
2026-07-17 (ALL tuning and every choice of "best"), held out >= 2026-07-18,
HO1 to 2026-08-25, HO2 from 2026-08-26. No stop. Nothing written to the
registry or the live system. pair_triggers_true is never read.

TARGET. reach = depth >= |z_at_entry|, exactly whyscreen's: depth = the largest
move toward mu over minutes 1..600 after the entry bar's close, on 1-minute
closes with mu, beta, alpha, sigma frozen at entry; asserted equal to the 10h
MFE target.

CHANCE PROBABILITY (reading tool only; never a feature, never a model input).
Per episode, its 1-minute increments of the folded move get random signs (the
whyscreen construction, bridging missing minutes), 50 seeds (1000..1049); the
share of seeds whose flipped path reaches mu. It uses future step sizes.

LIQUIDATION. Headroom at 20x = hedge_estimators.liquidation_distance(beta, 20)
/ sigma, in entry sigma. A reverter "hits liquidation before mu" if the
adverse move (away from mu, from the entry close) reaches the headroom at any
minute before the first minute the path reaches mu. Assumed (A): 1-minute
closes, no fees, no funding, margin exactly as liquidation_distance models it.

FEATURES (44). The six (vol_48, vol_48_1m, vratio, vol_slope, sandwich,
off_mark); the 20 why-it-moved columns via whyscreen.why_columns (agreed
transforms, train-median fill); the 10 Step 0 columns (reachfeat.npz); raw entry
facts |z_at_entry|, beta, r2, sigma; hour of day and day of week at the
DECISION time (entry_time + 30 minutes, the entry bar's close) as sine and
cosine. Gap filled, fixed, not tuned: log() on the positive scale columns
vol_48, vol_48_1m, sigma, breadth_ratio, and log1p() on the counts
triggers_past_rate and triggers_past_30d, because heavy tails hurt the linear
models (trees are unaffected by monotone transforms). Values that cannot be
transformed, and every other missing value, take the TRAIN median; counts per
column are reported.

MODELS (fitted on train; every choice on val by log loss):
  random       analytic: flag share = catch rate, hit rate = base rate
  vol-only     logistic, unpenalised, standardised: vol_48, vol_48_1m, sigma
  logistic L1  all 44, standardised on train, liblinear; C on val over
               {0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1, 3}
  LightGBM     binary, all 44, seed 0, deterministic, 6 threads.
               max_depth d in {1, 2, 3, 4, 6, 8} with num_leaves = 2^d; and
               "unlimited" max_depth = -1 with num_leaves tuned over
               {64, 128, 256, 512}. min_data_in_leaf over {20, 100, 400}.
               gbdt: learning rate over {0.03, 0.1}, rounds by early stopping
               on val log loss (patience 100, cap 3000).
               DART: learning rate 0.1, rounds over {100, 300, 600}, each a
               separate fit (DART rescales earlier trees, so a prefix of a
               longer run is not the shorter model).
               14 configurations (7 depths x 2 boostings), each with its own
               val-chosen settings. Fitted depth and leaf counts reported.
  "Best tree" = the configuration with the lowest val log loss. "Best model"
  (headline, liquidation) = whichever of logistic L1 and the best tree has the
  lower val log loss. Held-out never chooses.

SCORING, held out only, HO1 and HO2 separately, every model. Rank by score
within the period. For catch c in {50, 80, 90}%: flag share = the smallest
share of episodes whose top-ranked set holds c of the period's reverters; hit
rate = reverters flagged / flagged. Top-20% hit rate and its beyond-chance gap
(real reach rate - mean chance probability, in the top 20%). AUC, log loss,
calibration by decile of score. Paired day-clustered 95% intervals
(envelope.day_boot within the period, 300 resamples, ranks recomputed in each
resample) for: every model minus vol-only on flag share at 80% catch and on
top-20% hit rate; best tree minus logistic; best tree minus the depth-1 tree.

IMPORTANCE, best logistic and best tree, held out: grouped permutation, 20
shuffles, log-loss skill points lost (per-row increase / base-rate log loss),
day-clustered. Groups: 4-bar with 12-bar versions; 1-minute with 30-minute
(vol_48 with vol_48_1m, the why-it-moved twins); leg_a/leg_b breadth with
breadth_ratio; hour sin/cos; weekday sin/cos; every other column alone.
SHAP interaction values for the best tree only: a seeded sample of 5,000 held
out (2,500 HO1, 2,500 HO2). Free memory checked first. shap's TreeExplainer is
timed on 100 rows; if the extrapolated time exceeds 15 minutes, shapiq
TreeSHAP-IQ (k-SII, order 2) is used instead. The top 10 pairs by mean
|interaction| are checked directly on ALL held-out rows, HO1 and HO2: reach
rate in the 2x2 split at each feature's TRAIN median, plus the interaction
contrast (HH - HL - LH + LL) with a day-clustered interval, reported, not
gated. Pre-registered pairs, the same table: lone_share_12 x
vol_spike_mover_12, common_share_12 x lagger_spread_12, breadth_ratio x
vol_spike_mover_12. Gap filled: the brief names the features, not the
lookback; the 6h (12-bar) versions are used, the longer measure of the move.

READING RULES (fixed now; "clears zero" = the 95% interval excludes zero; point
estimates alone never count). Gap filled: "some model" means the two models
chosen on val, logistic L1 and the best tree. The other 13 tree configurations
are reported but do not vote; letting 15 candidates vote would make a chance
pass likely.
  SIGNAL: a candidate's flag share at 80% catch minus vol-only's has its
    interval wholly below zero in BOTH HO1 and HO2.
  COMBINATIONS MATTER: best tree minus logistic on the same measure, interval
    wholly below zero in both halves, AND the depth curve improves beyond depth
    1, read as: best tree minus the val-best depth-1 tree on the same measure,
    interval wholly below zero in both halves. If the best tree IS depth 1,
    combinations do not matter.
  STRONG: a candidate's flag share at 80% catch has its interval wholly below
    0.5, AND the beyond-chance gap of the episodes it flags at 80% catch has
    its interval wholly above zero, in both halves.
  REGIME-DEPENDENT: a candidate that clears SIGNAL in exactly one half. Not a
    signal.
A pass earns the stop test and a trade-level check later; it is not a result.
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
from envelope import (HO_BOUNDARY, build_targets_1m, day_boot, load_1m_series,
                      one_min_paths, scan_1m_coverage, select_1m_subset)

PATHS_OUT = os.path.join(paths.DATASETS, "reach_paths.npz")
CHANCE_SEEDS = range(1000, 1050)
LEVERAGE = 20.0
CATCH = (0.5, 0.8, 0.9)
TOP = 0.2
N_SHUF = 20
SEED = 20261013
THREADS = 6
C_GRID = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0)
DEPTHS = (1, 2, 3, 4, 6, 8, -1)
LEAVES_UNLIM = (64, 128, 256, 512)
MDL = (20, 100, 400)
LR_GBDT = (0.03, 0.1)
DART_ROUNDS = (100, 300, 600)
PRE_REG = (("lone_share_12", "vol_spike_mover_12"), ("common_share_12", "lagger_spread_12"),
           ("breadth_ratio", "vol_spike_mover_12"))


def population():
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    return Y, meta, np.flatnonzero(used)


# ======================================================================= paths
def stage_paths():
    from hedge_estimators import liquidation_distance
    t0 = time.time()
    Y, meta, rows = population()
    e = Y[rows, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    series = load_1m_series(sorted(set(meta.ticker_a.iloc[rows]) | set(meta.ticker_b.iloc[rows])), False)
    P, _ = one_min_paths(meta, rows, series)
    del series
    # HL-FLOW1: the population is the dislocations whose 1-minute window (minutes
    # 0..600 after the entry close) EXISTS (rule B span test) AND is finite for both
    # legs. A hole minute (rule iii) is NaN, so an episode whose window touches one
    # is dropped here and counted, not bridged.
    fin_all = np.isfinite(P).all(axis=1)
    print(f"  1-minute window exists (rule B): {len(rows):,} of {len(meta):,} dislocations; "
          f"finite on all 601 minutes: {int(fin_all.sum()):,}; lost to archive holes: "
          f"{int((~fin_all).sum()):,} ({100*(~fin_all).mean():.2f}% of the matched)")
    rows, P = rows[fin_all], P[fin_all]
    e = Y[rows, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    move = -(P - e[:, None]) * s[:, None]
    del P
    seg = move[:, 1:601]
    depth = np.nanmax(seg, 1)
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    dmax = float(np.max(np.abs(depth - T1M[("MFE", 20)])))
    print(f"  depth vs the 10h MFE target: max |diff| {dmax:.2e} (must be 0)")
    if dmax > 0:
        raise SystemExit("[REACH] depth does not equal the 10h MFE.")
    need = np.abs(e)
    reach = depth >= need
    hit_m = np.where(np.isfinite(seg), seg >= need[:, None], False)
    t_reach = np.where(reach, hit_m.argmax(1) + 1, -1)          # first minute at mu
    beta = meta.beta.to_numpy(float)[rows]
    sig = meta.sigma.to_numpy(float)[rows]
    head = liquidation_distance(beta, LEVERAGE) / sig
    adverse = np.where(np.isfinite(seg), -seg, -np.inf)
    cols = np.arange(1, 601)[None, :]
    before = cols < np.where(reach, t_reach, 601)[:, None]
    liq_before = (np.where(before, adverse, -np.inf).max(1) >= head)
    liq_any = adverse.max(1) >= head
    print(f"  reach mu within 10h: {reach.mean():.4f} ({int(reach.sum()):,} of {len(rows):,})")
    print(f"  liquidation headroom at 20x, entry sigma: median {np.median(head):.3f} "
          f"[p5 {np.percentile(head, 5):.3f}, p95 {np.percentile(head, 95):.3f}]")
    print(f"  reverters hitting liquidation before mu: {int((reach & liq_before).sum()):,} of "
          f"{int(reach.sum()):,};  any episode hitting it within 10h: {int(liq_any.sum()):,}")
    # chance probability: whyscreen's sign flip, 50 seeds
    fin = np.isfinite(move)
    last = pd.DataFrame(move).ffill(axis=1).to_numpy()
    prevv = np.concatenate([np.zeros((len(move), 1)), last[:, :-1]], axis=1)
    inc = np.where(fin, move - prevv, 0.0)
    inc[:, 0] = 0.0
    del last, prevv, move, seg, adverse, before, hit_m
    hits = np.zeros(len(rows))
    for sd_ in CHANCE_SEEDS:
        sg = np.random.default_rng(sd_).choice([-1.0, 1.0], size=inc.shape)
        pth = np.cumsum(sg * inc, axis=1)
        pth[~fin] = np.nan
        hits += np.nanmax(pth[:, 1:601], 1) >= need
        del sg, pth
    chance = hits / len(CHANCE_SEEDS)
    print(f"  chance probability (50 sign-flip seeds): mean {chance.mean():.4f}   [{time.time()-t0:.0f}s]")
    np.savez_compressed(PATHS_OUT, rows=rows, reach=reach, depth=depth, chance=chance,
                        head=head, liq_before=liq_before, liq_any=liq_any, t_reach=t_reach)
    print(f"  [WROTE] {os.path.relpath(PATHS_OUT, paths.RESEARCH)}")


# ===================================================================== helpers
def flag_share(score, y, c):
    o = np.argsort(-score, kind="stable")
    cum = np.cumsum(y[o])
    k = int(np.searchsorted(cum, c * cum[-1], side="left")) + 1
    return k / len(y), cum[k - 1] / k, o[:k]


def top_set(score, frac):
    k = int(round(frac * len(score)))
    return np.argsort(-score, kind="stable")[:k]


def logloss_rows(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p))


def tree_shape(bst):
    def dep(nd):
        if "split_index" not in nd:                     # a leaf
            return 0
        return 1 + max(dep(nd["left_child"]), dep(nd["right_child"]))
    info = bst.dump_model()["tree_info"]
    d = [dep(t["tree_structure"]) for t in info]
    lv = [t["num_leaves"] for t in info]
    return len(info), int(max(d)), float(np.mean(d)), int(max(lv)), float(np.mean(lv))


# ===================================================================== models
def assemble_features(meta, rows, e, tr):
    """The 44 REACH-MU features on `rows`: transformed, missing set to the TRAIN
    median. One definition, shared by reachmu and reachmu2. Returns (names, X,
    fills) with fills = (name, missing count, untransformable count); the
    why-it-moved counts are why_columns' fill.
    """
    from whyscreen import why_columns
    X5 = np.load(paths.ENVFEAT, allow_pickle=False)["X"].astype(np.float64)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], rows):
        raise SystemExit("[REACH] vol48_1m rows differ.")
    W = np.load(os.path.join(paths.DATASETS, "whyfeat.npz"), allow_pickle=False)
    R = np.load(os.path.join(paths.DATASETS, "reachfeat.npz"), allow_pickle=False)
    et = pd.to_datetime(meta.entry_time).to_numpy("datetime64[ns]")
    for nm_, A in (("whyfeat", W), ("reachfeat", R)):
        if not ((A["ticker_a"] == meta.ticker_a.to_numpy(str)).all() and (A["entry_time"] == et).all()):
            raise SystemExit(f"[REACH] {nm_}.npz is not aligned to disloc_meta.")
    wn = [str(x) for x in W["names"]]
    XN, _, _, _, _, wfill = why_columns(W["X"][rows], wn, tr)
    rn = [str(x) for x in R["names"]]
    dec = pd.to_datetime(meta.entry_time.to_numpy()[rows]) + pd.Timedelta(minutes=30)
    hr = (dec.hour + dec.minute / 60.0).to_numpy()
    dw = dec.dayofweek.to_numpy().astype(float)
    cols = {"vol_48": X5[rows, 0], "vol_48_1m": v48["vol_48_1m"], "vratio": X5[rows, 1],
            "vol_slope": X5[rows, 2], "sandwich": X5[rows, 3], "off_mark": X5[rows, 4]}
    for j, nm in enumerate(wn):
        cols[nm] = XN[:, j]
    for j, nm in enumerate(rn):
        cols[nm] = R["X"][rows, j].astype(float)
    cols["abs_z"] = np.abs(e)
    cols["beta"] = meta.beta.to_numpy(float)[rows]
    cols["r2"] = meta.r2.to_numpy(float)[rows]
    cols["sigma"] = meta.sigma.to_numpy(float)[rows]
    cols["hour_sin"], cols["hour_cos"] = np.sin(2 * np.pi * hr / 24), np.cos(2 * np.pi * hr / 24)
    cols["dow_sin"], cols["dow_cos"] = np.sin(2 * np.pi * dw / 7), np.cos(2 * np.pi * dw / 7)
    LOGS, LOG1P = ("vol_48", "vol_48_1m", "sigma", "breadth_ratio"), ("triggers_past_rate", "triggers_past_30d")
    names = list(cols)
    fills = []
    for nm in names:
        v = cols[nm].astype(float).copy()
        bad_tf = 0
        if nm in LOGS:
            bad_tf = int((np.isfinite(v) & (v <= 0)).sum())
            with np.errstate(divide="ignore", invalid="ignore"):
                v = np.where(v > 0, np.log(v), np.nan)
        elif nm in LOG1P:
            bad_tf = int((np.isfinite(v) & (v <= -1)).sum())
            with np.errstate(divide="ignore", invalid="ignore"):
                v = np.where(v > -1, np.log1p(v), np.nan)
        nmiss = int((~np.isfinite(v)).sum())
        if nmiss:
            v[~np.isfinite(v)] = float(np.nanmedian(v[tr]))
        cols[nm] = v
        fills.append((nm, nmiss, bad_tf))
    wf = {nm: n_ for nm, n_, _ in wfill}
    fills = [(nm, wf.get(nm, n_), b) for nm, n_, b in fills]
    return names, np.column_stack([cols[nm] for nm in names]), fills


def reach_group(nm):
    """The REACH-MU importance group of a feature (near-duplicates together)."""
    for a, b in (("_1m_4", "_4"), ("_1m_12", "_12")):
        if nm.endswith(a):
            nm = nm[: -len(a)] + b
    if nm in ("vol_48_1m",):
        return "vol_48"
    if nm in ("leg_a_breadth", "leg_b_breadth", "breadth_ratio"):
        return "breadth (a, b, ratio)"
    if nm.startswith("hour_"):
        return "hour"
    if nm.startswith("dow_"):
        return "weekday"
    for sfx in ("_4", "_12"):
        if nm.endswith(sfx):
            return nm[: -len(sfx)]
    return nm


def stage_models():
    import lightgbm as lgb
    from sklearn.linear_model import LogisticRegression
    t0 = time.time()
    Y, meta, rows = population()
    PZ = np.load(PATHS_OUT)
    if not np.array_equal(PZ["rows"], rows):
        raise SystemExit("[REACH] reach_paths.npz rows differ.")
    y = PZ["reach"].astype(int)
    chance = PZ["chance"]
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    sp = harness.Split(day, e)
    tr, va, te = sp.train, sp.val, sp.test
    h1 = te & (day < HO_BOUNDARY)
    h2 = te & (day >= HO_BOUNDARY)
    print("=" * 120)
    print("REACH-MU -- which spreads come back to mu within 10 hours")
    print("=" * 120)
    print(f"  {sp.describe()}")
    print(f"  HO1 {int(h1.sum()):,} (to 2026-08-25)   HO2 {int(h2.sum()):,} (from 2026-08-26)")

    # ---------------- features ----------------
    names, X, fills = assemble_features(meta, rows, e, tr)
    print(f"  features: {len(names)}")
    print("  missing set to the TRAIN median (why-it-moved counts are why_columns' fill):")
    print("    " + ";  ".join(f"{nm} {n_}" + (f" ({b} untransformable)" if b else "")
                              for nm, n_, b in fills if (n_ or b)))
    ix = {nm: j for j, nm in enumerate(names)}
    R = np.load(os.path.join(paths.DATASETS, "reachfeat.npz"), allow_pickle=False)
    rn = [str(x) for x in R["names"]]
    print()

    # ---------------- step 1 ----------------
    print("=" * 120)
    print("STEP 1 -- the chance bar (reading tool only) and how far the mover moved")
    print("=" * 120)
    blocks = (("train", tr), ("val", va), ("HO1", h1), ("HO2", h2))
    for lbl, m in blocks:
        print(f"  {lbl:<6} n {int(m.sum()):>6,}   real reach {y[m].mean():.4f}   mean chance "
              f"{chance[m].mean():.4f}   gap {y[m].mean() - chance[m].mean():+.4f}")
    raw_r = R["X"][rows]
    print("  mover distributions (raw, before fill): median [p5, p95]")
    for nm in ("mover_resid_z_4", "mover_resid_z_12", "mover_ret_4", "mover_ret_12"):
        v = raw_r[:, rn.index(nm)]
        print(f"    {nm:<18}" + "   ".join(
            f"{lbl} {np.nanmedian(v[m]):+.4f} [{np.nanpercentile(v[m], 5):+.4f}, {np.nanpercentile(v[m], 95):+.4f}]"
            for lbl, m in (("train", tr), ("HO1", h1), ("HO2", h2))))
    v = raw_r[:, rn.index("mover_resid_z_12")]
    fin = np.isfinite(v)
    cuts = np.quantile(v[tr & fin], np.linspace(0, 1, 11)[1:-1])
    g = np.where(fin, np.searchsorted(cuts, v, side="right"), -1)
    print("  by decile of mover_resid_z_12 (TRAIN cut points; finite rows): real reach / chance / gap  (n)")
    for lbl, m in (("train", tr), ("HO1", h1), ("HO2", h2)):
        cells = []
        for k in range(10):
            mk = m & (g == k)
            cells.append(f"d{k+1} {y[mk].mean():.3f}/{chance[mk].mean():.3f}/{y[mk].mean()-chance[mk].mean():+.3f} ({int(mk.sum())})")
        print(f"    {lbl:<6} " + "  ".join(cells))
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---------------- step 2 ----------------
    print("=" * 120)
    print("STEP 2 -- models (fitted on train; every choice on val by log loss)")
    print("=" * 120)
    mu_, sd_ = X[tr].mean(0), X[tr].std(0)
    sd_[sd_ == 0] = 1.0
    Z = (X - mu_) / sd_
    score = {}
    vol_cols = [ix["vol_48"], ix["vol_48_1m"], ix["sigma"]]
    lr_v = LogisticRegression(penalty=None, max_iter=5000).fit(Z[tr][:, vol_cols], y[tr])
    score["vol-only"] = lr_v.predict_proba(Z[:, vol_cols])[:, 1]
    print(f"  vol-only: val log loss {logloss_rows(y[va], score['vol-only'][va]).mean():.5f}")
    best_c, best_ll = None, np.inf
    for C in C_GRID:
        m_ = LogisticRegression(penalty="l1", C=C, solver="liblinear", max_iter=5000).fit(Z[tr], y[tr])
        ll_ = logloss_rows(y[va], m_.predict_proba(Z[va])[:, 1]).mean()
        print(f"    logistic L1 C={C:<6} val log loss {ll_:.5f}   nonzero {int((m_.coef_ != 0).sum())}")
        if ll_ < best_ll:
            best_c, best_ll, lr_l1 = C, ll_, m_
    score["logistic L1"] = lr_l1.predict_proba(Z)[:, 1]
    print(f"  logistic L1: C = {best_c} (val log loss {best_ll:.5f}); nonzero coefficients "
          f"{int((lr_l1.coef_ != 0).sum())} of {len(names)}: "
          + ", ".join(names[j] for j in np.flatnonzero(lr_l1.coef_[0] == 0)) + " dropped")
    print(f"  [{time.time()-t0:.0f}s]", flush=True)

    base_p = dict(objective="binary", metric="binary_logloss", seed=0, deterministic=True,
                  force_row_wise=True, num_threads=THREADS, verbosity=-1)
    trees = {}
    for d in DEPTHS:
        for boost in ("gbdt", "dart"):
            best = None
            leaves = LEAVES_UNLIM if d == -1 else (2 ** d,)
            for nl in leaves:
                for mdl in MDL:
                    grid = ([(lr, None) for lr in LR_GBDT] if boost == "gbdt"
                            else [(0.1, r) for r in DART_ROUNDS])
                    for lr, rounds in grid:
                        p = dict(base_p, boosting=boost, max_depth=d, num_leaves=nl,
                                 min_data_in_leaf=mdl, learning_rate=lr)
                        # fresh Datasets per fit: binning params never carry over
                        dtr = lgb.Dataset(X[tr], y[tr], feature_name=names)
                        dva = lgb.Dataset(X[va], y[va], reference=dtr)
                        if boost == "gbdt":
                            bst = lgb.train(p, dtr, 3000, valid_sets=[dva],
                                            callbacks=[lgb.early_stopping(100, verbose=False)])
                            it = bst.best_iteration
                        else:
                            p.update(drop_seed=0)
                            bst = lgb.train(p, dtr, rounds)
                            it = rounds
                        pv = bst.predict(X[va], num_iteration=it)
                        ll_ = logloss_rows(y[va], pv).mean()
                        if best is None or ll_ < best[0]:
                            best = (ll_, bst, it, dict(num_leaves=nl, min_data_in_leaf=mdl,
                                                       learning_rate=lr, rounds=it))
            ll_, bst, it, cfg = best
            lbl = f"{'unlim' if d == -1 else 'depth ' + str(d)} {boost}"
            nt, dmax, dmean, lmax, lmean = tree_shape(
                lgb.Booster(model_str=bst.model_to_string(num_iteration=it)))
            trees[lbl] = dict(d=d, boost=boost, val_ll=ll_, cfg=cfg,
                              shape=(nt, dmax, dmean, lmax, lmean), bst=bst, it=it)
            score[lbl] = bst.predict(X, num_iteration=it)
            print(f"  {lbl:<14} val log loss {ll_:.5f}  {cfg}  trees {nt}, fitted depth max {dmax} "
                  f"mean {dmean:.2f}, leaves max {lmax} mean {lmean:.1f}   [{time.time()-t0:.0f}s]",
                  flush=True)
    best_tree = min(trees, key=lambda k: trees[k]["val_ll"])
    d1 = min((k for k in trees if trees[k]["d"] == 1), key=lambda k: trees[k]["val_ll"])
    best_model = best_tree if trees[best_tree]["val_ll"] < best_ll else "logistic L1"
    print(f"  BEST TREE (val): {best_tree} (val log loss {trees[best_tree]['val_ll']:.5f});  "
          f"val-best depth-1 tree: {d1};  BEST MODEL (val): {best_model}")
    print()

    # ---------------- step 3 ----------------
    print("=" * 120)
    print("STEP 3 -- scoring, held out only, HO1 and HO2 separately")
    print("=" * 120)
    halves = {"HO1": np.flatnonzero(h1), "HO2": np.flatnonzero(h2)}
    hboot = {hn: day_boot(day[ix_]) for hn, ix_ in halves.items()}
    order = ["vol-only", "logistic L1"] + list(trees)
    res = {}
    for hn, ixh in halves.items():
        yh, ch = y[ixh], chance[ixh]
        base = yh.mean()
        print(f"  {hn}: n {len(ixh):,}, reverters {int(yh.sum()):,} ({base:.4f}), mean chance {ch.mean():.4f}")
        print(f"    {'model':<16}" + "".join(f"{f'catch {int(100*c)}%: flag / hit':>28}" for c in CATCH)
              + f"{'top20 hit':>11}{'top20 gap':>11}{'AUC':>8}{'log loss':>10}")
        print(f"    {'random':<16}" + "".join(f"{f'{c:.3f} / {base:.3f}':>28}" for c in CATCH)
              + f"{base:>11.3f}{base - ch.mean():>+11.3f}{0.5:>8.3f}{logloss_rows(yh, np.full(len(yh), y[tr].mean())).mean():>10.5f}")
        for mn in order:
            sc = score[mn][ixh]
            cat = [flag_share(sc, yh, c)[:2] for c in CATCH]
            tp = top_set(sc, TOP)
            r_ = dict(cat=cat, top_hit=yh[tp].mean(), top_gap=yh[tp].mean() - ch[tp].mean(),
                      auc=auc(yh, sc), ll=logloss_rows(yh, sc).mean())
            res[(hn, mn)] = r_
            print(f"    {mn:<16}" + "".join(f"{f'{a:.3f} / {b:.3f}':>28}" for a, b in cat)
                  + f"{r_['top_hit']:>11.3f}{r_['top_gap']:>+11.3f}{r_['auc']:>8.4f}{r_['ll']:>10.5f}")
        print()

    def boot_diff(hn, a, b, what):
        ixh = halves[hn]
        yh, ch = y[ixh], chance[ixh]
        sa, sb = score[a][ixh], score[b][ixh]

        def f(sc, yy, cc):
            if what == "flag80":
                return flag_share(sc, yy, 0.8)[0]
            tp = top_set(sc, TOP)
            return yy[tp].mean()
        pt = f(sa, yh, ch) - f(sb, yh, ch)
        dr = [f(sa[i_], yh[i_], ch[i_]) - f(sb[i_], yh[i_], ch[i_]) for i_ in hboot[hn]]
        lo, hi = np.percentile(dr, [2.5, 97.5])
        return pt, lo, hi

    def boot_level(hn, a):
        ixh = halves[hn]
        yh, ch, sa = y[ixh], chance[ixh], score[a][ixh]

        def f(sc, yy, cc):
            fs, _, fl = flag_share(sc, yy, 0.8)
            return fs, yy[fl].mean() - cc[fl].mean()
        pt = f(sa, yh, ch)
        dr = np.array([f(sa[i_], yh[i_], ch[i_]) for i_ in hboot[hn]])
        return pt, np.percentile(dr, [2.5, 97.5], axis=0)

    print("  PAIRED, day-clustered 95% (A minus B). flag80 = flag share needed for an 80% catch "
          "(- = A needs fewer); top20 = top-20% hit rate (+ = A better)")
    diffs = {}
    comps = [(mn, "vol-only") for mn in order if mn != "vol-only"] + [(best_tree, "logistic L1"), (best_tree, d1)]
    for a, b in comps:
        if a == b:
            continue
        cells = []
        for hn in halves:
            for what in ("flag80", "top20"):
                pt, lo, hi = boot_diff(hn, a, b, what)
                diffs[(a, b, hn, what)] = (pt, lo, hi)
                tag = ("*" if (hi < 0 if what == "flag80" else lo > 0) else
                       "!" if (lo > 0 if what == "flag80" else hi < 0) else " ")
                cells.append(f"{hn} {what} {pt:+.4f} [{lo:+.4f},{hi:+.4f}]{tag}")
        votes = a in ("logistic L1", best_tree) or b != "vol-only"
        print(f"    {a + ' - ' + b:<34}" + "  ".join(cells)
              + ("" if votes else "   (reported, does not vote)"), flush=True)
    print("    (* = A significantly better, ! = A significantly worse)")
    print()
    print("  DEPTH CURVE -- flag share for an 80% catch and top-20% hit rate, by depth "
          "(intervals: the model's own level, day-clustered)")
    for boost in ("gbdt", "dart"):
        for hn in halves:
            cells = []
            for d in DEPTHS:
                lbl = f"{'unlim' if d == -1 else 'depth ' + str(d)} {boost}"
                r_ = res[(hn, lbl)]
                cells.append(f"{'unl' if d == -1 else 'd' + str(d)} {r_['cat'][1][0]:.3f}/{r_['top_hit']:.3f}")
            print(f"    {boost:<5}{hn:<5}" + "   ".join(cells))
    print()

    # ---------------- reading rules ----------------
    cands = ["logistic L1", best_tree]
    lev = {(mn, hn): boot_level(hn, mn) for mn in cands for hn in halves}
    print("  CANDIDATE LEVELS at 80% catch: flag share and beyond-chance gap of the flagged set, "
          "with day-clustered 95%")
    for (mn, hn), (pt, ci_) in lev.items():
        print(f"    {mn:<16}{hn}  flag share {pt[0]:.4f} [{ci_[0][0]:.4f}, {ci_[1][0]:.4f}]   "
              f"beyond-chance gap {pt[1]:+.4f} [{ci_[0][1]:+.4f}, {ci_[1][1]:+.4f}]")
    sig_h = {mn: [hn for hn in halves if diffs[(mn, "vol-only", hn, "flag80")][2] < 0] for mn in cands}
    signal = any(len(v) == 2 for v in sig_h.values())
    regime = [mn for mn, v in sig_h.items() if len(v) == 1]
    comb = (best_tree != d1 and trees[best_tree]["d"] != 1
            and all(diffs[(best_tree, "logistic L1", hn, "flag80")][2] < 0 for hn in halves)
            and all(diffs[(best_tree, d1, hn, "flag80")][2] < 0 for hn in halves))
    strong = [mn for mn in cands if all(lev[(mn, hn)][1][1][0] < 0.5 and lev[(mn, hn)][1][0][1] > 0
                                        for hn in halves)]
    print()
    print("  READING RULES")
    for mn in cands:
        print(f"    {mn:<16} flag80 significantly below vol-only in: {', '.join(sig_h[mn]) or 'neither half'}")
    print(f"    SIGNAL: {'YES' if signal else 'NO'}"
          + (f"   REGIME-DEPENDENT (one half only): {', '.join(regime)}" if regime else ""))
    print(f"    COMBINATIONS MATTER: {'YES' if comb else 'NO'}")
    print(f"    STRONG (flag80 wholly < 0.5 and flagged beyond-chance gap wholly > 0, both halves): "
          f"{', '.join(strong) if strong else 'none'}")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---------------- calibration ----------------
    print("  CALIBRATION by decile of score (mean predicted / observed), held out halves")
    for mn in ["vol-only", "logistic L1", best_tree]:
        for hn, ixh in halves.items():
            sc, yh = score[mn][ixh], y[ixh]
            g = np.clip(np.searchsorted(np.quantile(sc, np.linspace(0, 1, 11)[1:-1]), sc, side="right"), 0, 9)
            print(f"    {mn:<16}{hn}  " + "  ".join(f"{sc[g == k].mean():.3f}/{yh[g == k].mean():.3f}"
                                                   for k in range(10)))
    print()

    # ---------------- importance ----------------
    print("=" * 120)
    print(f"IMPORTANCE -- grouped permutation, held out, {N_SHUF} shuffles, log-loss skill points lost "
          "(+ = matters), day-clustered 95%")
    print("=" * 120)

    groups = {}
    for j, nm in enumerate(names):
        groups.setdefault(reach_group(nm), []).append(j)
    print("  groups: " + ";  ".join(f"{g_}({len(v)})" for g_, v in groups.items()))
    teix = np.flatnonzero(te)
    bte = day_boot(day[teix])
    lc_ = logloss_rows(y[teix], np.full(len(teix), y[tr].mean()))
    predict = {"logistic L1": lambda M_: lr_l1.predict_proba((M_ - mu_) / sd_)[:, 1],
               best_tree: lambda M_: trees[best_tree]["bst"].predict(M_, num_iteration=trees[best_tree]["it"])}
    imp = {}
    for mn, fn in predict.items():
        Xt = X[teix]
        base_l = logloss_rows(y[teix], fn(Xt))
        for gi, (g_, js) in enumerate(groups.items()):
            acc = np.zeros(len(teix))
            for s_ in range(N_SHUF):
                perm = np.random.default_rng([SEED, gi, s_]).permutation(len(teix))
                Xp = Xt.copy()
                Xp[:, js] = Xt[perm][:, js]
                acc += logloss_rows(y[teix], fn(Xp)) - base_l
            acc /= N_SHUF
            pt = 100 * acc.mean() / lc_.mean()
            dr = [100 * acc[i_].mean() / lc_[i_].mean() for i_ in bte]
            hp = {hn: 100 * acc[np.isin(teix, ixh)].mean() / lc_[np.isin(teix, ixh)].mean()
                  for hn, ixh in halves.items()}
            imp[(mn, g_)] = (pt, *np.percentile(dr, [2.5, 97.5]), hp["HO1"], hp["HO2"])
        print(f"    done {mn}   [{time.time()-t0:.0f}s]", flush=True)
    for mn in predict:
        print(f"  {mn}")
        for g_ in sorted(groups, key=lambda k: -imp[(mn, k)][0]):
            pt, lo, hi, a1, a2 = imp[(mn, g_)]
            print(f"    {g_:<24}{pt:+.4f} [{lo:+.4f}, {hi:+.4f}]{'  clears' if lo > 0 else '':<8}"
                  f"   HO1 {a1:+.4f}  HO2 {a2:+.4f}")
    print()

    # ---------------- SHAP interactions ----------------
    print("=" * 120)
    print(f"SHAP INTERACTIONS -- best tree only ({best_tree}), 5,000 held-out episodes (2,500 HO1 + 2,500 HO2)")
    print("=" * 120)
    import subprocess
    vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    pg = 16384 if "16384" in vm.splitlines()[0] else 4096
    free = sum(int(l.split(":")[1].strip().rstrip(".")) for l in vm.splitlines()
               if l.startswith(("Pages free", "Pages inactive", "Pages speculative"))) * pg / 1e9
    print(f"  free + inactive memory: {free:.2f} GB;  swap: "
          + subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout.strip())
    rs_ = np.random.default_rng(SEED)
    samp = np.concatenate([rs_.choice(halves["HO1"], 2500, replace=False),
                           rs_.choice(halves["HO2"], 2500, replace=False)])
    bst = trees[best_tree]["bst"]
    it = trees[best_tree]["it"]
    import shap
    bshap = lgb.Booster(model_str=bst.model_to_string(num_iteration=it))
    expl = shap.TreeExplainer(bshap)
    t_s = time.time()
    expl.shap_interaction_values(X[samp[:100]])
    est = (time.time() - t_s) * 50
    print(f"  shap TreeExplainer on 100 rows: {time.time()-t_s:.1f}s -> about {est/60:.1f} min for 5,000")
    if est <= 15 * 60:
        IV = expl.shap_interaction_values(X[samp])
        if isinstance(IV, list):
            IV = IV[-1]
        Mi = np.abs(IV).mean(0)
        used_tool = f"shap {shap.__version__} TreeExplainer"
    else:
        import shapiq
        ex = shapiq.TreeExplainer(model=bshap, index="k-SII", max_order=2)
        Mi = np.zeros((len(names), len(names)))
        for r_ in X[samp]:
            iv = ex.explain(r_)
            for key, val in iv.interaction_lookup.items():
                if len(key) == 2:
                    Mi[key[0], key[1]] += abs(iv.values[val])
                    Mi[key[1], key[0]] += abs(iv.values[val])
        Mi /= len(samp)
        used_tool = f"shapiq {shapiq.__version__} TreeSHAP-IQ k-SII"
    print(f"  tool: {used_tool}   [{time.time()-t0:.0f}s]")
    iu = np.triu_indices(len(names), 1)
    pairs_ = sorted(zip(Mi[iu], iu[0], iu[1]), reverse=True)[:10]
    med = {nm: float(np.median(X[tr, ix[nm]])) for nm in names}

    def two_by_two(fa, fb):
        out = []
        for hn, ixh in [("held out", teix)] + list(halves.items()):
            A_ = X[ixh, ix[fa]] > med[fa]
            B_ = X[ixh, ix[fb]] > med[fb]
            yh = y[ixh]
            cell = {(a_, b_): (yh[(A_ == a_) & (B_ == b_)].mean(), int(((A_ == a_) & (B_ == b_)).sum()))
                    for a_ in (False, True) for b_ in (False, True)}
            con = lambda yy, AA, BB: (yy[AA & BB].mean() - yy[AA & ~BB].mean()
                                       - yy[~AA & BB].mean() + yy[~AA & ~BB].mean())
            pt = con(yh, A_, B_)
            bt = day_boot(day[ixh])
            dr = [con(yh[i_], A_[i_], B_[i_]) for i_ in bt]
            lo, hi = np.percentile(dr, [2.5, 97.5])
            out.append((hn, cell, pt, lo, hi))
        return out

    def show(fa, fb, extra=""):
        print(f"  {fa} x {fb}{extra}")
        for hn, cell, pt, lo, hi in two_by_two(fa, fb):
            print(f"    {hn:<9} LL {cell[(False, False)][0]:.3f} ({cell[(False, False)][1]})  "
                  f"LH {cell[(False, True)][0]:.3f} ({cell[(False, True)][1]})  "
                  f"HL {cell[(True, False)][0]:.3f} ({cell[(True, False)][1]})  "
                  f"HH {cell[(True, True)][0]:.3f} ({cell[(True, True)][1]})   "
                  f"contrast {pt:+.4f} [{lo:+.4f}, {hi:+.4f}]{'  clears' if lo > 0 or hi < 0 else ''}")
    print("  TOP 10 PAIRS by mean |interaction|; 2x2 at TRAIN medians (first feature L/H, second L/H), "
          "reach rate (n)")
    for k_, (v_, a, b_) in enumerate(pairs_):
        show(names[a], names[b_], f"   (rank {k_+1}, mean |interaction| {v_:.5f})")
    print()
    print("  PRE-REGISTERED PAIRS")
    for fa, fb in PRE_REG:
        show(fa, fb)
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---------------- liquidation ----------------
    print("=" * 120)
    print(f"LIQUIDATION at 20x -- reverters the best model ({best_model}) flags at an 80% catch")
    print("=" * 120)
    lb = PZ["liq_before"]
    for hn, ixh in halves.items():
        _, _, fl = flag_share(score[best_model][ixh], y[ixh], 0.8)
        fr = ixh[fl][y[ixh[fl]] == 1]
        allr = ixh[y[ixh] == 1]
        print(f"  {hn}: flagged reverters {len(fr):,}; hit liquidation before mu {int(lb[fr].sum()):,} "
              f"({lb[fr].mean():.4f});  all reverters in {hn}: {int(lb[allr].sum()):,} of {len(allr):,} "
              f"({lb[allr].mean():.4f})")
    print()
    print("  Nothing written to the registry or the live system. No stop. pair_triggers_true never read.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 120)


if __name__ == "__main__":
    st = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "models"
    {"paths": stage_paths, "models": stage_models}[st]()
