"""HL-MASTER1 G2: hedge quality at t = 0, pair level. Features only (no label); every value uses information at minute < t = 0 = T + 30 min.

    python -u research/dataset/master_g2.py > research/dataset/logs/master_g2.log

INPUT: stage A events (research/datasets/master/work/pair/events.parquet), the 30m log-price panel (the same panel stage A used), the 30m high/low
of both legs, and the 1-minute log closes of both legs. a = leg A (numerator), b = leg B; all prices are LOG prices; i = the trigger bar's index inside its
NaN-free segment; every window ENDS at bar i (the close observed at T + 30 min) and reaches back inside the segment only.

COLUMNS (definition; sign; missing rule). Expected direction (recorded, not tested): r2 higher -> reverts more (OKX evidence); every other column two-sided.
  r2_2d              squared Pearson correlation of the two log-price LEVELS over the 96 bars (2 d) ending at i  (= stage A's r2; asserted equal)
  r2_7d              the same over 336 bars (7 d)
  corr_30m_2d, corr_30m_7d   Pearson correlation of the legs' 30-minute log RETURNS over the last 96 / 336 bars ending at i
  corr_1m_24h        Pearson correlation of the legs' 1-minute log returns over the 1,440 minutes ending with the 1m bar labelled T + 29 (the trigger close);
                     a return is used only when both legs have both of its minute closes; NaN if fewer than 1,000 usable minutes; n_1m_24h = usable minutes
  beta, abs_beta, sign_beta   the entry-geometry beta (vol-matched sd(a)/sd(b) signed by the covariance, 96-bar), its absolute value and sign
  neutrality         |1 - |beta|| / (1 + |beta|)   (0 = equal-notional legs; symmetric under swapping the legs)
  beta_stab          std/|mean| of the rolling beta over the 336 bars to i (stage A's column, copied)
  beta_chg_24h, beta_chg_7d   beta[i] - beta[i-48] and beta[i] - beta[i-336]; NaN when the earlier bar is before the segment's first finite beta
  vol_ratio_2d, vol_ratio_7d  sd(30m returns of A) / sd(30m returns of B) over 96 / 336 bars (ddof 1)
  crossings_7d       number of sign changes of the standardised spread w (frozen entry geometry) over the 336 bars to i (335 transitions); NaN if the trigger is younger than 336 bars (coin unit only)
  halflife_h         AR(1) half-life of w over the 336 bars in hours: w_t = c + phi w_{t-1} fitted by OLS; -ln2/ln(phi) x 0.5 if 0 < phi < 1, else NaN (not mean-reverting)
  phi_7d             the AR(1) coefficient itself (always defined)
  vratio             envfeat's: sd(steps)/sd(levels) of the sign-folded w over the last 96 bars x 3.396899 (iid = 1)
  vol_slope          envfeat's: sd of the last 16 steps / sd of the 32 steps before them
  sandwich           envfeat's cohesion: mean over the last 96 bars of (the sign-folded spread's within-bar maximum, from the legs' 30m high/low, minus its close) / sigma;
                     the beta-sign-correct bound; NaN bars skipped; NaN if none
  flag columns: g2_nan_1m (1 if corr_1m_24h is NaN), seg_bars (bars into the segment, stage A's bars_into_segment, so a short history is visible)
GAP-FILLS tagged A: crossings_7d, halflife_h and phi_7d use the FROZEN entry geometry (mu, beta, alpha, sigma estimated at i, applied back over the 336 bars), not a
rolling mean per bar; corr_1m_24h keeps flat (carried-close) minutes as zero returns and excludes NaN minutes.
SIGN FOLDING. vratio, vol_slope, sandwich use w multiplied by sign(z) like envfeat, so they are invariant to a global flip. crossings, halflife and phi are
sign invariant by construction. Swapping A and B: r2, corr_*, neutrality, crossings, halflife, phi, vratio, vol_slope, sandwich are unchanged; beta, abs_beta,
vol_ratio_* become reciprocals; beta_chg, beta_stab change (tested in the symmetry test, not asserted equal).
"""
import os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths
import universe_panel, rolling_spread as rs
from adapters.hyperliquid_futures import bar_file
from envelope import load_1m_series
from envfeat import iid_vratio_norm

WORK = os.path.join(paths.DATASETS, "master", "work", "pair")
FIT, ENTRY, FAST, SLOW, SAND = 336, 96, 16, 32, 96
NAMES = ["r2_2d", "r2_7d", "corr_30m_2d", "corr_30m_7d", "corr_1m_24h", "n_1m_24h", "both_traded_share_24h", "beta", "abs_beta", "sign_beta", "neutrality", "beta_stab",
         "beta_chg_24h", "beta_chg_7d", "vol_ratio_2d", "vol_ratio_7d", "crossings_7d", "halflife_h", "phi_7d", "vratio", "vol_slope", "sandwich",
         "g2_nan_1m", "seg_bars"]
VDIV = iid_vratio_norm(ENTRY)

panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
idx = pd.to_datetime(panel.index)
V = panel.to_numpy(float)
cols = list(panel.columns)
ix = {c: j for j, c in enumerate(cols)}
pairs = universe_panel.tradeable_pairs(cols)
HI = np.full(V.shape, np.nan)
LO = np.full(V.shape, np.nan)
SER = None
E = None
EVG = {}
TRD = {}


def load_hilo():
    for c in cols:
        d = pd.read_feather(bar_file(c, "30m"), columns=["date", "high", "low"])
        t = pd.to_datetime(d.date, utc=True).dt.tz_localize(None)
        for arr, fld in ((HI, "high"), (LO, "low")):
            arr[:, ix[c]] = pd.Series(np.log(d[fld].to_numpy(float)), index=t).reindex(idx).to_numpy()


def roll_r2(a, b, w):
    sa, sb = pd.Series(a), pd.Series(b)
    cov, va, vb = sa.rolling(w).cov(sb), sa.rolling(w).var(), sb.rolling(w).var()
    with np.errstate(divide="ignore", invalid="ignore"):
        return ((cov ** 2) / (va * vb)).to_numpy()


def crossings(w):
    """Sign changes of each row of w (n, T): the number of t with w[t] * w[t-1] < 0."""
    return (w[:, 1:] * w[:, :-1] < 0).sum(1)


def ar1_phi(w):
    """OLS slope of w[t] on w[t-1] (with intercept) per row."""
    x0, x1 = w[:, :-1], w[:, 1:]
    x0m, x1m = x0 - x0.mean(1, keepdims=True), x1 - x1.mean(1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (x0m * x1m).sum(1) / (x0m ** 2).sum(1)


def halflife_h(phi):
    """AR(1) half-life in hours for 30-minute bars: -ln 2 / ln phi x 0.5 if 0 < phi < 1, else NaN."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where((phi > 0) & (phi < 1), -np.log(2) / np.log(phi) * 0.5, np.nan)


def kernel(a, b, hia, loa, hib, lob, ii, z, be, al, mu, sg, bstab, ta1, tb1, A1, B1, TA, TB):
    """G2 for the events at positions `ii` of one NaN-free segment (arrays a, b = log closes of the two legs, hia.. = 30m log high/low).

    ta1/tb1 are the offsets of the 1m bar labelled T + 29 into each leg's own dense minute array A1/B1 (log closes, NaN = no price).
    Everything read is at index <= ii (30m) or <= ta1/tb1 (1m).
    """
    n = len(ii)
    out = np.full((n, len(NAMES)), np.nan)
    r = rs.rolling_spread_stats(a, b, 0.5)
    r2_96 = r.r2
    r2_336 = roll_r2(a, b, FIT)
    pad = lambda x: np.r_[np.nan, np.diff(x)]
    ra, rb = pd.Series(pad(a)), pd.Series(pad(b))
    c96, c336 = ra.rolling(ENTRY).corr(rb).to_numpy(), ra.rolling(FIT).corr(rb).to_numpy()
    sd = lambda s, w: s.rolling(w).std().to_numpy()
    vr96, vr336 = sd(ra, ENTRY) / sd(rb, ENTRY), sd(ra, FIT) / sd(rb, FIT)
    beta = r.beta
    # standardised spread windows under each event's frozen geometry: (n, 336)
    # windows of 336 bars ending at ii; a trigger younger than 336 bars (coin unit) gets a NaN-padded front, and the 7-day columns below are set NaN for it
    pad_ = np.full(FIT, np.nan)
    Aw = np.lib.stride_tricks.sliding_window_view(np.r_[pad_, a], FIT)[ii + 1]
    Bw = np.lib.stride_tricks.sliding_window_view(np.r_[pad_, b], FIT)[ii + 1]
    young = ii < FIT - 1
    w = (Aw - be[:, None] * Bw - al[:, None] - mu[:, None]) / sg[:, None]
    s = np.where(z >= 0, 1.0, -1.0)
    wf = w * s[:, None]
    cross = np.where(young, np.nan, crossings(w))
    phi = np.where(young, np.nan, ar1_phi(w))
    hl = halflife_h(phi)
    lvl = wf[:, -ENTRY:]
    stp = np.diff(lvl, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        vratio = stp.std(1) / np.clip(lvl.std(1), 1e-12, None) * VDIV
    dW = np.diff(wf, axis=1)
    vol_slope = dW[:, -FAST:].std(1) / np.clip(dW[:, -(FAST + SLOW):-FAST].std(1), 1e-12, None)
    # sandwich over bars [i-95, i]
    off = np.arange(-(SAND - 1), 1)
    I = ii[:, None] + off[None, :]
    ha, la_, hb, lb = hia[I], loa[I], hib[I], lob[I]
    ca, cb = a[I], b[I]
    bb = be[:, None]
    sp_hi = ha - bb * np.where(bb > 0, lb, hb)
    sp_lo = la_ - bb * np.where(bb > 0, hb, lb)
    sp_cl = ca - bb * cb
    ss = s[:, None]
    gap = np.where(ss > 0, sp_hi, -sp_lo) - ss * sp_cl
    with np.errstate(invalid="ignore"):
        fin = np.isfinite(gap)
        cnt = fin.sum(1)
        sandwich = np.where(cnt > 0, np.where(fin, gap, 0.0).sum(1) / np.maximum(cnt, 1), np.nan) / sg
    # 1-minute correlation over 1,440 minutes ending at t1m (inclusive)
    c1m = np.full(n, np.nan)
    n1m = np.zeros(n)
    bts = np.full(n, np.nan)
    for j in range(n):
        ea, eb = int(ta1[j]), int(tb1[j])
        if ea - 1440 < 0 or eb - 1440 < 0 or ea >= len(A1) or eb >= len(B1):
            continue
        da, db = np.diff(A1[ea - 1440:ea + 1]), np.diff(B1[eb - 1440:eb + 1])
        m = np.isfinite(da) & np.isfinite(db)
        n1m[j] = m.sum()
        bts[j] = (TA[ea - 1439:ea + 1] * TB[eb - 1439:eb + 1]).sum() / 1440.0
        if m.sum() >= 1000:
            c1m[j] = np.corrcoef(da[m], db[m])[0, 1]
    cols_ = {
        "r2_2d": r2_96[ii], "r2_7d": r2_336[ii], "corr_30m_2d": c96[ii], "corr_30m_7d": c336[ii], "corr_1m_24h": c1m, "n_1m_24h": n1m, "both_traded_share_24h": bts,
        "beta": be, "abs_beta": np.abs(be), "sign_beta": np.sign(be), "neutrality": np.abs(1 - np.abs(be)) / (1 + np.abs(be)), "beta_stab": bstab,
        "beta_chg_24h": np.where(ii - 48 >= 0, be - beta[np.clip(ii - 48, 0, None)], np.nan),
        "beta_chg_7d": np.where(ii - FIT >= 0, be - beta[np.clip(ii - FIT, 0, None)], np.nan),
        "vol_ratio_2d": vr96[ii], "vol_ratio_7d": vr336[ii], "crossings_7d": cross, "halflife_h": hl, "phi_7d": phi,
        "vratio": vratio, "vol_slope": vol_slope, "sandwich": sandwich, "g2_nan_1m": np.isnan(c1m).astype(float), "seg_bars": ii.astype(float)}
    for q, nm in enumerate(NAMES):
        out[:, q] = cols_[nm]
    return out, r2_96[ii]


def pair_job(k):
    ev = EVG.get(k)
    if ev is None:
        return k, None
    a_, b_ = pairs[k]
    ja, jb = ix[a_], ix[b_]
    t0a, A1 = SER[a_]
    t0b, B1 = SER[b_]
    TA, TB = TRD[a_], TRD[b_]
    res = []
    for (g0, g1), g in ev.groupby(["seg_start_bar", "seg_end_bar"]):
        ii = g.bars_into_segment.to_numpy()
        T = g.entry_time.to_numpy().astype("datetime64[m]") + np.timedelta64(29, "m")
        ta1 = ((T - t0a) / np.timedelta64(1, "m")).astype(np.int64)
        tb1 = ((T - t0b) / np.timedelta64(1, "m")).astype(np.int64)
        o, r2chk = kernel(V[g0:g1, ja], V[g0:g1, jb], HI[g0:g1, ja], LO[g0:g1, ja], HI[g0:g1, jb], LO[g0:g1, jb], ii, g.z.to_numpy(), g.beta.to_numpy(),
                          g.alpha.to_numpy(), g.mu.to_numpy(), g.sigma.to_numpy(), g.beta_stab.to_numpy(), ta1, tb1, A1, B1, TA, TB)
        assert np.allclose(r2chk, g.r2.to_numpy(), equal_nan=True, atol=1e-12), "r2_2d differs from stage A's r2"
        res.append((g.event_id.to_numpy(), o))
    return k, res


def main():
    global SER, E, EVG
    t0 = time.time()
    E = pd.read_parquet(os.path.join(WORK, "events.parquet"))
    EVG = {k: g for k, g in E.groupby("pair_index")}
    load_hilo()
    coins = sorted(set(E.ticker_a) | set(E.ticker_b))
    SER = load_1m_series(coins, True)
    for c in coins:                                   # dense 'the coin traded in this minute' (1.0 / 0.0), same indexing as SER
        d = pd.read_feather(bar_file(c, "1m"), columns=["date", "mins_since_trade"])
        mi = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None).to_numpy().astype("datetime64[m]")
        off = ((mi - mi.min()) / np.timedelta64(1, "m")).astype(np.int64)
        arr = np.zeros(len(SER[c][1]))
        arr[off] = (d["mins_since_trade"].to_numpy(float) == 0).astype(float)
        TRD[c] = arr
    print(f"[G2] {len(E):,} events, {len(EVG):,} pairs; inputs loaded [{time.time() - t0:.0f}s]", flush=True)
    ids, outs = [], []
    with Pool(int(os.environ.get("NPROC", 8))) as pool:
        for q, (k, res) in enumerate(pool.imap(pair_job, sorted(EVG), chunksize=8)):
            if res:
                for i_, o_ in res:
                    ids.append(i_); outs.append(o_)
            if (q + 1) % 2000 == 0:
                print(f"  {q + 1} pairs  [{time.time() - t0:.0f}s]", flush=True)
    ev = np.concatenate(ids)
    X = np.concatenate(outs)
    G = pd.DataFrame(X.astype(np.float32), columns=NAMES)
    G.insert(0, "event_id", ev)
    G = G.sort_values("event_id").reset_index(drop=True)
    assert len(G) == len(E) and (G.event_id.to_numpy() == E.event_id.to_numpy()).all()
    G.to_parquet(os.path.join(WORK, "g2.parquet"), index=False)
    print(f"[DONE] {len(G):,} rows x {len(NAMES)} columns  [{time.time() - t0:.0f}s]")
    for nm in NAMES:
        v = G[nm].to_numpy(float)
        print(f"  {nm:<14} NaN {100 * np.isnan(v).mean():6.2f}%  p5 {np.nanpercentile(v, 5):+.4g}  median {np.nanmedian(v):+.4g}  p95 {np.nanpercentile(v, 95):+.4g}")
    # invariants
    assert ((G.r2_2d >= -1e-6) & (G.r2_2d <= 1 + 1e-6)).all() and ((G.r2_7d.dropna() >= -1e-6) & (G.r2_7d.dropna() <= 1 + 1e-6)).all()
    for c in ("corr_30m_2d", "corr_30m_7d", "corr_1m_24h"):
        v = G[c].dropna()
        assert ((v >= -1 - 1e-5) & (v <= 1 + 1e-5)).all(), c
    assert (G.neutrality >= 0).all() and (G.neutrality <= 1).all()
    assert (G.crossings_7d >= 0).all() and (G.crossings_7d <= 335).all()
    print("[INVARIANTS] r2 in [0,1], correlations in [-1,1], neutrality in [0,1], crossings in [0,335]: OK")
    print("[MONTH] NaN share of corr_1m_24h and beta_chg_7d by month:")
    m = pd.to_datetime(E.entry_time).dt.to_period("M")
    print(G.assign(m=m.values).groupby("m")[["corr_1m_24h", "beta_chg_7d", "halflife_h", "sandwich"]].agg(lambda s: s.isna().mean()).round(4).to_string())


if __name__ == "__main__":
    main()
