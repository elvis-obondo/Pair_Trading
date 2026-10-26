"""WHY-IT-MOVED features: which leg moved, with the market or not, on what volume,
and how liquid the lagging leg is. Steps 1-2 of the brief, plus the checks.

    .venv/bin/python research/dislocation_model/whyfeat.py 2>&1 \
        | tee research/dislocation_model/logs/whyfeat.log

Writes research/datasets/whyfeat.npz (rows aligned to disloc_meta, all 60,000).
Everything is known at the entry bar. Nothing reads past it (audited per row).

STEP 1 -- THE MARKET FACTOR. 30-minute log returns of all 214 panel tickers
(BTC and ETH included). At every bar t, a PCA of the CORRELATION matrix of the
previous 336 bars (t-336 .. t-1, 7 days), over the tickers with a complete
window and a return at t. The first 3 components. Each factor's return is an
eigenportfolio return (Avellaneda & Lee 2010): weights = eigenvector / the
ticker's trailing sd, normalised to sum to 1 in absolute value; PC1's sign is
set so its weights sum positive. Each ticker's loadings are OLS betas (with an
intercept) of its window returns on the 3 factor returns over the same window.
Residual at t = r(t) - loadings . F(t) (the intercept is not subtracted).
Bar t's own return is the close at the entry bar's close -- known at entry.

STEP 2 -- FEATURES, per episode at its entry bar i, lookbacks L = 4 and 12 bars
(bars i-L+1 .. i). The spread is a - beta*b (frozen entry beta, meta).
  contribution of A = sum resid_A;  of B = -beta * sum resid_B.
  DOMINANT leg = the larger |contribution| (gap filled: the brief's "larger
  absolute residual" is judged on contribution to the spread, which is what
  lone_share's denominator measures).
  lone_share     max|contribution| / (|contrib_A| + |contrib_B|), in [0.5, 1]
  common_share   |common| / (|common| + |residual|), where common = sum over
                 the window of (load_A - beta*load_B) . F(t) and residual =
                 contrib_A + contrib_B. Gap filled: bounded, because common /
                 (common + residual) is unbounded when the two offset.
  mkt_move       |sum of PC1 returns| over the window (log-return units)
  vol_spike_mover  dominant leg: mean bar volume over the window / its median
                 bar volume over the 336 bars before the window
  vol_spike_ratio  vol_spike of the dominant leg / vol_spike of the other
  vadj_resid     Avellaneda & Lee volume-time: the dominant contribution,
                 folded by sign(z) and divided by the entry sigma, x (mean bar
                 volume over the 336 bars before the window / mean over the
                 window)
  lagger_spread  EDGE (Ardia, Guidotti & Kroencke, JFE 2024; the authors'
                 `bidask` package, v2.1.0) on the NON-dominant leg over bars
                 i-47 .. i of 30m OHLC, / the median of the same rolling
                 estimate over the trailing 30 days (bars i-1440 .. i-1)
Every volume feature is a ratio of a coin to its own history (OKX volume may be
in contracts). The sign convention -- whether the dominant leg pushed the
spread toward the dislocation -- is reported against z_at_entry.

1-MINUTE VERSIONS of features 4 and 5 (vol_spike_mover, vol_spike_ratio,
vadj_resid), suffix _1m, for the 53,757 measurable episodes. Gap filled: the
same formulas on 1-MINUTE bars -- lookbacks 4 and 12 one-minute bars ending at
the entry bar's close (minute entry+29), baselines over the trailing 7 days of
minutes before the window. The dominant leg is the one from the 30-minute
lookback with the same index. vadj_resid_1m uses the dominant leg's RAW
1-minute log move over the window (there is no 1-minute factor model, so it is
not a residual), folded and in entry sigma. A minute with no bar is EXCLUDED,
never counted as zero volume and never filled.

CHECKS, stop on failure: max index touched <= entry bar for every feature
family (30m) and <= entry+29 minutes (1m); coverage with missing rows by cause;
median/p5/p95; Spearman against the existing six, flagging > 0.8 against
vol_48 or vol_48_1m as "restates volatility".
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
import universe_panel

WIN = 336           # 7 days of 30-minute bars
NPC = 3
LOOKS = (4, 12)
EDGE_BARS = 48
EDGE_BASE = 1440    # 30 days of 30-minute bars
MIN7 = 7 * 24 * 60
RAW_DIR = os.path.join(os.path.dirname(paths.RESEARCH), "user_data", "data", "okx", "futures")
OUT = os.path.join(paths.DATASETS, "whyfeat.npz")


def take(A, I, jcol):
    """A[I, jcol] with NaN wherever I < 0 -- a negative index must never wrap
    around to the END of the panel."""
    out = A[np.clip(I, 0, None), jcol].astype(float)
    out[I < 0] = np.nan
    return out


def raw_panel(field, pidx, tickers):
    """One raw 30m OHLCV field on the panel grid, NOT logged; gaps stay NaN."""
    out = np.full((len(pidx), len(tickers)), np.nan)
    for j, t in enumerate(tickers):
        f = os.path.join(RAW_DIR, f"{t}_USDT_USDT-30m-futures.feather")
        if not os.path.exists(f):
            continue
        d = pd.read_feather(f, columns=["date", field])
        ix = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
        s = pd.Series(d[field].to_numpy(float), index=ix)
        out[:, j] = s[~s.index.duplicated(keep="last")].reindex(pidx).to_numpy()
    return out


# ---------------------------------------------------------------- Step 1
def market_factor(LC):
    """Trailing correlation PCA at every bar. Returns resid (n, N), F (n, 3),
    loadings (n, N, 3) float32, var explained (n, 3), n eligible (n,)."""
    R = np.full_like(LC, np.nan)
    R[1:] = np.diff(LC, axis=0)
    n, N = R.shape
    resid = np.full((n, N), np.nan)
    F = np.full((n, NPC), np.nan)
    LOAD = np.full((n, N, NPC), np.nan, np.float32)
    VE = np.full((n, NPC), np.nan)
    NE = np.zeros(n, int)
    for t in range(WIN + 1, n):
        Wn = R[t - WIN:t]
        el = np.isfinite(Wn).all(0) & np.isfinite(R[t])
        k = int(el.sum())
        NE[t] = k
        if k < 10:
            continue
        X = Wn[:, el]
        mu, sd = X.mean(0), X.std(0, ddof=1)
        ok = sd > 0
        if not ok.all():
            el[np.flatnonzero(el)[~ok]] = False
            X, mu, sd = X[:, ok], mu[ok], sd[ok]
            k = int(el.sum())
        Z = (X - mu) / sd
        _, sv, Vt = np.linalg.svd(Z, full_matrices=False)
        V = Vt[:NPC].T                                   # (k, 3) eigenvectors
        VE[t] = (sv[:NPC] ** 2 / (WIN - 1)) / k          # share of the trace
        Wt = V / sd[:, None]
        Wt /= np.abs(Wt).sum(0, keepdims=True)
        if Wt[:, 0].sum() < 0:
            Wt[:, 0] *= -1
        Fw = X @ Wt                                      # (336, 3) window factor returns
        Ft = R[t, el] @ Wt
        A = np.column_stack([np.ones(WIN), Fw])
        B, *_ = np.linalg.lstsq(A, X, rcond=None)        # (4, k)
        ld = B[1:].T                                     # (k, 3)
        F[t] = Ft
        LOAD[t, el] = ld
        resid[t, el] = R[t, el] - ld @ Ft
    return R, resid, F, LOAD, VE, NE


def _edge_worker(args):
    from bidask import edge
    o, h, l, c = args
    n = len(c)
    out = np.full(n, np.nan)
    fin = np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c)
    run = np.convolve(fin.astype(int), np.ones(EDGE_BARS, int), "full")[:n]
    for t in np.flatnonzero(run == EDGE_BARS):
        sl = slice(t - EDGE_BARS + 1, t + 1)
        try:
            v = edge(o[sl], h[sl], l[sl], c[sl])
        except Exception:
            v = np.nan
        out[t] = v if v is not None else np.nan
    return out


def rolling_edge(O, H, L_, C):
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(7) as pool:
        cols = pool.map(_edge_worker, [(O[:, j], H[:, j], L_[:, j], C[:, j])
                                       for j in range(C.shape[1])], chunksize=4)
    return np.column_stack(cols)


def load_1m_volume(ticker):
    """Dense minute array of volume and log close from the ticker's first minute."""
    f = os.path.join(RAW_DIR, f"{ticker}_USDT_USDT-1m-futures.feather")
    d = pd.read_feather(f, columns=["date", "close", "volume"])
    ix = (pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
          .to_numpy().astype("datetime64[m]"))
    t0 = ix.min()
    off = ((ix - t0) / np.timedelta64(1, "m")).astype(np.int64)
    v = np.full(off.max() + 1, np.nan)
    c = np.full(off.max() + 1, np.nan)
    v[off] = d["volume"].to_numpy(float)
    c[off] = np.log(d["close"].to_numpy(float))
    return t0, v, c


def prepare():
    """Everything the features read that does not depend on WHICH entries:
    the panel, the trailing-PCA factor and residuals, the raw 30m OHLCV and the
    rolling EDGE, every bar and ticker. Shared by main() and any re-anchored
    computation (delayed2.py), so the features have one definition."""
    t0 = time.time()
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    pidx = pd.to_datetime(panel.index)
    cols = list(panel.columns)
    ixc = {c: k for k, c in enumerate(cols)}
    LC = panel.to_numpy(float)
    R, resid, F, LOAD, VE, NE = market_factor(LC)
    print(f"  [prepare] market factor   [{time.time()-t0:.0f}s]", flush=True)
    V = raw_panel("volume", pidx, cols)
    O = raw_panel("open", pidx, cols)
    Hh = raw_panel("high", pidx, cols)
    Ll = raw_panel("low", pidx, cols)
    Cc = raw_panel("close", pidx, cols)
    print(f"  raw 30m OHLCV loaded   [{time.time()-t0:.0f}s]")
    E = rolling_edge(O, Hh, Ll, Cc)
    print(f"  rolling 48-bar EDGE at every bar, every ticker   [{time.time()-t0:.0f}s]")
    return dict(pidx=pidx, cols=cols, ixc=ixc, LC=LC, R=R, resid=resid, F=F, LOAD=LOAD,
                VE=VE, NE=NE, V=V, E=E)


def compute(M, P, used, t0):
    """The 20 features for the entries in M (bar_index, entry_time, tickers, beta,
    sigma, z_at_entry), anchored at M.bar_index and, for the 1-minute versions,
    at entry_time + 29 minutes. `used` marks the rows that get 1-minute versions.
    Returns dict(feats, cause, touch, dom_store, max_off, s, J)."""
    pidx, ixc = P["pidx"], P["ixc"]
    resid, F, LOAD, V, E = P["resid"], P["F"], P["LOAD"], P["V"], P["E"]
    N_ep = len(M)
    J = M.bar_index.to_numpy(int)
    if not (pidx[J] == pd.to_datetime(M.entry_time)).all():
        raise SystemExit("[WHY] meta.bar_index does not resolve to entry_time.")
    ja = M.ticker_a.map(ixc).to_numpy(int)
    jb = M.ticker_b.map(ixc).to_numpy(int)
    beta = M.beta.to_numpy(float)
    sig = M.sigma.to_numpy(float)
    s = np.sign(M.z_at_entry.to_numpy(float))
    s[s == 0] = 1.0
    feats, cause = {}, {}
    touch = {}
    dom_store = {}
    rows = np.arange(N_ep)
    for L in LOOKS:
        offs = np.arange(-L + 1, 1)
        I = J[:, None] + offs[None, :]
        ra, rb = resid[I, ja[:, None]], resid[I, jb[:, None]]
        cA = ra.sum(1)
        cB = -beta * rb.sum(1)
        miss_res = ~(np.isfinite(ra).all(1) & np.isfinite(rb).all(1))
        domA = np.abs(cA) >= np.abs(cB)
        jd, jo = np.where(domA, ja, jb), np.where(domA, jb, ja)
        cd = np.where(domA, cA, cB)
        dom_store[L] = (domA, jd, jo, cd)
        lone = np.maximum(np.abs(cA), np.abs(cB)) / (np.abs(cA) + np.abs(cB))
        la, lb = LOAD[I, ja[:, None]].astype(float), LOAD[I, jb[:, None]].astype(float)
        FF = F[I]                                                    # (N, L, 3)
        comm = ((la - beta[:, None, None] * lb) * FF).sum((1, 2))
        res_sp = cA + cB
        common = np.abs(comm) / (np.abs(comm) + np.abs(res_sp))
        mkt = np.abs(F[I, 0].sum(1))
        Ib = J[:, None] + np.arange(-L - WIN + 1, -L + 1)[None, :]   # 336 bars before the window
        vwin_d = np.nanmean(V[I, jd[:, None]], 1)
        vwin_o = np.nanmean(V[I, jo[:, None]], 1)
        vb_d, vb_o = take(V, Ib, jd[:, None]), take(V, Ib, jo[:, None])
        med_d, med_o = np.nanmedian(vb_d, 1), np.nanmedian(vb_o, 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            sp_d = vwin_d / med_d
            sp_o = vwin_o / med_o
            vratio_ = sp_d / sp_o
            vadj = (s * cd / sig) * (np.nanmean(vb_d, 1) / vwin_d)
        eI = J[:, None] + np.arange(-EDGE_BASE, 0)[None, :]
        e_now = E[J, jo]
        e_base = np.nanmedian(take(E, eI, jo[:, None]), 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            lag = e_now / e_base
        sfx = f"_{L}"
        # Without both residuals the DOMINANT leg is undefined, so every
        # dominant-leg feature is missing there -- never computed on whichever
        # leg a NaN comparison happened to pick.
        dom_dep = {"vol_spike_mover", "vol_spike_ratio", "vadj_resid", "lagger_spread"}
        for nm, v in (("lone_share", lone), ("common_share", common), ("mkt_move", mkt),
                      ("vol_spike_mover", sp_d), ("vol_spike_ratio", vratio_),
                      ("vadj_resid", vadj), ("lagger_spread", lag)):
            v = np.where(np.isfinite(v), v, np.nan)
            if nm in dom_dep:
                v = np.where(miss_res, np.nan, v)
            feats[nm + sfx] = v
            c = np.full(N_ep, "", dtype=object)
            if nm in ("lone_share", "common_share", "mkt_move"):
                c[miss_res] = "a leg not in the factor fit (listing edge / gap)"
            elif nm in ("vol_spike_mover", "vol_spike_ratio", "vadj_resid"):
                c[miss_res] = "a leg not in the factor fit (listing edge / gap)"
                c[(c == "") & ~np.isfinite(v)] = "volume missing or zero baseline"
            else:
                c[miss_res] = "a leg not in the factor fit (listing edge / gap)"
                c[(c == "") & ~np.isfinite(e_now)] = "EDGE undefined at entry"
                c[(c == "") & ~np.isfinite(v)] = "EDGE baseline missing or zero"
            c[(c == "") & ~np.isfinite(v)] = "other non-finite"
            cause[nm + sfx] = c
        touch[f"factor/resid L={L}"] = I.max(1)              # windows end at i
        touch[f"volume L={L}"] = np.maximum(I.max(1), Ib.max(1))
        touch[f"EDGE L={L}"] = np.maximum(J, eI.max(1))
    print(f"  30m features built   [{time.time()-t0:.0f}s]")
    # ---------------- 1m versions ----------------
    print("STEP 2b -- 1-minute versions of vol_spike_mover / vol_spike_ratio / vadj_resid")
    r1 = np.flatnonzero(used)
    entry_m = pd.to_datetime(M.entry_time).to_numpy().astype("datetime64[m]")
    last = entry_m + np.timedelta64(29, "m")
    need = {}
    for L in LOOKS:
        domA = dom_store[L][0]
        for leg in ("d", "o"):
            need[(L, leg)] = np.where(domA if leg == "d" else ~domA, M.ticker_a.to_numpy(),
                                      M.ticker_b.to_numpy())
    S1 = {(L, leg, q): np.full(N_ep, np.nan) for L in LOOKS for leg in ("d", "o")
          for q in ("win", "med", "mean", "dlog")}
    max_off = -10 ** 9
    nmiss = np.zeros(N_ep, int)
    tick = sorted(set(M.ticker_a.iloc[r1]) | set(M.ticker_b.iloc[r1]))
    for ti, tk in enumerate(tick):
        t0m, vol, lc = load_1m_volume(tk)
        for L in LOOKS:
            for leg in ("d", "o"):
                rr = r1[need[(L, leg)][r1] == tk]
                if not len(rr):
                    continue
                endo = ((last[rr] - t0m) / np.timedelta64(1, "m")).astype(np.int64)
                max_off = max(max_off, int((last[rr] - entry_m[rr]).max() / np.timedelta64(1, "m")))
                wI = endo[:, None] + np.arange(-L + 1, 1)[None, :]
                bI = endo[:, None] + np.arange(-L - MIN7 + 1, -L + 1)[None, :]
                ok_w = (wI >= 0) & (wI < len(vol))
                ok_b = (bI >= 0) & (bI < len(vol))
                vw = np.where(ok_w, vol[np.clip(wI, 0, len(vol) - 1)], np.nan)
                vb = np.where(ok_b, vol[np.clip(bI, 0, len(vol) - 1)], np.nan)
                with np.errstate(invalid="ignore"):
                    S1[(L, leg, "win")][rr] = np.nanmean(vw, 1)
                    S1[(L, leg, "med")][rr] = np.nanmedian(vb, 1)
                    S1[(L, leg, "mean")][rr] = np.nanmean(vb, 1)
                pe = np.where((endo >= 0) & (endo < len(lc)), lc[np.clip(endo, 0, len(lc) - 1)], np.nan)
                ps = endo - L
                p0 = np.where((ps >= 0) & (ps < len(lc)), lc[np.clip(ps, 0, len(lc) - 1)], np.nan)
                S1[(L, leg, "dlog")][rr] = pe - p0
                if leg == "d":
                    nmiss[rr] += (~np.isfinite(vw)).sum(1)
        if (ti + 1) % 50 == 0:
            print(f"    1m volume: {ti+1} of {len(tick)} tickers   [{time.time()-t0:.0f}s]",
                  flush=True)
    for L in LOOKS:
        domA = dom_store[L][0]
        undef = ~np.isfinite(feats[f"lone_share_{L}"])   # dominant leg undefined
        bd = np.where(domA, 1.0, -beta)            # the dominant leg's weight in the spread
        with np.errstate(divide="ignore", invalid="ignore"):
            spd = S1[(L, "d", "win")] / S1[(L, "d", "med")]
            spo = S1[(L, "o", "win")] / S1[(L, "o", "med")]
            v1 = {"vol_spike_mover_1m": spd, "vol_spike_ratio_1m": spd / spo,
                  "vadj_resid_1m": (s * bd * S1[(L, "d", "dlog")] / sig)
                                   * (S1[(L, "d", "mean")] / S1[(L, "d", "win")])}
        for nm, v in v1.items():
            v = np.where(np.isfinite(v) & ~undef, v, np.nan)
            m1 = np.zeros(N_ep, bool)
            m1[r1] = True
            v[~m1] = np.nan
            feats[f"{nm}_{L}"] = v
            c = np.full(N_ep, "", dtype=object)
            c[~m1] = "outside the 53,757 1-minute set"
            c[(c == "") & undef] = "a leg not in the factor fit (dominant leg undefined)"
            c[(c == "") & ~np.isfinite(v)] = "1m volume missing or zero median"
            cause[f"{nm}_{L}"] = c
    print(f"  1m features built; max minute read relative to entry_time: +{max_off} "
          f"(must be +29)   [{time.time()-t0:.0f}s]")
    print()
    return dict(feats=feats, cause=cause, touch=touch, dom_store=dom_store, max_off=max_off,
                s=s, J=J)


def main():
    t0 = time.time()
    M = pd.read_parquet(paths.META)
    N_ep = len(M)
    P = prepare()
    pidx, ixc, LC = P["pidx"], P["ixc"], P["LC"]
    R, F, VE, NE = P["R"], P["F"], P["VE"], P["NE"]
    print("=" * 112)
    print("WHY-IT-MOVED -- build and checks")
    print("=" * 112)
    print(f"  panel {LC.shape[0]:,} bars x {LC.shape[1]} tickers ({pidx[0]} -> {pidx[-1]}); "
          f"{N_ep:,} episodes")
    print()
    # ---------------- Step 1 ----------------
    print("STEP 1 -- trailing PCA market factor, every bar, previous 336 bars, 3 components")
    print(f"  fitted on {int((NE >= 10).sum()):,} bars; eligible tickers per bar: median "
          f"{int(np.median(NE[NE >= 10]))}, min {int(NE[NE >= 10].min())}, max {NE.max()}   "
          f"[{time.time()-t0:.0f}s]")
    ve = pd.DataFrame(VE, index=pidx, columns=["PC1", "PC2", "PC3"]).dropna()
    vm = ve.groupby(ve.index.to_period("Q")).median()
    print("  variance explained (share of the correlation trace), median by quarter:")
    for q, r in vm.iterrows():
        print(f"    {str(q):<8} PC1 {r.PC1:.3f}  PC2 {r.PC2:.3f}  PC3 {r.PC3:.3f}  "
              f"(sum {r.sum():.3f})")
    print(f"  over all bars: PC1 median {ve.PC1.median():.3f} [p5 {ve.PC1.quantile(.05):.3f}, "
          f"p95 {ve.PC1.quantile(.95):.3f}]; PC2 {ve.PC2.median():.3f}; PC3 {ve.PC3.median():.3f}")
    btc = R[:, ixc["BTC"]] if "BTC" in ixc else None
    m = np.isfinite(F[:, 0]) & np.isfinite(btc)
    cb = float(np.corrcoef(F[m, 0], btc[m])[0, 1])
    cbq = pd.Series(F[m, 0], index=pidx[m]).groupby(pidx[m].to_period("Q")).apply(
        lambda x: np.corrcoef(x.to_numpy(), btc[m][pidx[m].to_period("Q") == x.name])[0, 1])
    print(f"  corr(PC1 return, BTC return), all bars: {cb:.3f}"
          + ("" if cb > 0.7 else "   <-- NOT high, as the brief expected"))
    print("    by quarter: " + ", ".join(f"{q} {v:.3f}" for q, v in cbq.items()))
    print()
    # ---------------- Step 2: 30m features ----------------
    print("STEP 2 -- features at the entry bar, lookbacks 4 and 12 bars")
    from envelope import scan_1m_coverage, select_1m_subset
    cov = scan_1m_coverage(M, verbose=False)
    used, _ = select_1m_subset(M, cov, verbose=False)
    r1 = np.flatnonzero(used)
    C = compute(M, P, used, t0)
    feats, cause, touch, dom_store = C["feats"], C["cause"], C["touch"], C["dom_store"]
    max_off, s, J = C["max_off"], C["s"], C["J"]
    # sign convention
    print("  SIGN CONVENTION (features are unsigned or folded; reported, not used):")
    for L in LOOKS:
        domA, jd, jo, cd = dom_store[L]
        push = (s * cd) > 0
        print(f"    L={L:>2}: dominant leg is A on {domA.mean():.3f}; the dominant leg's "
              f"contribution pushed the spread TOWARD the dislocation (sign = sign(z)) on "
              f"{push.mean():.3f}")
    print()
    # ---------------- CHECKS ----------------
    print("=" * 112)
    print("CHECKS")
    print("=" * 112)
    bad = False
    print("  LOOKAHEAD -- max 30m index touched minus the entry index, per family:")
    for k, v in touch.items():
        d = int((v - J).max())
        print(f"    {k:<22} max {d:+d} (must be <= 0)")
        bad |= d > 0
    print(f"    1-minute families      max minute +{max_off} relative to entry_time "
          f"(must be <= +29)")
    bad |= max_off > 29
    if bad:
        raise SystemExit("[WHY] STOP -- a feature reads past the entry bar.")
    print("    -> PASS")
    print()
    names = list(feats.keys())
    print(f"  COVERAGE and DISTRIBUTION ({N_ep:,} episodes; _1m features on the 53,757 set)")
    print(f"    {'feature':<26}{'finite':>8}{'of':>8}{'median':>11}{'p5':>11}{'p95':>11}"
          f"   missing by cause")
    for nm in names:
        v = feats[nm]
        base = int(used.sum()) if nm.endswith(("_1m_4", "_1m_12")) else N_ep
        fin = np.isfinite(v)
        cs = pd.Series(cause[nm][~fin]).value_counts()
        cs = cs[cs.index != "outside the 53,757 1-minute set"]
        print(f"    {nm:<26}{int(fin.sum()):>8,}{base:>8,}{np.nanmedian(v):>11.4g}"
              f"{np.nanpercentile(v, 5):>11.4g}{np.nanpercentile(v, 95):>11.4g}   "
              + "; ".join(f"{k}: {n_:,}" for k, n_ in cs.items()))
    print()
    print("  SPEARMAN against the existing six (on the 53,757 set), flag > 0.8 vs vol_48 / vol_48_1m")
    fz = np.load(paths.ENVFEAT, allow_pickle=False)
    X5 = fz["X"].astype(float)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], r1):
        raise SystemExit("[WHY] vol48_1m rows differ from the 53,757 set.")
    six = {"vol_48": X5[r1, 0], "vol_48_1m": v48["vol_48_1m"], "vratio": X5[r1, 1],
           "vol_slope": X5[r1, 2], "sandwich": X5[r1, 3], "off_mark": X5[r1, 4]}
    print(f"    {'feature':<26}" + "".join(f"{k:>11}" for k in six))
    flags = []
    for nm in names:
        v = feats[nm][r1]
        row = []
        for k, w in six.items():
            m_ = np.isfinite(v) & np.isfinite(w)
            row.append(pd.Series(v[m_]).corr(pd.Series(w[m_]), method="spearman"))
        fl = max(abs(row[0]), abs(row[1])) > 0.8
        if fl:
            flags.append(nm)
        print(f"    {nm:<26}" + "".join(f"{x:>+11.3f}" for x in row)
              + ("   RESTATES VOLATILITY" if fl else ""))
    print(f"  flagged 'restates volatility': {', '.join(flags) if flags else 'none'}")
    np.savez_compressed(OUT, names=np.array(names), X=np.column_stack([feats[n] for n in names]),
                        restates=np.array(flags), ticker_a=M.ticker_a.to_numpy(str),
                        ticker_b=M.ticker_b.to_numpy(str),
                        entry_time=pd.to_datetime(M.entry_time).to_numpy("datetime64[ns]"))
    print(f"  [WROTE] {os.path.relpath(OUT, paths.RESEARCH)}  ({N_ep:,} x {len(names)})")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    main()
