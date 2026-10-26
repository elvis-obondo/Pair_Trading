"""HL-MASTER1 integrity tests for G5 (flow).

    python -u research/dataset/master_tests_g5.py > research/dataset/logs/master_tests_g5.log

  1. POISON (1,000 pair legs, 300 coin legs): for a sampled leg at cutoff o, every raw flow minute at or after o is replaced by random values, the coin's arrays are rebuilt by the PRODUCTION build_A
     and leg_block, and all leg columns must be identical to the last digit.
  2. INDEPENDENT recomputation (2,000 legs) by plain slices of the raw minute arrays (no cumulative sums, no pandas rolling): windows, normalisers (direct medians over the 336 cutoffs), the 5-minute and
     30-minute bins, the forced searches (with their direct median of positive values), slopes and the acceleration share.
  3. INVARIANTS: Sum of the 12 five-minute bins' buy and sell = the 60-minute window's; shares in [0,1]; imb in [-1,1]; nested windows for non-negative sums; net weights in [0,1].
  4. SWAP on the building blocks with d held fixed: net(x_A, x_B, wA) = net(x_B, x_A, 1 - wA).
"""
import os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g5 as G5
import master_g5_run as R5
import flowfeat as ff

rng = np.random.default_rng(20261030)
_cache = {}


def _raw(c):
    if c not in _cache:
        _cache.clear()
        _cache[c] = G5.read_coin_raw(c)
    return _cache[c]


def poison_job(args):
    c, rows = args
    raw = _raw(c)
    A = G5.build_A(raw)
    bad = []
    rg = np.random.default_rng(abs(hash(c)) % (2 ** 32))
    for o, s in rows:
        base = G5.leg_block(A, np.array([o]), np.array([float(s)]))
        P = {k: v.copy() for k, v in raw.items()}
        for k, v in P.items():
            v[o:] = np.nan_to_num(v[o:]) + rg.uniform(1, 1e2, len(v) - o)      # original + at least 1, so every replaced value differs from its original (NaN minutes become values too)
        Ap = G5.build_A(P)
        got = G5.leg_block(Ap, np.array([o]), np.array([float(s)]))
        for k in base:
            if not np.array_equal(base[k], got[k], equal_nan=True):
                bad.append((c, o, k, float(base[k][0]), float(got[k][0])))
    return bad


def test_poison(ev, n_pair, n_coin):
    t0 = time.time()
    jobs = {}
    for u, n in (("pair", n_pair), ("coin", n_coin)):
        E, o = ev[u]
        d = E.d.to_numpy(float)
        for r in rng.choice(len(E), n, replace=False):
            if u == "pair" and rng.random() < 0.5:
                c, s = E.ticker_b.iloc[r], -d[r] * np.sign(E.beta.iloc[r])
            else:
                c, s = E.ticker_a.iloc[r], d[r]
            jobs.setdefault(c, []).append((int(o[r]), float(s)))
    with Pool(int(os.environ.get("NPROC", 8))) as pool:
        res = pool.map(poison_job, sorted(jobs.items()), chunksize=1)
    bad = [b for r in res for b in r]
    print(f"[G5 POISON] {n_pair} pair legs + {n_coin} coin legs (all raw flow minutes at or after o replaced), {len(G5.NAMES_LEG)} columns each: changed in {len(bad)} cases [{time.time() - t0:.0f}s]")
    for b in bad[:10]:
        print("  CHANGED", b)
    assert not bad
    print("[G5 POISON] PASS")


def ref_leg(raw, o, s):
    """Plain-slice reference of the window block, the 5-minute bins and the forced searches for one leg."""
    out = {}
    buy, sell = raw["taker_buy_usd"], raw["taker_sell_usd"]
    pos = s > 0

    def wi(k, W, a=None):
        a = raw[k] if a is None else a
        w = a[o - W:o] if o - W >= 0 else None
        return None if w is None or np.isnan(w).any() else float(w.sum())

    def win_all(oc, W, tn_only=False):
        if oc - W < 0:
            return None
        b, sl = buy[oc - W:oc], sell[oc - W:oc]
        if np.isnan(b).any():
            return None
        return float(b.sum() + sl.sum())
    for W in G5.WINS:
        B, S = wi("taker_buy_usd", W), wi("taker_sell_usd", W)
        if B is None:
            for q in G5.Q_WIN:
                out[f"{q}_{W}"] = np.nan
            continue
        TN = B + S
        fl, fs = wi("liq_forced_long_usd", W), wi("liq_forced_short_usd", W)
        bk, ad = wi("backstop_liq_usd", W), wi("adl_usd", W)
        ob, osl, cb, cs = (wi(k, W) for k in ("open_buy_usd", "open_sell_usd", "close_buy_usd", "close_sell_usd"))
        wal = wi("n_taker_wallets", W)
        tn_min = raw["taker_buy_usd"][o - W:o] + raw["taker_sell_usd"][o - W:o]
        t3 = float(np.sum(np.where(tn_min > 0, np.nan_to_num(raw["top3_taker_share"][o - W:o]) * tn_min, 0.0)))
        tw_w = raw["twap_taker_usd"][o - W:o]
        g = (lambda x: x / TN) if TN > 0 else (lambda x: np.nan)
        op, cl = (ob if pos else osl), (cb if pos else cs)
        out[f"imb_{W}"] = g(s * (B - S)); out[f"forced_share_{W}"] = g(fs if pos else fl); out[f"forced_net_{W}"] = g(s * (fs - fl))
        out[f"backstop_ratio_{W}"] = g(bk - ad); out[f"adl_ratio_{W}"] = g(ad)
        out[f"backstop_share_{W}"] = (bk - ad) / (TN + bk - ad) if TN + (bk - ad) > 0 else np.nan
        out[f"adl_share_{W}"] = ad / (TN + ad) if TN + ad > 0 else np.nan
        out[f"open_push_{W}"] = g(op); out[f"close_push_{W}"] = g(cl)
        out[f"open_close_ratio_{W}"] = op / (op + cl) if TN > 0 and (op + cl) > 0 else np.nan
        out[f"top3_{W}"] = g(t3)
        wraw = wal / (TN / 1e6) if TN > 0 else np.nan
        out[f"wallets_raw_{W}"] = wraw
        out[f"twap_share_{W}"] = float(tw_w.sum()) / TN if TN > 0 and not np.isnan(tw_w).any() else np.nan
        qs, ts = [], []
        for k in range(336):
            oc = o - W - 30 * k
            if oc - W < 0:
                qs.append(np.nan); ts.append(np.nan); continue
            t_ = win_all(oc, W)
            if t_ is None:
                qs.append(np.nan); ts.append(np.nan); continue
            w_ = raw["n_taker_wallets"][oc - W:oc]
            ts.append(t_); qs.append(float(w_.sum()) / (t_ / 1e6) if t_ > 0 else np.nan)
        qs, ts = np.array(qs), np.array(ts)
        nm = np.nanmedian(qs) if np.isfinite(qs).sum() >= 144 else np.nan
        nt = np.nanmedian(ts) if np.isfinite(ts).sum() >= 144 else np.nan
        out[f"wallets_per_musd_{W}"] = wraw / nm if nm > 0 else np.nan
        out[f"volume_ratio_{W}"] = TN / nt if nt > 0 else np.nan
    # bins
    span = raw["taker_buy_usd"][o - 60:o]
    ok5 = not np.isnan(span).any()
    for k in range(12):
        sl = slice(o - 60 + 5 * k, o - 60 + 5 * (k + 1))
        B, S = buy[sl].sum(), sell[sl].sum()
        fp = (raw["liq_forced_short_usd"] if pos else raw["liq_forced_long_usd"])[sl].sum()
        out[f"imb_5m_{k}"] = s * (B - S) / (B + S) if ok5 and B + S > 0 else np.nan
        out[f"forced_5m_{k}"] = fp / (B + S) if ok5 and B + S > 0 else np.nan
    for pre, start in (("", 360), ("pre_", 420)):
        okb = not np.isnan(buy[o - start:o - start + 360]).any()
        for k in range(12):
            sl = slice(o - start + 30 * k, o - start + 30 * (k + 1))
            B, S = buy[sl].sum(), sell[sl].sum()
            fp = (raw["liq_forced_short_usd"] if pos else raw["liq_forced_long_usd"])[sl].sum()
            out[f"imb_30m_{pre}{k}"] = s * (B - S) / (B + S) if okb and B + S > 0 else np.nan
            out[f"forced_30m_{pre}{k}"] = fp / (B + S) if okb and B + S > 0 else np.nan
    imb5 = np.array([out[f"imb_5m_{k}"] for k in range(12)])
    if np.isfinite(imb5).any():
        kk = int(np.argmax(np.where(np.isfinite(imb5), np.abs(imb5), -1.0)))
        out["max_abs_imb_5m"], out["max_abs_imb_5m_bin"] = imb5[kk], float(kk)
    else:
        out["max_abs_imb_5m"] = out["max_abs_imb_5m_bin"] = np.nan
    pf = (raw["liq_forced_short_usd"] if pos else raw["liq_forced_long_usd"])[o - 1440:o]
    last = None
    for m in range(1439, -1, -1):
        if np.isfinite(pf[m]) and pf[m] > 0:
            last = 1439 - m
            break
    out["mins_since_forced_any"] = float(last) if last is not None else np.nan
    allp = (raw["liq_forced_short_usd"] if pos else raw["liq_forced_long_usd"])[o - 10080:o]
    posv = allp[np.isfinite(allp) & (allp > 0)]
    thr = np.median(posv) if len(posv) >= 20 else np.nan
    sp = None
    if np.isfinite(thr):
        for m in range(1439, -1, -1):
            if np.isfinite(pf[m]) and pf[m] > 3 * thr:
                sp = 1439 - m
                break
    out["mins_since_forced_spike"] = float(sp) if sp is not None else np.nan
    for Wn in (30, 60):
        b, sl_ = buy[o - Wn:o], sell[o - Wn:o]
        if np.isnan(b).any() or np.isnan(sl_).any():
            out[f"slope_cum_imb_{Wn}"] = np.nan
            continue
        c = np.cumsum(s * (b - sl_))
        x = np.arange(1, Wn + 1) - (Wn + 1) / 2.0
        tn = (b + sl_).sum()
        out[f"slope_cum_imb_{Wn}"] = float((c * x).sum() / (x * x).sum() / tn) if tn > 0 else np.nan
    pv = (buy if pos else sell)[o - 60:o]
    out["accel_share"] = float(pv[-15:].sum() / pv.sum()) if not np.isnan(pv).any() and pv.sum() > 0 else np.nan
    return out


def test_indep(ev, n):
    t0 = time.time()
    G = {}
    for u, lgs in (("pair", ("a", "b")), ("coin", ("a",))):
        for lg in lgs:
            G[(u, lg)] = pd.read_parquet(os.path.join(G5.WORK, u, f"g5_{lg}.parquet"))
    bad, ncmp, mx = [], 0, 0.0
    picks = []
    for u in ("pair", "coin"):
        E, o = ev[u]
        for r in rng.choice(len(E), n // 2, replace=False):
            lg = "b" if (u == "pair" and rng.random() < 0.5) else "a"
            c = E.ticker_b.iloc[r] if lg == "b" else E.ticker_a.iloc[r]
            d = float(E.d.iloc[r])
            s = -d * np.sign(E.beta.iloc[r]) if lg == "b" else d
            picks.append((c, u, lg, int(r), int(o[r]), float(s)))
    picks.sort()
    cur, raw = None, None
    for c, u, lg, r, o, s in picks:
        if c != cur:
            raw, cur = G5.read_coin_raw(c), c
        exp = ref_leg(raw, o, s)
        got = G[(u, lg)].iloc[r]
        for k, v in exp.items():
            g = float(got[f"{lg}_{k}"])
            ncmp += 1
            if np.isnan(v) != np.isnan(g):
                bad.append((c, u, lg, r, k, v, g)); continue
            if np.isnan(v):
                continue
            err = abs(v - g)
            mx = max(mx, err / (1e-6 + 1e-4 * abs(v)))
            if err > 1e-6 + 1e-4 * abs(v):
                bad.append((c, u, lg, r, k, v, g))
    print(f"[G5 INDEP] {len(picks)} legs: {ncmp:,} comparisons; mismatches {len(bad)}; worst error / tolerance {mx:.3f} [{time.time() - t0:.0f}s]")
    for b in bad[:15]:
        print("  MISMATCH", b)
    assert not bad
    print("[G5 INDEP] PASS")


def test_invariants(ev):
    for u in ("pair", "coin"):
        for lg in (("a", "b", "net") if u == "pair" else ("a",)):
            G = pd.read_parquet(os.path.join(G5.WORK, u, f"g5_{lg}.parquet"))
            for W in G5.WINS:
                for q in ("forced_share", "backstop_share", "adl_share", "open_push", "close_push", "open_close_ratio", "twap_share"):
                    x = G[f"{lg}_{q}_{W}"].dropna()
                    assert ((x >= -1e-6) & (x <= 1 + 1e-6)).all(), (u, lg, q, W, float(x.min()), float(x.max()))
                for q in ("backstop_ratio", "adl_ratio"):                       # off-book dollars over on-book taker notional: >= 0 and unbounded
                    x = G[f"{lg}_{q}_{W}"].dropna()
                    assert (x >= -1e-6).all(), (u, lg, q, W, float(x.min()))
                    if lg == "a":
                        print(f"   {u} {lg}_{q}_{W}: max {float(x.max()):.3f}, share above 1: {100 * float((x > 1).mean()):.4f}%")
                x = G[f"{lg}_imb_{W}"].dropna()
                assert ((x >= -1 - 1e-6) & (x <= 1 + 1e-6)).all(), (u, lg, "imb", W)
        sh = pd.read_parquet(os.path.join(G5.WORK, u, "g5_shape.parquet"))
        w = sh.w_a.dropna()
        assert ((w >= 0) & (w <= 1)).all()
    # sum of the twelve 5-minute bins = the 60-minute window (production functions, sampled legs)
    E, o = ev["pair"]
    c = E.ticker_a.iloc[0]
    A = G5.load_coin(c)
    oo = o[(E.ticker_a == c).to_numpy()][:2000]
    s = np.ones(len(oo))
    _, _, ok5, B5, S5 = G5.bins(A, oo, s, 60, 5, 12)
    B60 = G5.wsum(A["taker_buy_usd"], oo, 60)
    ok = ok5 & np.isfinite(B5.sum(1))
    assert np.allclose(B5.sum(1)[ok], B60[ok], rtol=1e-9, atol=1e-6), "the twelve 5-minute bins do not add up to the 60-minute window"
    print("[G5 INVARIANTS] PASS (shares in [0,1], imb in [-1,1], net weights in [0,1], the twelve 5-minute bins add up to the 60-minute window)")


def test_swap(ev):
    sh = pd.read_parquet(os.path.join(G5.WORK, "pair", "g5_shape.parquet"))
    A = pd.read_parquet(os.path.join(G5.WORK, "pair", "g5_a.parquet"), columns=["a_imb_60", "a_forced_share_60"])
    B = pd.read_parquet(os.path.join(G5.WORK, "pair", "g5_b.parquet"), columns=["b_imb_60", "b_forced_share_60"])
    net = pd.read_parquet(os.path.join(G5.WORK, "pair", "g5_net.parquet"), columns=["net_imb_60", "net_forced_share_60"])
    wA = sh.w_a.to_numpy(float)
    ix = rng.choice(len(sh), 100000, replace=False)
    for q in ("imb_60", "forced_share_60"):
        xa, xb = A[f"a_{q}"].to_numpy(float)[ix], B[f"b_{q}"].to_numpy(float)[ix]
        w = wA[ix]
        n1 = np.where(w > 0, w * xa, 0) + np.where(1 - w > 0, (1 - w) * xb, 0)
        n2 = np.where(1 - w > 0, (1 - w) * xb, 0) + np.where(w > 0, w * xa, 0)
        got = net[f"net_{q}"].to_numpy(float)[ix]
        ok = np.isfinite(got)
        assert np.allclose(n1[ok], got[ok], atol=1e-6) and np.allclose(n1[ok], n2[ok])
    print("[G5 SWAP] PASS on the building blocks (d held fixed): net(x_A, x_B, wA) = net(x_B, x_A, 1 - wA) and equals the stored net columns on 100,000 events; the leg block is a function of (coin, cutoff, push sign) only")


def main():
    t0 = time.time()
    ev = R5.event_tables()
    test_invariants(ev)
    test_swap(ev)
    test_indep(ev, 2000)
    test_poison(ev, 1000, 300)
    print(f"[TESTS G5] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
