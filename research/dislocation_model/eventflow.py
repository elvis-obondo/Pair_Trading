"""HL-EVENT1 Part A3: the flow series of every event and control, plus the targets and bar arrays.

    python -u research/dislocation_model/eventflow.py

Reads datasets/ev_events.parquet, ev_pairs.parquet, ev_market.npz, ev_coinstats/{coin}.npz and
the per-coin flow and 1-minute files, ONE COIN AT A TIME. t = 0 is the cutoff C = T + 30 min;
a window [C - b, C - a) uses minutes < C only.

SERIES per event or control link, signed by d (+ = pushing the coin the way it dislocated), for
the five pre-registered windows P1 [-60,0), P2 [-360,-60), P3 [-1440,-360), C6 [-360,0), C24 [-1440,0):
  imb      (buy - sell) / (buy + sell), times d
  forced   forced notional on the pushing side (liq_forced_short_usd if d > 0 else liq_forced_long_usd) / taker notional
  open     opening push share (open_buy_usd if d > 0 else open_sell_usd) / taker notional
  close    closing push share (close_buy_usd if d > 0 else close_sell_usd) / taker notional
  ratio    open / (open + close)
  top3     sum of per-minute top-3 notional / taker notional                       [PROXY]
  wallets  sum of per-minute distinct taker wallets / (taker notional in $M), divided by its trailing
           7-day median (the median of the same W-minute quantity at the 336 half-hour cutoffs ending
           at or before the window start; NaN if < 144 valid)                      [PROXY]
  volume   taker notional / the same trailing 7-day median of window totals
  twap     twap_taker_usd / taker notional (NaN before 2025-07-27 08:00)
  resid    d * (coin residual return over the window): coin 30m log return minus beta * benchmark return,
           beta frozen at the event (the control's own bar), at the 30-minute grid
  mk_idx   d * the benchmark index return over the window (the market-move block)
  mk_liq   market-wide forced liquidation notional (all coins) in the window / its trailing 7-day median
A window with ANY missing minute is NaN; a zero taker notional makes the ratios NaN. No zero fill.

TARGETS (events only; the 1-minute spread path). The coin's 1-minute spread is
(log close - beta * LV - alpha - mu) / sigma with beta, alpha, mu, sigma frozen at the event and LV the
BRIDGED 1-minute index level: the benchmark's 30-minute level at each half-hour mark, interpolated
inside each bar by the equal-weight 1-minute benchmark returns with the bar's remaining difference
spread linearly, so the path reproduces the 30-minute z at every mark (asserted). reach = depth >=
|z|, depth = the largest move toward mu over minutes 1..600 after the entry close, no stop. The
population is the events whose 601-minute window is finite for the coin and the benchmark.
chance = the same path's 1-minute steps with random signs, 50 seeds (the build 3 construction).
vol_48 / vol_48_1m = mean |step| of that frozen spread over the last 24 h at 30-minute / 1-minute steps.

Event-time profile bins (relative to t = 0): 1-minute inside [-60, 60), 5-minute in [-1440, -60) and
[60, 600): 504 bins. Accumulated for events, control set 1 and control set 2 (imb, forced, open,
and the 30-minute residual price path k = -48..20 bars). Events also keep the after-trigger bins
(0..600: 168) of imb, forced, open for Part C. Per-coin bar arrays for the impact model go to
datasets/ev_bars/{coin}.npz.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import paths
import coinevents as ce
import evmarket as em
import flowfeat as ff

WINS = {"P1": (60, 0), "P2": (360, 60), "P3": (1440, 360), "C6": (360, 0), "C24": (1440, 0)}
WN = list(WINS)
SER = ["imb", "forced", "open", "close", "ratio", "top3", "wallets", "volume", "twap", "resid", "mk_idx", "mk_liq"]
COLS = ["taker_buy_usd", "taker_sell_usd", "liq_forced_long_usd", "liq_forced_short_usd", "open_buy_usd", "open_sell_usd",
        "close_buy_usd", "close_sell_usd", "n_taker_wallets", "top3_taker_share", "twap_taker_usd"]
EDGES = np.concatenate([np.arange(-1440, -60, 5), np.arange(-60, 60, 1), np.arange(60, 600, 5)])
WIDTH = np.concatenate([np.full(276, 5), np.full(120, 1), np.full(108, 5)])
NB = len(EDGES)
AFTER0 = 276 + 60                                  # first bin with start >= 0
NAFT = NB - AFTER0                                 # 168
PATH = np.arange(-1440, 601)                       # minutes relative to t = 0 for the 1-minute spread path
BARK = np.arange(-48, 21)                          # 30-minute bar offsets of the residual-price profile
SEEDS = range(1000, 1050)
OUT_SERIES = os.path.join(paths.DATASETS, "ev_series.npz")
OUT_TARGET = os.path.join(paths.DATASETS, "ev_targets.npz")
OUT_PROFILE = os.path.join(paths.DATASETS, "ev_profile.npz")
OUT_AFTER = os.path.join(paths.DATASETS, "ev_after.npz")
BAR_DIR = os.path.join(paths.DATASETS, "ev_bars")


def shifted_median(series, sh):
    """Median of the 336 values ending `sh` half-hour cutoffs earlier; NaN if < 144 valid."""
    r = pd.Series(series).rolling(ff.TRAIL, min_periods=ff.MINVALID).median().to_numpy()
    out = np.full(len(r), np.nan)
    out[sh:] = r[:-sh]
    return out


def build_LV(lc_len, idx1, L, ir, obar):
    """Bridged 1-minute index level at price time tau (LV[tau], tau in minute offsets; NaN where unknown)."""
    LV = np.full(ff.N + 1, np.nan)
    starts = obar - 30
    ok = (starts >= 0) & (obar <= ff.N) & np.isfinite(ir) & np.isfinite(L)
    ok[0] = False
    ok[1:] &= np.isfinite(L[:-1])
    bars = np.flatnonzero(ok)
    if len(bars) == 0:
        return LV
    M = idx1[starts[bars][:, None] + np.arange(30)[None, :]]
    cum = np.cumsum(M, axis=1)
    tot = cum[:, -1]
    corr = (np.arange(1, 31) / 30.0)[None, :] * (ir[bars] - tot)[:, None]
    lev = L[bars - 1][:, None] + cum + corr
    lev[~np.isfinite(tot)] = np.nan
    LV[starts[bars][:, None] + 1 + np.arange(30)[None, :]] = lev
    return LV


class Market:
    def __init__(self):
        z = np.load(em.OUT)
        self.S, self.n, self.mkt, self.breadth, self.hole = z["S1m"], z["n1m"].astype(np.int64), z["mkt_liq"], z["breadth_j"], z["hole"]
        self.mcs, self.mnc = ff.cum_nan(self.mkt)
        self.med = {}
        for w, (b, a) in WINS.items():
            tot = ff.cutoff_series(self.mcs, self.mnc, b - a)
            self.med[w] = shifted_median(tot, b // 30)


def coin_windows(rows, o, d, beta, bar, cum, norm, V, L, jcol, mk, jj):
    """(nrows, len(SER), 5) window series for the rows (events or controls) of one coin."""
    out = np.full((len(o), len(SER), len(WN)), np.nan, np.float32)
    for wi, w in enumerate(WN):
        b_, a_ = WINS[w]
        s_, e_ = o - b_, o - a_
        ok = (s_ >= 0) & (e_ <= ff.N)
        s2, e2 = np.where(ok, s_, 0), np.where(ok, e_, 0)
        good = ok & ((cum["nc"][e2] - cum["nc"][s2]) == 0)
        sm = lambda k: cum[k][e2] - cum[k][s2]
        tn = np.where(good, sm("tn"), np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            pos = np.where(good & (tn > 0), 1.0, np.nan)
            pk = lambda kp, kn: np.where(d > 0, sm(kp), sm(kn))
            imb = pos * d * (sm("buy") - sm("sell")) / tn
            forced = pos * pk("fs", "fl") / tn
            op, cp = pos * pk("ob", "os") / tn, pos * pk("cb", "cs") / tn
            ratio = np.where((op + cp) > 0, op / (op + cp), np.nan)
            top3 = pos * sm("t3") / tn
            wraw = pos * sm("wal") / (tn / 1e6)
            nm_w, nm_v = norm[w][0][jj], norm[w][1][jj]
            wal = np.where(nm_w > 0, wraw / nm_w, np.nan)
            vol = np.where(nm_v > 0, tn / nm_v, np.nan)
            tw_ok = ok & ((cum["ntw"][e2] - cum["ntw"][s2]) == 0)
            twap = np.where(tw_ok, pos * sm("tw") / tn, np.nan)
            bi, ai = bar - b_ // 30, bar - a_ // 30
            rok = bi >= 0
            bi2 = np.where(rok, bi, 0)
            resid = d * ((V[ai, jcol] - V[bi2, jcol]) - beta * (L[ai] - L[bi2]))
            resid = np.where(rok, resid, np.nan)
            midx = np.where(rok, d * (L[ai] - L[bi2]), np.nan)
            ml_tot = np.where(ok & ((mk.mnc[e2] - mk.mnc[s2]) == 0), mk.mcs[e2] - mk.mcs[s2], np.nan)
            ml = np.where(mk.med[w][jj] > 0, ml_tot / mk.med[w][jj], np.nan)
        for si, arr in enumerate((imb, forced, op, cp, ratio, top3, wal, vol, twap, resid, midx, ml)):
            out[:, si, wi] = arr
    return out


def coin_profile(o, d, cum):
    """(nrows, 3, NB): imb, forced, open per event-time bin (NaN if the bin has a missing minute or no taker notional)."""
    s_, e_ = o[:, None] + EDGES[None, :], o[:, None] + (EDGES + WIDTH)[None, :]
    ok = (s_ >= 0) & (e_ <= ff.N)
    s2, e2 = np.where(ok, s_, 0), np.where(ok, e_, 0)
    good = ok & ((cum["nc"][e2] - cum["nc"][s2]) == 0)
    sm = lambda k: cum[k][e2] - cum[k][s2]
    tn = np.where(good, sm("tn"), np.nan)
    dd = d[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        pos = np.where(good & (tn > 0), 1.0, np.nan)
        imb = pos * dd * (sm("buy") - sm("sell")) / tn
        forced = pos * np.where(dd > 0, sm("fs"), sm("fl")) / tn
        opn = pos * np.where(dd > 0, sm("ob"), sm("os")) / tn
    return np.stack([imb, forced, opn], axis=1).astype(np.float32)


def main():
    t0 = time.time()
    EV = pd.read_parquet(ce.EVENTS)
    PR = pd.read_parquet(ce.PAIRS)
    panel, idx, V, cols = ce.load_panel()
    cidx = {c: j for j, c in enumerate(cols)}
    mk = Market()
    nev, npr = len(EV), len(PR)
    SERIES_EV = np.full((nev, len(SER), len(WN)), np.nan, np.float32)
    SERIES_PR = np.full((npr, len(SER), len(WN)), np.nan, np.float32)
    # targets
    T_ = dict(reach=np.zeros(nev, bool), depth=np.full(nev, np.nan), chance=np.full(nev, np.nan), fin=np.zeros(nev, bool),
              t_reach=np.full(nev, -1, np.int32), vol_48=np.full(nev, np.nan), vol_48_1m=np.full(nev, np.nan),
              nmiss_1m=np.zeros(nev, np.int32), e_err=np.full(nev, np.nan))
    MOVE = np.full((nev, 601), np.nan, np.float32)
    PROF = {g: [np.zeros((3, NB)), np.zeros((3, NB)), np.zeros(len(BARK)), np.zeros(len(BARK))] for g in (0, 1, 2)}
    AFTER = np.full((nev, 3, NAFT), np.nan, np.float32)
    os.makedirs(BAR_DIR, exist_ok=True)
    coins = sorted(EV.coin.unique())
    max_err_repro = 0.0
    for k, c in enumerate(coins):
        j = cidx[c]
        st = np.load(os.path.join(ce.STATS_DIR, f"{c}.npz"))
        L, ir = st["L"], st["ir"]
        fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date"] + COLS)
        a = {kk: ff.dense(fl, kk) for kk in COLS}
        del fl
        buy, sell = a["taker_buy_usd"], a["taker_sell_usd"]
        TN = buy + sell
        top3n = np.where(TN > 0, np.nan_to_num(a["top3_taker_share"]) * TN, np.where(np.isnan(TN), np.nan, 0.0))
        cum = {}
        for nm, arr in (("buy", buy), ("sell", sell), ("fl", a["liq_forced_long_usd"]), ("fs", a["liq_forced_short_usd"]),
                        ("ob", a["open_buy_usd"]), ("os", a["open_sell_usd"]), ("cb", a["close_buy_usd"]),
                        ("cs", a["close_sell_usd"]), ("wal", a["n_taker_wallets"]), ("tn", TN), ("t3", top3n)):
            cum[nm], nc = ff.cum_nan(arr)
            if nm == "buy":
                cum["nc"] = nc
        cum["tw"], cum["ntw"] = ff.cum_nan(a["twap_taker_usd"])
        norm = {}
        for w, (b_, a_) in WINS.items():
            wtot = ff.cutoff_series(cum["wal"], cum["nc"], b_ - a_)
            tntot = ff.cutoff_series(cum["tn"], cum["nc"], b_ - a_)
            with np.errstate(divide="ignore", invalid="ignore"):
                q = np.where(tntot > 0, wtot / (tntot / 1e6), np.nan)
            norm[w] = (shifted_median(q, b_ // 30), shifted_median(tntot, b_ // 30))
        # ---------------- rows of this coin
        ev = EV[EV.coin == c]
        pr = PR[PR.coin == c]
        for tbl, is_ev in ((ev, True), (pr, False)):
            if not len(tbl):
                continue
            T = pd.to_datetime(tbl["T"])
            o = ff.minute_index(T + pd.Timedelta(minutes=30))
            bar = tbl["bar"].to_numpy(int) if "bar" in tbl else None
            if bar is None:
                bar = np.searchsorted(idx.values, T.values)
            assert (idx[bar] == T.values).all()
            jj = (o - ff.CUT_PHASE) // 30
            assert ((o - ff.CUT_PHASE) % 30 == 0).all()
            d = tbl["d"].to_numpy(float)
            S_ = coin_windows(tbl, o, d, tbl["beta"].to_numpy(float), bar, cum, norm, V, L, j, mk, jj)
            P_ = coin_profile(o, d, cum)
            kb = np.clip(bar[:, None] + BARK[None, :], 0, len(L) - 1)
            okb = (bar[:, None] + BARK[None, :] >= 0) & (bar[:, None] + BARK[None, :] < len(L))
            rp = d[:, None] * ((V[kb, j] - V[bar, j][:, None]) - tbl["beta"].to_numpy(float)[:, None] * (L[kb] - L[bar][:, None]))
            rp = np.where(okb, rp, np.nan)
            if is_ev:
                SERIES_EV[tbl.event_id.to_numpy()] = S_
                AFTER[tbl.event_id.to_numpy()] = P_[:, :, AFTER0:]
                grp = np.zeros(len(tbl), int)
            else:
                SERIES_PR[tbl.index.to_numpy()] = S_
                grp = tbl["set"].to_numpy(int)
            for g in np.unique(grp):
                m_ = grp == g
                gi = 0 if is_ev else int(g)
                fin = np.isfinite(P_[m_])
                PROF[gi][0] += np.where(fin, P_[m_], 0.0).sum(0); PROF[gi][1] += fin.sum(0)
                fr = np.isfinite(rp[m_])
                PROF[gi][2] += np.where(fr, rp[m_], 0.0).sum(0); PROF[gi][3] += fr.sum(0)
        # ---------------- bar arrays for the impact model (30-minute): residual return, regressors, scale
        nb = len(L)
        obar = ff.minute_index(idx + pd.Timedelta(minutes=30))
        lim = (obar - 30 >= 0) & (obar <= ff.N)
        e_ = np.where(lim, obar, 0); s_ = np.where(lim, obar - 30, 0)
        okb = lim & ((cum["nc"][e_] - cum["nc"][s_]) == 0)
        tnb = np.where(okb, cum["tn"][e_] - cum["tn"][s_], np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            imb_b = np.where(tnb > 0, (cum["buy"][e_] - cum["buy"][s_] - (cum["sell"][e_] - cum["sell"][s_])) / tnb, np.nan)
            frc_b = np.where(tnb > 0, ((cum["fs"][e_] - cum["fs"][s_]) - (cum["fl"][e_] - cum["fl"][s_])) / tnb, np.nan)
        r30 = np.full(nb, np.nan); r30[1:] = V[1:, j] - V[:-1, j]
        bprev = np.full(nb, np.nan); bprev[1:] = st["beta"][:-1]
        res = r30 - bprev * ir
        vs = pd.Series(res).rolling(48, min_periods=40).std().shift(1).to_numpy()
        np.savez_compressed(os.path.join(BAR_DIR, f"{c}.npz"), resid=res, volscale=vs, imb=imb_b, forced=frc_b,
                            tn=tnb, ir=ir, beta_prev=bprev)
        # ---------------- targets (events): the 1-minute spread path
        lc = em.load_lc(c)
        r1 = em.ret1m(lc)
        fin1 = np.isfinite(r1)
        no = mk.n - fin1
        with np.errstate(invalid="ignore", divide="ignore"):
            i1 = (mk.S - np.where(fin1, r1, 0.0)) / no
        idx1 = np.where(fin1 & (no >= ce.MIN_OTHER), i1, np.nan)
        LV = build_LV(len(lc), idx1, L, ir, obar)
        eo = ff.minute_index(pd.to_datetime(ev["T"]) + pd.Timedelta(minutes=30))
        taus = eo[:, None] + PATH[None, :]
        tk = np.clip(taus, 1, ff.N)
        okp = (taus >= 1) & (taus <= ff.N)
        Xp = np.where(okp, lc[np.clip(tk - 1, 0, ff.N - 1)], np.nan)
        Lp = np.where(okp, LV[tk], np.nan)
        be, al = ev.beta.to_numpy(float)[:, None], ev.alpha.to_numpy(float)[:, None]
        mu_, sg_ = ev.mu.to_numpy(float)[:, None], ev.sigma.to_numpy(float)[:, None]
        Pz = (Xp - be * Lp - al - mu_) / sg_
        z0 = Pz[:, 1440]
        err = np.abs(z0 - ev.z.to_numpy(float))
        T_["e_err"][ev.event_id.to_numpy()] = err
        mk_ok = np.isfinite(err)
        max_err_repro = max(max_err_repro, float(np.nanmax(err)) if mk_ok.any() else 0.0)
        # reproduction at every 30-minute mark of the pre-event window: z from the 30m panel
        bar_e = ev["bar"].to_numpy(int)
        for kk in range(-48, 1, 6):
            zz = (V[bar_e + kk, j] - ev.beta.to_numpy(float) * L[bar_e + kk] - ev.alpha.to_numpy(float) - ev.mu.to_numpy(float)) / ev.sigma.to_numpy(float)
            e2 = np.abs(Pz[:, 1440 + 30 * kk] - zz)
            max_err_repro = max(max_err_repro, float(np.nanmax(e2)) if np.isfinite(e2).any() else 0.0)
        e0 = ev.z.to_numpy(float)
        sgn = np.where(e0 >= 0, 1.0, -1.0)
        move = -(Pz[:, 1440:] - e0[:, None]) * sgn[:, None]
        fin_all = np.isfinite(Pz[:, 1440:]).all(1) & ev.has_outcome.to_numpy(bool)
        depth = np.where(fin_all, np.nanmax(np.where(np.isfinite(move[:, 1:]), move[:, 1:], -np.inf), 1), np.nan)
        reach = fin_all & (depth >= np.abs(e0))
        hitm = np.where(np.isfinite(move[:, 1:]), move[:, 1:] >= np.abs(e0)[:, None], False)
        trch = np.where(reach, hitm.argmax(1) + 1, -1)
        p30 = Pz[:, ::30][:, :49]
        v48 = np.nanmean(np.abs(np.diff(p30, axis=1)), 1) if p30.shape[1] > 1 else np.nan
        d1 = np.diff(Pz[:, :1441], axis=1)
        with np.errstate(invalid="ignore"):
            v48m = np.nanmean(np.abs(d1), 1)
        # chance probability (build 3's construction, 50 seeds, finite rows only)
        ch = np.full(len(ev), np.nan)
        if fin_all.any():
            mm = move[fin_all]
            inc = np.zeros_like(mm); inc[:, 1:] = np.diff(mm, axis=1)
            hits = np.zeros(len(mm))
            for sd_ in SEEDS:
                sg = np.random.default_rng([sd_, j]).choice([-1.0, 1.0], size=inc.shape)
                hits += np.cumsum(sg * inc, axis=1)[:, 1:].max(1) >= np.abs(e0[fin_all])
            ch[fin_all] = hits / len(SEEDS)
        eid = ev.event_id.to_numpy()
        T_["reach"][eid], T_["depth"][eid], T_["chance"][eid], T_["fin"][eid], T_["t_reach"][eid] = reach, depth, ch, fin_all, trch
        T_["vol_48"][eid], T_["vol_48_1m"][eid] = v48, v48m
        T_["nmiss_1m"][eid] = (~np.isfinite(Pz)).sum(1)
        MOVE[eid] = move.astype(np.float32)
        if (k + 1) % 20 == 0:
            print(f"  coin {k + 1}/{len(coins)}  [{time.time() - t0:.0f}s]", flush=True)
    np.savez_compressed(OUT_SERIES, ev=SERIES_EV, pr=SERIES_PR, series=np.array(SER), windows=np.array(WN))
    np.savez_compressed(OUT_TARGET, move=MOVE, **T_)
    np.savez_compressed(OUT_PROFILE, edges=EDGES, width=WIDTH, bark=BARK,
                        **{f"g{g}_{n}": v for g, vs_ in PROF.items() for n, v in zip(("sum", "cnt", "psum", "pcnt"), vs_)})
    np.savez_compressed(OUT_AFTER, after=AFTER)
    print(f"[EVENTFLOW] events {nev:,}, links {npr:,}; 1-minute path reproduces the z at the entry and the 30-minute marks, "
          f"max abs error {max_err_repro:.2e}  [{time.time() - t0:.0f}s]")
    fin = T_["fin"]
    print(f"[TARGET] 1-minute window finite for {int(fin.sum()):,} of {int(EV.has_outcome.sum()):,} events with an outcome window "
          f"(lost to holes {int(EV.has_outcome.sum() - fin.sum()):,}); reach {T_['reach'][fin].mean():.4f}; "
          f"mean chance {np.nanmean(T_['chance'][fin]):.4f}")
    for w in WN:
        for si, sname in enumerate(SER):
            v = SERIES_EV[:, si, WN.index(w)]
            if w == "C24":
                print(f"  NaN share, events, {sname:<8} C24: {100 * np.isnan(v).mean():.2f}%")


if __name__ == "__main__":
    main()
