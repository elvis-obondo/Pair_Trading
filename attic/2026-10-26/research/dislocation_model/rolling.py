"""The rolling (expanding-window walk-forward) version of hl3_tests.run, fixed by docs/prompts/HL_BUILD6_FULL_POPULATION.md
("Rolling (walk-forward) test"). Used by HL-WALLET1 (build 5) now, by builds 4b and 6 later.

FOLDS. Expanding window over the event days. The first test block starts 180 calendar days after the first event day; test blocks are
30 calendar days; the last block is whatever is left (shorter, kept). Fold k fits on every event before its block, tests on its block.
EMBARGO. Events within 1 day before a test block, and within 1 day before the validation block, are dropped from fitting (a 10-hour
outcome would otherwise run across the boundary).
VALIDATION. Inside each fold, the last 20% of that fold's fit days (after the embargo). Every setting (C, min_data_in_leaf, rounds) is chosen on that
fold's validation by log loss, nothing is carried back from a later fold, no fold sees its own test block. Normalisers (train-median fills and
standardisation) are fitted on that fold's train rows only. The REAL models are never shuffled in time; shuffling appears only in the null.

SETS and MODELS: as hl3_tests (reference; each group; ALL; KEPT = reference + the groups surviving the pruning rule on that fold's validation;
logistic L1, LightGBM depth 1-4). The "rep" model of a set = its lowest-validation-log-loss model IN THAT FOLD, so a set's pooled rep scores mix
the folds' own choices. The reference logistic (unpenalised, the 4 reference columns) is refitted per fold on that fold's train rows.

SCORING. Per fold and pooled over all test blocks (the folds' out-of-sample predictions concatenated and ranked together): flag share at 80%
catch (lower better), top-20% hit rate, beyond-chance gap at 80% catch (higher better). Paired differences against the reference logistic on
the pooled predictions with day-clustered 95% intervals (300 resamples of test days, ranks recomputed in each resample). Per fold: the same
point differences, and the share of folds on the good side.
READING RULE (fixed): a CELL is a FINDING when its pooled interval excludes zero on the good side AND the difference is on the good side in at
least two thirds of the folds. A pooled-clearing cell with fewer than two thirds of folds is REGIME-DEPENDENT: reported, not a pass.
Folds are not cells; the pooled cells are: (sets) x (5 models + rep) x 3 measures.
PERMUTATION NULL: the whole rolling pipeline rerun with the targets (y and chance together) moved between WHOLE DAYS (each day takes its
events' targets from another day, matched cyclically by the event's index within the day), 20 seeds; the pooled rep-minus-reference differences are
compared with the observed. [gap-fill: with unequal day sizes "shuffled by whole day" is implemented as this day-to-day reassignment.]
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import reachmu2
import hl3_tests as h3
from envelope import day_boot
from hl3_common import measure
from reachmu import logloss_rows

FIRST_TEST_DAYS, BLOCK_DAYS, VAL_FRAC = 180, 30, 0.2
MEASURES = h3.MEASURES
N_NULL = 20
FOLD_MIN_TEST = 200


def make_folds(day):
    """[(test_start, test_end)] over the event days."""
    days = np.unique(day)
    s = days[0] + np.timedelta64(FIRST_TEST_DAYS, "D")
    out = []
    while s <= days[-1]:
        e = s + np.timedelta64(BLOCK_DAYS, "D")
        out.append((s, e))
        s = e
    return out


def fold_masks(day, s, e):
    """(train, val, test) boolean masks for one fold, embargo applied."""
    one = np.timedelta64(1, "D")
    fit_days = np.unique(day[day < s - one])
    nval = max(1, int(round(VAL_FRAC * len(fit_days))))
    vstart = fit_days[-nval]
    tr = day < vstart - one
    va = (day >= vstart) & (day < s - one)
    te = (day >= s) & (day < e)
    return tr, va, te


def fit_reference(ref_X, y, tr):
    from sklearn.linear_model import LogisticRegression
    mu, sd = ref_X[tr].mean(0), ref_X[tr].std(0)
    lr = LogisticRegression(penalty=None, max_iter=5000).fit((ref_X[tr] - mu) / sd, y[tr])
    return lr.predict_proba((ref_X - mu) / sd)[:, 1]


def shuffle_days(day, y, chance, rng):
    """Targets (y, chance) moved between whole days: day d takes day pi(d)'s events, matched cyclically by index within the day."""
    ud, inv = np.unique(day, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    starts = np.r_[0, np.cumsum(np.bincount(inv))]
    perm = rng.permutation(len(ud))
    ynew, cnew = y.copy(), chance.copy()
    for k in range(len(ud)):
        mine = order[starts[k]:starts[k + 1]]
        src = order[starts[perm[k]]:starts[perm[k] + 1]]
        take = src[np.arange(len(mine)) % len(src)]
        ynew[mine], cnew[mine] = y[take], chance[take]
    return ynew, cnew


def run_pipeline(P, D, y, chance, verbose=False, folds=None):
    """All folds. Returns dict: scores {set: {model: pooled array (NaN outside test)}}, ref (pooled), fold_of (-1 outside test), kept per fold,
    rep per (fold, set), val log losses, folds list."""
    t0 = time.time()
    day, n = P.day, P.n
    FX, names, GROUPS, cols_of = D["FX"], D["names"], tuple(D["groups"]), D["cols_of"]
    ref_raw, rnames = D["ref_X"], D["rnames"]
    ref_fill = []
    folds = make_folds(day) if folds is None else folds
    sc = {}
    ref = np.full(n, np.nan)
    fold_of = np.full(n, -1, int)
    kept_per, rep_per, vll_per = [], [], []
    for k, (s, e) in enumerate(folds):
        tr, va, te = fold_masks(day, s, e)
        if te.sum() < FOLD_MIN_TEST:
            continue
        # reference columns: NaNs (non-positive vol or sigma) are filled with THIS fold's train median, nothing else
        ref_X = ref_raw.copy()
        nfill = []
        for j in range(ref_X.shape[1]):
            bad_ = ~np.isfinite(ref_X[:, j])
            nfill.append(int(bad_.sum()))
            if bad_.any():
                ref_X[bad_, j] = np.nanmedian(ref_raw[tr, j])
        ref_fill.append((k, nfill))
        ref_p_all = fit_reference(ref_X, y, tr)
        ref[te] = ref_p_all[te]
        fold_of[te] = k
        blocks = {g: h3.prep_block(FX[:, cols_of[g]], tr)[0] for g in GROUPS}
        sets = {"reference": (ref_X, rnames)}
        for g in GROUPS:
            sets[g] = (np.column_stack([ref_X, blocks[g]]), rnames + [names[j] for j in cols_of[g]] + [f"{g}_nan"])
        nm_of = lambda gs: sum(([names[j] for j in cols_of[g]] + [f"{g}_nan"] for g in gs), [])
        sets["ALL"] = (np.column_stack([ref_X] + [blocks[g] for g in GROUPS]), rnames + nm_of(GROUPS))
        # pruning on this fold's validation (ALL set, L1 and depth-2 tree)
        Xall, nall = sets["ALL"]
        mu_, sd_ = Xall[tr].mean(0), Xall[tr].std(0); sd_[sd_ == 0] = 1.0
        Zall = (Xall - mu_) / sd_
        _, l1, _ = reachmu2.fit_l1(Zall, y, tr, va)
        _, bt2, it2, _ = reachmu2.fit_tree(Xall, y, tr, va, 2, nall)
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
        kept = [g for g in GROUPS if impL[g]["val"][1] > 0 or impT[g]["val"][1] > 0]
        sets["KEPT"] = (np.column_stack([ref_X] + [blocks[g] for g in kept]) if kept else ref_X, rnames + nm_of(kept))
        kept_per.append((k, kept))
        reps, vl = {}, {}
        for sn, (Xs, ns) in sets.items():
            score, vll, _, _, rep = h3.fit_set(Xs, ns, y, tr, va, None)
            reps[sn], vl[sn] = rep, vll
            d_ = sc.setdefault(sn, {})
            for m, v in score.items():
                d_.setdefault(m, np.full(n, np.nan))[te] = v[te]
            d_.setdefault("rep", np.full(n, np.nan))[te] = score[rep][te]
        rep_per.append((k, reps)); vll_per.append((k, vl))
        if verbose:
            print(f"  fold {k:>2} test {pd.Timestamp(s).date()}..{pd.Timestamp(e).date()}  train {int(tr.sum()):,} val {int(va.sum()):,} test {int(te.sum()):,}; "
                  f"kept {kept if kept else 'none'}; reps " + ", ".join(f"{a} {b}" for a, b in reps.items()) + f"  [{time.time() - t0:.0f}s]", flush=True)
    return dict(ref_fill=ref_fill, sc=sc, ref=ref, fold_of=fold_of, kept=kept_per, reps=rep_per, vll=vll_per, folds=folds)


def cells(P, y, chance, R, sets_scored):
    """Pooled paired cells and per-fold good-sign shares. Returns {(set, model, measure): (pt, lo, hi, share_good, nfolds)}."""
    fo = R["fold_of"]
    te = np.flatnonzero(fo >= 0)
    day = P.day[te]
    boots = day_boot(day)
    out = {}
    folds_ix = [np.flatnonzero(fo == k) for k in np.unique(fo[fo >= 0])]
    ref = R["ref"]
    for sn in sets_scored:
        for m, arr in R["sc"][sn].items():
            for w in MEASURES:
                a, b_, yy, cc = arr[te], ref[te], y[te], chance[te]
                pt = measure(w, a, yy, cc) - measure(w, b_, yy, cc)
                dr = [measure(w, a[b], yy[b], cc[b]) - measure(w, b_[b], yy[b], cc[b]) for b in boots]
                lo, hi = np.percentile(dr, [2.5, 97.5])
                good = 0
                for ix in folds_ix:
                    d_ = measure(w, arr[ix], y[ix], chance[ix]) - measure(w, ref[ix], y[ix], chance[ix])
                    good += int(d_ < 0 if w == "flag80" else d_ > 0)
                out[(sn, m, w)] = (pt, lo, hi, good / len(folds_ix), len(folds_ix))
    return out


def good_side(w, lo, hi):
    return hi < 0 if w == "flag80" else lo > 0


def bad_side(w, lo, hi):
    return lo > 0 if w == "flag80" else hi < 0


def verdict(w, c):
    pt, lo, hi, sh, nf = c
    if good_side(w, lo, hi):
        return "FINDING" if sh >= 2 / 3 else "REGIME-DEPENDENT"
    if bad_side(w, lo, hi):
        return "HARMS"
    return ""
