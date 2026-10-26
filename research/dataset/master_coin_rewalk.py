"""HL-MASTER1 integrity item 5, coin unit: labels re-walk with an INDEPENDENT benchmark (checker 2026-10-26).

    python -u research/dataset/master_coin_rewalk.py > research/dataset/logs/master_coin_rewalk.log
    STORED=1 python -u research/dataset/master_coin_rewalk.py > research/dataset/logs/master_coin_rewalk_stored.log     (2,000 events against the stored benchmark return series)

For 500 random coin events with label_gap = 0 and 100 with label_gap = 1 (the gaps must agree), the whole path is rebuilt from the RAW 1-minute feathers, without master_coin / eventflow / coinevents code:
  1. every coin's 1-minute log closes (universe = the flow-table coins, as evmarket); 1-minute returns r(m) = lc(m) - lc(m-1) where both finite;
  2. the 30m panel from the 30m BAR FILES (the coin's log close at the bar's open time; compared with the 1m close labelled T + 29, which agrees wherever both exist); benchmark return ir(b) = mean of the OTHER coins' finite 30m log returns, valid when the coin's own return is finite
     and at least 30 others are finite;
  3. the segment of the event's bar: the maximal run of finite ir around it (first price bar = the bar before the first finite return); the index LEVEL L = 0 at the segment's first bar and L(b) = L(b-1) + ir(b);
  4. the BRIDGED 1-minute level inside a bar b (30 minutes ending at t0_b = minute_index(T_b + 30)): LV(t0_b - 30 + 1 + k) = L(b-1) + sum_{i<=k} idx1(t0_b - 30 + i) + (k+1)/30 x (ir(b) - sum_{i<29} idx1) for k = 0..29,
     with idx1(m) = the mean of the OTHER coins' finite 1-minute returns at minute m (valid when the coin's own return is finite and >= 30 others);
  (the m = 0 point is bridged inside the trigger bar like any other: if one of that bar's 30 one-minute index returns is missing it is NaN, as in the stored labels, even though L(b) itself is known)
  5. the path P(m) = (lc(tau-1) - beta LV(tau) - alpha - mu) / sigma, tau = t0 + m, m = 0..600, with the event's stored frozen beta, alpha, mu, sigma; P(0) must equal z (asserted to 1e-9);
  6. the labels depth_10h, reach_10h, minutes_to_mu, adverse, mfe_sigma, mae_sigma, outcome_1p0, gross_1p0 (the definitions of the dictionary), compared with labels.parquet (tolerance 1e-5 sigma, integers exact).
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths
import flowfeat as ff
from adapters.hyperliquid_futures import HL_FUTURES_DIR, bar_file

WORK = os.path.join(paths.DATASETS, "master", "work", "coin")
MIN_OTHER = 30
rng = np.random.default_rng(20261026)


def main():
    t0 = time.time()
    E = pd.read_parquet(os.path.join(WORK, "events.parquet"))
    LB = pd.read_parquet(os.path.join(WORK, "labels.parquet"))
    coins = sorted(f[:-8] for f in os.listdir(ff.FLOW_DIR) if f.endswith(".parquet"))
    lc = {}
    for c in coins:
        p = HL_FUTURES_DIR / f"{c}-1m.feather"
        if not p.exists():
            continue
        f = pd.read_feather(p, columns=["date", "close"])
        a = np.full(ff.N, np.nan)
        ix = ff.minute_index(f["date"].dt.tz_localize(None))
        ok = (ix >= 0) & (ix < ff.N)
        a[ix[ok]] = np.log(f["close"].to_numpy(float)[ok])
        lc[c] = a
    names = sorted(lc)
    print(f"[REWALK coin] raw 1m closes of {len(names)} coins loaded  [{time.time() - t0:.0f}s]", flush=True)
    # 1-minute returns and the cross-section sums (own computation)
    S1 = np.zeros(ff.N); n1 = np.zeros(ff.N, np.int64)
    R1 = {}
    for c in names:
        r = np.full(ff.N, np.nan); r[1:] = lc[c][1:] - lc[c][:-1]
        R1[c] = r
        fin = np.isfinite(r)
        S1 += np.where(fin, r, 0.0); n1 += fin
    # bar axis: the entry_time grid of the events' bars; bar_index -> T via the union of events' (bar_index, entry_time) pairs
    bt = E.groupby("bar_index").entry_time.first()
    nb = int(bt.index.max()) + 1
    T = pd.Series(pd.NaT, index=range(nb), dtype="datetime64[ns]")
    T.loc[bt.index] = bt.to_numpy()
    # the bar axis is a regular 30-minute grid: fill every bar from the known ones
    t_first = bt.iloc[0] - pd.Timedelta(minutes=30) * int(bt.index[0])
    Tall = pd.DatetimeIndex([t_first + pd.Timedelta(minutes=30) * b for b in range(nb)])
    assert (Tall[bt.index.to_numpy()] == pd.DatetimeIndex(bt.to_numpy())).all(), "bar axis is not a regular 30-minute grid"
    o_bar = ff.minute_index(Tall + pd.Timedelta(minutes=30))             # t0 of each bar (minute index o)
    close_ix = o_bar - 1                                                  # the 1-minute close labelled T + 29
    ok_ix = (close_ix >= 0) & (close_ix < ff.N)
    V = np.full((nb, len(names)), np.nan)                                # the 30m closes from the 30m BAR FILES (the source of the 30m panel), indexed by the bar's open time
    V1 = np.full((nb, len(names)), np.nan)                               # the same from the 1m closes at T + 29, for the comparison below
    tpos = pd.Series(np.arange(nb), index=Tall)
    for k, c in enumerate(names):
        V1[ok_ix, k] = lc[c][close_ix[ok_ix]]
        b30 = pd.read_feather(bar_file(c, "30m"), columns=["date", "close"])
        dts = pd.DatetimeIndex(b30["date"].dt.tz_localize(None))
        pos = tpos.reindex(dts).to_numpy()
        okp = np.isfinite(pos)
        V[pos[okp].astype(int), k] = np.log(b30["close"].to_numpy(float)[okp])
    both = np.isfinite(V) & np.isfinite(V1)
    dis = np.argwhere(np.isfinite(V) != np.isfinite(V1))
    one = {}
    for k, c in enumerate(names):
        f1 = pd.read_feather(HL_FUTURES_DIR / f"{c}-1m.feather", columns=["date", "close"])
        one[c] = pd.DatetimeIndex(f1["date"].dt.tz_localize(None))
    print(f"[REWALK coin] the {len(dis)} coin-bars finite in one price file only (coin, 30m bar label T, 30m close, 1m close at T+29, 1m row exists at T+29, 30m row exists):")
    b30rows = {}
    for b, k in dis:
        c = names[k]
        t29 = Tall[b] + pd.Timedelta(minutes=29)
        if c not in b30rows:
            b30rows[c] = pd.DatetimeIndex(pd.read_feather(bar_file(c, "30m"), columns=["date"])["date"].dt.tz_localize(None))
        print(f"   {c:<10} {Tall[b]}  30m close {np.exp(V[b, k]) if np.isfinite(V[b, k]) else float('nan'):.6g}  1m close {np.exp(V1[b, k]) if np.isfinite(V1[b, k]) else float('nan'):.6g}  1m row {bool(one[c].isin([t29]).any())}  30m row {bool(b30rows[c].isin([Tall[b]]).any())}")
    print(f"[REWALK coin] 30m closes from the 30m bar files vs the 1m close labelled T + 29: max |diff| where both finite {np.abs(V - V1)[both].max():.2e}; finite in one only: {int((np.isfinite(V) != np.isfinite(V1)).sum())} coin-bars (the independent benchmark uses the 30m bar files, as the panel does)")
    R = np.full_like(V, np.nan); R[1:] = V[1:] - V[:-1]
    finR = np.isfinite(R)
    S30 = np.where(finR, R, 0.0).sum(1); n30 = finR.sum(1)
    print(f"[REWALK coin] 30m panel {V.shape} rebuilt  [{time.time() - t0:.0f}s]", flush=True)
    import coinevents as ce
    stored = os.environ.get("STORED") == "1" or os.environ.get("GAPS") == "1"
    GAPS = os.environ.get("GAPS") == "1"
    gap_tab = []
    ok_lbl = np.flatnonzero(LB.label_gap.to_numpy() == 0)
    gap_lbl = np.flatnonzero(LB.label_gap.to_numpy() == 1)
    pick = gap_lbl if GAPS else rng.choice(ok_lbl, 2000, replace=False) if stored else np.r_[rng.choice(ok_lbl, 500, replace=False), rng.choice(gap_lbl, min(100, len(gap_lbl)), replace=False)]
    bad, nc, ngap_ok, nlab = [], 0, 0, 0
    perc = {}
    for r in pick:
        e = E.iloc[r]
        c = e.ticker_a
        k = names.index(c)
        if c not in perc:
            fin = finR[:, k]
            no = n30 - fin
            with np.errstate(invalid="ignore", divide="ignore"):
                ir = np.where(fin & (no >= MIN_OTHER), (S30 - np.where(fin, R[:, k], 0.0)) / no, np.nan)
            fr = np.isfinite(ir)
            seg = np.cumsum(np.r_[0, np.diff(fr.astype(np.int8)) == 1]) * fr        # run id (0 = not in a run)
            fin1 = np.isfinite(R1[c])
            no1 = n1 - fin1
            with np.errstate(invalid="ignore", divide="ignore"):
                idx1 = np.where(fin1 & (no1 >= MIN_OTHER), (S1 - np.where(fin1, R1[c], 0.0)) / no1, np.nan)
            if stored:                                                   # STORED mode: the benchmark return and level of the lineage (coin stats), only the bridging and the label logic are re-done
                st = np.load(os.path.join(ce.STATS_DIR, f"{c}.npz"))
                ir = st["ir"][:nb].astype(float); fr = np.isfinite(ir)
            perc[c] = (ir, fr, seg, idx1)
        ir, fr, seg, idx1 = perc[c]
        b = int(e.bar_index)
        P = np.full(601, np.nan)
        if fr[b]:
            a = b
            while a - 1 >= 0 and fr[a - 1]:
                a -= 1
            a -= 1                                                       # the first price bar of the segment = the bar before the first finite return
            L = np.zeros(nb) * np.nan
            L[a] = 0.0
            last = b + 21
            for q in range(a + 1, min(last, nb - 1) + 1):
                if not fr[q]:
                    break
                L[q] = L[q - 1] + ir[q]
            t0m = int(o_bar[b])
            taus = t0m + np.arange(601)
            LV = np.full(601, np.nan)
            for m in range(601):
                tau = taus[m]
                q = b + (m - 1) // 30 + 1 if m > 0 else b               # the bar whose 30 minutes (o_q - 30, o_q] contain tau; m = 0 is the last minute of the trigger bar itself
                if q >= nb or not np.isfinite(L[q - 1]) or not np.isfinite(ir[q]):
                    continue
                oq = int(o_bar[q])
                kk = tau - (oq - 30) - 1                                  # 0..29
                mm = idx1[oq - 30: oq]
                cum = np.cumsum(mm)
                if not np.isfinite(cum[-1]):
                    continue
                LV[m] = L[q - 1] + cum[kk] + (kk + 1) / 30.0 * (ir[q] - cum[-1])
            X = np.where((taus - 1 >= 0) & (taus - 1 < ff.N), lc[c][np.clip(taus - 1, 0, ff.N - 1)], np.nan)
            P = (X - e.beta * LV - e.alpha - e.mu) / e.sigma
        if GAPS:                                                          # classify every stored gap event: which minutes of the 601 are NaN in the rebuilt path
            nanpos = np.flatnonzero(~np.isfinite(P))
            gap_tab.append((r, len(nanpos), bool(len(nanpos) and nanpos[0] == 0), bool(len(nanpos) == 1 and nanpos[0] == 0)))
            continue
        row = LB.iloc[r]
        gap = int(not np.isfinite(P).all())
        if gap != int(row.label_gap):
            bad.append((r, "label_gap", gap, row.label_gap)); continue
        ngap_ok += 1
        if gap:
            continue
        assert abs(P[0] - e.z) < 1e-9, (r, P[0], e.z)
        z = e.z
        move = -(P - z) * np.sign(z); need = abs(z)
        depth = move[1:].max(); hit = np.flatnonzero(move[1:] >= need); adv = np.flatnonzero(move[1:] <= -need); stop = np.flatnonzero(move[1:] <= -1.0)
        if len(hit) and (not len(stop) or hit[0] < stop[0]):
            out, gross = 1, move[1:][hit[0]]
        elif len(stop):
            out, gross = -1, move[1:][stop[0]]
        else:
            out, gross = 0, move[600]
        exp = {"depth_10h": depth, "reach_10h": float(depth >= need), "minutes_to_mu": (hit[0] + 1) if len(hit) else np.nan, "adverse": float(len(adv) > 0),
               "mfe_sigma": max(0.0, move[1:].max()), "mae_sigma": max(0.0, (-move[1:]).max()), "outcome_1p0": float(out), "gross_1p0": gross}
        for kx, v in exp.items():
            g = row[kx]
            nc += 1
            if (np.isnan(v) != np.isnan(g)) or (not np.isnan(v) and abs(v - g) > 1e-5):
                bad.append((r, kx, v, g))
        nlab += 1
    if GAPS:
        G_ = pd.DataFrame(gap_tab, columns=["r", "n_nan", "m0_nan", "m0_only"])
        print(f"[COIN GAP EVENTS] {len(G_)} coin events stored with label_gap = 1 (of {len(LB):,}): path NaN at m = 0 in {int(G_.m0_nan.sum())}; ONLY at m = 0 (one NaN minute, the trigger bar's bridge) in {int(G_.m0_only.sum())}; "
              f"NaN count median {G_.n_nan.median():.0f}, max {int(G_.n_nan.max())}; events with a NaN at m = 0 and more later: {int((G_.m0_nan & ~G_.m0_only).sum())}")
        return
    tag = "STORED benchmark (ir from the coin stats), label logic and bridging re-done" if stored else "independent benchmark"
    print(f"[REWALK coin {tag}] {len(pick)} events ({len(pick) - (0 if stored else 100)} with finite path): label_gap agrees on {ngap_ok}; {nlab} paths x 8 labels = {nc:,} comparisons; mismatches {len(bad)}  [{time.time() - t0:.0f}s]")
    for x in bad[:15]:
        print("   MISMATCH", x)
    assert not bad
    print(f"[REWALK coin {tag}] PASS")


if __name__ == "__main__":
    main()
