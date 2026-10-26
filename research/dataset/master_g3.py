"""HL-MASTER1 G3: pair and coin history, as-of t = 0. Features only; they read PAST LABELS, so the resolution rule below is the whole look-ahead defence.

    python -u research/dataset/master_g3.py > research/dataset/logs/master_g3.log

RESOLUTION. For an event i at bar label T_i (t0 = T_i + 30 min), a previous event j of the same series is RESOLVED at t0 iff  T_i - T_j >= 600 minutes  (its 1-minute outcome
path ends with the 1m close at T_j + 630 min <= t0 exactly when T_i - T_j >= 600; the boundary counts as resolved)  AND label_gap_j = 0. Events that are not resolved
are excluded from every outcome column (their TIMES are known, so they do count in n_prev_triggers, days_since_last_trigger and triggers_last_7d).
The outcome used is reach_10h (and minutes_to_mu). pair_triggers_true is never used.

COLUMNS (series = the pair for the pair unit; the coin for the coin unit):
  n_prev_triggers          all earlier events of the series (T_j < T_i)
  n_prev_resolved          the resolved ones
  prev_reach_raw           mean reach_10h of the resolved ones (NaN if none)
  prev_reach_shrunk        (sum reach + 20 g) / (n_resolved + 20), g = the AS-OF global rate = mean reach_10h over ALL resolved events of the unit at t0 (any series); NaN only
                           while no event of the unit is resolved yet
  global_reach_asof        g itself (context)
  last1_reach .. last5_reach   reach_10h of the last five resolved events, MOST RECENT FIRST (NaN if fewer)
  last5_mean               mean of those available (NaN if none)
  days_since_last_trigger  (T_i - T of the previous event of the series) in days, NaN if none (resolved or not)
  triggers_last_7d         earlier events with T_i - 7 d <= T_j < T_i
  prev_mean_minutes_to_mu  mean minutes_to_mu of the resolved events that reached mu (NaN if none)
  PAIR UNIT ONLY, for leg A and leg B (prefix a_, b_): coin_n_resolved, coin_reach_raw, coin_reach_shrunk  = the leg's coin-vs-market history from the COIN unit under the same
                           rule (g = the coin unit's as-of global rate); and coin_reach_shrunk_diff = a_ - b_ shrunk.
OUTPUT: research/datasets/master/work/{pair,coin}/g3.parquet
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths

WORK = os.path.join(paths.DATASETS, "master", "work")
RES_MIN, SHR, BIG = 600, 20.0, 10 ** 9
KEEP = ["n_prev_triggers", "n_prev_resolved", "prev_reach_raw", "prev_reach_shrunk", "global_reach_asof", "last1_reach", "last2_reach", "last3_reach", "last4_reach",
        "last5_reach", "last5_mean", "days_since_last_trigger", "triggers_last_7d", "prev_mean_minutes_to_mu"]


def minutes(t):
    return ((pd.to_datetime(t) - pd.Timestamp("1970-01-01")) // pd.Timedelta(minutes=1)).to_numpy().astype(np.int64)


class Hist:
    """Prefix structures over one unit's events, sorted by (series, T)."""

    def __init__(self, series_code, T, reach, mtm, gap):
        order = np.lexsort((T, series_code))
        self.order = order
        self.g = series_code[order].astype(np.int64)
        self.T = T[order]
        self.key = self.g * BIG + self.T
        assert np.all(np.diff(self.key) > 0), "two events of one series at the same minute"
        self.valid = (gap[order] == 0) & np.isfinite(reach[order])
        self.reach = np.where(self.valid, reach[order], 0.0)
        self.reached = self.valid & (self.reach > 0)
        self.mtm = np.where(self.reached, mtm[order], 0.0)
        zi, zf = np.zeros(1, np.int64), np.zeros(1)
        self.cv = np.concatenate([zi, np.cumsum(self.valid, dtype=np.int64)])          # cv[k] = valid among the first k sorted rows
        self.cr = np.concatenate([zf, np.cumsum(self.reach)])
        self.cn = np.concatenate([zi, np.cumsum(self.reached, dtype=np.int64)])
        self.cm = np.concatenate([zf, np.cumsum(self.mtm)])
        self.vpos = np.flatnonzero(self.valid)
        # as-of global rate: events sorted by their resolution time T + 600
        v = np.flatnonzero(self.valid)
        ro = np.argsort(self.T[v] + RES_MIN, kind="stable")
        self.g_times = (self.T[v] + RES_MIN)[ro]
        self.g_cum = np.cumsum(self.reach[v][ro])

    def global_rate(self, Tq):
        k = np.searchsorted(self.g_times, Tq, side="right")           # resolved: T_j + 600 <= T_q
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(k > 0, np.where(k > 0, self.g_cum[np.clip(k - 1, 0, None)], 0.0) / np.maximum(k, 1), np.nan), k

    def query(self, series_q, Tq, own=False):
        """History columns for queries (series, T_q). `own` = the queries are the unit's own events (n_prev counts strictly earlier)."""
        gq = series_q.astype(np.int64)
        lo = np.searchsorted(self.key, gq * BIG, side="left")
        p_all = np.searchsorted(self.key, gq * BIG + Tq, side="left")            # earlier events: T_j < T_q
        p_res = np.searchsorted(self.key, gq * BIG + Tq - RES_MIN, side="right")  # resolvable: T_j <= T_q - 600
        out = {}
        out["n_prev_triggers"] = (p_all - lo).astype(float)
        nres = self.cv[p_res] - self.cv[lo]
        out["n_prev_resolved"] = nres.astype(float)
        sr = self.cr[p_res] - self.cr[lo]
        with np.errstate(invalid="ignore", divide="ignore"):
            out["prev_reach_raw"] = np.where(nres > 0, sr / np.maximum(nres, 1), np.nan)
        g, _ = self.global_rate(Tq)
        out["global_reach_asof"] = g
        out["prev_reach_shrunk"] = (sr + SHR * g) / (nres + SHR)
        base = self.cv[p_res]
        for m in range(1, 6):
            ok = (self.cv[p_res] - m) >= self.cv[lo]
            pos = self.vpos[np.clip(base - m, 0, len(self.vpos) - 1)] if len(self.vpos) else np.zeros(len(gq), int)
            out[f"last{m}_reach"] = np.where(ok, self.reach[pos], np.nan)
        L5 = np.column_stack([out[f"last{m}_reach"] for m in range(1, 6)])
        with np.errstate(invalid="ignore"):
            out["last5_mean"] = np.where(np.isfinite(L5).any(1), np.nanmean(np.where(np.isfinite(L5), L5, np.nan), axis=1), np.nan)
        has_prev = p_all > lo
        prevT = self.T[np.clip(p_all - 1, 0, None)]
        out["days_since_last_trigger"] = np.where(has_prev, (Tq - prevT) / 1440.0, np.nan)
        p7 = np.searchsorted(self.key, gq * BIG + Tq - 7 * 1440, side="left")
        out["triggers_last_7d"] = (p_all - p7).astype(float)
        nreach = self.cn[p_res] - self.cn[lo]
        with np.errstate(invalid="ignore", divide="ignore"):
            out["prev_mean_minutes_to_mu"] = np.where(nreach > 0, (self.cm[p_res] - self.cm[lo]) / np.maximum(nreach, 1), np.nan)
        return out


def load(unit):
    d = os.path.join(WORK, unit)
    E = pd.read_parquet(os.path.join(d, "events.parquet"))
    LB = pd.read_parquet(os.path.join(d, "labels.parquet"))
    assert (E.event_id.to_numpy() == LB.event_id.to_numpy()).all()
    return E, LB


def build(unit):
    t0 = time.time()
    E, LB = load(unit)
    T = minutes(E.entry_time)
    reach = LB.reach_10h.to_numpy(float)
    mtm = LB.minutes_to_mu.to_numpy(float)
    gap = LB.label_gap.to_numpy()
    series = E.pair_index.to_numpy()
    H = Hist(series, T, reach, mtm, gap)
    cols = H.query(series, T, own=True)
    G = pd.DataFrame({k: v.astype(np.float32) for k, v in cols.items()})
    G = G[KEEP]
    if unit == "pair":
        Ec, Lc = load("coin")
        coin_code = pd.factorize(Ec.ticker_a)[0]
        cmap = dict(zip(Ec.ticker_a, coin_code))
        Hc = Hist(coin_code.astype(np.int64), minutes(Ec.entry_time), Lc.reach_10h.to_numpy(float), Lc.minutes_to_mu.to_numpy(float), Lc.label_gap.to_numpy())
        for side, col in (("a", "ticker_a"), ("b", "ticker_b")):
            code = E[col].map(cmap)
            known = code.notna().to_numpy()
            q = Hc.query(np.where(known, code, 0).astype(np.int64), T)
            for src, dst in (("n_prev_resolved", f"{side}_coin_n_resolved"), ("prev_reach_raw", f"{side}_coin_reach_raw"), ("prev_reach_shrunk", f"{side}_coin_reach_shrunk")):
                v = q[src].astype(float)
                v[~known] = np.nan
                G[dst] = v.astype(np.float32)
        G["coin_reach_shrunk_diff"] = (G.a_coin_reach_shrunk - G.b_coin_reach_shrunk).astype(np.float32)
    G.insert(0, "event_id", E.event_id.to_numpy())
    G.to_parquet(os.path.join(WORK, unit, "g3.parquet"), index=False)
    print(f"[G3 {unit}] {len(G):,} rows x {len(G.columns) - 1} columns  [{time.time() - t0:.0f}s]")
    for c in G.columns[1:]:
        v = G[c].to_numpy(float)
        print(f"  {c:<26} NaN {100 * np.isnan(v).mean():6.2f}%  median {np.nanmedian(v) if np.isfinite(v).any() else np.nan:+.4g}  p95 {np.nanpercentile(v, 95) if np.isfinite(v).any() else np.nan:+.4g}")
    assert (G.n_prev_resolved <= G.n_prev_triggers).all()
    assert ((G.prev_reach_raw.dropna() >= 0) & (G.prev_reach_raw.dropna() <= 1)).all()
    assert ((G.prev_reach_shrunk.dropna() >= 0) & (G.prev_reach_shrunk.dropna() <= 1)).all()
    return G


def main():
    for unit in ("coin", "pair"):
        build(unit)


if __name__ == "__main__":
    main()
