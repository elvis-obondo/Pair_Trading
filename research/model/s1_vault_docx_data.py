"""HL-VAULT1 Word report (planner brief 2026-11-12): builds ONE data file, research/model/logs/s1/s1_vault_docx_data.json,
with every number and every sentence of the document pre-built. The renderer (s1_vault_docx_render.js) only formats this
JSON; it holds no numbers or findings of its own. REPORTED, NOT GATED: findings are stated, no recommendation changes the plan.

    python -u research/model/s1_vault_docx_data.py > research/model/logs/s1/s1_vault_docx_data.log

READS (nothing is simulated, no model is refit, no setting of steps 3-5 changes):
  - the four numbers reports (test base / open20, vault_open10 / vault_open20) and their engine reports;
  - the 48 vault trade / minute-equity / skip parquets and the 48 test-month ones (test: base and open20 tags);
  - the sealed picks file (sha asserted), the 2 h / 5 h calibrated file s1_vault_iso_2h5h.parquet (sha asserted against its
    settings JSON), s1_vault_iso_2h5h.json, s1_vault_report.json, s1d_report.json, s1h_report.json, the model JSON;
  - vault labels and event geometry (z, tickers, minutes_to_mu) through vault_loader (third read of the vault, labels only);
  - the test months through s1_profit1_horizons.build_frame (the same frame HL-PROFIT1-H used) for the test-side comparisons.

DECISION RULES (fixed here before anything is run):
  R1 Rank breakdowns use the Rule A picks of step 4 (q = 1% unless a table says otherwise) against ALL events of the same
     group, lift = gap(picks in group) - gap(all events in group), gap = mean(reach_10h) - mean(chance_10h) (harness.lift).
     Groups: UTC calendar month and ISO week (vault); test fold (test); coin (an event counts for both of its legs); direction
     (short the spread when z > 0, long when z < 0 -- the engine's dir_a = -sign(z)); |z| bucket with fixed edges
     [0, 2, 2.5, 3, 4, 5, inf). Point values only for groups; the interval is given for the pooled sets (day-block
     bootstrap, 2,000 resamples, level 0.9875, seed 20261113). Test-side sets are the pooled test months (folds 1-7).
  R2 Lift by size: the vault's own top 1%, 2%, 5% by p_10h (ceil, seeded random tie-break) and the Rule A picks, vault and
     test months (test: s1d_report.json for the top 1/2/5%, recomputed for the Rule A picks).
  R3 Calibration: read from s1_vault_iso_2h5h.json (every bucket, 2/5/10 h) -- not recomputed.
  R4 Horizons: HL-PROFIT1-H's Q1, Q2 and Q4 tables on the vault, same definitions (quintiles of the calibrated p_2h / p_5h
     over all picks of that q, average rank so ties share a bin; trades = stop none, open cap 10, per fee mode; net/notional;
     still open at 2 h = holding > 120 min, at 5 h = holding > 300 min) with the test-month table beside it, computed by the
     same function on the s1_profit1_horizons frame and base trade logs. Per quintile: n, reach within h, reach within 10 h,
     mean calibrated p, minutes_to_mu median, and for traded picks: n_traded, win rate (exit at mu), share profitable
     (net > 0), mean net $ and mean net/notional per trade, mean hold, share open at 2 h and 5 h.
  R5 Trading, all 48 runs: every field from the numbers reports (final equity, net PnL = final - 1,000, return, gross, fees,
     funding paid / received, trades, win rate (exit at mu), mean win / loss, profit factor, max drawdown, Sharpe, best / worst
     day, mean hold, exit shares, liquidations, skips, peak margin, minimum distance to liquidation) plus, from the trade
     files, mean leverage and the long / short split (n, win rate, net $). The engine's final equity is re-derived from the
     minute-equity file and asserted equal to 1e-6.
  R6 Best config = the run with the highest final equity within each vault tag; the q 1% / stop none / maker run is
     included as the standing reference. For these: daily equity, calendar-month PnL, per-coin top/bottom 10 (reports),
     PnL by |z| bucket and by direction, and the three deepest drawdown episodes (peak day, bottom day, recovery day or
     "not recovered"; an episode is a maximal run of days with equity below its running maximum; depth = bottom / peak - 1).
  R7 Side by side: for every metric in R5, the 24 runs x (test open10, test open20, vault open10, vault open20).
  R8 Sentences (summary, findings): built in this script from the computed numbers with comparison words chosen by the
     numbers themselves; no direction word is typed. No sentence recommends a change.
"""
import hashlib
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
import s1h_recalibration as S1H  # noqa: E402
import s1_profit1_horizons as HZ  # noqa: E402 -- build_frame, load_trades, quintile (test-month comparison)
import s1_vault_report as VR  # noqa: E402 -- top_k_mask, PICKS, sha256
import vault_loader as VL  # noqa: E402

ROOT = VR.ROOT
LOG_DIR = VR.LOG_DIR
TRADE_DIR = os.path.join(HERE, "logs", "profit1")
OUT_JSON = os.path.join(LOG_DIR, "s1_vault_docx_data.json")
CHART_DIR = os.path.join(LOG_DIR, "vault_docx_charts")
SEED = 20261113
N_RESAMPLES, LEVEL = 2000, 0.9875
QS = (0.01, 0.005, 0.001)
STOPS = ("0p5", "1p0", "2p0", "none")
FEES = ("taker", "maker")
START_EQUITY = 1000.0
ZB_EDGES = [0, 2.0, 2.5, 3.0, 4.0, 5.0, np.inf]
ZB_LABELS = ["<2", "2-2.5", "2.5-3", "3-4", "4-5", ">=5"]
TAGS = {"test_open10": ("", "s1_profit1_numbers_report.json", "s1_profit1_report.json", 10),
        "test_open20": ("_open20", "s1_profit1_numbers_report_open20.json", "s1_profit1_report_open20.json", 20),
        "vault_open10": ("_vault_open10", "s1_profit1_numbers_report_vault_open10.json", "s1_profit1_report_vault_open10.json", 10),
        "vault_open20": ("_vault_open20", "s1_profit1_numbers_report_vault_open20.json", "s1_profit1_report_vault_open20.json", 20)}
EXPECTED_ISO_FILE_SHA = None      # read from s1_vault_iso_2h5h_settings.json (stage_a_sha256)


def log(msg):
    print(msg, flush=True)


def recs(df):
    return json.loads(df.to_json(orient="records", double_precision=15))


def run_key(q, stop, fee):
    return f"q{q}_stop{stop}_fee{fee}"


def win_txt(num):
    v = sorted({int(r["cagr_n_days"]) for r in num["runs"].values()})
    return str(v[0]) if len(v) == 1 else f"{v[0]}-{v[-1]}"


def fnum(x, d=4):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


# ---------------------------------------------------------------------------
# frames
# ---------------------------------------------------------------------------
def vault_frame():
    got = VR.sha256(VR.PICKS)
    assert got == VR.EXPECTED_PICKS_SHA, "picks file != the reviewed step-4 output"
    settings = json.load(open(os.path.join(LOG_DIR, "s1_vault_iso_2h5h_settings.json")))
    iso_path = os.path.join(LOG_DIR, "s1_vault_iso_2h5h.parquet")
    iso_sha = VR.sha256(iso_path)
    assert iso_sha == settings["stage_a_sha256"], "2 h / 5 h calibrated file != the settings JSON's sha"
    log(f"[VDOC] picks sha {got}; iso 2h/5h file sha {iso_sha} (matches its settings JSON)")
    picks = pd.read_parquet(VR.PICKS).merge(pd.read_parquet(iso_path), on="event_id", validate="one_to_one")
    ev = VL.load_vault_events(columns=["z", "ticker_a", "ticker_b", "minutes_to_mu", "reach_2h", "reach_5h"]).reset_index(drop=True)
    cols = ["event_id", "z", "ticker_a", "ticker_b", "minutes_to_mu", "reach_2h", "reach_5h", "reach_10h", "chance_10h", "label_gap"]
    df = picks.merge(ev[cols], on="event_id", how="inner", validate="one_to_one")
    assert len(df) == len(picks) == len(ev) and int((df["label_gap"] != 0).sum()) == 0
    df = df.rename(columns={"p_cal_10h": "cal_10h", "p_cal_2h": "cal_2h", "p_cal_5h": "cal_5h"})
    df = df.sort_values("event_id").reset_index(drop=True)
    log(f"[VDOC] vault frame: {len(df):,} events, t0 {df['t0'].min()} .. {df['t0'].max()}")
    return df


def test_frame():
    scored = HZ.build_frame().reset_index(drop=True)           # folds 1-7, picks, iso_*, minutes_to_mu
    ev = H.load_search_events(columns=["z", "ticker_a", "ticker_b", "chance_10h"])
    sub = ev.loc[scored["event_id"].to_numpy()]
    for c in ("z", "ticker_a", "ticker_b", "chance_10h"):
        scored[c] = sub[c].to_numpy()
    scored = scored.rename(columns={"iso_2h": "cal_2h", "iso_5h": "cal_5h", "iso_10h": "cal_10h"})
    log(f"[VDOC] test frame: {len(scored):,} events, folds {sorted(scored['fold'].unique())}")
    return scored


# ---------------------------------------------------------------------------
# R1 / R2: ranking quality
# ---------------------------------------------------------------------------
def gap_of(reach, chance):
    return float(np.mean(reach) - np.mean(chance)) if len(reach) else float("nan")


def group_lift(df, mask, key):
    rows = []
    for g, idx in df.groupby(key, observed=True).groups.items():
        sub = df.loc[idx]
        top = sub[mask[sub.index]]
        ga, gt = gap_of(sub["reach_10h"], sub["chance_10h"]), gap_of(top["reach_10h"], top["chance_10h"])
        rows.append(dict(group=str(g), n_all=int(len(sub)), n_picks=int(len(top)), reach_all=float(sub["reach_10h"].mean()),
                         reach_picks=float(top["reach_10h"].mean()) if len(top) else None,
                         chance_picks=float(top["chance_10h"].mean()) if len(top) else None,
                         gap_all=ga, gap_picks=gt if len(top) else None, lift=(gt - ga) if len(top) else None))
    return rows


def coin_table(df, mask, top_n=15):
    legs = pd.concat([df[["ticker_a", "reach_10h", "chance_10h"]].rename(columns={"ticker_a": "coin"}).assign(pick=mask),
                      df[["ticker_b", "reach_10h", "chance_10h"]].rename(columns={"ticker_b": "coin"}).assign(pick=mask)])
    rows = []
    for coin, g in legs.groupby("coin"):
        p = g[g["pick"]]
        if len(p) == 0:
            continue
        ga, gp = gap_of(g["reach_10h"], g["chance_10h"]), gap_of(p["reach_10h"], p["chance_10h"])
        rows.append(dict(coin=coin, n_pick_legs=int(len(p)), n_all_legs=int(len(g)), reach_picks=float(p["reach_10h"].mean()),
                         gap_picks=gp, gap_all=ga, lift=gp - ga))
    t = pd.DataFrame(rows).sort_values("n_pick_legs", ascending=False)
    tot = int(mask.sum()) * 2
    summ = dict(n_coins_with_picks=int(len(t)), pick_legs=tot,
                share_top5=float(t["n_pick_legs"].head(5).sum() / tot), share_top10=float(t["n_pick_legs"].head(10).sum() / tot))
    return recs(t.head(top_n)), summ


def rank_section(vdf, tdf, rng):
    out = {}
    day_v = vdf["t0"].dt.floor("D").to_numpy()
    day_t = tdf["t0"].dt.floor("D").to_numpy()
    # R2 lift by set size, with intervals
    def boot(df, day, mask):
        reach, chance = df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy()
        p, lo, hi = H.day_block_bootstrap(day, mask, reach, chance, N_RESAMPLES, LEVEL, rng)
        return dict(n=int(mask.sum()), share=float(mask.mean()), reach=float(reach[mask].mean()), chance=float(chance[mask].mean()),
                    lift=float(p), lo=lo, hi=hi)
    sets = {"vault": [], "test": []}
    for frac in (0.01, 0.02, 0.05):
        sets["vault"].append(dict(label=f"own top {frac:.0%} by p_10h", **boot(vdf, day_v, VR.top_k_mask(vdf["p_10h"].to_numpy(), frac, rng))))
    for q in QS:
        sets["vault"].append(dict(label=f"Rule A picks q={q}", **boot(vdf, day_v, vdf[f"pick_{q}"].to_numpy())))
        sets["test"].append(dict(label=f"Rule A picks q={q}", **boot(tdf, day_t, tdf[f"pick_{q}"].to_numpy())))
    s1d = json.load(open(os.path.join(LOG_DIR, "s1d_report.json")))["item1_robustness"]
    for frac in ("0.01", "0.02", "0.05"):
        r = s1d[frac]
        pf17 = {int(k): v for k, v in r["per_fold"].items() if int(k) >= 1}
        lift_f17 = sum(v["n"] * v["lift"] for v in pf17.values()) / sum(v["n"] for v in pf17.values())
        sets["test"].append(dict(label=f"S1-D top {float(frac):.0%} by p_10h, folds 0-7 (per fold, pooled)", n=None, share=None, reach=None,
                                 chance=None, lift=r["pooled_point"], lo=r["pooled_lo"], hi=r["pooled_hi"], lift_folds_1_7=float(lift_f17),
                                 n_positive_folds=r["n_positive"], n_folds=len(r["per_fold"])))
    out["lift_sets"] = sets
    for side in ("vault", "test"):
        for r in sets[side]:
            log(f"[VDOC] lift {side} {r['label']}: lift {r['lift']:.4f} [{r['lo']:.4f}, {r['hi']:.4f}]")
    q1v, q1t = vdf["pick_0.01"].to_numpy(), tdf["pick_0.01"].to_numpy()
    # by month / fold / week
    vdf = vdf.assign(month=vdf["t0"].dt.strftime("%Y-%m"),
                     week=vdf["t0"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d"),
                     dirn=np.where(vdf["z"] > 0, "short spread (z>0)", "long spread (z<0)"),
                     zb=pd.cut(vdf["z"].abs(), ZB_EDGES, right=False, labels=ZB_LABELS))
    tdf = tdf.assign(dirn=np.where(tdf["z"] > 0, "short spread (z>0)", "long spread (z<0)"),
                     zb=pd.cut(tdf["z"].abs(), ZB_EDGES, right=False, labels=ZB_LABELS))
    out["by_month"] = {"vault": group_lift(vdf, q1v, "month"), "test": group_lift(tdf, q1t, "fold")}
    for r, k in zip(out["by_month"]["test"], sorted(tdf["fold"].unique())):
        r["start"] = str(H.TEST_BLOCK_STARTS[int(k)].date())
    out["by_week"] = {"vault": group_lift(vdf, q1v, "week")}
    out["by_dir"] = {"vault": group_lift(vdf, q1v, "dirn"), "test": group_lift(tdf, q1t, "dirn")}
    out["by_z"] = {"vault": group_lift(vdf, q1v, "zb"), "test": group_lift(tdf, q1t, "zb")}
    out["by_coin"], out["coin_summary"] = {}, {}
    for side, df, m in (("vault", vdf, q1v), ("test", tdf, q1t)):
        out["by_coin"][side], out["coin_summary"][side] = coin_table(df, m)
        log(f"[VDOC] coins {side}: {out['coin_summary'][side]}")
    import ast
    import re
    score_log = os.path.join(LOG_DIR, "vault_pull3", "vault-score_i-09ef2cd4868ff3b29.log")      # model-code mapping needs the feature cache (AWS only)
    txt = open(score_log, errors="replace").read()
    coins = {tuple(ast.literal_eval(m)) for m in re.findall(r"model's levels; coins: (\[.*?\])", txt)}
    assert len(coins) == 1, coins
    unseen = set(next(iter(coins)))
    n_log = int(re.search(r"events with at least one unseen leg: ([\d,]+) of", txt).group(1).replace(",", ""))
    leg_unseen = vdf["ticker_a"].isin(unseen) | vdf["ticker_b"].isin(unseen)
    assert int(leg_unseen.sum()) == n_log, (int(leg_unseen.sum()), n_log)
    log(f"[VDOC] unseen coins {sorted(unseen)} (from the score log): {n_log:,} events, matches the log's count")
    out["unseen_coin_picks"] = dict(n_events=int(leg_unseen.sum()), n_picks_q1=int((leg_unseen & q1v).sum()), coins=sorted(unseen))
    out["event_share_by_z"] = {"vault": {k: float(v) for k, v in vdf["zb"].value_counts(normalize=True).sort_index().items()},
                                "test": {k: float(v) for k, v in tdf["zb"].value_counts(normalize=True).sort_index().items()}}
    out["pick_share_by_dir"] = {"vault": float((vdf.loc[q1v, "z"] > 0).mean()), "test": float((tdf.loc[q1t, "z"] > 0).mean())}
    return out, vdf, tdf


# ---------------------------------------------------------------------------
# R4: horizons (same definitions as s1_profit1_horizons.py Q1, Q2, Q4)
# ---------------------------------------------------------------------------
def horizon_tables(df, trades):
    """df: a frame with the common columns; trades: {(q, fee): trades indexed by event_id with net_over_notional}."""
    res = {}
    for q in QS:
        picks = df[df[f"pick_{q}"]].copy()
        for h in (2, 5, 10):
            picks[f"qt_{h}h"] = HZ.quintile(picks[f"cal_{h}h"])
        res[str(q)] = {"n_picks": int(len(picks)), "levels": {f"{h}h": int(picks[f"cal_{h}h"].nunique()) for h in (2, 5, 10)}}
        for h in (2, 5):
            rows = []
            for b in range(1, 6):
                s = picks[picks[f"qt_{h}h"] == b]
                reachers = s.loc[s["reach_10h"] == 1, "minutes_to_mu"].dropna()
                row = dict(quintile=b, n=int(len(s)), mean_cal_p=float(s[f"cal_{h}h"].mean()), reach_h=float(s[f"reach_{h}h"].mean()),
                           reach_10h=float(s["reach_10h"].mean()), mtm_median=float(reachers.median()) if len(reachers) else None)
                for fee in ("maker", "taker"):
                    t = trades[(q, fee)]
                    tt = t.loc[t.index.intersection(s["event_id"].to_numpy())]
                    row[f"{fee}_n_traded"] = int(len(tt))
                    if len(tt):
                        row[f"{fee}_win_mu"] = float((tt["exit_reason"] == "mu").mean())
                        row[f"{fee}_share_profitable"] = float((tt["net"] > 0).mean())
                        row[f"{fee}_mean_net_usd"] = float(tt["net"].mean())
                        row[f"{fee}_mean_net_over_notional"] = float(tt["net_over_notional"].mean())
                        row[f"{fee}_mean_hold_min"] = float(tt["holding_minutes"].mean())
                        row[f"{fee}_open_at_2h"] = float((tt["holding_minutes"] > 120).mean())
                        row[f"{fee}_open_at_5h"] = float((tt["holding_minutes"] > 300).mean())
                rows.append(row)
            res[str(q)][f"by_p{h}h"] = rows
        for fee in ("maker", "taker"):
            t = trades[(q, fee)]
            res[str(q)][f"all_traded_{fee}"] = dict(
                n=int(len(t)), win_mu=float((t["exit_reason"] == "mu").mean()), share_profitable=float((t["net"] > 0).mean()),
                mean_net_usd=float(t["net"].mean()), open_at_2h=float((t["holding_minutes"] > 120).mean()),
                open_at_5h=float((t["holding_minutes"] > 300).mean()))
    return res


def vault_trades_for_horizons():
    tr = {}
    for q in QS:
        for fee in ("maker", "taker"):
            t = pd.read_parquet(os.path.join(TRADE_DIR, f"trades_q{q}_stopnone_fee{fee}_vault_open10.parquet"))
            assert (t["stop"] == "none").all() and (t["fee_mode"] == fee).all() and (t["q"] == q).all()
            t["net_over_notional"] = t["net"] / t["notional"]
            tr[(q, fee)] = t.set_index("event_id")
    return tr


def test_trades_for_horizons():
    tr = {}
    for q in QS:
        for fee in ("maker", "taker"):
            t = pd.read_parquet(os.path.join(TRADE_DIR, f"trades_q{q}_stopnone_fee{fee}.parquet"))
            assert (t["stop"] == "none").all() and (t["fee_mode"] == fee).all() and (t["q"] == q).all()
            t["net_over_notional"] = t["net"] / t["notional"]
            tr[(q, fee)] = t.set_index("event_id")
    return tr


# ---------------------------------------------------------------------------
# R5 / R6: trading
# ---------------------------------------------------------------------------
def daily_equity(me, anchor, nominal_end):
    day_end = max((me["time"].max().normalize() + pd.Timedelta(days=1)) if len(me) else nominal_end, nominal_end)
    days = pd.date_range(anchor, day_end, freq="D", inclusive="left")
    s = me.set_index("time")["account_value"].resample("D").last().reindex(days)
    s.loc[anchor] = START_EQUITY
    return s.ffill()


def drawdown_episodes(d, top=3):
    run_max = d.cummax()
    under = d < run_max
    eps, i, n = [], 0, len(d)
    idx = list(d.index)
    while i < n:
        if not under.iloc[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and under.iloc[j + 1]:
            j += 1
        peak_day = idx[i - 1] if i > 0 else idx[0]
        peak = float(run_max.iloc[i])
        seg = d.iloc[i:j + 1]
        bottom_day = seg.idxmin()
        rec = idx[j + 1] if j + 1 < n else None
        eps.append(dict(peak_day=str(peak_day.date()), bottom_day=str(bottom_day.date()),
                        recovery_day=str(rec.date()) if rec is not None else "not recovered", depth=float(seg.min() / peak - 1),
                        depth_usd=float(seg.min() - peak),
                        days_underwater=int(j - i + 1)))
        i = j + 1
    eps = sorted(eps, key=lambda e: e["depth"])
    return eps if top is None else eps[:top]


def z_bucket(z):
    return pd.cut(pd.Series(z).abs(), ZB_EDGES, right=False, labels=ZB_LABELS)


def run_record(rep, key, trades, z_by_event):
    r = rep["runs"][key]
    assert set(r["skip_counts"]) <= {"book_full", "margin", "min_order"}, r["skip_counts"]
    rec = dict(q=r["q"], stop=r["stop"], fee=r["fee"], n_trades=r["n_trades"], final_equity=r["final_equity"],
               net_pnl=r["final_equity"] - START_EQUITY, total_return=r["total_return"], cagr=r["cagr"], gross=r["total_gross"],
               fees=r["total_fee"], fee_share=r["fee_share_of_gross"], funding_paid=r["total_funding_paid"],
               funding_received=r["total_funding_received"], win_rate=r["win_rate"], mean_win=r["mean_win"], mean_loss=r["mean_loss"],
               profit_factor=r["profit_factor"], max_dd_pct=r["max_drawdown"]["max_dd_pct"], max_dd_usd=r["max_drawdown"]["max_dd_usd"],
               sharpe=r["sharpe"], sortino=r["sortino"], best_day=r["best_day"], worst_day=r["worst_day"],
               share_positive_days=r["share_positive_days"], mean_hold_min=r["mean_holding_minutes"], stop_share=r["stop_share"],
               timeout_share=r["timeout_share"], liquidation_share=r["liquidation_share"], n_liquidations=r["n_liquidations"],
               skip_book_full=r["skip_counts"].get("book_full", 0), skip_margin=r["skip_counts"].get("margin", 0),
               skip_min_order=r["skip_counts"].get("min_order", 0), peak_margin=r["peak_margin_used"],
               mean_open=r["mean_open_positions"], min_dist_liq=r["distance_to_liquidation_ratio"]["min"], mean_net=r["mean_net"])
    t = trades
    rec["mean_leverage"] = float(t["leverage"].mean()) if len(t) else None
    rec["mean_notional"] = float(t["notional"].mean()) if len(t) else None
    z = z_by_event.reindex(t["event_id"]).to_numpy()
    assert not np.isnan(z).any(), "a traded event has no z"
    short = z > 0
    for name, m in (("short", short), ("long", ~short)):
        sub = t[m]
        rec[f"n_{name}"] = int(len(sub))
        rec[f"win_{name}"] = float((sub["exit_reason"] == "mu").mean()) if len(sub) else None
        rec[f"net_{name}"] = float(sub["net"].sum())
    return rec


def load_tag(tag, z_by_event):
    suffix, nr, er, max_open = TAGS[tag]
    num = json.load(open(os.path.join(LOG_DIR, nr)))
    eng = json.load(open(os.path.join(LOG_DIR, er)))
    assert eng["config"]["max_open"] == max_open and eng["config"]["slippage_spread_share"] == 0.0
    recs_, curves, eq_cache = {}, {}, {}
    for q in QS:
        for stop in STOPS:
            for fee in FEES:
                key = run_key(q, stop, fee)
                t = pd.read_parquet(os.path.join(TRADE_DIR, f"trades_{key}{suffix}.parquet"))
                recs_[key] = run_record(num, key, t, z_by_event)
                eq_cache[key] = t
    return num, recs_, eq_cache


def best_detail(tag, key, num, trades, z_by_event, anchor, nominal_end):
    suffix = TAGS[tag][0]
    me = pd.read_parquet(os.path.join(TRADE_DIR, f"minute_equity_{key}{suffix}.parquet")).sort_values("time")
    d = daily_equity(me, anchor, nominal_end)
    eng_final = json.load(open(os.path.join(LOG_DIR, TAGS[tag][2])))["runs"][key]["final_equity"]
    assert abs(float(d.iloc[-1]) - eng_final) < 1e-6, f"{tag} {key}: daily series final {d.iloc[-1]} != engine {eng_final}"
    pnl = d.diff().dropna()
    monthly = pnl.groupby(pnl.index.strftime("%Y-%m")).agg(["sum", "count"])
    r = num["runs"][key]
    eps_all = drawdown_episodes(d, top=None)
    dds = eps_all[:3]
    mdd = r["max_drawdown"]
    # the report's max_dd_pct is the deepest episode in PERCENT; its bottom / start / recovery dates belong to the deepest
    # episode in USD (numbers_gen.max_drawdown uses dd_usd.idxmin()), which can be a different episode
    usd = min(eps_all, key=lambda e: e["depth_usd"])
    assert abs(dds[0]["depth"] - mdd["max_dd_pct"]) < 1e-9, (dds[0]["depth"], mdd["max_dd_pct"])
    assert abs(usd["depth_usd"] - mdd["max_dd_usd"]) < 1e-6, (usd["depth_usd"], mdd["max_dd_usd"])
    assert usd["bottom_day"] == mdd["bottom"], (usd["bottom_day"], mdd["bottom"])
    assert usd["recovery_day"] == (mdd["recovery"] or "not recovered"), (usd["recovery_day"], mdd["recovery"])
    assert abs(float(monthly["sum"].sum()) - (float(d.iloc[-1]) - START_EQUITY)) < 1e-6
    z = z_by_event.reindex(trades["event_id"]).to_numpy()
    tz = trades.assign(zb=z_bucket(z).to_numpy(), dirn=np.where(z > 0, "short spread (z>0)", "long spread (z<0)"))
    def grp(col):
        g = tz.groupby(col, observed=True).agg(n=("net", "size"), net=("net", "sum"), mean_net=("net", "mean"),
                                               win_mu=("exit_reason", lambda s: float((s == "mu").mean())))
        return recs(g.reset_index().rename(columns={col: "group"}).astype({"group": str}))
    return dict(tag=tag, key=key, daily_equity=[[str(i.date()), float(v)] for i, v in d.items()],
                monthly=[dict(month=m, pnl=float(row["sum"]), days=int(row["count"])) for m, row in monthly.iterrows()],
                top_coins=r["top10_coins"], bottom_coins=r["bottom10_coins"], top_pairs=r["top10_pairs"], bottom_pairs=r["bottom10_pairs"],
                by_z=grp("zb"), by_dir=grp("dirn"), drawdowns=dds,
                max_drawdown_report=r["max_drawdown"], exit_reasons={k: int(v) for k, v in trades["exit_reason"].value_counts().items()})


def charts(out, vdf_calib, rank, best_vault, best_test_equity):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(CHART_DIR, exist_ok=True)
    paths = {}
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, h in zip(axes, ("2", "5", "10")):
        rows = [r for r in vdf_calib[h]["rows"] if r["bucket"].startswith("decile")]
        ax.plot([r["cal"] for r in rows], [r["actual"] for r in rows], "o-", label="vault (calibrated vs actual)")
        ax.plot([r["t_cal"] for r in rows], [r["t_actual"] for r in rows], "s--", label="test months (isotonic vs actual)")
        lim = max(max(r["cal"], r["actual"], r["t_cal"], r["t_actual"]) for r in rows) * 1.05
        ax.plot([0, lim], [0, lim], color="gray", lw=0.8)
        ax.set_title(f"{h} h by decile"); ax.set_xlabel("mean calibrated p"); ax.set_ylabel("actual reach rate")
    axes[0].legend(fontsize=7); fig.tight_layout()
    paths["calibration"] = os.path.join(CHART_DIR, "calibration_deciles.png"); fig.savefig(paths["calibration"], dpi=120); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    vm = rank["by_month"]["vault"]; tm = rank["by_month"]["test"]
    ax.bar(range(len(tm)), [r["lift"] for r in tm], color="#9ab", label="test months (by fold)")
    ax.bar([len(tm) + 1 + i for i in range(len(vm))], [r["lift"] for r in vm], color="#c63", label="vault (by UTC month)")
    ax.set_xticks(list(range(len(tm))) + [len(tm) + 1 + i for i in range(len(vm))])
    ax.set_xticklabels([r["start"][:7] for r in tm] + [r["group"] for r in vm], rotation=45, fontsize=7)
    ax.set_ylabel("lift, Rule A picks q=1%"); ax.legend(fontsize=7); fig.tight_layout()
    paths["lift_month"] = os.path.join(CHART_DIR, "lift_by_month.png"); fig.savefig(paths["lift_month"], dpi=120); plt.close(fig)
    for tag, d in best_vault.items():
        fig, ax = plt.subplots(figsize=(8, 3.8))
        for label, det in d.items():
            vals = [v for _, v in det["daily_equity"]]
            ax.plot(range(len(vals)), vals, label=label)
        ax.axhline(START_EQUITY, color="gray", lw=0.8, ls=":")
        ax.set_xlabel("days since the window start"); ax.set_ylabel("account value ($)"); ax.legend(fontsize=7)
        ax.set_title(f"{tag}: daily account value"); fig.tight_layout()
        paths[f"equity_{tag}"] = os.path.join(CHART_DIR, f"equity_{tag}.png"); fig.savefig(paths[f"equity_{tag}"], dpi=120); plt.close(fig)
    return paths


def main():
    t0 = time.time()
    log(f"[VDOC] sha256 s1_vault_docx_data.py {VR.sha256(__file__)}; start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC")
    rng = np.random.default_rng(SEED)
    vdf = vault_frame()
    tdf = test_frame()
    rank, vdf, tdf = rank_section(vdf, tdf, rng)
    iso = json.load(open(os.path.join(LOG_DIR, "s1_vault_iso_2h5h.json")))
    calib = iso["calibration"]
    # R4 horizons
    hz = {"vault": horizon_tables(vdf, vault_trades_for_horizons()), "test": horizon_tables(tdf, test_trades_for_horizons())}
    log("[VDOC] horizons built (vault and test)")
    # R5 trading
    z_vault = vdf.set_index("event_id")["z"]
    z_test = tdf.set_index("event_id")["z"]
    tags, trade_cache, nums = {}, {}, {}
    for tag in TAGS:
        z = z_vault if tag.startswith("vault") else z_test
        nums[tag], tags[tag], trade_cache[tag] = load_tag(tag, z)
        log(f"[VDOC] {tag}: 24 runs read; above $1,000: {sum(1 for r in tags[tag].values() if r['final_equity'] > START_EQUITY)}")
    # R6 best configs (vault tags) + test counterparts
    anchor_v = H.VAULT_START.normalize() - pd.Timedelta(days=1)
    last_t0 = pd.read_parquet(VR.PICKS, columns=["t0"])["t0"].max()
    nominal_v = last_t0.normalize() + pd.Timedelta(days=1)
    anchor_t = H.TEST_BLOCK_STARTS[1].normalize() - pd.Timedelta(days=1)
    nominal_t = H.TEST_BLOCK_ENDS[7].normalize()
    best = {}
    best_for_chart = {}
    ref_key = run_key(0.01, "none", "maker")
    for vt, tt in (("vault_open10", "test_open10"), ("vault_open20", "test_open20")):
        top = max(tags[vt], key=lambda k: tags[vt][k]["final_equity"])
        keys = [("best", top)] + ([("reference", ref_key)] if ref_key != top else [])
        best[vt] = {}
        best_for_chart[vt] = {}
        for role, k in keys:
            det = best_detail(vt, k, nums[vt], trade_cache[vt][k], z_vault, anchor_v, nominal_v)
            det["role"] = role
            det["test_counterpart"] = tags[tt][k]
            det["test_drawdowns"] = None
            tdet = best_detail(tt, k, nums[tt], trade_cache[tt][k], z_test, anchor_t, nominal_t)
            det["test_drawdowns"] = tdet["drawdowns"]
            det["test_daily_equity"] = tdet["daily_equity"]
            best[vt][k] = det
            best_for_chart[vt][f"vault {k} ({role})"] = det
            best_for_chart[vt][f"test months {k} ({role})"] = tdet
            log(f"[VDOC] best detail {vt} {k} ({role}): final {tags[vt][k]['final_equity']:.2f}; drawdowns {det['drawdowns']}")
    paths = charts({}, calib, rank, best_for_chart, None)
    # R7 side by side (all metrics, 24 runs x 4 columns)
    metric_keys = [k for k in next(iter(tags["vault_open10"].values())) if k not in ("q", "stop", "fee")]
    sbs = {m: {k: [tags[t][k][m] for t in TAGS] for k in tags["vault_open10"]} for m in metric_keys}
    # setup block
    model = json.load(open(os.path.join(LOG_DIR, "s1_prevault_model.json")))
    picks_settings = json.load(open(os.path.join(LOG_DIR, "s1_vault_picks_settings.json")))
    eng_v = json.load(open(os.path.join(LOG_DIR, TAGS["vault_open10"][2])))
    setup = dict(window_start=str(H.VAULT_START), last_event=str(vdf["t0"].max()), n_events=int(len(vdf)), n_coins=int(pd.concat([vdf["ticker_a"], vdf["ticker_b"]]).nunique()),
                 n_days=int(vdf["t0"].dt.floor("D").nunique()), engine_window_days=win_txt(nums["vault_open10"]), test_engine_window_days=win_txt(nums["test_open10"]), picks={str(q): int(vdf[f"pick_{q}"].sum()) for q in QS},
                 cutoffs=picks_settings["cutoffs"], pcal=dict(pool_folds=picks_settings["pool_folds"], n_fit=picks_settings["n_fit"], n_dropped=picks_settings["n_dropped"],
                                                              guard_inclusive=picks_settings["guard_inclusive"]),
                 iso_settings=json.load(open(os.path.join(LOG_DIR, "s1_vault_iso_2h5h_settings.json"))),
                 model_settings=model["settings"], model_fit={k: v for k, v in model["fit_result"].items() if isinstance(v, (int, float, str, bool))},
                 model_known_gaps=model["known_gaps"], engine_config=eng_v["config"],
                 test_window=[str(H.TEST_BLOCK_STARTS[1].date()), str(H.TEST_BLOCK_ENDS[7].date())])
    log(f"[VDOC] setup: {setup['n_events']:,} events, {setup['n_coins']} coins, {setup['n_days']} days; picks {setup['picks']}")

    # R8 sentences
    def above(tag): return sum(1 for r in tags[tag].values() if r["final_equity"] > START_EQUITY)
    v_top1 = rank["lift_sets"]["vault"][0]
    t_top1 = [r for r in rank["lift_sets"]["test"] if r["label"].startswith("S1-D top 1%")][0]
    STOP_NAME = {"0p5": "stop 0.5 sigma", "1p0": "stop 1 sigma", "2p0": "stop 2 sigma", "none": "no stop"}
    lab = lambda r: f"q {r['q'] * 100:g}% / {STOP_NAME[r['stop']]} / {r['fee']} fees"
    def cmp(a, b, up="higher", down="lower", same="equal"): return up if a > b else (down if a < b else same)
    q1 = [r for r in calib["10"]["rows"] if r["bucket"] == "Rule A picks q=0.01"][0]
    best_o10 = max(tags["vault_open10"].values(), key=lambda r: r["final_equity"])
    best_o20 = max(tags["vault_open20"].values(), key=lambda r: r["final_equity"])
    worst_o20 = min(tags["vault_open20"].values(), key=lambda r: r["final_equity"])
    ref10, ref20 = tags["vault_open10"][ref_key], tags["vault_open20"][ref_key]
    maker_above = {t: sum(1 for r in tags[t].values() if r["fee"] == "maker" and r["final_equity"] > START_EQUITY) for t in TAGS}
    taker_above = {t: sum(1 for r in tags[t].values() if r["fee"] == "taker" and r["final_equity"] > START_EQUITY) for t in TAGS}
    assert any(g.startswith("2a") and "FAILED" in g and "ACCEPTED" in g for g in setup["model_known_gaps"]), "the model JSON no longer records the 2a failure and its acceptance"
    summary = [
        f"The vault is {setup['n_events']:,} pair events from {setup['window_start'][:10]} to {setup['last_event'][:10]} ({setup['n_coins']} coins). Days: {setup['n_days']} calendar days contain events; the engine's annualisation window, which counts whole days from the vault start to the last event day, is {setup['engine_window_days']} days. "
        f"The model, the pick rule, the 10 h probability calibration and the backtest settings were fixed before any vault label or outcome was read, and nothing in them was changed afterwards. "
        f"Two deviations are on record: the p_cal pool used folds {picks_settings['pool_folds'][0]}-{picks_settings['pool_folds'][-1]} with the guard t0 + 10 h {'<=' if picks_settings['guard_inclusive'] else '<'} vault start (a ruling made after the vault was scored and before any label was read, differing from the brief's wording), "
        f"and the refit's reproduction check on fold 0 (2a) missed its preset tolerance and was accepted by the user as solver-level agreement (see Known gaps). "
        f"The 2 h and 5 h calibration maps and this report were added afterwards at the user's request; the maps are fitted on search-period data only.",
        f"Ranking: the vault's own top 1% by p_10h has a lift of {v_top1['lift']:.4f} (interval {v_top1['lo']:.4f} to {v_top1['hi']:.4f}). The comparator is S1-D's top 1% over folds 0-7 (the search-period out-of-fold predictions), which had "
        f"{t_top1['lift']:.4f} ({t_top1['lo']:.4f} to {t_top1['hi']:.4f}). The vault point estimate is {cmp(v_top1['lift'], t_top1['lift'], 'above', 'below', 'equal to')} the S1-D figure "
        f"(over folds 1-7 only, the test months used in the trading tables, the n-weighted value from the same file is {t_top1['lift_folds_1_7']:.4f}, no interval available). The vault and S1-D (folds 0-7) intervals {'overlap' if (v_top1['lo'] <= t_top1['hi'] and t_top1['lo'] <= v_top1['hi']) else 'do not overlap'}"
        f"{', so the difference between the two point estimates is not established by these intervals' if (v_top1['lo'] <= t_top1['hi'] and t_top1['lo'] <= v_top1['hi']) else ''}, "
        f"and the vault interval is {'wholly above' if v_top1['lo'] > 0 else 'not wholly above'} zero.",
        f"Probabilities: for the Rule A q=1% picks the model's raw p_10h averages {q1['raw']:.4f}, the calibrated p {q1['cal']:.4f}, and the actual reach rate is {q1['actual']:.4f}.",
        f"Trading: {above('vault_open10')} of 24 runs ended above the $1,000 start at max_open 10 and {above('vault_open20')} of 24 at max_open 20; in the test months the counts were "
        f"{above('test_open10')} and {above('test_open20')}. The engine window is {setup['engine_window_days']} days for the vault and {setup['test_engine_window_days']} days for the test period, "
        f"so equity and return are not per-month comparable.",
        f"Reference run (q 1%, no stop, maker fees): vault open10 ends at ${ref10['final_equity']:,.2f}, open20 at ${ref20['final_equity']:,.2f}; the same runs in the test months ended at "
        f"${tags['test_open10'][ref_key]['final_equity']:,.2f} and ${tags['test_open20'][ref_key]['final_equity']:,.2f}.",
        f"Best vault run at max_open 10: {lab(best_o10)}, ${best_o10['final_equity']:,.2f}; at max_open 20: {lab(best_o20)}, "
        f"${best_o20['final_equity']:,.2f}. Worst at max_open 20: {lab(worst_o20)}, ${worst_o20['final_equity']:,.2f}.",
        f"Liquidations in the 48 vault runs: {sum(r['n_liquidations'] for t in ('vault_open10', 'vault_open20') for r in tags[t].values())}. Slippage is set to zero, so results are an upper bound.",
    ]
    findings = [
        f"Ranking signal: lift at the vault's own top 1% / 2% / 5% = " + " / ".join(f"{r['lift']:.4f}" for r in rank["lift_sets"]["vault"][:3]) +
        "; S1-D over folds 0-7 " + " / ".join(f"{r['lift']:.4f}" for r in rank["lift_sets"]["test"][-3:]) + " (over folds 1-7: " + " / ".join(f"{r['lift_folds_1_7']:.4f}" for r in rank["lift_sets"]["test"][-3:]) + ").",
        f"By month the vault lift (Rule A q=1%) is " + ", ".join(f"{r['group']}: {r['lift']:.4f}" for r in rank["by_month"]["vault"]) + f"; the test folds range from "
        f"{min(r['lift'] for r in rank['by_month']['test']):.4f} to {max(r['lift'] for r in rank['by_month']['test']):.4f}.",
        f"Concentration by coin: the q=1% picks touch {rank['coin_summary']['vault']['n_coins_with_picks']} coins; the top 5 coins carry {rank['coin_summary']['vault']['share_top5']:.1%} of pick legs and the top 10 carry "
        f"{rank['coin_summary']['vault']['share_top10']:.1%} (test months: {rank['coin_summary']['test']['share_top5']:.1%} and {rank['coin_summary']['test']['share_top10']:.1%}).",
        f"Direction: {rank['pick_share_by_dir']['vault']:.1%} of the vault q=1% picks short the spread (z > 0) against {rank['pick_share_by_dir']['test']:.1%} in the test months.",
        f"Maker versus taker: runs above $1,000 at max_open 10 are {maker_above['vault_open10']} of 12 with maker fees and {taker_above['vault_open10']} of 12 with taker fees in the vault "
        f"({maker_above['test_open10']} and {taker_above['test_open10']} in the test months); at max_open 20: {maker_above['vault_open20']} and {taker_above['vault_open20']} "
        f"({maker_above['test_open20']} and {taker_above['test_open20']}).",
        f"Unseen coins: {rank['unseen_coin_picks']['n_events']:,} vault events involve coins the model never saw ({', '.join(rank['unseen_coin_picks']['coins'])}); {rank['unseen_coin_picks']['n_picks_q1']} of the q=1% picks are among them.",
    ]
    result = dict(meta=dict(script_sha256=VR.sha256(__file__), generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), seed=SEED,
                            n_resamples=N_RESAMPLES, level=LEVEL, z_edges=ZB_LABELS),
                  summary=summary, findings=findings, setup=setup, rank=rank, calib=calib, horizons=hz, trading=tags,
                  best=best, side_by_side=sbs, side_by_side_cols=list(TAGS), charts=paths,
                  runs_above_start={t: above(t) for t in TAGS})
    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (float, np.floating)):
            return None if not np.isfinite(o) else float(o)      # NaN / inf are not valid JSON for the renderer
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return o
    json.dump(clean(result), open(OUT_JSON, "w"), indent=1, default=str)
    for s in summary + findings:
        log(f"[VDOC] TEXT: {s}")
    log(f"[VDOC] wrote {OUT_JSON} (sha256 {VR.sha256(OUT_JSON)})  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
