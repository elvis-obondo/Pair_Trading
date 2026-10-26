"""META-LABEL v2: a one-sided flag from the envelope, with realistic stop fills.

    .venv/bin/python research/dislocation_model/meta_label_v2.py 2>&1 \
        | tee research/dislocation_model/logs/meta_label_v2.log

WHY v1 IS VOID. Its "violent" target was two-sided (it flagged likely winners
too), its cut-off flagged 86% of trades, and the ledger hard-codes every stop
fill at 1.005x. v2 flags only the ADVERSE side, from the registry's own MAE and
MFE envelopes, and replays every stop on 1-minute closes.

THE TRADES. research/exit_study/grid_run/grid_w2_s050.csv, 3,844 trades, 17 Aug
-> 21 Sep 2026, written by the engine between the one-bar entry fix and the
liquidation commit. A RULE-OUT TEST ONLY.

STEP 0 -- GATES, each stops the run on failure:
  1. LINEAR QR REFIT. MAE on the vol_48_1m set, MFE on the vol_48 set, train
     rows only, all five horizons, build_context + fit_linear + enforce_two_pass
     exactly as the registry. Held-out predictions must equal the cached ones
     (match1m / match1m_mae_vol1m) to 1e-12.
  2. SCORE EVERY TRADE with meta_label.entry_bar_features(): coverage 3,844.
     Trade predictions get the same standardisation (train mean/sd) and the
     same two-pass enforcement.
  3. REPLAY THE STOPS on the engine's own path. The engine (run_portfolio_
     backtest, exit_check_minutes=1) checks a position at every 1-minute label
     from its entry instant, plus each 30-minute close, the 30-minute check
     FIRST at a shared timestamp; a minute where either leg has no price is
     skipped; within a check the order is time stop, adverse move, take profit
     (signal_generator.generate_exit_signal); take-profit and time-stop fill at
     the actual spread. Only the stop fill was modelled (1.005x). The replay
     keeps all of that and fills the stop at the first checked price at or
     beyond the stop level, which is what a 1-minute stop actually gets.
     P&L, fees and R come from portfolio.Position.pnl -- the engine's code, not
     re-derived (unchanged since this ledger was written).
     THE ENGINE'S DATA CUT-OFF (approved by the user after the first run
     stopped here on 3 of 3,844 trades): the engine loaded 1-minute prices only
     up to its window end (cfg_end_date), so after it the engine could check
     only at its last 30-minute close. The GATE replay applies that same
     cut-off, to prove it walks the engine's path; the ANALYSIS replay uses the
     true 1-minute path, because realistic fills are the point.
     GATES: take-profit and time-stop trades reproduce the ledger's exit reason,
     exit time and R (1e-9); adverse-move trades reproduce the ledger's exit
     time and, booked at 1.005x through pnl(), the ledger's R. Reported: the
     replayed overshoot distribution.
  4. NO-STOP ARM. The same replay without the stop: take profit, 72h, or
     liquidation first. Liquidation as the current engine does it: checked
     before any other exit, at hedge_estimators.liquidation_distance(beta, 20),
     booked exactly at the liquidation level through pnl().

STEP 1 -- FLAGS, fixed now, never tuned on outcomes. Per horizon k (0.5, 1, 2,
5, 10h), from each trade's predicted envelope:
  A_k  predicted MAE q95 above the 80th percentile of the 3,844 trades
  B_k  predicted MAE q50 / predicted MFE q50 above its 80th percentile.
       Where predicted MFE q50 <= 0 the model expects no favourable move at
       all, so the ratio is set to +inf (the most adverse-dominated); counted.

STEP 2 -- ARMS on replayed fills, each against taking every trade:
  SKIP flagged trades dropped (slots never backfilled); HALF flagged at 0.5x.
  20 cells = 10 flags x 2 arms. Per cell: mean R, total R, total $ (the
  engine's net dollars from pnl(): move x leg-A notional less round-trip cost
  on gross -- the brief's "gross_notional x net return" computed by the engine
  rather than re-derived), trade count, win rate; paired day-clustered 95%
  intervals (trade entry day, 1,000 resamples); random null (same count,
  1,000 draws) -> the arm's percentile on total R and on total $.
Also: the share of replayed overshoot cost (R lost versus a fill exactly at the
stop level) carried by flagged trades against their share of trades; the
stopping premium (with-stop R minus no-stop R) for flagged and unflagged trades.
The same scoreboard for trades entered beyond 3.5 sigma, separately.

READING RULE, fixed in the brief. SURVIVES if at least 3 of 20 cells beat the
null's 95th percentile on BOTH total R and total $, the winners cluster in one
flag, and no cell is significantly worse on dollars. Gaps filled now:
"cluster" = at least two-thirds of the winning cells share a flag (A or B);
"significantly worse on dollars" = the paired $ interval entirely below zero.
A survivor earns only a full engine run with the rule wired in; it is not a
result. Anything else is reported as found.

MULTIPLE-TESTING CHECKS, reported BESIDE the reading rule, never replacing it
(added at the user's request before any result was read). For the 20-cell
family, on DAILY P&L (trade entry day; an arm's dropped trades contribute 0),
once on total R and once on dollars, each arm against take-everything:
  Hansen SPA   arch.bootstrap.SPA, losses = -daily P&L; H0: no arm beats
               take-everything. Lower / consistent / upper p-values.
  StepM        arch.bootstrap.StepM (Romano-Wolf). arch returns only the set of
               superior arms at a given size, so each arm's ADJUSTED p-value is
               the smallest size on a 0.005 grid at which StepM keeps it, with
               the bootstrap seed fixed so every size sees the same draws.
LIVE-FILL STAGE (--stage fills), the user's Option 2, added after the
once-a-minute run: each replayed stop keeps its replayed TIME (the 1-minute
path decides whether a trade stops, takes profit or times out) but its FILL is
drawn, with replacement, from the 316 stop-outs measured in paper trading
with the tick-watching monitor (research/from_vm/scanner_trades.csv,
overshoot_ratio, exit_reason adverse_move, blind_gap_seconds 0). One draw per
stop per seed; 200 seeds (0..199); every headline number reported as median
and range over seeds. Stop R and $ are LINEAR in the fill ratio, so each is
evaluated exactly through the engine's pnl() at ratios 0 and 1 and
interpolated. Added column: dollars at constant size -- every trade rescaled
to the median gross notional of the 3,844 (exact: pnl is linear in size).
NOTE: random fill assignment removes any link between a trade's violence and
its fill quality, so if violent trades really fill worse, this understates
what skipping them saves. The scoreboard is computed on daily sums with
bootstrap day COUNTS -- arithmetically identical to resampling trades by day.
The reading rule is unchanged: it is judged per seed, and the share of seeds
on which it survives is reported.

Settings, fixed now: stationary bootstrap with block_size=1 -- i.e. days
resampled independently, the same assumption as every day-clustered interval
in this project; 10,000 reps; studentized; seed 20261012.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
from envelope import (FP_KEY, HLABEL, HORIZONS, QUANTILES, build_context,
                      build_targets_1m, build_targets_30m, cache_fingerprint,
                      enforce_two_pass, fit_linear, flat_targets, scan_1m_coverage,
                      select_1m_subset)
from meta_label import LEDGER, entry_bar_features
from vol1m import MAE_CACHE

LEVERAGE = 20.0
SHARE = 0.20
N_NULL = 1000
N_BOOT = 1000
J50, J95 = QUANTILES.index(0.5), QUANTILES.index(0.95)
ENVNAMES = ["vol_48", "vratio", "vol_slope", "sandwich", "off_mark"]
STATE = os.path.join(paths.DATASETS, "meta_label_v2_state.npz")
LIVE_LEDGER = os.path.join(paths.RESEARCH, "from_vm", "scanner_trades.csv")
N_SEEDS = 200


# ---------------------------------------------------------------- Step 0.1
def refit_registry_linear():
    """Linear QR per direction on train only; returns per direction the fitted
    models per horizon and the train standardisation. Gate: held-out
    predictions equal the cache."""
    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    day = meta.day.to_numpy()
    cov = scan_1m_coverage(meta, verbose=False)
    used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(used)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    Xm = X[rows].copy()
    Xa = X[rows].copy()
    Xa[:, 0] = v48["vol_48_1m"]
    caches = {"MFE": np.load(paths.envelope_preds("match1m"), allow_pickle=False),
              "MAE": np.load(paths.envelope_preds(MAE_CACHE), allow_pickle=False)}
    fps = {"MFE": cache_fingerprint([rows], flat_targets({"30m": T30, "1m": T1M}), Xm),
           "MAE": cache_fingerprint([rows], flat_targets(
               {("MAE", k): T1M[("MAE", k)] for k in HORIZONS}), Xa)}
    out = {}
    for d, Xd in (("MFE", Xm), ("MAE", Xa)):
        if str(caches[d][FP_KEY]) != fps[d]:
            raise SystemExit(f"[META2] {d} cache fingerprint does not match.")
        ctx = build_context(np.ones(len(rows), bool), Xd, day[rows], Y[rows, 0],
                            verbose=(d == "MFE"))
        models, raw = {}, []
        for k in HORIZONS:
            lm = []
            raw.append(fit_linear(ctx, T1M[(d, k)], f"1m/{d}/{HLABEL[k]}/meta2", models=lm))
            models[k] = lm
            print(f"  fitted Linear QR {d} {HLABEL[k]}", flush=True)
        enf, _, _ = enforce_two_pass(np.stack(raw))
        err = max(float(np.max(np.abs(enf[i] - caches[d][f"1m|{d}|Linear QR|{k}"])))
                  for i, k in enumerate(HORIZONS))
        print(f"  GATE 1 {d}: refit vs cached held-out predictions, worst {err:.2e}")
        if err > 1e-12:
            raise SystemExit(f"[META2] STOP -- the {d} Linear QR refit does not "
                             f"reproduce the cache.")
        tr = ctx["train"]
        mu = Xd[tr].mean(0)
        sd = Xd[tr].std(0)
        sd[sd == 0] = 1.0
        if float(np.max(np.abs((Xd[ctx["test"]] - mu) / sd - ctx["Zte"]))) > 0:
            raise SystemExit("[META2] standardisation does not match build_context.")
        out[d] = (models, mu, sd)
    return out


def predict_trades(reg, F):
    """Two-pass-enforced (horizon, trade, quantile) predictions per direction."""
    from tail_classifier import FEATURES
    cols = {"MFE": [FEATURES.index(n) for n in ENVNAMES],
            "MAE": [FEATURES.index("vol_48_1m")] + [FEATURES.index(n) for n in ENVNAMES[1:]]}
    P = {}
    for d, (models, mu, sd) in reg.items():
        Z = (F[:, cols[d]] - mu) / sd
        raw = np.stack([np.column_stack([m.predict(Z) for _, m in models[k]])
                        for k in HORIZONS])
        P[d], _, _ = enforce_two_pass(raw)
    return P


# ---------------------------------------------------------------- Step 0.3/0.4
def replay(L, stop=True, engine_end=None):
    """Walk every trade on the engine's own check sequence. Returns exit reason,
    exit spread, exit time (as hours held) per trade. engine_end: drop every
    check whose price label is after it, as the engine's data did."""
    import universe_panel
    import intrabar
    from hedge_estimators import liquidation_distance
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    tick = sorted(set(L.ticker_a) | set(L.ticker_b))
    lo, hi = L.t_open.min() - pd.Timedelta(hours=1), L.t_open.max() + pd.Timedelta(hours=74)
    fine = intrabar.load_panel(tick, start=lo, end=hi, timeframe="1m")
    if fine.index.tz is not None:
        fine.index = fine.index.tz_convert("UTC").tz_localize(None)
    fine = fine.reindex(pd.date_range(lo.floor("min"), hi.ceil("min"), freq="1min"))
    f0 = fine.index[0]
    F1 = {t: fine[t].to_numpy(float) if t in fine.columns else None for t in tick}
    P30 = {t: panel[t] for t in tick}
    nblk = 145                                   # 72.5h of 30-minute blocks
    m_off = (np.arange(nblk)[:, None] * 30 + np.arange(30)[None, :])   # minutes
    h1 = m_off / 60.0
    h30 = (np.arange(1, nblk + 1) * 30) / 60.0
    hours = np.concatenate([h1, h30[:, None]], axis=1).ravel()
    n = len(L)
    reason = np.empty(n, dtype=object)
    xs = np.full(n, np.nan)
    xh = np.full(n, np.nan)
    for r in range(n):
        t = L.iloc[r]
        a, b = t.ticker_a, t.ticker_b
        if F1[a] is None or F1[b] is None:
            raise SystemExit(f"[META2] no 1m data for {a}/{b}")
        k0 = int((t.t_open - f0) / pd.Timedelta(minutes=1))
        ia = F1[a][k0 + m_off]
        ib = F1[b][k0 + m_off]
        lab30 = t.t_open + pd.to_timedelta(np.arange(nblk) * 30, unit="min")
        pa30 = P30[a].reindex(lab30).to_numpy(float)
        pb30 = P30[b].reindex(lab30).to_numpy(float)
        pa = np.concatenate([ia, pa30[:, None]], axis=1).ravel()
        pb = np.concatenate([ib, pb30[:, None]], axis=1).ravel()
        ok = np.isfinite(pa) & np.isfinite(pb)
        if engine_end is not None:
            lab1 = t.t_open + pd.to_timedelta(m_off.ravel(), unit="min")
            labs = np.concatenate([lab1.to_numpy().reshape(nblk, 30),
                                   lab30.to_numpy()[:, None]], axis=1).ravel()
            ok &= labs <= np.datetime64(engine_end)
        al, be = t.alpha_at_entry, t.beta_at_entry
        sp = pa - al - be * pb
        e, mu = t.entry_spread, t.mu_at_entry
        stopd = 0.5 * t.sigma_at_entry
        tp = e - 1.0 * (e - mu)
        hi_ = e > mu
        d = -1.0 if hi_ else 1.0
        c_time = ok & (hours >= 72.0)
        if hi_:
            c_adv = ok & (sp >= e + stopd)
            c_tp = ok & (sp <= tp)
        else:
            c_adv = ok & (sp <= e - stopd)
            c_tp = ok & (sp >= tp)
        if not stop:
            liq = float(liquidation_distance(be, LEVERAGE))
            c_liq = ok & (d * (sp - e) <= -liq)
            c_adv = c_liq
        anyc = c_time | c_adv | c_tp
        if not anyc.any():
            reason[r] = "open"
            continue
        i = int(np.argmax(anyc))
        xh[r] = hours[i]
        if not stop and c_adv[i]:
            reason[r], xs[r] = "liquidated", e - d * liq
        elif c_time[i] and (stop or not c_adv[i]):
            reason[r], xs[r] = "time_stop", sp[i]
        elif c_adv[i]:
            reason[r], xs[r] = "adverse_move", sp[i]
        else:
            reason[r], xs[r] = "take_profit", sp[i]
    return reason, xs, xh


def position(t):
    from portfolio import Position
    sig = dict(entry_spread=t.entry_spread, mu_at_entry=t.mu_at_entry,
               sigma_at_entry=t.sigma_at_entry, alpha_at_entry=t.alpha_at_entry,
               beta_at_entry=t.beta_at_entry)
    siz = dict(leg_a_notional=t.leg_a_notional, leg_b_notional=t.leg_b_notional,
               gross_notional=t.gross_notional, margin=t.margin)
    return Position(t.trade_num, t.ticker_a, t.ticker_b, sig, siz, t.t_open, 0.5)


def book(L, xs):
    """(net $, R) per trade through the engine's Position.pnl."""
    usd, R = np.full(len(L), np.nan), np.full(len(L), np.nan)
    for r in range(len(L)):
        if np.isfinite(xs[r]):
            net, _, rr = position(L.iloc[r]).pnl(float(xs[r]))
            usd[r], R[r] = net, rr
    return usd, R


# ---------------------------------------------------------------- Step 2
def boot_days(day, n=N_BOOT, seed=5):
    du = np.unique(day)
    pos = {d: np.flatnonzero(day == d) for d in du}
    rb = np.random.default_rng(seed)
    return [np.concatenate([pos[d] for d in rb.choice(du, len(du), replace=True)])
            for _ in range(n)]


def stats(R, U, w, keep):
    rr, uu = (R * w)[keep], (U * w)[keep]
    return np.array([rr.mean(), rr.sum(), uu.sum(), keep.sum(), (rr > 0).mean()])


def scoreboard(tag, R, U, flags, day, rng):
    """20 cells: arms x flags, paired intervals and random null."""
    n = len(R)
    ones, allk = np.ones(n), np.ones(n, bool)
    base = stats(R, U, ones, allk)
    boot = boot_days(day)
    bb = np.array([stats(R[ix], U[ix], ones[ix], allk[ix]) for ix in boot])
    print(f"  {tag}: ALL  {n:,} trades  mean R {base[0]:+.4f}  total R {base[1]:+.1f}  "
          f"total $ {base[2]:+,.0f}  win {base[4]:.3f}")
    print(f"  {'cell':<12}{'flag%':>6}{'mean R':>9}{'d mean R [95% CI]':>28}{'total R':>9}"
          f"{'d total R [95% CI]':>28}{'total $':>10}{'d $ [95% CI]':>30}{'n':>6}{'win':>7}"
          f"{'pct R':>7}{'pct $':>7}")
    res = {}
    for fname, fl in flags.items():
        nf = int(fl.sum())
        draws = [rng.choice(n, nf, replace=False) for _ in range(N_NULL)]
        for arm in ("SKIP", "HALF"):
            w = np.where(fl, 0.5, 1.0) if arm == "HALF" else ones
            keep = ~fl if arm == "SKIP" else allk
            s = stats(R, U, w, keep)
            dd = np.array([stats(R[ix], U[ix], w[ix], keep[ix]) for ix in boot]) - bb
            ci = np.percentile(dd, [2.5, 97.5], axis=0)
            nv = []
            for pk in draws:
                m = np.zeros(n, bool)
                m[pk] = True
                nv.append(stats(R, U, np.where(m, 0.5, 1.0) if arm == "HALF" else ones,
                                ~m if arm == "SKIP" else allk))
            nv = np.array(nv)
            pR = 100.0 * (nv[:, 1] < s[1]).mean()
            pU = 100.0 * (nv[:, 2] < s[2]).mean()
            beats = s[1] > np.percentile(nv[:, 1], 95) and s[2] > np.percentile(nv[:, 2], 95)
            worse = ci[1, 2] < 0
            res[(fname, arm)] = dict(s=s, d=s - base, ci=ci, pR=pR, pU=pU, beats=beats,
                                     worse=worse)
            dm, dt, du = (s - base)[:3]
            print(f"  {fname+' '+arm:<12}{100*fl.mean():>5.1f}%{s[0]:>+9.4f}"
                  f"{f'{dm:+.4f} [{ci[0,0]:+.4f},{ci[1,0]:+.4f}]':>28}{s[1]:>+9.1f}"
                  f"{f'{dt:+.1f} [{ci[0,1]:+.1f},{ci[1,1]:+.1f}]':>28}{s[2]:>+10,.0f}"
                  f"{f'{du:+,.0f} [{ci[0,2]:+,.0f},{ci[1,2]:+,.0f}]':>30}{int(s[3]):>6}"
                  f"{s[4]:>7.3f}{pR:>6.1f}%{pU:>6.1f}%"
                  f"{'  BEATS' if beats else ''}{'  $WORSE' if worse else ''}")
    return res


def spa_stepm(R, U, flags, day):
    """Hansen SPA and Romano-Wolf StepM on daily P&L, 20 arms vs take-everything."""
    from arch.bootstrap import SPA, StepM
    days = np.unique(day)
    pos = np.searchsorted(days, day)
    ones = np.ones(len(R))

    def daily(v):
        return np.bincount(pos, weights=v, minlength=len(days))

    out = {}
    for unit, X_ in (("total R", R), ("dollars", U)):
        bench = daily(X_)
        cols, names = [], []
        for fname, fl in flags.items():
            cols.append(daily(np.where(fl, 0.0, X_)))
            names.append(f"{fname} SKIP")
            cols.append(daily(np.where(fl, 0.5, 1.0) * X_))
            names.append(f"{fname} HALF")
        M_ = pd.DataFrame(np.column_stack(cols), columns=names)
        spa = SPA(-bench, -M_, block_size=1, reps=10_000, seed=20261012)
        spa.compute()
        grid = np.round(np.arange(0.005, 1.0001, 0.005), 3)
        padj = {n_: np.nan for n_ in names}
        for a in grid:
            sm = StepM(-bench, -M_, size=float(a), block_size=1, reps=10_000, seed=20261012)
            try:
                sm.compute()
                kept = list(sm.superior_models)
            except ValueError:
                # arch 8.0.0 StepM bug: its step-down loop tests the LAST step's
                # count, not the running total, so once every arm has been judged
                # superior it re-runs SPA on an empty set and raises. Reaching
                # that point means every arm is superior at this size.
                kept = names
            for n_ in kept:
                if np.isnan(padj[n_]):
                    padj[n_] = float(a)
            if not any(np.isnan(v) for v in padj.values()):
                break
        out[unit] = (spa.pvalues, padj, len(days))
    return out


def main():
    t0 = time.time()
    print("=" * 140)
    print("META-LABEL v2 -- a one-sided envelope flag, on replayed 1-minute stop fills")
    print("=" * 140)
    L = pd.read_csv(LEDGER, low_memory=False)
    L["t_open"] = pd.to_datetime(L.opened_at)
    L["t_close"] = pd.to_datetime(L.closed_at)
    beyond = np.abs(L.z_at_entry.to_numpy(float)) > 3.5
    wk = L.t_open.dt.to_period("W")
    gn = L.groupby(wk).gross_notional.median()
    print("  STATED BEFORE ANY NUMBER:")
    print("  - all 10 slots are full 86.5% of the time: this can rule the idea OUT, not IN")
    print("  - 17 Aug - 21 Sep is the previously identified favourable window")
    print(f"  - {100*beyond.mean():.0f}% of trades entered beyond 3.5 sigma ({int(beyond.sum()):,}),"
          f" unlike the first-crossing training episodes; reported separately")
    print(f"  - position size grew over the window: median gross notional by week "
          + ", ".join(f"{v:,.0f}" for v in gn.to_numpy())
          + " -- dollar results are weighted to the last weeks")
    print()

    # ---- gate 1 ----
    print("STEP 0.1 -- refit Linear QR exactly as the registry")
    reg = refit_registry_linear()
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- gate 2 ----
    print("STEP 0.2 -- score every trade at its own entry bar")
    F, cause, M_like, W, audit = entry_bar_features(L)
    nc = int((cause == "").sum())
    print(f"  complete feature rows {nc:,} of {len(L):,}")
    if nc != len(L):
        raise SystemExit("[META2] STOP -- feature coverage is not 3,844.")
    gb = np.abs(M_like.beta.to_numpy() - L.beta_at_entry.to_numpy())
    gs = np.abs(M_like.sigma.to_numpy() / L.sigma_at_entry.to_numpy() - 1)
    print(f"  entry geometry recomputed vs the ledger's own: beta max |diff| {gb.max():.2e}, "
          f"sigma max relative diff {gs.max():.2e}")
    P = predict_trades(reg, F)
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- gate 3 ----
    print("STEP 0.3 -- replay every exit on the engine's own check sequence")
    eend = pd.Timestamp(L.cfg_end_date.iloc[0])
    rs_, xs, xh = replay(L, stop=True, engine_end=eend)
    usd, R = book(L, xs)
    print(f"  gate replay with the engine's 1-minute data cut-off at {eend}")
    led_r = L.r.to_numpy(float)
    led_reason = L.exit_reason.to_numpy()
    led_h = L.hours_held.to_numpy(float)
    same_reason = rs_ == led_reason
    tpts = np.isin(led_reason, ["take_profit", "time_stop"])
    ok_tp = tpts & same_reason & (np.abs(R - led_r) <= 1e-9) & (np.abs(xh - led_h) <= 1e-6)
    print(f"  exit reason agrees: {int(same_reason.sum()):,} of {len(L):,}")
    print(f"  take-profit / time-stop trades reproducing reason, exit time and R (1e-9): "
          f"{int(ok_tp.sum()):,} of {int(tpts.sum()):,}")
    adv = led_reason == "adverse_move"
    st_book = np.array([position(L.iloc[r]).pnl(
        L.entry_spread.iloc[r] - position(L.iloc[r]).direction * 0.5
        * L.sigma_at_entry.iloc[r] * 1.005)[2] if adv[r] else np.nan for r in range(len(L))])
    ok_adv = adv & same_reason & (np.abs(xh - led_h) <= 1e-6) & (np.abs(st_book - led_r) <= 1e-9)
    print(f"  adverse-move trades reproducing exit time, and the ledger R when booked at "
          f"1.005x through pnl(): {int(ok_adv.sum()):,} of {int(adv.sum()):,}")
    if ok_tp.sum() != tpts.sum() or ok_adv.sum() != adv.sum():
        bad = np.flatnonzero((tpts & ~ok_tp) | (adv & ~ok_adv))[:5]
        for r in bad:
            print(f"    trade {L.trade_num.iloc[r]}: ledger {led_reason[r]} {led_h[r]:.4f}h "
                  f"R {led_r[r]:+.6f}; replay {rs_[r]} {xh[r]:.4f}h R {R[r]:+.6f}")
        raise SystemExit("[META2] STOP -- the replay does not reproduce the ledger.")
    print("  -> PASS: the replay walks exactly the engine's path")
    # the ANALYSIS replay: the true 1-minute path, no cut-off
    rs_g, R_g = rs_.copy(), R.copy()
    rs_, xs, xh = replay(L, stop=True)
    usd, R = book(L, xs)
    chg = np.flatnonzero((rs_ != rs_g) | (np.abs(R - R_g) > 1e-9))
    print(f"  analysis replay on the true 1-minute path: {len(chg)} trade(s) differ from the "
          f"gate replay" + (": " + ", ".join(f"#{L.trade_num.iloc[r]} {R_g[r]:+.3f}->{R[r]:+.3f}"
                                               for r in chg) if len(chg) else ""))
    sto = rs_ == "adverse_move"
    dirn = np.where(L.entry_spread > L.mu_at_entry, -1.0, 1.0)
    ov = -dirn * (xs - L.entry_spread.to_numpy()) / (0.5 * L.sigma_at_entry.to_numpy())
    print(f"  replayed stop overshoot ({int(sto.sum()):,} stops): median {np.median(ov[sto]):.3f}x,"
          f" mean {ov[sto].mean():.3f}x, p90 {np.percentile(ov[sto], 90):.3f}x "
          f"(the ledger booked 1.005x)")
    R_exact = np.array([position(L.iloc[r]).pnl(L.entry_spread.iloc[r] - dirn[r] * 0.5
                        * L.sigma_at_entry.iloc[r])[2] if sto[r] else np.nan
                        for r in range(len(L))])
    ocost = np.where(sto, R_exact - R, 0.0)
    print(f"  ALL trades: ledger mean R {led_r.mean():+.4f} (total {led_r.sum():+.1f});  "
          f"replayed mean R {R.mean():+.4f} (total {R.sum():+.1f}), replayed $ {usd.sum():+,.0f}")
    print(f"  overshoot cost, replayed fills vs exact stop fills: {ocost.sum():.1f} R in total")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- gate 4 ----
    print("STEP 0.4 -- the no-stop arm (take profit, 72h, or liquidation at 20x)")
    rn, xn, hn = replay(L, stop=False)
    usd_n, R_n = book(L, xn)
    for k_, v in pd.Series(rn).value_counts().items():
        print(f"  {k_:<14}{v:>6,}  ({100*v/len(L):.1f}%)")
    print(f"  no-stop mean R {np.nanmean(R_n):+.4f} (total {np.nansum(R_n):+.1f}), "
          f"$ {np.nansum(usd_n):+,.0f};  with-stop mean R {R.mean():+.4f}")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- flags ----
    print("=" * 140)
    print("STEP 1 -- FLAGS (top 20% of trades by the prediction; never tuned on outcomes)")
    print("=" * 140)
    flags = {}
    for i, k in enumerate(HORIZONS):
        a = P["MAE"][i][:, J95]
        flags[f"A {HLABEL[k]}"] = a > np.quantile(a, 1 - SHARE)
        mae50, mfe50 = P["MAE"][i][:, J50], P["MFE"][i][:, J50]
        ratio = np.where(mfe50 > 0, mae50 / np.where(mfe50 > 0, mfe50, 1.0), np.inf)
        cutb = np.quantile(ratio[np.isfinite(ratio)], 1 - SHARE) if np.isfinite(ratio).any() else np.inf
        flags[f"B {HLABEL[k]}"] = ratio > cutb
        print(f"  {HLABEL[k]:<5} A: MAE q95 cut {np.quantile(a, 1-SHARE):.3f} sigma, "
              f"{int(flags[f'A {HLABEL[k]}'].sum())} flagged;  B: MFE q50 <= 0 on "
              f"{int((mfe50 <= 0).sum())} trades (ratio := +inf), cut {cutb:.3f}, "
              f"{int(flags[f'B {HLABEL[k]}'].sum())} flagged;  A and B overlap "
              f"{int((flags[f'A {HLABEL[k]}'] & flags[f'B {HLABEL[k]}']).sum())}")
    print()

    day = L.t_open.dt.floor("D").to_numpy()
    # per-trade state for the live-fill stage: stop R and $ are linear in the
    # fill ratio, so pnl() at ratios 0 and 1 pins them exactly
    def at_ratio(rho):
        out = np.full((2, len(L)), np.nan)
        for r in np.flatnonzero(sto):
            net, _, rr = position(L.iloc[r]).pnl(L.entry_spread.iloc[r] - dirn[r] * 0.5
                                                 * L.sigma_at_entry.iloc[r] * rho)
            out[:, r] = (rr, net)
        return out
    z0, z1 = at_ratio(0.0), at_ratio(1.0)
    np.savez_compressed(STATE, R=R, usd=usd, R_n=R_n, usd_n=usd_n, sto=sto,
                        aR=z0[0], bR=z1[0] - z0[0], aU=z0[1], bU=z1[1] - z0[1],
                        gross=L.gross_notional.to_numpy(float), day=day,
                        beyond=beyond, F=np.column_stack(list(flags.values())),
                        fnames=np.array(list(flags.keys())))
    print(f"  [WROTE] {os.path.relpath(STATE, paths.RESEARCH)} -- per-trade state for --stage fills")
    rng = np.random.default_rng(20261012)
    print("=" * 140)
    print("STEP 2 -- THE SCOREBOARD, all 3,844 trades, replayed fills. d = arm - ALL; "
          "pct = percentile in the random null")
    print("=" * 140)
    res = scoreboard("ALL TRADES", R, usd, flags, day, rng)
    print()

    print("=" * 140)
    print("WHERE THE LOSS LIVES -- overshoot cost and the stopping premium, by flag")
    print("=" * 140)
    prem = R - R_n
    print(f"  {'flag':<10}{'trade share':>12}{'overshoot-cost share':>22}"
          f"{'premium flagged':>17}{'premium unflagged':>19}   (premium = with-stop R - no-stop R, mean)")
    for fname, fl in flags.items():
        print(f"  {fname:<10}{fl.mean():>12.3f}{ocost[fl].sum()/ocost.sum():>22.3f}"
              f"{np.nanmean(prem[fl]):>+17.4f}{np.nanmean(prem[~fl]):>+19.4f}")
    print(f"  all trades: premium {np.nanmean(prem):+.4f}")
    print()

    print("=" * 140)
    print(f"THE SAME SCOREBOARD, trades entered beyond 3.5 sigma only ({int(beyond.sum()):,})")
    print("=" * 140)
    res35 = scoreboard(">3.5 SIGMA", R[beyond], usd[beyond],
                       {k: v[beyond] for k, v in flags.items()}, day[beyond], rng)
    print()

    print("=" * 140)
    print("READING RULE -- fixed in the brief (gaps filled in the docstring)")
    print("=" * 140)
    win = [c for c, v in res.items() if v["beats"]]
    worse = [c for c, v in res.items() if v["worse"]]
    by_flag = pd.Series([c[0][0] for c in win]).value_counts()
    cluster = len(win) > 0 and by_flag.iloc[0] >= (2.0 / 3.0) * len(win)
    print(f"  cells beating the null's 95th pct on BOTH total R and $: {len(win)} of 20 "
          f"(about 1 expected by chance){': ' + ', '.join(' '.join(c) for c in win) if win else ''}")
    print(f"  winners clustered in one flag (>= 2/3): {cluster}"
          f"{' (' + ', '.join(f'{k}:{v}' for k, v in by_flag.items()) + ')' if win else ''}")
    print(f"  cells significantly worse on dollars: {len(worse)}"
          f"{': ' + ', '.join(' '.join(c) for c in worse) if worse else ''}")
    surv = len(win) >= 3 and cluster and not worse
    print(f"  VERDICT: {'SURVIVES -- earns only a full engine run with the rule wired in' if surv else 'DOES NOT SURVIVE -- reported as found'}")
    print()
    print("  MULTIPLE-TESTING CHECKS, beside the rule (not replacing it): daily P&L, 20 arms")
    print("  vs take-everything; Hansen SPA and Romano-Wolf StepM (arch.bootstrap)")
    mt = spa_stepm(R, usd, flags, day)
    for unit, (pv, padj, nd) in mt.items():
        print(f"  {unit} ({nd} days): SPA p-values lower {pv['lower']:.4f}  consistent "
              f"{pv['consistent']:.4f}  upper {pv['upper']:.4f}")
        best = sorted(padj.items(), key=lambda kv: (np.inf if np.isnan(kv[1]) else kv[1]))
        print(f"    StepM adjusted p (0.005 grid; '>1' = never kept): " + ", ".join(
            f"{k} {('>1' if np.isnan(v) else f'{v:.3f}')}" for k, v in best))
    win35 = [c for c, v in res35.items() if v["beats"]]
    print(f"  (beyond 3.5 sigma, reported not gated: {len(win35)} of 20 cells beat the null on both)")
    print("  Nothing in the registry or live system was touched.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 140)


# ------------------------------------------------------------ live-fill stage
_G = {}


def _init_worker():
    z = np.load(STATE, allow_pickle=False)
    G = {k: z[k] for k in z.files}
    d = pd.read_csv(LIVE_LEDGER)
    st = d[(d.exit_reason == "adverse_move")
           & (pd.to_numeric(d.blind_gap_seconds, errors="coerce").fillna(0) == 0)]
    G["live"] = pd.to_numeric(st.overshoot_ratio, errors="coerce").dropna().to_numpy(float)
    days = np.unique(G["day"])
    G["pos"] = np.searchsorted(days, G["day"])
    G["nd"] = len(days)
    # the same day resamples as every interval here (boot_days, seed 5), as counts
    du = days
    rb = np.random.default_rng(5)
    G["C"] = np.array([np.bincount(rb.choice(len(du), len(du), replace=True),
                                   minlength=len(du)) for _ in range(N_BOOT)], float)
    # null draws, fixed per flag and shared by every seed
    rn = np.random.default_rng(20261012)
    n = len(G["R"])
    G["picks"] = [np.array([rn.choice(n, int(G["F"][:, j].sum()), replace=False)
                            for _ in range(N_NULL)]) for j in range(G["F"].shape[1])]
    G["medgross"] = float(np.median(G["gross"]))
    _G.update(G)


def _cells(R, U, Uc, F, fnames, pos, nd, C, picks, mask=None):
    """Every cell, vectorised. Returns dict per (flag, arm)."""
    if mask is not None:
        R, U, Uc, F, pos = R[mask], U[mask], Uc[mask], F[mask], pos[mask]
    n = len(R)
    win = (R > 0).astype(float)
    dsum = lambda v: np.bincount(pos, weights=v, minlength=nd)
    base = {q: dsum(v) for q, v in (("R", R), ("U", U), ("Uc", Uc), ("n", np.ones(n)), ("w", win))}
    bb = {q: C @ v for q, v in base.items()}
    tot = {q: v.sum() for q, v in base.items()}
    out = {}
    for j, fname in enumerate(fnames):
        fl = F[:, j].astype(bool)
        nf = int(fl.sum())
        if mask is None:
            pk = picks[j]
        else:
            rr = np.random.default_rng(20261012 + j)
            pk = np.array([rr.choice(n, nf, replace=False) for _ in range(N_NULL)])
        for arm in ("SKIP", "HALF"):
            if arm == "SKIP":
                arm_d = {q: dsum(np.where(fl, 0.0, v)) for q, v in
                         (("R", R), ("U", U), ("Uc", Uc), ("n", np.ones(n)), ("w", win))}
            else:
                arm_d = {q: dsum(np.where(fl, 0.5, 1.0) * v) for q, v in
                         (("R", R), ("U", U), ("Uc", Uc))}
                arm_d["n"], arm_d["w"] = base["n"], base["w"]
            at = {q: v.sum() for q, v in arm_d.items()}
            ab = {q: C @ v for q, v in arm_d.items()}
            mR, mR_b = at["R"] / at["n"], ab["R"] / ab["n"]
            bmR_b = bb["R"] / bb["n"]
            ci = lambda x: np.percentile(x, [2.5, 97.5])
            res = dict(dmean=mR - tot["R"] / tot["n"], dtotR=at["R"] - tot["R"],
                       dU=at["U"] - tot["U"], dUc=at["Uc"] - tot["Uc"],
                       ci_mean=ci(mR_b - bmR_b), ci_R=ci(ab["R"] - bb["R"]),
                       ci_U=ci(ab["U"] - bb["U"]), ci_Uc=ci(ab["Uc"] - bb["Uc"]),
                       n=at["n"], win=at["w"] / at["n"])
            for q, v in (("R", R), ("U", U), ("Uc", Uc)):
                ps = v[pk].sum(1)
                nul = tot[q] - (ps if arm == "SKIP" else 0.5 * ps)
                res["pct_" + q] = 100.0 * (nul < at[q]).mean()
                res["beat_" + q] = at[q] > np.percentile(nul, 95)
            res["beats"] = res["beat_R"] and res["beat_U"]
            res["worseU"] = res["ci_U"][1] < 0
            out[(fname, arm)] = res
    return out, tot


def _one_seed(seed):
    from arch.bootstrap import SPA, StepM
    G = _G
    rng = np.random.default_rng(seed)
    sto = G["sto"].astype(bool)
    rho = G["live"][rng.integers(len(G["live"]), size=len(G["R"]))]
    R = np.where(sto, G["aR"] + G["bR"] * rho, G["R"])
    U = np.where(sto, G["aU"] + G["bU"] * rho, G["usd"])
    Uc = U * G["medgross"] / G["gross"]
    F, fnames = G["F"], [str(x) for x in G["fnames"]]
    cells, tot = _cells(R, U, Uc, F, fnames, G["pos"], G["nd"], G["C"], G["picks"])
    cells35, _ = _cells(R, U, Uc, F, fnames, G["pos"], G["nd"], G["C"], G["picks"],
                        mask=G["beyond"].astype(bool))
    Rex = np.where(sto, G["aR"] + G["bR"], 0.0)
    ocost = np.where(sto, Rex - R, 0.0)
    prem = R - G["R_n"]
    where = {f: (ocost[F[:, j].astype(bool)].sum() / ocost.sum(),
                 np.nanmean(prem[F[:, j].astype(bool)]), np.nanmean(prem[~F[:, j].astype(bool)]))
             for j, f in enumerate(fnames)}
    # SPA and StepM on daily P&L
    mt = {}
    for unit, X_ in (("R", R), ("U", U)):
        dsum = lambda v: np.bincount(G["pos"], weights=v, minlength=G["nd"])
        bench = dsum(X_)
        cols, names = [], []
        for j, f in enumerate(fnames):
            fl = F[:, j].astype(bool)
            cols += [dsum(np.where(fl, 0.0, X_)), dsum(np.where(fl, 0.5, 1.0) * X_)]
            names += [f"{f} SKIP", f"{f} HALF"]
        M_ = pd.DataFrame(np.column_stack(cols), columns=names)
        spa = SPA(-bench, -M_, block_size=1, reps=10_000, seed=20261012)
        spa.compute()
        padj = {n_: np.nan for n_ in names}
        for a in np.round(np.arange(0.005, 1.0001, 0.005), 3):
            sm = StepM(-bench, -M_, size=float(a), block_size=1, reps=10_000, seed=20261012)
            try:
                sm.compute()
                kept = list(sm.superior_models)
            except ValueError:      # arch 8.0.0 StepM empty-set bug; see spa_stepm
                kept = names
            for n_ in kept:
                if np.isnan(padj[n_]):
                    padj[n_] = float(a)
            if not any(np.isnan(v) for v in padj.values()):
                break
        mt[unit] = (dict(spa.pvalues), padj)
    stop_ov = rho[sto]
    return dict(seed=seed, tot=tot, cells=cells, cells35=cells35, where=where, mt=mt,
                ov=(np.median(stop_ov), stop_ov.mean(), np.percentile(stop_ov, 90)))


def fills():
    import multiprocessing as mp
    t0 = time.time()
    print("=" * 140)
    print("META-LABEL v2 -- LIVE-FILL STAGE: every stop's fill drawn from the 316 measured "
          "paper-trading stop-outs, 200 seeds")
    print("=" * 140)
    _init_worker()
    G = _G
    lv = G["live"]
    print(f"  live fills: {len(lv)} stop-outs, median {np.median(lv):.4f}x, mean {lv.mean():.4f}x, "
          f"p90 {np.percentile(lv, 90):.4f}x, max {lv.max():.4f}x")
    print(f"  {int(G['sto'].sum()):,} replayed stops keep their replayed time; each gets a drawn "
          f"fill. Constant-size $ uses the median gross notional {G['medgross']:,.2f}.")
    print("  NOTE: random fill assignment removes any link between a trade's violence and its")
    print("  fill quality. If violent trades really fill worse, this understates what skipping")
    print("  them saves.")
    print("  STATED BEFORE ANY NUMBER: slots full 86.5% of the time (rule-out only); 17 Aug - 21")
    print("  Sep is the favourable window; 31% of trades entered beyond 3.5 sigma; position size")
    print("  grew about fivefold, so raw $ are weighted to the last weeks (hence constant-size $).")
    print()
    with mp.get_context("spawn").Pool(7, initializer=_init_worker) as pool:
        out = []
        for k, r in enumerate(pool.imap_unordered(_one_seed, range(N_SEEDS)), 1):
            out.append(r)
            if k % 20 == 0:
                print(f"  seeds done {k}/{N_SEEDS}   [{time.time()-t0:.0f}s]", flush=True)
    out.sort(key=lambda r: r["seed"])
    med = lambda a: f"{np.median(a):+.4g} [{np.min(a):+.4g}, {np.max(a):+.4g}]"
    medp = lambda a: f"{np.median(a):.1f} [{np.min(a):.1f}, {np.max(a):.1f}]"
    print()
    print("=" * 140)
    print("HEADLINE -- median [min, max] over 200 seeds")
    print("=" * 140)
    ov = np.array([r["ov"] for r in out])
    print(f"  drawn stop fills per seed: median {med(ov[:, 0])}, mean {med(ov[:, 1])}, p90 {med(ov[:, 2])}")
    T = {q: np.array([r["tot"][q] for r in out]) for q in ("R", "U", "Uc", "n")}
    print(f"  TAKE EVERYTHING: mean R {med(T['R'] / T['n'])}   total R {med(T['R'])}   total $ "
          f"{med(T['U'])}   constant-size $ {med(T['Uc'])}")
    nbeat = np.array([sum(c["beats"] for c in r["cells"].values()) for r in out])
    nworse = np.array([sum(c["worseU"] for c in r["cells"].values()) for r in out])
    surv = []
    for r in out:
        win = [c for c, v in r["cells"].items() if v["beats"]]
        bf = pd.Series([c[0][0] for c in win]).value_counts()
        clus = len(win) > 0 and bf.iloc[0] >= (2.0 / 3.0) * len(win)
        surv.append(len(win) >= 3 and clus and not any(v["worseU"] for v in r["cells"].values()))
    print(f"  cells beating the null on BOTH total R and $, per seed: median {np.median(nbeat):.0f}, "
          f"range {nbeat.min()}-{nbeat.max()} (about 1 expected by chance)")
    print(f"  cells significantly worse on dollars, per seed: median {np.median(nworse):.0f}, "
          f"range {nworse.min()}-{nworse.max()}")
    print(f"  READING RULE (unchanged, judged per seed): SURVIVES on {int(np.sum(surv))} of "
          f"{N_SEEDS} seeds")
    print()
    print("=" * 140)
    print("THE 20 CELLS -- arm minus take-everything, median [min, max] over seeds; pct = percentile")
    print("in the random null; 'beat' = seeds beating the null on BOTH R and $; '$worse' = seeds")
    print("with the dollar interval entirely below zero")
    print("=" * 140)
    keys = list(out[0]["cells"].keys())
    print(f"  {'cell':<12}{'d mean R':>28}{'d total R':>26}{'d $':>28}{'d $ const size':>28}"
          f"{'pct R':>20}{'pct $':>20}{'pct $c':>20}{'beat':>6}{'$worse':>7}")
    for c in keys:
        g = lambda f: np.array([r["cells"][c][f] for r in out])
        print(f"  {' '.join(c):<12}{med(g('dmean')):>28}{med(g('dtotR')):>26}{med(g('dU')):>28}"
              f"{med(g('dUc')):>28}{medp(g('pct_R')):>20}{medp(g('pct_U')):>20}"
              f"{medp(g('pct_Uc')):>20}{int(g('beats').sum()):>6}{int(g('worseU').sum()):>7}")
    print("  median day-clustered 95% intervals (over seeds), d total R / d $ / d $ const:")
    for c in keys:
        g = lambda f: np.array([r["cells"][c][f] for r in out])
        print(f"    {' '.join(c):<12}[{np.median(g('ci_R')[:, 0]):+.1f}, {np.median(g('ci_R')[:, 1]):+.1f}]"
              f"   [{np.median(g('ci_U')[:, 0]):+,.0f}, {np.median(g('ci_U')[:, 1]):+,.0f}]"
              f"   [{np.median(g('ci_Uc')[:, 0]):+,.0f}, {np.median(g('ci_Uc')[:, 1]):+,.0f}]")
    print()
    print("=" * 140)
    print("STOPPING PREMIUM AND OVERSHOOT SHARE -- median [min, max] over seeds")
    print("=" * 140)
    print(f"  {'flag':<10}{'overshoot-cost share':>28}{'premium flagged':>28}{'premium unflagged':>28}"
          f"   (share of trades 0.200 each)")
    for f in out[0]["where"]:
        w = np.array([r["where"][f] for r in out])
        print(f"  {f:<10}{med(w[:, 0]):>28}{med(w[:, 1]):>28}{med(w[:, 2]):>28}")
    print()
    print("=" * 140)
    print("BEYOND 3.5 SIGMA (1,178 trades), reported not gated")
    print("=" * 140)
    nb35 = np.array([sum(c["beats"] for c in r["cells35"].values()) for r in out])
    print(f"  cells beating the null on both, per seed: median {np.median(nb35):.0f}, range "
          f"{nb35.min()}-{nb35.max()}")
    for c in keys:
        g = lambda f: np.array([r["cells35"][c][f] for r in out])
        print(f"    {' '.join(c):<12}d total R {med(g('dtotR'))}   d $ {med(g('dU'))}   d $c "
              f"{med(g('dUc'))}   pct R {medp(g('pct_R'))}  pct $ {medp(g('pct_U'))}  beat "
              f"{int(g('beats').sum())}")
    print()
    print("=" * 140)
    print("MULTIPLE-TESTING CHECKS, beside the rule: Hansen SPA and Romano-Wolf StepM on daily")
    print("P&L, 20 arms vs take-everything -- median [min, max] over seeds")
    print("=" * 140)
    for unit, lbl in (("R", "total R"), ("U", "dollars")):
        for pv in ("lower", "consistent", "upper"):
            a = np.array([r["mt"][unit][0][pv] for r in out])
            print(f"  {lbl:<8} SPA {pv:<11} {np.median(a):.4f} [{a.min():.4f}, {a.max():.4f}]")
        mins = np.array([np.nanmin([v if np.isfinite(v) else 1.01 for v in r["mt"][unit][1].values()])
                         for r in out])
        print(f"  {lbl:<8} StepM smallest adjusted p across the 20 arms: median {np.median(mins):.3f}, "
              f"range {mins.min():.3f}-{mins.max():.3f}")
        names = list(out[0]["mt"][unit][1].keys())
        meds = {n_: np.median([r["mt"][unit][1][n_] if np.isfinite(r["mt"][unit][1][n_]) else 1.01
                               for r in out]) for n_ in names}
        print(f"  {lbl:<8} StepM median adjusted p per arm (1.01 = never kept): " + ", ".join(
            f"{k} {v:.3f}" for k, v in sorted(meds.items(), key=lambda kv: kv[1])))
    print()
    print(f"  Nothing in the registry or live system was touched.  [{time.time()-t0:.0f}s]")
    print("=" * 140)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("main", "fills"), default="main",
                    help="main = gates, replays, flags, once-a-minute scoreboard, and the "
                         "saved per-trade state. fills = live-fill draws, 200 seeds.")
    if ap.parse_args().stage == "fills":
        fills()
    else:
        main()
