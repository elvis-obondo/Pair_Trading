"""HL-VAULT1 Word report, PART C (planner brief 2026-11-12, user approved): ranking and decay, label versus trade,
independence and market exposure, risk, sizing and capacity, cost sensitivity (arithmetic only), live workload. ANALYSIS ONLY on
saved outputs (trade files, minute-equity files, skip files, cleaned prices, build2 1-minute cache, event labels). Vault and test
months side by side. No rule, filter or cut-off is chosen; no baselines, shuffles or permutation checks. No engine rerun, no AWS.

    python -u research/model/s1_vault_docx_partc.py > research/model/logs/s1/s1_vault_docx_partc.log

Writes research/model/logs/s1/s1_vault_docx_partc.json (sections of pre-formatted tables, same layout as Part B).

DECISION RULES (fixed here before anything is run):
  C1  Ranking and decay.
      (a) Deciles of the traded set of the primary runs (q 1% / no stop / maker, max_open 10 and 20; taker open10): signals
          p_cal_10h, calibrated p_5h, calibrated p_2h and EV. EV = p_cal_10h * mean net of mu-exit trades + (1 - p_cal_10h) * mean net
          of timeout trades, the two means taken from the TEST-month trades of the same configuration (search data, so no vault
          information enters the vault's EV; for the test months the means are the pooled test means, i.e. in-sample for that side).
          EV is an increasing linear function of p_cal_10h when the mu-exit mean exceeds the timeout mean (asserted), so its deciles
          equal p_cal_10h's; the table says so instead of repeating it. Per decile: n, mean signal, win rate (mu), win rate (net > 0),
          mean net $, mean net / notional, total net $. Spearman correlation of each signal with net / notional per trade.
      (b) Lift / gain curve over ALL events at top 0.1, 0.25, 0.5, 1, 2, 3, 4, 5, 7.5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100% by
          p_10h (ceil, seeded random tie-break; test: per fold, concatenated, as S1): n, reach within 10 h, chance, lift, share of all
          reachers captured.
      (c) Weekly lift and reliability: Rule A q=1% picks by Monday-start week (vault; test months too): n events, n picks, reach of picks,
          lift, mean p_cal_10h of picks and actual reach (pred vs actual); Spearman correlation of week order with weekly lift and with
          (actual - predicted) over weeks with >= 30 picks; first-half versus second-half pooled lift (weeks split at the median week).
  Receipt: the gain curve's top-1% lift is checked against s1_vault_report.json (own top 1%) and s1d_report.json (pooled 0.0841), tolerance 5e-4.
  C2  Label versus trade, per run of the Part B run list, h in {2, 5, 10}: of the traded events with reach_h = 1, the number with net > 0;
      reverted-but-lost trades by reason: stopped out first (exit reason stop), exit at mu but gross below fees + slippage, exit at mu with
      gross covering fees + slippage but funding turning net negative, other. Also the count of traded events with reach_h = 0 and net > 0.
      For the primary run, reverted-but-lost by |z| bucket.
  C3  Independence and market exposure: picks per day (q 1%, 0.5%, 0.1%: mean, median, 90th percentile, max, days with none); open trades per day
      (mean of the daily mean and max of n_open, from minute equity); trades per entry hour (mean, max, share of trades in the 10 busiest
      hours); clusters = connected components of trades linked when they share a coin and their [t0, exit] intervals overlap (union-find),
      reported as number of clusters, mean and largest size (a cluster count is an upper bound on independent bets, not an estimate of them).
      Market proxies (two, labelled): (1) BTC from user_data/normalized/BTC.feather (30-minute closes): market return = log of the last close of
      the UTC day over the previous day's last close; market volatility = std of the day's 30-minute log returns; every day of both PnL windows
      must be present (asserted). (2) the equal-weighted mean over the saved coins (cleaned price files; built only from coins the strategy
      picked, so partly selected by the strategy) of the same daily return and of the daily std of 1-minute log returns. Daily PnL (primary runs) by tercile of |market return| and of market volatility (terciles of the window's days): days, mean
      daily PnL, share of the run's net (for each proxy); Pearson and Spearman of daily PnL with market return, |market return| and volatility; net without the
      best day and without the best 3 days.
  C4  Risk (the daily-equity final value must equal the report's final equity, 1e-6, for every run), every one of the 24 runs per tag and period: daily PnL mean, std, t-stat (mean / (std / sqrt(n days))), worst and best day, longest run
      of losing days, deepest drawdown (daily equity) with its length and the days from its bottom to recovery, worst trade, longest run of losing
      trades (by exit time), peak gross exposure (sum of open notional, sweep of entry and exit times), peak margin and minimum distance to
      liquidation from the reports. For the primary runs: the 10 largest losing trades. The vault's losing configurations (final equity below
      $1,000): counts by q, stop and fee, and the same for the test months.
  C5  Sizing and capacity (primary runs): margin utilisation (margin used / account value: mean, median, 95th pct, max), share of minutes with
      n_open at the cap and at cap - 1, skips by reason; taken versus skipped picks (q 1% picks of the run): n, reach within 10 h, mean p_cal_10h,
      mean |z|, mean gross in sigma at a no-stop exit from the cleaned-price paths (first mu hit else minute 600), win-at-mu share; return
      on margin = total net / time-average margin used; leg notional (N/(1+|beta|) and N|beta|/(1+|beta|)) versus the coin's traded notional in the
      entry minute and versus its trailing 60-minute median (build2 1-minute cache, column notional): median, 90th and 99th pct, shares above 1%,
      5%, 10%; coin liquidity tiers = terciles of the coin's median daily traded notional over the window; a trade belongs to the tier of its
      less liquid leg; per tier: trades, win rate, mean net, total net, share of net, median ratio.
  C6  Cost sensitivity, arithmetic only on the saved trades: extra slippage s bp per fill (2 fills per trade) on the trade's notional, s in
      {0, 1, 2, 3, 5, 7.5, 10}: net PnL = sum(net) - 2 * s / 10,000 * sum(notional); break-even slippage = sum(net) / (2 * sum(notional)) in bp;
      maker share needed: lambda* = -net_taker / (net_maker - net_taker) clipped to [0, 1] when the two runs' totals straddle zero (net PnL = lambda
      * maker + (1 - lambda) * taker; the account path differs between the two runs, so this is an interpolation of totals, not a run); funding total
      and sign by direction.
  C7  Live workload (events and picks): picks per day, per UTC hour of day (mean per day), per timestamp (max, distribution), q 1%, 0.5%, 0.1%.
  Entry-delay (latency) sensitivity is NOT computed (needs an engine change); the report states what the saved prices allow.
  No stability-flag step in Part C (Part B owns F). Windows: vault anchor = VAULT_START day - 1, nominal end = day after the last pick;
  test anchor = fold-1 start day - 1, nominal end = fold-7 end (as s1_vault_docx_data.py). Market proxy needs prices for the saved coins only.
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
import s1_vault_docx_data as DD  # noqa: E402
import s1_vault_docx_partb as PB  # noqa: E402
import s1_vault_report as VR  # noqa: E402
import vault_loader as VL  # noqa: E402

LOG_DIR, TRADE_DIR = DD.LOG_DIR, DD.TRADE_DIR
OUT_JSON = os.path.join(LOG_DIR, "s1_vault_docx_partc.json")
BUILD2 = os.path.join(TRADE_DIR, "build2_1m_cache")
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BTC_FILE = os.path.join(ROOT, "user_data", "normalized", "BTC.feather")
table, f4, f0, P, quint, zb, spearman = PB.table, PB.f4, PB.f0, PB.P, PB.quint, PB.zb, PB.spearman
ZL = DD.ZB_LABELS
QS = DD.QS
PRIMARY = [(10, 0.01, "none", "maker"), (20, 0.01, "none", "maker"), (10, 0.01, "none", "taker")]
FRACS = [0.001, 0.0025, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
SLIPS = [0, 1, 2, 3, 5, 7.5, 10]
CHECK_FINAL = []
WIN = {}
CAP_STOPS = ("0p5", "1p0", "2p0", "none")


def log(m):
    print(m, flush=True)


def load_trades(per, mo, q, stop, fee):
    return pd.read_parquet(os.path.join(TRADE_DIR, f"trades_q{q}_stop{stop}_fee{fee}{PB.SUFFIX[(per, mo)]}.parquet"))


def load_me(per, mo, q, stop, fee):
    return pd.read_parquet(os.path.join(TRADE_DIR, f"minute_equity_q{q}_stop{stop}_fee{fee}{PB.SUFFIX[(per, mo)]}.parquet")).sort_values("time")


def load_skips(per, mo, q, stop, fee):
    return pd.read_parquet(os.path.join(TRADE_DIR, f"skips_q{q}_stop{stop}_fee{fee}{PB.SUFFIX[(per, mo)]}.parquet"))


def per_label(per):
    return "Vault" if per == "vault" else "Test months"


# ---------------------------------------------------------------------------
# C1
# ---------------------------------------------------------------------------
def c1_deciles(per, df, t, ev_coef):
    d = df.set_index("event_id")
    t = t.copy()
    t["cal_5h"] = d.loc[t["event_id"], "cal_5h"].to_numpy()
    t["cal_2h"] = d.loc[t["event_id"], "cal_2h"].to_numpy()
    t["ret"] = t["net"] / t["notional"]
    mu_m, to_m = ev_coef
    assert mu_m > to_m, "EV is not increasing in p_cal_10h"
    tabs = []
    rows_c = []
    for sig, name in (("p_cal_10h", "calibrated p_10h"), ("cal_5h", "calibrated p_5h"), ("cal_2h", "calibrated p_2h")):
        t["dec"] = pd.qcut(t[sig].rank(method="first"), 10, labels=False)
        rows = []
        for k in range(10):
            s = t[t["dec"] == k]
            rows.append([k + 1, f0(len(s)), f4(s[sig].mean()), P(float((s["exit_reason"] == "mu").mean())), P(float((s["net"] > 0).mean())), f4(s["net"].mean(), 3), f4(s["ret"].mean(), 5), f4(s["net"].sum(), 2)])
        tabs.append(table(f"{per_label(per)}: traded set by decile of {name}", ["decile (1 = lowest)", "trades", f"mean {name}", "win rate (mu)", "win rate (net>0)", "mean net $", "mean net / notional", "total net $"], rows))
        rows_c.append([name, f4(spearman(t[sig], t["ret"]), 4)])
    ev = t["p_cal_10h"] * mu_m + (1 - t["p_cal_10h"]) * to_m
    rows_c.append(["EV (mu-exit mean net $ %.4f, timeout mean net $ %.4f)" % (mu_m, to_m), f4(spearman(ev, t["ret"]), 4)])
    tabs.append(table(f"{per_label(per)}: Spearman correlation of the signal with net / notional per trade", ["signal", "rank correlation"], rows_c,
                      note="EV is an increasing linear function of calibrated p_10h here (asserted), so EV deciles are identical to the calibrated p_10h deciles above."))
    return tabs


def top_mask(p, frac, rng):
    return DD.VR.top_k_mask(p, frac, rng)


def gain_curve(df, per, rng):
    out, lifts = [], {}
    reach, chance = df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy()
    base_gap = reach.mean() - chance.mean()
    if per == "vault":
        blocks = [np.arange(len(df))]
    else:
        blocks = [np.where(df["fold"].to_numpy() == k)[0] for k in sorted(df["fold"].unique())]
    for fr in FRACS:
        idx = np.concatenate([b[top_mask(df["p_10h"].to_numpy()[b], fr, rng)] for b in blocks])
        r, c = reach[idx], chance[idx]
        lifts[fr] = float((r.mean() - c.mean()) - base_gap)
        out.append([f"{fr * 100:g}%", f0(len(idx)), f4(r.mean()), f4(c.mean()), f4((r.mean() - c.mean()) - base_gap), P(float(r.sum() / reach.sum()), 1)])
    return lifts, table(f"{per_label(per)}: lift / gain curve over all events, by p_10h", ["top share", "events", "reach within 10 h", "chance", "lift", "share of all reachers captured"], out,
                 note="Test months: top share taken inside each fold and pooled, as in S1.")


def weekly(per, df):
    q1 = df["pick_0.01"].to_numpy()
    d = df.assign(week=df["t0"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d"), pk=q1)
    rows, stats = [], []
    for wk, g in d.groupby("week"):
        p = g[g["pk"]]
        gap_all = g["reach_10h"].mean() - g["chance_10h"].mean()
        lift = (p["reach_10h"].mean() - p["chance_10h"].mean() - gap_all) if len(p) else None
        pred = float(p["cal_10h"].mean()) if len(p) else None
        act = float(p["reach_10h"].mean()) if len(p) else None
        rows.append([wk, f0(len(g)), f0(len(p)), f4(act) if act is not None else "n/a", f4(lift) if lift is not None else "n/a", f4(pred) if pred is not None else "n/a",
                     f4(act - pred) if act is not None else "n/a"])
        stats.append((wk, len(p), lift, (act - pred) if act is not None else None, p["reach_10h"].sum(), p["chance_10h"].sum(), g["reach_10h"].mean(), g["chance_10h"].mean(), len(g)))
    tab = table(f"{per_label(per)}: weekly lift and reliability, Rule A q=1% picks", ["week (Monday)", "events", "picks", "actual reach (picks)", "lift", "mean calibrated p (picks)", "actual - predicted"], rows)
    ok = [(i, s) for i, s in enumerate(stats) if s[1] >= 30 and s[2] is not None]
    rho_l = spearman([i for i, _ in ok], [s[2] for _, s in ok]) if len(ok) >= 4 else None
    rho_r = spearman([i for i, _ in ok], [s[3] for _, s in ok]) if len(ok) >= 4 else None
    half = len(stats) // 2

    def pooled(sub):
        n = sum(s[1] for s in sub)
        if n == 0:
            return None, 0
        r = sum(s[4] for s in sub) / n
        c = sum(s[5] for s in sub) / n
        ga = sum(s[6] * s[8] for s in sub) / sum(s[8] for s in sub) - sum(s[7] * s[8] for s in sub) / sum(s[8] for s in sub)
        return (r - c) - ga, n
    l1, n1 = pooled(stats[:half])
    l2, n2 = pooled(stats[half:])
    summ = table(f"{per_label(per)}: is the edge fading? (weekly lift, weeks with >= 30 picks)", ["measure", "value"],
                 [["weeks used / total weeks", f"{len(ok)} / {len(stats)}"], ["Spearman (week order, lift)", f4(rho_l, 3) if rho_l is not None else "n/a"],
                  ["Spearman (week order, actual - predicted)", f4(rho_r, 3) if rho_r is not None else "n/a"],
                  [f"pooled lift, first {half} weeks (picks {n1:,})", f4(l1) if l1 is not None else "n/a"],
                  [f"pooled lift, last {len(stats) - half} weeks (picks {n2:,})", f4(l2) if l2 is not None else "n/a"]])
    return [tab, summ], dict(weeks=[s[0] for s in stats], lift=[s[2] for s in stats], n=[s[1] for s in stats])


# ---------------------------------------------------------------------------
# C2
# ---------------------------------------------------------------------------
def c2(per, df, t, label):
    d = df.set_index("event_id")
    t = t.copy()
    t["fees"] = t["entry_fee"] + t["exit_fee"]
    t["slip"] = t["entry_slip"] + t["exit_slip"]
    t["fund"] = t["funding_paid"] - t["funding_received"]
    rows = []
    for h in (2, 5, 10):
        rv = d.loc[t["event_id"], f"reach_{h}h"].to_numpy() == 1
        pos = (t["net"] > 0).to_numpy()
        lost = rv & ~pos
        sub = t[lost]
        stopped = int((sub["exit_reason"] == "stop").sum())
        mu_exit = sub[sub["exit_reason"] == "mu"]
        gross_short = int((mu_exit["gross_pnl"] <= mu_exit["fees"] + mu_exit["slip"]).sum())
        fund_turn = int(((mu_exit["gross_pnl"] > mu_exit["fees"] + mu_exit["slip"]) & (mu_exit["net"] <= 0)).sum())
        other = int(len(sub)) - stopped - len(mu_exit)
        rows.append([f"{h} h", f0(len(t)), f0(int(rv.sum())), f0(int((rv & pos).sum())), P(float((rv & pos).sum() / max(1, rv.sum()))), f0(int(lost.sum())), f0(stopped), f0(gross_short), f0(fund_turn), f0(other),
                     f0(int((~rv & pos).sum()))])
    return table(f"{label}: label versus trade", ["horizon", "trades", "label says reverted by h", "of those, net > 0", "share", "reverted but lost", "...stopped out first", "...exit at mu, gross below fees + slippage",
                                                    "...exit at mu, gross covers fees + slippage, funding turns it negative", "...other", "label says not reverted but net > 0"], rows)


def c2_by_z(per, df, t, label):
    d = df.set_index("event_id")
    t = t.copy()
    t["zb"] = zb(d.loc[t["event_id"], "z"]).to_numpy()
    rv = d.loc[t["event_id"], "reach_10h"].to_numpy() == 1
    rows = []
    for b in ZL:
        m = (t["zb"] == b).to_numpy() & rv
        if m.sum():
            rows.append([b, f0(int(m.sum())), f0(int((t.loc[m, "net"] <= 0).sum())), P(float((t.loc[m, "net"] <= 0).mean()))])
    return table(f"{label}: events reverted within 10 h by |z| bucket, and how many of those trades lost", ["|z|", "reverted trades", "of those, net <= 0", "share lost"], rows)


# ---------------------------------------------------------------------------
# C3
# ---------------------------------------------------------------------------
def picks_per_day(df, period, ndays=None):
    day = df["t0"].dt.floor("D")
    alld = pd.date_range(day.min(), day.max(), freq="D")
    rows = []
    for q in QS:
        c = day[df[f"pick_{q}"]].value_counts().reindex(alld, fill_value=0)
        rows.append([f"q={q}", f0(int(c.sum())), f4(c.mean(), 1), f4(c.median(), 0), f4(c.quantile(0.9), 0), f0(int(c.max())), f0(int((c == 0).sum())), f0(len(alld))])
    return table(f"{period}: picks per UTC day", ["set", "picks", "mean per day", "median", "90th pct", "max", "days with none", "days"], rows)


def clusters(t):
    n = len(t)
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    t0 = pd.to_datetime(t["t0"], utc=True).to_numpy()
    tx = pd.to_datetime(t["exit_time"], utc=True).to_numpy()
    coins = np.concatenate([t["ticker_a"].to_numpy(), t["ticker_b"].to_numpy()])
    idx = np.concatenate([np.arange(n), np.arange(n)])
    order = np.lexsort((np.concatenate([t0, t0]), coins))
    last_end, last_i, last_c = None, None, None
    for k in order:
        c, i = coins[k], idx[k]
        if c == last_c and last_end is not None and t0[i] <= last_end:
            ra, rb = find(i), find(last_i)
            if ra != rb:
                parent[ra] = rb
            if tx[i] > last_end:
                last_end, last_i = tx[i], i
        else:
            last_c, last_end, last_i = c, tx[i], i
    roots = np.array([find(i) for i in range(n)])
    sizes = pd.Series(roots).value_counts()
    return int(len(sizes)), float(sizes.mean()), int(sizes.max())


def market_proxy(per, days):
    pdir = os.path.join(TRADE_DIR, "cleaned_vault" if per == "vault" else "cleaned", "price")
    ret, vol = {}, {}
    d0, d1 = days.min(), days.max() + pd.Timedelta(days=1)
    for fn in sorted(os.listdir(pdir)):
        df = pd.read_parquet(os.path.join(pdir, fn), columns=["label", "log_close"])
        ts = (df["label"].dt.tz_localize("UTC") if df["label"].dt.tz is None else df["label"]).astype("datetime64[ns, UTC]")
        m = (ts >= d0 - pd.Timedelta(days=1)) & (ts < d1)
        s = pd.Series(df.loc[m, "log_close"].to_numpy(), index=ts[m]).dropna()
        if len(s) < 1000:
            continue
        daily_last = s.resample("D").last()
        ret[fn[:-8]] = daily_last.diff()
        vol[fn[:-8]] = s.diff().dropna().resample("D").std()
    R = pd.DataFrame(ret).reindex(days)
    V = pd.DataFrame(vol).reindex(days)
    return R.mean(axis=1), V.mean(axis=1), R.shape[1]


def btc_proxy(per, days_needed):
    b = pd.read_feather(BTC_FILE)
    s_ = pd.Series(np.log(b["close"].to_numpy(float)), index=pd.to_datetime(b["date"], utc=True).astype("datetime64[ns, UTC]")).sort_index()
    last = s_.resample("D").last()
    ret = last.diff()
    vol = s_.diff().dropna().resample("D").std()
    need = pd.DatetimeIndex(days_needed)
    assert ret.reindex(need).notna().all() and vol.reindex(need).notna().all(), f"BTC: a day of the {per} window is missing"
    return ret.reindex(need), vol.reindex(need), "BTC 30-minute closes"


def c3_market(per, mo, tkey, anchor, nominal, mproxy):
    q, stop, fee = tkey
    me = load_me(per, mo, q, stop, fee)
    d = DD.daily_equity(me, anchor, nominal)
    pnl = d.diff().dropna()
    mret, mvol, pname = mproxy
    j = pd.DataFrame({"pnl": pnl, "mret": mret.reindex(pnl.index), "mabs": mret.abs().reindex(pnl.index), "mvol": mvol.reindex(pnl.index)}).dropna()
    tot = float(pnl.sum())
    tabs = []
    rows = []
    for col, nm in (("mabs", "|market return|"), ("mvol", "market volatility")):
        j["tc"] = pd.qcut(j[col].rank(method="first"), 3, labels=["low third", "middle third", "high third"])
        for k in ("low third", "middle third", "high third"):
            s = j[j["tc"] == k]
            rows.append([nm, k, f0(len(s)), f4(s["pnl"].mean(), 2), f4(s["pnl"].sum(), 2), P(float(s["pnl"].sum() / tot), 1) if tot != 0 else "n/a", P(float((s["pnl"] > 0).mean()), 1)])
    tabs.append(table(f"{per_label(per)}, {PB.pretty(q, stop, fee)}, open{mo}: daily PnL by market regime (proxy: {pname})", ["measure", "tercile of days", "days", "mean daily PnL $", "total PnL $", "share of run PnL", "share of days positive"], rows))
    rows = [[nm, f4(j["pnl"].corr(j[c]), 3), f4(j["pnl"].corr(j[c], method="spearman"), 3)] for c, nm in (("mret", "market return"), ("mabs", "|market return|"), ("mvol", "market volatility"))]
    best = pnl.sort_values(ascending=False)
    rows2 = [["total net", f4(tot, 2)], ["best day", f4(float(best.iloc[0]), 2)], ["net without the best day", f4(tot - float(best.iloc[0]), 2)], ["net without the best 3 days", f4(tot - float(best.iloc[:3].sum()), 2)],
             ["share of net from the best day", P(float(best.iloc[0] / tot), 1) if tot != 0 else "n/a"]]
    tabs.append(table(f"{per_label(per)}, {PB.pretty(q, stop, fee)}, open{mo}: daily PnL correlation with the market proxy ({pname})", ["measure", "Pearson", "Spearman"], rows))
    big_day = table(f"{per_label(per)}, {PB.pretty(q, stop, fee)}, open{mo}: does the run need one big day?", ["", "$"], rows2)
    return tabs, big_day


# ---------------------------------------------------------------------------
# C4
# ---------------------------------------------------------------------------
def exposure_peak(t):
    ev = pd.concat([pd.DataFrame({"time": t["t0"].to_numpy(), "d": t["notional"].to_numpy()}), pd.DataFrame({"time": pd.to_datetime(t["exit_time"]).to_numpy(), "d": -t["notional"].to_numpy()})])
    ev = ev.sort_values(["time", "d"])
    return float(ev["d"].cumsum().max())


def longest_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def c4_rows(per, mo, num, anchor, nominal):
    rows, recs_ = [], []
    for q in QS:
        for stop in CAP_STOPS:
            for fee in ("taker", "maker"):
                t = load_trades(per, mo, q, stop, fee)
                me = load_me(per, mo, q, stop, fee)
                d = DD.daily_equity(me, anchor, nominal)
                pnl = d.diff().dropna()
                eps = DD.drawdown_episodes(d, top=None)
                deep = eps[0] if eps else None
                rec_days = None
                if deep:
                    if deep["recovery_day"] == "not recovered":
                        rec_days = "not recovered"
                    else:
                        rec_days = (pd.Timestamp(deep["recovery_day"]) - pd.Timestamp(deep["bottom_day"])).days
                tt = t.sort_values("exit_time")
                run_ = num["runs"][f"q{q}_stop{stop}_fee{fee}"]
                assert abs(float(d.iloc[-1]) - run_["final_equity"]) < 1e-6, f"daily-equity final {d.iloc[-1]} != report {run_['final_equity']} ({per} {mo} {q} {stop} {fee})"
                CHECK_FINAL.append(1)
                tstat = pnl.mean() / (pnl.std(ddof=1) / np.sqrt(len(pnl))) if pnl.std(ddof=1) > 0 else None
                rows.append([q, PB.STOP_NAME[stop], fee, f4(pnl.mean(), 2), f4(pnl.std(ddof=1), 2), f4(tstat, 2) if tstat is not None else "n/a", f0(len(pnl)), f4(pnl.min(), 2), f4(pnl.max(), 2),
                             f0(longest_run((pnl < 0).tolist())), P(deep["depth"]) if deep else "none", f0(deep["days_underwater"]) if deep else "n/a", str(rec_days) if deep else "n/a",
                             f4(t["net"].min(), 2), f0(longest_run((tt["net"] <= 0).tolist())), f4(exposure_peak(t), 0), f4(run_["peak_margin_used"], 0), f4(run_["distance_to_liquidation_ratio"]["min"], 3)])
                recs_.append(dict(q=q, stop=stop, fee=fee, final=float(d.iloc[-1])))
    tab = table(f"{per_label(per)}, max_open {mo}: risk, every run",
                ["q", "stop", "fee", "mean daily PnL $", "std $", "t-stat", "days", "worst day $", "best day $", "longest run of losing days", "deepest drawdown", "days underwater", "days from bottom to recovery",
                 "worst trade $", "longest run of losing trades", "peak gross exposure $", "peak margin $", "min distance to liquidation"], rows)
    return tab, recs_


def losing_attrs(per_recs, label):
    rows = []
    losing = [r for r in per_recs if r["final"] < DD.START_EQUITY]
    for attr, vals in (("q", QS), ("stop", CAP_STOPS), ("fee", ("taker", "maker"))):
        for v in vals:
            tot = [r for r in per_recs if r[attr] == v]
            ls = [r for r in losing if r[attr] == v]
            rows.append([attr, PB.STOP_NAME.get(v, v) if attr == "stop" else v, f"{len(ls)} of {len(tot)}"])
    return table(f"{label}: configurations ending below $1,000 ({len(losing)} of {len(per_recs)}), by attribute", ["attribute", "value", "losing runs"], rows)


def worst_trades(per, t, label):
    w = t.nsmallest(10, "net")
    rows = [[r.t0.strftime("%Y-%m-%d %H:%M"), f"{r.ticker_a}/{r.ticker_b}", r.exit_reason, f0(r.holding_minutes), f4(r.net, 2), f4(r.notional, 0)] for r in w.itertuples()]
    return table(f"{label}: the 10 largest losing trades", ["entry", "pair", "exit reason", "minutes held", "net $", "notional $"], rows)


# ---------------------------------------------------------------------------
# C5
# ---------------------------------------------------------------------------
def build2_notional(coins, d0, d1):
    out = {}
    for c in coins:
        f = os.path.join(BUILD2, f"{c}-1m.feather")
        if not os.path.exists(f):
            continue
        df = pd.read_feather(f, columns=["date", "notional"])
        ts = pd.to_datetime(df["date"], utc=True)
        m = (ts >= d0 - pd.Timedelta(hours=2)) & (ts < d1)
        s = pd.Series(df.loc[m, "notional"].to_numpy(float), index=ts[m]).groupby(level=0).last()
        out[c] = s
    return out


def c5(per, mo, key, df, geo, move_cache, anchor, nominal, notional_cache):
    q, stop, fee = key
    t = load_trades(per, mo, q, stop, fee)
    me = load_me(per, mo, q, stop, fee)
    sk = load_skips(per, mo, q, stop, fee)
    label = f"{per_label(per)}, {PB.pretty(q, stop, fee)}, open{mo}"
    cap = mo
    util = (me["margin_used"] / me["account_value"]).to_numpy()
    at_cap, near = float((me["n_open"] >= cap).mean()), float((me["n_open"] >= cap - 1).mean())
    tabs = [table(f"{label}: margin utilisation and how often the book was full", ["measure", "value"],
                  [["mean margin used / account value", P(float(util.mean()), 2)], ["median", P(float(np.median(util)), 2)], ["95th percentile", P(float(np.quantile(util, 0.95)), 2)], ["max", P(float(util.max()), 2)],
                   [f"share of minutes with n_open = {cap} (the cap)", P(at_cap, 2)], [f"share of minutes with n_open >= {cap - 1}", P(near, 2)],
                   ["skips by reason", "; ".join(f"{k} {v:,}" for k, v in sk["reason"].value_counts().items())],
                   ["return on margin used = total net / time-average margin used", f4(float(t["net"].sum() / me["margin_used"].mean()), 4)],
                   ["total net $", f4(float(t["net"].sum()), 2)], ["time-average margin used $", f4(float(me["margin_used"].mean()), 2)]],
                  note=f"Window length: the engine window is {WIN[per]} days ({'vault' if per == 'vault' else 'test months'}), so return on margin is over {WIN[per]} days and the two periods are not directly comparable in level.")]
    # taken vs skipped
    d = df.set_index("event_id")
    picks = d[d[f"pick_{q}"]]
    taken = set(t["event_id"])
    skipped = set(sk["event_id"]) - taken
    rows = []
    for nm, ids in (("taken", sorted(taken)), ("skipped", sorted(skipped)), ("all picks of the q", sorted(picks.index))):
        sub = picks.loc[picks.index.intersection(ids)]
        g, w = [], []
        for e in sub.index:
            if e in move_cache["pos"]:
                mv = move_cache["move"][move_cache["pos"][e]]
                za = abs(float(sub.loc[e, "z"]))
                hit = np.where(mv[1:601] >= za)[0]
                ex = (hit[0] + 1) if len(hit) else 600
                g.append(mv[ex])
                w.append(1.0 if len(hit) else 0.0)
        rows.append([nm, f0(len(sub)), f4(sub["reach_10h"].mean()), f4(sub["cal_10h"].mean()), f4(sub["z"].abs().mean(), 3), f4(float(np.mean(g)), 4) if g else "n/a", P(float(np.mean(w)), 1) if w else "n/a", f0(len(g))])
    tabs.append(table(f"{label}: taken versus skipped picks (skipped = book full, margin or minimum order)", ["picks", "n", "reach within 10 h (label)", "mean calibrated p_10h", "mean |z|", "mean gross at a no-stop exit (sigma)", "win-at-mu share", "n with a price path"], rows,
                      note="Paths exist only for events in the traded or skipped sets of the primary runs; the sigma gross is the move at the first mu hit, else at minute 600 (no stop, no costs)."))
    # capacity
    tt = t.copy()
    tt["g"] = geo.loc[tt["event_id"], ["beta"]].to_numpy().ravel()
    na = tt["notional"] / (1 + tt["g"].abs())
    nb = tt["notional"] * tt["g"].abs() / (1 + tt["g"].abs())
    ratios = []
    drop = {"entry_minute": dict(absent=0, empty=0, one_leg=0), "trailing_60min_median": dict(absent=0, empty=0, one_leg=0)}
    for i, r in enumerate(tt.itertuples()):
        row, absent = [], False
        for coin, leg in ((r.ticker_a, na.iloc[i]), (r.ticker_b, nb.iloc[i])):
            s = notional_cache.get(coin)
            if s is None:
                absent = True
                row.append((np.nan, np.nan))
                continue
            minute = r.t0.floor("min")
            v = s.get(minute, np.nan)
            w = s.loc[minute - pd.Timedelta(minutes=60):minute - pd.Timedelta(minutes=1)]
            row.append((leg / v if v and v > 0 else np.nan, leg / w.median() if len(w) and w.median() > 0 else np.nan))
        out_ = []
        for k, name in enumerate(("entry_minute", "trailing_60min_median")):
            vals = [x[k] for x in row if not np.isnan(x[k])]
            if not vals:
                drop[name]["absent" if absent else "empty"] += 1
            elif len(vals) == 1:
                drop[name]["one_leg"] += 1
            out_.append(max(vals) if vals else np.nan)
        ratios.append(tuple(out_))
    rr = pd.DataFrame(ratios, columns=["entry_minute", "trailing_60min_median"])
    rows = []
    for c in rr.columns:
        v = rr[c].dropna()
        rows.append([c.replace("_", " "), f0(len(v)), f4(v.median(), 4), f4(v.quantile(0.9), 4), f4(v.quantile(0.99), 4)] + [P(float((v > x).mean()), 1) for x in (0.01, 0.05, 0.10)])
    tabs.append(table(f"{label}: larger leg notional as a share of the coin's traded notional (build2 1-minute cache)", ["denominator", "trades", "median", "90th pct", "99th pct", "share above 1%", "above 5%", "above 10%"], rows,
                      note=("Per trade the larger of the two legs' ratios. Entry minute = the bar labelled t0 (the first minute after the signal); the trailing window is the 60 bars before it. "
                           + " ".join(f"{nm.replace('_', ' ')}: {sum(dv[k] for k in ('absent', 'empty'))} of {len(tt):,} trades left out ({dv['absent']} with a coin absent from the cache, {dv['empty']} with no traded notional "
                                      f"in the {'entry minute (bar missing or zero)' if nm == 'entry_minute' else 'trailing window (no bars or zero median)'} on either leg); {dv['one_leg']} further trades use one leg only because the other leg had none." for nm, dv in drop.items()))))
    # tiers
    med_daily = {c: float(s.groupby(s.index.floor("D")).sum().median()) for c, s in notional_cache.items() if len(s)}
    ser = pd.Series(med_daily)
    terc = pd.qcut(ser.rank(method="first"), 3, labels=["least liquid third", "middle third", "most liquid third"])
    tier_of = terc.to_dict()
    order = {"least liquid third": 0, "middle third": 1, "most liquid third": 2}
    tt["tier"] = [min((tier_of.get(a), tier_of.get(b)), key=lambda x: order.get(x, 9)) if tier_of.get(a) and tier_of.get(b) else None for a, b in zip(tt["ticker_a"], tt["ticker_b"])]
    tt["ratio"] = rr["entry_minute"].to_numpy()
    tot = float(tt["net"].sum())
    rows = []
    for tier in order:
        s = tt[tt["tier"] == tier]
        rows.append([tier, f0(len(s)), P(float((s["exit_reason"] == "mu").mean())) if len(s) else "n/a", f4(s["net"].mean(), 3) if len(s) else "n/a", f4(s["net"].sum(), 2), P(float(s["net"].sum() / tot), 1) if tot != 0 else "n/a", f4(s["ratio"].median(), 4) if len(s) else "n/a"])
    tabs.append(table(f"{label}: by coin liquidity tier (terciles of median daily traded notional; a trade takes its less liquid leg's tier)", ["tier", "trades", "win rate (mu)", "mean net $", "total net $", "share of run net", "median leg / minute notional"], rows))
    ent = rr["entry_minute"].dropna()
    return tabs, dict(share10=float((ent > 0.10).mean()), n_used=int(len(ent)), n_trades=int(len(tt)))


# ---------------------------------------------------------------------------
# C6
# ---------------------------------------------------------------------------
def c6(per, mo):
    rows, mix = [], []
    nets = {}
    for q in QS:
        for stop in CAP_STOPS:
            for fee in ("taker", "maker"):
                t = load_trades(per, mo, q, stop, fee)
                sn, sno = float(t["net"].sum()), float(t["notional"].sum())
                nets[(q, stop, fee)] = sn
                be = sn / (2 * sno) * 1e4
                rows.append([q, PB.STOP_NAME[stop], fee, f4(sn, 2)] + [f4(sn - 2 * s / 1e4 * sno, 2) for s in SLIPS[1:]] + [f4(be, 2) if sn > 0 else "none (net not positive)"])
            nm, nt = nets[(q, stop, "maker")], nets[(q, stop, "taker")]
            if nm > 0 and nt >= 0:
                lam = "0% (taker alone stays above $1,000)"
            elif nm <= 0:
                lam = "not reachable (maker alone is not above $1,000)"
            else:
                lam = P(float(-nt / (nm - nt)), 1)
            mix.append([q, PB.STOP_NAME[stop], f4(nm, 2), f4(nt, 2), lam])
    head = ["q", "stop", "fee", "net PnL at 0 bp"] + [f"net at +{s:g} bp per fill" for s in SLIPS[1:]] + ["break-even extra slippage (bp per fill)"]
    t1 = table(f"{per_label(per)}, max_open {mo}: net PnL with extra slippage per fill (arithmetic on the saved trades)", head, rows,
               note="Net values below -$1,000 mean the account would have been wiped out; those cells are arithmetic only.")
    t2 = table(f"{per_label(per)}, max_open {mo}: maker share of fills needed to keep net PnL above zero (interpolating the maker and taker runs' totals)", ["q", "stop", "maker run net $", "taker run net $", "maker share needed"], mix)
    return [t1, t2]


def funding_dir(per, mo, key, z_by):
    q, stop, fee = key
    t = load_trades(per, mo, q, stop, fee)
    t["z"] = z_by.reindex(t["event_id"]).to_numpy()
    t["fund"] = t["funding_paid"] - t["funding_received"]
    rows = []
    for nm, m in (("short spread (z>0)", t["z"] > 0), ("long spread (z<0)", t["z"] < 0), ("all", np.ones(len(t), bool))):
        s = t[m]
        rows.append([nm, f0(len(s)), f4(s["funding_paid"].sum(), 2), f4(s["funding_received"].sum(), 2), f4(s["fund"].sum(), 2), "cost" if s["fund"].sum() > 0 else "income"])
    return table(f"{per_label(per)}, {PB.pretty(q, stop, fee)}, open{mo}: funding by direction", ["direction", "trades", "funding paid $", "funding received $", "net funding $ (paid - received)", "sign"], rows)


# ---------------------------------------------------------------------------
# C7
# ---------------------------------------------------------------------------
def workload(per, df):
    tabs = [picks_per_day(df, per_label(per))]
    rows = []
    for q in QS:
        pk = df[df[f"pick_{q}"]]
        nd = df["t0"].dt.floor("D").nunique()
        byh = pk["t0"].dt.hour.value_counts().reindex(range(24), fill_value=0) / nd
        per_ts = pk.groupby("t0").size()
        rows.append([f"q={q}", f4(per_ts.mean(), 2), f0(int(per_ts.max())), f4(per_ts.quantile(0.9), 0), f0(int(len(per_ts))), f"{int(byh.idxmax()):02d}:00", f4(float(byh.max()), 2), f"{int(byh.idxmin()):02d}:00", f4(float(byh.min()), 2)])
    tabs.append(table(f"{per_label(per)}: picks per timestamp and busiest hours of the day (UTC)", ["set", "mean picks per timestamp with a pick", "max at one timestamp", "90th pct", "timestamps with a pick", "busiest hour", "picks per day then", "quietest hour", "picks per day then"], rows))
    rows = []
    for h in range(24):
        rows.append([f"{h:02d}:00"] + [f4(len(df[df[f"pick_{q}"] & (df["t0"].dt.hour == h)]) / df["t0"].dt.floor("D").nunique(), 3) for q in QS])
    tabs.append(table(f"{per_label(per)}: mean picks per day by UTC hour of day", ["hour", "q=1%", "q=0.5%", "q=0.1%"], rows))
    return tabs


def main():
    t0 = time.time()
    log(f"[PARTC] sha256 s1_vault_docx_partc.py {VR.sha256(__file__)}; start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC")
    PB.FLAGS.clear()
    _st = json.load(open(os.path.join(LOG_DIR, "s1_vault_docx_data.json")))["setup"]
    WIN["vault"], WIN["test"] = _st["engine_window_days"], _st["test_engine_window_days"]
    vdf, tdf = DD.vault_frame(), DD.test_frame()
    for df, nm in ((vdf, "vault"), (tdf, "test")):
        df["z"] = df["z"].astype(float)
    nums = {tag: json.load(open(os.path.join(LOG_DIR, DD.TAGS[tag][1]))) for tag in DD.TAGS}
    z_v, z_t = vdf.set_index("event_id")["z"], tdf.set_index("event_id")["z"]
    sections = []
    # EV coefficients from the test months (search data), per fee
    ev_coef = {}
    for fee in ("maker", "taker"):
        tt = load_trades("test", 10, 0.01, "none", fee)
        ev_coef[fee] = (float(tt.loc[tt["exit_reason"] == "mu", "net"].mean()), float(tt.loc[tt["exit_reason"] == "timeout", "net"].mean()))
        log(f"[PARTC] EV coefficients from test trades, fee {fee}: mu-exit mean net {ev_coef[fee][0]:.4f}, timeout mean net {ev_coef[fee][1]:.4f}")

    # ---------------- C1
    s1 = dict(heading="Part C-1. Ranking and decay", level=1, intro="Do higher-probability picks earn more, or only win more? Is the edge fading inside the vault? Deciles are over the traded set of each run; the lift curve is over all events.", tables=[], images=[], flags=[])
    for (mo, q, stop, fee) in PRIMARY:
        for per, df in (("vault", vdf), ("test", tdf)):
            t = load_trades(per, mo, q, stop, fee)
            tabs = c1_deciles(per, df, t, ev_coef[fee])
            for tb in tabs:
                tb["title"] += f" -- {PB.pretty(q, stop, fee)}, open{mo}"
            s1["tables"] += tabs
    rng = np.random.default_rng(DD.SEED + 7)
    lv, tb_v = gain_curve(vdf, "vault", rng)
    lt, tb_t = gain_curve(tdf, "test", rng)
    s1["tables"] += [tb_v, tb_t]
    ref_v = json.load(open(os.path.join(LOG_DIR, "s1_vault_report.json")))["lift"]["rows"][0]
    assert ref_v["label"] == "own top 1% by p_10h"
    s1d = json.load(open(os.path.join(LOG_DIR, "s1d_report.json")))["item1_robustness"]["0.01"]
    pf = {int(k): v for k, v in s1d["per_fold"].items() if int(k) >= 1}
    ref_t = sum(v["n"] * v["lift"] for v in pf.values()) / sum(v["n"] for v in pf.values())
    log(f"[PARTC] RECEIPT gain curve top 1% lift: vault {lv[0.01]:.4f} vs s1_vault_report.json {ref_v['lift']:.4f}; test (folds 1-7) {lt[0.01]:.4f} vs s1d_report.json per-fold lifts folds 1-7, n-weighted {ref_t:.4f} "
        f"(tolerance 5e-4). For reference s1d_report.json pooled over folds 0-7 = {s1d['pooled_point']:.4f}; the test months of this report are folds 1-7.")
    assert abs(lv[0.01] - ref_v["lift"]) < 5e-4 and abs(lt[0.01] - ref_t) < 5e-4, "gain-curve top-1% lift off the reference"
    wk = {}
    for per, df in (("vault", vdf), ("test", tdf)):
        tabs, wk[per] = weekly(per, df)
        s1["tables"] += tabs
    sections.append(s1)
    log(f"[PARTC] C1 done [{time.time()-t0:.0f}s]")

    # ---------------- C2
    s2 = dict(heading="Part C-2. Label versus trade", level=1, intro="Of the events whose label says the spread reverted by h, how many trades ended net-positive after fees, and why did the rest lose? A trade at no stop exits at mu on the first hit, so a reverted trade that lost was lost to costs; with a stop it can also have been stopped before mu.", tables=[], images=[], flags=[])
    for (mo, q, stop, fee) in PB.RUNS:
        for per, df in (("vault", vdf), ("test", tdf)):
            t = load_trades(per, mo, q, stop, fee)
            s2["tables"].append(c2(per, df, t, f"{per_label(per)}, {PB.pretty(q, stop, fee)}, open{mo}"))
    for per, df in (("vault", vdf), ("test", tdf)):
        s2["tables"].append(c2_by_z(per, df, load_trades(per, 10, 0.01, "none", "maker"), f"{per_label(per)}, {PB.pretty(0.01, 'none', 'maker')}, open10"))
    sections.append(s2)
    log(f"[PARTC] C2 done [{time.time()-t0:.0f}s]")

    # ---------------- C3
    s3 = dict(heading="Part C-3. Independence and market exposure", level=1, intro="How many separate bets are these trades? Is the PnL a market-stress effect? Two market proxies are used and labelled in each table: BTC (30-minute closes from user_data/normalized/BTC.feather: daily log-close change, and the daily standard deviation of 30-minute log returns), and the equal-weighted mean over the saved coins (built only from coins the strategy picked, so partly selected by the strategy).", tables=[], images=[], flags=[])
    for per, df in (("vault", vdf), ("test", tdf)):
        s3["tables"].append(picks_per_day(df, per_label(per)))
    anchor = {"vault": DD.H.VAULT_START.normalize() - pd.Timedelta(days=1), "test": H.TEST_BLOCK_STARTS[1].normalize() - pd.Timedelta(days=1)}
    last_t0 = pd.read_parquet(VR.PICKS, columns=["t0"])["t0"].max()
    nominal = {"vault": last_t0.normalize() + pd.Timedelta(days=1), "test": H.TEST_BLOCK_ENDS[7].normalize()}
    mprox = {}
    for per in ("vault", "test"):
        days = pd.date_range(anchor[per] + pd.Timedelta(days=1), nominal[per] + pd.Timedelta(days=3), freq="D", inclusive="left")
        mr, mv, ncoin = market_proxy(per, days)
        pnl_days = days[days < nominal[per]]
        btc = btc_proxy(per, pnl_days[pnl_days > anchor[per]])
        mprox[per] = [btc, (mr, mv, f"equal-weighted mean of the {ncoin} saved coins (partly selected by the strategy)")]
        log(f"[PARTC] market proxies {per}: BTC ({len(pnl_days)} days present) and {ncoin} saved coins [{time.time()-t0:.0f}s]")
    for (mo, q, stop, fee) in PRIMARY:
        rows, cl_rows = [], []
        for per, df in (("vault", vdf), ("test", tdf)):
            t = load_trades(per, mo, q, stop, fee)
            me = load_me(per, mo, q, stop, fee)
            nopen = me.set_index("time")["n_open"].resample("D")
            hr = t.groupby(t["t0"].dt.floor("h")).size()
            top10 = float(hr.sort_values(ascending=False).head(10).sum() / len(t))
            ncl, mcl, bcl = clusters(t)
            rows.append([per_label(per), f4(nopen.mean().mean(), 2), f4(nopen.max().mean(), 2), f0(int(nopen.max().max())), f4(hr.mean(), 2), f0(int(hr.max())), P(top10, 1)])
            cl_rows.append([per_label(per), f0(len(t)), f0(ncl), f4(mcl, 2), f0(bcl), f0(t[["ticker_a", "ticker_b"]].stack().nunique())])
            for pr in mprox[per]:
                tb_, big = c3_market(per, mo, (q, stop, fee), anchor[per], nominal[per], pr)
                s3["tables"] += tb_
            s3["tables"].append(big)
        s3["tables"].append(table(f"{PB.pretty(q, stop, fee)}, open{mo}: open trades per day and trades per entry hour", ["", "mean of daily mean n_open", "mean of daily max n_open", "max n_open on any day", "mean trades per entry hour (hours with a trade)", "max in one hour", "share of trades in the 10 busiest hours"], rows))
        s3["tables"].append(table(f"{PB.pretty(q, stop, fee)}, open{mo}: clusters of trades (same coin, overlapping holding time)", ["", "trades", "clusters", "mean trades per cluster", "largest cluster", "distinct coins traded"], cl_rows,
                                  note="The cluster count is an upper bound on the number of independent bets, not an estimate of it."))
    sections.append(s3)
    log(f"[PARTC] C3 done [{time.time()-t0:.0f}s]")

    # ---------------- C4
    s4 = dict(heading="Part C-4. Risk", level=1, intro="Daily PnL statistics, drawdown, streaks, exposure and distance to liquidation for every run; the largest losses of the primary runs; what the losing configurations share.", tables=[], images=[], flags=[])
    recs = {}
    for per, mo_tag in (("vault", {10: "vault_open10", 20: "vault_open20"}), ("test", {10: "test_open10", 20: "test_open20"})):
        for mo in (10, 20):
            tab, rr = c4_rows(per, mo, nums[mo_tag[mo]], anchor[per], nominal[per])
            s4["tables"].append(tab)
            recs[(per, mo)] = rr
            s4["tables"].append(losing_attrs(rr, f"{per_label(per)}, max_open {mo}"))
    for (mo, q, stop, fee) in PRIMARY:
        for per in ("vault", "test"):
            s4["tables"].append(worst_trades(per, load_trades(per, mo, q, stop, fee), f"{per_label(per)}, {PB.pretty(q, stop, fee)}, open{mo}"))
    sections.append(s4)
    log(f"[PARTC] C4 receipt: daily-equity final value equals the report's final equity (1e-6) for {len(CHECK_FINAL)} runs")
    log(f"[PARTC] C4 done [{time.time()-t0:.0f}s]")

    # ---------------- C5
    cap_fact = {}
    s5 = dict(heading="Part C-5. Sizing and capacity", level=1, intro="How full was the book, were skipped picks different, and how big was each trade next to the market it traded in? Volume is the build2 1-minute traded notional per coin.", tables=[], images=[], flags=[])
    geo_v = VL.load_vault_events(columns=["ticker_a", "ticker_b", "beta", "alpha", "mu", "sigma", "z"]).reset_index(drop=True).set_index("event_id")
    geo_t = H.load_search_events(columns=["ticker_a", "ticker_b", "beta", "alpha", "mu", "sigma", "z"])
    for per in ("vault", "test"):
        keys = [(mo, q, stop, fee) for (mo, q, stop, fee) in PRIMARY]
        ids = set()
        for (mo, q, stop, fee) in keys:
            ids |= set(load_trades(per, mo, q, stop, fee)["event_id"]) | set(load_skips(per, mo, q, stop, fee)["event_id"])
        ids = sorted(ids)
        geo = (geo_v if per == "vault" else geo_t).loc[ids]
        base = vdf if per == "vault" else tdf
        t0s = base.set_index("event_id").loc[ids, "t0"].to_numpy()
        move = PB.move_paths(np.array(ids), geo, t0s, os.path.join(TRADE_DIR, "cleaned_vault" if per == "vault" else "cleaned"))
        mc = dict(pos={e: i for i, e in enumerate(ids)}, move=move)
        coins = set()
        for (mo, q, stop, fee) in keys:
            tt = load_trades(per, mo, q, stop, fee)
            coins |= set(tt["ticker_a"]) | set(tt["ticker_b"])
        d0 = anchor[per] + pd.Timedelta(days=1)
        notional_cache = build2_notional(sorted(coins), pd.Timestamp(d0), pd.Timestamp(nominal[per]) + pd.Timedelta(days=1))
        log(f"[PARTC] C5 {per}: paths for {len(ids):,} events, build2 notional for {len(notional_cache)} coins [{time.time()-t0:.0f}s]")
        df_ = vdf if per == "vault" else tdf
        for key in keys:
            tb5, fact5 = c5(per, key[0], key[1:], df_, geo, mc, anchor[per], nominal[per], notional_cache)
            s5["tables"] += tb5
            if key == PRIMARY[0]:
                cap_fact[per] = fact5
    sections.append(s5)
    log(f"[PARTC] C5 done [{time.time()-t0:.0f}s]")

    # ---------------- C6
    s6 = dict(heading="Part C-6. Cost sensitivity (arithmetic only)", level=1, intro="Extra slippage per fill applied to the traded notional of the saved trades, break-even slippage per configuration, the maker share needed, and funding by direction. No run is repeated; account sizing is held as the run had it.", tables=[], images=[], flags=[])
    for per in ("vault", "test"):
        for mo in (10, 20):
            s6["tables"] += c6(per, mo)
    for per, z_by in (("vault", z_v), ("test", z_t)):
        for (mo, q, stop, fee) in PRIMARY:
            s6["tables"].append(funding_dir(per, mo, (q, stop, fee), z_by))
    sections.append(s6)
    log(f"[PARTC] C6 done [{time.time()-t0:.0f}s]")

    # ---------------- C7
    s7 = dict(heading="Part C-7. Live workload", level=1, intro="What paper trading would face: picks per day, per hour and per timestamp.", tables=[], images=[], flags=[])
    for per, df in (("vault", vdf), ("test", tdf)):
        s7["tables"] += workload(per, df)[1:]
    sections.append(s7)

    # charts
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    for per in ("vault", "test"):
        w = wk[per]
        ax[0].plot(range(len(w["lift"])), [np.nan if v is None else v for v in w["lift"]], marker="o", ms=3, label=per)
    ax[0].set_xlabel("week number"); ax[0].set_ylabel("lift, Rule A q=1% picks"); ax[0].legend(fontsize=7)
    for per, df in (("vault", vdf), ("test months", tdf)):
        rng2 = np.random.default_rng(DD.SEED + 9)
        reach, chance = df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy()
        blocks = [np.arange(len(df))] if per == "vault" else [np.where(df["fold"].to_numpy() == k)[0] for k in sorted(df["fold"].unique())]
        ys = []
        for fr in FRACS:
            idx = np.concatenate([b[top_mask(df["p_10h"].to_numpy()[b], fr, rng2)] for b in blocks])
            ys.append((reach[idx].mean() - chance[idx].mean()) - (reach.mean() - chance.mean()))
        ax[1].plot([f * 100 for f in FRACS], ys, marker="o", ms=3, label=per)
    ax[1].set_xscale("log"); ax[1].set_xlabel("top share of events (%)"); ax[1].set_ylabel("lift"); ax[1].legend(fontsize=7)
    fig.tight_layout()
    chart = os.path.join(DD.CHART_DIR, "partc_decay_and_gain.png")
    fig.savefig(chart, dpi=120)
    plt.close(fig)
    s1["images"].append(chart)
    pm = PB.pretty(*PRIMARY[0][1:])
    findings_extra = [f"Capacity ({pm}, max_open {PRIMARY[0][0]}): the share of trades whose larger leg exceeded 10% of that coin's traded notional in the entry minute was {cap_fact['vault']['share10']:.1%} in the vault "
                      f"({cap_fact['vault']['n_used']:,} of {cap_fact['vault']['n_trades']:,} trades with a measurable entry minute) and {cap_fact['test']['share10']:.1%} in the test months "
                      f"({cap_fact['test']['n_used']:,} of {cap_fact['test']['n_trades']:,})."]
    log("[PARTC] FINDING: " + findings_extra[0])
    json.dump(dict(sections=sections, findings_extra=findings_extra, script_sha256=VR.sha256(__file__)), open(OUT_JSON, "w"), indent=1, default=str)
    n_tab = sum(len(s["tables"]) for s in sections)
    log(f"[PARTC] {len(sections)} sections, {n_tab} tables; wrote {OUT_JSON} (sha256 {VR.sha256(OUT_JSON)})  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
