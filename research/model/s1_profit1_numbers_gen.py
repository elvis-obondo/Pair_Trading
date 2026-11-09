"""HL-PROFIT1: the report-tables generator (brief docs/prompts/HL_PROFIT1_LIVE_PICKS.md, "Report"
section). Reads ONLY the artifacts s1_profit1.py already wrote (research/model/logs/profit1/
trades_*.parquet, minute_equity_*.parquet, skips_*.parquet, liquidations_*.parquet, and
research/model/logs/s1/s1_profit1_report.json) -- no new simulation, no new rule. Every number in the
NUMBERS.md section this script writes is printed by this script; nothing is typed by hand (CLAUDE.md).
Writes the actual NUMBERS.md section (markdown) to research/dislocation_model/logs/
s1_profit1_numbers_section.md, to be pasted into NUMBERS.md by hand (S1-H's own hand-off pattern) --
plus the full JSON (s1_profit1_numbers_report.json) and 6 equity PNGs.

    python -u research/model/s1_profit1_numbers_gen.py > research/model/logs/s1/s1_profit1_numbers_gen.log

Checker's post-run notes (round 1), applied here (not in the engine):
(1) Fallback/slippage counts carry no dollars at slippage_spread_share=0.0 (the reported run) -- left
    out of the report entirely; the engine's own log is the receipt for anyone who wants them.
(2) "Most runs net profitable" is a count this script prints (n_runs_above_start), not an eyeballed
    claim.
(3) Known gaps wording is exactly: "slippage excluded by the user's choice (legs are small); costs are
    a lower bound and results an upper bound (optimistic)." -- guarded (N6 below) by reading
    report.json's own CONFIG and asserting slippage_spread_share == 0.0 before writing it, so a 0.5
    output could never carry this line.
(4) The per-run tables are primary. A pooled-over-24-runs total is printed ONCE, labelled
    "cost-share diagnostic (OVERLAPPING accounts, not a combined P&L)" -- the 24 runs share the same
    picks' price history, so summing them is not a portfolio total.
(5) This script and its output stay under research/model/ (tracked); the ALSO-tracked
    research/model/diagnostics/ holds a second, sha256-identical copy of the exploratory diagnostic
    scripts/logs that already lived under the gitignored research/model/logs/profit1/diagnostics/ --
    both copies exist (checker N7: the gitignored originals are kept, not deleted; deleting local data
    needs the user's own yes).

Checker's round-2 findings (numbered N1-N7 + minors), applied here:
N1. This script now writes the actual NUMBERS.md markdown section (not just JSON/log/PNGs).
N2. final_equity is asserted against report.json's own final_equity (1e-6) for every run; the daily
    equity series' day range is extended per-run to the LAST minute_equity row (covers the last exit,
    even past fold 7's nominal end), and an anchor day (DAY0 - 1) at START_EQUITY is added so the first
    real day's P&L is not dropped by diff()/pct_change().
N3. "minimum distance to liquidation per day" is now the RATIO account_value / maintenance (not the USD
    difference), as the brief states; reports the per-day-minimum series' own min, median and the date
    of the min.
N4. The monthly P&L table is each fold's TOTAL equity change (USD and %), not the mean daily change.
    n_months_positive uses the total.
N5. Funding paid and funding received are each reported as USD and as a share of gross (slippage stays
    $0, correctly, at share=0.0).
N6. The known-gaps "slippage excluded" line is guarded: read report.json's CONFIG and ASSERT
    slippage_spread_share == 0.0 before writing it.
N7. Docstring (5) corrected above -- both copies of the diagnostics exist, not "not duplicated".
Minor fixes: the liquidation table is printed (date/positions_closed/loss) even when empty; the coin
split is labelled "net of trades involving the coin (each trade counted for both coins)"; CAGR is
labelled with its day count N; Sharpe/Sortino are labelled "annualised, sqrt(365)"; the EV check notes
fold 1 is never scored (no earlier test month to fit on).

Planner ruling 2026-11-09: the day-block bootstrap interval on mean net (not in the brief's report
list) is dropped entirely -- no function, no CONFIG values, no report fields.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
import harness as H  # noqa: E402

PROFIT_DIR = os.path.join(HERE, "logs", "profit1")
LOG_DIR = os.path.join(HERE, "logs", "s1")
NUMBERS_DIR = os.path.join(ROOT, "research", "dislocation_model", "logs")
QS = (0.01, 0.005, 0.001)
STOPS = ("0p5", "1p0", "2p0", "none")
FEES = ("taker", "maker")
START_EQUITY = 1000.0
DAY0 = H.TEST_BLOCK_STARTS[1].normalize()
ANCHOR_DAY = DAY0 - pd.Timedelta(days=1)
DAY_END_NOMINAL = H.TEST_BLOCK_ENDS[7].normalize()


def log(msg):
    print(msg, flush=True)


def run_key(q, stop, fee):
    return f"q{q}_stop{stop}_fee{fee}"


def load_run(q, stop, fee):
    key = run_key(q, stop, fee)
    trades = pd.read_parquet(os.path.join(PROFIT_DIR, f"trades_{key}.parquet"))
    me = pd.read_parquet(os.path.join(PROFIT_DIR, f"minute_equity_{key}.parquet")).sort_values("time")
    sk = pd.read_parquet(os.path.join(PROFIT_DIR, f"skips_{key}.parquet"))
    liq = pd.read_parquet(os.path.join(PROFIT_DIR, f"liquidations_{key}.parquet"))
    return trades, me, sk, liq


def daily_equity_series(me):
    """checker N2: the day range runs from ANCHOR_DAY (DAY0 - 1, pinned to START_EQUITY so the first
    real day's diff()/pct_change() is not dropped) to the LAST minute_equity row's own day (covers the
    last exit even if it lands after fold 7's nominal end -- a 600-minute hold starting just before the
    gap day runs past it). Zero-activity days in between are forward-filled (brief: "zero-trade days
    counted")."""
    day_end = (me["time"].max().normalize() + pd.Timedelta(days=1)) if len(me) else DAY_END_NOMINAL
    day_end = max(day_end, DAY_END_NOMINAL)
    days = pd.date_range(ANCHOR_DAY, day_end, freq="D", inclusive="left")
    if len(me) == 0:
        return pd.Series(START_EQUITY, index=days)
    s = me.set_index("time")["account_value"]
    daily_last = s.resample("D").last()
    daily = daily_last.reindex(days)
    daily.loc[ANCHOR_DAY] = START_EQUITY
    daily = daily.ffill()
    return daily


def max_drawdown(daily_eq):
    """checker N9: runs on the FULL series, anchor day included, so a first-day fall below START_EQUITY
    is itself a drawdown from the $1,000 peak (slicing to DAY0: before computing cummax() would have
    hidden that)."""
    d = daily_eq
    running_max = d.cummax()
    dd_usd = d - running_max
    dd_pct = dd_usd / running_max
    bottom_idx = dd_usd.idxmin()
    dd_usd_min = float(dd_usd.min())
    dd_pct_min = float(dd_pct.min())
    peak_before = running_max.loc[bottom_idx]
    start_idx = d[:bottom_idx][d[:bottom_idx] == peak_before].index.max()
    after = d.loc[bottom_idx:]
    recovered = after[after >= peak_before]
    recovery_idx = recovered.index.min() if len(recovered) else None
    underwater = dd_usd < 0
    longest = 0
    cur = 0
    for v in underwater:
        cur = cur + 1 if v else 0
        longest = max(longest, cur)
    return dict(max_dd_usd=dd_usd_min, max_dd_pct=dd_pct_min,
                start=str(start_idx.date()) if pd.notna(start_idx) else None,
                bottom=str(bottom_idx.date()), recovery=str(recovery_idx.date()) if recovery_idx is not None else None,
                longest_underwater_days=int(longest))


def sharpe_sortino(daily_eq):
    """Annualised, sqrt(365), on daily returns from DAY0 on. checker N9: pct_change() runs on the FULL
    series FIRST (so DAY0's own return, against the anchor day, is computed), THEN sliced to DAY0: --
    slicing first would have thrown day 1's return away before it was ever computed."""
    ret = daily_eq.pct_change().loc[DAY0:].dropna()
    n = len(ret)
    if n < 2 or ret.std(ddof=1) == 0:
        sharpe = float("nan")
    else:
        sharpe = float(ret.mean() / ret.std(ddof=1) * np.sqrt(365))
    downside = ret[ret < 0]
    if len(downside) < 2 or downside.std(ddof=1) == 0:
        sortino = float("nan")
    else:
        sortino = float(ret.mean() / downside.std(ddof=1) * np.sqrt(365))
    return sharpe, sortino, n


def fold_of(ts):
    ts = pd.Timestamp(ts)
    for k in range(1, 8):
        if H.TEST_BLOCK_STARTS[k] <= ts < H.TEST_BLOCK_ENDS[k]:
            return k
    return None


def per_run_report(q, stop, fee, engine_report):
    trades, me, sk, liq = load_run(q, stop, fee)
    n_trades = len(trades)
    daily_eq = daily_equity_series(me)
    final_equity = float(daily_eq.iloc[-1])

    # checker N2: assert against the engine's own report.json, not just the resampled daily series
    engine_final = engine_report["runs"][run_key(q, stop, fee)]["final_equity"]
    assert abs(final_equity - engine_final) < 1e-6, (
        f"{run_key(q, stop, fee)}: generator final_equity {final_equity} != engine report.json "
        f"final_equity {engine_final}")

    total_return = final_equity / START_EQUITY - 1
    n_days_cagr = (daily_eq.index[-1] - DAY0).days
    cagr = (final_equity / START_EQUITY) ** (365.0 / n_days_cagr) - 1 if final_equity > 0 and n_days_cagr > 0 else float("nan")

    # checker N9: diff() on the FULL series first (so DAY0's own change, from the anchor, is computed),
    # THEN sliced to DAY0: -- the opposite order drops day 1's P&L before it is ever computed.
    daily_ret = daily_eq.diff().loc[DAY0:]
    daily_pnl_mean, daily_pnl_median = float(daily_ret.mean()), float(daily_ret.median())
    share_pos_days = float((daily_ret > 0).mean())
    worst_day, best_day = float(daily_ret.min()), float(daily_ret.max())

    dd = max_drawdown(daily_eq)
    sharpe, sortino, n_days_sharpe = sharpe_sortino(daily_eq)

    # checker N4: each fold's TOTAL equity change (USD and %), not the mean daily change. All 7
    # TEST_BLOCK_STARTS/ENDS fall exactly at 00:00:00 UTC (not mid-day).
    monthly = {}
    for k in range(1, 8):
        mask = (daily_eq.index >= H.TEST_BLOCK_STARTS[k]) & (daily_eq.index < H.TEST_BLOCK_ENDS[k])
        sub = daily_eq[mask]
        if len(sub) < 1:
            monthly[k] = dict(n_days=0, total_pnl_usd=None, total_pnl_pct=None)
            continue
        start_eq = daily_eq[daily_eq.index < H.TEST_BLOCK_STARTS[k]].iloc[-1] if (daily_eq.index < H.TEST_BLOCK_STARTS[k]).any() else sub.iloc[0]
        end_eq = sub.iloc[-1]
        monthly[k] = dict(n_days=int(mask.sum()), total_pnl_usd=float(end_eq - start_eq),
                           total_pnl_pct=float(end_eq / start_eq - 1) if start_eq else None)
    n_months_positive = sum(1 for v in monthly.values() if v["total_pnl_usd"] is not None and v["total_pnl_usd"] > 0)

    # checker N8: days outside every fold's mask -- the exit spill after fold 7's nominal end (a
    # 600-minute hold starting just before the gap day runs past it) -- are not in any fold's total, so
    # sum(folds) alone does not reconcile with final_equity - START_EQUITY. Computed independently (not
    # just defined as the residual) so the assert below is a real check that every day is accounted for
    # exactly once across anchor + 7 folds + outside, with no gap or double count.
    fold7_end_eq = float(daily_eq[daily_eq.index < H.TEST_BLOCK_ENDS[7]].iloc[-1])
    outside_pnl = float(final_equity - fold7_end_eq)
    fold_sum = sum(v["total_pnl_usd"] for v in monthly.values() if v["total_pnl_usd"] is not None)
    reconciled_total = fold_sum + outside_pnl
    expected_total = final_equity - START_EQUITY
    assert abs(reconciled_total - expected_total) < 1e-6, (
        f"{run_key(q, stop, fee)}: sum(fold totals)={fold_sum:.6f} + outside={outside_pnl:.6f} = "
        f"{reconciled_total:.6f} != final_equity - START_EQUITY = {expected_total:.6f}")
    monthly["outside"] = dict(n_days=int((daily_eq.index >= H.TEST_BLOCK_ENDS[7]).sum()),
                               total_pnl_usd=outside_pnl, total_pnl_pct=None,
                               note="exit spill / boundary days at or after fold 7's nominal end")

    if n_trades:
        win_rate = float((trades["exit_reason"] == "mu").mean())
        stop_share = float((trades["exit_reason"] == "stop").mean())
        timeout_share = float((trades["exit_reason"] == "timeout").mean())
        liq_share = float((trades["exit_reason"] == "liquidation").mean())
        mean_net, median_net = float(trades["net"].mean()), float(trades["net"].median())
        roc = trades["net"] / trades["margin"]
        mean_roc, median_roc = float(roc.mean()), float(roc.median())
        win_mask = trades["net"] > 0
        mean_win = float(trades.loc[win_mask, "net"].mean()) if win_mask.any() else float("nan")
        mean_loss = float(trades.loc[~win_mask, "net"].mean()) if (~win_mask).any() else float("nan")
        sum_win = float(trades.loc[win_mask, "net"].sum())
        sum_loss = float(trades.loc[~win_mask, "net"].sum())
        profit_factor = sum_win / abs(sum_loss) if sum_loss != 0 else float("inf")
        mean_hold = float(trades["holding_minutes"].mean())
    else:
        win_rate = stop_share = timeout_share = liq_share = float("nan")
        mean_net = median_net = mean_roc = median_roc = float("nan")
        mean_win = mean_loss = profit_factor = mean_hold = float("nan")

    total_fee = float((trades["entry_fee"] + trades["exit_fee"]).sum()) if n_trades else 0.0
    total_slip = float((trades["entry_slip"] + trades["exit_slip"]).sum()) if n_trades else 0.0
    total_fund_paid = float(trades["funding_paid"].sum()) if n_trades else 0.0
    total_fund_recv = float(trades["funding_received"].sum()) if n_trades else 0.0
    total_gross = float(trades["gross_pnl"].sum()) if n_trades else 0.0
    # checker N5: every cost as USD AND as a share of gross
    fee_share = total_fee / total_gross if total_gross else float("nan")
    slip_share = total_slip / total_gross if total_gross else float("nan")
    fund_paid_share = total_fund_paid / total_gross if total_gross else float("nan")
    fund_recv_share = total_fund_recv / total_gross if total_gross else float("nan")

    peak_margin = float(me["margin_used"].max()) if len(me) else 0.0
    # checker N3: the RATIO account_value / maintenance, not the USD difference
    me_nonzero_maint = me[me["maintenance"] > 0] if len(me) else me
    if len(me_nonzero_maint):
        ratio = me_nonzero_maint["account_value"] / me_nonzero_maint["maintenance"]
        min_ratio_by_day = ratio.groupby(me_nonzero_maint["time"].dt.floor("D")).min()
    else:
        min_ratio_by_day = pd.Series(dtype=float)
    dist_to_liq = dict(
        min=float(min_ratio_by_day.min()) if len(min_ratio_by_day) else None,
        median=float(min_ratio_by_day.median()) if len(min_ratio_by_day) else None,
        date_of_min=str(min_ratio_by_day.idxmin().date()) if len(min_ratio_by_day) else None,
    )
    mean_open = float(me["n_open"].mean()) if len(me) else 0.0
    max_open = int(me["n_open"].max()) if len(me) else 0

    # minor: print the liquidation table even when empty
    liq_table = liq[["time", "account_value_before", "maintenance"]].to_dict(orient="records") if len(liq) else []

    skip_counts = sk["reason"].value_counts().to_dict() if len(sk) else {}

    by_fold = {}
    if n_trades:
        trades = trades.copy()
        trades["fold"] = trades["t0"].apply(fold_of)
        for k, g in trades.groupby("fold"):
            by_fold[int(k)] = dict(n=len(g), mean_net=float(g["net"].mean()))

    by_pair = (trades.groupby(["ticker_a", "ticker_b"])["net"].sum().sort_values(ascending=False)
               if n_trades else pd.Series(dtype=float))
    by_pair.index = [f"{a}/{b}" for a, b in by_pair.index] if len(by_pair) else by_pair.index
    coin_net = {}
    if n_trades:
        for _, r in trades.iterrows():
            coin_net[r["ticker_a"]] = coin_net.get(r["ticker_a"], 0.0) + r["net"]
            coin_net[r["ticker_b"]] = coin_net.get(r["ticker_b"], 0.0) + r["net"]
    coin_series = pd.Series(coin_net).sort_values(ascending=False) if coin_net else pd.Series(dtype=float)

    return dict(
        q=q, stop=stop, fee=fee, n_trades=n_trades, final_equity=final_equity, total_return=total_return,
        cagr=cagr, cagr_n_days=n_days_cagr, daily_pnl_mean=daily_pnl_mean, daily_pnl_median=daily_pnl_median,
        share_positive_days=share_pos_days, worst_day=worst_day, best_day=best_day,
        max_drawdown=dd, sharpe=sharpe, sortino=sortino, sharpe_sortino_n_days=n_days_sharpe,
        monthly=monthly, n_months_positive=n_months_positive, win_rate=win_rate, stop_share=stop_share,
        timeout_share=timeout_share, liquidation_share=liq_share, mean_net=mean_net, median_net=median_net,
        mean_return_on_margin=mean_roc, median_return_on_margin=median_roc, mean_win=mean_win,
        mean_loss=mean_loss, profit_factor=profit_factor, mean_holding_minutes=mean_hold,
        total_fee=total_fee, fee_share_of_gross=fee_share, total_slippage=total_slip,
        slippage_share_of_gross=slip_share, total_funding_paid=total_fund_paid,
        funding_paid_share_of_gross=fund_paid_share, total_funding_received=total_fund_recv,
        funding_received_share_of_gross=fund_recv_share, total_gross=total_gross,
        peak_margin_used=peak_margin, distance_to_liquidation_ratio=dist_to_liq,
        mean_open_positions=mean_open, max_open_positions=max_open, n_liquidations=len(liq),
        liquidation_table=liq_table, skip_counts=skip_counts, by_fold=by_fold,
        top10_pairs=by_pair.head(10).to_dict() if len(by_pair) else {},
        bottom10_pairs=by_pair.tail(10).to_dict() if len(by_pair) else {},
        top10_coins=coin_series.head(10).to_dict() if len(coin_series) else {},
        bottom10_coins=coin_series.tail(10).to_dict() if len(coin_series) else {},
    )


def ev_check(q, fee):
    """stop=none only (planner ruling). EV = p_cal * mean_net(reached=mu) + (1-p_cal) *
    mean_net(not reached=timeout), the two means fit on EARLIER test months only (expanding, t0+10h
    guard -- correct because the maximum hold is 600 minutes = 10h, so a fit-pool event is only used
    once its own 10h outcome is known before the scored fold starts). Fold 1 is never scored: there is
    no earlier test month to fit on. 5 EV quintiles pooled over folds 2-7: mean EV vs realised mean net."""
    trades, _, _, _ = load_run(q, "none", fee)
    if len(trades) == 0:
        return None
    trades = trades.copy()
    trades["fold"] = trades["t0"].apply(fold_of)
    trades = trades[trades["exit_reason"].isin(["mu", "timeout"])]
    ev_rows = []
    for k in range(2, 8):
        test_start_k = H.TEST_BLOCK_STARTS[k]
        fit_pool = trades[trades["fold"] < k]
        guard = (fit_pool["t0"] + pd.Timedelta(hours=10)) <= test_start_k
        fit_h = fit_pool[guard]
        if fit_h.empty:
            continue
        mean_reached = fit_h.loc[fit_h["exit_reason"] == "mu", "net"].mean()
        mean_not = fit_h.loc[fit_h["exit_reason"] == "timeout", "net"].mean()
        test_block = trades[trades["fold"] == k].copy()
        test_block["ev"] = test_block["p_cal_10h"] * mean_reached + (1 - test_block["p_cal_10h"]) * mean_not
        ev_rows.append(test_block)
    if not ev_rows:
        return None
    pooled = pd.concat(ev_rows, ignore_index=True)
    pooled["ev_quintile"] = pd.qcut(pooled["ev"], 5, labels=False, duplicates="drop")
    q_tab = pooled.groupby("ev_quintile").agg(n=("ev", "size"), mean_ev=("ev", "mean"),
                                               mean_realised_net=("net", "mean"))
    return dict(n_scored=len(pooled), fold_1_scored=False, quintiles=q_tab.to_dict(orient="index"))


def plot_equity_curves():
    """One plain matplotlib PNG per (q, fee mode), all 4 stops on it (the brief asks for "per q, all
    stops on it"; fee mode is a second axis the brief doesn't resolve, so this script makes one PNG per
    q PER fee mode -- 6 PNGs -- rather than guess which fee mode to drop)."""
    paths = []
    for q in QS:
        for fee in FEES:
            fig, ax = plt.subplots(figsize=(8, 5))
            for stop in STOPS:
                _, me, _, _ = load_run(q, stop, fee)
                daily_eq = daily_equity_series(me)
                ax.plot(daily_eq.index, daily_eq.values, label=f"stop={stop}")
            ax.axhline(START_EQUITY, color="gray", linewidth=0.8, linestyle=":")
            ax.set_title(f"HL-PROFIT1 equity curve, q={q}, fee={fee}")
            ax.set_xlabel("date")
            ax.set_ylabel("account value (USD)")
            ax.legend()
            fig.tight_layout()
            out_path = os.path.join(NUMBERS_DIR, f"s1_profit1_equity_q{q}_fee{fee}.png")
            fig.savefig(out_path, dpi=120)
            plt.close(fig)
            paths.append(out_path)
            log(f"[NUMGEN] equity PNG written: {out_path}")
    return paths


def _numbers_md_lines(report, splits_filter=None):
    """splits_filter: if given, an iterable of run keys -- only those runs get a coin/pair split table
    (used for the NUMBERS.md excerpt, one run per q, per the planner's instruction; None means all 24,
    the default, used for the full section file). Returns the list of markdown lines (no trailing join
    or file write -- callers decide how to assemble/write, so the excerpt and the NUMBERS.md append can
    share the exact same text, checker E2)."""
    lines = ["## [HL-PROFIT1] Portfolio backtest, S1's live picks, build2 d3/asm price, "
             "slippage_spread_share=0.0", ""]
    lines.append(f"Runs ending above the ${START_EQUITY:.0f} start: "
                 f"{report['n_runs_above_start']}/{report['n_runs_total']}.")
    lines.append("")
    lines.append("| q | stop | fee | final_equity | total_return | n_trades | win_rate | profit_factor | "
                 "sharpe | sortino | max_dd_pct |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for key, r in report["runs"].items():
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {r['final_equity']:.2f} | "
                     f"{r['total_return']:.4f} | {r['n_trades']:,} | {r['win_rate']:.4f} | "
                     f"{r['profit_factor']:.4f} | {r['sharpe']:.3f} | {r['sortino']:.3f} | "
                     f"{r['max_drawdown']['max_dd_pct']:.4f} |")
    lines.append("")
    lines.append("### Costs (USD and share of gross), per run")
    lines.append("| q | stop | fee | gross | fee | fee_share | slippage | slip_share | funding_paid | "
                 "fund_paid_share | funding_received | fund_recv_share |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for key, r in report["runs"].items():
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {r['total_gross']:.2f} | "
                     f"{r['total_fee']:.2f} | {r['fee_share_of_gross']:.4f} | {r['total_slippage']:.2f} | "
                     f"{r['slippage_share_of_gross']:.4f} | {r['total_funding_paid']:.2f} | "
                     f"{r['funding_paid_share_of_gross']:.4f} | {r['total_funding_received']:.2f} | "
                     f"{r['funding_received_share_of_gross']:.4f} |")
    lines.append("")
    lines.append("### CAGR (annualised, N days), per run")
    lines.append("| q | stop | fee | cagr | cagr_n_days |")
    lines.append("|---|---|---|---|---|")
    for key, r in report["runs"].items():
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {r['cagr']:.4f} | {r['cagr_n_days']} |")
    lines.append("")
    lines.append("### Daily P&L, per run")
    lines.append("| q | stop | fee | mean | median | share_positive_days | worst_day | best_day |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for key, r in report["runs"].items():
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {r['daily_pnl_mean']:.4f} | "
                     f"{r['daily_pnl_median']:.4f} | {r['share_positive_days']:.4f} | "
                     f"{r['worst_day']:.2f} | {r['best_day']:.2f} |")
    lines.append("")
    lines.append("### Trades, per run")
    lines.append("| q | stop | fee | win_rate(mu) | stop_share | timeout_share | mean_net | median_net | "
                 "mean_roc | median_roc | mean_win | mean_loss | mean_holding_min |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for key, r in report["runs"].items():
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {r['win_rate']:.4f} | "
                     f"{r['stop_share']:.4f} | {r['timeout_share']:.4f} | {r['mean_net']:.4f} | "
                     f"{r['median_net']:.4f} | {r['mean_return_on_margin']:.4f} | "
                     f"{r['median_return_on_margin']:.4f} | {r['mean_win']:.4f} | {r['mean_loss']:.4f} | "
                     f"{r['mean_holding_minutes']:.1f} |")
    lines.append("")
    lines.append("### Skips by reason, per run")
    skip_reasons = sorted({rsn for r in report["runs"].values() for rsn in r["skip_counts"]})
    lines.append("| q | stop | fee | " + " | ".join(skip_reasons) + " |")
    lines.append("|---|---|---|" + "---|" * len(skip_reasons))
    for key, r in report["runs"].items():
        counts = " | ".join(str(r["skip_counts"].get(rsn, 0)) for rsn in skip_reasons)
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {counts} |")
    lines.append("")
    lines.append("### Leverage and risk, per run")
    lines.append("| q | stop | fee | peak_margin_used | mean_open | max_open | n_liquidations |")
    lines.append("|---|---|---|---|---|---|---|")
    for key, r in report["runs"].items():
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {r['peak_margin_used']:.2f} | "
                     f"{r['mean_open_positions']:.2f} | {r['max_open_positions']} | {r['n_liquidations']} |")
    lines.append("")
    lines.append("### Liquidation events, per run")
    any_liq = any(r["liquidation_table"] for r in report["runs"].values())
    if not any_liq:
        lines.append("none, in any of the 24 runs.")
    else:
        for key, r in report["runs"].items():
            if not r["liquidation_table"]:
                continue
            lines.append(f"**{key}**:")
            lines.append("| time | account_value_before | maintenance |")
            lines.append("|---|---|---|")
            for row in r["liquidation_table"]:
                lines.append(f"| {row['time']} | {row['account_value_before']:.2f} | {row['maintenance']:.2f} |")
    lines.append("")
    lines.append("### Splits: top/bottom 10 coins (net of trades involving the coin, each trade "
                 "counted for both coins) and pairs" +
                 (", per run" if splits_filter is None else " (one run per q, stop=none, fee=maker; "
                  "see the full section file for all 24)"))
    for key, r in report["runs"].items():
        if splits_filter is not None and key not in splits_filter:
            continue
        lines.append(f"**{key}** -- top 10 coins:")
        lines.append("| coin | net |")
        lines.append("|---|---|")
        for c, v in r["top10_coins"].items():
            lines.append(f"| {c} | {v:.2f} |")
        lines.append(f"**{key}** -- bottom 10 coins:")
        lines.append("| coin | net |")
        lines.append("|---|---|")
        for c, v in r["bottom10_coins"].items():
            lines.append(f"| {c} | {v:.2f} |")
        lines.append(f"**{key}** -- top 10 pairs:")
        lines.append("| pair | net |")
        lines.append("|---|---|")
        for c, v in r["top10_pairs"].items():
            lines.append(f"| {c} | {v:.2f} |")
        lines.append(f"**{key}** -- bottom 10 pairs:")
        lines.append("| pair | net |")
        lines.append("|---|---|")
        for c, v in r["bottom10_pairs"].items():
            lines.append(f"| {c} | {v:.2f} |")
        lines.append("")
    lines.append("### Drawdown and distance to liquidation, per run")
    lines.append("| q | stop | fee | max_dd_usd | max_dd_pct | dd_start | dd_bottom | dd_recovery | "
                 "longest_underwater_days | min_dist_ratio | median_dist_ratio | date_of_min |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for key, r in report["runs"].items():
        dd, dist = r["max_drawdown"], r["distance_to_liquidation_ratio"]
        lines.append(f"| {r['q']} | {r['stop']} | {r['fee']} | {dd['max_dd_usd']:.2f} | "
                     f"{dd['max_dd_pct']:.4f} | {dd['start']} | {dd['bottom']} | {dd['recovery']} | "
                     f"{dd['longest_underwater_days']} | "
                     f"{dist['min']:.4f} | {dist['median']:.4f} | {dist['date_of_min']} |")
    lines.append("")
    lines.append("### Monthly (fold) total P&L, per run")
    lines.append("All 7 test blocks start/end exactly at 00:00:00 UTC (not mid-day). \"outside\" is the "
                 "exit spill after fold 7's nominal end; sum(fold totals) + outside reconciles to "
                 "final_equity - start to 1e-6 (asserted in the generator).")
    lines.append("")
    for key, r in report["runs"].items():
        lines.append(f"**{key}** (n_months_positive={r['n_months_positive']}/7):")
        lines.append("| fold | n_days | total_pnl_usd | total_pnl_pct |")
        lines.append("|---|---|---|---|")
        fold_keys = sorted((k for k in r["monthly"] if k != "outside"), key=int)
        for k in fold_keys:
            m = r["monthly"][k]
            upnl = f"{m['total_pnl_usd']:.2f}" if m["total_pnl_usd"] is not None else "n/a"
            ppnl = f"{m['total_pnl_pct']:.4f}" if m["total_pnl_pct"] is not None else "n/a"
            lines.append(f"| {k} | {m['n_days']} | {upnl} | {ppnl} |")
        out = r["monthly"]["outside"]
        lines.append(f"| outside | {out['n_days']} | {out['total_pnl_usd']:.2f} | n/a |")
        lines.append("")
    lines.append("### EV check (stop=none only; fold 1 not scored, no earlier test month to fit on)")
    # checker E1: built from the ev_check results, not typed in -- counts how many of the (up to 6)
    # tables have mean_realised_net non-decreasing quintile 0->4, and quotes one real violation from
    # the data (the first break found) rather than a fixed example.
    ev_tables = [(key, ev) for key, ev in report["ev_check"].items() if ev is not None]
    n_monotonic, example = 0, None
    for key, ev in ev_tables:
        ordered = [ev["quintiles"][qq]["mean_realised_net"] for qq in sorted(ev["quintiles"])]
        qkeys = sorted(ev["quintiles"])
        is_monotonic = all(ordered[i] <= ordered[i + 1] for i in range(len(ordered) - 1))
        if is_monotonic:
            n_monotonic += 1
        elif example is None:
            for i in range(len(ordered) - 1):
                if ordered[i] > ordered[i + 1]:
                    example = (key, qkeys[i], ordered[i], qkeys[i + 1], ordered[i + 1])
                    break
    ex_txt = (f"e.g. {example[0]}: quintile {example[1]} mean_realised_net={example[2]:.4f} is above "
              f"quintile {example[3]}'s {example[4]:.4f}" if example else "")
    lines.append(f"EV quintiles rank realised net monotonically (quintile 0 to 4 non-decreasing) in "
                 f"{n_monotonic}/{len(ev_tables)} tables ({ex_txt}). EV here is descriptive only -- it "
                 f"does not rank realised net in these tables, and no claim that it predicts profit "
                 f"should be drawn from this table.")
    lines.append("")
    for key, ev in ev_tables:
        lines.append(f"**{key}** (n_scored={ev['n_scored']}):")
        lines.append("| quintile | n | mean_ev | mean_realised_net |")
        lines.append("|---|---|---|---|")
        for qq, row in sorted(ev["quintiles"].items()):
            lines.append(f"| {qq} | {row['n']} | {row['mean_ev']:.4f} | {row['mean_realised_net']:.4f} |")
        lines.append("")
    pcd = report.get("pooled_cost_share_diagnostic")
    if pcd:
        lines.append(f"### {pcd['label']}")
        lines.append(f"n_trades={pcd['n_trades']:,} gross={pcd['gross']:,.2f} fee={pcd['fee']:,.2f} "
                     f"funding_net={pcd['funding_net']:,.2f} net={pcd['net']:,.2f} "
                     f"fee_share_of_gross={pcd['fee_share_of_gross']:.4f}")
        lines.append("")
    lines.append("### Known gaps")
    for g in report["known_gaps"]:
        lines.append(f"- {g}")
    lines.append("")
    lines.append("### Equity curve PNGs")
    for p in report["equity_png_paths"]:
        lines.append(f"- {os.path.relpath(p, ROOT)}")
    return lines


def write_numbers_md(report, out_path, splits_filter=None):
    lines = _numbers_md_lines(report, splits_filter=splits_filter)
    open(out_path, "w").write("\n".join(lines))
    log(f"[NUMGEN] NUMBERS.md section written: {out_path}")


def main():
    t0 = pd.Timestamp.now()
    log(f"[NUMGEN] start {t0.isoformat()}")
    engine_report = json.load(open(os.path.join(LOG_DIR, "s1_profit1_report.json")))
    report = {"runs": {}, "ev_check": {}}
    for q in QS:
        for stop in STOPS:
            for fee in FEES:
                key = run_key(q, stop, fee)
                r = per_run_report(q, stop, fee, engine_report)
                report["runs"][key] = r
                log(f"[NUMGEN] {key}: final_equity={r['final_equity']:.2f} (engine-matched) "
                    f"total_return={r['total_return']:.4f} n_trades={r['n_trades']} win_rate={r['win_rate']:.4f} "
                    f"profit_factor={r['profit_factor']:.4f} sharpe={r['sharpe']:.3f} "
                    f"(n_days={r['sharpe_sortino_n_days']}) max_dd_pct={r['max_drawdown']['max_dd_pct']:.4f}")
    for q in QS:
        for fee in FEES:
            key = f"q{q}_fee{fee}"
            ev = ev_check(q, fee)
            report["ev_check"][key] = ev
            if ev:
                log(f"[NUMGEN] EV check {key}: n_scored={ev['n_scored']} (fold 1 not scored)")
                for qq, row in sorted(ev["quintiles"].items()):
                    log(f"[NUMGEN]   quintile {qq}: n={row['n']} mean_ev={row['mean_ev']:.4f} "
                        f"mean_realised_net={row['mean_realised_net']:.4f}")

    n_above_start = sum(1 for r in report["runs"].values() if r["final_equity"] > START_EQUITY)
    report["n_runs_above_start"] = n_above_start
    report["n_runs_total"] = len(report["runs"])
    log(f"[NUMGEN] runs ending above the ${START_EQUITY:.0f} start: {n_above_start}/{len(report['runs'])}")

    all_trades = []
    for q in QS:
        for stop in STOPS:
            for fee in FEES:
                tr, _, _, _ = load_run(q, stop, fee)
                all_trades.append(tr)
    pooled = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    if len(pooled):
        pooled_gross = float(pooled["gross_pnl"].sum())
        pooled_fee = float((pooled["entry_fee"] + pooled["exit_fee"]).sum())
        pooled_fund = float((pooled["funding_paid"] - pooled["funding_received"]).sum())
        pooled_net = float(pooled["net"].sum())
        report["pooled_cost_share_diagnostic"] = dict(
            label="cost-share diagnostic (OVERLAPPING accounts across the 24 runs, not a combined P&L)",
            n_trades=len(pooled), gross=pooled_gross, fee=pooled_fee, funding_net=pooled_fund, net=pooled_net,
            fee_share_of_gross=pooled_fee / pooled_gross if pooled_gross else float("nan"))
        log(f"[NUMGEN] pooled cost-share diagnostic (NOT a combined P&L): n_trades={len(pooled):,} "
            f"gross={pooled_gross:,.2f} fee={pooled_fee:,.2f} funding_net={pooled_fund:,.2f} net={pooled_net:,.2f} "
            f"fee_share_of_gross={report['pooled_cost_share_diagnostic']['fee_share_of_gross']:.4f}")

    # checker N6: guard the "slippage excluded" line against the engine's own recorded CONFIG
    share = engine_report["config"]["slippage_spread_share"]
    assert share == 0.0, (
        f"known-gaps text says slippage was excluded by the user's choice, but report.json's own "
        f"CONFIG has slippage_spread_share={share}, not 0.0 -- refusing to write a gaps line that "
        f"doesn't match the run it describes")
    report["known_gaps"] = [
        "slippage excluded by the user's choice (legs are small); costs are a lower bound and results "
        "an upper bound (optimistic).",
        "max_leverage is today's snapshot (hindsight); limits were different in the past.",
        "liquidation is checked on 1-minute closes; a move inside a minute can liquidate earlier.",
        "maker fills are assumed to fill; in practice they may not.",
        "the test months were already used for the cut-off, the deep dive and the calibration: "
        "results are optimistic until the vault or paper-trading check.",
    ]

    report["equity_png_paths"] = plot_equity_curves()

    out_path = os.path.join(LOG_DIR, "s1_profit1_numbers_report.json")
    json.dump(report, open(out_path, "w"), indent=2, default=str)
    log(f"[NUMGEN] report written: {out_path}")

    md_path = os.path.join(NUMBERS_DIR, "s1_profit1_numbers_section.md")
    write_numbers_md(report, md_path)
    log(f"[NUMGEN] NUMBERS.md section (full, 24-run splits) written: {md_path}")

    # Planner's instruction (2026-11-09): paste every per-run table + splits for one run per q
    # (stop=none, maker) into NUMBERS.md itself, link the full section file for the rest.
    # checker E2: build ONE canonical string (leading blank line + the footer link line both baked in)
    # and write that EXACT string to both the excerpt file and the NUMBERS.md append -- byte-identical,
    # not reconstructed differently in each place.
    excerpt_path = os.path.join(NUMBERS_DIR, "s1_profit1_numbers_excerpt.md")
    one_per_q = [run_key(q, "none", "maker") for q in QS]
    full_rel = os.path.relpath(md_path, ROOT)
    excerpt_lines = _numbers_md_lines(report, splits_filter=one_per_q)
    excerpt_lines.append(f"Full section (all 24 runs' splits, identical per-run tables): {full_rel}")
    canonical_text = "\n" + "\n".join(excerpt_lines) + "\n"
    open(excerpt_path, "w").write(canonical_text)
    log(f"[NUMGEN] NUMBERS.md excerpt written: {excerpt_path}")

    numbers_md_path = os.path.join(ROOT, "research", "dislocation_model", "NUMBERS.md")
    existing = open(numbers_md_path).read()
    marker = "## [HL-PROFIT1]"
    if marker in existing:
        log(f"[NUMGEN] NUMBERS.md already has a {marker} section -- not appending again")
    else:
        with open(numbers_md_path, "a") as f:
            f.write(canonical_text)
        log(f"[NUMGEN] NUMBERS.md appended: {numbers_md_path}")
    assert open(excerpt_path).read() == canonical_text, "excerpt file does not match the canonical text"
    log(f"[NUMGEN] done  [{(pd.Timestamp.now()-t0).total_seconds():.0f}s]")


if __name__ == "__main__":
    main()
