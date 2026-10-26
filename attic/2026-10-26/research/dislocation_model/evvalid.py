"""HL-EVENT1 validator for eventflow.py's window series: 500 events + 500 control links, independent.

    python -u research/dislocation_model/evvalid.py

Each sampled row's 12 series x 5 windows are recomputed from the per-minute flow files and the 30-minute
panel with direct slices and sums (no cumulative sums, no rolling objects, the benchmark recomputed from
the panel, not read from the cache), on arrays TRUNCATED AT THE ROW'S CUTOFF C = T + 30 min, so a read at or
after C would raise. Compared with ev_series.npz (float32 storage: rtol 1e-4, atol 1e-5); the NaN pattern
must match exactly. Any mismatch aborts.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import coinevents as ce
import eventflow as ef
import evmarket as em
import flowfeat as ff

SEED, NROWS = 20261016, 500


def window_values(a, M, o, d, beta, V_c, ir, bar, b_, a_):
    """The 12 series for one row and one window, from arrays truncated at o (all minutes < C)."""
    s, e = o - b_, o - a_
    nan = np.full(len(ef.SER), np.nan)
    if s < 0:
        return nan
    seg = lambda k: a[k][s:e]
    assert len(seg("taker_buy_usd")) == (b_ - a_) and len(a["taker_buy_usd"]) == o
    out = {}
    if not np.isnan(seg("taker_buy_usd")).any():
        buy, sell = seg("taker_buy_usd").sum(), seg("taker_sell_usd").sum()
        tn = buy + sell
        # a complete window with no trades has volume 0 (a real value); ratios need tn > 0
        if True:
            pk = lambda kp, kn: (seg(kp) if d > 0 else seg(kn)).sum()
            out["imb"] = d * (buy - sell) / tn if tn > 0 else np.nan
            out["forced"] = pk("liq_forced_short_usd", "liq_forced_long_usd") / tn if tn > 0 else np.nan
            op = pk("open_buy_usd", "open_sell_usd") / tn if tn > 0 else np.nan
            cp = pk("close_buy_usd", "close_sell_usd") / tn if tn > 0 else np.nan
            out["open"], out["close"] = op, cp
            out["ratio"] = op / (op + cp) if tn > 0 and (op + cp) > 0 else np.nan
            tnm = seg("taker_buy_usd") + seg("taker_sell_usd")
            out["top3"] = np.where(tnm > 0, np.nan_to_num(seg("top3_taker_share")) * tnm, 0.0).sum() / tn if tn > 0 else np.nan
            wraw = seg("n_taker_wallets").sum() / (tn / 1e6) if tn > 0 else np.nan
            W = b_ - a_
            vw, vt = [], []
            for k in range(ff.TRAIL):
                ce_ = o - b_ - 30 * k
                if ce_ - W < 0:
                    continue
                x = a["taker_buy_usd"][ce_ - W:ce_]
                if len(x) != W or np.isnan(x).any():
                    continue
                t_ = x.sum() + a["taker_sell_usd"][ce_ - W:ce_].sum()
                vt.append(t_)
                if t_ > 0:
                    vw.append(a["n_taker_wallets"][ce_ - W:ce_].sum() / (t_ / 1e6))
            mw = np.median(vw) if len(vw) >= ff.MINVALID else np.nan
            mt = np.median(vt) if len(vt) >= ff.MINVALID else np.nan
            out["wallets"] = wraw / mw if mw > 0 else np.nan
            out["volume"] = tn / mt if mt > 0 else np.nan
            tw = seg("twap_taker_usd")
            out["twap"] = np.nan if (np.isnan(tw).any() or tn <= 0) else tw.sum() / tn
    bi, ai = bar - b_ // 30, bar - a_ // 30
    if bi >= 0:
        sir = ir[bi + 1:ai + 1].sum()                       # the benchmark return over the bars in the window
        out["mk_idx"] = d * sir
        out["resid"] = d * ((V_c[ai] - V_c[bi]) - beta * sir)
    W = b_ - a_
    Mw = M[s:e]
    cur = np.nan if np.isnan(Mw).any() else Mw.sum()
    vals = []
    for k in range(ff.TRAIL):
        ce_ = o - b_ - 30 * k
        if ce_ - W < 0:
            continue
        t_ = M[ce_ - W:ce_]
        if len(t_) == W and not np.isnan(t_).any():
            vals.append(t_.sum())
    med = np.median(vals) if len(vals) >= ff.MINVALID else np.nan
    out["mk_liq"] = cur / med if (med > 0 and np.isfinite(cur)) else np.nan
    return np.array([out.get(k, np.nan) for k in ef.SER])


def run():
    t0 = time.time()
    EV, PR = pd.read_parquet(ce.EVENTS), pd.read_parquet(ce.PAIRS)
    Z = np.load(ef.OUT_SERIES)
    panel, idx, V, cols = ce.load_panel()
    S, n30, R = ce.index_returns(V)
    cidx = {c: j for j, c in enumerate(cols)}
    rng = np.random.default_rng(SEED)
    ev_rows = np.sort(rng.choice(len(EV), NROWS, replace=False))
    pr_rows = np.sort(rng.choice(len(PR), NROWS, replace=False))
    coins = sorted(set(EV.coin.iloc[ev_rows]) | set(PR.coin.iloc[pr_rows]))
    allcoins = sorted(f[:-8] for f in os.listdir(ff.FLOW_DIR) if f.endswith(".parquet"))
    flow, mkt = {}, np.zeros(ff.N)
    for c in allcoins:
        fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date"] + ef.COLS)
        cols_ = {k: ff.dense(fl, k) for k in ef.COLS}
        mkt += np.nan_to_num(cols_["liq_forced_long_usd"]) + np.nan_to_num(cols_["liq_forced_short_usd"])
        if c in coins:
            flow[c] = cols_
    z = np.load(em.OUT)
    mkt = np.where(z["hole"], np.nan, mkt)
    print(f"[EVVALID] loaded flows for {len(flow)} sampled coins and the market sum  [{time.time() - t0:.0f}s]", flush=True)
    bad, maxerr, ncmp = [], 0.0, 0
    irc = {c: ce.coin_index_ret(S, n30, R, cidx[c]) for c in coins}
    for kind, tbl, rows, arr in (("event", EV, ev_rows, Z["ev"]), ("link", PR, pr_rows, Z["pr"])):
        for r in rows:
            row = tbl.iloc[r]
            c = row["coin"]
            o = int(ff.minute_index(pd.Series([pd.Timestamp(row["T"]) + pd.Timedelta(minutes=30)]))[0])
            a = {k: v[:o] for k, v in flow[c].items()}              # NOTHING at or after C survives
            Mtr = mkt[:o]
            j = cidx[c]
            exp = np.full((len(ef.SER), len(ef.WN)), np.nan)
            for wi, w in enumerate(ef.WN):
                b_, a_ = ef.WINS[w]
                exp[:, wi] = window_values(a, Mtr, o, row["d"], row["beta"], V[:, j], irc[c], int(row["bar"]), b_, a_)
            got = arr[r if kind == "link" else int(row["event_id"])].astype(float)
            for si in range(len(ef.SER)):
                for wi in range(len(ef.WN)):
                    v, g = exp[si, wi], got[si, wi]
                    ncmp += 1
                    if np.isnan(v) != np.isnan(g):
                        bad.append((kind, int(r), ef.SER[si], ef.WN[wi], v, g)); continue
                    if np.isnan(v):
                        continue
                    err = abs(v - g); maxerr = max(maxerr, err)
                    if err > 1e-5 + 1e-4 * abs(v):
                        bad.append((kind, int(r), ef.SER[si], ef.WN[wi], v, g))
    print(f"[EVVALID] {NROWS} events + {NROWS} links x {len(ef.SER)} series x {len(ef.WN)} windows = {ncmp:,} comparisons; "
          f"mismatches {len(bad)}; max abs diff {maxerr:.2e}  [{time.time() - t0:.0f}s]")
    print("[EVVALID] every flow and market array was truncated at the row's cutoff C before any read")
    for b in bad[:20]:
        print("  MISMATCH", b)
    if bad:
        raise SystemExit("[EVVALID] FAILED")
    print("[EVVALID] PASS")


if __name__ == "__main__":
    run()
