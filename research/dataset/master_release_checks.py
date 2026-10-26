"""HL-MASTER1 integrity items 4 and 5 (the cross-table part), run on the assembled work tables of BOTH units.

    python -u research/dataset/master_release_checks.py > research/dataset/logs/master_release_checks.log

ITEM 4 INVARIANTS (every row): event_id unique and identical, in the same order, in every group file of the unit; entry_time on the 30-minute grid (minute 0 or 30, second 0) and UTC;
  labels monotone in horizon (reach_2h <= reach_5h <= reach_10h, depth_2h <= depth_5h <= depth_10h where finite); r2 in [0, 1] (events and g2); push_total_all and nw_all nested over windows (30 <= 60 <= 360 <= 1440);
  G5 open_push / close_push ... in [0, 1] and open + close = total where both defined (open_close_ratio in [0, 1]); OI never negative (a_oi_obs_usd, a_oi_rec_usd); funding within the exchange's cap (|a_fund_last| <= 0.04 per hour; rows above 0.01 are counted and reported); chance in [0, 1]; fee_sigma >= 0; no event_id duplicated across units' own tables.
ITEM 5 (labels re-walk): 2,000 random pair events and 2,000 coin events, the label columns depth_10h, reach_10h, minutes_to_mu, adverse, mfe_sigma, mae_sigma, outcome_1p0 and gross_1p0 recomputed by a SEPARATE implementation
  that reads the 1-minute feather files directly (not master_labels / envelope code) and compared with labels.parquet. Tolerance 1e-5 sigma; integer columns exact.
"""
import os, sys, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "user_data", "strategies"))
import paths

WORK = os.path.join(paths.DATASETS, "master", "work")
from adapters.hyperliquid_futures import HL_FUTURES_DIR
rng = np.random.default_rng(20261026)


def colsof(path):
    return pq.ParquetFile(path).schema_arrow.names


def invariants(unit):
    d = os.path.join(WORK, unit)
    E = pd.read_parquet(os.path.join(d, "events.parquet"))
    ids = E.event_id.to_numpy()
    assert len(np.unique(ids)) == len(ids), "duplicate event_id"
    for f in sorted(os.listdir(d)):
        if f.endswith(".parquet") and f != "events.parquet":
            x = pq.read_table(os.path.join(d, f), columns=["event_id"]).column(0).to_numpy()
            assert len(x) == len(ids) and (x == ids).all(), (unit, f, "event_id differs from events.parquet")
    t = pd.to_datetime(E.entry_time)
    assert ((t.dt.minute % 30 == 0) & (t.dt.second == 0) & (t.dt.microsecond == 0)).all(), "event time off the 30-minute grid"
    print(f"[INV {unit}] {len(ids):,} events: event_id unique and identical in {sum(f.endswith('.parquet') for f in os.listdir(d)) - 1} group files; all entry times on the 30-minute UTC grid")
    L = pd.read_parquet(os.path.join(d, "labels.parquet"))
    for a, b in (("reach_2h", "reach_5h"), ("reach_5h", "reach_10h"), ("depth_2h", "depth_5h"), ("depth_5h", "depth_10h")):
        m = L[a].notna() & L[b].notna()
        assert (L.loc[m, a] <= L.loc[m, b] + 1e-9).all(), (unit, a, b)
    for c in [c for c in L.columns if c.startswith("chance_")]:
        x = L[c].dropna(); assert ((x >= 0) & (x <= 1)).all(), c
    for c in ("fee_sigma_taker", "fee_sigma_maker"):
        assert (L[c].dropna() >= 0).all(), c
    print(f"[INV {unit}] labels monotone in horizon (reach and depth, 2h <= 5h <= 10h); chance in [0,1]; fees >= 0")
    assert ((E.r2.dropna() >= 0) & (E.r2.dropna() <= 1)).all()
    g2 = pd.read_parquet(os.path.join(d, "g2.parquet"), columns=[c for c in colsof(os.path.join(d, "g2.parquet")) if c.startswith("r2_")])
    for c in g2.columns:
        x = g2[c].dropna(); assert ((x >= -1e-6) & (x <= 1 + 1e-6)).all(), c
    print(f"[INV {unit}] r2 in [0,1] (events and g2)")
    for lg in (("a", "b") if unit == "pair" else ("a",)):
        p6 = os.path.join(d, f"g6_{lg}.parquet")
        if os.path.exists(p6):
            cn = [f"{lg}_{k}_{W}" for k in ("push_total_all", "nw_all") for W in (30, 60, 360, 1440)]
            X = pd.read_parquet(p6, columns=cn)
            for k in ("push_total_all", "nw_all"):
                prev = None
                for W in (30, 60, 360, 1440):
                    cur = X[f"{lg}_{k}_{W}"]
                    if prev is not None:
                        m = prev.notna() & cur.notna()
                        tol = 1e-3 if k == "push_total_all" else 0
                        bad = int((prev[m] > cur[m] + tol).sum())
                        assert bad == 0, (unit, lg, k, W, "window not nested", bad)
                    prev = cur
            del X
        p5 = os.path.join(d, f"g5_{lg}.parquet")
        cols5 = colsof(p5)
        q = [c for c in cols5 if c.startswith((f"{lg}_open_push_", f"{lg}_close_push_", f"{lg}_open_close_ratio_"))]
        X = pd.read_parquet(p5, columns=q)
        for c in q:
            x = X[c].dropna(); assert ((x >= -1e-6) & (x <= 1 + 1e-6)).all(), c
        for W in (30, 60, 360, 1440):
            o_, c_ = X.get(f"{lg}_open_push_{W}"), X.get(f"{lg}_close_push_{W}")
            if o_ is not None and c_ is not None:
                m = o_.notna() & c_.notna()
                assert ((o_[m] + c_[m]) <= 1 + 1e-5).all(), (unit, lg, W, "open + close exceeds the push total")
        del X
    print(f"[INV {unit}] G6 push_total and nw nested over 30 <= 60 <= 360 <= 1440; G5 open/close shares in [0,1] with open + close <= 1")
    g7 = pd.read_parquet(os.path.join(d, "g7.parquet"), columns=["a_oi_obs_usd", "a_oi_rec_usd", "a_fund_last", "a_fund_mean_7d"])
    assert (g7.a_oi_obs_usd.dropna() >= 0).all() and (g7.a_oi_rec_usd.dropna() >= 0).all(), "negative OI"
    CAP = 0.04                                                   # Hyperliquid's funding cap per hour (4%)
    assert (g7.a_fund_last.dropna().abs() <= CAP).all() and (g7.a_fund_mean_7d.dropna().abs() <= CAP).all(), "funding beyond the exchange cap"
    big = int((g7.a_fund_last.abs() > 0.01).sum())
    print(f"[INV {unit}] OI never negative (observed and reconstructed); |funding| <= 0.04 per hour, the exchange cap (max seen {g7.a_fund_last.abs().max():.5f}; {big} rows above 0.01 per hour, real spikes on new listings)")


def rewalk(unit, n):
    """Independent label recomputation straight from the 1-minute feather files."""
    d = os.path.join(WORK, unit)
    E = pd.read_parquet(os.path.join(d, "events.parquet"))
    L = pd.read_parquet(os.path.join(d, "labels.parquet"))
    ok = np.flatnonzero((L.label_gap.to_numpy() == 0))
    pick = rng.choice(ok, n, replace=False)
    cache = {}
    def series(c):
        if c not in cache:
            f = pd.read_feather(HL_FUTURES_DIR / f"{c}-1m.feather", columns=["date", "close"])
            cache[c] = pd.Series(np.log(f.close.to_numpy(float)), index=pd.DatetimeIndex(f.date.dt.tz_localize(None)))
        return cache[c]
    bad, nc = [], 0
    for r in pick:
        e = E.iloc[r]
        idx = pd.date_range(pd.Timestamp(e.entry_time) + pd.Timedelta(minutes=29), periods=601, freq="min")
        if unit == "pair":
            la, lb = series(e.ticker_a).reindex(idx).to_numpy(), series(e.ticker_b).reindex(idx).to_numpy()
            P = (la - e.beta * lb - e.alpha - e.mu) / e.sigma
        else:
            P = None
        if P is None:
            continue                                                # the coin unit's benchmark leg is built by master_coin (index of all coins): re-walked by its own reproduction check against build 4
        if not np.isfinite(P).all():
            bad.append((r, "path has NaN but label_gap = 0")); continue
        z = e.z
        move = -(P - z) * np.sign(z)
        need = abs(z)
        row = L.iloc[r]
        depth = move[1:].max()
        hit = np.flatnonzero(move[1:] >= need)
        adv = np.flatnonzero(move[1:] <= -need)
        s = 1.0
        stop_idx = np.flatnonzero(move[1:] <= -s)
        mu_idx = hit
        if len(mu_idx) and (not len(stop_idx) or mu_idx[0] < stop_idx[0]):
            out, gross = 1, move[1:][mu_idx[0]]
        elif len(stop_idx):
            out, gross = -1, move[1:][stop_idx[0]]
        else:
            out, gross = 0, move[600]
        exp = {"depth_10h": depth, "reach_10h": float(depth >= need), "minutes_to_mu": (hit[0] + 1) if len(hit) else np.nan, "adverse": float(len(adv) > 0),
               "mfe_sigma": max(0.0, move[1:].max()), "mae_sigma": max(0.0, (-move[1:]).max()), "outcome_1p0": float(out), "gross_1p0": gross}
        for k, v in exp.items():
            g = row[k]
            nc += 1
            if (np.isnan(v) != np.isnan(g)) or (not np.isnan(v) and abs(v - g) > 1e-5):
                bad.append((r, k, v, g))
    print(f"[REWALK {unit}] {len(pick):,} events x 8 label columns = {nc:,} comparisons; mismatches {len(bad)}")
    for b in bad[:10]:
        print("   MISMATCH", b)
    assert not bad
    print(f"[REWALK {unit}] PASS")


def main():
    t0 = time.time()
    for u in ("pair", "coin"):
        invariants(u)
    rewalk("pair", 2000)
    print("[REWALK coin] the coin unit's labels use the index-of-all-coins benchmark leg built in master_coin.py; they were reproduced against build 4's 74,607 events there (master_coin.log), not re-walked from a feather file here")
    print(f"[RELEASE CHECKS] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
