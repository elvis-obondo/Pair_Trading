"""COSTS1 no-bounce check (rules: research/model/costs1_rules.md section 10, fixed before this code).

Question: is the reversion real in book-midpoint terms, or was it the last-trade close bouncing between bid and ask?
Events and picks are the saved ones (signal still built from closes; a signal built from mids is NOT tested). Only the prices that measure the
entry stretch, the path and the exit change. Findings are reported, not acted on. Local, no pull, no engine change, no tuning.

DECISION RULES (copied from section 10; the rules file governs)
  ALIGNMENT  ctxs row stamped T is label T-1 (engine: clean_ctx_group). Close of label L pairs with the ctxs mid stamped L+1. Path index k reads stamp t0+k
             (close label t0-1+k). Entry ref pairs with stamp t0, exit ref with stamp exit_time. Capture delay of a few seconds is an assumption, not corrected.
  MID        ctxs mid_px, log; NaN or <= 0 is missing (coverage is NOT full: whole coins are 0 on some days); no forward fill for entry and exit prices. The G8 table mid at the
             same stamp is (a) a cross-check (|diff| in bp by tier, flagged under 99% within 1 bp) and (b) for the TRADE re-pricing a labelled fallback where the ctxs mid is
             missing; both the ctxs-only and the with-fallback version are printed. Event-level tables use ctxs only.
  FRESH      a close is fresh when mins_since_trade == 0 at its label (entry label t0-1, exit label exit_time-1). Event fresh = both legs fresh at the entry label; trade fresh = four closes
             fresh. The measured quantity is the CLOSE VS MID GAP; only the fresh stratum is called bounce, the stale stratum stale price.
  SPREAD     P[k] = (log a - beta log b - alpha - mu) / sigma, s = +1 if z >= 0 else -1; reached at k when s P[k] <= 0, k = 1..h. Stretch |z| = s P[0]; mid |z_mid| = s P_mid[0].
             Mid events already through mu at entry (|z_mid| <= 0) are counted NOT reached (own line; the alternative is printed beside).
  HORIZONS   120 / 300 / 600 minutes (2 / 5 / 10 h). Gross move at horizon h = -(P[h] - P[0]) s; mid value uses minute h or the last minute with both mids within 5 minutes before it.
  MATCHED    every close-versus-mid comparison is on events (trades) that have all the mids needed; close figures on all events are printed beside.
  RECEIPT    close reach/time-to-mu recomputed here must equal the saved labels on at least 99.9% of events; otherwise the run stops.
  TRADES     A = saved net. B = saved net - saved gross + gross_mid (mid-to-mid gross, fees/funding as saved). C = existing headline costed net (costs_headline_conservative_*).
  HEADLINE   vault q 1% / no stop / taker / open10: GROSS RATIO sum(gross_mid) / sum(saved gross) on the trades with all four mids (ctxs with G8 fallback). Bands (this cell only, carried by
             the gross ratio): < 25% mostly close-vs-mid gap, 25-75% partly, > 75% mostly real; zero or negative (or saved gross <= 0) falls in the bottom band; if < 90% of the run's
             trades have all four mids (with the fallback) no band is applied. The net ratio B / A is printed beside with gross, fees, funding and net dollars.
"""
import hashlib
import json
import math
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
assert os.environ.get("PROFIT1_VAULT", "") != "1"
import harness as H  # noqa: E402
import vault_loader as VL  # noqa: E402
import s1h_recalibration as S1H  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)     # all-NaN slices in nanmean/nanmedian of empty strata print as nan
T = os.path.join(MODEL, "logs", "profit1") + os.sep
C1 = os.path.join(MODEL, "logs", "costs1") + os.sep
S1 = os.path.join(MODEL, "logs", "s1") + os.sep
TIERS = ["least liquid third", "middle third", "most liquid third"]
HZ = (120, 300, 600)
K = 601
CHUNK = 10000
SFX = {("vault", 10): "_vault_open10", ("vault", 20): "_vault_open20", ("test", 10): "", ("test", 20): "_open20"}
T0 = time.time()
RES = {}
TIMES = {}


def log(m):
    print(m, flush=True)


def lap(name, t):
    TIMES[name] = round(time.time() - t, 1)
    log(f"[NOBOUNCE] timing: {name} took {TIMES[name]:.1f}s")


def epoch_min(ts):
    return ((pd.to_datetime(ts, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(minutes=1)).to_numpy().astype("int64")


def pct(x):
    return f"{100 * x:.1f}%"


# ------------------------------------------------------------------ tiers (costs_analysis rule: median daily traded notional terciles; extended by the mapped coins' cut points)
def coin_medians(coins, d0, d1):
    a, b = d0 // 1440, d1 // 1440
    med = {}
    for c in coins:
        f_ = f"{T}build2_1m_cache/{c}-1m.feather"
        if not os.path.exists(f_):
            continue
        df = pd.read_feather(f_, columns=["date", "notional"])
        m = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None).to_numpy().astype("datetime64[m]").astype(np.int64)
        nt = df["notional"].to_numpy(float)
        dd = m // 1440
        sel = (dd >= a) & (dd <= b) & np.isfinite(nt)
        s_ = pd.Series(nt[sel]).groupby(dd[sel]).sum()
        s_ = s_[s_ > 0]
        med[c] = float(s_.median()) if len(s_) else np.nan
    return pd.Series(med)


def build_tiers(side, coins, mapped, runs_range):
    """tier of every coin: the costs1 mapping where it exists (asserted to equal the cut-point rule), the cut-point rule otherwise"""
    med = coin_medians(sorted(set(coins) | {c for v in mapped.values() for c in v}), *runs_range)
    inv = {c: k for k, v in mapped.items() for c in v}
    mm = med[[c for c in inv if c in med.index]]
    lo = mm[[c for c in mm.index if inv[c] == TIERS[0]]].max()
    mid_lo = mm[[c for c in mm.index if inv[c] == TIERS[1]]].min()
    mid_hi = mm[[c for c in mm.index if inv[c] == TIERS[1]]].max()
    hi_lo = mm[[c for c in mm.index if inv[c] == TIERS[2]]].min()
    cut1, cut2 = (lo + mid_lo) / 2, (mid_hi + hi_lo) / 2
    assert lo < mid_lo and mid_hi < hi_lo, "mapped tiers are not separated by median daily notional"
    out = {}
    for c, v in med.items():
        if np.isnan(v):
            continue
        t = TIERS[0] if v < cut1 else (TIERS[1] if v < cut2 else TIERS[2])
        if c in inv:
            assert inv[c] == t, f"{side} {c}: mapped tier {inv[c]} != cut-point tier {t}"
        out[c] = t
    log(f"[NOBOUNCE] tiers {side}: {len(inv)} mapped coins reproduced exactly by the cut points (median daily notional {cut1:,.0f} / {cut2:,.0f}); {len(out) - len(inv)} further coins tiered by the same cut points")
    return out


# ------------------------------------------------------------------ dense price arrays on one stamp axis
def load_arrays(side, coins, base, n_min):
    """CL[cid, stamp - base] = log close of label stamp-1 (cleaned prices as the engine used); ML = log ctxs mid_px stamped `stamp`; MS = mins_since_trade of the close of label stamp-1"""
    d = "cleaned_vault" if side == "vault" else "cleaned"
    cid = {c: i for i, c in enumerate(coins)}
    CL = np.full((len(coins), n_min), np.nan)
    MS = np.full((len(coins), n_min), np.nan, dtype=np.float32)
    for c in coins:
        f_ = f"{T}{d}/price/{c}.parquet"
        if not os.path.exists(f_):
            continue
        df = pd.read_parquet(f_, columns=["label", "log_close", "mins_since_trade"])
        st = df["label"].to_numpy().astype("datetime64[m]").astype(np.int64) + 1 - base
        ok = (st >= 0) & (st < n_min)
        CL[cid[c], st[ok]] = df["log_close"].to_numpy(float)[ok]
        MS[cid[c], st[ok]] = df["mins_since_trade"].to_numpy(float)[ok]
    ML = np.full((len(coins), n_min), np.nan)
    d0, d1 = base // 1440, (base + n_min - 1) // 1440
    nrow = noff = 0
    for dd in range(d0, d1 + 1):
        day = pd.Timestamp(dd * 86400, unit="s").strftime("%Y%m%d")
        f_ = f"{T}ctxs_cache/{day}.parquet"
        if not os.path.exists(f_):
            continue
        p = pd.read_parquet(f_, columns=["time", "coin", "mid_px"])
        off = (p["time"].dt.second != 0) | (p["time"].dt.microsecond != 0)
        noff += int(off.sum())
        p = p[~off]
        st = epoch_min(p["time"]) - base
        c_ = p["coin"].astype(str).map(cid)
        ok = c_.notna().to_numpy() & (st >= 0) & (st < n_min)
        ci = c_.to_numpy()[ok].astype(np.int64)
        assert not pd.Series(ci * 10 ** 7 + st[ok]).duplicated().any(), f"duplicate (coin, stamp) in ctxs {day}"
        mv = p["mid_px"].to_numpy(float)[ok]
        with np.errstate(invalid="ignore", divide="ignore"):
            ML[ci, st[ok]] = np.where(mv > 0, np.log(mv), np.nan)
        nrow += int(ok.sum())
    log(f"[NOBOUNCE] arrays {side}: {len(coins)} coins x {n_min:,} minutes; ctxs rows used {nrow:,}, off-minute rows dropped {noff:,}; finite mids {int(np.isfinite(ML).sum()):,}, finite closes {int(np.isfinite(CL).sum()):,}")
    return cid, CL, ML, MS


# ------------------------------------------------------------------ events
def load_events(side):
    cols = ["ticker_a", "ticker_b", "beta", "alpha", "mu", "sigma", "z", "reach_2h", "reach_5h", "reach_10h", "minutes_to_mu"]
    if side == "vault":
        ev = VL.load_vault_events(columns=cols)
        ev = ev[ev["label_gap"] == 0].reset_index(drop=True)
        pk = pd.read_parquet(S1 + "s1_vault_picks_all.parquet")
        pk_ids = set(pk["event_id"])
        assert set(ev["event_id"]) == pk_ids, f"vault events ({len(ev):,}) and picks table ({len(pk):,}) differ"
        ev = ev.merge(pk[["event_id", "p_10h", "pick_0.01"]], on="event_id", validate="one_to_one")
        ev["fold"] = 99
    else:
        df, events = S1H.load_data()
        s1g = json.load(open(S1 + "s1g_report.json"))
        blk, _ = S1H.compute_picks(df, s1g)
        full = H.load_search_events(columns=cols).reset_index(drop=True).set_index("event_id")
        sub = full.reindex(blk["event_id"])
        ev = blk[["event_id", "fold", "p_10h", "pick_0.01"]].reset_index(drop=True)
        for c in cols:
            ev[c] = sub[c].to_numpy()
        ev["t0"] = sub["t0"].to_numpy()
        assert ev["ticker_a"].notna().all()
    ev["t0m"] = epoch_min(ev["t0"])
    ev["pick"] = ev["pick_0.01"].astype(bool)
    log(f"[NOBOUNCE] events {side}: {len(ev):,} (picks q 1%: {int(ev['pick'].sum()):,}); t0 {ev['t0'].min()} .. {ev['t0'].max()}")
    return ev


def chunk_stats(ev, cid, CL, ML, MS, base):
    """per-event path statistics for close and mid"""
    n = len(ev)
    ia = ev["ticker_a"].map(cid).to_numpy().astype(np.int64)
    ib = ev["ticker_b"].map(cid).to_numpy().astype(np.int64)
    t0 = ev["t0m"].to_numpy()
    beta, alpha, mu, sigma, z = (ev[c].to_numpy(float) for c in ("beta", "alpha", "mu", "sigma", "z"))
    s = np.where(z >= 0, 1.0, -1.0)
    cols = (t0 - base)[:, None] + np.arange(K)[None, :]
    assert cols.min() >= 0 and cols.max() < ML.shape[1]
    out = {}
    P = {}
    out["fresh_ent"] = (MS[ia, t0 - base] == 0) & (MS[ib, t0 - base] == 0)
    for name, A in (("c", CL), ("m", ML)):
        la, lb = A[ia[:, None], cols], A[ib[:, None], cols]
        P[name] = s[:, None] * ((la - beta[:, None] * lb - alpha[:, None] - mu[:, None]) / sigma[:, None])   # s x P
        out[f"fin_{name}"] = np.isfinite(la).all(1) & np.isfinite(lb).all(1)
        out[f"miss_{name}"] = (~(np.isfinite(la[:, 1:]) & np.isfinite(lb[:, 1:]))).sum(1)
    fm = np.isfinite(P["m"])                                           # minutes where the mid exists (both legs)
    sPc = P["c"]
    hit_cm = (sPc[:, 1:] <= 0) & fm[:, 1:]                             # close tested ONLY on the minutes where the mid exists (same-minutes comparator)
    out["tmu_cm"] = np.where(hit_cm.any(1), hit_cm.argmax(1) + 1, np.nan)
    for h in HZ:
        v = np.full(n, np.nan)
        for back in range(5, -1, -1):
            wm = -(P["m"][:, h - back] - P["m"][:, 0])
            wc = -(sPc[:, h - back] - sPc[:, 0])
            v = np.where(np.isfinite(wm), wc, v)
        out[f"mv_cm_{h}"] = v
    for name in ("c", "m"):
        sP = P[name]
        out[f"z_{name}"] = sP[:, 0]                                   # s x P[0]
        hit = sP[:, 1:] <= 0                                           # NaN compares False
        anyhit = hit.any(1)
        out[f"tmu_{name}"] = np.where(anyhit, hit.argmax(1) + 1, np.nan)
        for h in HZ:
            if name == "c":
                v = -(sP[:, h] - sP[:, 0])
            else:
                v = np.full(n, np.nan)
                for back in range(5, -1, -1):                          # last finite within 5 minutes before h (back = 0 is minute h itself, taken last so it wins)
                    w = -(sP[:, h - back] - sP[:, 0])
                    v = np.where(np.isfinite(w), w, v)
            out[f"mv_{name}_{h}"] = v
    return out


def run_period(side, ev, tier_of, mapped_all):
    t = time.time()
    coins = sorted(set(ev["ticker_a"]) | set(ev["ticker_b"]))
    base = int(ev["t0m"].min()) - 1
    n_min = int(ev["t0m"].max()) + K + 2 - base
    cid, CL, ML, MS = load_arrays(side, coins, base, n_min)
    rows = []
    for i0 in range(0, len(ev), CHUNK):
        sub = ev.iloc[i0:i0 + CHUNK]
        o = chunk_stats(sub, cid, CL, ML, MS, base)
        rows.append(pd.DataFrame(o, index=sub.index))
        if (i0 // CHUNK) % 30 == 0:
            log(f"[NOBOUNCE]   {side}: {min(i0 + CHUNK, len(ev)):,} / {len(ev):,} events, {time.time() - t:.0f}s")
    R = pd.concat(rows)
    lap(f"event paths {side}", t)
    return R, cid, CL, ML, MS, base


# ------------------------------------------------------------------ tables
def q(a, qs=(1, 5, 25, 50, 75, 95, 99)):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return np.percentile(a, qs) if len(a) else np.full(len(qs), np.nan)


def groups(E):
    """yield (set name, tier name, mask) for all/picks x all tiers + each tier"""
    for gname, gm in (("all events", np.ones(len(E), bool)), ("q1% picks", E["pick"].to_numpy())):
        yield gname, "ALL TIERS", gm
        for tr in TIERS:
            yield gname, tr, gm & (E["tier"].to_numpy() == tr)


def report_period(side, E, fresh_coin, tier_of):
    """E: events with path stats merged. All tables printed here; returns dict for the json"""
    out = {}
    log(f"[NOBOUNCE] ===== {side.upper()} events {len(E):,} =====")
    # mid coverage
    log(f"[NOBOUNCE] LOST FOR LACK OF A MID ({side}): events without both entry mids, by tier (picks in brackets)")
    for gname, tr, gm in groups(E):
        e = E[gm]
        lost = ~e["ent_mid"]
        nm = int((e["miss_m"] > 0).sum())
        log(f"[NOBOUNCE]   {gname:11s} {tr:20s}: n {len(e):>9,}; lost entry mid {int(lost.sum()):>7,} ({pct(lost.mean() if len(e) else float('nan'))}); matched {int(e['ent_mid'].sum()):>9,}; with >= 1 missing mid minute in the window {nm:,} ({pct(nm / max(len(e), 1))})")
        out[f"lost|{gname}|{tr}"] = dict(n=len(e), lost=int(lost.sum()), matched=int(e["ent_mid"].sum()), with_missing_path_minute=nm)
    mon = pd.to_datetime(E["t0"], utc=True).dt.strftime("%Y-%m")
    log(f"[NOBOUNCE] LOST FOR LACK OF A MID ({side}) BY MONTH AND TIER: share of events without both entry mids (n in brackets)")
    for mth in sorted(mon.unique()):
        mm_ = (mon == mth).to_numpy()
        cells = []
        for tr in ["ALL"] + TIERS:
            m2 = mm_ if tr == "ALL" else mm_ & (E["tier"].to_numpy() == tr)
            cells.append(f"{tr.split()[0]} {pct(1 - E['ent_mid'].to_numpy()[m2].mean()) if m2.any() else 'n/a'} ({int(m2.sum()):,})")
            out[f"lost_month|{mth}|{tr}"] = dict(n=int(m2.sum()), lost_share=float(1 - E["ent_mid"].to_numpy()[m2].mean()) if m2.any() else None)
        log(f"[NOBOUNCE]   {mth}: " + "; ".join(cells))
    # freshness of the closes (naming rule: only the fresh stratum may be called bounce)
    log(f"[NOBOUNCE] FRESH CLOSES ({side}): share of minutes with a trade in that minute (mins_since_trade = 0), by tier (coin share, minute-weighted), and share of events / picks whose two entry closes are both fresh")
    for tr in TIERS:
        cs = [c for c in fresh_coin.index if tier_of.get(c) == tr]
        wsum = fresh_coin.loc[cs, "n"].sum()
        sh = float((fresh_coin.loc[cs, "share"] * fresh_coin.loc[cs, "n"]).sum() / wsum) if wsum else float("nan")
        m = (E["tier"].to_numpy() == tr)
        log(f"[NOBOUNCE]   {tr:20s}: {len(cs)} coins, fresh-minute share {pct(sh)}; events both entry closes fresh {pct(E['fresh_ent'].to_numpy()[m].mean())}; picks {pct(E['fresh_ent'].to_numpy()[m & E['pick'].to_numpy()].mean())}")
        log(f"[NOBOUNCE]       by coin: " + ", ".join(f"{c} {fresh_coin.loc[c, 'share']:.2f}" for c in sorted(cs, key=lambda c: fresh_coin.loc[c, "share"])))
        out[f"fresh|{tr}"] = dict(coins=len(cs), minute_share=sh, events=float(E['fresh_ent'].to_numpy()[m].mean()), by_coin={c: float(fresh_coin.loc[c, "share"]) for c in cs})
    # receipt
    r = E["fin_c"].to_numpy()
    n_rc = int(r.sum())
    rep = {}
    mism = {}
    for h, col in ((120, "reach_2h"), (300, "reach_5h"), (600, "reach_10h")):
        mine = (E["tmu_c"].to_numpy() <= h)
        lab = E[col].to_numpy(float) > 0.5
        mism[h] = int(((mine != lab) & r).sum())
    lab_t = E["minutes_to_mu"].to_numpy(float)
    both = r & np.isfinite(E["tmu_c"].to_numpy()) & np.isfinite(lab_t)
    t_mis = int((E["tmu_c"].to_numpy()[both] != lab_t[both]).sum())
    share = 1 - max(list(mism.values()) + [t_mis]) / max(n_rc, 1)
    log(f"[NOBOUNCE] RECEIPT close path vs saved labels ({side}): events with a finite close window {n_rc:,} of {len(E):,}; reach mismatches 2h/5h/10h {mism[120]:,} / {mism[300]:,} / {mism[600]:,}; minutes_to_mu mismatches among both finite {t_mis:,} of {int(both.sum()):,}; equal share (worst of the four) {100 * share:.4f}%")
    assert share >= 0.999, f"close-based reach does not reproduce the saved labels ({side}): refusing to continue"
    out["receipt_labels"] = dict(n=n_rc, mism=mism, t_mism=t_mis, both=int(both.sum()))
    # stretch
    log(f"[NOBOUNCE] ENTRY STRETCH ({side}), sigma units, matched events (entry mid of both legs present); close-vs-mid gap share = sum(|z| - |z_mid|) / sum(|z|)")
    for gname, tr, gm in groups(E):
        e = E[gm & E["ent_mid"].to_numpy()]
        if not len(e):
            continue
        zc, zm = e["z_c"].to_numpy(), e["z_m"].to_numpy()
        d = zc - zm
        qq = lambda a: " ".join(f"{x:.3f}" for x in q(a))
        log(f"[NOBOUNCE]   {gname:11s} {tr:20s}: n {len(e):>9,}; mean |z| {zc.mean():.3f}, |z_mid| {zm.mean():.3f}, d {d.mean():.3f}; CLOSE-VS-MID GAP SHARE {pct(d.sum() / zc.sum())}; median d/|z| {pct(float(np.median(d / zc)))}; |z_mid| <= 0: {pct((zm <= 0).mean())}; |z_mid| < |z|/2: {pct((zm < zc / 2).mean())}")
        log(f"[NOBOUNCE]       quantiles 1/5/25/50/75/95/99:  |z| {qq(zc)} | |z_mid| {qq(zm)} | d {qq(d)}")
        out[f"stretch|{gname}|{tr}"] = dict(n=len(e), mean_z=float(zc.mean()), mean_zmid=float(zm.mean()), bounce_share=float(d.sum() / zc.sum()), median_d_over_z=float(np.median(d / zc)),
                                            share_no_stretch=float((zm <= 0).mean()), share_lt_half=float((zm < zc / 2).mean()), q_z=q(zc).tolist(), q_zmid=q(zm).tolist(), q_d=q(d).tolist())
    log(f"[NOBOUNCE] ENTRY STRETCH ({side}) BY FRESHNESS of the two entry closes: fresh = both legs traded in that minute (the gap here may be called bounce); stale = at least one leg's close is an older trade (the gap is stale price)")
    for gname, tr, gm in groups(E):
        for fs, fm in (("fresh", E["fresh_ent"].to_numpy()), ("stale", ~E["fresh_ent"].to_numpy())):
            e = E[gm & E["ent_mid"].to_numpy() & fm]
            if not len(e):
                continue
            zc, zm = e["z_c"].to_numpy(), e["z_m"].to_numpy()
            d = zc - zm
            log(f"[NOBOUNCE]   {gname:11s} {tr:20s} {fs:5s}: n {len(e):>9,}; mean |z| {zc.mean():.3f}, |z_mid| {zm.mean():.3f}; close-vs-mid gap share of the stretch {pct(d.sum() / zc.sum())}; median d/|z| {pct(float(np.median(d / zc)))}; |z_mid| <= 0: {pct((zm <= 0).mean())}")
            out[f"stretch_fresh|{gname}|{tr}|{fs}"] = dict(n=len(e), gap_share=float(d.sum() / zc.sum()), median_d_over_z=float(np.median(d / zc)), share_no_stretch=float((zm <= 0).mean()))
    # reversion
    log(f"[NOBOUNCE] REVERSION ({side}): matched events; reach rate (mid: through-at-entry counted NOT reached; alt = counted reached), time to mu (minutes, reached only), mean gross move at the horizon (sigma)")
    for gname, tr, gm in groups(E):
        e = E[gm & E["ent_mid"].to_numpy()]
        if not len(e):
            continue
        thr = e["z_m"].to_numpy() <= 0
        for h in HZ:
            rc_all = e["tmu_c"].to_numpy() <= h
            rc = e["tmu_cm"].to_numpy() <= h
            rm_raw = e["tmu_m"].to_numpy() <= h
            rm = rm_raw & ~thr
            rm_alt = rm_raw | thr
            tc, tm = e["tmu_cm"].to_numpy(), e["tmu_m"].to_numpy()
            mc, mm = e[f"mv_cm_{h}"].to_numpy(), e[f"mv_m_{h}"].to_numpy()
            ok = np.isfinite(mc) & np.isfinite(mm)
            log(f"[NOBOUNCE]   {gname:11s} {tr:20s} {h // 60:>2d}h: n {len(e):>9,}; reach close, same minutes as the mid {pct(rc.mean())} (close on all minutes {pct(rc_all.mean())}) mid {pct(rm.mean())} (alt {pct(rm_alt.mean())}; through at entry {pct(thr.mean())}); "
                f"time to mu mean/median close {np.nanmean(np.where(rc, tc, np.nan)):.0f}/{np.nanmedian(np.where(rc, tc, np.nan)):.0f} mid {np.nanmean(np.where(rm, tm, np.nan)):.0f}/{np.nanmedian(np.where(rm, tm, np.nan)):.0f}; "
                f"gross move close (same minute) {mc[ok].mean():.3f} mid {mm[ok].mean():.3f} (n {int(ok.sum()):,}, dropped for no mid at the horizon {len(e) - int(ok.sum()):,})")
            out[f"rev|{gname}|{tr}|{h}"] = dict(n=len(e), reach_close=float(rc.mean()), reach_mid=float(rm.mean()), reach_mid_alt=float(rm_alt.mean()), through_at_entry=float(thr.mean()),
                                                reach_close_all_minutes=float(rc_all.mean()), tmu_close_mean=float(np.nanmean(np.where(rc, tc, np.nan))), tmu_mid_mean=float(np.nanmean(np.where(rm, tm, np.nan))),
                                                mv_close=float(mc[ok].mean()), mv_mid=float(mm[ok].mean()), mv_n=int(ok.sum()))
    # ranking
    e = E[E["ent_mid"].to_numpy()].copy()
    e["quint"] = pd.qcut(e["p_10h"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5])
    thr = e["z_m"].to_numpy() <= 0
    e["rc"] = e["tmu_cm"].to_numpy() <= 600
    e["rm"] = (e["tmu_m"].to_numpy() <= 600) & ~thr
    log(f"[NOBOUNCE] RANKING ({side}): 10 h reach rate by raw p_10h quintile (1 = lowest), matched events, close (tested on the same minutes as the mid) vs mid")
    qs = e.groupby("quint", observed=True).agg(n=("rc", "size"), close=("rc", "mean"), mid=("rm", "mean"), p_mean=("p_10h", "mean"))
    for k, rr in qs.iterrows():
        log(f"[NOBOUNCE]   quintile {k}: n {int(rr['n']):>9,}; mean p_10h {rr['p_mean']:.3f}; reach close {pct(rr['close'])} mid {pct(rr['mid'])}")
    pk = e["pick"].to_numpy()
    lc, lm = e.loc[pk, "rc"].mean() / e["rc"].mean(), e.loc[pk, "rm"].mean() / e["rm"].mean()
    log(f"[NOBOUNCE]   LIFT AT THE TOP 1% ({side}): picks n {int(pk.sum()):,}; reach picks close {pct(e.loc[pk, 'rc'].mean())} mid {pct(e.loc[pk, 'rm'].mean())}; all events close {pct(e['rc'].mean())} mid {pct(e['rm'].mean())}; lift close {lc:.2f}x, mid {lm:.2f}x")
    out["ranking"] = dict(quintiles=qs.reset_index().astype({"quint": int}).to_dict("records"), lift_close=float(lc), lift_mid=float(lm))
    return out


# ------------------------------------------------------------------ G8 cross-check and trades
def g8_check(side, G, cid, ML, base, tier_of):
    n_min = ML.shape[1]
    st = G["minute"].to_numpy() - base
    ok = (st >= 0) & (st < n_min) & G["coin"].map(cid).notna().to_numpy()
    g = G[ok]
    if not len(g):
        log(f"[NOBOUNCE] G8 CROSS-CHECK {side}: no G8 rows in this period's window")
        return {}
    ci = g["coin"].map(cid).to_numpy().astype(np.int64)
    cm = ML[ci, g["minute"].to_numpy() - base]
    gm = np.log(g["mid"].to_numpy(float))
    both = np.isfinite(cm) & np.isfinite(gm)
    d = np.abs(np.exp(cm[both] - gm[both]) - 1) * 1e4
    tr = g["coin"].map(tier_of).to_numpy()[both]
    res = {}
    log(f"[NOBOUNCE] G8 CROSS-CHECK {side}: |ctxs mid - G8 mid| in bp on (coin, minute) pairs both have: rows {len(g):,}, both finite {int(both.sum()):,} ({pct(both.mean())})")
    flagged = False
    for name in ["ALL"] + TIERS:
        m = np.ones(len(d), bool) if name == "ALL" else tr == name
        if not m.any():
            continue
        x = d[m]
        w1 = float((x <= 1).mean())
        flagged |= (name != "ALL") and w1 < 0.99
        log(f"[NOBOUNCE]   {name:20s}: n {int(m.sum()):>9,}; p50 {np.percentile(x, 50):.3f} p90 {np.percentile(x, 90):.3f} p99 {np.percentile(x, 99):.3f} max {x.max():.2f} bp; within 1 bp {pct(w1)}")
        res[name] = dict(n=int(m.sum()), p50=float(np.percentile(x, 50)), p90=float(np.percentile(x, 90)), p99=float(np.percentile(x, 99)), max=float(x.max()), within1=w1)
    log(f"[NOBOUNCE]   {'FLAGGED: under 99% within 1 bp in some tier; the G8 mid is shown beside for the re-priced trades' if flagged else 'not flagged: every tier has at least 99% of rows within 1 bp'}")
    res["flagged"] = bool(flagged)
    return res


def reprice(side, ev, cid, CL, ML, MS, base, G8, tier_of):
    out = {}
    geo = ev.set_index("event_id")
    Gs = G8.drop_duplicates(["coin", "minute"]).set_index(["coin", "minute"])["mid"]
    assert len(Gs) == len(G8), "duplicate (coin, minute) in the G8 table"

    def g8mid(coins, stamps):
        v = Gs.reindex(pd.MultiIndex.from_arrays([np.asarray(coins), np.asarray(stamps)])).to_numpy(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(v > 0, np.log(v), np.nan)

    log(f"[NOBOUNCE] RE-PRICED TRADES ({side}): A = saved net (close, zero cost); B = mid-to-mid net (same fees and funding); C = existing costed headline net (costs_analysis, conservative curve; fills priced off the book mid of the fill minute on own-minute rows)")
    log(f"[NOBOUNCE]   two versions below: 'ctxs only' (all four mids from the ctxs cache) and 'ctxs + G8 fallback' (a missing ctxs mid at a stamp is replaced by the G8 table mid at the same stamp, labelled)")
    for mo in (10, 20):
        for fee in ("maker", "taker"):
            d = pd.read_parquet(f"{T}trades_q0.01_stopnone_fee{fee}{SFX[(side, mo)]}.parquet").reset_index(drop=True)
            hd = pd.read_parquet(f"{C1}costs_headline_conservative_{side}_open{mo}_{fee}.parquet")
            assert d["event_id"].is_unique and set(d["event_id"]) == set(hd["event_id"])
            assert geo.loc[d["event_id"], "pick"].all(), "a saved q1% trade is not a pick"
            g = geo.reindex(d["event_id"])
            b_ = np.abs(g["beta"].to_numpy())
            la, lb = d["notional"].to_numpy() / (1 + b_), d["notional"].to_numpy() * b_ / (1 + b_)
            z, beta = g["z"].to_numpy(), g["beta"].to_numpy()
            dira = np.where(z >= 0, -1.0, 1.0)
            dirb = np.where(z >= 0, 1.0, -1.0) * np.where(beta >= 0, 1.0, -1.0)
            t0m, exm = epoch_min(d["t0"]), epoch_min(d["exit_time"])
            ia, ib = d["ticker_a"].map(cid).to_numpy().astype(np.int64), d["ticker_b"].map(cid).to_numpy().astype(np.int64)
            # the stamp t0 holds the close of label t0-1 (the engine's ref_in); the stamp exit_time the close of label exit_time-1 (ref_out)
            ca0, ca1, cb0, cb1 = CL[ia, t0m - base], CL[ia, exm - base], CL[ib, t0m - base], CL[ib, exm - base]
            gross_c = la * dira * (np.exp(ca1 - ca0) - 1) + lb * dirb * (np.exp(cb1 - cb0) - 1)
            err = np.abs(gross_c - d["gross_pnl"].to_numpy())
            assert err.max() < 1e-4, f"saved gross not reproduced from the cleaned closes ({side} open{mo} {fee}): max {err.max()}"
            m4 = [ML[ia, t0m - base], ML[ia, exm - base], ML[ib, t0m - base], ML[ib, exm - base]]
            st4 = [(d["ticker_a"], t0m), (d["ticker_a"], exm), (d["ticker_b"], t0m), (d["ticker_b"], exm)]
            f4 = [np.where(np.isfinite(m), m, g8mid(c_, s_)) for m, (c_, s_) in zip(m4, st4)]
            n_fallback_stamps = int(sum(((~np.isfinite(m)) & np.isfinite(f)).sum() for m, f in zip(m4, f4)))

            def gross_mid(v):
                return la * dira * (np.exp(v[1] - v[0]) - 1) + lb * dirb * (np.exp(v[3] - v[2]) - 1)
            gm_c = gross_mid(m4)
            gm_f = gross_mid(f4)
            have_c, have_f = np.isfinite(gm_c), np.isfinite(gm_f)
            gs = d["gross_pnl"].to_numpy()
            A = d["net"].to_numpy()
            fees = (d["entry_fee"] + d["exit_fee"]).to_numpy()
            fund = (d["funding_paid"] - d["funding_received"]).to_numpy()
            fresh = (MS[ia, t0m - base] == 0) & (MS[ib, t0m - base] == 0) & (MS[ia, exm - base] == 0) & (MS[ib, exm - base] == 0)
            hdi = hd.set_index("event_id").reindex(d["event_id"])
            Cn = hdi["c_net"].to_numpy(float)
            tier = hdi["tier"].to_numpy()
            key = f"{side} open{mo} {fee}"
            log(f"[NOBOUNCE]   ---- {key}: trades {len(d):,}; saved gross reproduced from the cleaned closes (max abs diff ${err.max():.1e}); sum A on all trades ${A.sum():,.2f}, saved gross ${gs.sum():,.2f}, fees ${fees.sum():,.2f}, funding paid net ${fund.sum():,.2f}; all four closes fresh {pct(fresh.mean())}")
            tmon = pd.to_datetime(d["t0"], utc=True).dt.strftime("%Y-%m").to_numpy()
            log(f"[NOBOUNCE]     coverage of trades with all four mids, by entry month (ctxs only / with G8 fallback): " + "; ".join(f"{mth} {pct(have_c[tmon == mth].mean())} / {pct(have_f[tmon == mth].mean())} (n {int((tmon == mth).sum()):,})" for mth in sorted(set(tmon))))
            log(f"[NOBOUNCE]     coverage by tier (ctxs only / with fallback): " + "; ".join(f"{tr.split()[0]} {pct(have_c[tier == tr].mean())} / {pct(have_f[tier == tr].mean())} (n {int((tier == tr).sum()):,})" for tr in TIERS if (tier == tr).any()) + f"; stamps filled from the G8 table {n_fallback_stamps:,}")
            res = dict(n=len(d), A_all=float(A.sum()), gross_all=float(gs.sum()), fees_all=float(fees.sum()), cover_ctxs=float(have_c.mean()), cover_fallback=float(have_f.mean()))
            for ver, have, gmid in (("ctxs only", have_c, gm_c), ("ctxs + G8 fallback", have_f, gm_f)):
                B = A - gs + gmid
                strata = [("ALL TIERS", np.ones(len(d), bool))] + [(t_, tier == t_) for t_ in TIERS] + [("ALL TIERS fresh", fresh), ("ALL TIERS stale", ~fresh)]
                for name, mk in strata:
                    m = have & mk
                    if not m.any():
                        continue
                    sg, sgm, sA, sB, sC, sF, sFd = gs[m].sum(), gmid[m].sum(), A[m].sum(), B[m].sum(), np.nansum(Cn[m]), fees[m].sum(), fund[m].sum()
                    log(f"[NOBOUNCE]     [{ver:18s}] {name:16s}: matched {int(m.sum()):>5,} (lost {int((mk & ~have).sum()):>4,}); gross close ${sg:>9,.2f} gross mid ${sgm:>9,.2f} GROSS RATIO {(sgm / sg if sg else float('nan')):>7.1%}; fees ${sF:>8,.2f} funding ${sFd:>7,.2f}; net A ${sA:>9,.2f} B ${sB:>9,.2f} (B/A {(sB / sA if sA else float('nan')):>7.1%}) C ${sC:>9,.2f}")
                    res[f"{ver}|{name}"] = dict(n=int(m.sum()), lost=int((mk & ~have).sum()), gross_close=float(sg), gross_mid=float(sgm), gross_ratio=float(sgm / sg) if sg else None, fees=float(sF), funding=float(sFd), A=float(sA), B=float(sB), C=float(sC))
                # B - C beside the cost decomposition (filled trades of the matched set)
                m = have & hdi["c_filled"].to_numpy(bool)
                if m.any():
                    ci, cx = hdi["c_cost_in"].to_numpy(float)[m], hdi["c_cost_x"].to_numpy(float)[m]
                    bc = (B[m].sum() - np.nansum(Cn[m])) / (2 * d["notional"].to_numpy()[m].sum()) * 1e4
                    log(f"[NOBOUNCE]     [{ver:18s}] RECEIPT B - C = ${B[m].sum() - np.nansum(Cn[m]):,.2f} over {int(m.sum()):,} filled matched trades = {bc:.2f} bp of traded notional per fill (2 x notional); costs_analysis decomposition on the same trades: mean entry cost (two legs summed) {np.nanmean(ci):.2f} bp, exit {np.nanmean(cx):.2f} bp, mean per leg-fill {np.nanmean(ci + cx) / 4:.2f} bp (+-1 minute and proxy rows are priced off the close and fees can differ, so the two are close, not equal)")
                    res[f"{ver}|B_minus_C_bp_per_fill"] = float(bc)
            out[key] = res
            if (side, mo, fee) == ("vault", 10, "taker"):
                for ver, have, gmid in (("ctxs only", have_c, gm_c), ("ctxs + G8 fallback", have_f, gm_f)):
                    sg, sgm, sA = gs[have].sum(), gmid[have].sum(), A[have].sum()
                    sB = (A - gs + gmid)[have].sum()
                    ratio = sgm / sg if sg > 0 else float("nan")
                    cov = have.mean()
                    if ver == "ctxs only":
                        band = "(coverage shown beside the headline; the band is carried by the fallback version)"
                    elif cov < 0.9:
                        band = "NO BAND APPLIED (fewer than 90% of the run's trades have all four mids, with the fallback)"
                    elif not (sg > 0) or not (ratio > 0):
                        band = "bottom band: MOSTLY CLOSE VS MID GAP (zero or negative ratio)"
                    else:
                        band = "MOSTLY CLOSE VS MID GAP (under 25%)" if ratio < 0.25 else ("PARTLY close vs mid gap (25% to 75%)" if ratio <= 0.75 else "MOSTLY REAL (over 75%)")
                    log(f"[NOBOUNCE]   HEADLINE CELL vault q 1% / no stop / taker / open10 [{ver}]: gross mid ${sgm:,.2f} / gross close ${sg:,.2f} on the same {int(have.sum()):,} trades (coverage {pct(cov)}; all trades: gross close ${gs.sum():,.2f}) = GROSS RATIO {ratio:.1%}; net ratio B/A {sB:,.2f} / {sA:,.2f} = {(sB / sA if sA else float('nan')):.1%} -> {band}")
                    out[f"headline|{ver}"] = dict(gross_mid=float(sgm), gross_close=float(sg), gross_ratio=float(ratio), net_B=float(sB), net_A=float(sA), coverage=float(cov), band=band, n=int(have.sum()))
    return out


def main():
    log(f"[NOBOUNCE] script sha256 {hashlib.sha256(open(__file__, 'rb').read()).hexdigest()[:12]}; rules: research/model/costs1_rules.md section 10 (sha256 {hashlib.sha256(open(MODEL + '/costs1_rules.md', 'rb').read()).hexdigest()[:12]})")
    cj = json.load(open(C1 + "costs_analysis_conservative.json"))
    G8 = pd.read_parquet(C1 + "g8/g8_rows.parquet", columns=["coin", "minute", "mid"])
    RES["notes"] = dict(rules_section="10", alignment="close of label L pairs with ctxs mid stamped L+1")
    for side in ("vault", "test"):
        t = time.time()
        ev = load_events(side)
        runs = [pd.read_parquet(f"{T}trades_q0.01_stopnone_fee{fee}{SFX[(side, mo)]}.parquet", columns=["t0", "exit_time"]) for mo in (10, 20) for fee in ("maker", "taker")]
        rng = (min(int(epoch_min(r["t0"]).min()) for r in runs), max(int(epoch_min(r["exit_time"]).max()) for r in runs))
        coins = sorted(set(ev["ticker_a"]) | set(ev["ticker_b"]))
        tier_of = build_tiers(side, coins, cj["tier_coins"][side], rng)
        lap(f"load events and tiers {side}", t)
        R, cid, CL, ML, MS, base = run_period(side, ev, tier_of, cj["tier_coins"][side])
        E = pd.concat([ev.reset_index(drop=True), R.reset_index(drop=True)], axis=1)
        ta = E["ticker_a"].map(tier_of)
        tb = E["ticker_b"].map(tier_of)
        o = {n: i for i, n in enumerate(TIERS)}
        E["tier"] = [min((a, b), key=lambda x: o[x]) if isinstance(a, str) and isinstance(b, str) else None for a, b in zip(ta, tb)]
        E["ent_mid"] = np.isfinite(E["z_m"])
        # |z| from the engine's own saved z must equal the close-based stretch
        zerr = np.abs(E["z_c"].to_numpy() - np.abs(E["z"].to_numpy()))[E["fin_c"].to_numpy()]
        log(f"[NOBOUNCE] RECEIPT stretch: close |z| recomputed vs saved |z|: max abs diff {np.nanmax(zerr):.2e} over {len(zerr):,} events")
        assert np.nanmax(zerr) < 1e-3, "close-based entry stretch differs from the saved z"
        log(f"[NOBOUNCE] events with no tier (a coin without a median notional): {int(E['tier'].isna().sum()):,}")
        fr = {}
        for c, i_ in cid.items():
            x = MS[i_]
            fin = np.isfinite(x)
            fr[c] = dict(share=float((x[fin] == 0).mean()) if fin.any() else np.nan, n=int(fin.sum()))
        fresh_coin = pd.DataFrame(fr).T.dropna()
        RES[side] = report_period(side, E[E["tier"].notna()], fresh_coin, tier_of)
        t = time.time()
        RES[side]["g8_check"] = g8_check(side, G8, cid, ML, base, tier_of)
        RES[side]["reprice"] = reprice(side, E, cid, CL, ML, MS, base, G8, tier_of)
        lap(f"cross-check and re-pricing {side}", t)
        del CL, ML, MS, E, R
    RES["TIMES"] = TIMES
    json.dump(RES, open(C1 + "costs_nobounce.json", "w"), indent=1, default=float)
    log(f"[NOBOUNCE] wrote logs/costs1/costs_nobounce.json; total {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
