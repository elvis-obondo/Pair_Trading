"""HL-WALLET1 validator for hl5_features.py: 300 events + 300 control links, recomputed independently.

    python -u research/dislocation_model/hl5_valid.py [--days N]

For each sampled row and each of the five windows, recompute all 15 features from the raw T1 / T2 files with plain pandas
(filtering each file to bins < t = 0, groupby per wallet, skill by an explicit loop over the previous 30 days' T2 files, deciles
over the wallets active on day D-1), no rolling state, no searchsorted. Compare with hl5_features.npz (float32: rtol 1e-4, atol 1e-6);
the NaN pattern must match exactly. Any mismatch aborts.
"""
import os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hl5_features as H

SEED, NROWS = 20261016, 300


def t1_range(coin, lo_ms, hi_ms):
    """T1 rows of one coin with bin in [lo, hi): read the day files that can hold them, filter, nothing else."""
    d0 = pd.Timestamp(lo_ms, unit="ms", tz="UTC").floor("D")
    d1 = pd.Timestamp(hi_ms - 1, unit="ms", tz="UTC").floor("D")
    parts = []
    for d in pd.date_range(d0, d1, freq="D"):
        x = H.load_t1(d)
        if x is None:
            continue
        x = x[x.coin.astype(str) == coin]
        b = H.ms_of(x.bin)
        parts.append(x[(b >= lo_ms) & (b < hi_ms)])
    return pd.concat(parts, ignore_index=True) if parts else None


def skill_table(D):
    """wallet -> skill from T2 of D-30..D-1; and the set of wallets active on D-1; forced counts."""
    frames = []
    for k in range(1, H.TRAIL_SKILL + 1):
        x = H.load_t2(D - pd.Timedelta(days=k))
        if x is not None:
            frames.append(x)
    if not frames:
        return pd.Series(dtype=float), set(), pd.Series(dtype=float)
    A = pd.concat(frames)
    g = A.groupby("wallet")
    vol, pnl, nf, fo = g.volume_usd.sum(), g.closed_pnl_usd.sum(), g.n_fills.sum(), g.n_forced_events.sum()
    act = g.size()
    sk = (pnl / vol) * nf / (nf + H.K_SHRINK)
    sk = sk[(act >= H.MIN_ACTIVE) & (vol > 0)]
    prev = H.load_t2(D - pd.Timedelta(days=1))
    return sk, set(prev.wallet) if prev is not None else set(), fo


def expected(coin, T, d, holes, cand):
    t0 = int(H.ms_of(pd.Series([T]))[0]) + 30 * 60_000
    D = pd.Timestamp(T).tz_convert("UTC").floor("D") if pd.Timestamp(T).tzinfo else pd.Timestamp(T, tz="UTC").floor("D")
    sk, prev_active, fo = skill_table(D)
    cuts = None
    pa = sk[sk.index.isin(prev_active)]
    if len(pa) >= 100:
        cuts = (np.percentile(pa.to_numpy(), 10), np.percentile(pa.to_numpy(), 90))
    # persistent set
    pparts, nd = [], 0
    for k in range(1, H.TRAIL_PERS + 1):
        x = H.load_t1(D - pd.Timedelta(days=k))
        if x is not None:
            nd += 1
            x = x[x.coin.astype(str) == coin]
            pparts.append(x.assign(n=x.taker_buy_usd + x.taker_sell_usd).groupby("wallet").n.sum())
    pers = None
    if nd >= H.MIN_PERS_DAYS:
        s = pd.concat(pparts).groupby(level=0).sum().sort_values(ascending=False, kind="stable")
        pers = set(s.index[:10]) if len(s) else None
        if not len(s):
            pers = None
    out = np.full((len(H.WN), H.NF), np.nan)
    for wi, w in enumerate(H.WN):
        bw, ew = H.WINS[w]
        lo, hi = t0 - bw * 60_000, t0 - ew * 60_000
        if lo < int(H.DATA_START.value // 10**6) or ((H.hole_bin_ms() >= lo) & (H.hole_bin_ms() < hi)).any():
            continue
        x = t1_range(coin, lo, hi)
        if x is None:
            x = pd.DataFrame(columns=["wallet", "taker_buy_usd", "taker_sell_usd", "twap_usd", "forced_long_usd", "forced_short_usd",
                                      "absorbed_buy_usd", "absorbed_sell_usd"])
        both = x.taker_buy_usd.sum() + x.taker_sell_usd.sum()
        push = x.taker_buy_usd if d > 0 else x.taker_sell_usd
        pt = push.sum()
        f = np.full(H.NF, np.nan)
        f[H.FEATS.index("push_total")] = pt
        f[H.FEATS.index("forced_push")] = (x.forced_short_usd if d > 0 else x.forced_long_usd).sum()
        opp = x.absorbed_sell_usd if d > 0 else x.absorbed_buy_usd
        f[H.FEATS.index("absorbed_opp")] = opp[x.wallet.isin(cand)].sum()
        if pt > 0:
            sw = push.groupby(x.wallet).sum()
            sw = sw[sw > 0]
            sh = (sw / pt).sort_values(ascending=False)
            f[0], f[1], f[2], f[3] = sh.iloc[0], sh.iloc[:3].sum(), (sh ** 2).sum(), len(sh)
            if pers is not None:
                f[4] = sw[sw.index.isin(pers)].sum() / pt
            if not x.twap_usd.isna().any() and both > 0:
                f[5] = x.twap_usd.sum() / both
            s_ = sk.reindex(sw.index)
            ok = s_.notna()
            if ok.any():
                f[6] = (s_[ok] * sw[ok]).sum() / sw[ok].sum()
            f[7] = sw[ok].sum() / pt
            if cuts is not None:
                f[8] = sw[ok & (s_ <= cuts[0])].sum() / pt
                f[9] = sw[ok & (s_ >= cuts[1])].sum() / pt
            fz = fo.reindex(sw.index).fillna(0)
            f[10] = sw[fz > 0].sum() / pt
            f[11] = f[H.FEATS.index("absorbed_opp")] / pt
        else:
            f[3] = 0.0
        out[wi] = f
    return out


def run():
    t0 = time.time()
    EV, PR = pd.read_parquet(H.EVENTS), pd.read_parquet(H.PAIRS)
    Z = np.load(H.OUT)
    cand = set(H.candidates())
    holes = H.hole_bin_ms()
    rng = np.random.default_rng(SEED)
    ndays = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else None
    lim = pd.Timestamp("2025-05-25", tz="UTC") + pd.Timedelta(days=ndays) if ndays else None
    bad, ncmp, maxerr = [], 0, 0.0
    for kind, tbl, arr in (("event", EV, Z["ev"]), ("link", PR, Z["pr"])):
        T = pd.to_datetime(tbl["T"], utc=True)
        pool = np.flatnonzero(T < lim) if lim is not None else np.arange(len(tbl))
        rows = np.sort(rng.choice(pool, min(NROWS, len(pool)), replace=False))
        for r in rows:
            row = tbl.iloc[r]
            exp = expected(row["coin"], row["T"], row["d"], holes, cand)
            got = arr[r].astype(float)
            for wi in range(len(H.WN)):
                for fi in range(H.NF):
                    v, g = exp[wi, fi], got[wi, fi]
                    ncmp += 1
                    if np.isnan(v) != np.isnan(g):
                        bad.append((kind, int(r), H.WN[wi], H.FEATS[fi], v, g)); continue
                    if np.isnan(v):
                        continue
                    err = abs(v - g); maxerr = max(maxerr, err)
                    if err > 1e-6 + 1e-4 * abs(v):
                        bad.append((kind, int(r), H.WN[wi], H.FEATS[fi], v, g))
    print(f"[HL5-VALID] {2 * NROWS} rows x {len(H.WN)} windows x {H.NF} features = {ncmp:,} comparisons; mismatches {len(bad)}; "
          f"max abs diff {maxerr:.2e}  [{time.time() - t0:.0f}s]")
    for b in bad[:20]:
        print("  MISMATCH", b)
    if bad:
        raise SystemExit("[HL5-VALID] FAILED")
    print("[HL5-VALID] PASS")


if __name__ == "__main__":
    run()
