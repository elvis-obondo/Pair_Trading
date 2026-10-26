"""HL-MASTER1 G2b: symmetric z (orientation-proof) at t = 0, on every event of the CURRENT event set (version 1). Adds columns only: no new event table, no labels.

    python -u research/dataset/master_g2b.py [pair|coin] > research/dataset/logs/master_g2b_<unit>.log

WHY. The adaptive trigger's z uses the rolling series of per-bar-beta spreads, so it changes when the legs are swapped (found by the G2 swap test). These columns apply bar i's
OWN beta_i and alpha_i to the WHOLE 96-bar window (the frozen-geometry normalisation the outcomes already use), which is exactly leg-symmetric.
For each bar k of a NaN-free segment (window = the 96 bars k-95..k, beta_k, alpha_k from rolling_spread.rolling_beta_alpha, the vol-matched symmetric estimator):
  sigma_sym_k = sqrt( var_a + beta_k^2 var_b - 2 beta_k cov_ab )   [sample (ddof 1) moments of the window = the std of (a_j - beta_k b_j) over the window]
  z_sym_k     = (a_k - beta_k b_k - alpha_k) / sigma_sym_k           [alpha_k = mean(a) - beta_k mean(b), so the window mean of a_j - beta_k b_j - alpha_k is 0]
  threshold_sym_k = 99th percentile (numpy linear) of |z_sym| over bars k-96..k-1 (excludes bar k)
  trig_sym_k  = 1 if |z_sym_k| > threshold_sym_k and |z_sym_{k-1}| <= threshold_sym_{k-1} (a fresh crossing, the same rule as the adaptive trigger, on z_sym), 0 if finite and not,
                NaN if either threshold or either z is not finite
  z_ratio     = |z_sym| / |z|   (z = the event's own entry z)
Columns per event: sigma_sym, z_sym, z_ratio, threshold_sym, trig_sym.
SWAP REQUIREMENT (asserted in master_tests_g2b.py): with the legs swapped, z_sym' = -sign(beta) z_sym, sigma_sym' = sigma_sym / |beta|, trig_sym' = trig_sym on every event.
COIN UNIT: leg B is the benchmark level L (segment-wise from 0), same construction.
OUTPUT: research/datasets/master/work/{pair,coin}/g2b.parquet. Reported: share of events with trig_sym = 1, corr(z, z_sym), the z_ratio distribution.
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
import universe_panel
import rolling_spread as rs

W, THR_BARS, THR_PCT = 96, 96, 99.0
WORK = os.path.join(paths.DATASETS, "master", "work")
NAMES = ["sigma_sym", "z_sym", "z_ratio", "threshold_sym", "trig_sym"]


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


def sym_series(a, b):
    """(sigma_sym, z_sym, threshold_sym, trig_sym) per bar of one NaN-free segment (log prices a, b)."""
    beta, alpha = rs.rolling_beta_alpha(a, b, W)
    sa, sb = pd.Series(a), pd.Series(b)
    va, vb, cov = sa.rolling(W).var().to_numpy(), sb.rolling(W).var().to_numpy(), sa.rolling(W).cov(sb).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        var = va + beta ** 2 * vb - 2 * beta * cov
        sig = np.sqrt(np.where(var > 0, var, np.nan))
        z = (a - beta * b - alpha) / sig
    fz = np.isfinite(z)
    thr = adaptive_threshold(np.where(fz, np.abs(z), np.nan))
    trig = np.full(len(z), np.nan)
    ok = np.zeros(len(z), bool)
    ok[1:] = fz[1:] & fz[:-1] & np.isfinite(thr[1:]) & np.isfinite(thr[:-1])
    cond = np.zeros(len(z))
    cond[1:] = (np.abs(z[1:]) > thr[1:]) & (np.abs(z[:-1]) <= thr[:-1])
    trig[ok] = cond[ok]
    return sig, z, thr, trig


V = None
E = None
LEVEL = {}
J = {}


def job(key):
    g0, g1, ja, jb_or_coin, rows = key
    a = V[g0:g1, ja]
    b = V[g0:g1, jb_or_coin] if UNIT == "pair" else LEVEL[ja][g0:g1]
    sig, z, thr, trig = sym_series(a, b)
    return rows, sig, z, thr, trig


UNIT = "pair"


def main():
    global V, E, UNIT
    t0 = time.time()
    UNIT = sys.argv[1] if len(sys.argv) > 1 else "pair"
    E = pd.read_parquet(os.path.join(WORK, UNIT, "events.parquet"))
    if UNIT == "pair":
        panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
        cols = list(panel.columns)
        V = panel.to_numpy(float)
        ix = {c: j for j, c in enumerate(cols)}
        ja_all = E.ticker_a.map(ix).to_numpy()
        jb_all = E.ticker_b.map(ix).to_numpy()
    else:
        import coinevents as ce
        panel, idx, V, cols = ce.load_panel()
        ix = {c: j for j, c in enumerate(cols)}
        ja_all = E.ticker_a.map(ix).to_numpy()
        jb_all = np.zeros(len(E), int)
        for c in E.ticker_a.unique():
            LEVEL[ix[c]] = np.load(os.path.join(ce.STATS_DIR, f"{c}.npz"))["L"]
    keys = []
    df = pd.DataFrame({"ja": ja_all, "jb": jb_all, "g0": E.seg_start_bar.to_numpy(), "g1": E.seg_end_bar.to_numpy()})
    for (ja, jb, g0, g1), g in df.groupby(["ja", "jb", "g0", "g1"]):
        keys.append((int(g0), int(g1), int(ja), int(jb), g.index.to_numpy()))
    print(f"[G2b {UNIT}] {len(E):,} events in {len(keys):,} segments  [{time.time() - t0:.0f}s]", flush=True)
    out = {k: np.full(len(E), np.nan) for k in NAMES[:2] + ["threshold_sym", "trig_sym"]}
    ii = E.bars_into_segment.to_numpy()
    with Pool(int(os.environ.get("NPROC", 8))) as pool:
        for q, (rows, sig, z, thr, trig) in enumerate(pool.imap(job, keys, chunksize=16)):
            p = ii[rows]
            out["sigma_sym"][rows], out["z_sym"][rows] = sig[p], z[p]
            out["threshold_sym"][rows], out["trig_sym"][rows] = thr[p], trig[p]
            if (q + 1) % 5000 == 0:
                print(f"  {q + 1} segments  [{time.time() - t0:.0f}s]", flush=True)
    G = pd.DataFrame({"event_id": E.event_id.to_numpy(), "sigma_sym": out["sigma_sym"], "z_sym": out["z_sym"],
                      "z_ratio": np.abs(out["z_sym"]) / np.abs(E.z.to_numpy(float)), "threshold_sym": out["threshold_sym"], "trig_sym": out["trig_sym"]})
    G.to_parquet(os.path.join(WORK, UNIT, "g2b.parquet"), index=False)
    z, zs = E.z.to_numpy(float), G.z_sym.to_numpy()
    ok = np.isfinite(zs)
    print(f"[DONE {UNIT}] {len(G):,} events  [{time.time() - t0:.0f}s]")
    print(f"  NaN: " + ", ".join(f"{c} {100 * G[c].isna().mean():.3f}%" for c in NAMES))
    print(f"  share of current events with trig_sym = 1: {100 * np.nanmean(G.trig_sym.to_numpy()):.2f}% (trig_sym defined for {100 * np.isfinite(G.trig_sym.to_numpy()).mean():.2f}%)")
    print(f"  corr(z, z_sym) {np.corrcoef(z[ok], zs[ok])[0, 1]:.4f}; same sign {100 * np.mean(np.sign(z[ok]) == np.sign(zs[ok])):.2f}%")
    print("  z_ratio quantiles 1/5/25/50/75/95/99%: " + " / ".join(f"{np.nanquantile(G.z_ratio, q):.3f}" for q in (.01, .05, .25, .5, .75, .95, .99)))
    print(f"  |z_sym| > threshold_sym at the event bar for {100 * np.nanmean(np.abs(zs) > G.threshold_sym.to_numpy()):.2f}% of events")


if __name__ == "__main__":
    main()
