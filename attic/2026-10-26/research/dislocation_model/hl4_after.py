"""HL-EVENT1 Part C: after the trigger. Descriptive paths (C1) and the delayed decision test (C2).

    python -u research/dislocation_model/hl4_after.py > research/dislocation_model/logs/hl4_after.log

Fixed before any result. t = 0 = T + 30 min; minute k after t = 0 is seg[:, k] (the move toward mu in sigma units,
mu and sigma frozen at the trigger; seg[:, 0] = 0). Population: the events with a finite 1-minute window and a 10h
outcome window (ev_targets `fin`); halves as in the earlier parts (HO1 days before 2026-08-15, HO2 from it).

POST-TRIGGER FLOW (0, +60] minutes, signed by d like the pre-trigger series, from minutes [t0, t0 + 60) only:
  imb_post, forced_post, open_post (shares of taker notional), notional_ratio = post taker notional / pre taker
  notional (window P1 = [-60, 0)), vol_post = post taker notional / its trailing 7-day median of 60-minute totals
  (cutoffs at or before t = 0). NaN if any minute of the window is missing.

C1 DESCRIPTIVE (held-out halves; no model):
  (a) the average after-trigger path (bins 0..600) of imb, forced, open (eventflow's after bins) and of the residual
      price (= -seg, in sigma units, 1-minute) for REVERTERS vs NON-REVERTERS (reach within 10 h), with the day-clustered
      95% interval of the difference at t = +5, +15, +30, +60, +120, +300, +600 minutes; and a PNG;
  (b) the first 60 minutes split by what the pushing flow did: DRIED UP = notional_ratio < 0.5 (a threshold fixed now;
      gap filled, the brief gives none); otherwise
      CONTINUED = imb_post > 0, FLIPPED = imb_post < 0 (imb_post = 0 is its own category). Reach rate, mean chance
      probability and the gap by category, per half, with a day-clustered interval on the gap.
C2 DELAYED DECISION (the DELAYED pattern, d = 60): population = events not at mu by minute 60 (t_reach > 60 or never)
  with a finite path in 1..60; the already-reverted ones are counted and set aside. Target reach_d = reaches mu at some
  minute in (60, 600]. chance_d = the same still-open event's 1-minute increments from minute 60 on with random signs,
  50 seeds (1000..1049), the share reaching mu in (60, 600].
  REFERENCE = log vol_48, log vol_48_1m, log sigma, |z|, and dist_now = |z| - seg[60] (unpenalised logistic).
  ADD-ON = imb_post, forced_post, open_post, log1p(vol_post), as one group with a train-median fill and an any-NaN
  indicator. Models L1 and LightGBM d1-d4 as build 3, scored on each held-out half: flag share at 80% catch, top-20%
  hit rate, beyond-chance gap, paired day-clustered intervals of every add-on model minus the reference logistic, and the
  same-learner diagnostics. CELLS: 5 models x 2 halves x 3 measures = 30; expected by chance at 95% two-sided 1.5
  (0.75 per sign). HELP = the representative's flag80 interval wholly below zero in BOTH halves. No pruning (one group).
  Directions are not stated (two-sided).
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import harness
import paths
import eventflow as ef
import flowfeat as ff
import hl3_tests as h3
from envelope import HO_BOUNDARY, day_boot
from hl3_common import CATCH, measure
from hl4_tests import CoinPop, build_design
from reachmu import auc, flag_share

D_LAG = 60
SEEDS = range(1000, 1050)
OUT = os.path.join(paths.DATASETS, "ev_post.npz")
PNG = os.path.join(paths.RESEARCH, "dislocation_model", "logs", "hl4_after.png")
CHECK_MIN = (5, 15, 30, 60, 120, 300, 600)


def post_features(EV):
    """(n_events, 5): imb_post, forced_post, open_post, notional_ratio, vol_post. One coin at a time."""
    out = np.full((len(EV), 5), np.nan)
    for c in sorted(EV.coin.unique()):
        ev = EV[EV.coin == c]
        fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"),
                             columns=["date", "taker_buy_usd", "taker_sell_usd", "liq_forced_long_usd", "liq_forced_short_usd",
                                      "open_buy_usd", "open_sell_usd"])
        a = {k: ff.dense(fl, k) for k in fl.columns if k != "date"}
        cum = {}
        for nm, arr in (("buy", a["taker_buy_usd"]), ("sell", a["taker_sell_usd"]), ("fl", a["liq_forced_long_usd"]),
                        ("fs", a["liq_forced_short_usd"]), ("ob", a["open_buy_usd"]), ("os", a["open_sell_usd"]),
                        ("tn", a["taker_buy_usd"] + a["taker_sell_usd"])):
            cum[nm], nc = ff.cum_nan(arr)
            if nm == "buy":
                cum["nc"] = nc
        tot = ff.cutoff_series(cum["tn"], cum["nc"], D_LAG)
        med = pd.Series(tot).rolling(ff.TRAIL, min_periods=ff.MINVALID).median().to_numpy()
        o = ff.minute_index(pd.to_datetime(ev["T"]) + pd.Timedelta(minutes=30))
        jj = (o - ff.CUT_PHASE) // 30
        d = ev["d"].to_numpy(float)
        s_, e_ = o, o + D_LAG
        ok = e_ <= ff.N
        s2, e2 = np.where(ok, s_, 0), np.where(ok, e_, 0)
        good = ok & ((cum["nc"][e2] - cum["nc"][s2]) == 0)
        sm = lambda k: cum[k][e2] - cum[k][s2]
        tn = np.where(good, sm("tn"), np.nan)
        # the pre-trigger P1 notional [-60, 0)
        sp, ep = o - D_LAG, o
        okp = sp >= 0
        goodp = okp & ((cum["nc"][ep] - cum["nc"][np.maximum(sp, 0)]) == 0)
        tnp = np.where(goodp, cum["tn"][ep] - cum["tn"][np.maximum(sp, 0)], np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            pos = np.where(good & (tn > 0), 1.0, np.nan)
            imb = pos * d * (sm("buy") - sm("sell")) / tn
            frc = pos * np.where(d > 0, sm("fs"), sm("fl")) / tn
            opn = pos * np.where(d > 0, sm("ob"), sm("os")) / tn
            ratio = np.where(tnp > 0, tn / tnp, np.nan)
            vol = np.where(med[jj] > 0, tn / med[jj], np.nan)
        out[ev.event_id.to_numpy()] = np.column_stack([imb, frc, opn, ratio, vol])
    return out


def day_gap_ci(P, mask, rng, n=300):
    """Mean reach - mean chance on `mask` with a day-clustered 95% interval."""
    ix = np.flatnonzero(mask)
    if len(ix) < 30:
        return np.nan, np.nan, np.nan, len(ix)
    g = P.y[ix] - P.chance[ix]
    ud, inv = np.unique(P.day[ix], return_inverse=True)
    sm, ct = np.bincount(inv, weights=g), np.bincount(inv).astype(float)
    pick = rng.integers(0, len(ud), size=(n, len(ud)))
    bm = sm[pick].sum(1) / ct[pick].sum(1)
    return float(g.mean()), *np.percentile(bm, [2.5, 97.5]), len(ix)


def c1(P, EV, AFT, MOVE, POST):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(20261015)
    rows = P.rows
    print("=" * 118)
    print("C1 -- AFTER THE TRIGGER, descriptive (held-out halves); (a) is CONDITIONED ON THE OUTCOME, not predictive")
    print("=" * 118)
    resid = -MOVE[rows]                                     # residual price signed by d, sigma units, minutes 0..600
    bins_start = ef.EDGES[ef.AFTER0:]
    bins_w = ef.WIDTH[ef.AFTER0:]
    series = {"imb": AFT[rows][:, 0, :], "forced": AFT[rows][:, 1, :], "open": AFT[rows][:, 2, :]}
    # residual price at the bin ends
    series["residual price"] = np.column_stack([resid[:, int(min(s + w, 600))] for s, w in zip(bins_start, bins_w)])
    fig, ax = plt.subplots(4, 2, figsize=(13, 13), sharex=True)
    for hi, (hn, ix) in enumerate(P.halves.items()):
        rv = ix[P.y[ix] == 1]
        nr = ix[P.y[ix] == 0]
        print(f"  {hn}: reverters {len(rv):,}, non-reverters {len(nr):,}")
        for si, (nm, M) in enumerate(series.items()):
            mr, mn = np.nanmean(M[rv], 0), np.nanmean(M[nr], 0)
            ax[si, hi].plot(bins_start, mr, label="reverters", color="tab:green")
            ax[si, hi].plot(bins_start, mn, label="non-reverters", color="tab:red")
            ax[si, hi].set_title(f"{hn}: {nm}")
            line = []
            for tmin in CHECK_MIN:
                b = int(np.searchsorted(bins_start + bins_w, tmin, side="left"))
                b = min(b, len(bins_start) - 1)
                va, vb = M[rv, b], M[nr, b]
                if np.isfinite(va).sum() < 30 or np.isfinite(vb).sum() < 30:
                    line.append(f"+{tmin}: n/a"); continue
                dd = np.nanmean(va) - np.nanmean(vb)
                days = np.unique(P.day[ix])
                pos = {d_: (np.flatnonzero(P.day[rv] == d_), np.flatnonzero(P.day[nr] == d_)) for d_ in days}
                dr = []
                for _ in range(200):
                    pick = rng.choice(days, len(days), replace=True)
                    ra = np.concatenate([pos[d_][0] for d_ in pick]); rb = np.concatenate([pos[d_][1] for d_ in pick])
                    if len(ra) and len(rb):
                        dr.append(np.nanmean(va[ra]) - np.nanmean(vb[rb]))
                lo, hi_ = np.percentile(dr, [2.5, 97.5])
                line.append(f"+{tmin}: {dd:+.4f} [{lo:+.4f},{hi_:+.4f}]")
            print(f"    {nm:<15} reverters - non-reverters at " + "; ".join(line))
    for a_ in ax.ravel():
        a_.axvline(0, color="grey", lw=0.5)
    ax[0, 0].legend()
    plt.tight_layout(); plt.savefig(PNG, dpi=100)
    print(f"  [WROTE] {os.path.relpath(PNG, paths.RESEARCH)}")
    # ---- (b) what the pushing flow did in the first hour
    imb_p, ratio_p = POST[rows, 0], POST[rows, 3]
    cat = np.full(P.n, "n/a", dtype=object)
    fin = np.isfinite(imb_p) & np.isfinite(ratio_p)
    cat[fin & (ratio_p < 0.5)] = "dried up"
    cat[fin & (ratio_p >= 0.5) & (imb_p > 0)] = "continued"
    cat[fin & (ratio_p >= 0.5) & (imb_p < 0)] = "flipped"
    cat[fin & (ratio_p >= 0.5) & (imb_p == 0)] = "exactly 0"
    print()
    print("  FIRST HOUR AFTER THE TRIGGER by what the pushing flow did (dried up: post notional < 0.5 x pre notional;")
    print("  else continued if imbalance > 0, flipped if < 0, exactly 0 reported on its own)")
    for hn, ix in P.halves.items():
        mh = np.zeros(P.n, bool); mh[ix] = True
        for k in ("continued", "dried up", "flipped", "exactly 0", "n/a"):
            m = mh & (cat == k)
            g = day_gap_ci(P, m, rng)
            if m.sum() == 0:
                continue
            print(f"    {hn} {k:<10} n {int(m.sum()):>6,}  reach {P.y[m].mean():.4f}  chance {P.chance[m].mean():.4f}  "
                  f"gap {g[0]:+.4f} [{g[1]:+.4f}, {g[2]:+.4f}]")


def c2(P, EV, MOVE, POST, ref_X):
    print()
    print("=" * 118)
    print("C2 -- DELAYED DECISION at d = +60 minutes")
    print("=" * 118)
    seg = MOVE[P.rows].astype(float)
    need = np.abs(P.e)
    t_reach = np.load(ef.OUT_TARGET)["t_reach"][P.rows]
    reverted = (t_reach > 0) & (t_reach <= D_LAG)
    still = ~reverted & np.isfinite(seg[:, 1:D_LAG + 1]).all(1)
    print(f"  events {P.n:,}; already at mu by minute {D_LAG}: {int(reverted.sum()):,} (set aside); still open {int(still.sum()):,}")
    idx = np.flatnonzero(still)
    seg_d = seg[idx, D_LAG]
    y = ((t_reach[idx] > D_LAG)).astype(int)                                   # reached mu in (60, 600]
    dist_now = need[idx] - seg_d
    # chance_d: random signs on the 1-minute increments from minute 60 on
    inc = np.diff(seg[idx, D_LAG:], axis=1)
    hits = np.zeros(len(idx))
    for sd_ in SEEDS:
        sg = np.random.default_rng([sd_, 60]).choice([-1.0, 1.0], size=inc.shape)
        hits += (seg_d[:, None] + np.cumsum(sg * inc, axis=1)).max(1) >= need[idx]
    chance = hits / len(SEEDS)

    class Sub:
        pass
    S = Sub()
    S.n, S.y, S.chance = len(idx), y, chance
    S.day, S.e = P.day[idx], P.e[idx]
    S.sp = harness.Split(S.day, S.e)
    S.tr, S.va, S.te = S.sp.train, S.sp.val, S.sp.test
    S.halves = {"HO1": np.flatnonzero(S.te & (S.day < HO_BOUNDARY)), "HO2": np.flatnonzero(S.te & (S.day >= HO_BOUNDARY))}
    S.hboot = {hn: day_boot(S.day[ix]) for hn, ix in S.halves.items()}
    print(f"  {S.sp.describe()}")
    print(f"  still-open reach_d rate {y.mean():.4f}, mean chance_d {chance.mean():.4f}, gap {y.mean() - chance.mean():+.4f}; "
          f"train {int(S.tr.sum()):,} val {int(S.va.sum()):,} HO1 {len(S.halves['HO1']):,} HO2 {len(S.halves['HO2']):,}")
    rX = np.column_stack([ref_X[idx], dist_now])
    for j in range(rX.shape[1]):
        m_ = ~np.isfinite(rX[:, j])
        if m_.any():
            rX[m_, j] = np.nanmedian(rX[S.tr, j])
    from sklearn.linear_model import LogisticRegression
    mu, sd = rX[S.tr].mean(0), rX[S.tr].std(0)
    lr = LogisticRegression(penalty=None, max_iter=5000).fit((rX[S.tr] - mu) / sd, y[S.tr])
    ref_p = lr.predict_proba((rX - mu) / sd)[:, 1]
    A = POST[P.rows][idx][:, [0, 1, 2]]
    A = np.column_stack([A, np.log1p(np.where(np.isfinite(POST[P.rows][idx][:, 4]), POST[P.rows][idx][:, 4], np.nan))])
    blk, nanm = h3.prep_block(A, S.tr)
    print(f"  add-on rows with any NaN: {int(nanm.any(1).sum()):,} of {S.n:,}")
    rn = ["log_vol_48", "log_vol_48_1m", "log_sigma", "abs_z", "dist_now"]
    sets = {"reference": (rX, rn), "ADDON": (np.column_stack([rX, blk]), rn + ["imb_post", "forced_post", "open_post", "log1p_vol_post", "ADDON_nan"])}
    SC, VL, REP = {}, {}, {}
    for sn, (Xs, ns) in sets.items():
        score, vll, _, info, rep = h3.fit_set(Xs, ns, y, S.tr, S.va)
        SC[sn], VL[sn], REP[sn] = score, vll, rep
        print(f"  {sn:<10}" + "   ".join(f"{k} {vll[k]:.5f}" for k in vll) + f"   -> representative {rep}")
    print()
    print("  CELLS: 5 models x 2 halves x 3 measures = 30; expected by chance at 95% two-sided 1.5 (0.75 per sign)")
    for hn, ix in S.halves.items():
        yh = y[ix]
        print(f"  {hn}: n {len(ix):,}, reach_d {yh.mean():.4f}, chance_d {chance[ix].mean():.4f}; reference logistic AUC {auc(yh, ref_p[ix]):.4f}; "
              f"flag80 {measure('flag80', ref_p[ix], yh, chance[ix]):.3f}, top20 {measure('top20', ref_p[ix], yh, chance[ix]):.3f}, "
              f"gap80 {measure('gap80', ref_p[ix], yh, chance[ix]):+.4f}")
        for c in CATCH:
            fs, hr, _ = flag_share(ref_p[ix], yh, c)
            print(f"      reference catch {int(100 * c)}%: flag share {fs:.3f}, hit rate {hr:.3f}")
    D = {}
    hits_good = 0
    print("  PAIRED, every ADDON model minus the reference logistic (flag80: - is better; top20, gap80: + is better; * good, ! bad)")
    for k in SC["ADDON"]:
        cells = []
        for hn, ix in S.halves.items():
            for w in h3.MEASURES:
                a_, b_, yy, cc = SC["ADDON"][k][ix], ref_p[ix], y[ix], chance[ix]
                pt = measure(w, a_, yy, cc) - measure(w, b_, yy, cc)
                dr = [measure(w, a_[b], yy[b], cc[b]) - measure(w, b_[b], yy[b], cc[b]) for b in S.hboot[hn]]
                lo, hi = np.percentile(dr, [2.5, 97.5])
                D[(k, hn, w)] = (pt, lo, hi)
                good = hi < 0 if w == "flag80" else lo > 0
                bad = lo > 0 if w == "flag80" else hi < 0
                hits_good += int(good)
                cells.append(f"{hn} {w} {pt:+.4f} [{lo:+.4f},{hi:+.4f}]{'*' if good else '!' if bad else ' '}")
        print(f"    ADDON {k:<3}" + "  ".join(cells))
    print(f"  good-side cells {hits_good} of 30 (expected by chance 0.75)")
    ref_tree = min((k for k in VL["reference"] if k != "L1"), key=lambda k: VL["reference"][k])
    tree_k = min((k for k in VL["ADDON"] if k != "L1"), key=lambda k: VL["ADDON"][k])
    print("  SAME-LEARNER DIAGNOSTICS, flag80")
    for lbl, a_, b_ in (("L1 - L1", SC["ADDON"]["L1"], SC["reference"]["L1"]), (f"{tree_k} - {ref_tree}", SC["ADDON"][tree_k], SC["reference"][ref_tree])):
        res = []
        for hn, ix in S.halves.items():
            yy, cc = y[ix], chance[ix]
            pt = measure("flag80", a_[ix], yy, cc) - measure("flag80", b_[ix], yy, cc)
            dr = [measure("flag80", a_[ix][b], yy[b], cc[b]) - measure("flag80", b_[ix][b], yy[b], cc[b]) for b in S.hboot[hn]]
            lo, hi = np.percentile(dr, [2.5, 97.5])
            res.append((hn, pt, lo, hi))
        print(f"    {lbl:<14}" + "  ".join(f"{h} {p:+.4f} [{lo:+.4f},{hi:+.4f}]" for h, p, lo, hi in res)
              + f"   clears both: {'YES' if all(r[3] < 0 for r in res) else 'no'}")
    rep = REP["ADDON"]
    clear = [hn for hn in S.halves if D[(rep, hn, "flag80")][2] < 0]
    print(f"  READING: representative {rep}; HELP (flag80 wholly below zero in both halves): {'YES' if len(clear) == 2 else 'NO'}"
          + (f"  (clears in {clear[0]} only: regime-dependent)" if len(clear) == 1 else ""))


def main():
    t0 = time.time()
    P = CoinPop()
    EV = P.EV_all
    ref_X = build_design(P)[0]
    AFT = np.load(ef.OUT_AFTER)["after"]
    MOVE = np.load(ef.OUT_TARGET)["move"]
    POST = post_features(EV)
    np.savez_compressed(OUT, post=POST)
    print(f"[POST] imb/forced/open/ratio/vol over (0, +60]: finite for {int(np.isfinite(POST[:, 0]).sum()):,} of {len(EV):,} events "
          f"[{time.time() - t0:.0f}s]")
    c1(P, EV, AFT, MOVE, POST)
    c2(P, EV, MOVE, POST, ref_X)
    print(f"  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
