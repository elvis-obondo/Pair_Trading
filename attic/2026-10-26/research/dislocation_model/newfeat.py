"""Two new, independent features: hour-of-day and hedge quality. Tested apart.

    .venv/bin/python research/dislocation_model/newfeat.py 2>&1 \
        | tee research/dislocation_model/logs/newfeat.log

WHY THESE TWO. Every feature so far describes the spread's own recent movement.
These do not. Hour-of-day is temporal; r2 and |beta| describe how well the two
legs are paired. They are tested SEPARATELY so a pass can be attributed.

THE CANDIDATES.
  HOUR-OF-DAY  sin(2 pi h/24), cos(2 pi h/24), two columns, UTC. h is read off
               the entry timestamp (entry_time, the entry bar's OPEN label) as a
               fractional hour, hour + minute/60. Entries sit on :00 and :30, so
               this places 48 points on the circle; an integer hour would fold
               each :30 onto the :00 before it. The timestamp is known before
               the entry bar closes, so there is no look-ahead. The panel's
               timestamps are UTC (data_loader parses with utc=True and drops
               the zone), so the naive entry_time is UTC.
  HEDGE-QUALITY  r2 and |beta|, joined from disloc_meta.parquet. Both come from
               the same rolling_spread_stats call, at the entry bar, over the
               same 96-bar window as the mu, sigma, beta and alpha that freeze
               the entry geometry. Confirmed below by recomputing them from the
               panel for a random sample of episodes.

THE BASELINE IS THE CURRENT REGISTRY, PER DIRECTION. MAE: the five features with
vol_48 -> vol_48_1m, predictions from the match1m_mae_vol1m cache. MFE: the
original five, predictions from the match1m cache. Both fingerprint-checked. A
candidate's columns are ADDED to that baseline; nothing else changes.

THE TEST. QTREE only. Two cells: 1-minute target, ALL, MFE 10h and MAE 10h, the
matched 53,757-episode set, the usual split. New = QTREE refitted on baseline +
candidate, all five horizons, the same two-pass enforcement, scored at 10h.
Skill and calibration gap, compared PAIRED against the cached baseline on
identical held-out rows and day resamples. Levels are a later look at
already-scored rows; the paired differences are the new measurement.

THE RULE, fixed before the run, per candidate. Per cell: IMPROVES if a paired
measure (skill, gap) is significantly better and neither is significantly
worse; LOSES if either is significantly worse; HOLDS otherwise.
  PROPAGATE  neither cell loses and at least one improves
  SPLIT      one cell improves and the other loses -> chase only the winning
             side across the other four horizons, before any registry change
  MARGINAL   no cell improves. Stop and report.
Gap filled in the brief's wording: "both improve or hold -> propagate" and
"neither improves -> marginal" overlap when both cells merely HOLD. That case
is MARGINAL; there is nothing to propagate. Propagation and the horizon chase
are the NEXT builds, not done in this run.

IF A CANDIDATE PASSES (PROPAGATE or SPLIT): permutation importance of the
refitted QTREE in both cells, same units as IMPORTANCE -- skill points against
climatology on the held-out block, 20 shuffles, day-clustered interval, per-
horizon predictions before horizon enforcement. The candidate's columns are
shuffled jointly (the two hour columns are one feature), each column alone, and
every baseline feature alongside, for scale.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
from envelope import (FP_KEY, HLABEL, HORIZONS, build_context, build_targets_1m,
                      build_targets_30m, assert_1m_dominates, cache_fingerprint,
                      day_boot, enforce_two_pass, fit_qtree, flat_targets,
                      gap_ci, gap_paired_ci, scan_1m_coverage, select_1m_subset,
                      skill_ci, _pinball_rows)
from importance import importance, qtree_predict
from vol1m import MAE_CACHE, paired_skill_ci

CELLS = (("MFE", 20), ("MAE", 20))
SEED = 20261011
N_SPOT = 300              # episodes whose r2/beta are recomputed from the panel
SPOT_TOL = 1e-9


def spot_check_geometry(meta, rows, rng):
    """Recompute beta, alpha, mu, sigma and r2 at the entry bar from the panel.

    Same slice convention as mkdisloc.py: the pair's joint finite region,
    rolling_spread_stats over it, read at the entry bar. If r2 matches
    alongside mu/sigma/beta, it is the same entry-time geometry.
    """
    import universe_panel
    import rolling_spread as rs
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    V = panel.to_numpy(float)
    ok = np.isfinite(V)
    first = ok.argmax(axis=0)
    cols = {c: j for j, c in enumerate(panel.columns)}
    pos = pd.Index(panel.index)
    pick = rng.choice(rows, N_SPOT, replace=False)
    worst = {k: 0.0 for k in ("beta", "alpha", "mu", "sigma", "r2")}
    for i in pick:
        r = meta.iloc[i]
        ja, jb = cols[r.ticker_a], cols[r.ticker_b]
        f = max(first[ja], first[jb])
        t = pos.get_loc(pd.Timestamp(r.entry_time))
        st = rs.rolling_spread_stats(V[f:, ja], V[f:, jb], 0.5)
        for k in worst:
            got = float(getattr(st, k)[t - f])
            worst[k] = max(worst[k], abs(got - float(r[k])) / max(1.0, abs(float(r[k]))))
    return worst


def load_baselines(Y, meta, X, names, rows, v48):
    """1-minute targets and the current registry baseline per direction,
    fingerprint-checked: MFE on vol_48 (match1m), MAE on vol_48_1m."""
    iv = names.index("vol_48")
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    c_mfe = np.load(paths.envelope_preds("match1m"), allow_pickle=False)
    c_mae = np.load(paths.envelope_preds(MAE_CACHE), allow_pickle=False)
    X_mfe = X[rows].copy()
    X_mae = X[rows].copy()
    X_mae[:, iv] = v48["vol_48_1m"]
    fp_mfe = cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), X_mfe)
    fp_mae = cache_fingerprint([rows], flat_targets(
        {("MAE", k): T1M[("MAE", k)] for k in HORIZONS}), X_mae)
    if str(c_mfe[FP_KEY]) != fp_mfe or str(c_mae[FP_KEY]) != fp_mae:
        raise SystemExit("[NEWF] a baseline cache fingerprint does not match.")
    print(f"  baselines: MFE match1m {fp_mfe[:12]} (vol_48), MAE {MAE_CACHE} "
          f"{fp_mae[:12]} (vol_48_1m) -- both match")
    print()
    return T1M, {"MFE": (X_mfe, c_mfe, names),
                 "MAE": (X_mae, c_mae,
                         ["vol_48_1m" if n == "vol_48" else n for n in names])}


def cell_outcome(ds, dg):
    """Per-measure tags and the cell outcome, from paired (pt, lo, hi) intervals."""
    s_t = "better" if ds[1] > 0 else "WORSE" if ds[2] < 0 else ""
    g_t = "better" if dg[2] < 0 else "WORSE" if dg[1] > 0 else ""
    oc = ("LOSES" if "WORSE" in (s_t, g_t)
          else "IMPROVES" if "better" in (s_t, g_t) else "HOLDS")
    return s_t, g_t, oc


def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    day = meta.day.to_numpy()

    print("=" * 112)
    print("NEW FEATURES -- hour-of-day and hedge quality, tested separately")
    print("=" * 112)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], rows):
        raise SystemExit("[NEWF] vol48_1m.npz rows differ from the population.")
    print(f"  population: the matched {len(rows):,}-episode set")
    print()

    # ---- build ----
    print("=" * 112)
    print("BUILD -- with checks")
    print("=" * 112)
    et = pd.to_datetime(meta.entry_time.iloc[rows])
    mins = np.unique(et.dt.minute.to_numpy())
    h = et.dt.hour.to_numpy() + et.dt.minute.to_numpy() / 60.0
    hs, hc = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    unit = float(np.max(np.abs(hs ** 2 + hc ** 2 - 1)))
    print(f"  HOUR   entry minutes present: {sorted(int(m) for m in mins)};  "
          f"distinct hours {len(np.unique(h))};  max |sin^2+cos^2-1| {unit:.3e}")
    if unit > 1e-12:
        raise SystemExit("[NEWF] the hour encoding is not on the unit circle.")
    hcount = np.bincount(et.dt.hour.to_numpy(), minlength=24)
    print(f"         episodes per UTC hour: min {hcount.min():,}, max {hcount.max():,}")
    r2 = meta.r2.to_numpy(float)[rows]
    ab = np.abs(meta.beta.to_numpy(float)[rows])
    for nm, v in (("r2", r2), ("|beta|", ab)):
        print(f"  {nm:<6} NaN {int(np.isnan(v).sum())}, non-finite "
              f"{int((~np.isfinite(v)).sum())};  min {np.nanmin(v):.4f}  median "
              f"{np.nanmedian(v):.4f}  max {np.nanmax(v):.4f}")
    if not (np.isfinite(r2).all() and np.isfinite(ab).all()):
        raise SystemExit("[NEWF] r2 or |beta| has a non-finite value in the population.")
    if r2.min() < -1e-12 or r2.max() > 1 + 1e-12:
        raise SystemExit("[NEWF] r2 outside [0, 1].")
    print(f"  Spearman(r2, |beta|) = "
          f"{pd.Series(r2).corr(pd.Series(ab), method='spearman'):.4f}")
    worst = spot_check_geometry(meta, rows, rng)
    print(f"  GEOMETRY  {N_SPOT} random episodes recomputed from the panel at the entry "
          f"bar (rolling_spread_stats, 96-bar window), max relative diff:")
    print("            " + "  ".join(f"{k} {v:.2e}" for k, v in worst.items()))
    if max(worst.values()) > SPOT_TOL:
        raise SystemExit("[NEWF] stored geometry does not reproduce from the panel.")
    print("            r2 reproduces with beta, alpha, mu and sigma: the same frozen "
          "entry-time geometry.")
    np.savez_compressed(os.path.join(paths.DATASETS, "newfeat.npz"), rows=rows,
                        hour_sin=hs, hour_cos=hc, r2=r2, abs_beta=ab)
    print("  [WROTE] research/datasets/newfeat.npz")
    print()

    t0 = time.time()
    Y, rows, day, T1M, base, nf = load_reused(
        "WIDER SCREEN -- hour-of-day and hedge quality at 1h / 5h / 10h, 12 cells")

    cands = (("HOUR-OF-DAY", ["hour_sin", "hour_cos"], np.column_stack([hs, hc])),
             ("HEDGE-QUALITY", ["r2", "abs_beta"], np.column_stack([r2, ab])))
    verdicts = {}
    for tag, cnames, C in cands:
        print("=" * 112)
        print(f"{tag} -- baseline + {' + '.join(cnames)}, QTREE, 10h, paired on "
              f"identical rows")
        print("=" * 112)
        res, outcome, fitted = {}, {}, {}
        for d, k in CELLS:
            Xb, cb, bnames = base[d]
            Xn = np.column_stack([Xb, C])
            ctx = build_context(np.ones(len(rows), bool), Xn, day[rows], Y[rows, 0],
                                verbose=(d == "MFE" and tag == cands[0][0]))
            boot = day_boot(ctx["day_test"])
            tes, qm = [], None
            for kk in HORIZONS:
                ms = [] if kk == k else None
                tes.append(fit_qtree(ctx, T1M[(d, kk)], models=ms))
                if kk == k:
                    qm = ms
            enf, _, _ = enforce_two_pass(np.stack(tes))
            new = enf[HORIZONS.index(k)]
            y = T1M[(d, k)][ctx["test"]]
            old = cb[f"1m|{d}|QTREE|{k}"]
            clim = cb[f"1m|{d}|Climatology|{k}"]
            res[d] = dict(so=skill_ci(y, old, clim, boot)[0],
                          sn=skill_ci(y, new, clim, boot)[0],
                          ds=paired_skill_ci(y, old, new, clim, boot),
                          go=gap_ci(y, old, boot)[0], gn=gap_ci(y, new, boot)[0],
                          dg=gap_paired_ci(y, old, y, new, boot))
            fitted[d] = (ctx, qm, y, _pinball_rows(y, clim), boot, bnames + cnames)
            print(f"  refitted QTREE {d}, five horizons   [{time.time()-t0:.0f}s]",
                  flush=True)
        print()
        print("  skill: + = candidate helps.  gap: - = better calibrated.")
        print(f"  {'cell':<10}{'measure':<9}{'base':>8}{'+cand':>8}{'new - old':>11}"
              f"{'[95% CI]':>18}{'':>9}{'cell':>10}")
        for d, k in CELLS:
            r = res[d]
            ds, dg = r["ds"], r["dg"]
            s_t, g_t, oc = cell_outcome(ds, dg)
            outcome[d] = oc
            print(f"  {d+' 10h':<10}{'skill %':<9}{r['so']:>+8.2f}{r['sn']:>+8.2f}"
                  f"{ds[0]:>+11.3f}{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{s_t:>9}{oc:>10}")
            print(f"  {'':<10}{'gap pp':<9}{r['go']:>8.2f}{r['gn']:>8.2f}"
                  f"{dg[0]:>+11.3f}{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{g_t:>9}")
        print()
        oc = list(outcome.values())
        if "IMPROVES" not in oc:
            v = "MARGINAL"
            msg = "No cell improves. Stop; not propagated."
        elif "LOSES" not in oc:
            v = "PROPAGATE"
            msg = "Neither cell loses and at least one improves. Registry rebuild is the next build."
        else:
            win = [d for d in outcome if outcome[d] == "IMPROVES"][0]
            v = "SPLIT"
            msg = (f"{win} improves, the other loses. Next: chase {win} across the "
                   f"other four horizons. Not done in this run.")
        verdicts[tag] = v
        print(f"  VERDICT {tag}: MFE {outcome['MFE']}, MAE {outcome['MAE']} -> {v}. {msg}")
        print()

        if v == "MARGINAL":
            continue
        print(f"  IMPORTANCE -- refitted QTREE with {tag}, skill points vs climatology,")
        print(f"  held out, {20} shuffles, day-clustered 95% interval, pre-horizon-enforcement.")
        for d, k in CELLS:
            ctx, qm, y, pc, boot, allnames = fitted[d]
            pred = lambda Xp: qtree_predict(qm, Xp)
            sk = 100 * (1 - _pinball_rows(y, pred(ctx["Xte"])).mean() / pc.mean())
            print(f"  {d} 10h  (refit skill {sk:+.2f}%, pre-horizon-enforcement)")
            nb = len(allnames) - len(cnames)
            rowsets = [(n, [j]) for j, n in enumerate(allnames)]
            rowsets.append((f"{tag} jointly", list(range(nb, len(allnames)))))
            for n, cols_ in rowsets:
                p_, lo, hi = importance(pred, ctx["Xte"], cols_, y, pc, boot, rng)
                mark = "  <- candidate" if (n in cnames or n.endswith("jointly")) else ""
                print(f"    {n:<26}{p_:>+9.3f}  [{lo:+.3f},{hi:+.3f}]{mark}")
            print(f"    [{time.time()-t0:.0f}s]", flush=True)
        print()

    print("=" * 112)
    print("DECISION -- rule fixed in the docstring before the run")
    print("=" * 112)
    for tag, vv in verdicts.items():
        print(f"  {tag:<15} {vv}")
    print("  Levels are a later look at already-scored rows; the paired differences")
    print("  are the new measurement. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------- wider screen: 1h, 5h, 10h
SCREEN = (2, 10, 20)                 # 1h, 5h, 10h
PUBLISHED_10H = {                    # HOUR-OF-DAY / HEDGE-QUALITY, 10h, paired deltas
    ("HOUR-OF-DAY", "MFE"): (-0.218, +0.029), ("HOUR-OF-DAY", "MAE"): (-0.104, -0.029),
    ("HEDGE-QUALITY", "MFE"): (+0.034, +0.021), ("HEDGE-QUALITY", "MAE"): (-0.163, +0.196)}


def load_reused(title):
    """Population, newfeat.npz (verified against a fresh read of meta), the
    1-minute targets and the fingerprint-checked baselines. No rebuild."""
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    day = meta.day.to_numpy()

    print("=" * 112)
    print(title)
    print("=" * 112)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    nf = np.load(os.path.join(paths.DATASETS, "newfeat.npz"))
    if not (np.array_equal(v48["rows"], rows) and np.array_equal(nf["rows"], rows)):
        raise SystemExit("[NEWF] a saved feature file's rows differ from the population.")
    et = pd.to_datetime(meta.entry_time.iloc[rows])
    h = et.dt.hour.to_numpy() + et.dt.minute.to_numpy() / 60.0
    fresh = dict(hour_sin=np.sin(2 * np.pi * h / 24), hour_cos=np.cos(2 * np.pi * h / 24),
                 r2=meta.r2.to_numpy(float)[rows],
                 abs_beta=np.abs(meta.beta.to_numpy(float)[rows]))
    dmax = max(float(np.max(np.abs(nf[k] - v))) for k, v in fresh.items())
    print(f"  population: {len(rows):,} episodes; newfeat.npz reused, stored columns vs "
          f"a fresh read of meta: max diff {dmax:.1e}")
    if dmax > 0.0:
        raise SystemExit("[NEWF] newfeat.npz differs from meta.")
    print()
    T1M, base = load_baselines(Y, meta, X, names, rows, v48)
    return Y, rows, day, T1M, base, nf


def horizons():
    """Both candidates at 1h, 5h and 10h, both directions: 12 cells.

    REUSES newfeat.npz -- no rebuild. The stored rows must equal the
    population and the stored columns must equal a fresh read of meta, so the
    features scored are provably the ones whose checks passed.

    ONE QTREE FIT per candidate per direction, over all five horizons (the
    two-pass enforcement needs them all), scored at 1h, 5h and 10h. The fit is
    deterministic, so 10h must reproduce the published HOUR-OF-DAY /
    HEDGE-QUALITY deltas to the printed precision: a consistency check, not a
    new measurement. 1h and 5h are the new measurements.

    12 cells = 2 candidates x 2 directions x 3 horizons, each with two paired
    measures. Stated in advance so a lone borderline result is read against
    that count.

    THE RULE, fixed before the run, per candidate, per direction. A horizon's
    outcome is as before: IMPROVES if skill or gap is significantly better and
    neither is significantly worse; LOSES if either is significantly worse;
    HOLDS otherwise.
      RULED OUT  LOSES at any of the three horizons
      CLEARS     no LOSES, and IMPROVES at 2 or more of the 3
      NOT CLEAR  anything else
    Per candidate:
      one direction CLEARS, the other does not -> chase the winner at the
          remaining two horizons (0.5h, 2h), before any registry change
      both CLEAR -> propagate to the registry
      neither CLEARS -> MARGINAL, confirmed
    Gaps filled: "real harm" and "real improvement" are read as the LOSES and
    IMPROVES outcomes above; the brief did not say what happens if both
    directions clear, and propagation is the natural reading. The chase and
    any propagation are the NEXT builds, not done in this run.
    """
    t0 = time.time()
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    names = [str(x) for x in f["names"]]
    day = meta.day.to_numpy()

    print("=" * 112)
    print("WIDER SCREEN -- hour-of-day and hedge quality at 1h / 5h / 10h, 12 cells")
    print("=" * 112)
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    nf = np.load(os.path.join(paths.DATASETS, "newfeat.npz"))
    if not (np.array_equal(v48["rows"], rows) and np.array_equal(nf["rows"], rows)):
        raise SystemExit("[NEWF] a saved feature file's rows differ from the population.")
    et = pd.to_datetime(meta.entry_time.iloc[rows])
    h = et.dt.hour.to_numpy() + et.dt.minute.to_numpy() / 60.0
    fresh = dict(hour_sin=np.sin(2 * np.pi * h / 24), hour_cos=np.cos(2 * np.pi * h / 24),
                 r2=meta.r2.to_numpy(float)[rows],
                 abs_beta=np.abs(meta.beta.to_numpy(float)[rows]))
    dmax = max(float(np.max(np.abs(nf[k] - v))) for k, v in fresh.items())
    print(f"  population: {len(rows):,} episodes; newfeat.npz reused, stored columns vs "
          f"a fresh read of meta: max diff {dmax:.1e}")
    if dmax > 0.0:
        raise SystemExit("[NEWF] newfeat.npz differs from meta.")
    print()
    t0 = time.time()
    Y, rows, day, T1M, base, nf = load_reused(
        "WIDER SCREEN -- hour-of-day and hedge quality at 1h / 5h / 10h, 12 cells")

    cands = (("HOUR-OF-DAY", ["hour_sin", "hour_cos"],
              np.column_stack([nf["hour_sin"], nf["hour_cos"]])),
             ("HEDGE-QUALITY", ["r2", "abs_beta"],
              np.column_stack([nf["r2"], nf["abs_beta"]])))
    verdicts = {}
    for tag, cnames, C in cands:
        print("=" * 112)
        print(f"{tag} -- baseline + {' + '.join(cnames)}, QTREE, paired on identical rows")
        print("=" * 112)
        print("  skill: + = candidate helps.  gap: - = better calibrated.")
        print(f"  {'cell':<10}{'measure':<9}{'base':>8}{'+cand':>8}{'new - old':>11}"
              f"{'[95% CI]':>18}{'':>9}{'horizon':>10}")
        dirv = {}
        for d in ("MFE", "MAE"):
            Xb, cb, _ = base[d]
            ctx = build_context(np.ones(len(rows), bool), np.column_stack([Xb, C]),
                                day[rows], Y[rows, 0], verbose=False)
            boot = day_boot(ctx["day_test"])
            enf, _, _ = enforce_two_pass(np.stack(
                [fit_qtree(ctx, T1M[(d, kk)]) for kk in HORIZONS]))
            ocs = []
            for k in SCREEN:
                new = enf[HORIZONS.index(k)]
                y = T1M[(d, k)][ctx["test"]]
                old = cb[f"1m|{d}|QTREE|{k}"]
                clim = cb[f"1m|{d}|Climatology|{k}"]
                ds = paired_skill_ci(y, old, new, clim, boot)
                dg = gap_paired_ci(y, old, y, new, boot)
                s_t, g_t, oc = cell_outcome(ds, dg)
                ocs.append(oc)
                cell = f"{d} {HLABEL[k]}"
                print(f"  {cell:<10}{'skill %':<9}{skill_ci(y, old, clim, boot)[0]:>+8.2f}"
                      f"{skill_ci(y, new, clim, boot)[0]:>+8.2f}{ds[0]:>+11.3f}"
                      f"{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{s_t:>9}{oc:>10}")
                print(f"  {'':<10}{'gap pp':<9}{gap_ci(y, old, boot)[0]:>8.2f}"
                      f"{gap_ci(y, new, boot)[0]:>8.2f}{dg[0]:>+11.3f}"
                      f"{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{g_t:>9}")
                if k == 20:
                    ps, pg = PUBLISHED_10H[(tag, d)]
                    if round(ds[0], 3) != ps or round(dg[0], 3) != pg:
                        raise SystemExit(f"[NEWF] {tag} {d} 10h does not reproduce the "
                                         f"published deltas {ps:+.3f} / {pg:+.3f}.")
                    print(f"  {'':<10}10h reproduces the published deltas "
                          f"({ps:+.3f} / {pg:+.3f})")
            dirv[d] = ("RULED OUT" if "LOSES" in ocs
                       else "CLEARS" if ocs.count("IMPROVES") >= 2 else "NOT CLEAR")
            print(f"  -> {d}: {' / '.join(ocs)} at 1h / 5h / 10h -> {dirv[d]}"
                  f"   [{time.time()-t0:.0f}s]", flush=True)
        clear = [d for d in dirv if dirv[d] == "CLEARS"]
        if not clear:
            v = "MARGINAL (confirmed)"
        elif len(clear) == 2:
            v = "PROPAGATE -- the registry rebuild is the next build"
        else:
            v = (f"CHASE {clear[0]} at 0.5h and 2h before any registry change "
                 f"-- the next build, not done here")
        verdicts[tag] = (dirv, v)
        print(f"  VERDICT {tag}: MFE {dirv['MFE']}, MAE {dirv['MAE']} -> {v}")
        print()

    print("=" * 112)
    print("DECISION -- rule fixed in horizons()' docstring before the run")
    print("=" * 112)
    for tag, (dirv, v) in verdicts.items():
        print(f"  {tag:<15} MFE {dirv['MFE']:<10} MAE {dirv['MAE']:<10} -> {v}")
    print("  10h is a reproduction; 1h and 5h are new paired measurements on")
    print("  held-out rows scored before. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------- all four together (exploratory)
NEW4 = ["hour_sin", "hour_cos", "r2", "abs_beta"]
# Per-horizon outcomes of the two individual tests (HOUR-OF-DAY / HEDGE-QUALITY
# wider screen), and their paired (skill, gap) deltas, for the comparison.
INDIV = {
    ("MFE", 2): (("HOLDS", +0.119, +0.023), ("HOLDS", -0.025, -0.017)),
    ("MFE", 10): (("HOLDS", +0.031, +0.018), ("IMPROVES", +0.052, -0.053)),
    ("MFE", 20): (("LOSES", -0.218, +0.029), ("HOLDS", +0.034, +0.021)),
    ("MAE", 2): (("HOLDS", -0.197, +0.053), ("LOSES", +0.095, +0.127)),
    ("MAE", 10): (("IMPROVES", +0.056, -0.153), ("LOSES", -0.033, +0.109)),
    ("MAE", 20): (("HOLDS", -0.104, -0.029), ("LOSES", -0.163, +0.196))}


def combined():
    """All four new columns at once, on the current baseline. EXPLORATORY.

    Not a path to registry adoption whatever the result: r2/|beta| are
    confirmed harmful to MAE calibration at every horizon tested, and the hour
    pair is confirmed harmful to MFE skill at 10h. So this stage issues NO
    adoption verdict. A positive cell here would need more scrutiny than a
    fresh idea, not less.

    Nine columns: the baseline five (vol_48_1m for MAE, vol_48 for MFE;
    vratio, vol_slope, sandwich, off_mark) + hour_sin, hour_cos, r2, |beta|,
    from newfeat.npz. QTREE only. One fit per direction over all five
    horizons, two-pass enforced, scored at 1h, 5h, 10h, paired against the
    cached baseline QTREE on identical held-out rows and day resamples. Six
    cells, each with two measures.

    PERMUTATION IMPORTANCE, all nine features, at each of the six cells: the
    per-horizon refit before horizon enforcement, held out, 20 shuffles, skill
    points against climatology, day-clustered interval -- IMPORTANCE's units.
    Also jointly: the hour pair, the hedge pair, all four new, the old five.

    IS THE COMBINATION DIFFERENT? Fixed before the run. Each cell's outcome
    (IMPROVES / HOLDS / LOSES, defined as before) is compared with what the
    two individual tests predict for that cell:
        predicted LOSES     if either individual test LOSES there
        predicted IMPROVES  if either IMPROVES and neither LOSES
        predicted HOLDS     otherwise
      AS PREDICTED  the combined outcome equals the prediction
      DIFFERENT     it does not -- named, with its direction (better or worse
                    than predicted)
    The combination "genuinely does something different" only if at least one
    cell is DIFFERENT. Note the prediction is generous: the two lone 5h
    improvements were judged noise last run, but they still count as
    predicted IMPROVES here, so a combined HOLDS there shows as DIFFERENT
    (worse) without meaning much. The individual paired deltas are printed
    beside the combined ones so size can be read, not just category.
    """
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    Y, rows, day, T1M, base, nf = load_reused(
        "COMBINED (exploratory) -- baseline + hour_sin, hour_cos, r2, |beta|; "
        "1h / 5h / 10h")
    C = np.column_stack([nf[k] for k in NEW4])
    print("  skill: + = combination helps.  gap: - = better calibrated.")
    print("  indiv: the two individual tests' paired deltas (hour | hedge), skill / gap.")
    print()
    print(f"  {'cell':<10}{'measure':<9}{'base':>8}{'+four':>8}{'new - old':>11}"
          f"{'[95% CI]':>18}{'':>9}{'outcome':>10}   indiv hour | hedge")
    table, imp = {}, {}
    for d in ("MFE", "MAE"):
        Xb, cb, bnames = base[d]
        allnames = bnames + NEW4
        ctx = build_context(np.ones(len(rows), bool), np.column_stack([Xb, C]),
                            day[rows], Y[rows, 0], verbose=False)
        boot = day_boot(ctx["day_test"])
        tes, mods = [], {}
        for kk in HORIZONS:
            ms = [] if kk in SCREEN else None
            tes.append(fit_qtree(ctx, T1M[(d, kk)], models=ms))
            if kk in SCREEN:
                mods[kk] = ms
        enf, _, _ = enforce_two_pass(np.stack(tes))
        for k in SCREEN:
            new = enf[HORIZONS.index(k)]
            y = T1M[(d, k)][ctx["test"]]
            old = cb[f"1m|{d}|QTREE|{k}"]
            clim = cb[f"1m|{d}|Climatology|{k}"]
            ds = paired_skill_ci(y, old, new, clim, boot)
            dg = gap_paired_ci(y, old, y, new, boot)
            s_t, g_t, oc = cell_outcome(ds, dg)
            ih, iq = INDIV[(d, k)]
            pred = ("LOSES" if "LOSES" in (ih[0], iq[0])
                    else "IMPROVES" if "IMPROVES" in (ih[0], iq[0]) else "HOLDS")
            rank = {"LOSES": 0, "HOLDS": 1, "IMPROVES": 2}
            cmp_ = ("AS PREDICTED" if oc == pred else
                    f"DIFFERENT ({'better' if rank[oc] > rank[pred] else 'worse'} "
                    f"than predicted {pred})")
            table[(d, k)] = (oc, pred, cmp_)
            cell = f"{d} {HLABEL[k]}"
            print(f"  {cell:<10}{'skill %':<9}{skill_ci(y, old, clim, boot)[0]:>+8.2f}"
                  f"{skill_ci(y, new, clim, boot)[0]:>+8.2f}{ds[0]:>+11.3f}"
                  f"{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{s_t:>9}{oc:>10}"
                  f"   {ih[1]:+.3f} | {iq[1]:+.3f}")
            print(f"  {'':<10}{'gap pp':<9}{gap_ci(y, old, boot)[0]:>8.2f}"
                  f"{gap_ci(y, new, boot)[0]:>8.2f}{dg[0]:>+11.3f}"
                  f"{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{g_t:>9}{'':>10}"
                  f"   {ih[2]:+.3f} | {iq[2]:+.3f}")
            print(f"  {'':<10}vs individual tests: {cmp_}")

            # ---- importance, this cell ----
            pc = _pinball_rows(y, clim)
            qm = mods[k]
            predict = lambda Xp, qm=qm: qtree_predict(qm, Xp)
            sk = 100 * (1 - _pinball_rows(y, predict(ctx["Xte"])).mean() / pc.mean())
            sets = [(n, [j]) for j, n in enumerate(allnames)]
            nb = len(bnames)
            sets += [("hour pair", [nb, nb + 1]), ("hedge pair", [nb + 2, nb + 3]),
                     ("all four new", list(range(nb, nb + 4))),
                     ("old five", list(range(nb)))]
            imp[(d, k)] = (sk, [(n, importance(predict, ctx["Xte"], c_, y, pc, boot, rng))
                                for n, c_ in sets])
        print(f"  [{time.time()-t0:.0f}s]", flush=True)
    print()

    print("=" * 112)
    print("PERMUTATION IMPORTANCE -- all nine features, skill points vs climatology,")
    print("held out, 20 shuffles, day-clustered 95% interval, pre-horizon-enforcement")
    print("=" * 112)
    keys = [(d, k) for d in ("MFE", "MAE") for k in SCREEN]
    print(f"  {'feature':<14}" + "".join(f"{d+' '+HLABEL[k]:>22}" for d, k in keys))
    print(f"  {'(refit skill)':<14}" + "".join(f"{f'{imp[c][0]:+.2f}%':>22}" for c in keys))
    for i_, (n, _) in enumerate(imp[keys[0]][1]):
        label = "vol_48(_1m)" if n in ("vol_48", "vol_48_1m") else n
        cells = []
        for c in keys:
            p_, lo, hi = imp[c][1][i_][1]
            cells.append(f"{p_:+.2f} [{lo:+.2f},{hi:+.2f}]")
        print(f"  {label:<14}" + "".join(f"{x:>22}" for x in cells))
    print("  vol_48(_1m) is vol_48 in the MFE columns and vol_48_1m in the MAE columns.")
    print()

    print("=" * 112)
    print("IS THE COMBINATION DIFFERENT? -- rule fixed in combined()' docstring")
    print("=" * 112)
    for c in keys:
        oc, pred, cmp_ = table[c]
        print(f"  {c[0]} {HLABEL[c[1]]:<5} combined {oc:<9} predicted {pred:<9} -> {cmp_}")
    ndiff = sum(1 for c in keys if table[c][2] != "AS PREDICTED")
    print(f"  {ndiff} of 6 cells differ from the individual tests' prediction.")
    print("  EXPLORATORY: no adoption verdict is issued by this stage. Nothing in the")
    print("  registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------- all four together, full registry
REG_MODELS = ("Linear QR", "QTREE", "kNN", "CQR")
# QTREE's paired (skill, gap) deltas from the 3-horizon COMBINED run: this
# stage's QTREE must reproduce them (same deterministic fit).
QTREE_COMBINED = {("MFE", 2): (+0.219, -0.062), ("MFE", 10): (+0.033, +0.062),
                  ("MFE", 20): (-0.191, +0.059), ("MAE", 2): (-0.247, +0.006),
                  ("MAE", 10): (-0.002, -0.164), ("MAE", 20): (-0.109, +0.115)}


def fit_registry(rows, day, Y, T1M, base, C, cnames, t0):
    """Refit Linear QR, QTREE, kNN and CQR on baseline + C, all five horizons,
    both directions, and score each cell PAIRED against that model's cached
    baseline. Returns per-cell results and, per (direction, horizon), the
    context and pre-enforcement predictors used for permutation importance.
    kNN and CQR predictors are rebuilt from parts and must equal the registry
    functions' output exactly."""
    from sklearn.neighbors import NearestNeighbors
    from envelope import (KNN_K, QUANTILES, CQR_PAIRS, MEDIAN_IX, apply_cqr,
                          conformal_width, fit_cqr, fit_knn, fit_linear)
    results, preds = {}, {}
    for d in ("MFE", "MAE"):
        Xb, cb, bnames = base[d]
        allnames = bnames + list(cnames)
        ctx = build_context(np.ones(len(rows), bool), np.column_stack([Xb, C]),
                            day[rows], Y[rows, 0], verbose=(d == "MFE"))
        boot = day_boot(ctx["day_test"])
        nn = NearestNeighbors(n_neighbors=KNN_K).fit(ctx["Ztr"])
        raw = {mn: [] for mn in REG_MODELS}
        for kk in HORIZONS:
            y = T1M[(d, kk)]
            ytr = y[ctx["train"]]
            lm = []
            raw["Linear QR"].append(fit_linear(ctx, y, f"1m/{d}/{HLABEL[kk]}/+{'+'.join(cnames)}",
                                               models=lm))
            qm = []
            raw["QTREE"].append(fit_qtree(ctx, y, models=qm))
            raw["kNN"].append(fit_knn(ctx, y))
            raw["CQR"].append(fit_cqr(ctx, y))
            # predictors rebuilt from parts, for importance
            yva = y[ctx["val"]]
            va = qtree_predict(qm, ctx["Xva"])
            widths = [conformal_width(yva, va[:, jl], va[:, jh], a)[0]
                      for jl, jh, a in CQR_PAIRS]
            shift = float(np.median(yva - va[:, MEDIAN_IX]))
            P = {
                "Linear QR": ("Z", lambda Z, lm=lm: np.maximum.accumulate(
                    np.column_stack([m.predict(Z) for _, m in lm]), axis=1)),
                "QTREE": ("X", lambda X_, qm=qm: qtree_predict(qm, X_)),
                "kNN": ("Z", lambda Z, ytr=ytr, nn=nn: np.quantile(
                    ytr[nn.kneighbors(Z, return_distance=False)], QUANTILES, axis=1).T),
                "CQR": ("X", lambda X_, qm=qm, w=widths, s_=shift:
                        apply_cqr(qtree_predict(qm, X_), w, s_)[0]),
            }
            ek = float(np.max(np.abs(P["kNN"][1](ctx["Zte"]) - raw["kNN"][-1])))
            ec = float(np.max(np.abs(P["CQR"][1](ctx["Xte"]) - raw["CQR"][-1])))
            if ek > 1e-12 or ec > 1e-12:
                raise SystemExit(f"[NEWF] rebuilt predictor differs from the registry "
                                 f"output at {d} {HLABEL[kk]}: kNN {ek:.2e}, CQR {ec:.2e}")
            preds[(d, kk)] = (ctx, P, allnames, len(bnames))
            print(f"  fitted {d} {HLABEL[kk]:<5} all four models; rebuilt kNN/CQR "
                  f"match the registry ({ek:.0e}, {ec:.0e})   [{time.time()-t0:.0f}s]",
                  flush=True)
        for mn in REG_MODELS:
            enf, _, _ = enforce_two_pass(np.stack(raw[mn]))
            for i, k in enumerate(HORIZONS):
                y = T1M[(d, k)][ctx["test"]]
                old = cb[f"1m|{d}|{mn}|{k}"]
                clim = cb[f"1m|{d}|Climatology|{k}"]
                new = enf[i]
                ds = paired_skill_ci(y, old, new, clim, boot)
                dg = gap_paired_ci(y, old, y, new, boot)
                s_t, g_t, oc = cell_outcome(ds, dg)
                results[(mn, d, k)] = dict(
                    so=skill_ci(y, old, clim, boot)[0], sn=skill_ci(y, new, clim, boot)[0],
                    go=gap_ci(y, old, boot)[0], gn=gap_ci(y, new, boot)[0],
                    ds=ds, dg=dg, s_t=s_t, g_t=g_t, oc=oc, boot=boot,
                    y=y, pc=_pinball_rows(y, clim))
    print()
    return results, preds


def combined_registry():
    """All four new columns, all four feature-using models, all five horizons,
    both directions: 40 cells. EXPLORATORY -- no adoption verdict, whatever
    the result. r2/|beta| are confirmed harmful to MAE calibration and the
    hour pair to MFE skill at 10h, so a positive cell earns more scrutiny.

    Nine columns as in combined(). Climatology uses no features and is the
    fixed denominator. Each model is refitted on the nine columns at all five
    horizons, two-pass enforced per model, and compared PAIRED against its own
    cached baseline predictions (MFE: match1m on vol_48; MAE: match1m_mae_vol1m
    on vol_48_1m) on identical held-out rows and day resamples. Per-cell
    outcome as before: IMPROVES / HOLDS / LOSES.

    40 cells x 2 measures = 80 paired tests. With no effect at all, each
    one-sided 2.5% tail would still fire about twice on each side by chance.
    Stated now so a scattered handful of significant cells is read against it.

    CHECKS. QTREE must reproduce the 3-horizon COMBINED deltas exactly. CQR and
    kNN predictions are rebuilt from their parts for importance (QTREE models
    + val widths/shift; a neighbour index on train), and each rebuild must equal
    the registry function's output on the unshuffled held-out rows.

    IS ANYTHING DIFFERENT FROM WHAT THE INDIVIDUAL TESTS PREDICT? Fixed now.
    The individual tests were QTREE only, at 1h/5h/10h. So:
      QTREE 1h/5h/10h  the rule of combined(), and these six cells must
                       reproduce that run -- they cannot be new
      every other cell no cell-level prediction exists. The individual tests'
                       finding is "no gain": both candidates MARGINAL. So HOLDS
                       or LOSES is CONSISTENT, and IMPROVES is NEW -- named
                       and flagged for extra scrutiny, not adopted
    A model "shows movement" if any of its 10 cells is IMPROVES or LOSES.

    IMPORTANCE, for every model that shows movement, at each of its moved
    cells: all nine columns singly and the four groups (hour pair, hedge pair,
    all four new, old five), 20 shuffles, held out, skill points against
    climatology, day-clustered interval, per-horizon predictions before horizon
    enforcement (Linear QR and QTREE re-ordered along q, as in IMPORTANCE).
    Linear QR and kNN are shuffled on the train-standardised columns, which is
    the same permutation of the same rows. Read the hour pair from its joint row:
    shuffling sin or cos alone puts rows off the unit circle.
    """
    from envelope import LINEAR_FALLBACKS
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    Y, rows, day, T1M, base, nf = load_reused(
        "COMBINED, FULL REGISTRY (exploratory) -- 4 models x 5 horizons x 2 "
        "directions = 40 cells")
    C = np.column_stack([nf[k] for k in NEW4])
    rank = {"LOSES": 0, "HOLDS": 1, "IMPROVES": 2}
    results, preds = fit_registry(rows, day, Y, T1M, base, C, NEW4, t0)

    # ---- QTREE reproduction ----
    worst = 0.0
    for (d, k), (ps, pg) in QTREE_COMBINED.items():
        r = results[("QTREE", d, k)]
        if round(r["ds"][0], 3) != ps or round(r["dg"][0], 3) != pg:
            raise SystemExit(f"[NEWF] QTREE {d} {HLABEL[k]} does not reproduce the "
                             f"3-horizon COMBINED run.")
    print("  QTREE reproduces the 3-horizon COMBINED deltas at all six cells.")
    print(f"  Linear QR LP fallbacks (alpha > 0): {len(LINEAR_FALLBACKS)}"
          + (f" -- {LINEAR_FALLBACKS}" if LINEAR_FALLBACKS else ""))
    print()

    print("=" * 112)
    print("PAIRED vs each model's own 5-feature baseline -- skill: + helps; gap: - better")
    print("=" * 112)
    for mn in REG_MODELS:
        print(f"  {mn}")
        print(f"    {'cell':<10}{'skill base':>11}{'+four':>7}{'new-old':>9}{'[95% CI]':>18}"
              f"{'':>7}{'gap base':>9}{'+four':>7}{'new-old':>9}{'[95% CI]':>18}{'':>7}"
              f"{'outcome':>10}  vs prediction")
        for d in ("MFE", "MAE"):
            for k in HORIZONS:
                r = results[(mn, d, k)]
                ds, dg, oc = r["ds"], r["dg"], r["oc"]
                if mn == "QTREE" and k in SCREEN:
                    ih, iq = INDIV[(d, k)]
                    pred = ("LOSES" if "LOSES" in (ih[0], iq[0])
                            else "IMPROVES" if "IMPROVES" in (ih[0], iq[0]) else "HOLDS")
                    cmp_ = ("as predicted" if oc == pred else
                            f"DIFFERENT ({'better' if rank[oc] > rank[pred] else 'worse'}"
                            f" than {pred}) -- reproduced")
                else:
                    cmp_ = "NEW -- extra scrutiny" if oc == "IMPROVES" else "consistent"
                r["cmp"] = cmp_
                cell = f"{d} {HLABEL[k]}"
                print(f"    {cell:<10}{r['so']:>+11.2f}{r['sn']:>+7.2f}{ds[0]:>+9.3f}"
                      f"{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{r['s_t']:>7}"
                      f"{r['go']:>9.2f}{r['gn']:>7.2f}{dg[0]:>+9.3f}"
                      f"{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{r['g_t']:>7}"
                      f"{oc:>10}  {cmp_}")
        print()

    print("=" * 112)
    print("COUNTS")
    print("=" * 112)
    print(f"  {'model':<11}{'dir':<5}{'IMPROVES':>9}{'HOLDS':>7}{'LOSES':>7}"
          f"{'skill+':>8}{'skill-':>8}{'gap+':>6}{'gap-':>6}")
    tot = dict(i=0, h=0, l=0, sb=0, sw=0, gb=0, gw=0)
    for mn in REG_MODELS:
        for d in ("MFE", "MAE"):
            rs = [results[(mn, d, k)] for k in HORIZONS]
            c_ = dict(i=sum(r["oc"] == "IMPROVES" for r in rs),
                      h=sum(r["oc"] == "HOLDS" for r in rs),
                      l=sum(r["oc"] == "LOSES" for r in rs),
                      sb=sum(r["s_t"] == "better" for r in rs),
                      sw=sum(r["s_t"] == "WORSE" for r in rs),
                      gb=sum(r["g_t"] == "better" for r in rs),
                      gw=sum(r["g_t"] == "WORSE" for r in rs))
            for k_ in tot:
                tot[k_] += c_[k_]
            print(f"  {mn:<11}{d:<5}{c_['i']:>9}{c_['h']:>7}{c_['l']:>7}"
                  f"{c_['sb']:>8}{c_['sw']:>8}{c_['gb']:>6}{c_['gw']:>6}")
    print(f"  {'ALL 40':<16}{tot['i']:>9}{tot['h']:>7}{tot['l']:>7}{tot['sb']:>8}"
          f"{tot['sw']:>8}{tot['gb']:>6}{tot['gw']:>6}")
    print("  (skill+/gap+ = significantly better; skill-/gap- = significantly worse.")
    print("   By chance alone, about 2 of 80 tests would fire on each side.)")
    print()

    moved = [mn for mn in REG_MODELS
             if any(results[(mn, d, k)]["oc"] != "HOLDS"
                    for d in ("MFE", "MAE") for k in HORIZONS)]
    print("=" * 112)
    print(f"PERMUTATION IMPORTANCE -- models showing movement: {', '.join(moved) or 'none'}")
    print("skill points vs climatology, held out, 20 shuffles, day-clustered 95% interval,")
    print("per-horizon predictions before horizon enforcement; at each moved cell only")
    print("=" * 112)
    for mn in moved:
        cells = [(d, k) for d in ("MFE", "MAE") for k in HORIZONS
                 if results[(mn, d, k)]["oc"] != "HOLDS"]
        for d, k in cells:
            ctx, P, allnames, nb = preds[(d, k)]
            space, fn = P[mn]
            Xte = ctx["Zte"] if space == "Z" else ctx["Xte"]
            r = results[(mn, d, k)]
            y, pc, boot = r["y"], r["pc"], r["boot"]
            sk = 100 * (1 - _pinball_rows(y, fn(Xte)).mean() / pc.mean())
            sets = [(n, [j]) for j, n in enumerate(allnames)]
            sets += [("hour pair", [nb, nb + 1]), ("hedge pair", [nb + 2, nb + 3]),
                     ("all four new", list(range(nb, nb + 4))),
                     ("old five", list(range(nb)))]
            print(f"  {mn} {d} {HLABEL[k]} ({r['oc']}; refit skill {sk:+.2f}%, "
                  f"pre-horizon-enforcement)")
            for n, c_ in sets:
                p_, lo, hi = importance(fn, Xte, c_, y, pc, boot, rng)
                mark = "  <- new" if n in NEW4 or n in ("hour pair", "hedge pair",
                                                        "all four new") else ""
                print(f"    {n:<14}{p_:>+8.3f}  [{lo:+.3f},{hi:+.3f}]{mark}")
            print(f"    [{time.time()-t0:.0f}s]", flush=True)
    print()

    print("=" * 112)
    print("DIFFERENT FROM THE INDIVIDUAL TESTS? -- rule fixed in the docstring")
    print("=" * 112)
    new_cells = [(mn, d, k) for (mn, d, k), r in results.items()
                 if r["cmp"].startswith("NEW")]
    print(f"  NEW (an improvement where the individual tests predict no gain): "
          f"{len(new_cells)} of 34 cells without a cell-level prediction")
    for mn, d, k in new_cells:
        r = results[(mn, d, k)]
        print(f"    {mn} {d} {HLABEL[k]}: skill {r['ds'][0]:+.3f} [{r['ds'][1]:+.3f},"
              f"{r['ds'][2]:+.3f}]  gap {r['dg'][0]:+.3f} [{r['dg'][1]:+.3f},"
              f"{r['dg'][2]:+.3f}]")
    print("  QTREE 1h/5h/10h: reproduced from the 3-horizon run, not new.")
    print("  EXPLORATORY: no adoption verdict. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------- market-wide volatility
N_RECHECK = 500           # episodes whose market_vol is recomputed from a truncated slice


def build_market_vol(meta, rows, train):
    """market_vol for every population row, with the correctness checks.

    DEFINITION. For each ticker in the pair universe, the mean absolute
    30-minute log-return over the last 48 bars ending at the entry bar -- the
    49 closes at indices t-48..t, the same 24 hours vol_48 covers. Then the
    MEDIAN across tickers, excluding the episode's own two legs.

    UNIVERSE. The 212 tradeable tickers. BTC and ETH are carried in the panel
    only as market factors (universe_panel.FACTOR_ONLY), never paired, so they
    are not part of the universe being described and are left out.

    LISTED AS OF THE ENTRY BAR. A ticker counts only if all 49 closes in its
    window are finite. The panel's finite region per ticker is one contiguous
    block ending at the last bar (asserted in mkdisloc), so this means: listed
    at least 24 hours before the entry bar. A ticker that lists later is NaN at
    every earlier bar and cannot enter an earlier episode's reading.

    NORMALISATION. Raw values are in log-return units. market_vol = raw /
    median(raw over TRAIN rows): 1.0 is a typical train-period universe; 2.0 is
    a universe moving twice as much. A positive rescaling, so it changes no
    model: Linear QR and kNN standardise every column on train inside
    build_context, which absorbs any positive scale exactly, and trees are
    invariant to it. It is done for readability, as the brief asks.
    """
    import universe_panel
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    uni = [c for c in panel.columns
           if universe_panel._base_symbol(c) not in universe_panel.FACTOR_ONLY]
    col = {c: j for j, c in enumerate(uni)}
    V = panel[uni].to_numpy(float)                       # log prices
    absr = pd.DataFrame(np.abs(np.diff(V, axis=0)))
    # A[t] = mean |r| over returns t-47..t, i.e. closes t-48..t; NaN if any missing
    A = np.vstack([np.full((1, len(uni)), np.nan),
                   absr.rolling(48, min_periods=48).mean().to_numpy()])
    t = meta.bar_index.to_numpy()[rows]
    if not (panel.index[t] == pd.to_datetime(meta.entry_time.iloc[rows])).all():
        raise SystemExit("[NEWF] bar_index does not point at entry_time in the panel.")
    ja = np.array([col[x] for x in meta.ticker_a.iloc[rows]])
    jb = np.array([col[x] for x in meta.ticker_b.iloc[rows]])
    M = A[t].copy()                                       # episodes x tickers
    legs_live = np.isfinite(M[np.arange(len(t)), ja]) & np.isfinite(M[np.arange(len(t)), jb])
    M[np.arange(len(t)), ja] = np.nan
    M[np.arange(len(t)), jb] = np.nan
    used = np.isfinite(M)
    if used[np.arange(len(t)), ja].any() or used[np.arange(len(t)), jb].any():
        raise SystemExit("[NEWF] an episode's own leg is inside its market average.")
    count = used.sum(1)
    raw = np.nanmedian(M, axis=1)

    # independent recompute from a slice that ENDS at the entry bar
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(t), N_RECHECK, replace=False)
    worst, max_idx = 0.0, -1
    for e in pick:
        sl = V[t[e] - 48: t[e] + 1]
        max_idx = max(max_idx, t[e] - 48 + len(sl) - 1 - t[e])   # offset of last row read
        ok = np.isfinite(sl).all(0)
        ok[[ja[e], jb[e]]] = False
        v = np.median(np.abs(np.diff(sl[:, ok], axis=0)).mean(0))
        worst = max(worst, abs(v - raw[e]))
    return dict(raw=raw, count=count, t=t, legs_live=legs_live, worst=worst,
                max_off=max_idx, n_uni=len(uni), norm=float(np.median(raw[train])))


def market_vol():
    """market_vol, added on top of the current registry baseline, all four
    feature-using models, five horizons, both directions: 40 cells.

    TEST. Baseline per direction as always: MAE on vol_48_1m, MFE on vol_48,
    the other four unchanged; market_vol added as a sixth column. Linear QR,
    QTREE, kNN and CQR refitted, two-pass enforced, each compared PAIRED with
    its own cached baseline. Per cell: IMPROVES / HOLDS / LOSES as before.
    80 paired tests; by chance about 2 fire on each side.

    IMPORTANCE. market_vol's own permutation importance (20 shuffles, held
    out, skill points, day-clustered interval, pre-enforcement) at every cell
    that moves, in every model -- required at harmed kNN cells by the rule,
    and cheap enough elsewhere to trace any movement to the column.

    THE RULE, fixed before the run, per direction (20 cells: 4 models x 5
    horizons):
      confirmed harm  a LOSES cell, EXCEPT a kNN LOSES cell where market_vol's
                      importance interval does not clear zero (lower bound
                      <= 0): that is read as distance dilution, not as
                      evidence against the feature
      CLEARS          no confirmed harm AND IMPROVES in a majority of the 20
                      cells, i.e. 11 or more
    Per feature:
      both directions clear -> propagate to both
      one clears            -> propagate to that direction only
      neither               -> MARGINAL: report and stop
    Gaps filled: "majority of its cells" = 11 of the direction's 20; "explained
    by kNN dilution" = the importance test above. Propagation is the NEXT
    build; nothing is written to the registry here.
    """
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    Y, rows, day, T1M, base, nf = load_reused(
        "MARKET-VOL -- median universe volatility, 4 models x 5 horizons x 2 "
        "directions = 40 cells")
    meta = pd.read_parquet(paths.META)
    from harness import Split
    train = Split(day[rows], Y[rows, 0]).train

    print("=" * 112)
    print("BUILD -- with checks, before any scoring")
    print("=" * 112)
    B = build_market_vol(meta, rows, train)
    print(f"  universe: {B['n_uni']} tickers (BTC/ETH excluded as factor-only)")
    print(f"  1. no look-ahead: every episode's window ends at its bar_index, which is "
          f"its entry_time in the panel; independent recompute on {N_RECHECK} "
          f"episodes from a slice ending at the entry bar: last row read at offset "
          f"+{B['max_off']} (must be 0), max diff {B['worst']:.1e}")
    if B["max_off"] != 0 or B["worst"] > 1e-15:
        raise SystemExit("[NEWF] market_vol does not reproduce from a truncated slice.")
    print(f"  2. leg exclusion: neither leg in its own average, all {len(rows):,} "
          f"episodes (asserted); legs that WERE live and so actually removed: "
          f"{int(B['legs_live'].sum()):,} of {len(rows):,}")
    cnt = B["count"]
    thin = cnt < 0.5 * np.median(cnt)
    sp = Split(day[rows], Y[rows, 0])
    print(f"  3. tickers per episode: min {cnt.min()}, median {np.median(cnt):.0f}, "
          f"max {cnt.max()}")
    q = pd.Series(cnt).groupby(pd.to_datetime(day[rows]).to_period("Q")).agg(
        ["min", "median", "max", "size"])
    for per, r_ in q.iterrows():
        print(f"       {str(per):<8} episodes {int(r_['size']):>6,}   tickers min "
              f"{int(r_['min']):>3}  median {r_['median']:>5.0f}  max {int(r_['max']):>3}")
    print(f"     thin (< half the median, < {0.5*np.median(cnt):.0f} tickers): "
          f"{int(thin.sum()):,} episodes -- train {int((thin & sp.train).sum()):,}, "
          f"val {int((thin & sp.val).sum()):,}, held out {int((thin & sp.test).sum()):,}")
    if not np.isfinite(B["raw"]).all():
        raise SystemExit("[NEWF] an episode has no universe to average.")
    mv = B["raw"] / B["norm"]
    print(f"  normalised: raw / train median ({B['norm']:.3e} log-return per 30m); "
          f"market_vol median {np.median(mv):.3f}, 5-95% "
          f"{np.percentile(mv, 5):.3f}-{np.percentile(mv, 95):.3f}, max {mv.max():.2f}")
    v48 = base["MFE"][0][:, 0]
    v48_1m = base["MAE"][0][:, 0]
    sr = lambda a, b: pd.Series(a).corr(pd.Series(b), method="spearman")
    print(f"  Spearman(market_vol, vol_48) {sr(mv, v48):.3f};  "
          f"(market_vol, vol_48_1m) {sr(mv, v48_1m):.3f}")
    np.savez_compressed(os.path.join(paths.DATASETS, "market_vol.npz"), rows=rows,
                        market_vol=mv, raw=B["raw"], count=cnt, norm=B["norm"])
    print("  [WROTE] research/datasets/market_vol.npz")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    results, preds = fit_registry(rows, day, Y, T1M, base, mv[:, None],
                                  ["market_vol"], t0)
    print()

    print("=" * 112)
    print("PAIRED vs each model's own 5-feature baseline -- skill: + helps; gap: - better")
    print("=" * 112)
    for mn in REG_MODELS:
        print(f"  {mn}")
        print(f"    {'cell':<10}{'skill base':>11}{'+mvol':>7}{'new-old':>9}{'[95% CI]':>18}"
              f"{'':>7}{'gap base':>9}{'+mvol':>7}{'new-old':>9}{'[95% CI]':>18}{'':>7}"
              f"{'outcome':>10}")
        for d in ("MFE", "MAE"):
            for k in HORIZONS:
                r = results[(mn, d, k)]
                ds, dg = r["ds"], r["dg"]
                print(f"    {d+' '+HLABEL[k]:<10}{r['so']:>+11.2f}{r['sn']:>+7.2f}"
                      f"{ds[0]:>+9.3f}{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{r['s_t']:>7}"
                      f"{r['go']:>9.2f}{r['gn']:>7.2f}{dg[0]:>+9.3f}"
                      f"{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{r['g_t']:>7}{r['oc']:>10}")
        print()

    print("=" * 112)
    print("market_vol IMPORTANCE at every moved cell -- skill points vs climatology")
    print("=" * 112)
    for (mn, d, k), r in results.items():
        if r["oc"] == "HOLDS":
            continue
        ctx, P, allnames, nb = preds[(d, k)]
        space, fn = P[mn]
        Xte = ctx["Zte"] if space == "Z" else ctx["Xte"]
        r["imp"] = importance(fn, Xte, [nb], r["y"], r["pc"], r["boot"], rng)
        p_, lo, hi = r["imp"]
        print(f"  {mn:<10}{d} {HLABEL[k]:<5}{r['oc']:>9}   market_vol {p_:+.3f} "
              f"[{lo:+.3f},{hi:+.3f}]   [{time.time()-t0:.0f}s]", flush=True)
    print()

    print("=" * 112)
    print("DECISION -- rule fixed in market_vol()' docstring before the run")
    print("=" * 112)
    clears = {}
    for d in ("MFE", "MAE"):
        cells = [(mn, k) for mn in REG_MODELS for k in HORIZONS]
        imp_ = sum(results[(mn, d, k)]["oc"] == "IMPROVES" for mn, k in cells)
        harm, excused = [], []
        for mn, k in cells:
            r = results[(mn, d, k)]
            if r["oc"] != "LOSES":
                continue
            if mn == "kNN" and r["imp"][1] <= 0:
                excused.append(f"kNN {HLABEL[k]}")
            else:
                harm.append(f"{mn} {HLABEL[k]}")
        clears[d] = not harm and imp_ >= 11
        print(f"  {d}: IMPROVES {imp_} of 20 (need 11);  confirmed harm {len(harm)}"
              f"{' -- ' + ', '.join(harm) if harm else ''};  kNN losses read as dilution "
              f"{len(excused)}{' -- ' + ', '.join(excused) if excused else ''}"
              f"  -> {'CLEARS' if clears[d] else 'does not clear'}")
    win = [d for d in clears if clears[d]]
    if not win:
        v = "MARGINAL -- report and stop, nothing propagated"
    elif len(win) == 2:
        v = "PROPAGATE to both directions -- the next build"
    else:
        v = f"PROPAGATE to {win[0]} only -- the next build"
    print(f"  VERDICT MARKET-VOL: {v}")
    print("  Levels are a later look at already-scored rows; paired differences are")
    print("  the new measurement. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------- market_vol: Linear QR on MAE, five horizons
MV_PUBLISHED = {1: (-0.005, -0.017), 2: (+0.025, -0.016), 4: (+0.071, -0.044),
                10: (+0.101, -0.029), 20: (+0.164, +0.016)}   # MARKET-VOL, Linear QR MAE
PLAIN_MISS_REF = {"Linear QR": 1.908, "Climatology": 1.949}  # PLAIN-MISS, MAE 10h


def mvol_linear():
    """market_vol in Linear QR on MAE: the full horizon check, and the plain miss.

    SCOPE. Linear QR only, MAE only. Baseline = the current MAE registry
    features (vol_48_1m, vratio, vol_slope, sandwich, off_mark); new = the same
    plus market_vol from market_vol.npz. Refitted at all five horizons (the
    two-pass enforcement needs them all), compared PAIRED with the cached
    Linear QR MAE predictions (match1m_mae_vol1m), day-clustered intervals.

    WHAT IS NEW HERE. The MARKET-VOL run already scored all five horizons, so
    the five paired deltas must REPRODUCE it -- a check, not a new measurement.
    New: market_vol's permutation importance at 0.5h and 1h (HOLDS cells there,
    so none was computed), importance re-drawn at 2h/5h/10h with the same
    method for one consistent table, the five-horizon net effect, and the 10h
    plain miss.

    PLAIN MISS. Mean |y - q50| of the median guess at 10h, after enforcement,
    held out, in sigma -- exactly twice the q50 pinball loss, as in PLAIN-MISS.
    Old Linear QR and Climatology come from the cache and must reproduce
    1.908 and 1.949. The new-minus-old difference gets a paired day-clustered
    interval.

    THE RULE, fixed before the run. ADOPT for Linear QR / MAE if BOTH:
      (a) NO HARM: no horizon has a significantly worse skill or gap;
      (b) NET IMPROVEMENT: the mean of the five paired skill gains has a
          day-clustered 95% interval entirely above zero (the same day
          resamples at every horizon, so the average is resampled jointly).
    Otherwise do not adopt. Gaps filled: the brief's "no real harm" and
    "net effect a genuine improvement" are read as (a) and (b). Adoption means
    the registry rebuild for this model/direction is the NEXT build; nothing
    is written here.
    """
    from envelope import fit_linear, LINEAR_FALLBACKS
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    Y, rows, day, T1M, base, nf = load_reused(
        "MARKET-VOL, Linear QR / MAE -- all five horizons, importance, plain miss")
    mvz = np.load(os.path.join(paths.DATASETS, "market_vol.npz"))
    if not np.array_equal(mvz["rows"], rows):
        raise SystemExit("[NEWF] market_vol.npz rows differ from the population.")
    d = "MAE"
    Xb, cb, bnames = base[d]
    ctx = build_context(np.ones(len(rows), bool), np.column_stack([Xb, mvz["market_vol"]]),
                        day[rows], Y[rows, 0], verbose=True)
    boot = day_boot(ctx["day_test"])
    raw, mods = [], {}
    for k in HORIZONS:
        lm = []
        raw.append(fit_linear(ctx, T1M[(d, k)], f"1m/{d}/{HLABEL[k]}/+market_vol",
                              models=lm))
        mods[k] = lm
        print(f"  fitted Linear QR MAE {HLABEL[k]}   [{time.time()-t0:.0f}s]", flush=True)
    enf, _, _ = enforce_two_pass(np.stack(raw))
    print(f"  Linear QR LP fallbacks (alpha > 0): {len(LINEAR_FALLBACKS)}")
    print()

    print("=" * 112)
    print("PAIRED vs Linear QR's cached MAE baseline -- skill: + helps; gap: - better")
    print("=" * 112)
    print(f"  {'h':<6}{'skill base':>11}{'+mvol':>7}{'new-old':>9}{'[95% CI]':>18}{'':>7}"
          f"{'gap base':>9}{'+mvol':>7}{'new-old':>9}{'[95% CI]':>18}{'':>7}"
          f"{'mvol importance':>17}{'[95% CI]':>18}")
    harm, draws = [], []
    for i, k in enumerate(HORIZONS):
        y = T1M[(d, k)][ctx["test"]]
        old = cb[f"1m|{d}|Linear QR|{k}"]
        clim = cb[f"1m|{d}|Climatology|{k}"]
        new = enf[i]
        ds = paired_skill_ci(y, old, new, clim, boot)
        dg = gap_paired_ci(y, old, y, new, boot)
        s_t, g_t, _ = cell_outcome(ds, dg)
        if round(ds[0], 3) != MV_PUBLISHED[k][0] or round(dg[0], 3) != MV_PUBLISHED[k][1]:
            raise SystemExit(f"[NEWF] {HLABEL[k]} does not reproduce MARKET-VOL "
                             f"({ds[0]:+.3f}/{dg[0]:+.3f} vs {MV_PUBLISHED[k]}).")
        if "WORSE" in (s_t, g_t):
            harm.append(HLABEL[k])
        po, pn, pc = _pinball_rows(y, old), _pinball_rows(y, new), _pinball_rows(y, clim)
        draws.append(np.array([100.0 * (po[ix].mean() - pn[ix].mean()) / pc[ix].mean()
                               for ix in boot]))
        lm = mods[k]
        fn = lambda Z, lm=lm: np.maximum.accumulate(
            np.column_stack([m.predict(Z) for _, m in lm]), axis=1)
        ip = importance(fn, ctx["Zte"], [len(bnames)], y, pc, boot, rng)
        print(f"  {HLABEL[k]:<6}{skill_ci(y, old, clim, boot)[0]:>+11.2f}"
              f"{skill_ci(y, new, clim, boot)[0]:>+7.2f}{ds[0]:>+9.3f}"
              f"{f'[{ds[1]:+.3f},{ds[2]:+.3f}]':>18}{s_t:>7}"
              f"{gap_ci(y, old, boot)[0]:>9.2f}{gap_ci(y, new, boot)[0]:>7.2f}{dg[0]:>+9.3f}"
              f"{f'[{dg[1]:+.3f},{dg[2]:+.3f}]':>18}{g_t:>7}"
              f"{ip[0]:>+17.3f}{f'[{ip[1]:+.3f},{ip[2]:+.3f}]':>18}")
        if k == 20:
            y20, old20, new20, clim20 = y, old, new, clim
    print("  all five paired deltas reproduce the MARKET-VOL run (asserted).")
    print()

    # net effect: mean of the five paired skill gains, resampled jointly
    pts = []
    for i, k in enumerate(HORIZONS):
        y = T1M[(d, k)][ctx["test"]]
        r_ = paired_skill_ci(y, cb[f"1m|{d}|Linear QR|{k}"], enf[i],
                             cb[f"1m|{d}|Climatology|{k}"], boot)
        pts.append(r_[0])
    net = float(np.mean(pts))
    nd = np.mean(np.vstack(draws), axis=0)
    nlo, nhi = float(np.percentile(nd, 2.5)), float(np.percentile(nd, 97.5))

    print("=" * 112)
    print("PLAIN MISS -- MAE 10h, average |actual - median guess|, sigma, held out")
    print("=" * 112)
    miss = lambda p_: np.abs(y20 - p_[:, 2])
    mo, mn_, mc = miss(old20), miss(new20), miss(clim20)
    for nm, m_ in (("Linear QR", mo), ("Climatology", mc)):
        if round(float(m_.mean()), 3) != PLAIN_MISS_REF[nm]:
            raise SystemExit(f"[NEWF] {nm} plain miss {m_.mean():.4f} does not reproduce "
                             f"PLAIN-MISS {PLAIN_MISS_REF[nm]}.")
    dd = mn_ - mo
    bd = np.array([dd[ix].mean() for ix in boot])
    print(f"  Climatology                   {mc.mean():.3f} sigma   (reproduces PLAIN-MISS)")
    print(f"  Linear QR, without market_vol {mo.mean():.3f} sigma   (reproduces PLAIN-MISS)")
    print(f"  Linear QR, with market_vol    {mn_.mean():.4f} sigma")
    print(f"  with - without: {dd.mean():+.4f} sigma [{np.percentile(bd, 2.5):+.4f}, "
          f"{np.percentile(bd, 97.5):+.4f}];  vs climatology: "
          f"{mn_.mean() - mc.mean():+.4f} sigma ({100*(mn_.mean()/mc.mean()-1):+.1f}%)")
    print()

    print("=" * 112)
    print("DECISION -- rule fixed in mvol_linear()' docstring before the run")
    print("=" * 112)
    print(f"  (a) no harm: horizons with a significantly worse measure: "
          f"{', '.join(harm) if harm else 'none'}")
    print(f"  (b) net improvement: mean paired skill gain over five horizons "
          f"{net:+.3f} [{nlo:+.3f}, {nhi:+.3f}]")
    ok = (not harm) and nlo > 0
    print(f"  VERDICT: {'ADOPT market_vol for Linear QR / MAE -- the registry rebuild is the next build' if ok else 'DO NOT ADOPT'}")
    print("  Levels are a later look at already-scored rows; paired differences are the")
    print("  measurement. Nothing in the registry was written.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("cells", "horizons", "combined",
                                        "combined_registry", "market_vol",
                                        "mvol_linear"),
                    default="cells",
                    help="cells = build both features and test at 10h. horizons = "
                         "reuse newfeat.npz and screen 1h/5h/10h. combined = all "
                         "four new columns together, exploratory, with importance. "
                         "combined_registry = the same, all four models x 5 horizons. "
                         "market_vol = build median universe volatility, 40-cell test. "
                         "mvol_linear = Linear QR / MAE, all horizons, plain miss.")
    stg = ap.parse_args().stage
    if stg == "horizons":
        horizons()
    elif stg == "combined":
        combined()
    elif stg == "combined_registry":
        combined_registry()
    elif stg == "market_vol":
        market_vol()
    elif stg == "mvol_linear":
        mvol_linear()
    else:
        main()
