"""REACH-MU v2 Step 2: perp vs index, volume-spike detail, signed breadth.

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/reachfeat2.py > research/dislocation_model/logs/reachfeat2.log 2>&1

Writes research/datasets/reachfeat2.npz (rows aligned to disloc_meta; values on
the matched 53,757, NaN elsewhere) and research/datasets/breadth_signed.npz
(signed |z| >= 2 counts per bar and coin). Reuses breadth_counts.npz for the
|z| >= 3 table. No funding data is read. Nothing reads past the entry bar;
audited per family, stop on failure.

TIMING. The entry bar is labelled T (30-minute, by open) and closes at T+30.
Hourly bars are labelled by open, so hour H closes at H+60. The last completed
hour at entry is H* = floor_hour(T - 30 min), whose close is at or before
T+30. The 1-minute window ends at minute T+29 (the entry bar's close).

DOMINANT LEG: whyfeat's (larger |contribution| to the spread from factor
residuals, whyfeat.market_factor recomputed). 2h features use the 4-bar
dominance, 6h features and everything else the 12-bar dominance. Leg direction
d = sign(z) * sign(w), w = 1 for A and -beta for B: the way the dominant leg's
price moved when it widened the spread.

1. PERP VS INDEX (hourly). basis(H) = log perp close - log index close, perp
   close = the 30-minute panel's close at label H+30 (= the hour's close),
   index close from {T}_USDT_USDT-1h-index.feather. Cross-sectional median
   basis per hour over every coin with both (the user's addition).
     basis_now        basis(H*)
     basis_rel_now    basis(H*) - median basis(H*)
     basis_move_L     basis(H*) - basis(H*-L), L = 2, 6 hours
     basis_rel_move_L the same on basis_rel
     index_share_L    (log index move over the L hours) / (log perp move),
                      clipped to [-2, 2]; missing if the perp did not move
   Gap filled: the brief computes these "per leg". Legs A and B are an
   arbitrary ticker order, so the model gets them as DOMINANT and OTHER:
     basis_now_dom, basis_now_oth, basis_rel_now_dom, basis_rel_now_oth,
     and per L: basis_move_dom_L, basis_rel_move_dom_L, index_share_dom_L,
     basis_move_diff_L, basis_rel_move_diff_L, index_share_diff_L
     (diff = dominant - other).
   Reported (the user's addition): Pearson and Spearman correlation between a
   leg's basis_move_L and the cross-sectional median basis_move_L, for leg A,
   leg B and the dominant leg.

2. VOLUME-SPIKE DETAIL, dominant leg (12-bar), 1-minute OHLCV over the last 6h
   (the 360 minutes ending at T+29); missing minutes are excluded, never
   zero-filled.
     peak window      the 30 consecutive minutes with the largest volume sum
     med30            the leg's median 30-minute bar volume over the 336 bars
                      before the 6h window (the panel's raw 30m volume;
                      1-minute sums equal 30-minute bars, checked, ratio 1.0)
     impact_per_vol   log( |log close move over the peak window| /
                      (window volume / med30) )
     wick_reject      the 5 highest-volume minutes: volume-weighted share of
                      each bar's range given back from the extreme in the
                      spike direction ((high-close)/(high-low) if d > 0, else
                      (close-low)/(high-low)); bars with zero range dropped
     retrace_started  -d * (log close at T+29 - log close at T+14) /
                      (sd of 1-minute log returns over the 7 days before the
                      6h window * sqrt(15)). Positive = already moving back.
                      Gap filled: there is no 1-minute factor model, so the
                      raw 1-minute return sd stands in for the residual sd.
     spike_persistence share of the 6h's minutes with volume > 3 x the median
                      minute volume over the 7 days before the window
     mins_since_peak  log(1 + minutes from the peak-volume minute to T+29)
     coinc_other, coinc_btc  log( the other leg's / BTC's volume over the same
                      peak window / its own med30 )
   Needs at least 300 finite minutes in the 6h, else missing.

3. SIGNED BREADTH. Every pair's z on its own rolling geometry (reachfeat's
   loop, mkdisloc's geometry). A leg's side in pair (a, b) at a bar: a is
   rich if z > 0; b's side is -sign(z) * sign(beta_t). Per bar and coin:
   pairs at |z| >= 2 where the coin is rich, and where it is cheap.
     signed_breadth_a, _b  share of the leg's finite-z pairs where it sits on
                           the SAME side as in this episode (a: sign z_entry;
                           b: -sign z_entry * sign beta), |z| >= 2, own pair
                           excluded
     signed_breadth_gap    dominant minus other
     breadth_change_1h, _4h  the dominant leg's |z| >= 3 share (reachfeat's
                           definition, own pair excluded) now minus 2 and 8
                           bars before
   GATE: the recomputed finite-z counts must equal breadth_counts.npz's nfin.

CHECKS: look-ahead per family; coverage and missing by cause; median/p5/p95;
Spearman against vol_48 and vol_48_1m (> 0.8 flagged "restates volatility").
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
import rolling_spread as rs
import universe_panel
from whyfeat import LOOKS, RAW_DIR, WIN, market_factor, raw_panel, take

OUT = os.path.join(paths.DATASETS, "reachfeat2.npz")
SIGNED = os.path.join(paths.DATASETS, "breadth_signed.npz")
COUNTS = os.path.join(paths.DATASETS, "breadth_counts.npz")
HOURS = (2, 6)
SPIKE_MIN = 360
MIN7 = 7 * 24 * 60
MIN_FIN = 300


def load_1m(ticker):
    f = os.path.join(RAW_DIR, f"{ticker}_USDT_USDT-1m-futures.feather")
    d = pd.read_feather(f, columns=["date", "high", "low", "close", "volume"])
    ix = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None).to_numpy().astype("datetime64[m]")
    t0 = ix.min()
    off = ((ix - t0) / np.timedelta64(1, "m")).astype(np.int64)
    out = {k: np.full(off.max() + 1, np.nan) for k in ("h", "l", "c", "v")}
    out["h"][off] = np.log(d["high"].to_numpy(float))
    out["l"][off] = np.log(d["low"].to_numpy(float))
    out["c"][off] = np.log(d["close"].to_numpy(float))
    out["v"][off] = d["volume"].to_numpy(float)
    return t0, out


def win(arr, start, n):
    """arr[start : start+n] with NaN outside the array (no wrap)."""
    I = start[:, None] + np.arange(n)[None, :]
    ok = (I >= 0) & (I < len(arr))
    return np.where(ok, arr[np.clip(I, 0, len(arr) - 1)], np.nan)


def main():
    t0 = time.time()
    M = pd.read_parquet(paths.META)
    N_ep = len(M)
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    pidx = pd.to_datetime(panel.index)
    cols = list(panel.columns)
    ixc = {c: k for k, c in enumerate(cols)}
    LC = panel.to_numpy(float)
    n, N = LC.shape
    J = M.bar_index.to_numpy(int)
    if not (pidx[J] == pd.to_datetime(M.entry_time)).all():
        raise SystemExit("[REACHF2] meta.bar_index does not resolve to entry_time.")
    ja = M.ticker_a.map(ixc).to_numpy(int)
    jb = M.ticker_b.map(ixc).to_numpy(int)
    beta = M.beta.to_numpy(float)
    s = np.sign(M.z_at_entry.to_numpy(float))
    s[s == 0] = 1.0
    from envelope import scan_1m_coverage, select_1m_subset
    cov = scan_1m_coverage(M, verbose=False)
    used, _ = select_1m_subset(M, cov, verbose=False)
    r1 = np.flatnonzero(used)
    print("=" * 112)
    print("REACH-MU v2 STEP 2 -- perp vs index, volume-spike detail, signed breadth")
    print("=" * 112)
    print(f"  panel {n:,} bars x {N} tickers; {N_ep:,} episodes, {len(r1):,} in the matched set")
    feats, cause, touch = {}, {}, {}

    # ---------------- dominance ----------------
    _, resid, _, _, _, _ = market_factor(LC)
    dom = {}
    for L in LOOKS:
        I = J[:, None] + np.arange(-L + 1, 1)[None, :]
        ra, rb = resid[I, ja[:, None]], resid[I, jb[:, None]]
        cA, cB = ra.sum(1), -beta * rb.sum(1)
        undef = ~(np.isfinite(ra).all(1) & np.isfinite(rb).all(1))
        domA = np.abs(cA) >= np.abs(cB)
        dom[L] = dict(domA=domA, undef=undef, jd=np.where(domA, ja, jb), jo=np.where(domA, jb, ja),
                      d=s * np.where(domA, 1.0, np.sign(-beta)))
    del resid
    print(f"  dominance recomputed (whyfeat.market_factor)   [{time.time()-t0:.0f}s]", flush=True)

    # ---------------- 1. perp vs index ----------------
    hrs = pd.date_range(pidx[0].floor("h"), pidx[-1].floor("h"), freq="h")
    hpos = {h: k for k, h in enumerate(hrs)}
    lab30 = pd.Series(np.arange(n), index=pidx)
    perp = np.full((len(hrs), N), np.nan)
    idxc = np.full((len(hrs), N), np.nan)
    j30 = lab30.reindex(hrs + pd.Timedelta(minutes=30)).to_numpy()
    okh = np.isfinite(j30)
    perp[okh] = LC[j30[okh].astype(int)]
    for k, t in enumerate(cols):
        d = pd.read_feather(os.path.join(RAW_DIR, f"{t}_USDT_USDT-1h-index.feather"), columns=["date", "close"])
        ix_ = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
        sr = pd.Series(np.log(d["close"].to_numpy(float)), index=ix_)
        idxc[:, k] = sr[~sr.index.duplicated(keep="last")].reindex(hrs).to_numpy()
    B = perp - idxc
    med = np.nanmedian(np.where(np.isfinite(B), B, np.nan), axis=1)
    Brel = B - med[:, None]
    print(f"  hourly basis: {len(hrs):,} hours x {N} coins; finite cells {int(np.isfinite(B).sum()):,}; "
          f"median coins per hour {int(np.median(np.isfinite(B).sum(1)))}   [{time.time()-t0:.0f}s]", flush=True)
    Tm = pd.to_datetime(M.entry_time)
    Hstar = (Tm - pd.Timedelta(minutes=30)).dt.floor("h")
    hk = Hstar.map(hpos).to_numpy(int)
    entry_close = (Tm + pd.Timedelta(minutes=30)).to_numpy("datetime64[m]")
    hclose = (Hstar + pd.Timedelta(minutes=60)).to_numpy("datetime64[m]")
    touch["perp vs index: latest hourly close read (minutes vs entry close)"] = \
        ((hclose - entry_close) / np.timedelta64(1, "m")).astype(int)
    leg = lambda A, h, j: take(A, h[:, None], j[:, None])[:, 0]
    L12 = dom[12]
    feats["basis_now_dom"] = leg(B, hk, L12["jd"])
    feats["basis_now_oth"] = leg(B, hk, L12["jo"])
    feats["basis_rel_now_dom"] = leg(Brel, hk, L12["jd"])
    feats["basis_rel_now_oth"] = leg(Brel, hk, L12["jo"])
    corr_rows = []
    for Lh, Lb in zip(HOURS, LOOKS):
        D = dom[Lb]
        mv = lambda A, j: leg(A, hk, j) - leg(A, hk - Lh, j)
        bm_d, bm_o = mv(B, D["jd"]), mv(B, D["jo"])
        br_d, br_o = mv(Brel, D["jd"]), mv(Brel, D["jo"])
        pm_d, pm_o = mv(perp, D["jd"]), mv(perp, D["jo"])
        im_d, im_o = mv(idxc, D["jd"]), mv(idxc, D["jo"])
        with np.errstate(divide="ignore", invalid="ignore"):
            is_d = np.clip(np.where(pm_d != 0, im_d / pm_d, np.nan), -2, 2)
            is_o = np.clip(np.where(pm_o != 0, im_o / pm_o, np.nan), -2, 2)
        feats[f"basis_move_dom_{Lh}"] = bm_d
        feats[f"basis_rel_move_dom_{Lh}"] = br_d
        feats[f"index_share_dom_{Lh}"] = is_d
        feats[f"basis_move_diff_{Lh}"] = bm_d - bm_o
        feats[f"basis_rel_move_diff_{Lh}"] = br_d - br_o
        feats[f"index_share_diff_{Lh}"] = is_d - is_o
        mmed = med[hk] - take(med[:, None], (hk - Lh)[:, None], np.zeros((N_ep, 1), int))[:, 0]
        for lname, v in (("leg A", mv(B, ja)), ("leg B", mv(B, jb)), ("dominant", bm_d)):
            m_ = np.isfinite(v) & np.isfinite(mmed)
            m_[np.setdiff1d(np.arange(N_ep), r1)] = False
            pr = float(np.corrcoef(v[m_], mmed[m_])[0, 1])
            sr_ = float(pd.Series(v[m_]).corr(pd.Series(mmed[m_]), method="spearman"))
            corr_rows.append((Lh, lname, int(m_.sum()), pr, sr_))
    for nm in [k for k in feats if k.startswith(("basis", "index_share"))]:
        und = L12["undef"] if ("now" in nm or nm.endswith("_6")) else dom[4]["undef"]
        feats[nm] = np.where(und, np.nan, feats[nm])
        c = np.full(N_ep, "", dtype=object)
        c[und] = "dominant leg undefined"
        c[(c == "") & ~np.isfinite(feats[nm])] = "index/perp missing or perp flat"
        cause[nm] = c
    print("  BASIS MOVE vs the cross-sectional median basis move (matched set):")
    for Lh, lname, nn, pr, sr_ in corr_rows:
        print(f"    {Lh}h  {lname:<9} n {nn:,}   Pearson {pr:+.3f} (R2 {pr*pr:.3f})   Spearman {sr_:+.3f}")
    print(f"  perp vs index done   [{time.time()-t0:.0f}s]", flush=True)
    print()

    # ---------------- 2. volume-spike detail ----------------
    V30 = raw_panel("volume", pidx, cols)
    Ib = J[:, None] + np.arange(-12 - WIN + 1, -12 + 1)[None, :]   # 336 bars before the 6h window
    touch["spike med30 baseline (30m bars)"] = Ib.max(1)
    med30 = {k: np.nanmedian(take(V30, Ib, jj[:, None]), 1)
             for k, jj in (("d", L12["jd"]), ("o", L12["jo"]), ("btc", np.full(N_ep, ixc["BTC"])))}
    entry_m = Tm.to_numpy().astype("datetime64[m]")
    lastm = entry_m + np.timedelta64(29, "m")
    S = {k: np.full(N_ep, np.nan) for k in ("impact", "wick", "retrace", "persist", "since")}
    pk_start = np.full(N_ep, np.datetime64("NaT"), dtype="datetime64[m]")
    nfinm = np.zeros(N_ep, int)
    tick = sorted(set(np.array(cols)[L12["jd"][r1]]))
    for ti, tk in enumerate(tick):
        rr = r1[np.array(cols)[L12["jd"][r1]] == tk]
        rr = rr[~L12["undef"][rr]]
        if not len(rr):
            continue
        tz, A = load_1m(tk)
        endo = ((lastm[rr] - tz) / np.timedelta64(1, "m")).astype(np.int64)
        st = endo - SPIKE_MIN + 1
        v = win(A["v"], st, SPIKE_MIN)
        c = win(A["c"], st, SPIKE_MIN)
        h = win(A["h"], st, SPIKE_MIN)
        l_ = win(A["l"], st, SPIKE_MIN)
        fm = np.isfinite(v)
        nfinm[rr] = fm.sum(1)
        v0 = np.where(fm, v, 0.0)
        cs = np.concatenate([np.zeros((len(rr), 1)), np.cumsum(v0, 1)], 1)
        w30 = cs[:, 30:] - cs[:, :-30]                                  # window sums, starts 0..330
        ws = w30.argmax(1)
        wsum = w30[np.arange(len(rr)), ws]
        cprev = win(A["c"], st + ws - 1, 1)[:, 0]
        cend = win(A["c"], st + ws + 29, 1)[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            imp = np.abs(cend - cprev) / (wsum / med30["d"][rr])
            S["impact"][rr] = np.where(imp > 0, np.log(imp), np.nan)
        top = np.argsort(-v0, 1)[:, :5]
        rows_ = np.arange(len(rr))[:, None]
        hh, ll, cc, vv = h[rows_, top], l_[rows_, top], c[rows_, top], v0[rows_, top]
        dd = L12["d"][rr][:, None]
        rng_ = hh - ll
        with np.errstate(divide="ignore", invalid="ignore"):
            g = np.where(dd > 0, (hh - cc) / rng_, (cc - ll) / rng_)
            ok_ = (rng_ > 0) & np.isfinite(g) & (vv > 0)
            S["wick"][rr] = np.where(ok_, g * vv, 0).sum(1) / np.where(ok_, vv, 0).sum(1)
        base_st = st - MIN7
        vb = win(A["v"], base_st, MIN7)
        cb = win(A["c"], base_st, MIN7)
        with np.errstate(invalid="ignore", divide="ignore"):
            sd1 = np.nanstd(np.diff(cb, axis=1), axis=1, ddof=1)
            r15 = c[:, -1] - c[:, -16]
            S["retrace"][rr] = -L12["d"][rr] * r15 / (sd1 * np.sqrt(15))
            mm = np.nanmedian(vb, 1)
            S["persist"][rr] = (np.where(fm, v > 3 * mm[:, None], False)).sum(1) / fm.sum(1)
        pkm = np.where(fm, v, -np.inf).argmax(1)
        S["since"][rr] = np.log1p((SPIKE_MIN - 1) - pkm)
        pk_start[rr] = tz + (st + ws).astype("timedelta64[m]")
        if (ti + 1) % 50 == 0:
            print(f"    spike detail: {ti+1} of {len(tick)} dominant tickers   [{time.time()-t0:.0f}s]", flush=True)
    short = np.zeros(N_ep, bool)
    short[r1] = nfinm[r1] < MIN_FIN
    for k in S:
        S[k][short] = np.nan
    # coincidence: other leg and BTC over the dominant leg's peak window
    coinc = {"o": np.full(N_ep, np.nan), "btc": np.full(N_ep, np.nan)}
    have = ~np.isnat(pk_start) & ~short
    other_t = np.array(cols)[L12["jo"]]
    for tk in sorted(set(other_t[have]) | {"BTC"}):
        tz, A = load_1m(tk)
        for key, sel in (("o", have & (other_t == tk)), ("btc", have if tk == "BTC" else None)):
            if sel is None or not sel.any():
                continue
            rr = np.flatnonzero(sel)
            stw = ((pk_start[rr] - tz) / np.timedelta64(1, "m")).astype(np.int64)
            vw = win(A["v"], stw, 30)
            with np.errstate(invalid="ignore", divide="ignore"):
                q = np.nansum(vw, 1) / med30[key][rr]
                q[np.isfinite(vw).sum(1) < 15] = np.nan
                coinc[key][rr] = np.where(q > 0, np.log(q), np.nan)
    mxm = int(((pk_start[have] + np.timedelta64(29, "m")) - lastm[have]).max() / np.timedelta64(1, "m"))
    touch["spike: last 1m read (minutes vs T+29)"] = None
    for nm, v in (("impact_per_vol", S["impact"]), ("wick_reject", S["wick"]),
                  ("retrace_started", S["retrace"]), ("spike_persistence", S["persist"]),
                  ("mins_since_peak", S["since"]), ("coinc_other", coinc["o"]), ("coinc_btc", coinc["btc"])):
        v = np.where(np.isfinite(v), v, np.nan)
        c = np.full(N_ep, "", dtype=object)
        m1 = np.zeros(N_ep, bool)
        m1[r1] = True
        c[~m1] = "outside the matched set"
        c[(c == "") & L12["undef"]] = "dominant leg undefined"
        c[(c == "") & short] = f"under {MIN_FIN} finite minutes in the 6h"
        c[(c == "") & ~np.isfinite(v)] = "volume/range/baseline missing or zero"
        feats[nm], cause[nm] = v, c
    print(f"  spike detail done; peak windows end at most {mxm:+d} min vs T+29 (must be <= 0)   "
          f"[{time.time()-t0:.0f}s]", flush=True)
    print()

    # ---------------- 3. signed breadth ----------------
    BC = np.load(COUNTS)
    ndis, nfin_saved = BC["ndis"], BC["nfin"]
    V = panel.to_numpy(float)
    ok = np.isfinite(V)
    first = np.array([ok[:, j].argmax() for j in range(N)])
    pairs = universe_panel.tradeable_pairs(cols)
    rich = np.zeros((n, N), np.int32)
    cheap = np.zeros((n, N), np.int32)
    nfin = np.zeros((n, N), np.int32)
    key = M.ticker_a + "|" + M.ticker_b
    ep_of = key.groupby(key).indices
    own = {k: np.zeros(N_ep, bool) for k in ("dis2", "fin2", "dis8", "fin8")}
    for pi, (a, b) in enumerate(pairs):
        xa, xb = ixc[a], ixc[b]
        f = max(first[xa], first[xb])
        r = rs.rolling_spread_stats(V[f:, xa], V[f:, xb], 0.5)
        z = r.z
        fin = np.isfinite(z) & np.isfinite(r.sigma) & (r.sigma > 0)
        zz = np.where(fin, z, 0.0)
        big = fin & (np.abs(zz) >= 2.0)
        sa = np.sign(zz)
        sb = -np.sign(zz) * np.sign(np.where(np.isfinite(r.beta), r.beta, 0.0))
        rich[f:, xa] += big & (sa > 0)
        cheap[f:, xa] += big & (sa < 0)
        rich[f:, xb] += big & (sb > 0)
        cheap[f:, xb] += big & (sb < 0)
        nfin[f:, xa] += fin
        nfin[f:, xb] += fin
        eps = ep_of.get(f"{a}|{b}")
        if eps is not None:
            dis3 = fin & (np.abs(zz) >= 3.0)
            for k_, lag in (("2", 2), ("8", 8)):
                li = J[eps] - lag - f
                okl = li >= 0
                own["dis" + k_][eps] = np.where(okl, dis3[np.clip(li, 0, None)], False)
                own["fin" + k_][eps] = np.where(okl, fin[np.clip(li, 0, None)], False)
        if (pi + 1) % 5000 == 0:
            print(f"    {pi+1:,} of {len(pairs):,} pairs   [{time.time()-t0:.0f}s]", flush=True)
    same = bool(np.array_equal(nfin, nfin_saved))
    print(f"  GATE -- recomputed finite-z counts equal breadth_counts.npz's: {same}")
    if not same:
        raise SystemExit("[REACHF2] STOP -- the pair geometry differs from reachfeat's.")
    np.savez_compressed(SIGNED, rich2=rich, cheap2=cheap, tickers=np.array(cols),
                        bars=pidx.to_numpy("datetime64[ns]"))
    print(f"  [WROTE] {os.path.relpath(SIGNED, paths.RESEARCH)}")
    side_a = s
    side_b = -s * np.sign(beta)
    with np.errstate(divide="ignore", invalid="ignore"):
        cnt_a = np.where(side_a > 0, rich[J, ja], cheap[J, ja]) - 1        # own pair: |z|>=3, same side
        cnt_b = np.where(side_b > 0, rich[J, jb], cheap[J, jb]) - 1
        sba = np.where(nfin[J, ja] > 1, cnt_a / (nfin[J, ja] - 1), np.nan)
        sbb = np.where(nfin[J, jb] > 1, cnt_b / (nfin[J, jb] - 1), np.nan)
    if (cnt_a < 0).any() or (cnt_b < 0).any():
        raise SystemExit("[REACHF2] own pair not counted on its own side at entry.")
    feats["signed_breadth_a"], feats["signed_breadth_b"] = sba, sbb
    domA = L12["domA"]
    feats["signed_breadth_gap"] = np.where(L12["undef"], np.nan, np.where(domA, sba - sbb, sbb - sba))
    jd = L12["jd"]
    with np.errstate(divide="ignore", invalid="ignore"):
        now = (ndis[J, jd] - 1) / (nfin_saved[J, jd] - 1)
        for k_, lag, nm in (("2", 2, "breadth_change_1h"), ("8", 8, "breadth_change_4h")):
            then = ((ndis[J - lag, jd] - own["dis" + k_]) / (nfin_saved[J - lag, jd] - own["fin" + k_]))
            feats[nm] = np.where(L12["undef"], np.nan, now - then)
    for nm in ("signed_breadth_a", "signed_breadth_b", "signed_breadth_gap", "breadth_change_1h", "breadth_change_4h"):
        c = np.full(N_ep, "", dtype=object)
        c[L12["undef"] & ("gap" in nm or "change" in nm)] = "dominant leg undefined"
        c[(c == "") & ~np.isfinite(feats[nm])] = "no finite-z partners"
        cause[nm] = c
    touch["signed breadth / breadth change (bar read)"] = J.copy()
    print()

    # ---------------- checks ----------------
    print("=" * 112)
    print("CHECKS")
    print("=" * 112)
    print("  LOOK-AHEAD (must be <= 0):")
    bad = False
    for k_, v in touch.items():
        if v is None:
            d_ = mxm
            print(f"    {k_:<64} max {d_:+d}; window ends at T+29 by construction")
        elif "minutes" in k_:
            d_ = int(v.max())
            print(f"    {k_:<64} max {d_:+d}")
        else:
            d_ = int((v - J).max())
            print(f"    {k_:<64} max {d_:+d}")
        bad |= d_ > 0
    if bad:
        raise SystemExit("[REACHF2] STOP -- a feature reads past the entry bar.")
    print("    -> PASS")
    print()
    names = list(feats)
    for nm in names:                       # values only on the matched set
        v = feats[nm].copy()
        mk = np.ones(N_ep, bool)
        mk[r1] = False
        v[mk] = np.nan
        feats[nm] = v
    print(f"  COVERAGE on the matched {len(r1):,}, median [p5, p95], missing by cause")
    for nm in names:
        v = feats[nm][r1]
        cs_ = pd.Series(cause[nm][r1][~np.isfinite(v)]).value_counts()
        print(f"    {nm:<24}{int(np.isfinite(v).sum()):>7,}  {np.nanmedian(v):+.4g} "
              f"[{np.nanpercentile(v, 5):+.4g}, {np.nanpercentile(v, 95):+.4g}]   "
              + "; ".join(f"{k}: {n_:,}" for k, n_ in cs_.items()))
    print()
    fz = np.load(paths.ENVFEAT, allow_pickle=False)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], r1):
        raise SystemExit("[REACHF2] vol48_1m rows differ.")
    ref = {"vol_48": fz["X"][r1, 0].astype(float), "vol_48_1m": v48["vol_48_1m"]}
    flags = []
    print("  SPEARMAN on the matched set, flag > 0.8 against vol_48 or vol_48_1m")
    for nm in names:
        v = feats[nm][r1]
        row = []
        for w in ref.values():
            m_ = np.isfinite(v) & np.isfinite(w)
            row.append(pd.Series(v[m_]).corr(pd.Series(w[m_]), method="spearman"))
        fl = max(abs(row[0]), abs(row[1])) > 0.8
        flags += [nm] if fl else []
        print(f"    {nm:<24} vol_48 {row[0]:+.3f}   vol_48_1m {row[1]:+.3f}" + ("   RESTATES VOLATILITY" if fl else ""))
    print(f"  flagged 'restates volatility': {', '.join(flags) if flags else 'none'}")
    fam = {nm: ("perp_index" if nm.startswith(("basis", "index_share")) else
                "signed_breadth" if nm.startswith(("signed_breadth", "breadth_change")) else "spike_detail")
           for nm in names}
    np.savez_compressed(OUT, names=np.array(names), family=np.array([fam[k] for k in names]),
                        X=np.column_stack([feats[k] for k in names]), restates=np.array(flags),
                        ticker_a=M.ticker_a.to_numpy(str),
                        entry_time=pd.to_datetime(M.entry_time).to_numpy("datetime64[ns]"))
    print(f"  [WROTE] {os.path.relpath(OUT, paths.RESEARCH)}  ({N_ep:,} x {len(names)})")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    main()
