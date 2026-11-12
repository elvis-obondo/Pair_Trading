"""HL-VAULT1 Word report, PART B (planner brief 2026-11-12, user approved): probability vs distance, where winners and
losers start, timing, paths, costs vs distance, stability. Vault and test months side by side. ANALYSIS ONLY on existing
data: no model, filter or rule is chosen; the vault is open, so any |z| or p cut-off read off these tables is a hypothesis
for later, not a result. Distance from mu is |z| in sigma units, never price percent.

    python -u research/model/s1_vault_docx_partb.py > research/model/logs/s1/s1_vault_docx_partb.log

Writes research/model/logs/s1/s1_vault_docx_partb.json: a list of sections, each with pre-formatted tables, text and
chart paths. The renderer (s1_vault_docx_render.js, Part B block) only draws them. Every cell is printed by this script.

READS: the vault and test frames of s1_vault_docx_data.py (labels, p, calibrated p, picks, z, minutes_to_mu); the trade files
of the chosen runs; the cleaned 1-minute price files (logs/profit1/cleaned_vault, logs/profit1/cleaned) for the paths in D;
event geometry (beta, alpha, mu, sigma, z) through vault_loader / load_search_events. Nothing is simulated or refit.

DECISION RULES (fixed here before anything is run):
  P1  |z| buckets: edges [0, 2, 2.5, 3, 4, 5, inf) (as Part A of the report). A "winner" is a trade with net > 0 after fees and
      funding, a "loser" one with net <= 0; "win rate (mu)" is the share exiting at mu. Quintiles are by average rank over the
      stated population (ties share a bin).
  P2  Section A (probability vs distance), per period, for h in {2, 5, 10}: |z| distribution (mean, median, 10/25/75/90th
      percentile) of all events, of the Rule A picks q = 1%, 0.5%, 0.1%, and of the own top 1% by p_h; Pearson and Spearman
      correlation of p_h with |z| on all events and on the q=1% picks; p_h, calibrated p_h and actual reach_h by |z| bucket
      (all events and q=1% picks); 2D table: quintile of calibrated p_h over the q=1% picks x |z| bucket with n, reach within h,
      and for the traded picks (stop none, maker, max_open 10) n traded, win rate (mu), mean net per trade; the same 2D table
      over all events (n, reach within h). Calibrated p = the vault's 2 h / 5 h / 10 h maps; test: S1-H's per-fold maps.
  P3  Sections B-E run-level, for the run list RUNS (below), vault and test side by side: B winners vs losers |z| distribution;
      by |z| bucket, by coin (top / bottom 10 by total net, a trade counts for both of its coins), direction (short the spread
      when z > 0), entry hour of day (UTC, 3-hour blocks), day of week, week, p_cal_10h quintile (within the run's trades);
      concentration (net of the top 10 trades, top 5 coins, top 5 days, and each as a share of the run's total net).
      C hold time of winners vs losers (mean, median, quartiles, 90th percentile), histogram, exit reasons with hold time,
      winners' timing (<= 60 min, 60-300, > 300), net per hour held by |z| bucket. D paths (below). E gross, fees, funding,
      slippage, net per trade by |z| bucket and by |z| decile of the run's trades, fee share of gross, and the break-even |z|
      = the lowest decile edge from which every higher decile has a positive mean net (or "none").
  P4  Section C, event level (all events and q=1% picks): share of events reaching mu within 1, 2, 5, 10 h (minutes_to_mu
      <= 60/120/300/600 among events with reach_10h = 1), median minutes_to_mu of reachers, by |z| bucket and by calibrated
      p_h quintile (q=1% picks).
  P5  Section D paths, from the cleaned price files with the engine's own formula (compute_move_paths): P = (log pA - beta log pB
      - alpha - mu) / sigma, move = -(P - z) * sign(z); move[0] must be ~0 (asserted). For each traded event the window is the
      601 minutes from t0 - 1 min; the trade's exit_minute bounds the path. MAE (max adverse excursion) = -min(0, min move[1..exit]),
      MFE = max(0, max move[1..exit]), both in sigma; MAE in % of margin uses the approximation $ per sigma = sigma * notional /
      (1 + |beta|) (the engine splits notional 1 : |beta| across the legs); that approximation is validated against each
      trade's gross P&L at exit (median ratio and 10th / 90th percentile are printed and shown in the report). Worst |P| for a
      loser = |z| + MAE. Winners that first went against us: share with MAE >= 0.25, 0.5, 1, 2 sigma (these are the shares a stop at
      that distance would have cut).
      PASS RULE for the approximation (fixed before the run): the "% of margin" rows are KEPT only if, for every one of the 18
      run/period pairs (9 runs x vault/test), the median ratio is within 0.9 to 1.1 AND the 10th and 90th percentiles are within 0.7
      to 1.3. Otherwise the "% of margin" rows are dropped everywhere and only sigma is shown; the report states which happened.
      PATH CHECK (independent of the approximation): in the stop runs (0.5, 1, 2 sigma; engine rule move <= -stop), every trade
      with exit_reason == stop must have MAE >= stop and every other exit MAE < stop (tolerance 1e-9); violation counts are printed
      and must be zero. move_paths also asserts that the price label at each window start equals the intended minute.
  P6  Stability (F): for each pair of tables (vault, test) over the same groups, a flag is raised when (a) the sign of the
      headline metric differs for a group with n >= 30 on both sides, or (b) the Spearman correlation of group order with the
      metric has the opposite sign on the two sides with |rho| >= 0.5 on both. Flags are listed with the table name; no
      judgement is attached. Each comparison (one vault/test table pair over the same groups) is one "table checked"; the number
      of tables checked and of tables flagged are printed and put in the section text, since some flags are expected by chance.
  RUNS: open10: q1% / none / maker, q1% / none / taker, q0.5% / none / maker, q0.1% / none / maker, q1% with stops 0.5, 1, 2
      (maker); open20: q1% / none / maker and taker. Vault tag vault_open10 / vault_open20, test tag base / open20.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
assert os.environ.get("PROFIT1_VAULT", "") != "1", "PROFIT1_VAULT must be unset"
import harness as H  # noqa: E402
import s1_profit1_horizons as HZ  # noqa: E402
import s1_vault_docx_data as DD  # noqa: E402 -- frames, TAGS, ZB edges
import s1_vault_report as VR  # noqa: E402
import vault_loader as VL  # noqa: E402

LOG_DIR, TRADE_DIR = DD.LOG_DIR, DD.TRADE_DIR
OUT_JSON = os.path.join(LOG_DIR, "s1_vault_docx_partb.json")
CHART_DIR = DD.CHART_DIR
ZE, ZL = DD.ZB_EDGES, DD.ZB_LABELS
HORIZ = (2, 5, 10)
QS = DD.QS
RUNS = [(10, 0.01, "none", "maker"), (10, 0.01, "none", "taker"), (10, 0.005, "none", "maker"), (10, 0.001, "none", "maker"),
        (10, 0.01, "0p5", "maker"), (10, 0.01, "1p0", "maker"), (10, 0.01, "2p0", "maker"),
        (20, 0.01, "none", "maker"), (20, 0.01, "none", "taker")]
SUFFIX = {("vault", 10): "_vault_open10", ("vault", 20): "_vault_open20", ("test", 10): "", ("test", 20): "_open20"}
MIN_N = 30


def log(m):
    print(m, flush=True)


STOP_NAME = {"none": "no stop", "0p5": "stop 0.5 sigma", "1p0": "stop 1 sigma", "2p0": "stop 2 sigma"}


def pretty(q, stop, fee):
    return f"q {q * 100:g}% / {STOP_NAME[stop]} / {fee} fees"


def f4(x, d=4):
    return "n/a" if x is None or (isinstance(x, (float, np.floating)) and not np.isfinite(x)) else f"{x:.{d}f}"


def f0(x):
    return "n/a" if x is None else f"{int(x):,}"


def P(x, d=1):
    return "n/a" if x is None or (isinstance(x, (float, np.floating)) and not np.isfinite(x)) else f"{100 * x:.{d}f}%"


def table(title, columns, rows, note=None):
    return dict(title=title, columns=columns, rows=[[str(c) for c in r] for r in rows], note=note)


def quint(x):
    return HZ.quintile(np.asarray(x, dtype=float))


def zb(z):
    return pd.cut(pd.Series(np.abs(np.asarray(z, dtype=float))), ZE, right=False, labels=ZL)


def pctiles(x):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return [None] * 6
    return [float(x.mean()), float(np.median(x))] + [float(v) for v in np.quantile(x, [0.10, 0.25, 0.75, 0.90])]


def spearman(a, b):
    a, b = pd.Series(np.asarray(a, dtype=float)), pd.Series(np.asarray(b, dtype=float))
    return float(a.rank().corr(b.rank()))


# ---------------------------------------------------------------------------
# stability flags (P6)
# ---------------------------------------------------------------------------
FLAGS = []
CHECKED = []
GROUP_ABS = {"gap": [], "usd": []}      # |mean| of eligible groups, both periods pooled, by metric family
FLAG_ABS = {"gap": [], "usd": []}       # same, groups flagged for opposite sign


def flag(name, vault, test, nv=None, nt=None):
    """vault / test: ordered dicts group -> metric; nv / nt: dict group -> n."""
    msgs = []
    CHECKED.append(name)
    kind = "gap" if name.startswith("A:") else "usd"
    for g in vault:
        if g in test and vault[g] is not None and test[g] is not None:
            if nv is None or (nv.get(g, 0) >= MIN_N and nt.get(g, 0) >= MIN_N):
                GROUP_ABS[kind] += [abs(vault[g]), abs(test[g])]
                if np.sign(vault[g]) != np.sign(test[g]) and vault[g] != 0 and test[g] != 0:
                    msgs.append(f"group {g}: vault {vault[g]:.4f}, test {test[g]:.4f} (opposite sign)")
                    FLAG_ABS[kind] += [abs(vault[g]), abs(test[g])]
    common = [g for g in vault if g in test and vault[g] is not None and test[g] is not None]
    if len(common) >= 4:
        order = np.arange(len(common))
        rv, rt = spearman(order, [vault[g] for g in common]), spearman(order, [test[g] for g in common])
        if np.isfinite(rv) and np.isfinite(rt) and abs(rv) >= 0.5 and abs(rt) >= 0.5 and np.sign(rv) != np.sign(rt):
            msgs.append(f"trend over the group order has opposite signs: vault rho {rv:.2f}, test rho {rt:.2f}")
    for m in msgs:
        FLAGS.append(f"{name}: {m}")
    return msgs


# ---------------------------------------------------------------------------
# Section A / C-event: per period, on the event frames
# ---------------------------------------------------------------------------
def section_a(df, trades_maker, period):
    tabs = []
    absz = df["z"].abs().to_numpy()
    sets = [("all events", np.ones(len(df), bool))] + [(f"Rule A picks q={q}", df[f"pick_{q}"].to_numpy()) for q in QS]
    for h in HORIZ:
        top = DD.VR.top_k_mask(df[f"p_{h}h"].to_numpy(), 0.01, np.random.default_rng(DD.SEED + h))
        sets_h = sets + [(f"own top 1% by p_{h}h", top)]
        rows = [[lab, f0(m.sum())] + [f4(v, 3) for v in pctiles(absz[m])] for lab, m in sets_h]
        tabs.append(table(f"{period}: |z| (sigma) of the high-p events, p_{h}h", ["set", "n", "mean", "median", "10th pct", "25th pct", "75th pct", "90th pct"], rows))
    rows = []
    q1 = df["pick_0.01"].to_numpy()
    for h in HORIZ:
        p = df[f"p_{h}h"].to_numpy()
        rows.append([f"p_{h}h", f4(np.corrcoef(p, absz)[0, 1], 3), f4(spearman(p, absz), 3), f4(np.corrcoef(p[q1], absz[q1])[0, 1], 3), f4(spearman(p[q1], absz[q1]), 3)])
    tabs.append(table(f"{period}: correlation of p_h with |z|", ["", "Pearson (all events)", "Spearman (all events)", "Pearson (q=1% picks)", "Spearman (q=1% picks)"], rows))
    bz = zb(df["z"]).to_numpy()
    for h in HORIZ:
        rows, store = [], {}
        for lab, m in (("all events", np.ones(len(df), bool)), ("q=1% picks", q1)):
            for b in ZL:
                mm = m & (bz == b)
                if mm.sum() == 0:
                    continue
                sub = df[mm]
                rows.append([lab, b, f0(mm.sum()), f4(sub[f"p_{h}h"].mean()), f4(sub[f"cal_{h}h"].mean()), f4(sub[f"reach_{h}h"].mean())])
                store[(lab, b)] = (sub[f"reach_{h}h"].mean() - sub[f"cal_{h}h"].mean(), len(sub))
        tabs.append(table(f"{period}: p_{h}h, calibrated p_{h}h and actual reach within {h} h, by |z| bucket", ["set", "|z| bucket", "n", "mean raw p", "mean calibrated p", "actual reach"], rows))
    for h in HORIZ:
        picks = df[q1].copy()
        picks["qt"] = quint(picks[f"cal_{h}h"])
        picks["zb"] = zb(picks["z"]).to_numpy()
        tr = trades_maker
        rows = []
        for qn in range(1, 6):
            for b in ZL:
                s = picks[(picks["qt"] == qn) & (picks["zb"] == b)]
                if len(s) == 0:
                    continue
                t = tr.loc[tr.index.intersection(s["event_id"].to_numpy())]
                rows.append([qn, b, f0(len(s)), f4(s[f"reach_{h}h"].mean()), f0(len(t)), P(float((t["exit_reason"] == "mu").mean()), 1) if len(t) else "n/a",
                             f4(t["net"].mean(), 3) if len(t) else "n/a"])
        tabs.append(table(f"{period}: q=1% picks, quintile of calibrated p_{h}h x |z| bucket", ["p quintile", "|z| bucket", "n picks", f"reach within {h} h", "n traded (maker, no stop, open10)", "win rate (mu)", "mean net $ / trade"], rows,
                          note="Quintile 1 is the lowest calibrated p."))
        al = df.copy()
        al["qt"] = quint(al[f"cal_{h}h"])
        al["zb"] = bz
        rows = []
        for qn in range(1, 6):
            for b in ZL:
                s = al[(al["qt"] == qn) & (al["zb"] == b)]
                if len(s):
                    rows.append([qn, b, f0(len(s)), f4(s[f"reach_{h}h"].mean())])
        tabs.append(table(f"{period}: ALL events, quintile of calibrated p_{h}h x |z| bucket", ["p quintile", "|z| bucket", "n events", f"reach within {h} h"], rows))
    return tabs


def section_c_events(df, period):
    tabs = []
    reach = df["reach_10h"].to_numpy() == 1
    mtm = df["minutes_to_mu"].to_numpy()
    q1 = df["pick_0.01"].to_numpy()

    def curve(m):
        n = int(m.sum())
        r = m & reach
        vals = [float((r & (mtm <= x)).sum() / n) if n else None for x in (60, 120, 300, 600)]
        med = float(np.median(mtm[r & ~np.isnan(mtm)])) if (r & ~np.isnan(mtm)).any() else None
        return n, vals, med
    rows = []
    for lab, m in (("all events", np.ones(len(df), bool)), ("q=1% picks", q1)):
        n, v, med = curve(m)
        rows.append([lab, f0(n)] + [P(x, 2) for x in v] + [f4(med, 0)])
    tabs.append(table(f"{period}: time to reach mu, all events and q=1% picks", ["set", "n", "within 1 h", "within 2 h", "within 5 h", "within 10 h", "median minutes (reachers)"], rows))
    bz = zb(df["z"]).to_numpy()
    rows, store = [], {}
    for lab, mm in (("all events", np.ones(len(df), bool)), ("q=1% picks", q1)):
        for b in ZL:
            m = mm & (bz == b)
            if m.sum():
                n, v, med = curve(m)
                rows.append([lab, b, f0(n)] + [P(x, 2) for x in v] + [f4(med, 0)])
    tabs.append(table(f"{period}: time to reach mu, by |z| bucket", ["set", "|z| bucket", "n", "within 1 h", "within 2 h", "within 5 h", "within 10 h", "median minutes (reachers)"], rows))
    for h in HORIZ:
        picks = df[q1]
        qt = quint(picks[f"cal_{h}h"])
        mt = picks["minutes_to_mu"].to_numpy()
        rc = picks["reach_10h"].to_numpy() == 1
        rows = []
        for qn in range(1, 6):
            m = qt == qn
            n = int(m.sum())
            vals = [float((m & rc & (mt <= x)).sum() / n) if n else None for x in (60, 120, 300, 600)]
            ok = m & rc & ~np.isnan(mt)
            rows.append([qn, f0(n)] + [P(x, 2) for x in vals] + [f4(float(np.median(mt[ok])), 0) if ok.any() else "n/a"])
        tabs.append(table(f"{period}: q=1% picks, time to reach mu by quintile of calibrated p_{h}h", ["p quintile", "n", "within 1 h", "within 2 h", "within 5 h", "within 10 h", "median minutes (reachers)"], rows))
    return tabs


# ---------------------------------------------------------------------------
# paths (P5)
# ---------------------------------------------------------------------------
def move_paths(event_ids, geo, t0s, price_dir):
    n = len(event_ids)
    VA, VB = np.full((n, 601), np.nan), np.full((n, 601), np.nan)
    ta, tb = geo["ticker_a"].to_numpy(), geo["ticker_b"].to_numpy()
    start = np.array([np.datetime64(pd.Timestamp(t).tz_convert("UTC").tz_localize(None) - pd.Timedelta(minutes=1), "m") for t in t0s])
    for coin in sorted(set(ta) | set(tb)):
        df = pd.read_parquet(os.path.join(price_dir, "price", f"{coin}.parquet"), columns=["label", "log_close"])
        labels = df["label"].to_numpy().astype("datetime64[m]")
        lo = labels[0]
        price = df["log_close"].to_numpy(float)
        for leg, arr, V in (("a", ta, VA), ("b", tb, VB)):
            for i in np.where(arr == coin)[0]:
                off = int((start[i] - lo) / np.timedelta64(1, "m"))
                assert off >= 0 and off + 601 <= len(price), f"{coin}: window out of range for event {event_ids[i]}"
                assert labels[off] == start[i], f"{coin}: label at offset {off} is {labels[off]}, intended {start[i]} (event {event_ids[i]})"
                assert labels[off + 600] == start[i] + np.timedelta64(600, "m"), f"{coin}: gap inside the window of event {event_ids[i]}"
                V[i] = price[off:off + 601]
    assert not np.isnan(VA).any() and not np.isnan(VB).any(), "a path window has a NaN"
    beta, alpha, mu, sigma, z = (geo[c].to_numpy(float) for c in ("beta", "alpha", "mu", "sigma", "z"))
    Pm = (VA - beta[:, None] * VB - alpha[:, None] - mu[:, None]) / sigma[:, None]
    s = np.where(z >= 0, 1.0, -1.0)
    move = -(Pm - z[:, None]) * s[:, None]
    assert np.abs(move[:, 0]).max() < 1e-6, f"move[0] not ~0: {np.abs(move[:, 0]).max()}"
    return move


def traded_event_set(period, runs):
    ids = set()
    for (mo, q, stop, fee) in runs:
        t = pd.read_parquet(os.path.join(TRADE_DIR, f"trades_q{q}_stop{stop}_fee{fee}{SUFFIX[(period, mo)]}.parquet"), columns=["event_id"])
        ids |= set(t["event_id"].to_numpy())
    return sorted(ids)


# ---------------------------------------------------------------------------
# run level (B, C, D, E)
# ---------------------------------------------------------------------------
def run_tables(t, z_by, move_by, geo_by, period, label, stop_name):
    t = t.copy()
    t["z"] = z_by.reindex(t["event_id"]).to_numpy()
    assert not t["z"].isna().any()
    t["absz"] = t["z"].abs()
    t["zb"] = zb(t["z"]).to_numpy()
    t["win"] = t["net"] > 0
    t["fees"] = t["entry_fee"] + t["exit_fee"]
    t["slip"] = t["entry_slip"] + t["exit_slip"]
    t["fund"] = t["funding_paid"] - t["funding_received"]
    t["dirn"] = np.where(t["z"] > 0, "short spread (z>0)", "long spread (z<0)")
    tot = float(t["net"].sum())
    tabs = {"B": [], "C": [], "D": [], "E": []}
    store = {}
    share = lambda x: P(x / tot, 1) if tot != 0 else "n/a"

    # B
    rows = []
    for lab, m in (("winners (net > 0)", t["win"]), ("losers (net <= 0)", ~t["win"]), ("all trades", np.ones(len(t), bool))):
        s = t[m]
        rows.append([lab, f0(len(s))] + [f4(v, 3) for v in pctiles(s["absz"])])
    tabs["B"].append(table(f"{label}: |z| of winners vs losers", ["", "n", "mean |z|", "median", "10th pct", "25th pct", "75th pct", "90th pct"], rows))
    rows, vs, ns = [], {}, {}
    for b in ZL:
        s = t[t["zb"] == b]
        if len(s) == 0:
            continue
        rows.append([b, f0(len(s)), P(len(s) / len(t)), P(float(s["win"].mean())), P(float((s["exit_reason"] == "mu").mean())), f4(s["net"].mean(), 3), f4(s["net"].sum(), 2), share(s["net"].sum())])
        vs[b], ns[b] = float(s["net"].mean()), len(s)
    tabs["B"].append(table(f"{label}: by |z| bucket", ["|z|", "trades", "share of trades", "win rate (net>0)", "win rate (mu)", "mean net $", "total net $", "share of run net"], rows))
    store["z_net"] = (vs, ns)
    rows = []
    for b in ["short spread (z>0)", "long spread (z<0)"]:
        s = t[t["dirn"] == b]
        rows.append([b, f0(len(s)), P(float(s["win"].mean())) if len(s) else "n/a", f4(s["net"].mean(), 3) if len(s) else "n/a", f4(s["net"].sum(), 2), share(s["net"].sum())])
    tabs["B"].append(table(f"{label}: by direction", ["direction", "trades", "win rate (net>0)", "mean net $", "total net $", "share of run net"], rows))
    t["hour_block"] = (t["t0"].dt.hour // 3 * 3).astype(int)
    for col, name, order in (("hour_block", "entry hour of day (UTC, 3-hour blocks)", sorted(t["hour_block"].unique())),
                             ("dow", "day of week of entry", list(range(7))), ("week", "week of entry (Monday)", None)):
        if col == "dow":
            t["dow"] = t["t0"].dt.dayofweek
        if col == "week":
            t["week"] = t["t0"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
        rows, vs, ns = [], {}, {}
        groups = order if order is not None else sorted(t[col].unique())
        for g in groups:
            s = t[t[col] == g]
            if len(s) == 0:
                continue
            rows.append([g, f0(len(s)), P(float(s["win"].mean())), f4(s["net"].mean(), 3), f4(s["net"].sum(), 2), share(s["net"].sum())])
            vs[str(g)], ns[str(g)] = float(s["net"].mean()), len(s)
        tabs["B"].append(table(f"{label}: by {name}", ["group", "trades", "win rate (net>0)", "mean net $", "total net $", "share of run net"], rows))
        store[col] = (vs, ns)
    t["pq"] = quint(t["p_cal_10h"])
    rows, vs, ns = [], {}, {}
    for qn in range(1, 6):
        s = t[t["pq"] == qn]
        if len(s) == 0:
            continue
        rows.append([qn, f"{s['p_cal_10h'].min():.4f} to {s['p_cal_10h'].max():.4f}", f0(len(s)), P(float(s["win"].mean())), P(float((s["exit_reason"] == "mu").mean())), f4(s["net"].mean(), 3), f4(s["net"].sum(), 2)])
        vs[str(qn)], ns[str(qn)] = float(s["net"].mean()), len(s)
    tabs["B"].append(table(f"{label}: by p_cal_10h quintile (within this run's trades)", ["quintile", "p_cal_10h range", "trades", "win rate (net>0)", "win rate (mu)", "mean net $", "total net $"], rows))
    store["pq"] = (vs, ns)
    legs = pd.concat([t[["ticker_a", "net", "win"]].rename(columns={"ticker_a": "coin"}), t[["ticker_b", "net", "win"]].rename(columns={"ticker_b": "coin"})])
    cg = legs.groupby("coin").agg(n=("net", "size"), total=("net", "sum"), win=("win", "mean")).sort_values("total", ascending=False)
    rows = [[c, f0(r.n), f4(r.total, 2), P(float(r.win))] for c, r in pd.concat([cg.head(10), cg.tail(10)]).iterrows()]
    tabs["B"].append(table(f"{label}: top 10 and bottom 10 coins by total net (a trade counts for both of its coins)", ["coin", "trades", "total net $", "win rate (net>0)"], rows))
    day = t.groupby(t["t0"].dt.floor("D"))["net"].sum().sort_values(ascending=False)
    top10_trades = float(t["net"].nlargest(10).sum())
    top5_coins = float(cg["total"].head(5).sum())
    top5_days = float(day.head(5).sum())
    rows = [["total net of the run", f4(tot, 2), "100.0%" if tot else "n/a"],
            ["top 10 trades", f4(top10_trades, 2), share(top10_trades)],
            ["top 5 coins (each trade counts for both coins, so these can add to more than the run total)", f4(top5_coins, 2), share(top5_coins)],
            ["top 5 days", f4(top5_days, 2), share(top5_days)],
            ["run net without the top 10 trades", f4(tot - top10_trades, 2), share(tot - top10_trades)]]
    tabs["B"].append(table(f"{label}: concentration of net PnL", ["", "net $", "share of run net"], rows))

    # C
    hold = t["holding_minutes"].to_numpy(float)
    rows = []
    for lab, m in (("winners", t["win"]), ("losers", ~t["win"]), ("all", np.ones(len(t), bool))):
        h = hold[np.asarray(m)]
        q = np.quantile(h, [0.25, 0.5, 0.75, 0.9]) if len(h) else [None] * 4
        rows.append([lab, f0(len(h)), f4(h.mean(), 1) if len(h) else "n/a"] + [f4(v, 0) for v in q])
    tabs["C"].append(table(f"{label}: hold time (minutes) of winners vs losers", ["", "trades", "mean", "25th pct", "median", "75th pct", "90th pct"], rows))
    edges = [0, 30, 60, 120, 180, 300, 450, 601]
    labs = ["<30", "30-60", "60-120", "120-180", "180-300", "300-450", "450-600"]
    cw = np.histogram(hold[t["win"].to_numpy()], bins=edges)[0]
    cl = np.histogram(hold[~t["win"].to_numpy()], bins=edges)[0]
    tabs["C"].append(table(f"{label}: histogram of hold time (minutes)", ["minutes held", "winners", "losers"], [[a, f0(b), f0(c)] for a, b, c in zip(labs, cw, cl)]))
    rows = []
    for r_, s in t.groupby("exit_reason"):
        rows.append([r_, f0(len(s)), P(len(s) / len(t)), f4(s["holding_minutes"].mean(), 1), f4(s["holding_minutes"].median(), 0), f4(s["net"].mean(), 3), f4(s["net"].sum(), 2)])
    tabs["C"].append(table(f"{label}: exit reasons", ["exit reason", "trades", "share", "mean hold min", "median hold min", "mean net $", "total net $"], rows))
    w = t[t["win"]]
    rows = []
    for lab, m in (("<= 60 min", w["holding_minutes"] <= 60), ("60-300 min", (w["holding_minutes"] > 60) & (w["holding_minutes"] <= 300)), ("> 300 min", w["holding_minutes"] > 300)):
        rows.append([lab, f0(int(m.sum())), P(float(m.mean())) if len(w) else "n/a", f4(w.loc[m, "net"].sum(), 2), P(float(w.loc[m, "net"].sum() / w["net"].sum())) if len(w) else "n/a"])
    tabs["C"].append(table(f"{label}: when winners win", ["winner exits within", "winners", "share of winners", "their net $", "share of winners' net"], rows))
    rows = []
    for b in ZL:
        s = t[t["zb"] == b]
        if len(s):
            rows.append([b, f0(len(s)), f4(s["holding_minutes"].sum() / 60, 1), f4(s["net"].sum(), 2), f4(s["net"].sum() / (s["holding_minutes"].sum() / 60), 4)])
    tabs["C"].append(table(f"{label}: net per hour held, by |z| bucket", ["|z|", "trades", "hours held", "total net $", "net $ per hour held"], rows))

    # D
    idx = np.array([move_by["pos"][e] for e in t["event_id"]])
    mv = move_by["move"][idx]
    em = t["exit_minute"].to_numpy(int)
    mae = np.array([max(0.0, -mv[i, 1:em[i] + 1].min()) for i in range(len(t))])
    mfe = np.array([max(0.0, mv[i, 1:em[i] + 1].max()) for i in range(len(t))])
    sig, bet = geo_by["sigma"].reindex(t["event_id"]).to_numpy(float), geo_by["beta"].reindex(t["event_id"]).to_numpy(float)
    dollar_per_sigma = sig * t["notional"].to_numpy(float) / (1 + np.abs(bet))
    approx_gross = mv[np.arange(len(t)), em] * dollar_per_sigma
    ok = np.abs(t["gross_pnl"].to_numpy()) > 1e-9
    ratio = approx_gross[ok] / t["gross_pnl"].to_numpy()[ok]
    val = [float(np.quantile(ratio, 0.5)), float(np.quantile(ratio, 0.1)), float(np.quantile(ratio, 0.9))]
    stop_d = {"none": np.inf, "0p5": 0.5, "1p0": 1.0, "2p0": 2.0}[stop_name]
    viol = None
    if np.isfinite(stop_d):
        is_stop = (t["exit_reason"] == "stop").to_numpy()
        viol = [int((is_stop & (mae < stop_d - 1e-9)).sum()), int((~is_stop & (mae > stop_d + 1e-9)).sum()), int(is_stop.sum()), int((~is_stop).sum())]
    mae_pct = mae * dollar_per_sigma / t["margin"].to_numpy(float)
    mfe_pct = mfe * dollar_per_sigma / t["margin"].to_numpy(float)
    t["mae"], t["mfe"], t["mae_pct"], t["mfe_pct"] = mae, mfe, mae_pct, mfe_pct
    rows = []
    for lab, m in (("winners", t["win"]), ("losers", ~t["win"])):
        s = t[m]
        for nm, col, fm in (("MAE (sigma)", "mae", lambda v: f4(v, 3)), ("MAE (% of margin)", "mae_pct", lambda v: P(v, 1)), ("MFE (sigma)", "mfe", lambda v: f4(v, 3)), ("MFE (% of margin)", "mfe_pct", lambda v: P(v, 1))):
            q = np.quantile(s[col], [0.5, 0.75, 0.9]) if len(s) else [None] * 3
            rows.append([lab, nm, f0(len(s)), fm(s[col].mean()) if len(s) else "n/a"] + [fm(v) if v is not None else "n/a" for v in q] + [fm(s[col].max()) if len(s) else "n/a"])
    tabs["D"].append(table(f"{label}: adverse and favourable excursion before the exit", ["", "measure", "trades", "mean", "median", "75th pct", "90th pct", "max"], rows,
                           note=f"% of margin uses the approximation $ per sigma = sigma x notional / (1 + |beta|); validation against each trade's gross P&L at exit: median ratio {val[0]:.3f}, 10th pct {val[1]:.3f}, 90th pct {val[2]:.3f} (1.000 = exact)."))
    tabs["D"][-1]["pct_rows"] = True
    ws = t[t["win"]]
    rows = []
    for thr in (0.25, 0.5, 1.0, 2.0):
        rows.append([f">= {thr} sigma", f0(int((ws["mae"] >= thr).sum())), P(float((ws["mae"] >= thr).mean())) if len(ws) else "n/a", f4(ws.loc[ws["mae"] >= thr, "net"].sum(), 2), P(float(ws.loc[ws["mae"] >= thr, "net"].sum() / ws["net"].sum())) if len(ws) else "n/a"])
    tabs["D"].append(table(f"{label}: winners that first went against us (a stop at this distance would have cut them)", ["adverse excursion", "winners", "share of winners", "their net $", "share of winners' net"], rows))
    ls = t[~t["win"]]
    rows = []
    for nm, v in (("MAE (sigma past entry)", ls["mae"]), ("MAE as a multiple of entry |z|", ls["mae"] / ls["absz"]), ("worst |P| = entry |z| + MAE (sigma from mu)", ls["absz"] + ls["mae"])):
        q = np.quantile(v, [0.5, 0.75, 0.9]) if len(ls) else [None] * 3
        rows.append([nm, f0(len(ls)), f4(v.mean(), 3) if len(ls) else "n/a"] + [f4(x, 3) if x is not None else "n/a" for x in q] + [f4(v.max(), 3) if len(ls) else "n/a"])
    tabs["D"].append(table(f"{label}: how far losers kept diverging", ["measure", "losers", "mean", "median", "75th pct", "90th pct", "max"], rows))

    # E
    def cost_rows(groups, names):
        rows, vs, ns = [], {}, {}
        for g, nm in zip(groups, names):
            s = t[g]
            if len(s) == 0:
                continue
            gross = s["gross_pnl"].sum()
            rows.append([nm, f0(len(s)), f4(s["gross_pnl"].mean(), 3), f4(s["fees"].mean(), 3), f4(s["fund"].mean(), 3), f4(s["slip"].mean(), 3), f4(s["net"].mean(), 3),
                         P(float(s["fees"].sum() / gross)) if gross != 0 else "n/a"])
            vs[nm], ns[nm] = float(s["net"].mean()), len(s)
        return rows, vs, ns
    head = ["group", "trades", "mean gross $", "mean fees $", "mean funding (paid - received) $", "mean slippage $", "mean net $", "fee share of gross"]
    rows, vs, ns = cost_rows([t["zb"] == b for b in ZL], ZL)
    tabs["E"].append(table(f"{label}: gross, costs and net per trade by |z| bucket", head, rows))
    store["E_z"] = (vs, ns)
    t["zdec"] = pd.qcut(t["absz"].rank(method="first"), 10, labels=False)
    edges_dec = [float(t.loc[t["zdec"] == d, "absz"].min()) for d in range(10)]
    names = [f"decile {d + 1} (|z| from {edges_dec[d]:.2f})" for d in range(10)]
    rows, vs, ns = cost_rows([t["zdec"] == d for d in range(10)], names)
    tabs["E"].append(table(f"{label}: gross, costs and net per trade by |z| decile of this run's trades", head, rows))
    mean_net_dec = [float(t.loc[t["zdec"] == d, "net"].mean()) for d in range(10)]
    be = None
    for d in range(10):
        if all(v > 0 for v in mean_net_dec[d:]):
            be = d
            break
    be_txt = f"|z| from {edges_dec[be]:.2f} (decile {be + 1} upward all have a positive mean net)" if be is not None else "none (the top decile's mean net is not positive)"
    tabs["E"].append(table(f"{label}: break-even |z| (descriptive)", ["", "value"], [["lowest |z| decile edge from which every higher decile has a positive mean net", be_txt]]))
    return tabs, store, val, viol


def main():
    t0 = time.time()
    log(f"[PARTB] sha256 s1_vault_docx_partb.py {VR.sha256(__file__)}; start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC")
    vdf, tdf = DD.vault_frame(), DD.test_frame()
    sections, validation = [], {}
    z_v, z_t = vdf.set_index("event_id")["z"], tdf.set_index("event_id")["z"]
    tr_v = DD.vault_trades_for_horizons()
    tr_t = DD.test_trades_for_horizons()
    # ---- A
    secA = dict(heading="Part B-A. Probability versus distance", level=1, intro="Distance from mu is |z| in sigma units. Calibrated p is the isotonic-corrected probability (vault: the vault maps; test months: S1-H's per-fold maps). Descriptive only: any |z| or p cut-off read off these tables is a hypothesis for later, not a result.",
                tables=[], images=[], flags=[])
    for per, df, tr in (("Vault", vdf, tr_v[(0.01, "maker")]), ("Test months", tdf, tr_t[(0.01, "maker")])):
        secA["tables"] += section_a(df, tr, per)
        log(f"[PARTB] section A {per}: {len(secA['tables'])} tables so far")
    # stability for A: actual - calibrated by |z| bucket (q=1% picks), per h
    for h in HORIZ:
        def gap_by_bucket(df):
            q1 = df["pick_0.01"].to_numpy()
            bz = zb(df["z"]).to_numpy()
            out, n = {}, {}
            for b in ZL:
                m = q1 & (bz == b)
                if m.sum():
                    out[b] = float(df.loc[m, f"reach_{h}h"].mean() - df.loc[m, f"cal_{h}h"].mean())
                    n[b] = int(m.sum())
            return out, n
        (gv, nv), (gt, nt) = gap_by_bucket(vdf), gap_by_bucket(tdf)
        secA["flags"] += flag(f"A: actual reach minus calibrated p_{h}h by |z| bucket (q=1% picks)", gv, gt, nv, nt)
    sections.append(secA)
    secC = dict(heading="Part B-C (events). Time to reach mu", level=1, intro="Events that reach mu within 10 h, timed from the label minutes_to_mu; share reaching within 1, 2, 5, 10 h.", tables=[], images=[], flags=[])
    for per, df in (("Vault", vdf), ("Test months", tdf)):
        secC["tables"] += section_c_events(df, per)
    sections.append(secC)
    log(f"[PARTB] event sections done [{time.time()-t0:.0f}s]")

    # ---- run level
    geo_v = VL.load_vault_events(columns=["ticker_a", "ticker_b", "beta", "alpha", "mu", "sigma", "z"]).reset_index(drop=True).set_index("event_id")
    geo_t = H.load_search_events(columns=["ticker_a", "ticker_b", "beta", "alpha", "mu", "sigma", "z"])
    move_cache = {}
    for per, runs_set in (("vault", traded_event_set("vault", RUNS)), ("test", traded_event_set("test", RUNS))):
        geo = (geo_v if per == "vault" else geo_t).loc[runs_set]
        base = vdf if per == "vault" else tdf
        t0s = base.set_index("event_id").loc[runs_set, "t0"].to_numpy()
        pdir = os.path.join(TRADE_DIR, "cleaned_vault" if per == "vault" else "cleaned")
        move = move_paths(np.array(runs_set), geo, t0s, pdir)
        move_cache[per] = dict(pos={e: i for i, e in enumerate(runs_set)}, move=move, geo=geo)
        log(f"[PARTB] paths {per}: {len(runs_set):,} traded events, move[0] check passed [{time.time()-t0:.0f}s]")
    pair_store = {}
    path_viol = []
    for (mo, q, stop, fee) in RUNS:
        key = f"q{q}_stop{stop}_fee{fee}"
        pk = pretty(q, stop, fee)
        sec = dict(heading=f"Part B-run: {pk}, max_open {mo}", level=1, intro="Vault first, then the test months for the same configuration. B = winners and losers by |z|, coin, direction, time, p_cal; C = hold time; D = paths; E = costs.", tables=[], images=[], flags=[])
        for per in ("vault", "test"):
            t = pd.read_parquet(os.path.join(TRADE_DIR, f"trades_{key}{SUFFIX[(per, mo)]}.parquet"))
            z_by = z_v if per == "vault" else z_t
            mc = move_cache[per]
            tabs, store, val, viol = run_tables(t, z_by, mc, mc["geo"], per, f"{'Vault' if per == 'vault' else 'Test months'}, {pk}, open{mo}", stop)
            if viol is not None:
                log(f"[PARTB] PATH CHECK {per} {key} open{mo}: stop exits {viol[2]:,} with MAE below the stop {viol[0]}; other exits {viol[3]:,} with MAE above the stop {viol[1]}")
                path_viol.append((per, key, mo, viol))
            pair_store[(key, mo, per)] = store
            validation[f"{per}_{key}_open{mo}"] = val
            log(f"[PARTB] {per} {key} open{mo}: {len(t):,} trades; $-per-sigma approximation ratio median {val[0]:.3f} (10th {val[1]:.3f}, 90th {val[2]:.3f})")
            for sec_letter in ("B", "C", "D", "E"):
                sec["tables"] += tabs[sec_letter]
        sv, st = pair_store[(key, mo, "vault")], pair_store[(key, mo, "test")]
        for k, name in (("z_net", "mean net $ by |z| bucket"), ("dow", "mean net $ by day of week"), ("hour_block", "mean net $ by entry hour block"), ("pq", "mean net $ by p_cal_10h quintile"), ("E_z", "mean net $ by |z| bucket (cost table)")):
            sec["flags"] += flag(f"{pk} open{mo}: {name}", sv[k][0], st[k][0], sv[k][1], st[k][1])
        sections.append(sec)
        log(f"[PARTB] run {key} open{mo} done [{time.time()-t0:.0f}s]")
    assert path_viol and all(v[3][0] == 0 and v[3][1] == 0 for v in path_viol), f"PATH CHECK violations: {path_viol}"
    log(f"[PARTB] PATH CHECK passed: {len(path_viol)} stop runs, zero violations of the engine's stop rule")
    # approximation pass rule (P5)
    bad = [(k, v) for k, v in validation.items() if not (0.9 <= v[0] <= 1.1 and 0.7 <= v[1] and v[2] <= 1.3)]
    pct_kept = not bad
    log(f"[PARTB] APPROXIMATION RULE: {len(validation)} run/period pairs; {len(bad)} outside (median 0.9-1.1, 10th >= 0.7, 90th <= 1.3) -> % of margin rows {'KEPT' if pct_kept else 'DROPPED'}")
    for k, v in bad:
        log(f"[PARTB]   outside: {k}: median {v[0]:.3f}, 10th {v[1]:.3f}, 90th {v[2]:.3f}")
    lo_ = min(v[1] for v in validation.values()); hi_ = max(v[2] for v in validation.values())
    for sec_ in sections:
        for tb in sec_["tables"]:
            if tb.pop("pct_rows", False):
                if pct_kept:
                    tb["note"] += f" Pass rule met in all {len(validation)} run/period pairs (median 0.9-1.1, 10th-90th pct 0.7-1.3; observed range of the 10th pct {lo_:.3f}, of the 90th pct {hi_:.3f})."
                else:
                    tb["rows"] = [r for r in tb["rows"] if "% of margin" not in r[1]]
                    tb["note"] = (f"The dollar-per-sigma approximation failed its pass rule in {len(bad)} of {len(validation)} run/period pairs (rule: median 0.9-1.1 and 10th-90th pct 0.7-1.3 in every pair; observed 10th pct as low as {lo_:.3f}, "
                                  f"90th pct as high as {hi_:.3f}), so the '% of margin' rows are dropped and only sigma is shown.")
    # charts: |z| distribution and hold-time histograms for the primary run
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    for per, df in (("vault", vdf), ("test months", tdf)):
        ax[0].hist(df.loc[df["pick_0.01"], "z"].abs(), bins=np.arange(0, 8, 0.25), alpha=0.5, density=True, label=f"{per}, q=1% picks")
        ax[0].hist(df["z"].abs(), bins=np.arange(0, 8, 0.25), histtype="step", density=True, label=f"{per}, all events")
    ax[0].set_xlabel("|z| (sigma)"); ax[0].set_ylabel("density"); ax[0].legend(fontsize=6)
    for per in ("vault", "test"):
        t = pd.read_parquet(os.path.join(TRADE_DIR, f"trades_q0.01_stopnone_feemaker{SUFFIX[(per, 10)]}.parquet"))
        ax[1].hist(t.loc[t["net"] > 0, "holding_minutes"], bins=np.arange(0, 640, 30), alpha=0.5, density=True, label=f"{per} winners")
        ax[1].hist(t.loc[t["net"] <= 0, "holding_minutes"], bins=np.arange(0, 640, 30), histtype="step", density=True, label=f"{per} losers")
    ax[1].set_xlabel("minutes held (q 1%, no stop, maker, open10)"); ax[1].legend(fontsize=6)
    fig.tight_layout()
    os.makedirs(CHART_DIR, exist_ok=True)
    chart = os.path.join(CHART_DIR, "partb_distance_and_hold.png")
    fig.savefig(chart, dpi=120)
    plt.close(fig)
    sections[0]["images"].append(chart)
    med = lambda a: float(np.median(a)) if len(a) else float("nan")
    stat_txt = (" A flag means only that the sign of a group's mean differs between the two periods (or that the group-order trends have opposite signs). "
                f"Median absolute group mean over the groups with a flag (both periods pooled) versus over all checked groups: probability gap (table family A) {med(FLAG_ABS['gap']):.4f} versus {med(GROUP_ABS['gap']):.4f} "
                f"({len(FLAG_ABS['gap']) // 2} flagged of {len(GROUP_ABS['gap']) // 2} groups); mean net $ per trade (run tables) {med(FLAG_ABS['usd']):.4f} versus {med(GROUP_ABS['usd']):.4f} ({len(FLAG_ABS['usd']) // 2} flagged of {len(GROUP_ABS['usd']) // 2} groups).")
    log("[PARTB] FLAG STATS:" + stat_txt)
    stab = dict(heading="Part B-F. Stability: patterns present in one period but not the other", level=1,
                intro=f"{len(CHECKED)} vault/test table pairs were checked and {sum(1 for c in CHECKED if any(f.startswith(c + ':') for f in FLAGS))} raised at least one flag ({len(FLAGS)} flag lines in all). Some flags are expected by chance across this many checks.{stat_txt} Flags raised by a fixed rule (opposite sign of the headline metric for a group with at least 30 trades or events on both sides, or opposite-signed trends over the group order with |rho| >= 0.5 on both sides). No judgement is attached; an empty list means none of the checked tables raised a flag.",
                tables=[], images=[], flags=FLAGS)
    sections.append(stab)
    json.dump(dict(sections=sections, validation=validation, runs=[list(r) for r in RUNS], script_sha256=VR.sha256(__file__)), open(OUT_JSON, "w"), indent=1, default=str)
    n_tab = sum(len(s["tables"]) for s in sections)
    nflag_tabs = sum(1 for c in CHECKED if any(f.startswith(c + ':') for f in FLAGS))
    log(f"[PARTB] {len(sections)} sections, {n_tab} tables, stability: {len(CHECKED)} tables checked, {nflag_tabs} flagged, {len(FLAGS)} flag lines")
    for fl in FLAGS:
        log(f"[PARTB] FLAG: {fl}")
    log(f"[PARTB] wrote {OUT_JSON} (sha256 {VR.sha256(OUT_JSON)})  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
