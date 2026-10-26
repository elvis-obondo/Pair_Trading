"""WHY-IT-MOVED, three checks on screen A's MFE gain, before any registry rebuild.

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/whycheck.py > research/dislocation_model/logs/whycheck.log 2>&1

MFE only; Linear QR and CQR; all five horizons. Same population (the matched
53,757), harness.Split unchanged (train < 2026-05-01, val for iteration count,
CQR calibration and -- here -- choosing the subset, never scored; held out
>= 2026-07-18), HO1/HO2 split at 2026-08-26, 1-minute targets, the same log
transforms and train-median fill (whyscreen.why_columns, one definition), the
same paired day-clustered method. Nothing is written to the registry or any
cache. MAE is not touched.

BASELINE, a gap in the brief filled before the run. The brief says "six" and
"six plus twenty". For MFE, screen A's baseline was the cached registry
prediction, fitted on the FIVE envelope features (vol_48, vratio, vol_slope,
sandwich, off_mark; cache envelope_preds_match1m.npz, fingerprint checked),
and its "+why" model was those five plus the 20. vol_48_1m is the MAE
registry's column, not MFE's. So "six" here means the MFE registry baseline,
the five, and "six plus twenty" means the 25-column model screen A scored.
Adding vol_48_1m would change the baseline and break the pairing with the
cache. Written "base" and "base+20" below.

GATE 0 -- REPRODUCTION. The base+20 refit must reproduce screen A's ten MFE
held-out skill differences and gap differences (logs/whyscreen.log) to the
printed precision, 0.0005. If any cell misses, STOP: the checks would not be
about screen A's gain.

GROUPS (fixed now). Near-duplicates share a group so each group gets its full
credit: a feature's 4-bar and 12-bar versions (2h and 6h), and each 1-minute
feature with its 30-minute twin (the 1-minute versions are at 4 and 12
MINUTES). Seven groups:
  lone_share (2), common_share (2), mkt_move (2), lagger_spread (2),
  vol_spike_mover (4), vol_spike_ratio (4), vadj_resid (4).

CHECK 1 -- GROUPED PERMUTATION IMPORTANCE in the base+20 models. For each
group, 20 shuffles: one row permutation applied to all the group's columns
together (their joint distribution kept), all five horizons re-predicted with
the fitted model, two-pass enforced as the scored predictions are, per-row
pinball recomputed. Importance = skill points lost = 100 x mean(pinball
increase) / mean(climatology pinball), climatology = train quantiles. Both
models face the same shuffles. Day-clustered 95% intervals. Reported per
horizon and as the five-horizon mean, on VAL (used to choose) and on HELD OUT
(used to judge). CQR's val importance is measured on the rows that set its
conformal widths and median shift; that leak raises its val skill level, not
the drop a shuffle causes, and val is still never scored.

CHECK 2 -- DOES THE GAIN HOLD. base+20 minus base, skill and calibration gap,
paired, day-clustered within each half, for HO1 and HO2 separately, every
horizon, both models. Full held-out shown beside as the reproduction.

CHECK 3 -- A SMALLER SET.
  SUBSET RULE (the brief's, fixed): keep the groups whose VALIDATION importance
  interval clears zero. Gap filled: importance is measured per horizon, so the
  interval used is the FIVE-HORIZON MEAN's, as in the per-model adoption rule;
  the subset is chosen PER MODEL. If no group clears for a model, its subset is
  empty and base+subset is base: the replacement rule is still applied, read
  off check 2's held-out base+20-minus-base cells; if all seven clear,
  base+subset is base+20 and is not refitted. Held-out never chooses.
  Refit base+subset; report held-out skill and gap against base+20 and against
  base, paired, plus HO1 and HO2.

READING RULES (the brief's, gaps filled before the run):
  SUBSET REPLACES THE FULL TWENTY, per model, if at NO horizon is base+subset
  significantly worse than base+20 on the full held out: skill difference's
  interval entirely below zero, or gap difference's interval entirely above
  zero. Gap filled: "worse" covers calibration as well as skill, because the
  registry is judged on both.
  THE GAIN IS REAL only if it is positive in BOTH HO1 and HO2 at three or more
  horizons for at least one model. Gap filled: "positive" means the paired
  skill difference's day-clustered interval lies above zero in that half, the
  project's standing reading (screen B's rule). The count with point estimates
  above zero is printed beside it, not used.
"""
import copy
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

import harness
import paths
from envelope import (CQR_PAIRS, FP_KEY, HLABEL, HORIZONS, HO_BOUNDARY, MEDIAN_IX,
                      QUANTILES, _pinball, _pinball_rows, apply_cqr, build_context,
                      build_targets_1m, build_targets_30m, cache_fingerprint,
                      conformal_width, day_boot, enforce_two_pass, fit_cqr, fit_linear,
                      flat_targets, gap_ci, gap_paired_ci, scan_1m_coverage,
                      select_1m_subset, skill_ci)
from vol1m import paired_skill_ci
from whyscreen import why_columns

N_SHUF = 20
SEED = 20261013
MODELS = ("Linear QR", "CQR")
# Screen A's MFE cells, logs/whyscreen.log lines 148-157: (skill diff, gap diff).
SCREEN_A = {
    ("Linear QR", 1): (+1.346, +0.200), ("Linear QR", 2): (+1.270, -0.383),
    ("Linear QR", 4): (+1.053, -0.653), ("Linear QR", 10): (+0.575, -0.754),
    ("Linear QR", 20): (+0.269, -0.618),
    ("CQR", 1): (+1.300, +0.143), ("CQR", 2): (+1.175, -0.210),
    ("CQR", 4): (+1.342, -0.574), ("CQR", 10): (+0.552, -0.513),
    ("CQR", 20): (+0.471, -0.331),
}


def group_of(nm):
    b = nm.rsplit("_", 1)[0]
    return b[:-3] if b.endswith("_1m") else b


def fit_model(mn, ctx, y, tag):
    """Fit one cell; return (val raw, test raw, predict(block_matrix) -> raw).

    The predictor takes the model's own input space: standardised Z for
    Linear QR, raw X for CQR (its QTREE runs on raw features). Each predictor
    is asserted to reproduce the fitter's held-out output exactly.
    """
    if mn == "Linear QR":
        ms = []
        te = fit_linear(ctx, y, tag, models=ms)

        def pred(Z):
            return np.column_stack([m.predict(Z) for _, m in ms])
        if not np.array_equal(pred(ctx["Zte"]), te):
            raise SystemExit(f"[WHYC] {tag}: Linear QR predictor does not reproduce fit_linear.")
        return pred(ctx["Zva"]), te, pred
    # CQR: fit_cqr's own steps, keeping the QTREE models at their val-chosen size.
    ytr, yva = y[ctx["train"]], y[ctx["val"]]
    trunc = []
    for q in QUANTILES:
        m = HistGradientBoostingRegressor(loss="quantile", quantile=q,
                                          random_state=0, **harness.TREE)
        m.fit(ctx["Xtr"], ytr)
        sv = list(m.staged_predict(ctx["Xva"]))
        best = int(np.argmin([_pinball(yva, p, q) for p in sv]))
        mt = copy.copy(m)
        mt._predictors = m._predictors[:best + 1]
        if not np.array_equal(mt.predict(ctx["Xva"]), sv[best]):
            raise SystemExit(f"[WHYC] {tag}: truncated QTREE differs from staged_predict.")
        trunc.append(mt)

    def qt(X):
        return np.maximum.accumulate(np.column_stack([m.predict(X) for m in trunc]), axis=1)
    va = qt(ctx["Xva"])
    widths = [conformal_width(yva, va[:, jl], va[:, jh], a)[0] for jl, jh, a in CQR_PAIRS]
    shift = float(np.median(yva - va[:, MEDIAN_IX]))

    def pred(X):
        return apply_cqr(qt(X), widths, shift)[0]
    te = pred(ctx["Xte"])
    if not np.array_equal(te, fit_cqr(ctx, y, tag)):
        raise SystemExit(f"[WHYC] {tag}: CQR reconstruction does not reproduce fit_cqr.")
    return pred(ctx["Xva"]), te, pred


def fit_set(ctx, T1M, label, t0):
    """Both models, five horizons, two-pass enforced on val and held out."""
    out = {}
    for mn in MODELS:
        va_raw, te_raw, preds = [], [], []
        for k in HORIZONS:
            va, te, p = fit_model(mn, ctx, T1M[("MFE", k)], f"1m/MFE/{HLABEL[k]}/{label}")
            va_raw.append(va)
            te_raw.append(te)
            preds.append(p)
            print(f"    fitted {mn} MFE {HLABEL[k]} on {label}   [{time.time()-t0:.0f}s]", flush=True)
        out[mn] = dict(va=enforce_two_pass(np.stack(va_raw))[0],
                       te=enforce_two_pass(np.stack(te_raw))[0], preds=preds)
    return out


def ci(draws):
    return np.percentile(draws, [2.5, 97.5])


def flag_skill(lo, hi):
    return "better" if lo > 0 else "WORSE" if hi < 0 else ""


def flag_gap(lo, hi):
    return "better" if hi < 0 else "WORSE" if lo > 0 else ""


def main():
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    X5 = np.load(paths.ENVFEAT, allow_pickle=False)["X"].astype(np.float64)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    W = np.load(os.path.join(paths.DATASETS, "whyfeat.npz"), allow_pickle=False)
    if not ((W["ticker_a"] == meta.ticker_a.to_numpy(str)).all()
            and (W["entry_time"] == pd.to_datetime(meta.entry_time).to_numpy("datetime64[ns]")).all()):
        raise SystemExit("[WHYC] whyfeat.npz is not aligned to disloc_meta.")
    names = [str(x) for x in W["names"]]
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    sp = harness.Split(day, e)
    XN, _, _, _, _, _ = why_columns(W["X"][rows], names, sp.train)
    Xm = X5[rows].copy()
    groups = {}
    for j, nm in enumerate(names):
        groups.setdefault(group_of(nm), []).append(j)
    G = list(groups)

    print("=" * 120)
    print("WHY-IT-MOVED -- three checks on screen A's MFE gain (MFE only; Linear QR and CQR)")
    print("=" * 120)
    print(f"  {sp.describe()}")
    print("  base = the MFE registry's five features (cached predictions); base+20 = screen A's model")
    print(f"  groups ({len(G)}): " + ";  ".join(f"{g} = {', '.join(names[j] for j in groups[g])}"
                                               for g in G))
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    cache = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    fp = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), Xm)
    if str(cache[FP_KEY]) != fp:
        raise SystemExit("[WHYC] MFE cache fingerprint mismatch.")
    print(f"  MFE cache fingerprint {fp} matches")
    print()

    ctx = build_context(np.ones(len(rows), bool), np.column_stack([Xm, XN]), day, e, verbose=False)
    nb = Xm.shape[1]
    yte = {k: T1M[("MFE", k)][ctx["test"]] for k in HORIZONS}
    yva = {k: T1M[("MFE", k)][ctx["val"]] for k in HORIZONS}
    base = {(mn, k): cache[f"1m|MFE|{mn}|{k}"] for mn in MODELS for k in HORIZONS}
    clim_te = {k: cache[f"1m|MFE|Climatology|{k}"] for k in HORIZONS}
    clim_va = {k: np.tile(np.quantile(T1M[("MFE", k)][ctx["train"]], QUANTILES),
                          (int(ctx["val"].sum()), 1)) for k in HORIZONS}
    dte = ctx["day_test"]
    dva = day[ctx["val"]]
    h1 = dte < HO_BOUNDARY
    idx = {"held out": np.arange(len(dte)), "HO1": np.flatnonzero(h1), "HO2": np.flatnonzero(~h1)}
    bt = {"held out": day_boot(dte), "HO1": day_boot(dte[h1]), "HO2": day_boot(dte[~h1])}
    bt_va = day_boot(dva)

    print("FITTING base+20 (screen A's model)")
    full = fit_set(ctx, T1M, "why", t0)
    print()

    # ---------------- GATE 0 -- reproduction ----------------
    print("=" * 120)
    print("GATE 0 -- base+20 reproduces screen A (held out, paired vs cache; tolerance 0.0005)")
    print("=" * 120)
    bad = []
    for mn in MODELS:
        for i, k in enumerate(HORIZONS):
            y, old, new = yte[k], base[(mn, k)], full[mn]["te"][i]
            ds = paired_skill_ci(y, old, new, clim_te[k], bt["held out"])[0]
            dg = gap_paired_ci(y, old, y, new, bt["held out"])[0]
            ref = SCREEN_A[(mn, k)]
            ok = abs(ds - ref[0]) <= 0.0005 and abs(dg - ref[1]) <= 0.0005
            print(f"  {mn:<10}{HLABEL[k]:>4}  skill diff {ds:+.4f} (screen A {ref[0]:+.3f})  "
                  f"gap diff {dg:+.4f} (screen A {ref[1]:+.3f})  {'ok' if ok else 'MISMATCH'}")
            if not ok:
                bad.append((mn, k))
    if bad:
        raise SystemExit(f"[WHYC] STOP -- gate 0 failed at {bad}: not screen A's gain.")
    print("  GATE 0 PASSES: all 10 cells reproduce screen A")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---------------- CHECK 2 -- halves ----------------
    print("=" * 120)
    print("CHECK 2 -- base+20 minus base, by half (paired, day-clustered 95%; skill: + helps; gap: - better)")
    print("=" * 120)
    real_ci, real_pt, base_worse = {}, {}, {}
    for mn in MODELS:
        real_ci[mn], real_pt[mn], base_worse[mn] = 0, 0, []
        for i, k in enumerate(HORIZONS):
            both_ci, both_pt = True, True
            for hn in ("held out", "HO1", "HO2"):
                ix = idx[hn]
                y, old, new, c = yte[k][ix], base[(mn, k)][ix], full[mn]["te"][i][ix], clim_te[k][ix]
                so = skill_ci(y, old, c, bt[hn])[0]
                sn = skill_ci(y, new, c, bt[hn])[0]
                ds = paired_skill_ci(y, old, new, c, bt[hn])
                go, gn = gap_ci(y, old, bt[hn])[0], gap_ci(y, new, bt[hn])[0]
                dg = gap_paired_ci(y, old, y, new, bt[hn])
                print(f"  {mn:<10}{HLABEL[k]:>4} {hn:<9} n {len(ix):>6,}  skill {so:+.2f} -> {sn:+.2f}  "
                      f"diff {ds[0]:+.3f} [{ds[1]:+.3f}, {ds[2]:+.3f}] {flag_skill(ds[1], ds[2]):<7}"
                      f"  gap {go:.2f} -> {gn:.2f}  diff {dg[0]:+.3f} [{dg[1]:+.3f}, {dg[2]:+.3f}] "
                      f"{flag_gap(dg[1], dg[2])}")
                if hn == "held out" and (ds[1] > 0 or dg[2] < 0):
                    base_worse[mn].append(HLABEL[k])     # base significantly worse than base+20
                if hn != "held out":
                    both_ci &= ds[1] > 0
                    both_pt &= ds[0] > 0
            real_ci[mn] += both_ci
            real_pt[mn] += both_pt
    print()
    for mn in MODELS:
        print(f"  {mn:<10} horizons with the skill gain's interval above zero in BOTH HO1 and HO2: "
              f"{real_ci[mn]} of 5   (point estimate above zero in both, not used: {real_pt[mn]} of 5)")
    is_real = any(real_ci[mn] >= 3 for mn in MODELS)
    print(f"  READING RULE -- the gain is real: {'YES' if is_real else 'NO'} "
          f"(needs 3+ horizons in both halves for at least one model)")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---------------- CHECK 1 -- grouped permutation importance ----------------
    print("=" * 120)
    print(f"CHECK 1 -- grouped permutation importance in base+20, {N_SHUF} shuffles, skill points lost "
          "(+ = the group matters), day-clustered 95%")
    print("=" * 120)
    blocks = {"val": dict(Z=ctx["Zva"], X=ctx["Xva"], y=yva, clim=clim_va, bt=bt_va, key="va"),
              "held out": dict(Z=ctx["Zte"], X=ctx["Xte"], y=yte, clim=clim_te, bt=bt["held out"], key="te")}
    imp = {}
    for bn, B in blocks.items():
        n = len(B["y"][HORIZONS[0]])
        for mn in MODELS:
            M = B["Z"] if mn == "Linear QR" else B["X"]
            base_pin = {k: _pinball_rows(B["y"][k], full[mn][B["key"]][i]) for i, k in enumerate(HORIZONS)}
            for gi, g in enumerate(G):
                cols = [nb + j for j in groups[g]]
                acc = {k: np.zeros(n) for k in HORIZONS}
                for s in range(N_SHUF):
                    perm = np.random.default_rng([SEED, 0 if bn == "val" else 1, gi, s]).permutation(n)
                    Mp = M.copy()
                    Mp[:, cols] = M[perm][:, cols]
                    stack = enforce_two_pass(np.stack([p(Mp) for p in full[mn]["preds"]]))[0]
                    for i, k in enumerate(HORIZONS):
                        acc[k] += _pinball_rows(B["y"][k], stack[i]) - base_pin[k]
                pc = {k: _pinball_rows(B["y"][k], B["clim"][k]) for k in HORIZONS}
                draws = np.array([[100.0 * acc[k][ix].mean() / N_SHUF / pc[k][ix].mean() for k in HORIZONS]
                                  for ix in B["bt"]])
                pts = [100.0 * acc[k].mean() / N_SHUF / pc[k].mean() for k in HORIZONS]
                imp[(bn, mn, g)] = dict(pts=pts, cis=[ci(draws[:, i]) for i in range(len(HORIZONS))],
                                        mean=float(np.mean(pts)), mean_ci=ci(draws.mean(1)))
            print(f"    importance done: {bn} / {mn}   [{time.time()-t0:.0f}s]", flush=True)
    for bn in blocks:
        for mn in MODELS:
            print()
            print(f"  {mn} -- {bn.upper()}")
            print(f"    {'group':<17}{'cols':>5}" + "".join(f"{HLABEL[k]:>24}" for k in HORIZONS)
                  + f"{'five-horizon mean':>28}")
            for g in G:
                r = imp[(bn, mn, g)]
                cells = "".join(f"{f'{p:+.3f} [{c[0]:+.3f},{c[1]:+.3f}]':>24}" for p, c in zip(r["pts"], r["cis"]))
                mc, mv = r["mean_ci"], r["mean"]
                print(f"    {g:<17}{len(groups[g]):>5}{cells}{f'{mv:+.3f} [{mc[0]:+.3f},{mc[1]:+.3f}]':>28}"
                      f"{'  clears' if mc[0] > 0 else ''}")
    print()

    # ---------------- CHECK 3 -- the subset ----------------
    print("=" * 120)
    print("CHECK 3 -- base+subset; subset = groups whose VAL five-horizon-mean importance interval clears zero")
    print("=" * 120)
    subsets = {mn: [g for g in G if imp[("val", mn, g)]["mean_ci"][0] > 0] for mn in MODELS}
    replaces = {}
    for mn in MODELS:
        sub = subsets[mn]
        cols = sorted(j for g in sub for j in groups[g])
        print(f"  {mn}: subset = {', '.join(sub) if sub else '(none)'}  ({len(cols)} of 20 columns)")
        if not sub:
            replaces[mn] = not base_worse[mn]
            print("    no group clears on val: base+subset is base, compared with base+20 in check 2")
            print(f"  READING RULE -- {mn}: base significantly worse than base+20 (check 2, held out) at: "
                  f"{', '.join(base_worse[mn]) if base_worse[mn] else 'none'} -> subset (empty) "
                  f"{'REPLACES the full twenty' if replaces[mn] else 'does NOT replace the full twenty'}")
            print()
            continue
        if len(sub) == len(G):
            print("    all seven groups clear: base+subset is base+20; nothing to refit")
            replaces[mn] = None
            continue
        cs = build_context(np.ones(len(rows), bool), np.column_stack([Xm, XN[:, cols]]), day, e, verbose=False)
        te_raw = []
        for k in HORIZONS:
            te_raw.append(fit_model(mn, cs, T1M[("MFE", k)], f"1m/MFE/{HLABEL[k]}/whysub")[1])
            print(f"    fitted {mn} MFE {HLABEL[k]} on base+subset   [{time.time()-t0:.0f}s]", flush=True)
        subp = enforce_two_pass(np.stack(te_raw))[0]
        worse_at = []
        for i, k in enumerate(HORIZONS):
            for hn in ("held out", "HO1", "HO2"):
                ix = idx[hn]
                y, c = yte[k][ix], clim_te[k][ix]
                s_ = subp[i][ix]
                for vs, ref in (("base+20", full[mn]["te"][i][ix]), ("base", base[(mn, k)][ix])):
                    ds = paired_skill_ci(y, ref, s_, c, bt[hn])
                    dg = gap_paired_ci(y, ref, y, s_, bt[hn])
                    print(f"    {HLABEL[k]:>4} {hn:<9} subset minus {vs:<8} skill {ds[0]:+.3f} "
                          f"[{ds[1]:+.3f}, {ds[2]:+.3f}] {flag_skill(ds[1], ds[2]):<7}  gap {dg[0]:+.3f} "
                          f"[{dg[1]:+.3f}, {dg[2]:+.3f}] {flag_gap(dg[1], dg[2])}")
                    if hn == "held out" and vs == "base+20" and (ds[2] < 0 or dg[1] > 0):
                        worse_at.append(HLABEL[k])
        replaces[mn] = not worse_at
        print(f"  READING RULE -- {mn}: base+subset significantly worse than base+20 at: "
              f"{', '.join(worse_at) if worse_at else 'none'} -> subset "
              f"{'REPLACES the full twenty' if replaces[mn] else 'does NOT replace the full twenty'}")
        print()

    print("=" * 120)
    print("SUMMARY")
    print(f"  check 2: gain real (3+ horizons, interval above zero in both halves, one model): "
          f"{'YES' if is_real else 'NO'}  -- Linear QR {real_ci['Linear QR']}/5, CQR {real_ci['CQR']}/5; "
          f"carried by: {', '.join(mn for mn in MODELS if real_ci[mn] >= 3) or 'neither'}")
    for mn in MODELS:
        r = replaces[mn]
        print(f"  check 3: {mn}: subset {subsets[mn] or '(none)'} -> "
              f"{'identical to base+20' if r is None else 'REPLACES' if r else 'does not replace'}")
    print("  Nothing was written to the registry or any cache. MAE not touched.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 120)


if __name__ == "__main__":
    main()
