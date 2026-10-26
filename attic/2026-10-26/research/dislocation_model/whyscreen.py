"""WHY-IT-MOVED screens: B (the best point toward mu) and A (the envelope).

    .venv/bin/python research/dislocation_model/whyscreen.py 2>&1 \
        | tee research/dislocation_model/logs/whyscreen.log

Reads research/datasets/whyfeat.npz (built and checked by whyfeat.py). The
matched 53,757-episode set, harness.Split unchanged (train < 2026-05-01, val,
held out >= 2026-07-18 touched once), HO1/HO2 split at 2026-08-26.

NEW FEATURES. All 20 columns of whyfeat.npz: lone_share, common_share,
mkt_move, vol_spike_mover, vol_spike_ratio, vadj_resid, lagger_spread at 4 and
12 bars, plus vol_spike_mover_1m, vol_spike_ratio_1m, vadj_resid_1m at 4 and 12
minutes. Gap filled, fixed before the run: a model needs complete rows, so if
every new column is finite on at least 95% of the 53,757, missing values are
set to that column's TRAIN median (reported per column); if any column is
below 95%, stop. Features flagged "restates volatility" by whyfeat are
reported as such whatever the screens say.

TRANSFORMS, fixed before the run at the user's instruction, not tuned:
  log(x)                 vol_spike_mover, vol_spike_ratio, lagger_spread and
                         their _1m versions (x <= 0 -> missing, counted)
  sign(x) * log(1 + |x|) vadj_resid and vadj_resid_1m
Applied BEFORE the missing-value fill, so the fill uses transformed medians.

SIGN-FLIP NULL (added to screen B's base distributions at the user's
instruction): each episode's 1-minute increments of the folded move (from the
entry close, bridging missing minutes between finite ones) get random signs,
20 seeds; timing, order and depth recomputed on the flipped paths and reported
beside the real ones. Real minus flipped depth and order are then broken down
by decile of each new feature (finite rows), with day-clustered intervals.
The flipped path keeps every step's size and removes any directional drift,
so real - flipped is the reversion the path carries.

SCREEN B -- the best point toward mu within 10h, from the 1-minute path on the
frozen entry geometry (envelope.one_min_paths; minutes 1..600 after the entry
bar's close, the same window as the 10h MFE).
  depth   the largest move toward mu, in sigma = the 10h MFE (asserted equal).
          Not refitted here: its result is screen A's MFE 10h cells.
  timing  minutes from entry to that best point (first minute if tied)
  order   1 if the best point comes BEFORE the worst point (the 10h MAE's
          minute), else 0
Base distributions first, before any model. Then, each on the current six
features (vol_48, vol_48_1m, vratio, vol_slope, sandwich, off_mark) against
the six plus the new 20, fitted on TRAIN:
  timing  Linear QR (unpenalised, HiGHS, standardised on train) at q25/50/75,
          re-ordered along q. Skill = pinball skill vs the train climatology
          quantiles, averaged over the three quantiles.
  order   logistic regression (standardised on train, default L2 C=1).
          Skill = log-loss skill vs the train base rate; AUC reported beside.
Paired differences (six+new minus six) with day-clustered 95% intervals, in
HO1 and HO2 separately. Calibration by decile of predicted probability for
order. Permutation importance of each new feature in the six+new models
(held out, 20 shuffles, skill points, day-clustered interval).
  SCREEN B PASSES only if the new features improve timing OR order with the
  paired interval clearing zero in BOTH HO1 and HO2. A pass earns a separate
  trading test later; it is not a result.

SCREEN A -- the envelope, on the current registry (Climatology, Linear QR,
CQR), MAE and MFE, all five horizons, 1-minute targets. Baseline: the cached
registry predictions (MAE on vol_48_1m, MFE on vol_48). New: Linear QR and CQR
refitted on baseline + the 20 new columns, two-pass enforced; paired,
day-clustered, against their own cached predictions. Climatology uses no
features and is the fixed denominator.
  THE MARKET-VOL ADOPTION RULE, unchanged: per direction, a cell LOSES if
  skill or gap is significantly worse (that is confirmed harm; there is no kNN
  in the registry, so the kNN-dilution exception never applies), IMPROVES if
  one is significantly better and neither worse. A direction CLEARS with no
  confirmed harm and IMPROVES in a majority of its cells. Gap filled: with
  QTREE and kNN retired the direction has 10 cells (2 models x 5 horizons),
  so the majority is 6.
  PER-MODEL ADOPTION (the rule market_vol was adopted under for Linear QR /
  MAE): ADOPT for a model and direction if no horizon has a significantly
  worse skill or gap AND the mean of the five paired skill gains has a
  day-clustered interval above zero.
"""
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, QuantileRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import roc_auc_score

import harness
import paths
from envelope import (FP_KEY, HLABEL, HORIZONS, HO_BOUNDARY, _pinball_rows,
                      build_context, build_targets_1m, build_targets_30m,
                      cache_fingerprint, day_boot, enforce_two_pass, fit_cqr,
                      fit_linear, flat_targets, gap_ci, gap_paired_ci,
                      load_1m_series, one_min_paths, scan_1m_coverage,
                      select_1m_subset, skill_ci)
from vol1m import MAE_CACHE, paired_skill_ci

TQ = (0.25, 0.50, 0.75)
N_SHUF = 20
SEED = 20261013


def pin(y, p, q):
    d = y - p
    return np.maximum(q * d, (q - 1) * d)


def fit_qr(Ztr, ytr, Zte):
    out = np.empty((len(Zte), len(TQ)))
    models = []
    for j, q in enumerate(TQ):
        m = None
        for al in (0.0, 1e-8, 1e-6, 1e-4):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", ConvergenceWarning)
                    m = QuantileRegressor(quantile=q, alpha=al, solver="highs").fit(Ztr, ytr)
                break
            except Exception:
                continue
        if m is None:
            raise SystemExit(f"[WHYS] timing QR q={q} failed at every alpha")
        out[:, j] = m.predict(Zte)
        models.append(m)
    return np.maximum.accumulate(out, axis=1), models


def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def why_columns(XN, names, train):
    """The 20 columns as the screens use them: transformed, then gaps filled.

    One definition, shared by whyscreen and whycheck, so the checks run on the
    exact columns screen A scored. Returns (filled, transformed-not-filled,
    log names, signed-log names, values <= 0 per log column, fill rows).
    Stops if any column is finite on under 95% of rows (rule in the docstring).
    """
    XN = XN.astype(float).copy()
    tf_log, tf_slog, nonpos = [], [], {}
    for j, nm in enumerate(names):
        base_nm = nm.rsplit("_", 1)[0]
        if base_nm in ("vol_spike_mover", "vol_spike_ratio", "lagger_spread",
                       "vol_spike_mover_1m", "vol_spike_ratio_1m"):
            c = XN[:, j]
            nonpos[nm] = int((np.isfinite(c) & (c <= 0)).sum())
            with np.errstate(divide="ignore", invalid="ignore"):
                XN[:, j] = np.where(c > 0, np.log(c), np.nan)
            tf_log.append(nm)
        elif base_nm in ("vadj_resid", "vadj_resid_1m"):
            XN[:, j] = np.sign(XN[:, j]) * np.log1p(np.abs(XN[:, j]))
            tf_slog.append(nm)
    XN_raw = XN.copy()          # transformed, NOT filled: for the decile breakdown
    fill = []
    for j, nm in enumerate(names):
        fr = np.isfinite(XN[:, j]).mean()
        if fr < 0.95:
            raise SystemExit(f"[WHYS] STOP -- {nm} is finite on {100*fr:.1f}% of the "
                             f"53,757, under the 95% fixed before the run.")
        med = float(np.nanmedian(XN[train, j]))
        nmiss = int((~np.isfinite(XN[:, j])).sum())
        XN[~np.isfinite(XN[:, j]), j] = med
        fill.append((nm, nmiss, med))
    return XN, XN_raw, tf_log, tf_slog, nonpos, fill


def main(skip_b=False):
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f5 = np.load(paths.ENVFEAT, allow_pickle=False)
    X5 = f5["X"].astype(np.float64)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], rows):
        raise SystemExit("[WHYS] vol48_1m rows differ.")
    W = np.load(os.path.join(paths.DATASETS, "whyfeat.npz"), allow_pickle=False)
    if not ((W["ticker_a"] == meta.ticker_a.to_numpy(str)).all()
            and (W["entry_time"] == pd.to_datetime(meta.entry_time).to_numpy("datetime64[ns]")).all()):
        raise SystemExit("[WHYS] whyfeat.npz is not aligned to disloc_meta.")
    names = [str(x) for x in W["names"]]
    restates = set(str(x) for x in W["restates"])
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    sp = harness.Split(day, e)
    XN, XN_raw, tf_log, tf_slog, nonpos, fill = why_columns(W["X"][rows], names, sp.train)
    print("=" * 120)
    print("WHY-IT-MOVED SCREENS -- B (the best point toward mu) then A (the envelope)")
    print("=" * 120)
    print(f"  {sp.describe()}")
    print(f"  TRANSFORMS (fixed, not tuned): log -> {', '.join(tf_log)}")
    print(f"    values <= 0 set missing: " + ", ".join(f"{k} {v}" for k, v in nonpos.items() if v)
          + (" (none)" if not any(nonpos.values()) else ""))
    print(f"    sign(x)*log(1+|x|) -> {', '.join(tf_slog)}")
    print(f"  new features: {len(names)};  flagged 'restates volatility' by whyfeat: "
          f"{', '.join(sorted(restates)) if restates else 'none'}")
    print("  missing values set to the TRAIN median: " + ", ".join(
        f"{nm} {n_}" for nm, n_, _ in fill if n_) + (" (none)" if not any(n_ for _, n_, _ in fill) else ""))
    SIX = np.column_stack([X5[rows, 0], v48["vol_48_1m"], X5[rows, 1], X5[rows, 2],
                           X5[rows, 3], X5[rows, 4]])
    print()

    if skip_b:
        T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
        print("  SCREEN B skipped (--skip-b): its results are in logs/whyscreen_B.log")
        print()
    if not skip_b:
        # ================= SCREEN B targets =================
        series = load_1m_series(sorted(set(meta.ticker_a.iloc[rows]) | set(meta.ticker_b.iloc[rows])),
                                False)
        P, miss = one_min_paths(meta, rows, series)
        del series
        s = np.sign(e)
        s[s == 0] = 1.0
        move = -(P - e[:, None]) * s[:, None]
        seg = move[:, 1:601]
        depth = np.nanmax(seg, 1)
        T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
        if float(np.max(np.abs(depth - T1M[("MFE", 20)]))) > 0:
            raise SystemExit("[WHYS] depth does not equal the 10h MFE.")
        best = np.nanargmax(np.where(np.isfinite(seg), seg, -np.inf), 1) + 1
        worst = np.nanargmax(np.where(np.isfinite(seg), -seg, -np.inf), 1) + 1
        timing = best.astype(float)
        order = (best < worst).astype(int)
        reach = depth >= np.abs(e)
        print("=" * 120)
        print("SCREEN B -- BASE DISTRIBUTIONS, before any model (minutes 1..600 after the entry bar's close)")
        print("=" * 120)
        print(f"  depth = the 10h MFE, asserted equal to the registry target (max diff 0)")
        for lbl, m in (("all 53,757", np.ones(len(rows), bool)), ("train", sp.train),
                       ("held out", sp.test), ("HO1", sp.test & (day < HO_BOUNDARY)),
                       ("HO2", sp.test & (day >= HO_BOUNDARY))):
            tm = timing[m]
            print(f"  {lbl:<11} n {int(m.sum()):>6,}  timing median {np.median(tm):>5.0f} min "
                  f"(p25 {np.percentile(tm, 25):.0f}, p75 {np.percentile(tm, 75):.0f});  best point "
                  f"FIRST {order[m].mean():.3f};  reaches mu {reach[m].mean():.3f};  depth median "
                  f"{np.median(depth[m]):.2f} sigma")
        hist = np.histogram(timing, bins=np.arange(0, 601, 60))[0]
        print("  timing histogram by hour (all): " + "  ".join(
            f"{h}-{h+1}h {c/len(timing):.3f}" for h, c in enumerate(hist)))
        F_ = lambda x: (2 / np.pi) * np.arcsin(np.sqrt(x))
        arc = np.diff(F_(np.linspace(0, 1, 11)))
        print("  arcsine law for the time of the maximum of a DRIFTLESS walk on [0, 10h]:  "
              + "  ".join(f"{h}-{h+1}h {a:.3f}" for h, a in enumerate(arc)))
        print("  NOTE: the timing histogram matches the arcsine law -- the U-shape is what a")
        print("  driftless walk produces, not evidence of structure. The only departure is a")
        print(f"  tilt: first hour {hist[0]/len(timing):.3f} vs {arc[0]:.3f} expected, last hour "
              f"{hist[-1]/len(timing):.3f} vs {arc[-1]:.3f}.")
        print(f"  best point in the last minute of the 10h window (still improving): "
              f"{(timing == 600).mean():.3f};  in the first minute: {(timing == 1).mean():.3f}")
        # ---- the sign-flip null ----
        fin = np.isfinite(move)
        last = pd.DataFrame(move).ffill(axis=1).to_numpy()
        prevv = np.concatenate([np.zeros((len(move), 1)), last[:, :-1]], axis=1)
        inc = np.where(fin, move - prevv, 0.0)
        inc[:, 0] = 0.0
        fl_t, fl_o, fl_d = [], [], []
        for sd_ in range(20):
            sg = np.random.default_rng(1000 + sd_).choice([-1.0, 1.0], size=inc.shape)
            pth = np.cumsum(sg * inc, axis=1)
            pth[~fin] = np.nan
            sg_ = pth[:, 1:601]
            fd = np.nanmax(sg_, 1)
            fb = np.nanargmax(np.where(np.isfinite(sg_), sg_, -np.inf), 1) + 1
            fw = np.nanargmax(np.where(np.isfinite(sg_), -sg_, -np.inf), 1) + 1
            fl_t.append(fb.astype(float))
            fl_o.append((fb < fw).astype(float))
            fl_d.append(fd)
        fl_t, fl_o, fl_d = np.array(fl_t), np.array(fl_o), np.array(fl_d)
        print()
        print("  SIGN-FLIP NULL -- each 1-minute increment's sign randomised, 20 seeds "
              "(median [min, max] over seeds)")
        mm = lambda a: f"{np.median(a):.3f} [{a.min():.3f}, {a.max():.3f}]"
        for lbl, m in (("all 53,757", np.ones(len(rows), bool)), ("held out", sp.test),
                       ("HO1", sp.test & (day < HO_BOUNDARY)), ("HO2", sp.test & (day >= HO_BOUNDARY))):
            print(f"    {lbl:<11} timing median: real {np.median(timing[m]):.0f} min, flipped "
                  f"{mm(np.median(fl_t[:, m], 1))};  best FIRST: real {order[m].mean():.3f}, "
                  f"flipped {mm(fl_o[:, m].mean(1))};  depth median: real {np.median(depth[m]):.3f}, "
                  f"flipped {mm(np.median(fl_d[:, m], 1))};  reaches mu: real {reach[m].mean():.3f}, "
                  f"flipped {mm((fl_d[:, m] >= np.abs(e[m])).mean(1))}")
        fh = np.histogram(fl_t.ravel(), bins=np.arange(0, 601, 60))[0] / fl_t.size
        print("    flipped timing histogram by hour: " + "  ".join(
            f"{h}-{h+1}h {c:.3f}" for h, c in enumerate(fh)))
        dd = depth - fl_d.mean(0)                 # per episode, real - mean flipped
        do = order - fl_o.mean(0)
        print()
        print("  REAL MINUS FLIPPED, by decile of each new feature (transformed; finite rows only;")
        print("  day-clustered 95% intervals). depth in sigma; order as a share.")
        for j, nm in enumerate(names):
            v = XN_raw[:, j]
            ok_ = np.isfinite(v)
            g = np.full(len(v), -1)
            g[ok_] = np.clip(np.searchsorted(np.quantile(v[ok_], np.linspace(0, 1, 11)[1:-1]),
                                             v[ok_], side="right"), 0, 9)
            cells_d, cells_o = [], []
            for k in range(10):
                mk = np.flatnonzero(g == k)
                bt = day_boot(day[mk])
                bd_ = [dd[mk][ix].mean() for ix in bt]
                bo_ = [do[mk][ix].mean() for ix in bt]
                ld, hd = np.percentile(bd_, [2.5, 97.5])
                lo_, ho_ = np.percentile(bo_, [2.5, 97.5])
                cells_d.append(f"{dd[mk].mean():+.2f}[{ld:+.2f},{hd:+.2f}]")
                cells_o.append(f"{do[mk].mean():+.3f}[{lo_:+.3f},{ho_:+.3f}]")
            print(f"    {nm:<24}depth " + " ".join(cells_d))
            print(f"    {'':<24}order " + " ".join(cells_o))
        print(f"  [{time.time()-t0:.0f}s]")
        print()

        # ================= SCREEN B models =================
        dte = day[sp.test]
        h1 = dte < HO_BOUNDARY
        halves = {"HO1": (h1, day_boot(dte[h1])), "HO2": (~h1, day_boot(dte[~h1]))}
        bfull = day_boot(dte)
        rng = np.random.default_rng(SEED)
        sets = {"six": SIX, "six+new": np.column_stack([SIX, XN])}
        Z, preds, mods = {}, {}, {}
        for nm, Xs in sets.items():
            mu, sd = Xs[sp.train].mean(0), Xs[sp.train].std(0)
            sd[sd == 0] = 1.0
            Z[nm] = (Xs - mu) / sd
        yt = timing[sp.test]
        clim_t = np.tile(np.quantile(timing[sp.train], TQ), (sp.n_test, 1))
        for nm in sets:
            p_, ms = fit_qr(Z[nm][sp.train], timing[sp.train], Z[nm][sp.test])
            preds[("timing", nm)], mods[("timing", nm)] = p_, ms
            lr = LogisticRegression(C=1.0, max_iter=5000).fit(Z[nm][sp.train], order[sp.train])
            preds[("order", nm)] = lr.predict_proba(Z[nm][sp.test])[:, 1]
            mods[("order", nm)] = lr
            print(f"  fitted timing QR and order logistic on {nm}   [{time.time()-t0:.0f}s]", flush=True)
        yo = order[sp.test]
        pclim = float(order[sp.train].mean())

        def t_rows(p_):
            return np.mean([pin(yt, p_[:, j], q) for j, q in enumerate(TQ)], axis=0)

        tl = {nm: t_rows(preds[("timing", nm)]) for nm in sets}
        tc = t_rows(clim_t)
        ol = {nm: ll(yo, preds[("order", nm)]) for nm in sets}
        oc = ll(yo, np.full(len(yo), pclim))

        def skill(lr_, lc_, ix):
            return 100.0 * (1 - lr_[ix].mean() / lc_[ix].mean())

        print("=" * 120)
        print("SCREEN B -- RESULTS: skill vs climatology, and six+new minus six (paired, day-clustered 95%)")
        print("=" * 120)
        passB = {}
        for tgt, L_, LC_ in (("timing", tl, tc), ("order", ol, oc)):
            ok_halves = []
            for hn, (m, bt) in [("held out", (np.ones(len(yt), bool), bfull))] + list(halves.items()):
                idx = np.flatnonzero(m)
                s6 = skill(L_["six"], LC_, idx)
                sn = skill(L_["six+new"], LC_, idx)
                dr = [skill(L_["six+new"], LC_, idx[ix]) - skill(L_["six"], LC_, idx[ix]) for ix in bt]
                lo, hi = np.percentile(dr, [2.5, 97.5])
                extra = ""
                if tgt == "order":
                    a6 = roc_auc_score(yo[idx], preds[("order", "six")][idx])
                    an = roc_auc_score(yo[idx], preds[("order", "six+new")][idx])
                    extra = f"   AUC six {a6:.4f} -> six+new {an:.4f}"
                print(f"  {tgt:<7}{hn:<9} skill six {s6:+.3f}%  six+new {sn:+.3f}%  diff "
                      f"{sn-s6:+.3f} [{lo:+.3f}, {hi:+.3f}]{'  BETTER' if lo > 0 else '  WORSE' if hi < 0 else ''}{extra}")
                if hn in ("HO1", "HO2"):
                    ok_halves.append(lo > 0)
            passB[tgt] = all(ok_halves)
        print()
        print("  ORDER calibration by decile of predicted probability (held out): mean predicted / observed")
        for nm in sets:
            p_ = preds[("order", nm)]
            g = np.clip(np.searchsorted(np.quantile(p_, np.linspace(0, 1, 11)[1:-1]), p_, side="right"), 0, 9)
            print(f"    {nm:<8} " + "  ".join(f"d{k+1} {p_[g == k].mean():.3f}/{yo[g == k].mean():.3f}"
                                             for k in range(10)))
        print()
        print("  PERMUTATION IMPORTANCE of each new feature in the six+new models (held out, "
              f"{N_SHUF} shuffles, skill points, day-clustered 95%)")
        Zte = Z["six+new"][sp.test]
        nb = SIX.shape[1]
        mt, mo = mods[("timing", "six+new")], mods[("order", "six+new")]
        base_t = tl["six+new"]
        base_o = ol["six+new"]
        print(f"    {'feature':<26}{'timing':>32}{'order':>32}{'':>4}")
        for j, nm in enumerate(names):
            acc_t = np.zeros(len(yt))
            acc_o = np.zeros(len(yt))
            for _ in range(N_SHUF):
                Zp = Zte.copy()
                Zp[:, nb + j] = Zte[rng.permutation(len(yt)), nb + j]
                pt = np.maximum.accumulate(np.column_stack([m_.predict(Zp) for m_ in mt]), axis=1)
                acc_t += t_rows(pt) - base_t
                acc_o += ll(yo, mo.predict_proba(Zp)[:, 1]) - base_o
            cells = []
            for acc, LC_ in ((acc_t, tc), (acc_o, oc)):
                d_ = acc / N_SHUF
                ptv = 100.0 * d_.mean() / LC_.mean()
                dr = [100.0 * d_[ix].mean() / LC_[ix].mean() for ix in bfull]
                lo, hi = np.percentile(dr, [2.5, 97.5])
                cells.append(f"{ptv:+.4f} [{lo:+.4f},{hi:+.4f}]")
            print(f"    {nm:<26}{cells[0]:>32}{cells[1]:>32}"
                  f"{'   RESTATES VOLATILITY' if nm in restates else ''}")
        print()
        print(f"  SCREEN B: timing {'PASSES' if passB['timing'] else 'does not pass'} "
              f"(HO1 and HO2 both clear);  order {'PASSES' if passB['order'] else 'does not pass'}  "
              f"-> {'PASS: earns a separate trading test later, not a result' if any(passB.values()) else 'NO PASS'}")
        print("  depth (= 10h MFE): see screen A, MFE 10h cells")
        print(f"  [{time.time()-t0:.0f}s]")
        print()

    # ================= SCREEN A =================
    print("=" * 120)
    print("SCREEN A -- the envelope: Linear QR and CQR refitted on baseline + 20 new columns")
    print("=" * 120)
    T30, _ = build_targets_30m(Y[rows])
    Xm = X5[rows].copy()
    Xa = X5[rows].copy()
    Xa[:, 0] = v48["vol_48_1m"]
    caches = {"MFE": np.load(paths.envelope_preds("match1m"), allow_pickle=False),
              "MAE": np.load(paths.envelope_preds(MAE_CACHE), allow_pickle=False)}
    fps = {"MFE": cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), Xm),
           "MAE": cache_fingerprint([rows], flat_targets(
               {("MAE", k): T1M[("MAE", k)] for k in HORIZONS}), Xa)}
    res = {}
    for d, Xb in (("MFE", Xm), ("MAE", Xa)):
        cb = caches[d]
        if str(cb[FP_KEY]) != fps[d]:
            raise SystemExit(f"[WHYS] {d} cache fingerprint mismatch.")
        ctx = build_context(np.ones(len(rows), bool), np.column_stack([Xb, XN]), day, e,
                            verbose=False)
        bt = day_boot(ctx["day_test"])
        for mn, fn in (("Linear QR", fit_linear), ("CQR", fit_cqr)):
            raw = []
            for k in HORIZONS:
                raw.append(fn(ctx, T1M[(d, k)], f"1m/{d}/{HLABEL[k]}/why"))
                print(f"    fitted {mn} {d} {HLABEL[k]}   [{time.time()-t0:.0f}s]", flush=True)
            enf, _, _ = enforce_two_pass(np.stack(raw))
            for i, k in enumerate(HORIZONS):
                y = T1M[(d, k)][ctx["test"]]
                old, clim = cb[f"1m|{d}|{mn}|{k}"], cb[f"1m|{d}|Climatology|{k}"]
                new = enf[i]
                ds = paired_skill_ci(y, old, new, clim, bt)
                dg = gap_paired_ci(y, old, y, new, bt)
                s_t = "better" if ds[1] > 0 else "WORSE" if ds[2] < 0 else ""
                g_t = "better" if dg[2] < 0 else "WORSE" if dg[1] > 0 else ""
                oc_ = ("LOSES" if "WORSE" in (s_t, g_t)
                       else "IMPROVES" if "better" in (s_t, g_t) else "HOLDS")
                po, pn, pc = _pinball_rows(y, old), _pinball_rows(y, new), _pinball_rows(y, clim)
                draws = np.array([100.0 * (po[ix].mean() - pn[ix].mean()) / pc[ix].mean() for ix in bt])
                res[(d, mn, k)] = dict(so=skill_ci(y, old, clim, bt)[0], sn=skill_ci(y, new, clim, bt)[0],
                                       go=gap_ci(y, old, bt)[0], gn=gap_ci(y, new, bt)[0],
                                       ds=ds, dg=dg, s_t=s_t, g_t=g_t, oc=oc_, draws=draws)
    print()
    print("  paired vs each model's cached registry prediction -- skill: + helps; gap: - better")
    print(f"  {'cell':<20}{'skill base':>11}{'+why':>8}{'diff':>9}{'[95% CI]':>19}{'':>8}"
          f"{'gap base':>9}{'+why':>7}{'diff':>9}{'[95% CI]':>19}{'':>8}{'outcome':>10}")
    for (d, mn, k), r in res.items():
        ds, dg = r["ds"], r["dg"]
        print(f"  {d+' '+mn+' '+HLABEL[k]:<20}{r['so']:>+11.2f}{r['sn']:>+8.2f}{ds[0]:>+9.3f}"
              f"{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>19}{r['s_t']:>8}{r['go']:>9.2f}{r['gn']:>7.2f}"
              f"{dg[0]:>+9.3f}{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>19}{r['g_t']:>8}{r['oc']:>10}")
    print()
    print("  ADOPTION -- the market-vol rule, unchanged (10 cells per direction, majority 6)")
    for d in ("MFE", "MAE"):
        cs = [r for (dd, _, _), r in res.items() if dd == d]
        nimp = sum(r["oc"] == "IMPROVES" for r in cs)
        nloss = sum(r["oc"] == "LOSES" for r in cs)
        print(f"    {d}: IMPROVES {nimp} of 10, confirmed harm {nloss} -> "
              f"{'CLEARS' if nloss == 0 and nimp >= 6 else 'does not clear'}")
    print("  PER-MODEL ADOPTION -- no horizon significantly worse AND the five-horizon mean skill")
    print("  gain's interval above zero")
    for d in ("MFE", "MAE"):
        for mn in ("Linear QR", "CQR"):
            cs = [res[(d, mn, k)] for k in HORIZONS]
            harm = [HLABEL[k] for k, r in zip(HORIZONS, cs) if "WORSE" in (r["s_t"], r["g_t"])]
            nd = np.mean(np.vstack([r["draws"] for r in cs]), axis=0)
            net = float(np.mean([r["ds"][0] for r in cs]))
            lo, hi = np.percentile(nd, [2.5, 97.5])
            ok = not harm and lo > 0
            print(f"    {d} {mn:<10} harm at: {', '.join(harm) if harm else 'none'};  mean skill gain "
                  f"{net:+.3f} [{lo:+.3f}, {hi:+.3f}] -> {'ADOPT' if ok else 'do not adopt'}")
    print()
    print(f"  Restates volatility (reported whatever the screens say): "
          f"{', '.join(sorted(restates)) if restates else 'none'}")
    print("  Nothing in the registry or live system was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 120)


if __name__ == "__main__":
    main(skip_b="--skip-b" in sys.argv)
