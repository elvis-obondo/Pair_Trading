"""HL-MASTER1 integrity item 9: known-answer events. The 2025-10-10 crash day and three other days (2025-07-15, 2026-03-01, 2026-09-15), TWO pair events each: every group's non-NaN values are printed, and a set of
hand checks recomputes headline columns straight from the raw sources, writing the difference. What was checked is recorded in the log.

    python -u research/dataset/master_known.py > research/dataset/logs/master_known.log

Events: on each day the pair event whose entry (t0 = entry + 30 min) is closest to 12:00 UTC, and the one closest to 21:00 UTC (the crash hour on 2025-10-10), ties by event_id.
HAND CHECKS per event (all from the raw 1-minute closes, flow table and l2 daily table, not from the master tables):
  1. geometry: z recomputed from the leg closes at the 1m close labelled T + 29 = (log A - beta log B - alpha - mu) / sigma; |diff| to events.z
  2. labels: the 601-minute path; depth_10h = max move over minutes 1..600; reach_10h = depth >= |z|; minutes_to_mu; compared with labels.parquet
  3. G4: a_log_price = log close at o - 1
  4. G5: a_imb_60 = s (B - S) / (B + S) of leg A's taker buy / sell over the 60 minutes before t0 (push sign s = d); compared with g5_a
  5. G9a: ret_btc_1h = log BTC close at o-1 minus at o-61
  6. G8: spread_bp and bid_d10 of leg A from the raw l2 row labelled o-1 (when the daily table is on this machine); compared with g8
"""
import os, sys, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
sys.path.insert(0, HERE)
import paths
import flowfeat as ff
import evmarket as em
import master_g5 as G5
import master_g8 as G8

WORK = os.path.join(paths.DATASETS, "master", "work", "pair")
DAYS = ["2025-10-10", "2025-07-15", "2026-03-01", "2026-09-15"]


def row_of(fname, eid_row_ix):
    t = pq.read_table(os.path.join(WORK, fname)).slice(eid_row_ix, 1).to_pandas()
    return t.iloc[0]


def main():
    t0 = time.time()
    E = pd.read_parquet(os.path.join(WORK, "events.parquet"))
    t0ts = pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30)
    files = sorted(f for f in os.listdir(WORK) if f.endswith(".parquet"))
    LC = {}
    def lc(c):
        if c not in LC:
            LC[c] = em.load_lc(c)
        return LC[c]
    n_ok = n_all = 0
    for day in DAYS:
        sel = np.flatnonzero((t0ts.dt.strftime("%Y-%m-%d") == day).to_numpy())
        if len(sel) == 0:
            print(f"[KNOWN] {day}: no events"); continue
        picks = []
        for hh in (12, 21):
            tgt = pd.Timestamp(f"{day} {hh}:00")
            d = np.abs((t0ts.iloc[sel] - tgt).dt.total_seconds().to_numpy())
            picks.append(int(sel[np.lexsort((E.event_id.iloc[sel].to_numpy(), d))[0]]))
        for r in dict.fromkeys(picks):
            e = E.iloc[r]
            o = int(ff.minute_index(t0ts.iloc[r:r + 1])[0])
            print("=" * 118)
            print(f"[KNOWN] {day}  event_id {int(e.event_id)}  row {r}  {e.ticker_a} / {e.ticker_b}  entry {e.entry_time}  t0 {t0ts.iloc[r]}  d {int(e.d)}  z {e.z:+.4f}  beta {e.beta:.4f}  sigma {e.sigma:.5f}")
            for f in files:
                if f in ("events.parquet",):
                    continue
                rw = row_of(f, r)
                if "event_id" in rw.index:
                    assert int(rw["event_id"]) == int(e.event_id), (f, "row misaligned")
                nz = {k: v for k, v in rw.items() if k != "event_id" and not (isinstance(v, float) and np.isnan(v)) and v is not None and not (isinstance(v, str) and v == "")}
                nnan = int(sum(isinstance(v, float) and np.isnan(v) for v in rw.values))
                print(f"  -- {f}: {len(nz)} values, {nnan} NaN")
                if f in ("g2b.parquet", "g3.parquet", "g4.parquet", "g9a.parquet", "labels.parquet", "g2.parquet", "g8.parquet", "g5_shape.parquet"):
                    print("     " + "; ".join(f"{k}={v:.5g}" if isinstance(v, (float, np.floating)) else f"{k}={v}" for k, v in nz.items()))
            la, lb = lc(e.ticker_a), lc(e.ticker_b)
            ok_checks = []
            # 1 geometry
            z_re = (la[o - 1] - e.beta * lb[o - 1] - e.alpha - e.mu) / e.sigma
            ok_checks.append(("geometry z", abs(z_re - e.z), 1e-3))
            # 2 labels
            path = (la[o - 1:o + 600] - e.beta * lb[o - 1:o + 600] - e.alpha - e.mu) / e.sigma
            L = row_of("labels.parquet", r)
            if np.isfinite(path).all():
                move = -(path - e.z) * np.sign(e.z)
                depth = move[1:601].max()
                hit = np.flatnonzero(move[1:601] >= abs(e.z))
                ok_checks.append(("label depth_10h", abs(depth - L.depth_10h), 1e-5))
                ok_checks.append(("label reach_10h", abs(float(depth >= abs(e.z)) - L.reach_10h), 0.5))
                ok_checks.append(("label minutes_to_mu", abs((hit[0] + 1 if len(hit) else np.nan) - L.minutes_to_mu) if len(hit) else (0.0 if np.isnan(L.minutes_to_mu) else 1e9), 0.5))
            else:
                ok_checks.append(("label_gap", abs(float(L.label_gap) - 1.0), 0.5))
            # 3 G4
            g4 = row_of("g4.parquet", r)
            ok_checks.append(("g4 a_log_price", abs(la[o - 1] - g4.a_log_price), 1e-5))
            # 4 G5 imbalance
            raw = G5.read_coin_raw(e.ticker_a)
            B, S = raw["taker_buy_usd"][o - 60:o], raw["taker_sell_usd"][o - 60:o]
            g5 = row_of("g5_a.parquet", r)
            if not (np.isnan(B).any() or np.isnan(S).any()) and B.sum() + S.sum() > 0:
                ok_checks.append(("g5 a_imb_60", abs(float(e.d) * (B.sum() - S.sum()) / (B.sum() + S.sum()) - g5.a_imb_60), 1e-4))
            # 5 G9a
            g9 = row_of("g9a.parquet", r)
            lbtc = lc("BTC")
            ok_checks.append(("g9a ret_btc_1h", abs((lbtc[o - 1] - lbtc[o - 61]) - g9.ret_btc_1h), 1e-5))
            # 6 G8
            m0 = G8.EM0 + o - 1
            p = os.path.join(paths.DATASETS, "l2", pd.Timestamp(m0 * 60, unit="s").strftime("%Y%m%d") + "_l2.parquet")
            if os.path.exists(p) and "g8.parquet" in files:
                D = pd.read_parquet(p)
                rr = D[(D.coin == e.ticker_a) & (D.minute == m0)]
                g8 = row_of("g8.parquet", r)
                if len(rr):
                    ok_checks.append(("g8 a_spread_bp", abs(rr.iloc[0].spread_bp - g8.a_spread_bp), 1e-3))
                    ok_checks.append(("g8 a_bid_d10", abs(rr.iloc[0].bid_d10 - g8.a_bid_d10), 1e-2 * max(1.0, abs(g8.a_bid_d10))))
                    ok_checks.append(("g8 snapshot_age_s", abs(60 - rr.iloc[0].snap_off_s - g8.a_snapshot_age_s), 1e-3))
                else:
                    ok_checks.append(("g8 row absent -> NaN", 0.0 if np.isnan(g8.a_spread_bp) else 1.0, 0.5))
            print("  HAND CHECKS (|recomputed from raw - stored|, tolerance):")
            for nm, diff, tol in ok_checks:
                n_all += 1
                good = bool(diff <= tol)
                n_ok += good
                print(f"     {'OK ' if good else 'BAD'} {nm:<24} diff {diff:.3g}  tol {tol:.3g}")
    print(f"\n[KNOWN] {n_ok} of {n_all} hand checks within tolerance  [{time.time() - t0:.0f}s]")
    assert n_ok == n_all, "a known-answer check failed"
    print("[KNOWN] PASS")


if __name__ == "__main__":
    main()
