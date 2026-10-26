"""HL-MASTER1 G7, open interest: the timestamp-lag check, the validation GATE, the gap-end drift, and the LEVEL path. Code first, nothing is run before the checker has seen it.

    python -u research/dataset/master_oi.py lag|gate|level > research/dataset/logs/master_oi_<stage>.log

INPUTS: asset_ctxs (research/datasets/ctxs/{YYYYMMDD}.parquet, one row per coin per snapshot; open_interest in COIN units) and the OI change from EVERY fill
(research/datasets/oi/{YYYYMMDD}_oi.parquet = build7_oi.py's output, pulled from s3://pair-trading-hl-289869684922/build7/oifull/): oi_delta_coin per (coin, minute).
Minute index m = flowfeat.minute_index (the window grid, 2025-05-25 14:32 on). A fill's minute is the minute of its time (floor).
CONVENTION: cd[k] = the sum of oi_delta over fill-minutes < k (labels 0..k-1), so a snapshot stamped m, which is the state AT m (the fills with time < m), is explained by cd[m] - cd[m_a]. The
expected answer of the lag stage is therefore L* = 0; an off-by-one in cd would show as L* = +-1 and must be caught, not fixed by the search: a two-fill synthetic test is asserted and printed before the table.
Snapshots whose stamp is not exactly on a minute (a late snapshot of build 1's kind) are DROPPED and counted; an hour mark without an observation drops its pair.

STAGE lag (B0-style, FIRST). Let obs[m] be the open_interest of the snapshot stamped at minute m (NaN where there is none) and cd[m] the cumulative sum of oi_delta_coin through minute m.
A snapshot stamped m may reflect the fills only up to minute m - L (a delay L >= 0 minutes; L < 0 would mean it reflects the future of its stamp: reported if it wins).
For L in -5..+10 and every pair of consecutive snapshots on the hour marks (m_a, m_b = m_a + 60, both observed, and no hole minute between): obsD = obs[m_b] - obs[m_a];
recD(L) = cd[m_b - L] - cd[m_a - L].  Pooled correlation of obsD and recD(L) over all coins and complete days, and the median absolute error / median |obsD|: the profile over L is printed; L* = argmax correlation.
STAGE gate (uses L*, only on days when asset_ctxs is complete: every hour mark present for the coin that day and the next 00:00): per coin-day, 24 hourly changes;
  corr_h = Pearson correlation of obsD and recD over the 24 hours (NaN if either is constant: counted as pass only if both are all zero);
  drift  = |sum recD - sum obsD| / mean(obs at the 25 marks);
  a coin-day PASSES if corr_h >= 0.99 AND drift < 0.005.  GATE: >= 95% of coin-days pass. Also printed: the pass share of each condition alone, by month, and the coins whose own pass share < 95% (the failing coins).
Gap drift: for each run of >= 2 consecutive missing hour marks of a coin (a real gap), at the gap's end: the level carried from the last observation before the gap,
  carried = obs[m_a] + cd[m_b - L] - cd[m_a - L], against the first observation after, relative to obs[m_b]; distribution printed. A failed gate STOPS the build (exit code 2): leave gap values NaN.
STAGE level (only if the gate passed; it passed with the units definition, master_oi_gate2.log): LEVEL path per coin per minute m:  OI(m) = obs[m_o] + UNITS x (cd[m - L*] - cd[m_o - L*])  (UNITS = 2: asset_ctxs units, gross of both sides), m_o = the last observed minute at or before m (anchored ONLY from the past; no later
observation corrects a path inside a gap). Minutes with a hole (build 2's 114 missing minutes) add no delta and are flagged. Outputs per coin (research/datasets/oi_level/{coin}.parquet):
oi_level_coin, mins_since_obs, in_gap (1 if mins_since_obs > 60). USD level and the event columns are built in master_g7.py from these.
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

CTX = os.path.join(paths.DATASETS, "ctxs")
OI = os.path.join(paths.DATASETS, "oi")
OUT = os.path.join(paths.DATASETS, "oi_level")
MISSING = os.path.join(ROOT, "research", "hyperliquid", "logs", "build5_missing_minutes.parquet")
UNITS = 2.0              # asset_ctxs open_interest = sum of |positions| (both sides) = 2 x one-sided OI; oi_delta in asset_ctxs units is sum(|p'| - |p|) = 2 x build7_oi.py's oi_delta_coin (planner 2026-10-25)
LAGS = list(range(-5, 11))
DROPPED = [0, 0]                        # snapshots dropped because their stamp is not exactly on the minute (a late snapshot already contains fills after the minute), total snapshots


def minutes(ts):
    t = pd.to_datetime(ts)
    if isinstance(t, pd.Series):
        t = t.dt.tz_localize(None) if t.dt.tz is not None else t
    elif getattr(t, "tz", None) is not None:
        t = t.tz_localize(None)
    return ff.minute_index(t)


def load_obs(coins=None):
    """obs[coin] = dense array of open_interest by minute (NaN where no snapshot)."""
    obs = {}
    for f in sorted(os.listdir(CTX)):
        if not f.endswith(".parquet") or f.startswith("_"):
            continue
        d = pd.read_parquet(os.path.join(CTX, f), columns=["time", "coin", "open_interest"])
        t_ = pd.to_datetime(d.time)
        on = ((t_.dt.second == 0) & (t_.dt.microsecond == 0) & (t_.dt.nanosecond == 0)).to_numpy()
        DROPPED[0] += int((~on).sum()); DROPPED[1] += len(d)
        d = d[on]
        m = minutes(d.time)
        ok = (m >= 0) & (m < ff.N)
        d = d[ok].assign(m=m[ok])
        for c, g in d.groupby(d.coin.astype(str)):
            if coins is not None and c not in coins:
                continue
            a = obs.setdefault(c, np.full(ff.N, np.nan))
            a[g.m.to_numpy()] = g.open_interest.to_numpy(float)          # the last snapshot of a minute wins
    return obs


def load_delta():
    """cd[coin] = cumulative oi_delta_coin by minute; hole minutes add nothing."""
    parts = {}
    for f in sorted(os.listdir(OI)):
        if not f.endswith("_oi.parquet"):
            continue
        d = pd.read_parquet(os.path.join(OI, f), columns=["coin", "minute", "oi_delta_coin"])
        m = minutes(d.minute)
        ok = (m >= 0) & (m < ff.N)
        d = d[ok].assign(m=m[ok])
        for c, g in d.groupby(d.coin.astype(str)):
            a = parts.setdefault(c, np.zeros(ff.N))
            np.add.at(a, g.m.to_numpy(), g.oi_delta_coin.to_numpy(float))
    return {c: np.concatenate([[0.0], np.cumsum(a)]) for c, a in parts.items()}      # cd[k] = sum of oi_delta over fill-minutes < k (length N + 1)


def hole_flags():
    h = pd.read_parquet(MISSING)
    h = h["minute"] if "minute" in h else h.iloc[:, 0]
    hm = minutes(h)
    cs = np.zeros(ff.N + 1)
    cs[hm + 1] += 1
    return np.cumsum(cs)


def synthetic_cd_test():
    d = np.zeros(30)
    d[10], d[11] = 5.0, 7.0
    cd = np.concatenate([[0.0], np.cumsum(d)])
    # the snapshot stamped 11 is the state at 11: it contains minute 10's fill but not minute 11's
    assert cd[11] - cd[10] == 5.0 and cd[12] - cd[11] == 7.0 and cd[10] - cd[9] == 0.0
    print("[OI CONVENTION] synthetic: fills at minutes 10 (+5) and 11 (+7): cd[11] - cd[10] = 5 (the snapshot stamped 11 contains the fill of minute 10, not that of minute 11); cd[12] - cd[11] = 7: PASS")


def stage_lag(obs, cd, holes):
    synthetic_cd_test()
    print(f"[OI] snapshots dropped because the stamp is not exactly on the minute: {DROPPED[0]:,} of {DROPPED[1]:,} ({100 * DROPPED[0] / max(DROPPED[1], 1):.3f}%)")
    print("[OI LAG] correlation of hourly observed OI change with the fills-based change, by assumed snapshot delay L (minutes)")
    res = {L: ([], []) for L in LAGS}
    for c, o in obs.items():
        if c not in cd:
            continue
        a_idx = np.flatnonzero(np.isfinite(o[:-60]) & np.isfinite(o[60:]))
        a_idx = a_idx[(a_idx - ff.CUT_PHASE) % 60 == 0]                         # hour marks (the grid starts at :32, so 28 minutes later is :00)
        a_idx = a_idx[(holes[a_idx + 61] - holes[a_idx]) == 0]                  # no hole minute in between
        for L in LAGS:
            ok = a_idx[(a_idx - L >= 0) & (a_idx + 60 - L < ff.N)]
            od = o[ok + 60] - o[ok]
            rd = cd[c][ok + 60 - L] - cd[c][ok - L]
            res[L][0].append(od); res[L][1].append(rd)
    best, rows = None, []
    for L in LAGS:
        od, rd = np.concatenate(res[L][0]), np.concatenate(res[L][1])
        r = np.corrcoef(od, rd)[0, 1]
        mae = np.median(np.abs(od - rd)) / max(np.median(np.abs(od)), 1e-12)
        rows.append((L, len(od), r, mae))
        if best is None or r > best[1]:
            best = (L, r)
    print(f"  {'L':>3}{'pairs':>12}{'corr':>10}{'median |err|/median |obs change|':>36}")
    for L, n, r, mae in rows:
        print(f"  {L:>3}{n:>12,}{r:>10.5f}{mae:>36.4f}")
    print(f"[OI LAG] L* = {best[0]} (correlation {best[1]:.5f})")
    if best[0] < 0:
        print("[OI LAG] STOP: L* < 0 means the snapshot contains fills AFTER its stamp; a level built on it would look ahead. Send the table to the reviewer before any level is built.")
        sys.exit(3)
    return best[0]


def stage_gate(obs, cd, holes, L):
    print(f"[OI GATE] L = {L}; coin-days complete when all 25 hour marks are observed and no hole minute lies in the day")
    rows = []
    for c, o in obs.items():
        if c not in cd:
            continue
        mark0 = np.flatnonzero(np.isfinite(o))
        if len(mark0) == 0:
            continue
        # day starts: minutes of 00:00 UTC
        d0 = pd.Timestamp("2025-05-25")
        day_starts = ff.minute_index(pd.date_range(d0, periods=int(ff.N / 1440) + 3, freq="D"))
        for ds in day_starts:
            marks = ds + 60 * np.arange(25)
            if marks[0] < 0 or marks[-1] >= ff.N:
                continue
            if not np.isfinite(o[marks]).all() or holes[marks[-1] + 1] - holes[marks[0]] != 0 or marks[0] - L < 0 or marks[-1] - L >= ff.N:
                continue
            od = np.diff(o[marks])
            rd = cd[c][marks[1:] - L] - cd[c][marks[:-1] - L]
            if od.std() == 0 or rd.std() == 0:
                corr = 1.0 if (np.all(od == 0) and np.all(rd == 0)) else np.nan
            else:
                corr = np.corrcoef(od, rd)[0, 1]
            drift = abs(rd.sum() - od.sum()) / max(np.mean(o[marks]), 1e-12)
            rows.append((c, ds, corr, drift))
    G = pd.DataFrame(rows, columns=["coin", "day_min", "corr", "drift"])
    G["month"] = (pd.Timestamp(ff.GRID0) + pd.to_timedelta(G.day_min, unit="m")).dt.to_period("M")
    G["pass_corr"] = G["corr"] >= 0.99
    G["pass_drift"] = G["drift"] < 0.005
    G["pass"] = G.pass_corr & G.pass_drift
    n = len(G)
    print(f"  coin-days evaluated: {n:,} over {G.coin.nunique()} coins")
    print(f"  pass: both {100 * G['pass'].mean():.2f}%; hourly correlation >= 0.99 alone {100 * G.pass_corr.mean():.2f}%; drift < 0.5% alone {100 * G.pass_drift.mean():.2f}%; "
          f"NaN correlation {100 * G['corr'].isna().mean():.2f}%")
    print("  by month (both): " + ", ".join(f"{k} {100 * v:.1f}%" for k, v in G.groupby("month")["pass"].mean().items()))
    pc = G.groupby("coin")["pass"].mean().sort_values()
    # diagnostics only: pooled-per-coin correlation, and coins whose median daily |observed hourly change| is below 0.1% of OI (quiet coins fail a 24-point correlation from noise)
    pooled = {}
    quiet = set()
    for c, g in G.groupby("coin"):
        od_all, rd_all, rel = [], [], []
        for ds in g.day_min:
            marks = ds + 60 * np.arange(25)
            od = np.diff(obs[c][marks]); rd = cd[c][marks[1:] - L] - cd[c][marks[:-1] - L]
            od_all.append(od); rd_all.append(rd); rel.append(np.median(np.abs(od)) / max(np.mean(obs[c][marks]), 1e-12))
        od_all, rd_all = np.concatenate(od_all), np.concatenate(rd_all)
        pooled[c] = np.corrcoef(od_all, rd_all)[0, 1] if od_all.std() > 0 and rd_all.std() > 0 else np.nan
        if np.median(rel) < 0.001:
            quiet.add(c)
    pooled = pd.Series(pooled)
    print(f"  DIAGNOSTIC pooled-per-coin hourly correlation: median {pooled.median():.5f}, 5% {pooled.quantile(.05):.5f}, min {pooled.min():.5f} ({pooled.idxmin()}); coins below 0.99: {int((pooled < 0.99).sum())}")
    isq = G.coin.isin(quiet)
    print(f"  DIAGNOSTIC quiet coins (median daily |hourly OI change| < 0.1% of OI): {len(quiet)} coins, {int(isq.sum()):,} coin-days; pass share quiet {100 * G['pass'][isq].mean():.2f}%, others {100 * G['pass'][~isq].mean():.2f}%; "
          f"corr alone quiet {100 * G.pass_corr[isq].mean():.2f}%, others {100 * G.pass_corr[~isq].mean():.2f}%")
    bad = pc[pc < 0.95]
    print(f"  coins with their own pass share < 95%: {len(bad)}: " + ", ".join(f"{c} {100 * v:.0f}%" for c, v in bad.head(40).items()))
    print(f"  drift quantiles 50/90/95/99%: " + " / ".join(f"{G.drift.quantile(q):.5f}" for q in (.5, .9, .95, .99)))
    ok = G["pass"].mean() >= 0.95
    print(f"[OI GATE] {'PASS' if ok else 'FAIL'}: {100 * G['pass'].mean():.2f}% of coin-days pass (needs >= 95%)")
    G.to_parquet(os.path.join(paths.DATASETS, "oi_gate_coin_days.parquet"), index=False)
    return ok


def stage_gaps(obs, cd, L):
    print("[OI GAP DRIFT] at the end of each real gap (>= 2 consecutive missing hour marks), the level carried from the last observation vs the first observation after")
    rel = []
    for c, o in obs.items():
        if c not in cd:
            continue
        idx = np.flatnonzero(np.isfinite(o))
        if len(idx) < 2:
            continue
        step = np.diff(idx)
        for k in np.flatnonzero(step > 120):
            a, b = idx[k], idx[k + 1]
            carried = o[a] + cd[c][b - L] - cd[c][a - L]
            rel.append((c, a, b, (carried - o[b]) / max(abs(o[b]), 1e-12), (b - a) / 60.0))
    R = pd.DataFrame(rel, columns=["coin", "m_a", "m_b", "rel_err", "gap_hours"])
    if len(R):
        print(f"  gaps: {len(R):,}; relative error |median| {R.rel_err.abs().median():.5f}, 90% {R.rel_err.abs().quantile(.9):.5f}, 99% {R.rel_err.abs().quantile(.99):.5f}; gap hours median {R.gap_hours.median():.1f}, max {R.gap_hours.max():.1f}")
        for lo, hi in ((2, 6), (6, 24), (24, 1e9)):
            s = R[(R.gap_hours >= lo) & (R.gap_hours < hi)]
            if len(s):
                print(f"    gaps of {lo}-{hi if hi < 1e8 else 'more'} h: {len(s):,}, median |error| {s.rel_err.abs().median():.5f}, 90% {s.rel_err.abs().quantile(.9):.5f}")
    R.to_parquet(os.path.join(paths.DATASETS, "oi_gap_drift.parquet"), index=False)


def level_path(o, cdc, L=0):
    """The reconstructed level of one coin: (level, last observed value, minutes since the observation) per minute. Pure: observations o (dense, NaN where none) and cd (length N + 1) in."""
    m = np.arange(len(o))
    last = np.maximum.accumulate(np.where(np.isfinite(o), m, -1))
    have = last >= 0
    lo = np.clip(last - L, 0, len(o) - 1)
    hi = np.clip(m - L, 0, len(o) - 1)
    level = np.where(have, o[np.clip(last, 0, None)] + UNITS * (cdc[hi] - cdc[lo]), np.nan)
    since = np.where(have, m - last, np.nan)
    obs_last = np.where(have, o[np.clip(last, 0, None)], np.nan)
    return level, obs_last, since


def stage_level(obs, cd, holes, L):
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for c, o in obs.items():
        if c not in cd:
            continue
        level, obs_last, since = level_path(o, cd[c], L)
        pd.DataFrame({"oi_level_coin": level.astype(np.float64), "oi_obs_last": obs_last.astype(np.float64), "mins_since_obs": since.astype(np.float32), "in_gap": (since > 60).astype(np.int8)}).to_parquet(
            os.path.join(OUT, f"{c}.parquet"), index=False)
        n += 1
    print(f"[OI LEVEL] {n} coins written to {OUT}; L* = {L}")


def main():
    stage = sys.argv[1]
    t0 = time.time()
    obs = load_obs()
    cd = load_delta()
    holes = hole_flags()
    print(f"[OI] observations for {len(obs)} coins, fills-based deltas for {len(cd)} coins  [{time.time() - t0:.0f}s]", flush=True)
    if stage == "lag":
        stage_lag(obs, cd, holes)
    else:
        L = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        if stage == "gate":
            ok = stage_gate(obs, cd, holes, L)
            stage_gaps(obs, cd, L)
            if not ok:
                sys.exit(2)
        elif stage == "level":
            stage_level(obs, cd, holes, L)
    print(f"  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
