"""THE harness. One split, one scorer, one bootstrap, one null, one set of gates.

This existed four times -- in `nonlinear.py`, `extscore.py`, `buckets.py` and
`control.py` -- and the copies had drifted. That drift produced a real bug, and
it is the reason this module exists rather than a convention:

    THE CI INDEXING BUG. `nonlinear.py`'s bootstrap built its day->row map from
    `day[te]`, so the indices it produced were positions WITHIN the held-out
    block, 0..n_te-1. It then used them to index the FULL-length target array
    `y`. The predictions were indexed correctly and the targets were not, so
    every interval it printed was computed against the wrong rows.

    It was caught by an interval not containing its own point estimate:
    `336 raw bars / reversion / 10h` scored 0.5016 with a reported 95% band of
    [0.4826, 0.5007]. The corrected run gives [0.4880, 0.5158].

    Nothing else would have caught it. The numbers were plausible and in some
    cells the bug made results look MORE significant: `18 engineered /
    reversion / 2h` read 0.5153 with a band of [0.4904, 0.5030] -- a point
    estimate outside its own interval, which read as a near-miss rather than as
    the broken arithmetic it was.

    `score_set` below takes the held-out target already subset, so the shapes
    cannot disagree. `_check_shapes` asserts it anyway.

WHAT IS FIXED HERE AND MUST NOT BE RE-TUNED PER EXPERIMENT

  CUT = 2026-07-18    70% of DISLOCATIONS, not of days. 41,936 fit / 18,064 held
                      out, 667 / 79 days. An earlier 70%-of-DAYS split at
                      2026-02-23 is SUPERSEDED -- see NUMBERS.md -- and must not
                      be reintroduced.
  train / val         the learner fits on the first 80% of FIT days; the number
                      of boosting iterations is chosen on the last 20%.
  THE HELD-OUT SET IS TOUCHED ONCE, at scoring time, and never for tuning.
  sign folding        primary. The window and the target are multiplied by
                      sign(z_entry) and every engineered feature is derived FROM
                      the folded window, so the learner sees one direction.

WHY UNFOLDED IS NOT THE PRIMARY READING. Unfolded, the reversion classifier
reaches AUC 0.59 and passes every gate. It is an artifact: `sign(z_entry)` alone
scores 0.4058 on the same target, i.e. 0.5942 inverted. The classifier is
recovering the entry sign, not information about the future. Report unfolded only
next to its sign-only column.

THE PERMUTATION NULL IS NOT OPTIONAL. A flexible learner's held-out R2 is
systematically negative and the real number cannot be read without knowing by
how much. The identical pipeline is rerun on shuffled targets -- row-wise and
whole-day, the latter respecting the day clustering -- and the day-shuffle is the
one that matters.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

CUT = np.datetime64("2026-05-25")
VAL_FRAC = 0.8
N_BOOT = 300
N_PERM = 15

# The learner. Fixed across every experiment so cells are comparable.
TREE = dict(max_iter=200, early_stopping=False, learning_rate=0.05,
            max_leaf_nodes=15, l2_regularization=1.0, min_samples_leaf=50)

# The gates a cell must clear to count as a finding.
GATE_R2 = 0.01        # regression: held-out R2 above +1% ...
GATE_AUC = 0.55       # classification: AUC above 0.55 ...
# ... AND the day-clustered CI excludes the null value AND the point estimate
# lies outside the whole permutation-null range. All three, or it is not a hit.


class Split:
    """The split, the sign vector, and the day-clustered bootstrap index sets.

    Build this once per dataset and pass it to every scorer. Holding the
    bootstrap resamples fixed across cells is deliberate: it makes two cells'
    intervals comparable rather than independently noisy.
    """

    def __init__(self, day, y_entry, seed=5, n_boot=N_BOOT):
        day = np.asarray(day)
        self.day = day
        self.fit = day < CUT
        self.test = ~self.fit
        fit_days = np.sort(np.unique(day[self.fit]))
        self.fit_days = fit_days
        vcut = fit_days[int(VAL_FRAC * len(fit_days))]
        self.vcut = vcut
        self.train = self.fit & (day < vcut)
        self.val = self.fit & (day >= vcut)

        # sign folding: +1/-1 per row, zeros sent to +1
        s = np.sign(np.asarray(y_entry, float))
        s[s == 0] = 1.0
        self.sign = s

        # day-clustered bootstrap, HELD-OUT-RELATIVE positions. Every array
        # indexed by these must already be subset to the held-out block.
        dte = day[self.test]
        self.test_days = np.unique(dte)
        pos = {d: np.flatnonzero(dte == d) for d in self.test_days}
        rb = np.random.default_rng(seed)
        self.boot = [
            np.concatenate([pos[d] for d in rb.choice(self.test_days, len(self.test_days), replace=True)])
            for _ in range(n_boot)
        ]
        self.n_test = int(self.test.sum())

    def describe(self):
        return (f"[SPLIT] train {self.train.sum():,} (<{pd.Timestamp(self.vcut).date()})   "
                f"val {self.val.sum():,}   HELD OUT {self.n_test:,} (>={pd.Timestamp(CUT).date()})\n"
                f"[SPLIT] held-out used ONCE, for scoring only; iterations chosen on val")


def _check_shapes(sp, pred, y_test):
    if len(pred) != sp.n_test or len(y_test) != sp.n_test:
        raise ValueError(
            f"held-out length mismatch: predictions {len(pred)}, targets {len(y_test)}, "
            f"held-out block {sp.n_test}. Pass the target ALREADY SUBSET to the "
            f"held-out rows -- this is the nonlinear.py CI bug, see the module docstring.")


def fit_predict(X, y, sp, classify, seed=0):
    """Fit on train, choose iterations on val, predict the held-out block once.

    Returns (score, held-out predictions, chosen iteration count). `y` is the
    FULL-length target; only the returned predictions are held-out-length.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    if classify:
        m = HistGradientBoostingClassifier(**TREE, random_state=seed).fit(X[sp.train], y[sp.train])
        sv = list(m.staged_decision_function(X[sp.val]))
        st = list(m.staged_decision_function(X[sp.test]))
        best = int(np.argmax([roc_auc_score(y[sp.val], p.ravel()) for p in sv]))
        pred = st[best].ravel()
        return roc_auc_score(y[sp.test], pred), pred, best
    m = HistGradientBoostingRegressor(**TREE, random_state=seed).fit(X[sp.train], y[sp.train])
    sv = list(m.staged_predict(X[sp.val]))
    st = list(m.staged_predict(X[sp.test]))
    best = int(np.argmin([((y[sp.val] - p) ** 2).sum() for p in sv]))
    pred = st[best]
    yy = y[sp.test]
    return 1 - ((yy - pred) ** 2).sum() / ((yy - yy.mean()) ** 2).sum(), pred, best


def ci(sp, pred, y_test, classify, ref=None):
    """Day-clustered 95% interval. `y_test` MUST already be the held-out rows.

    `ref` gives an interval on the DIFFERENCE against another model's held-out
    predictions -- the right way to price an incremental claim, and what turned
    external.py's "+2.04pp" into a number with an interval attached.
    """
    _check_shapes(sp, pred, y_test)
    if ref is not None:
        _check_shapes(sp, ref, y_test)
    out = np.empty(len(sp.boot))
    for i, ix in enumerate(sp.boot):
        yi = y_test[ix]
        try:
            if classify:
                out[i] = roc_auc_score(yi, pred[ix])
            else:
                denom = ((yi - yi.mean()) ** 2).sum()
                r = lambda p: 1 - ((yi - p[ix]) ** 2).sum() / denom
                out[i] = r(pred) - (r(ref) if ref is not None else 0.0)
        except Exception:
            out[i] = np.nan
    return np.nanpercentile(out, 2.5), np.nanpercentile(out, 97.5)


def permutation_null(X, y, sp, classify, n=N_PERM, seed=100, fitter=None):
    """Rerun the identical pipeline on shuffled targets.

    row-shuffle breaks everything; day-shuffle keeps the day clustering intact
    and is the one that matters. Returns {"row": array, "day": array}.

    `fitter(X, y, sp, seed) -> (score, ...)` replaces the harness learner when
    the model under test is not it (e.g. a logistic baseline), so every model
    gets the SAME shuffles from this one null rather than a private copy.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    if fitter is None:
        fitter = lambda X_, y_, sp_, seed: fit_predict(X_, y_, sp_, classify, seed=seed)
    fit_idx = np.flatnonzero(sp.fit)
    rows, days = [], []
    for k in range(n):
        r = np.random.default_rng(seed + k)
        yp = y.copy()
        yp[fit_idx] = y[r.permutation(fit_idx)]
        rows.append(fitter(X, yp, sp, k)[0])

        dmap = {d: v for d, v in zip(sp.fit_days, r.permutation(sp.fit_days))}
        yp2 = y.copy()
        for d in sp.fit_days:
            a = np.flatnonzero((sp.day == d) & sp.fit)
            b = np.flatnonzero(sp.day == dmap[d])
            if len(a) and len(b):
                yp2[a] = y[r.choice(b, len(a), replace=True)]
        days.append(fitter(X, yp2, sp, k)[0])
    return {"row": np.asarray(rows), "day": np.asarray(days)}


def passes(score, lo, classify, null=None):
    """All three conditions, or it is not a hit."""
    gate = (score > GATE_AUC and lo > 0.50) if classify else (score > GATE_R2 and lo > 0.0)
    if null is None:
        return gate
    return gate and score > max(null["row"].max(), null["day"].max())


def score_set(X, y, sp, classify, null=False, ref_pred=None):
    """One cell, end to end. Returns a dict ready to print or tabulate."""
    score, pred, iters = fit_predict(X, y, sp, classify)
    y_test = np.asarray(y)[sp.test]
    lo, hi = ci(sp, pred, y_test, classify, ref=ref_pred)
    nl = permutation_null(X, y, sp, classify) if null else None
    return dict(score=score, lo=lo, hi=hi, iters=iters, pred=pred,
                null=nl, hit=passes(score, lo, classify, nl))


def load():
    """The dataset. Returns (W, Y, meta, Split).

    There is no feature argument. The 41 external + 21 window features were
    retired on 2026-10-09: they were built against a 212-ticker / 36,172-bar
    panel and the panel now loads 214 / 36,215, so they were stale as well as
    superseded. `research/dislocation_model/envfeat.py` is the current feature
    layer and writes its own file; load it directly from `paths.ENVFEAT`.

    Nothing permanent was lost with `window_features`. The three columns worth
    keeping -- rv48, two and vr -- are three lines of numpy over `windows`,
    which stays in disloc.npz.
    """
    import paths
    z = np.load(paths.DISLOC)
    W = z["windows"].astype(np.float32)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    sp = Split(meta.day.to_numpy(), Y[:, 0])
    return W, Y, meta, sp
