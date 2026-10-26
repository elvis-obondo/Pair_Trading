"""HL-EVENT1 Part A1 + A2: coin-level dislocations and their matched controls.

    python -u research/dislocation_model/coinevents.py

BENCHMARK (A1). For a coin c at 30-minute bar t, the benchmark return is the equal-weight
mean of the finite 30m log returns of all OTHER live coins (BTC and ETH included, c
excluded); it is NaN when c's own return is not finite or fewer than 30 other coins are.
The index LEVEL is the cumulative sum of those returns inside a segment. A SEGMENT is a
maximal run of bars with finite benchmark returns (extended one bar back for the base
price); a NaN return starts a new segment, and no window, threshold or geometry spans a
NaN (build 2's rule (i)). The coin's spread is rolling_spread_stats(log price, index level):
the same 96-bar symmetric vol-matched geometry and code as the pair-level set.

TRIGGER. The adaptive rule, unchanged: a fresh crossing of |z| above the 99th percentile
(numpy linear) of the previous 96 |z| (bars i-96..i-1), no absolute floor, all 96 prior z
and both thresholds finite. NO sampling cap: every trigger in every segment of the 204
non-factor coins is an event. An event's outcome window needs i + 20 <= len(segment) - 1;
events without one are KEPT (`has_outcome` False) for the pre-trigger flow profile and
excluded from the reach target.

CONTROLS (A2), per event, up to 5 bars from the SAME coin:
  match   (i) the coin's trailing-48-bar volatility DECILE: the std of its 48 30m log returns
          at bars b-48..b-1 (all finite; the trigger bar's own return is EXCLUDED so the
          dislocating move does not set the decile), ranked against the previous 336 such
          values (the same series at bars b-336..b-1; NaN if fewer than 144),
          decile = floor(10 * share <= current); UTC hour of the cutoff C = T + 30 min within
          +/- 2 h (circular); weekday/weekend.  [Gap filled (a), ruled by Code Checker.]
  set 1   (ii) not within +/- 24 h (48 bars) of any trigger of that coin; (iii) a finite
          window: finite z and threshold at the bar, the C24 flow window [C-1440, C) finite
          (taker notional on every minute) and the coin's 30m prices over that span finite.
  set 2   "near-miss": |z| >= the 90th percentile of the previous 96 |z| and no fresh
          crossing of the 99th at bars i-4..i; the same matching (i), (ii) and (iii).
          [Gap filled (b), ruled by Code Checker: (ii) applies to set 2 as well ("same
          matching otherwise"); the number of near-miss candidates it removes is reported.
          (d): (iii) is a control acceptance criterion, applied here, not left to later
          NaN-dropping.]  Events are NOT filtered by C24 finiteness; the count of events
          with a non-finite C24 window is reported.
  The control's sign d' = sign(z) at the control bar. Matching uses no outcome and no flow.
  Controls may serve several events; within one event they are drawn without replacement
  (seeded). Events with no control are reported.

Per-coin per-bar arrays (z, thresholds, beta, mu, sigma, index level, ...) are cached under
datasets/ev_coinstats/{coin}.npz so the flow stage reads the SAME statistics.
Outputs datasets/ev_events.parquet (one row per event) and datasets/ev_pairs.parquet (one
row per event x control link: set, control bar, d', z', beta, ...). Times: `T` is the
30-minute bar label; t = 0 is T + 30 minutes.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import paths
import rolling_spread as rs
import universe_panel

EVENTS = os.path.join(paths.DATASETS, "ev_events.parquet")
PAIRS = os.path.join(paths.DATASETS, "ev_pairs.parquet")
STATS_DIR = os.path.join(paths.DATASETS, "ev_coinstats")
STATS_TABLE = os.path.join(paths.DATASETS, "ev_coin_table.parquet")
THR_BARS, THR_PCT, NEAR_PCT = 96, 99.0, 90.0
HORIZONS = 20
MINB = rs.min_bars_required(0.5)
SEG_MIN = MINB + THR_BARS          # shortest segment that can hold one trigger
N_CTRL = 5
EXCL_BARS = 48                     # +/- 24 h
MIN_OTHER = 30
VOL_BARS, DEC_PRIOR, DEC_MIN = 48, 336, 144
SEED = 20261015


def load_panel():
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    return panel, pd.to_datetime(panel.index), panel.to_numpy(float), list(panel.columns)


def prior_pct(absz, pct):
    """pct-th percentile (linear) of absz[i-96 .. i-1]; NaN where any of those is NaN or i < 96."""
    out = np.full(len(absz), np.nan)
    if len(absz) > THR_BARS:
        w = np.lib.stride_tricks.sliding_window_view(absz, THR_BARS)[: len(absz) - THR_BARS]
        good = np.isfinite(w).all(axis=1)
        q = np.full(len(w), np.nan)
        if good.any():
            q[good] = np.percentile(w[good], pct, axis=1)
        out[THR_BARS:] = q
    return out


def index_returns(V):
    """(S, n, R): sums and counts of finite 30m returns over all coins, and the returns."""
    R = np.full_like(V, np.nan)
    R[1:] = V[1:] - V[:-1]
    fin = np.isfinite(R)
    return np.where(fin, R, 0.0).sum(1), fin.sum(1), R


def coin_index_ret(S, n, R, j):
    """The benchmark return for coin j: equal-weight mean of the OTHER coins' finite returns."""
    r = R[:, j]
    fin = np.isfinite(r)
    no = n - fin
    with np.errstate(invalid="ignore", divide="ignore"):
        ir = (S - np.where(fin, r, 0.0)) / no
    return np.where(fin & (no >= MIN_OTHER), ir, np.nan)


def segments_of(ir):
    """Maximal runs of finite benchmark returns -> (first price bar, last price bar) inclusive."""
    fin = np.isfinite(ir)
    e = np.diff(np.r_[0, fin.astype(np.int8), 0])
    return [(s - 1, t - 1) for s, t in zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)) if s >= 1]


def vol_decile(r):
    """Std of the 48 30m log returns at bars b-48..b-1 (the trigger bar's own return excluded) and its
    decile against the same series at the previous 336 bars."""
    n = len(r)
    vol = np.full(n, np.nan)
    if n >= VOL_BARS:
        w = np.lib.stride_tricks.sliding_window_view(r, VOL_BARS)
        ok = np.isfinite(w).all(axis=1)
        v = np.full(len(w), np.nan)
        v[ok] = w[ok].std(axis=1, ddof=1)
        vol[VOL_BARS:] = v[:-1]                            # vol[b] = std of r[b-48 .. b-1]
    dec = np.full(n, -1, np.int8)
    if n > DEC_PRIOR:
        pw = np.lib.stride_tricks.sliding_window_view(vol, DEC_PRIOR)[: n - DEC_PRIOR]       # vol[b-336 .. b-1] for b = 336..
        cur = vol[DEC_PRIOR:]
        nvalid = np.isfinite(pw).sum(1)
        share = (pw <= cur[:, None]).sum(1) / np.maximum(nvalid, 1)
        d = np.minimum(np.floor(10 * share), 9).astype(np.int8)
        d[(nvalid < DEC_MIN) | ~np.isfinite(cur)] = -1
        dec[DEC_PRIOR:] = d
    return vol, dec


def coin_stats(j, V, S, n30, R):
    """Per-bar arrays for one coin: benchmark return, index LEVEL (segment-wise from 0), the spread
    statistics, the trigger flags and the segment ids. Cached by main() under datasets/ev_coinstats/."""
    ir = coin_index_ret(S, n30, R, j)
    segs = segments_of(ir)
    nb = len(V)
    z = np.full(nb, np.nan); thr = np.full(nb, np.nan); p90 = np.full(nb, np.nan)
    beta = np.full(nb, np.nan); alpha = np.full(nb, np.nan); mu = np.full(nb, np.nan)
    sigma = np.full(nb, np.nan); r2 = np.full(nb, np.nan)
    segid = np.full(nb, -1, np.int32); segend = np.full(nb, -1, np.int32)
    hit = np.zeros(nb, bool)
    L = np.full(nb, np.nan)
    for sid, (a, b) in enumerate(segs):
        if b - a + 1 < SEG_MIN:
            continue
        lvl = np.concatenate([[0.0], np.cumsum(ir[a + 1:b + 1])])
        L[a:b + 1] = lvl
        st = rs.rolling_spread_stats(V[a:b + 1, j], lvl, 0.5)
        zz = st.z
        fz = np.isfinite(zz) & np.isfinite(st.sigma) & (st.sigma > 0)
        absz = np.where(fz, np.abs(zz), np.nan)
        t99, t90 = prior_pct(absz, THR_PCT), prior_pct(absz, NEAR_PCT)
        h = np.zeros(len(zz), bool)
        h[1:] = fz[1:] & fz[:-1] & np.isfinite(t99[1:]) & np.isfinite(t99[:-1]) & (absz[1:] > t99[1:]) & (absz[:-1] <= t99[:-1])
        sl = slice(a, b + 1)
        z[sl], thr[sl], p90[sl] = zz, t99, t90
        beta[sl], alpha[sl], mu[sl], sigma[sl], r2[sl] = st.beta, st.alpha, st.mu, st.sigma, st.r2
        segid[sl] = sid; segend[sl] = b
        hit[sl] = h
    return dict(ir=ir, L=L, z=z, thr=thr, p90=p90, beta=beta, alpha=alpha, mu=mu, sigma=sigma, r2=r2,
                seg=segid, segend=segend, hit=hit, nseg=sum(1 for a, b in segs if b - a + 1 >= SEG_MIN))


def c24_ok_bars(c, j, V, idx):
    """Per bar: the C24 flow window [C-1440, C) has finite taker notional on every minute AND the
    coin's 30m prices over bars b-48..b are finite."""
    import flowfeat as ff
    fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date", "taker_buy_usd"])
    nc = ff.cum_nan(ff.dense(fl, "taker_buy_usd"))[1]
    o = ff.minute_index(idx + pd.Timedelta(minutes=30))
    lim = (o - 1440 >= 0) & (o <= ff.N)
    e, s = np.where(lim, o, 0), np.where(lim, o - 1440, 0)
    flow_ok = lim & ((nc[e] - nc[s]) == 0)
    fin = np.isfinite(V[:, j]).astype(np.int64)
    cf = np.concatenate([[0], np.cumsum(fin)])
    b = np.arange(len(fin))
    price_ok = (b - 48 >= 0) & ((cf[b + 1] - cf[np.maximum(b - 48, 0)]) == 49)
    return flow_ok & price_ok


def coin_tables(j, name, st_, idx, R, rng, V=None):
    """Events and control links for one coin. Returns (events dict-of-arrays, pairs dict-of-arrays, stats)."""
    z, thr, p90, beta, alpha, mu = st_["z"], st_["thr"], st_["p90"], st_["beta"], st_["alpha"], st_["mu"]
    sigma, r2, segid, segend, hit = st_["sigma"], st_["r2"], st_["seg"], st_["segend"], st_["hit"]
    nb = len(z)
    r30 = R[:, j]
    vol, dec = vol_decile(r30)
    cdt = idx + pd.Timedelta(minutes=30)
    hour = cdt.hour.to_numpy(); wk = (cdt.dayofweek.to_numpy() >= 5).astype(np.int8)
    ev = np.flatnonzero(hit)
    finz = np.isfinite(z) & np.isfinite(thr)
    # --- events
    E = dict(bar=ev, d=np.where(z[ev] >= 0, 1.0, -1.0), z=z[ev], thr=thr[ev], beta=beta[ev], alpha=alpha[ev], mu=mu[ev],
             sigma=sigma[ev], r2=r2[ev], seg=segid[ev], dec=dec[ev], vol48=vol[ev], hour=hour[ev], wkend=wk[ev],
             has_outcome=(ev + HORIZONS <= segend[ev]))
    # --- control candidates
    near_recent = np.zeros(nb, bool)
    for k in range(0, 5):                                      # a fresh crossing at bars i-4 .. i
        near_recent[k:] |= hit[: nb - k]
    c_far = np.ones(nb, bool)
    for e_ in ev:
        c_far[max(e_ - EXCL_BARS, 0):e_ + EXCL_BARS + 1] = False
    w24 = c24_ok_bars(name, j, V, idx)
    base = finz & (dec >= 0) & w24
    cand1 = base & c_far & np.isfinite(p90)
    cand2_pre = base & np.isfinite(p90) & (np.abs(z) >= p90) & ~near_recent
    cand2 = cand2_pre & c_far
    pairs = {k: [] for k in ("ev", "set", "bar")}
    nmatch = {1: [], 2: []}
    for s_, cand in ((1, cand1), (2, cand2)):
        cb = np.flatnonzero(cand)
        keymap = {}
        for b_ in cb:
            keymap.setdefault((int(dec[b_]), int(wk[b_]), int(hour[b_])), []).append(b_)
        keymap = {k: np.array(v) for k, v in keymap.items()}
        for i_, e_ in enumerate(ev):
            if dec[e_] < 0:
                nmatch[s_].append(0); continue
            pool = [keymap[k] for dh in range(-2, 3)
                    if (k := (int(dec[e_]), int(wk[e_]), int((hour[e_] + dh) % 24))) in keymap]
            pool = np.concatenate(pool) if pool else np.array([], int)
            pool = pool[pool != e_]
            nmatch[s_].append(len(pool))
            if len(pool):
                pick = rng.choice(pool, size=min(N_CTRL, len(pool)), replace=False)
                pairs["ev"] += [i_] * len(pick); pairs["set"] += [s_] * len(pick); pairs["bar"] += pick.tolist()
    pb = np.array(pairs["bar"], int)
    P = dict(ev=np.array(pairs["ev"], int), set=np.array(pairs["set"], np.int8), bar=pb,
             d=np.where(z[pb] >= 0, 1.0, -1.0), z=z[pb], beta=beta[pb], alpha=alpha[pb], mu=mu[pb], sigma=sigma[pb],
             hour=hour[pb], wkend=wk[pb])
    stats = dict(coin=name, events=len(ev), has_outcome=int(E["has_outcome"].sum()), cand1=int(cand1.sum()), cand2=int(cand2.sum()),
                 cand2_pre=int(cand2_pre.sum()), ev_c24_bad=int((~w24[ev]).sum()),
                 no_ctrl1=int(sum(1 for m in nmatch[1] if m == 0)), no_ctrl2=int(sum(1 for m in nmatch[2] if m == 0)),
                 segments=st_["nseg"])
    return E, P, stats


def main():
    t0 = time.time()
    panel, idx, V, cols = load_panel()
    S, n30, R = index_returns(V)
    factor = universe_panel.FACTOR_ONLY
    coins = [(j, c) for j, c in enumerate(cols) if universe_panel._base_symbol(c) not in factor]
    print(f"[INFO] panel {V.shape[0]} bars x {V.shape[1]} coins; {len(coins)} non-factor coins; SEG_MIN {SEG_MIN}", flush=True)
    ev_rows, pr_rows, st_rows = [], [], []
    eoff = 0
    for k, (j, c) in enumerate(coins):
        rng = np.random.default_rng([SEED, j])
        cs_ = coin_stats(j, V, S, n30, R)
        os.makedirs(STATS_DIR, exist_ok=True)
        np.savez_compressed(os.path.join(STATS_DIR, f"{c}.npz"), **{k_: v_ for k_, v_ in cs_.items() if k_ != "nseg"})
        E, P, st = coin_tables(j, c, cs_, idx, R, rng, V)
        if st["events"]:
            ev_rows.append(pd.DataFrame({"coin": c, "coin_j": j, "T": idx[E["bar"]], **{kk: vv for kk, vv in E.items()}}))
            pr_rows.append(pd.DataFrame({"coin": c, "coin_j": j, "event": P["ev"] + eoff, "T": idx[P["bar"]],
                                         **{kk: vv for kk, vv in P.items() if kk != "ev"}}))
            eoff += st["events"]
        st_rows.append(st)
        if (k + 1) % 30 == 0:
            print(f"  coin {k + 1}/{len(coins)}  events so far {eoff:,}  [{time.time() - t0:.0f}s]", flush=True)
    EV = pd.concat(ev_rows, ignore_index=True)
    EV["event_id"] = np.arange(len(EV))
    PR = pd.concat(pr_rows, ignore_index=True)
    EV.to_parquet(EVENTS)
    PR.to_parquet(PAIRS)
    ST = pd.DataFrame(st_rows)
    ST.to_parquet(STATS_TABLE)
    report(EV, PR, ST)
    print(f"[WROTE] {os.path.relpath(EVENTS, paths.RESEARCH)}, {os.path.relpath(PAIRS, paths.RESEARCH)}  [{time.time() - t0:.0f}s]")


def report(EV, PR, ST):
    az = EV.z.abs()
    print()
    print(f"EVENTS: {len(EV):,} (every trigger, no cap) over {EV.coin.nunique()} coins; with a 10h outcome window "
          f"{int(EV.has_outcome.sum()):,}; segments used {int(ST.segments.sum()):,}")
    pc = EV.groupby("coin").size()
    print(f"  per coin: min {pc.min()}, median {int(pc.median())}, max {pc.max()}; coins with none: {int((ST.events == 0).sum())}")
    print(f"  long (z > 0) {100 * (EV.z > 0).mean():.1f}%  short {100 * (EV.z < 0).mean():.1f}%")
    print(f"  |z| < 2: {100 * (az < 2).mean():.1f}%   2-3: {100 * ((az >= 2) & (az < 3)).mean():.1f}%   >= 3: {100 * (az >= 3).mean():.1f}%")
    print("  per month:", "  ".join(f"{str(p)} {c:,}" for p, c in EV["T"].dt.to_period("M").value_counts().sort_index().items()))
    for s_, lbl in ((1, "set 1 (matched, far from triggers)"), (2, "set 2 (near-miss)")):
        p = PR[PR.set == s_]
        per = p.groupby("event").size().reindex(EV.event_id, fill_value=0)
        nc = int((ST[f"no_ctrl{s_}"]).sum())
        print(f"  CONTROLS {lbl}: {len(p):,} links; events with 0 controls {nc:,} ({100 * nc / len(EV):.2f}%); "
              f"controls per event: mean {per.mean():.2f}, median {int(per.median())}, share with 5: {100 * (per == 5).mean():.1f}%; "
              f"candidate bars {int(ST[f'cand{s_}'].sum()):,}")
    print(f"  events with an unknown volatility decile (control match impossible): {int((EV.dec < 0).sum()):,}")
    if "ev_c24_bad" in ST:
        print(f"  events whose C24 flow window or 30m prices over it are not finite: {int(ST.ev_c24_bad.sum()):,} "
              f"({100 * ST.ev_c24_bad.sum() / len(EV):.2f}%); near-miss candidates removed by the +/- 24 h exclusion: "
              f"{int(ST.cand2_pre.sum() - ST.cand2.sum()):,} of {int(ST.cand2_pre.sum()):,}")


if __name__ == "__main__":
    main()
