"""HL-EVENT1 Part B2-B4: does the TYPE of flow, or the part of the move flow does not explain, predict the return to mu?

    python -u research/dislocation_model/hl4_tests.py > research/dislocation_model/logs/hl4_tests.log

THE DESIGN IS HL-FLOW1's (hl3_tests.run), unchanged, on the coin-level events. Fixed before any model is fitted;
held-out is touched once, at scoring; nothing is chosen on it.

POPULATION: the events with a finite 1-minute window and a 10h outcome window (ev_targets `fin`). TARGET: reach
(depth >= |z| on the 1-minute closes of the coin's spread, no stop, 10h), chance = 50 sign-flip seeds (eventflow.py).
SPLIT: harness.Split on the event day (UTC date of T): CUT 2026-05-25, validation = last 20% of the fit days,
HO1 = held-out days before 2026-08-15, HO2 from 2026-08-15.

REFERENCE (position): unpenalised logistic on log vol_48, log vol_48_1m, log sigma, |z|. The reference's own
held-out result on these events is printed (it may differ from the pair-level gap of -0.097 / -0.066).

FEATURES AT t = 0 (window series of eventflow.py, all signed by d and built from minutes < t = 0), windows P1, C6, C24:
  FORCED         forced share on the pushing side                                         3   expected +
  OPENCLOSE      opening push (-), closing push (+), open/(open+close) (two-sided)       9
  CONCENTRATION  top-3 share, wallets per $M normalised (two-sided)  [PROXIES]           6
  CONC-TWAP      TWAP share (two-sided), tested only on the rows where it exists          3
  VOLUME         taker notional / its trailing 7-day median (two-sided)                   3
  IMPACT         explained_share, unexplained_move (+: larger unexplained move -> reaches mu more)  2
  MARKET         benchmark return over P1/C6/C24 (two-sided), market forced liquidation / its median
                 over P1/C6/C24 (two-sided), 60-minute breadth (two-sided)                7
  33 model inputs. backstop and ADL are excluded (zero outside the 2025-10-10 crash). The expected signs are the brief's
  ONLY: forced -> reaches mu more (+); opening -> less (-); closing -> more (+); larger unexplained move -> more (+); everything
  else, including the ratio, top-3, wallets, TWAP, volume, explained_share and the market block, is two-sided.
  [Gap filled, consistent with HL-FLOW1: TWAP is NOT inside CONCENTRATION or ALL, because NaN-filling it would put TWAP
  into fits on rows where it does not exist; it is its own sub-group.]

TESTS: hl3_tests.run: reference vs reference + each group alone vs ALL vs the pruned set (the user's rule: drop a group
unless some model's validation interval is wholly above zero), models logistic L1 and LightGBM d1-d4, flag share at
80% catch / top-20% hit rate / beyond-chance gap, paired day-clustered intervals vs the reference logistic, the
same-learner diagnostics, the row-permutation null, the direction check, the reading rules.
CELLS: (6 groups + ALL + CONC-TWAP + KEPT = 9 sets) x 5 models x 2 halves x 3 measures = 270; expected by chance at 95%
two-sided 13.5 (6.75 per sign).

B4 THE STRONG-EVENT CUT (pre-registered, one extra row per group; not used to choose anything): the same test
restricted to events with (|z| >= 3) OR (forced share P1 > 0). Each group set and the reference are REFITTED on the
restricted train rows; the representative (lowest validation log loss) is scored on the restricted held-out rows against
the unpenalised logistic reference refitted on the same rows. 7 rows (6 groups + ALL) x 2 halves x 3 measures = 42
cells, intervals day-clustered, n reported.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import harness
import paths
import coinevents as ce
import eventflow as ef
import hl3_tests as h3
from envelope import HO_BOUNDARY, day_boot
from hl3_common import CATCH, half_measure, measure
from reachmu import auc, flag_share

GROUPS = ("FORCED", "OPENCLOSE", "CONCENTRATION", "VOLUME", "IMPACT", "MARKET")
EXTRA = "CONC-TWAP"
WIN3 = ("P1", "C6", "C24")
N_BOOT = 300


class CoinPop:
    """The matched coin-level population with hl3_common.Pop's interface."""

    def __init__(self):
        EV = pd.read_parquet(ce.EVENTS)
        T = np.load(ef.OUT_TARGET)
        fin = T["fin"].astype(bool)
        self.EV_all, self.fin = EV, fin
        self.rows = np.flatnonzero(fin)
        self.meta = EV.iloc[self.rows].reset_index(drop=True)
        self.y = T["reach"][self.rows].astype(int)
        self.chance = T["chance"][self.rows].astype(float)
        self.vol48, self.vol48m = T["vol_48"][self.rows], T["vol_48_1m"][self.rows]
        self.day = pd.to_datetime(self.meta["T"]).dt.floor("D").to_numpy()
        self.e = self.meta["z"].to_numpy(float)
        self.sp = harness.Split(self.day, self.e)
        self.tr, self.va, self.te = self.sp.train, self.sp.val, self.sp.test
        self.halves = {"HO1": np.flatnonzero(self.te & (self.day < HO_BOUNDARY)),
                       "HO2": np.flatnonzero(self.te & (self.day >= HO_BOUNDARY))}
        self.hboot = {hn: day_boot(self.day[ix]) for hn, ix in self.halves.items()}
        self.n = len(self.rows)


def build_design(P):
    """(ref_X, rnames, FX, names, expect, cols_of, extra) for the coin-level events."""
    Z = np.load(ef.OUT_SERIES)
    S = Z["ev"][P.rows].astype(float)
    ser = [str(x) for x in Z["series"]]
    wn = [str(x) for x in Z["windows"]]
    I = np.load(os.path.join(paths.DATASETS, "ev_impact.npz"))
    M = np.load(os.path.join("" + paths.DATASETS, "ev_market.npz"))
    jj = (ef.ff.minute_index(pd.to_datetime(P.meta["T"]) + pd.Timedelta(minutes=30)) - ef.ff.CUT_PHASE) // 30
    cols, names, expect, grp = [], [], [], []

    def add(g, nm, v, e=""):
        grp.append(g); names.append(nm); expect.append(e); cols.append(v)
    for w in WIN3:
        add("FORCED", f"forced_{w}", S[:, ser.index("forced"), wn.index(w)], "+")
    for w in WIN3:
        add("OPENCLOSE", f"open_{w}", S[:, ser.index("open"), wn.index(w)], "-")
        add("OPENCLOSE", f"close_{w}", S[:, ser.index("close"), wn.index(w)], "+")
        add("OPENCLOSE", f"ratio_{w}", S[:, ser.index("ratio"), wn.index(w)])
    for w in WIN3:
        add("CONCENTRATION", f"top3_{w}", S[:, ser.index("top3"), wn.index(w)])
        add("CONCENTRATION", f"wallets_{w}", S[:, ser.index("wallets"), wn.index(w)])
    for w in WIN3:
        add(EXTRA, f"twap_{w}", S[:, ser.index("twap"), wn.index(w)])
    for w in WIN3:
        add("VOLUME", f"volume_{w}", S[:, ser.index("volume"), wn.index(w)])
    add("IMPACT", "explained_share", I["explained_share"][P.rows])
    add("IMPACT", "unexplained_move", I["unexplained_move"][P.rows], "+")
    for w in WIN3:
        add("MARKET", f"mk_idx_{w}", S[:, ser.index("mk_idx"), wn.index(w)])
    for w in WIN3:
        add("MARKET", f"mk_liq_{w}", S[:, ser.index("mk_liq"), wn.index(w)])
    add("MARKET", "breadth_60", M["breadth_j"][jj])
    FX = np.column_stack(cols).astype(float)
    cols_of = {g: [j for j, gg in enumerate(grp) if gg == g] for g in GROUPS}
    extra = (EXTRA, [j for j, gg in enumerate(grp) if gg == EXTRA])
    # reference features: log vol_48, log vol_48_1m, log sigma, |z|
    raw = np.column_stack([P.vol48, P.vol48m, P.meta["sigma"].to_numpy(float)])
    with np.errstate(divide="ignore", invalid="ignore"):
        lg = np.where(raw > 0, np.log(raw), np.nan)
    ref_X = np.column_stack([lg, np.abs(P.e)])
    for j in range(ref_X.shape[1]):
        m_ = ~np.isfinite(ref_X[:, j])
        if m_.any():
            ref_X[m_, j] = np.nanmedian(ref_X[P.tr, j])
    return ref_X, FX, names, expect, cols_of, extra


def fit_reference(P, ref_X, mask=None):
    from sklearn.linear_model import LogisticRegression
    m = P.tr if mask is None else (P.tr & mask)
    mu, sd = ref_X[m].mean(0), ref_X[m].std(0)
    lr = LogisticRegression(penalty=None, max_iter=5000).fit((ref_X[m] - mu) / sd, P.y[m])
    return lr.predict_proba((ref_X - mu) / sd)[:, 1], lr


def strong_cut(P, D, FXn):
    """B4: the strong-event cut, one extra row per group."""
    forced_p1 = D["FX"][:, D["names"].index("forced_P1")]
    mask = (np.abs(P.e) >= 3) | (np.nan_to_num(forced_p1) > 0)
    print()
    print("=" * 118)
    print("B4 -- THE STRONG-EVENT CUT: (|z| >= 3) OR (forced share P1 > 0); groups and reference refitted on the restricted rows")
    print("=" * 118)
    ph = {hn: ix[mask[ix]] for hn, ix in P.halves.items()}
    print(f"  n: all {int(mask.sum()):,} of {P.n:,}; train {int((mask & P.tr).sum()):,}, val {int((mask & P.va).sum()):,}, "
          f"HO1 {len(ph['HO1']):,}, HO2 {len(ph['HO2']):,}; reach rate {P.y[mask].mean():.4f}")
    ref_p, _ = fit_reference(P, D["ref_X"], mask)
    boots = {hn: day_boot(P.day[ix]) for hn, ix in ph.items()}
    for hn, ix in ph.items():
        print(f"  {hn} reference (restricted refit): flag80 {measure('flag80', ref_p[ix], P.y[ix], P.chance[ix]):.3f}, "
              f"top20 {measure('top20', ref_p[ix], P.y[ix], P.chance[ix]):.3f}, gap80 {measure('gap80', ref_p[ix], P.y[ix], P.chance[ix]):+.4f}")
    sets = {}
    for g in GROUPS:
        blk, _ = h3.prep_block(D["FX"][:, D["cols_of"][g]], P.tr & mask)
        sets[g] = np.column_stack([D["ref_X"], blk])
    allb = [h3.prep_block(D["FX"][:, D["cols_of"][g]], P.tr & mask)[0] for g in GROUPS]
    sets["ALL"] = np.column_stack([D["ref_X"]] + allb)
    hits = 0
    print(f"  {'set':<14}{'model':<6}" + "".join(f"{hn + ' ' + w:>30}" for hn in ph for w in h3.MEASURES))
    for sn, Xs in sets.items():
        score, vll, _, _, rep = h3.fit_set(Xs, [f"c{i}" for i in range(Xs.shape[1])], P.y, P.tr, P.va, mask)
        cells = []
        for hn, ix in ph.items():
            for w in h3.MEASURES:
                a, b_, yy, cc = score[rep][ix], ref_p[ix], P.y[ix], P.chance[ix]
                pt = measure(w, a, yy, cc) - measure(w, b_, yy, cc)
                dr = [measure(w, a[b], yy[b], cc[b]) - measure(w, b_[b], yy[b], cc[b]) for b in boots[hn]]
                lo, hi = np.percentile(dr, [2.5, 97.5])
                good = hi < 0 if w == "flag80" else lo > 0
                hits += int(good)
                cells.append(f"{pt:+.4f} [{lo:+.4f},{hi:+.4f}]{'*' if good else ('!' if (lo > 0 if w == 'flag80' else hi < 0) else ' ')}")
        print(f"  {sn:<14}{rep:<6}" + "".join(f"{c:>30}" for c in cells))
    print(f"  B4 good-side hits: {hits} of 42 cells (expected by chance {0.025 * 42:.1f}); representative = lowest validation log loss; "
          f"flag80: - is better, top20 and gap80: + is better; * good side, ! bad side")


def main():
    t0 = time.time()
    P = CoinPop()
    ref_X, FX, names, expect, cols_of, extra = build_design(P)
    ref_p, lr = fit_reference(P, ref_X)
    print("=" * 118)
    print("HL-EVENT1 PART B -- the reference on the coin-level events")
    print("=" * 118)
    print(f"  events {len(P.EV_all):,}; matched population {P.n:,} (finite 1-minute window and a 10h outcome window); "
          f"train {int(P.tr.sum()):,} val {int(P.va.sum()):,} held out {int(P.te.sum()):,} (HO1 {len(P.halves['HO1']):,}, HO2 {len(P.halves['HO2']):,})")
    print(f"  reach rate {P.y.mean():.4f}, mean chance {P.chance.mean():.4f}; reference coefficients {np.round(lr.coef_[0], 3).tolist()}")
    for hn, ix in P.halves.items():
        yh = P.y[ix]
        print(f"  {hn}: n {len(ix):,}, reach {yh.mean():.4f}, chance {P.chance[ix].mean():.4f}, AUC {auc(yh, ref_p[ix]):.4f}")
        for c in CATCH:
            fs, hr, fx = flag_share(ref_p[ix], yh, c)
            print(f"    catch {int(100 * c)}%: flag share {fs:.3f}, hit rate {hr:.3f}  (random {c:.3f} / {yh.mean():.3f}); flagged chance {P.chance[ix][fx].mean():.3f}")
        for kind, lbl in (("flag80", "flag share at 80% catch"), ("top20", "top-20% hit rate"),
                          ("gap80", "beyond-chance gap, flagged at 80% catch"), ("gap20", "beyond-chance gap, top 20%")):
            r = half_measure(P, kind, ref_p, hn)
            print(f"    {lbl:<44}{r[0]:+.4f}  [{r[1]:+.4f}, {r[2]:+.4f}]")
    g80 = [half_measure(P, "gap80", ref_p, hn) for hn in P.halves]
    print(f"  REFERENCE GATE (gap80 wholly above zero in both halves): {'**YES**' if all(r[1] > 0 for r in g80) else 'NO'}")
    print()
    D = dict(title="HL-EVENT1 PART B3 -- flow features against position, coin-level events", ref_X=ref_X, ref_p=ref_p,
             rnames=["log_vol_48", "log_vol_48_1m", "log_sigma", "abs_z"], FX=FX, names=names, expect=expect,
             groups=GROUPS, cols_of=cols_of, extra=extra)
    h3.run(P, D)
    strong_cut(P, D, FX)
    print(f"  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
