"""HL-MASTER1 integrity item 7: eyeball sample. 20 random pair events, stratified (long/short x early/late x reached/not reached), each plotted from RAW data with the key columns annotated: a plain matplotlib PNG per event.

    python -u research/dataset/master_eyeball.py > research/dataset/logs/master_eyeball.log
Strata: d (push direction of leg A: +1 / -1) x time (entry before / after the median entry date) x reach_10h (1 / 0) = 8 cells; 20 events = 3 per cell for four cells and 2 for four (fixed seed 20261026),
events with label_gap = 0 only (a path is needed). Panels: (1) the frozen-geometry spread path in sigma units from t0 - 6 h to t0 + 10 h (from the 1-minute closes) with the entry level z, mu (0) and the reach level;
(2) both legs' prices rebased to t0; (3) leg A's taker buy and sell USD per 5 minutes (raw flow table) with the push-side imbalance; text box with 25 key columns across the groups and the labels.
OUTPUT: research/dataset/logs/eyeball/event_<id>.png and an index in the log.
"""
import os, sys, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
sys.path.insert(0, HERE)
import paths
import flowfeat as ff
import evmarket as em
import master_g5 as G5

WORK = os.path.join(paths.DATASETS, "master", "work", "pair")
OUT = os.path.join(HERE, "logs", "eyeball")
KEY = {"g2.parquet": ["r2_7d", "phi_7d", "halflife_h", "vratio"], "g2b.parquet": ["z_sym", "z_ratio"], "g3.parquet": ["n_prev_triggers", "prev_reach_shrunk"],
       "g4.parquet": ["a_liq_rank_7d", "a_rv_24h"], "g5_a.parquet": ["a_imb_60", "a_forced_share_60", "a_volume_ratio_60"], "g6_a.parquet": ["a_top1_all_60", "a_nw_all_60", "a_vault_push_share_60"],
       "g7.parquet": ["a_fund_last", "a_oi_rec_chg_24h"], "g8.parquet": ["a_spread_bp", "a_bid_d10", "a_snapshot_age_s"], "g9a.parquet": ["ret_btc_1h", "rv_idx_24h"],
       "labels.parquet": ["reach_10h", "depth_10h", "minutes_to_mu", "outcome_1p0", "net_1p0_taker"]}


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    E = pd.read_parquet(os.path.join(WORK, "events.parquet"))
    L = pd.read_parquet(os.path.join(WORK, "labels.parquet"), columns=["event_id", "label_gap", "reach_10h"])
    assert (E.event_id.to_numpy() == L.event_id.to_numpy()).all()
    ok = (L.label_gap.to_numpy() == 0)
    when = pd.to_datetime(E.entry_time)
    late = (when > when.median()).to_numpy()
    cell = (E.d.to_numpy() > 0).astype(int) * 4 + late.astype(int) * 2 + (L.reach_10h.to_numpy() > 0.5).astype(int)
    rg = np.random.default_rng(20261026)
    pick = []
    for c in range(8):
        ix = np.flatnonzero(ok & (cell == c))
        k = 3 if c < 4 else 2
        pick += list(rg.choice(ix, k, replace=False))
    tabs = {f: pq.read_table(os.path.join(WORK, f), columns=["event_id"] + cols).to_pandas() for f, cols in KEY.items() if os.path.exists(os.path.join(WORK, f))}
    t0ts = when + pd.Timedelta(minutes=30)
    cache = {}
    def lc(c):
        if c not in cache:
            cache[c] = em.load_lc(c)
        return cache[c]
    for r in pick:
        e = E.iloc[r]
        o = int(ff.minute_index(t0ts.iloc[r:r + 1])[0])
        la, lb = lc(e.ticker_a), lc(e.ticker_b)
        rel = np.arange(-360, 601)
        ix = o - 1 + rel
        S = (la[ix] - e.beta * lb[ix] - e.alpha - e.mu) / e.sigma
        fig = plt.figure(figsize=(13, 9))
        ax1 = fig.add_axes([0.06, 0.60, 0.60, 0.33]); ax2 = fig.add_axes([0.06, 0.34, 0.60, 0.22], sharex=ax1); ax3 = fig.add_axes([0.06, 0.06, 0.60, 0.22], sharex=ax1)
        ax1.plot(rel / 60, S, lw=0.8)
        ax1.axhline(0, color="g", lw=0.8); ax1.axhline(e.z, color="r", lw=0.6, ls="--"); ax1.axvline(0, color="k", lw=0.8)
        ax1.set_ylabel("spread (sigma, frozen geometry)"); ax1.set_title(f"event {int(e.event_id)}  {e.ticker_a}/{e.ticker_b}  t0 {t0ts.iloc[r]}  z {e.z:+.2f}  beta {e.beta:.2f}  d {int(e.d):+d}")
        ax2.plot(rel / 60, np.exp(la[ix] - la[o - 1]), lw=0.8, label=e.ticker_a); ax2.plot(rel / 60, np.exp(lb[ix] - lb[o - 1]), lw=0.8, label=e.ticker_b); ax2.axvline(0, color="k", lw=0.8)
        ax2.legend(loc="upper left", fontsize=8); ax2.set_ylabel("price / price at t0")
        raw = G5.read_coin_raw(e.ticker_a)
        lo, hi = o - 360, o + 120
        mins = np.arange(lo, hi)
        buy = np.nan_to_num(raw["taker_buy_usd"][lo:hi]).reshape(-1, 5).sum(1)
        sell = np.nan_to_num(raw["taker_sell_usd"][lo:hi]).reshape(-1, 5).sum(1)
        x5 = (mins[::5] - (o - 1)) / 60
        ax3.bar(x5, buy, width=0.07, color="g", alpha=0.7, label="taker buy USD"); ax3.bar(x5, -sell, width=0.07, color="r", alpha=0.7, label="taker sell USD")
        ax3.axvline(0, color="k", lw=0.8); ax3.legend(loc="upper left", fontsize=8); ax3.set_ylabel("leg A flow per 5 min"); ax3.set_xlabel("hours from t0")
        lines = []
        for f, cols in KEY.items():
            if f in tabs:
                row = tabs[f].iloc[r]
                assert int(row.event_id) == int(e.event_id)
                lines.append(f"[{f[:-8]}] " + "  ".join(f"{c}={row[c]:.4g}" for c in cols))
        fig.text(0.68, 0.93, "\n\n".join(lines), va="top", fontsize=7.5, family="monospace", wrap=True)
        p = os.path.join(OUT, f"event_{int(e.event_id)}.png")
        fig.savefig(p, dpi=90)
        plt.close(fig)
        print(f"  event {int(e.event_id)}  cell d={int(e.d):+d} {'late' if late[r] else 'early'} reach={int(L.reach_10h.iloc[r])}  -> {p}")
    print(f"[EYEBALL] {len(pick)} events plotted  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
