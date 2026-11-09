"""HL-PROFIT1 Task B (planner, 2026-11-09): descriptive-only |z| x p_cal grid on the EXISTING
max_open=10 trade logs for the 6 stop=none runs (3 q x 2 fee modes). No new simulation, no rule chosen
-- this reads only trades_q{q}_stopnone_fee{fee}.parquet (already on disk from the reported run) and
joins each trade's event_id to H.load_search_events()'s own "z" column for the event's known-at-entry
distance from mu (no look-ahead: z is a geometry input, fixed at pick time, not a backtest output).

Definitions (per the planner's instructions):
- distance = |z| (sigma units, known at entry).
- probability = p_cal_10h (already in the trade log).
- return per trade = net / notional (NOT USD net -- the brief's own return-on-exposure measure).
- win rate = share of exit_reason == "mu" (same definition used throughout s1_profit1_numbers_gen.py).
- profit_factor = sum(net>0 net$) / abs(sum(net<=0 net$)) -- on dollar net, same convention as the
  generator's per_run_report (profit_factor is a scale-dependent ratio of sums, not of the per-trade
  return; using net$ keeps it consistent with every other profit_factor already in NUMBERS.md).

Produces, per run: a 5-quantile |z| table, a 5-quantile p_cal table, and a 5x5 (|z| quintile x p_cal
quintile) grid, each with n, win_rate, mean/median return (net/notional), and profit_factor.

No filter or rule is chosen here. Any threshold read off this table needs the vault or paper-trading
check before it means anything -- the test months already drove the cutoff/deep-dive/calibration
choices upstream (same known gap as the main report).

    python -u research/model/s1_profit1_taskb_zq_grid.py > research/model/logs/s1/s1_profit1_taskb_gen.log
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
sys.path.insert(0, os.path.join(ROOT, "research"))
import harness as H  # noqa: E402

PROFIT_DIR = os.path.join(HERE, "logs", "profit1")
LOG_DIR = os.path.join(HERE, "logs", "s1")
NUMBERS_DIR = os.path.join(ROOT, "research", "dislocation_model", "logs")
QS = (0.01, 0.005, 0.001)
FEES = ("taker", "maker")
N_QUANTILES = 5


def log(msg):
    print(msg, flush=True)


def run_key(q, fee):
    return f"q{q}_stopnone_fee{fee}"


def quantile_table(df, col, value_col, label):
    """5-quantile table on `col`, reporting n/win_rate/mean+median `value_col`/profit_factor per bin.
    Uses pd.qcut with duplicates='drop' (same convention as ev_check in s1_profit1_numbers_gen.py) --
    if duplicate edges collapse bins, fewer than 5 rows come back and that is reported, not papered
    over."""
    bins, edges = pd.qcut(df[col], N_QUANTILES, labels=False, duplicates="drop", retbins=True)
    rows = []
    for b in sorted(bins.dropna().unique()):
        g = df[bins == b]
        win_rate = float((g["exit_reason"] == "mu").mean())
        mean_ret, median_ret = float(g[value_col].mean()), float(g[value_col].median())
        sum_win = float(g.loc[g["net"] > 0, "net"].sum())
        sum_loss = float(g.loc[g["net"] <= 0, "net"].sum())
        pf = sum_win / abs(sum_loss) if sum_loss != 0 else float("inf")
        rows.append(dict(quintile=int(b), n=int(len(g)), bin_lo=float(edges[int(b)]),
                          bin_hi=float(edges[int(b) + 1]), win_rate=win_rate, mean_return=mean_ret,
                          median_return=median_ret, profit_factor=pf))
    return rows, bins


def grid_table(df, z_bins, p_bins, value_col):
    rows = []
    for zb in sorted(z_bins.dropna().unique()):
        for pb in sorted(p_bins.dropna().unique()):
            mask = (z_bins == zb) & (p_bins == pb)
            g = df[mask]
            if len(g) == 0:
                rows.append(dict(z_quintile=int(zb), p_quintile=int(pb), n=0, win_rate=None,
                                  mean_return=None, median_return=None, profit_factor=None))
                continue
            win_rate = float((g["exit_reason"] == "mu").mean())
            mean_ret, median_ret = float(g[value_col].mean()), float(g[value_col].median())
            sum_win = float(g.loc[g["net"] > 0, "net"].sum())
            sum_loss = float(g.loc[g["net"] <= 0, "net"].sum())
            pf = sum_win / abs(sum_loss) if sum_loss != 0 else float("inf")
            rows.append(dict(z_quintile=int(zb), p_quintile=int(pb), n=int(len(g)), win_rate=win_rate,
                              mean_return=mean_ret, median_return=median_ret, profit_factor=pf))
    return rows


def per_run(q, fee, z_by_eid, t0_by_eid):
    key = run_key(q, fee)
    trades = pd.read_parquet(os.path.join(PROFIT_DIR, f"trades_{key}.parquet"))
    n0 = len(trades)
    trades = trades.copy()
    trades["z"] = trades["event_id"].map(z_by_eid)
    n_unmatched = int(trades["z"].isna().sum())
    assert n_unmatched == 0, (
        f"{key}: {n_unmatched}/{n0} trades have no matching event_id in load_search_events() -- "
        f"every pick came from that same table upstream, this should never happen")

    # checker's second join check: event_id alone can't prove the right event's z landed on this
    # trade -- also map the event's own t0 and assert it equals the trade's t0 (same tz), which proves
    # each trade got ITS event's z, not a mismatched row from a join gone wrong.
    trades["event_t0"] = trades["event_id"].map(t0_by_eid)
    t0_mismatch = (trades["event_t0"] != trades["t0"]).sum()
    assert t0_mismatch == 0, (
        f"{key}: {t0_mismatch}/{n0} trades have event_id->t0 != trade's own t0 -- the z join landed "
        f"on the wrong event")

    trades["abs_z"] = trades["z"].abs()
    trades["return_on_notional"] = trades["net"] / trades["notional"]

    z_rows, z_bins = quantile_table(trades, "abs_z", "return_on_notional", "abs_z")
    p_rows, p_bins = quantile_table(trades, "p_cal_10h", "return_on_notional", "p_cal_10h")
    grid_rows = grid_table(trades, z_bins, p_bins, "return_on_notional")

    log(f"[TASKB] {key}: n_trades={n0} abs_z quintiles={len(z_rows)} p_cal quintiles={len(p_rows)}")
    for r in z_rows:
        log(f"[TASKB]   |z| q{r['quintile']} [{r['bin_lo']:.3f},{r['bin_hi']:.3f}]: n={r['n']} "
            f"win_rate={r['win_rate']:.4f} mean_ret={r['mean_return']:.4f} "
            f"median_ret={r['median_return']:.4f} pf={r['profit_factor']:.4f}")
    for r in p_rows:
        log(f"[TASKB]   p_cal q{r['quintile']} [{r['bin_lo']:.4f},{r['bin_hi']:.4f}]: n={r['n']} "
            f"win_rate={r['win_rate']:.4f} mean_ret={r['mean_return']:.4f} "
            f"median_ret={r['median_return']:.4f} pf={r['profit_factor']:.4f}")

    return dict(q=q, fee=fee, n_trades=n0, abs_z_quintiles=z_rows, p_cal_quintiles=p_rows,
                grid=grid_rows)


MARKER = "## [HL-PROFIT1 taskB]"


def md_lines(report):
    lines = [f"{MARKER} |z| x p_cal descriptive grid, max_open=10, stop=none runs "
             "(DESCRIPTIVE ONLY -- no filter or rule chosen here)", ""]
    lines.append("distance = |z| (sigma, known at entry); probability = p_cal_10h; return per trade = "
                 "net/notional; win_rate = share exit_reason==mu; profit_factor on net$.")
    lines.append("")
    lines.append("**Any threshold read off this table needs the vault or paper-trading check before it "
                 "means anything -- the test months already drove the cutoff, the deep dive and the "
                 "calibration upstream of this same data.**")
    lines.append("")
    lines.append("### Monotonicity across the 6 runs (script-counted, not eyeballed)")
    lines.append("| measure | direction | monotone q0->q4 | top quintile has the highest value |")
    lines.append("|---|---|---|---|")
    for name, c in report["monotonicity_checks"].items():
        top = f"{c['n_top_quintile_highest']}/{c['n_runs']}" if c["n_top_quintile_highest"] is not None else "n/a"
        lines.append(f"| {name} | {c['direction']} | {c['n_monotone']}/{c['n_runs']} | {top} |")
    lines.append("")
    for key, r in report["runs"].items():
        lines.append(f"### {key} (n_trades={r['n_trades']:,})")
        lines.append("")
        lines.append("|z| quintiles:")
        lines.append("| quintile | range | n | win_rate | mean_return | median_return | profit_factor |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in r["abs_z_quintiles"]:
            lines.append(f"| {row['quintile']} | [{row['bin_lo']:.3f}, {row['bin_hi']:.3f}] | "
                         f"{row['n']} | {row['win_rate']:.4f} | {row['mean_return']:.4f} | "
                         f"{row['median_return']:.4f} | {row['profit_factor']:.4f} |")
        lines.append("")
        lines.append("p_cal_10h quintiles:")
        lines.append("| quintile | range | n | win_rate | mean_return | median_return | profit_factor |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in r["p_cal_quintiles"]:
            lines.append(f"| {row['quintile']} | [{row['bin_lo']:.4f}, {row['bin_hi']:.4f}] | "
                         f"{row['n']} | {row['win_rate']:.4f} | {row['mean_return']:.4f} | "
                         f"{row['median_return']:.4f} | {row['profit_factor']:.4f} |")
        lines.append("")
        lines.append("5x5 grid (|z| quintile x p_cal quintile):")
        lines.append("| |z| q \\ p_cal q | 0 | 1 | 2 | 3 | 4 |")
        lines.append("|---|---|---|---|---|---|")
        grid_by_cell = {(g["z_quintile"], g["p_quintile"]): g for g in r["grid"]}
        for zq in range(N_QUANTILES):
            cells = []
            for pq in range(N_QUANTILES):
                g = grid_by_cell.get((zq, pq))
                if g is None or g["n"] == 0:
                    cells.append("n=0")
                else:
                    cells.append(f"n={g['n']} wr={g['win_rate']:.2f} mret={g['mean_return']:.3f} "
                                 f"pf={g['profit_factor']:.2f}")
            lines.append(f"| {zq} | " + " | ".join(cells) + " |")
        lines.append("")
    return lines


def monotonicity_checks(report):
    """Checker's finding (2026-11-09): a hand-typed "pattern across all 6 runs" claim didn't match the
    data (checked 2/6, not 6/6, for several of the things originally claimed). Replaces that prose with
    script-printed counts only -- "k/6 runs monotone" per measure, and "top quintile highest in k/6" --
    so nothing described in a summary, NUMBERS.md or the Word report is typed from eyeballing."""
    def is_monotone(vals, increasing):
        return all((vals[i] <= vals[i + 1]) if increasing else (vals[i] >= vals[i + 1])
                   for i in range(len(vals) - 1))

    checks = {}
    # expected direction per axis: larger |z| -> lower win rate (decreasing); higher p_cal -> higher
    # win rate (increasing). Both axes expect return (mean/median) to rise q0->q4.
    axis_measures = {
        "abs_z": (("win_rate", False), ("mean_return", True), ("median_return", True)),
        "p_cal": (("win_rate", True), ("mean_return", True), ("median_return", True)),
    }
    for axis, key_prefix in (("abs_z", "abs_z_quintiles"), ("p_cal", "p_cal_quintiles")):
        for measure, increasing in axis_measures[axis]:
            n_mono, n_top_highest = 0, 0
            for run_key_, r in report["runs"].items():
                rows = sorted(r[key_prefix], key=lambda row: row["quintile"])
                vals = [row[measure] for row in rows]
                if is_monotone(vals, increasing):
                    n_mono += 1
                if vals[-1] == max(vals):
                    n_top_highest += 1
            n_runs = len(report["runs"])
            checks[f"{axis}_{measure}"] = dict(
                direction="decreasing q0->q4" if not increasing else "increasing q0->q4",
                n_monotone=n_mono, n_runs=n_runs,
                n_top_quintile_highest=n_top_highest if measure != "win_rate" else None)
    return checks


def main():
    t0 = pd.Timestamp.now()
    log(f"[TASKB] start {t0.isoformat()}")
    ev = H.load_search_events(columns=["z"])
    z_by_eid = ev["z"]
    t0_by_eid = ev["t0"]

    report = {"runs": {}}
    for q in QS:
        for fee in FEES:
            key = run_key(q, fee)
            report["runs"][key] = per_run(q, fee, z_by_eid, t0_by_eid)

    checks = monotonicity_checks(report)
    report["monotonicity_checks"] = checks
    for name, c in checks.items():
        extra = f" top_quintile_highest={c['n_top_quintile_highest']}/{c['n_runs']}" if c["n_top_quintile_highest"] is not None else ""
        log(f"[TASKB] monotonicity {name} ({c['direction']}): {c['n_monotone']}/{c['n_runs']} runs monotone{extra}")

    out_path = os.path.join(LOG_DIR, "s1_profit1_taskb_report.json")
    json.dump(report, open(out_path, "w"), indent=2, default=str)
    log(f"[TASKB] report written: {out_path}")

    # Checker's requirement (same discipline as open20): ONE canonical string, written byte-identical
    # to the standalone section file and to the NUMBERS.md append, with the footer link baked in so
    # both copies are literally the same bytes.
    md_path = os.path.join(NUMBERS_DIR, "s1_profit1_taskb_section.md")
    full_rel = os.path.relpath(md_path, ROOT)
    lines = md_lines(report)
    lines.append(f"Full section (this file, all 6 runs' tables): {full_rel}")
    canonical_text = "\n" + "\n".join(lines) + "\n"
    open(md_path, "w").write(canonical_text)
    log(f"[TASKB] section written: {md_path}")

    numbers_md_path = os.path.join(ROOT, "research", "dislocation_model", "NUMBERS.md")
    existing = open(numbers_md_path).read()
    if MARKER in existing:
        log(f"[TASKB] NUMBERS.md already has a {MARKER} section -- not appending again")
    else:
        with open(numbers_md_path, "a") as f:
            f.write(canonical_text)
        log(f"[TASKB] NUMBERS.md appended: {numbers_md_path}")
    assert open(md_path).read() == canonical_text, "section file does not match the canonical text"
    log(f"[TASKB] done  [{(pd.Timestamp.now()-t0).total_seconds():.0f}s]")


if __name__ == "__main__":
    main()
