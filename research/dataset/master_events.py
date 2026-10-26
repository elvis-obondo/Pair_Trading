"""HL-MASTER1 stage A: every pair trigger (the FULL population, no cap) with its entry geometry. No labels, no features beyond the entry inputs.

    python -u research/dataset/master_events.py > research/dataset/logs/master_events.log

THE RULE IS mkdisloc.py's, unchanged (adaptive trigger on the symmetric 96-bar geometry; fresh crossing of the pair's own previous-96-bar 99th
percentile of |z|; NaN-free segments, option i; first possible trigger i >= 335; at least 20 bars after the trigger inside the segment). Removed:
PER_PAIR (20 per pair) and TARGET (60,000): every trigger of every tradeable pair is written. The 336-bar windows are NOT stored.

PER EVENT (all known at t = 0 = entry_time + 30 min, the close of the trigger bar):
  event_id            row number after sorting by (pair order, bar)
  ticker_a, ticker_b  the pair in tradeable_pairs order (a is the numerator leg: spread = log A - beta log B - alpha)
  entry_time          the 30m bar LABEL T (bar open); the close is observed at T + 30 min
  bar_index           index of the bar in the 30m panel (24,305 bars)
  z, threshold        z at entry and the adaptive threshold it crossed
  beta, alpha, mu, sigma, r2     the frozen entry geometry (96-bar symmetric fit); r2 of that fit
  beta_stab           std/|mean| of the rolling beta over the 336 bars to the trigger (NaN if the segment is too young)
  vol_48              mean |30m change| of the entry-frozen standardised spread over the last 48 bars (envfeat's definition)
  mins_since_trade_a/b   of each leg at the trigger bar (1m bars)
  seg_start_bar, seg_end_bar (exclusive), bars_into_segment   the NaN-free segment the trigger lives in and the trigger's index inside it
  pair_index          the pair's position in universe_panel.tradeable_pairs (the key that ties events to the pair list)
  pair_triggers_true  triggers of the pair over its whole life (a count; NOT an as-of column: it uses the future, never a feature)
  y00..y20            the 30m standardised spread at the trigger bar and the next 20 bars (frozen geometry)  [label inputs, use the future]
OUTPUT: research/datasets/master/work/pair/events.parquet (+ events_y.npz). The 60,004 rows of disloc_meta.parquet must all appear (pair + entry
time), with the same z, beta, alpha, mu, sigma (asserted, max abs difference reported).
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

FIT_BARS, HORIZONS, THR_BARS, THR_PCT = 336, 20, 96, 99.0
OUTDIR = os.path.join(paths.DATASETS, "master", "work", "pair" + ("_smoke" if os.environ.get("SMOKE_PAIRS") else ""))

panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
idx = pd.to_datetime(panel.index)
V = panel.to_numpy(float)
cols = list(panel.columns)
n = len(panel)
ok = np.isfinite(V)
first = np.array([ok[:, j].argmax() for j in range(V.shape[1])])
last = np.array([n - 1 - ok[::-1, j].argmax() for j in range(V.shape[1])])
EW = rs.entry_window_bars(0.5)
MINB = rs.min_bars_required(0.5)
assert EW == THR_BARS
SEG_MIN = max(FIT_BARS - 1, MINB - 1 + THR_BARS) + HORIZONS + 1
pairs = universe_panel.tradeable_pairs(cols)
ix = {c: j for j, c in enumerate(cols)}
MST = {}


def load_mst():
    for c in cols:
        m = pd.read_feather(bar_file(c, "30m"), columns=["date", "mins_since_trade"])
        s = pd.Series(m.mins_since_trade.to_numpy(float), index=pd.to_datetime(m.date, utc=True).dt.tz_localize(None))
        MST[c] = s.reindex(idx).to_numpy()


def segments(fin):
    e = np.diff(np.r_[0, fin.astype(np.int8), 0])
    return list(zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)))


def adaptive_threshold(absz):
    thr = np.full(len(absz), np.nan)
    if len(absz) > THR_BARS:
        w = np.lib.stride_tricks.sliding_window_view(absz, THR_BARS)[: len(absz) - THR_BARS]
        good = np.isfinite(w).all(axis=1)
        q = np.full(len(w), np.nan)
        if good.any():
            q[good] = np.percentile(w[good], THR_PCT, axis=1)
        thr[THR_BARS:] = q
    return thr


def pair_events(k):
    a, b = pairs[k]
    ja, jb = ix[a], ix[b]
    f, l = max(first[ja], first[jb]), min(last[ja], last[jb])
    if l - f + 1 < SEG_MIN:
        return k, None, 0
    fin = ok[f:l + 1, ja] & ok[f:l + 1, jb]
    rows, nan_windows = [], 0
    for s0, s1 in segments(fin):
        if s1 - s0 < SEG_MIN:
            continue
        g0 = f + s0
        va, vb = V[g0:f + s1, ja], V[g0:f + s1, jb]
        r = rs.rolling_spread_stats(va, vb, 0.5)
        z = r.z
        absz = np.abs(z)
        fz = np.isfinite(z) & np.isfinite(r.sigma) & (r.sigma > 0)
        thr = adaptive_threshold(np.where(fz, absz, np.nan))
        hit = np.zeros(len(z), bool)
        hit[1:] = (fz[1:] & fz[:-1] & np.isfinite(thr[1:]) & np.isfinite(thr[:-1]) & (absz[1:] > thr[1:]) & (absz[:-1] <= thr[:-1]))
        c = np.flatnonzero(hit)
        c = c[(c >= FIT_BARS - 1) & (c + HORIZONS <= len(z) - 1)]
        for i in c:
            be, al, mu, sg = r.beta[i], r.alpha[i], r.mu[i], r.sigma[i]
            lo = i - FIT_BARS + 1
            w = (va[lo:i + 1] - be * vb[lo:i + 1] - al - mu) / sg
            y = (va[i:i + HORIZONS + 1] - be * vb[i:i + HORIZONS + 1] - al - mu) / sg
            if not (np.isfinite(w).all() and np.isfinite(y).all()):
                nan_windows += 1
                continue
            bw = r.beta[lo:i + 1]
            bstab = float(np.std(bw) / abs(np.mean(bw))) if np.isfinite(bw).all() and np.mean(bw) != 0 else np.nan
            gi = g0 + i
            vol48 = float(np.abs(np.diff(w[-49:])).mean())
            rows.append((k, gi, float(z[i]), float(thr[i]), float(be), float(al), float(mu), float(sg), float(r.r2[i]), bstab, vol48,
                         float(MST[a][gi]), float(MST[b][gi]), g0, int(i), y.astype(np.float32), f + s1))
    return k, rows, nan_windows


def main():
    t0 = time.time()
    load_mst()
    NP = int(os.environ.get("SMOKE_PAIRS", len(pairs)))      # SMOKE_PAIRS limits to the first N pairs: a labelled smoke test, never a result
    if NP < len(pairs):
        print(f"[SMOKE TEST] first {NP} of {len(pairs)} pairs only; outputs are not the dataset", flush=True)
    print(f"[INFO] panel {n} bars x {len(cols)} tickers {idx[0]} -> {idx[-1]}; {len(pairs)} pairs; shortest usable segment {SEG_MIN} bars", flush=True)
    chunks = []
    nan_w = 0
    with Pool(int(os.environ.get("NPROC", 8))) as pool:
        for q, (k, rows, nw) in enumerate(pool.imap(pair_events, range(NP), chunksize=8)):
            nan_w += nw
            if rows:
                chunks.append(rows)
            if (q + 1) % 2000 == 0:
                print(f"  {q + 1} pairs, {sum(len(c) for c in chunks):,} triggers  [{time.time() - t0:.0f}s]", flush=True)
    assert nan_w == 0, f"{nan_w} candidate windows non-finite inside finite segments"
    flat = [r for c in chunks for r in c]
    kk = np.array([r[0] for r in flat])
    E = pd.DataFrame({
        "ticker_a": np.array([pairs[k][0] for k in kk]), "ticker_b": np.array([pairs[k][1] for k in kk]),
        "bar_index": np.array([r[1] for r in flat], np.int32), "z": [r[2] for r in flat], "threshold": [r[3] for r in flat],
        "beta": [r[4] for r in flat], "alpha": [r[5] for r in flat], "mu": [r[6] for r in flat], "sigma": [r[7] for r in flat],
        "r2": [r[8] for r in flat], "beta_stab": [r[9] for r in flat], "vol_48": [r[10] for r in flat],
        "mins_since_trade_a": [r[11] for r in flat], "mins_since_trade_b": [r[12] for r in flat],
        "seg_start_bar": np.array([r[13] for r in flat], np.int32), "seg_end_bar": np.array([r[16] for r in flat], np.int32),
        "bars_into_segment": np.array([r[14] for r in flat], np.int32),
        "pair_index": kk.astype(np.int32)})
    Y = np.asarray([r[15] for r in flat], np.float32)
    E["entry_time"] = idx[E.bar_index.to_numpy()]
    E["pair_triggers_true"] = E.groupby("pair_index").pair_index.transform("size").astype(np.int32)
    E["event_id"] = np.arange(len(E), dtype=np.int64)
    E["d"] = np.where(E.z >= 0, 1, -1).astype(np.int8)
    os.makedirs(OUTDIR, exist_ok=True)
    E.to_parquet(os.path.join(OUTDIR, "events.parquet"), index=False)
    np.savez_compressed(os.path.join(OUTDIR, "events_y.npz"), y=Y)
    print(f"[DONE] {len(E):,} triggers over {E.pair_index.nunique():,} pairs; {E.entry_time.min()} -> {E.entry_time.max()}  [{time.time() - t0:.0f}s]")
    print(f"  per pair: median {E.groupby('pair_index').size().median():.0f}, max {E.groupby('pair_index').size().max()}; long {100 * (E.z > 0).mean():.1f}%")
    # invariants of mkdisloc
    e1 = np.abs(Y[:, 0] - E.z.to_numpy(np.float32)).max()
    print(f"[INVARIANT] max |y00 - z| {e1:.3e} (must be < 1e-4)")
    assert e1 < 1e-4 and (E.z.abs() > E.threshold).all()
    # the 60,004 old rows must reappear
    M = pd.read_parquet(paths.META)
    M["pair"] = M.ticker_a + "/" + M.ticker_b
    E["pair"] = E.ticker_a + "/" + E.ticker_b
    assert not E.duplicated(["pair", "entry_time"]).any(), "(pair, entry_time) is not unique in the full set"
    assert not M.duplicated(["pair", "entry_time"]).any(), "(pair, entry_time) is not unique in the old set"
    Wold = np.load(paths.DISLOC)["windows"]
    M["vol_48_old"] = np.abs(np.diff(Wold[:, -49:].astype(np.float64), axis=1)).mean(1)
    if NP < len(pairs):
        print("[SMOKE TEST] reproduction check skipped")
        return
    m = M.merge(E, left_on=["pair", "entry_time"], right_on=["pair", "entry_time"], suffixes=("_old", ""), how="left", indicator=True)
    miss = int((m._merge != "both").sum())
    print(f"[REPRODUCE] old rows {len(M):,}; found in the full set {len(M) - miss:,}; missing {miss}")
    assert miss == 0, "old rows missing from the full population"
    for c_old, c_new in (("z_at_entry", "z"), ("beta_old", "beta"), ("alpha_old", "alpha"), ("mu_old", "mu"), ("sigma_old", "sigma"),
                         ("r2_old", "r2"), ("threshold_at_entry", "threshold")):
        d = np.abs(m[c_old].to_numpy(float) - m[c_new].to_numpy(float)).max()
        print(f"  max |{c_old} - {c_new}| {d:.3e}")
        assert d < 1e-9
    for c_old, c_new in (("beta_stab_old", "beta_stab"), ("mins_since_trade_a_old", "mins_since_trade_a"),
                         ("mins_since_trade_b_old", "mins_since_trade_b"), ("vol_48_old", "vol_48")):
        x, y_ = m[c_old].to_numpy(float), m[c_new].to_numpy(float)
        assert (np.isnan(x) == np.isnan(y_)).all(), f"NaN pattern differs: {c_old}"
        d = np.nanmax(np.abs(x - y_)) if np.isfinite(x).any() else 0.0
        print(f"  max |{c_old} - {c_new}| {d:.3e}  (NaN-equal)")
        assert d < 1e-6, c_old
    print(f"[SHARE] the 60,004 old rows are {100 * len(M) / len(E):.2f}% of the full set")
    mo = E.entry_time.dt.to_period("M").value_counts().sort_index()
    print("[MONTH] triggers per month:\n" + mo.to_string())


if __name__ == "__main__":
    main()
