"""HL-MASTER1 G0 labels (the ONLY columns that use the future), pair level.

    python -u research/dataset/master_labels.py > research/dataset/logs/master_labels.log

INPUT: research/datasets/master/work/pair/events.parquet (stage A) and the 1-minute closes of both legs (user_data/data/hyperliquid/futures/*-1m.feather).
PATH. The 1-minute spread under the event's FROZEN entry geometry, in sigma units: P[m] = (log A - beta log B - alpha - mu) / sigma at the 1-minute close
labelled entry_time + 29 + m minutes, m = 0..600 (m = 0 is the trigger bar's own close = z; the 30m close labelled T is the 1m close labelled T+29).
move[m] = -(P[m] - z) * sign(z): positive = toward mu. mu is frozen (no re-estimation), there is no stop in the path itself.
GAPS. If ANY of the 601 minutes is NaN (an archive hole or a missing minute) every label of the event is NaN and label_gap = 1; label_nan_minutes counts the NaN
minutes. Nothing is filled. (This is build 3's population rule: the 1-minute window finite for both legs.)

LABELS (H in minutes after the trigger close; 2 h = 120, 5 h = 300, 10 h = 600):
  depth_2h/5h/10h        max over minutes 1..H of move (raw, can be negative); depth_10h equals build 3's `depth`
  reach_2h/5h/10h        depth_H >= |z|   (reach_10h equals build 3's `reach`)
  minutes_to_mu          first minute m in 1..600 with move >= |z|, NaN if none
  adverse                1 if move <= -|z| at some minute in 1..600 (the spread widened by at least its entry distance); minutes_to_adverse likewise
  mfe_sigma, mae_sigma   max(0, max move) and max(0, max(-move)) over minutes 1..600, in sigma
  chance_2h/5h/10h       the fraction of 50 seeds in which the path with its 1-minute STEPS multiplied by random +-1 signs reaches |z| within H minutes
                         (build 3's definition). The signs come from a generator seeded per event from [20261024, pair_index, bar_index], so a stored value does not depend on
                         chunking or workers; they are NOT the same draws as build 3's whole-population stream and agree with it in distribution only (reported).
  STOP-AWARE PAYOFF, for a stop distance s in {0.5, 1, 2} sigma beyond the entry level (the stop fires at the first minute with move <= -s), and for
  "none" (no stop): outcome_s = +1 if mu is reached first, -1 if stopped first, 0 if neither within 600 minutes (a minute cannot satisfy both: one close
  per minute). gross_s = the move at the exit minute (the first 1-minute close at or beyond mu / the stop; overshoot beyond the level is kept, because
  that is what a one-minute monitor realises), or move[600] if neither (marked to market at the end of the window). Fees: round trip = rate x position, the position's
  two legs sized 1 : |beta| in notional (spread = log A - beta log B), so a round trip costs rate x (1 + |beta|) per unit of leg-A notional, and one unit of
  leg-A notional earns (change in the log spread) in log units; in sigma units  fee_sigma = rate x (1 + |beta|) / sigma.  rate_taker = 0.00099
  (0.099% of the position per round trip), rate_maker = 0.000495 (half of it).  net_s_taker = gross_s - fee_sigma_taker; net_s_maker = gross_s - fee_sigma_maker.
  Columns: fee_sigma_taker, fee_sigma_maker, and for s in {0p5, 1p0, 2p0, none}: outcome_s, gross_s, net_s_taker, net_s_maker.
CHECKS (asserted): P[:, 0] equals z to 1e-9; P at every 30th minute reproduces y00..y20 to float32 precision (max error reported); reach/depth equal the
old values on the 60,004 old rows where build 3 has them (reach_paths.npz): reported.
OUTPUT: research/datasets/master/work/pair/labels.parquet keyed by event_id.
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
from envelope import load_1m_series, _window

WORK = os.path.join(paths.DATASETS, "master", "work", "pair")
HZ = {"2h": 120, "5h": 300, "10h": 600}
STOPS = {"0p5": 0.5, "1p0": 1.0, "2p0": 2.0, "none": np.inf}
RATE_TAKER, RATE_MAKER = 0.00099, 0.000495
N_SEEDS, CHUNK = 50, 20_000
SEED = 20261024
E = None
SER = None
Y_CHECK = True            # the pair unit checks the 1-minute path against the 30m outcomes y00..y20; the coin unit has none


def paths_for(ev):
    """(n, 601) frozen-geometry 1-minute spread path in sigma units; NaN where either leg's minute is NaN."""
    n = len(ev)
    entry = ev["entry_time"].to_numpy().astype("datetime64[m]")
    beta, alpha, mu, sg = (ev[c].to_numpy(float) for c in ("beta", "alpha", "mu", "sigma"))
    ta, tb = ev["ticker_a"].to_numpy(), ev["ticker_b"].to_numpy()
    P = np.empty((n, 601))
    for j in range(n):
        t0a, aa = SER[ta[j]]
        t0b, ab = SER[tb[j]]
        start = entry[j] + np.timedelta64(29, "m")
        va = _window(aa, int((start - t0a) / np.timedelta64(1, "m")), 601)
        vb = _window(ab, int((start - t0b) / np.timedelta64(1, "m")), 601)
        P[j] = (va - beta[j] * vb - alpha[j] - mu[j]) / sg[j]
    return P


def first_true(m):
    """(n,) first column index (1-based minute) where m is True, NaN if none."""
    anyt = m.any(1)
    return np.where(anyt, m.argmax(1) + 1.0, np.nan)


def chunk_labels(c):
    lo, hi = c * CHUNK, min((c + 1) * CHUNK, len(E))
    ev = E.iloc[lo:hi]
    n = len(ev)
    P = paths_for(ev)
    z = ev["z"].to_numpy(float)
    s = np.where(z >= 0, 1.0, -1.0)
    need = np.abs(z)
    nanmin = np.isnan(P).sum(1)
    gap = nanmin > 0
    out = {"event_id": ev["event_id"].to_numpy(), "label_gap": gap.astype(np.int8), "label_nan_minutes": nanmin.astype(np.int16)}
    fin = ~gap
    out["_p0err"] = np.where(fin, np.abs(P[:, 0] - z), 0.0)
    # 30-minute reproduction
    if Y_CHECK:
        Y = np.load(os.path.join(WORK, "events_y.npz"))["y"][lo:hi].astype(np.float64)
        out["_yerr"] = np.where(fin, np.abs(P[:, ::30][:, :21] - Y).max(1), 0.0)
    else:
        out["_yerr"] = np.zeros(n)
    move = -(P - z[:, None]) * s[:, None]
    seg = move[:, 1:601]
    nan_row = np.nan
    cm = np.maximum.accumulate(seg, axis=1)
    for nm, H in HZ.items():
        d = np.where(fin, cm[:, H - 1], nan_row)
        out[f"depth_{nm}"] = d
        out[f"reach_{nm}"] = np.where(fin, (d >= need).astype(float), nan_row)
    hit_mu = seg >= need[:, None]
    t_mu = np.where(fin, first_true(hit_mu), nan_row)
    out["minutes_to_mu"] = t_mu
    hit_adv = seg <= -need[:, None]
    t_adv = np.where(fin, first_true(hit_adv), nan_row)
    out["adverse"] = np.where(fin, (~np.isnan(t_adv)).astype(float), nan_row)
    out["minutes_to_adverse"] = t_adv
    out["mfe_sigma"] = np.where(fin, np.maximum(cm[:, 599], 0.0), nan_row)
    out["mae_sigma"] = np.where(fin, np.maximum((-seg).max(1), 0.0), nan_row)
    beta = ev["beta"].to_numpy(float)
    sig = ev["sigma"].to_numpy(float)
    ft, fm = RATE_TAKER * (1 + np.abs(beta)) / sig, RATE_MAKER * (1 + np.abs(beta)) / sig
    out["fee_sigma_taker"], out["fee_sigma_maker"] = ft, fm
    tmu = np.where(np.isnan(t_mu), np.inf, t_mu)
    rows = np.arange(n)
    for nm, sd in STOPS.items():
        if np.isinf(sd):
            tst = np.full(n, np.inf)
        else:
            tst = np.where(fin, np.where((seg <= -sd).any(1), (seg <= -sd).argmax(1) + 1.0, np.inf), np.inf)
        res = np.where(tmu < tst, 1.0, np.where(tst < tmu, -1.0, 0.0))
        ex = np.minimum(np.minimum(tmu, tst), 600).astype(int)
        gross = seg[rows, ex - 1]
        out[f"outcome_{nm}"] = np.where(fin, res, nan_row)
        out[f"gross_{nm}"] = np.where(fin, gross, nan_row)
        out[f"net_{nm}_taker"] = np.where(fin, gross - ft, nan_row)
        out[f"net_{nm}_maker"] = np.where(fin, gross - fm, nan_row)
    # chance: 50 sign-flip seeds on the 1-minute steps, seeded PER EVENT from a stable key (pair_index, bar_index), so a stored value does not depend
    # on chunking or worker layout. NaN rows are skipped.
    inc = np.diff(move[:, :601], axis=1)
    hits = {nm: np.zeros(n) for nm in HZ}
    pi, bi = ev["pair_index"].to_numpy(), ev["bar_index"].to_numpy()
    for j in range(n):
        if gap[j]:
            continue
        rng = np.random.default_rng([SEED, int(pi[j]), int(bi[j])])
        sg_ = rng.integers(0, 2, size=(N_SEEDS, 600), dtype=np.int8) * 2 - 1
        pth = np.cumsum(inc[j][None, :] * sg_, axis=1)
        for nm, H in HZ.items():
            hits[nm][j] = (pth[:, :H].max(1) >= need[j]).sum()
    for nm in HZ:
        out[f"chance_{nm}"] = np.where(fin, hits[nm] / N_SEEDS, nan_row)
    return pd.DataFrame(out)


def main():
    global E, SER
    t0 = time.time()
    E = pd.read_parquet(os.path.join(WORK, "events.parquet"))
    coins = sorted(set(E.ticker_a) | set(E.ticker_b))
    SER = load_1m_series(coins, True)
    nchunk = (len(E) + CHUNK - 1) // CHUNK
    print(f"[LABELS] {len(E):,} events, {nchunk} chunks of {CHUNK:,}, {len(coins)} coins; 1-minute series loaded [{time.time() - t0:.0f}s]", flush=True)
    outs = []
    with Pool(int(os.environ.get("NPROC", 8))) as pool:
        for q, df in enumerate(pool.imap(chunk_labels, range(nchunk))):
            outs.append(df)
            if (q + 1) % 20 == 0:
                print(f"  {q + 1}/{nchunk} chunks  [{time.time() - t0:.0f}s]", flush=True)
    L = pd.concat(outs, ignore_index=True)
    p0, ye = float(L.pop("_p0err").max()), float(L.pop("_yerr").max())
    print(f"[CHECK] max |P[:,0] - z| {p0:.3e}; max |1-minute path at the 30-minute marks - y00..y20| {ye:.3e}")
    assert p0 < 1e-9, "the 1-minute path does not start at z"
    assert ye < 1e-4, "the 1-minute path does not reproduce the 30-minute outcomes"
    L.to_parquet(os.path.join(WORK, "labels.parquet"), index=False)
    ok = L.label_gap == 0
    print(f"[DONE] {len(L):,} events; label_gap {int((~ok).sum()):,} ({100 * (~ok).mean():.2f}%); reach 2h/5h/10h "
          f"{L.reach_2h[ok].mean():.4f} / {L.reach_5h[ok].mean():.4f} / {L.reach_10h[ok].mean():.4f}; mean chance "
          f"{L.chance_2h[ok].mean():.4f} / {L.chance_5h[ok].mean():.4f} / {L.chance_10h[ok].mean():.4f}; adverse {L.adverse[ok].mean():.4f}  [{time.time() - t0:.0f}s]")
    # invariants
    assert (L.reach_2h[ok] <= L.reach_5h[ok]).all() and (L.reach_5h[ok] <= L.reach_10h[ok]).all(), "reach is not monotone in horizon"
    assert (L.chance_2h[ok] <= L.chance_5h[ok] + 1e-12).all() and (L.chance_5h[ok] <= L.chance_10h[ok] + 1e-12).all(), "chance is not monotone in horizon"
    assert not L.event_id.duplicated().any()
    # old rows: reach and depth equal build 3's
    M = pd.read_parquet(paths.META)
    Ev = E[["event_id", "ticker_a", "ticker_b", "entry_time"]]
    mm = M.reset_index().merge(Ev, on=["ticker_a", "ticker_b", "entry_time"], how="left")
    RP = np.load(os.path.join(paths.DATASETS, "reach_paths.npz"))
    rows = RP["rows"]
    got = L.set_index("event_id").loc[mm.event_id.to_numpy()[rows]]
    dr = np.abs(got.depth_10h.to_numpy() - RP["depth"]).max()
    rr = int((got.reach_10h.to_numpy().astype(bool) != RP["reach"]).sum())
    tr = int((np.nan_to_num(got.minutes_to_mu.to_numpy(), nan=-1) != RP["t_reach"]).sum())
    print(f"[REPRODUCE] build 3 rows {len(rows):,}: max |depth_10h - depth| {dr:.3e}; reach differs on {rr}; first minute at mu differs on {tr}; "
          f"label_gap among them {int(got.label_gap.sum())}")
    # build 3 measured the path from e = Y[rows, 0], the float32 z; here z is the exact float64 entry z. reach (depth - |z|) and the first minute at mu do not depend on
    # that rounding, depth itself differs by at most float32 eps x |z| (< 1e-6).
    print(f"  (depth differs only by the float32 rounding of build 3's entry z: max |depth diff| {dr:.2e} < 1e-6; reach and first minute identical)")
    assert dr < 1e-6 and rr == 0 and tr == 0, "labels do not reproduce build 3's reach, depth and first minute at mu"
    assert int(got.label_gap.sum()) == 0, "an old (finite-path) row has label_gap = 1"
    dch = got.chance_10h.to_numpy() - RP["chance"]
    dd = pd.to_datetime(M.entry_time.iloc[rows]).dt.floor("D").to_numpy()
    ud, inv = np.unique(dd, return_inverse=True)
    sm, ct = np.bincount(inv, weights=dch), np.bincount(inv).astype(float)
    rg = np.random.default_rng(1)
    pick = rg.integers(0, len(ud), size=(300, len(ud)))
    bm = sm[pick].sum(1) / ct[pick].sum(1)
    lo_, hi_ = np.percentile(bm, [2.5, 97.5])
    print(f"[CHANCE vs build 3] mean chance_10h new {got.chance_10h.mean():.4f}, build 3 {RP['chance'].mean():.4f}; mean difference {dch.mean():+.5f} "
          f"[{lo_:+.5f},{hi_:+.5f}] (day-clustered); per-row correlation {np.corrcoef(got.chance_10h.to_numpy(), RP['chance'])[0, 1]:.4f}; "
          f"a 50-seed Monte-Carlo value has sd up to 0.07 per row, so exact equality is not expected (different random draws)")


if __name__ == "__main__":
    main()
