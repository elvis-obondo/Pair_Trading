"""HL-PROFIT1 Word report (planner spec, 2026-11-09): builds ONE data file,
research/model/logs/s1/s1_profit1_docx_data.json, with every number the document needs already
pulled from the committed JSON/section files -- NOTHING is typed by hand here either. The renderer
(a separate Node/docx-js script) only formats this JSON into Word XML; it carries no numbers of its
own, so every figure in the final .docx traces back to this file, and this file traces back to:
  - research/model/logs/s1/s1_profit1_report{,_open20,_z3_open10,_z3_open20}.json (engine)
  - research/model/logs/s1/s1_profit1_numbers_report{,_open20,_z3_open10,_z3_open20}.json (generator)
  - research/model/logs/s1/s1_profit1_taskb_report.json (Task B)

    python -u research/model/s1_profit1_docx_data.py > research/model/logs/s1/s1_profit1_docx_data.log
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
sys.path.insert(0, os.path.join(ROOT, "research"))
import harness as H  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
QS = (0.01, 0.005, 0.001)
STOPS = ("0p5", "1p0", "2p0", "none")
FEES = ("taker", "maker")
VARIANTS = ("", "_open20", "_z3_open10", "_z3_open20")
VARIANT_LABEL = {"": "base (max_open=10)", "_open20": "open20 (max_open=20)",
                  "_z3_open10": "z3_open10 (|z|>=3, max_open=10)", "_z3_open20": "z3_open20 (|z|>=3, max_open=20)"}


def log(msg):
    print(msg, flush=True)


def run_key(q, stop, fee):
    return f"q{q}_stop{stop}_fee{fee}"


def load(tag_suffix):
    engine = json.load(open(os.path.join(LOG_DIR, f"s1_profit1_report{tag_suffix}.json")))
    numgen = json.load(open(os.path.join(LOG_DIR, f"s1_profit1_numbers_report{tag_suffix}.json")))
    return engine, numgen


PRE_SKIP_RE = re.compile(r"pre-skip check: q=([\d.]+) picks (\d+) -> (\d+)")
MISMATCH_BY_Q_RE = re.compile(r"\s+q=([\d.]+): (\d+)/([\d,]+) mismatched events")
MISMATCH_BY_FOLD_RE = re.compile(r"\s+fold (\d+): (\d+)/([\d,]+) mismatched events")


def parse_pre_skip_counts(log_path):
    """checker D1: read the z3 pre-skip counts from the engine's own log (not typed), keyed by q."""
    out = {}
    for line in open(log_path):
        m = PRE_SKIP_RE.search(line)
        if m:
            out[float(m.group(1))] = dict(n_before=int(m.group(2)), n_after=int(m.group(3)))
    return out


def parse_cross_check_mismatches(log_path):
    """checker D2/D8: read the cross-check mismatch counts from the engine's own log (not typed).
    by_q is kept for the breakdown display, but the TOTAL distinct picked events checked is the sum
    of the FOLD lines (q=0.005/0.001 picks are subsets of q=0.01, so summing by_q over-counts)."""
    by_q, by_fold = {}, {}
    for line in open(log_path):
        m = MISMATCH_BY_Q_RE.search(line)
        if m:
            by_q[float(m.group(1))] = dict(mismatched=int(m.group(2)), total=int(m.group(3).replace(",", "")))
            continue
        m = MISMATCH_BY_FOLD_RE.search(line)
        if m:
            by_fold[int(m.group(1))] = dict(mismatched=int(m.group(2)), total=int(m.group(3).replace(",", "")))
    return by_q, by_fold


def skip_total(engine_run):
    return int(sum(engine_run["skips"].values()))


def build_all24_table(numgen):
    rows = []
    for q in QS:
        for stop in STOPS:
            for fee in FEES:
                key = run_key(q, stop, fee)
                r = numgen["runs"][key]
                rows.append(dict(q=r["q"], stop=r["stop"], fee=r["fee"],
                                  final_equity=r["final_equity"], total_return=r["total_return"],
                                  n_trades=r["n_trades"], win_rate=r["win_rate"],
                                  profit_factor=r["profit_factor"], sharpe=r["sharpe"],
                                  sortino=r["sortino"], max_dd_pct=r["max_drawdown"]["max_dd_pct"]))
    return rows


def build_variant_comparison(loaded_by_variant):
    rows = []
    for q in QS:
        for stop in STOPS:
            for fee in FEES:
                key = run_key(q, stop, fee)
                for tag in VARIANTS:
                    engine, numgen = loaded_by_variant[tag]
                    er = engine["runs"][key]
                    nr = numgen["runs"][key]
                    rows.append(dict(
                        q=q, stop=stop, fee=fee, variant=VARIANT_LABEL[tag],
                        final_equity=nr["final_equity"], total_return=nr["total_return"],
                        n_trades=nr["n_trades"], win_rate=nr["win_rate"],
                        profit_factor=nr["profit_factor"], sharpe=nr["sharpe"],
                        max_dd_pct=nr["max_drawdown"]["max_dd_pct"],
                        min_dist_ratio=nr["distance_to_liquidation_ratio"]["min"],
                        skip_total=skip_total(er), n_liquidations=nr["n_liquidations"]))
    return rows


def top_bottom5(d):
    items = sorted(d.items(), key=lambda kv: kv[1], reverse=True)
    top5 = items[:5]
    bottom5 = items[-5:][::-1] if len(items) > 5 else []
    return top5, bottom5


def build_per_run_section(key, r, equity_png_rel):
    return dict(
        key=key, q=r["q"], stop=r["stop"], fee=r["fee"],
        results=dict(final_equity=r["final_equity"], total_return=r["total_return"],
                     cagr=r["cagr"], cagr_n_days=r["cagr_n_days"], n_trades=r["n_trades"],
                     win_rate=r["win_rate"], stop_share=r["stop_share"],
                     timeout_share=r["timeout_share"], profit_factor=r["profit_factor"],
                     sharpe=r["sharpe"], sortino=r["sortino"],
                     sharpe_sortino_n_days=r["sharpe_sortino_n_days"],
                     mean_net=r["mean_net"], median_net=r["median_net"],
                     mean_win=r["mean_win"], mean_loss=r["mean_loss"],
                     mean_holding_minutes=r["mean_holding_minutes"]),
        drawdown=r["max_drawdown"],
        distance_to_liquidation=r["distance_to_liquidation_ratio"],
        costs=dict(total_gross=r["total_gross"], total_fee=r["total_fee"],
                   fee_share_of_gross=r["fee_share_of_gross"], total_slippage=r["total_slippage"],
                   slippage_share_of_gross=r["slippage_share_of_gross"],
                   total_funding_paid=r["total_funding_paid"],
                   funding_paid_share_of_gross=r["funding_paid_share_of_gross"],
                   total_funding_received=r["total_funding_received"],
                   funding_received_share_of_gross=r["funding_received_share_of_gross"]),
        skips=r["skip_counts"], n_liquidations=r["n_liquidations"],
        leverage_risk=dict(peak_margin_used=r["peak_margin_used"],
                            mean_open_positions=r["mean_open_positions"],
                            max_open_positions=r["max_open_positions"]),
        monthly=r["monthly"], n_months_positive=r["n_months_positive"],
        **_top_bottom5_pair("coins", r["top10_coins"]),
        **_top_bottom5_pair("pairs", r["top10_pairs"]),
        equity_png=equity_png_rel,
    )


def _top_bottom5_pair(label, d):
    if not d:
        return {f"top5_{label}": {}, f"bottom5_{label}": {}}
    top5, bottom5 = top_bottom5(d)
    return {f"top5_{label}": dict(top5), f"bottom5_{label}": dict(bottom5)}


def build_taskb(taskb):
    return taskb  # already a clean, small JSON -- pass through as-is (the renderer formats it)


def main():
    log("[DOCXDATA] start")
    loaded_by_variant = {tag: load(tag) for tag in VARIANTS}
    base_engine, base_numgen = loaded_by_variant[""]

    data = {}
    data["meta"] = dict(
        generated_from=[
            "research/model/logs/s1/s1_profit1_report.json",
            "research/model/logs/s1/s1_profit1_numbers_report.json",
            "research/model/logs/s1/s1_profit1_report_open20.json",
            "research/model/logs/s1/s1_profit1_numbers_report_open20.json",
            "research/model/logs/s1/s1_profit1_report_z3_open10.json",
            "research/model/logs/s1/s1_profit1_numbers_report_z3_open10.json",
            "research/model/logs/s1/s1_profit1_report_z3_open20.json",
            "research/model/logs/s1/s1_profit1_numbers_report_z3_open20.json",
            "research/model/logs/s1/s1_profit1_taskb_report.json",
        ])

    # --- Summary ---
    test_blocks = [dict(fold=k, start=str(H.TEST_BLOCK_STARTS[k].date()),
                         end=str(H.TEST_BLOCK_ENDS[k].date())) for k in range(1, 8)]
    all24 = build_all24_table(base_numgen)
    n_above, n_total = base_numgen["n_runs_above_start"], base_numgen["n_runs_total"]
    best_run = max(all24, key=lambda r: r["total_return"])
    worst_run = min(all24, key=lambda r: r["total_return"])
    ev_tables = [(k, ev) for k, ev in base_numgen["ev_check"].items() if ev is not None]
    n_monotonic = 0
    for k, ev in ev_tables:
        ordered = [ev["quintiles"][qq]["mean_realised_net"] for qq in sorted(ev["quintiles"])]
        if all(ordered[i] <= ordered[i + 1] for i in range(len(ordered) - 1)):
            n_monotonic += 1
    taskb = json.load(open(os.path.join(LOG_DIR, "s1_profit1_taskb_report.json")))
    mono = taskb["monotonicity_checks"]
    open20_engine, open20_numgen = loaded_by_variant["_open20"]
    start_equity = base_engine["config"]["start_equity"]
    first_start, last_end = test_blocks[0]["start"], test_blocks[-1]["end"]

    # checker D5: compute, not type, the margin-skip claim -- count of base runs with margin==0, and
    # the open20 margin-skip min/max across its 24 runs.
    n_base_margin_zero = sum(1 for rr in base_engine["runs"].values() if rr["skips"]["margin"] == 0)
    open20_margin_counts = [rr["skips"]["margin"] for rr in open20_engine["runs"].values()]
    # checker D9: the mechanism is max_open x margin_frac, not "the same $1,000 pool" (margin is a
    # share of CURRENT equity, not the start equity) -- computed from each variant's own CONFIG.
    base_margin_frac = base_engine["config"]["margin_frac"]
    base_max_open = base_engine["config"]["max_open"]
    open20_max_open = open20_engine["config"]["max_open"]
    base_margin_cap_pct = base_max_open * base_margin_frac
    open20_margin_cap_pct = open20_max_open * base_margin_frac

    # checker D1: read the z3 pre-skip counts from both z3 engine logs (not typed), assert they agree.
    pre_skip_10 = parse_pre_skip_counts(os.path.join(LOG_DIR, "s1_profit1_z3_open10.log"))
    pre_skip_20 = parse_pre_skip_counts(os.path.join(LOG_DIR, "s1_profit1_z3_open20.log"))
    assert pre_skip_10 == pre_skip_20, (
        f"z3_open10 and z3_open20 pre-skip counts disagree: {pre_skip_10} vs {pre_skip_20}")

    n_folds = len(test_blocks)
    max_ev_quintile = base_engine["config"]["ev_quintiles"] - 1
    mono_n_runs = mono["p_cal_mean_return"]["n_runs"]
    z3_min_abs_z = loaded_by_variant["_z3_open10"][0]["config"]["min_abs_z"]

    key_findings = [
        f"Of the {n_total} base (max_open={base_max_open}) configurations, {n_above}/{n_total} end "
        f"the {n_folds} test blocks ({first_start} to {last_end}) above the ${start_equity:,.0f} start.",
        f"The best base config is q={best_run['q']}, stop={best_run['stop']}, fee={best_run['fee']} "
        f"(total_return={best_run['total_return']:.4f}); the worst is q={worst_run['q']}, "
        f"stop={worst_run['stop']}, fee={worst_run['fee']} (total_return={worst_run['total_return']:.4f}).",
        f"EV quintiles (stop=none only) rank realised net monotonically (quintile 0 to {max_ev_quintile} "
        f"non-decreasing) in {n_monotonic}/{len(ev_tables)} of the base q x fee combinations -- EV here "
        f"is descriptive only and does not rank realised net in these tables.",
        f"Raising max_open from {base_max_open} to {open20_max_open} (Task A) moves the count of runs "
        f"ending above start from {n_above}/{n_total} (max_open={base_max_open}) to "
        f"{open20_numgen['n_runs_above_start']}/{open20_numgen['n_runs_total']} "
        f"(max_open={open20_max_open}). margin skips are 0 in {n_base_margin_zero}/{n_total} base "
        f"(max_open={base_max_open}) runs, and range from {min(open20_margin_counts):,} to "
        f"{max(open20_margin_counts):,} across the {open20_numgen['n_runs_total']} open20 "
        f"(max_open={open20_max_open}) runs: at max_open={base_max_open} the open positions can need "
        f"at most {base_margin_cap_pct:.0%} of account value as margin ({base_max_open} x "
        f"{base_margin_frac:.0%}), so margin cannot bind; at max_open={open20_max_open} that rises to "
        f"{open20_margin_cap_pct:.0%} ({open20_max_open} x {base_margin_frac:.0%}), so it can.",
        f"Task B's descriptive |z| x p_cal grid on the {mono_n_runs} stop=none runs finds the top "
        f"p_cal quintile has the highest mean return in "
        f"{mono['p_cal_mean_return']['n_top_quintile_highest']}/{mono_n_runs} runs, but win_rate is "
        f"monotonic in only {mono['abs_z_win_rate']['n_monotone']}/{mono_n_runs} runs for |z| and "
        f"{mono['p_cal_win_rate']['n_monotone']}/{mono_n_runs} for p_cal, and mean return is monotonic "
        f"in {mono['abs_z_mean_return']['n_monotone']}/{mono_n_runs} runs for |z| and "
        f"{mono['p_cal_mean_return']['n_monotone']}/{mono_n_runs} for p_cal.",
        f"Task C's |z| >= {z3_min_abs_z} filter (in-sample -- chosen after seeing these test months) "
        f"cuts the q=0.01 pick count from {pre_skip_10[0.01]['n_before']:,} to "
        f"{pre_skip_10[0.01]['n_after']:,}, q=0.005 from {pre_skip_10[0.005]['n_before']:,} to "
        f"{pre_skip_10[0.005]['n_after']:,}, and q=0.001 from {pre_skip_10[0.001]['n_before']:,} to "
        f"{pre_skip_10[0.001]['n_after']:,}, before any skip is applied (identical in both z3_open10 "
        f"and z3_open20).",
    ]

    n_qs, n_stops, n_fees = len(base_engine["config"]["qs"]), len(base_engine["config"]["stops"]), len(base_engine["config"]["fee_modes"])
    data["summary"] = dict(config=base_engine["config"], test_blocks=test_blocks, n_folds=n_folds,
                            all24_table=all24, n_runs_above_start=n_above, n_runs_total=n_total,
                            key_findings=key_findings, known_gaps=base_numgen["known_gaps"])

    # checker's renderer rule: the renderer must contain no numbers of its own -- every heading/intro
    # sentence that needs a count or a CONFIG value is pre-built here, from data, not typed in JS.
    data["strings"] = dict(
        intro=f"A ${start_equity:,.0f} cross-margin account backtest, {n_total} configurations "
              f"({n_qs} pick thresholds x {n_stops} stop rules x {n_fees} fee modes), built from "
              f"Hyperliquid build2 d3/asm 1-minute trade-price bars.",
        test_period_heading=f"Test period ({n_folds} folds)",
        all24_heading=f"All {n_total} base configurations (max_open={base_max_open})",
        runs_above_start=f"Runs ending above the ${start_equity:,.0f} start: {n_above}/{n_total}.",
        comparisons_heading=f"3. Comparisons by stop, fee and q (base, max_open={base_max_open})",
        per_run_heading=f"4. Per-run detail ({n_total} base configurations, max_open={base_max_open})",
        taskb_heading=f"7. Task B: |z| x p_cal descriptive grid (max_open={base_max_open}, stop=none "
                      f"runs)",
        taskb_mono_heading=f"Monotonicity across the {mono_n_runs} runs (script-counted)",
        variant_intro=f"open20 = max_open raised from {base_max_open} to {open20_max_open}, all else "
                      f"unchanged. z3_open10/z3_open20 = a |z| >= {z3_min_abs_z} filter applied on top "
                      f"of the base picks (in-sample -- chosen after seeing these test months), at "
                      f"max_open={base_max_open} and max_open={open20_max_open} respectively.",
        account_rules_start=f"${start_equity:,.0f} starting cross-margin account; margin_frac x "
                            f"current equity x leverage sizing.",
    )

    # --- Per-run sections (24 base runs) ---
    per_run = []
    for q in QS:
        for stop in STOPS:
            for fee in FEES:
                key = run_key(q, stop, fee)
                r = base_numgen["runs"][key]
                png_rel = next((os.path.relpath(p, ROOT) for p in base_numgen["equity_png_paths"]
                                 if f"q{q}_fee{fee}" in p), None)
                per_run.append(build_per_run_section(key, r, png_rel))
    data["per_run_sections"] = per_run

    # --- EV check (base) ---
    data["ev_check"] = base_numgen["ev_check"]

    # --- Variant comparison (base/open20/z3_open10/z3_open20) ---
    data["variant_comparison"] = build_variant_comparison(loaded_by_variant)

    # --- Task B ---
    data["taskb"] = build_taskb(taskb)

    # --- Method/data section (counts pulled straight from the engine report + log-derived facts) ---
    # checker D2: read the cross-check mismatch counts per variant from each variant's own engine log,
    # not typed.
    log_name_by_tag = {"": "s1_profit1.log", "_open20": "s1_profit1_open20.log",
                        "_z3_open10": "s1_profit1_z3_open10.log", "_z3_open20": "s1_profit1_z3_open20.log"}
    cross_check_by_variant = {}
    for tag in VARIANTS:
        by_q, by_fold = parse_cross_check_mismatches(os.path.join(LOG_DIR, log_name_by_tag[tag]))
        cross_check_by_variant[VARIANT_LABEL[tag]] = dict(
            label="distinct picked events (sum of the per-fold lines; q=0.005/0.001 are subsets of "
                  "q=0.01, so summing by_q would over-count)",
            mismatched_total=sum(v["mismatched"] for v in by_fold.values()),
            events_total=sum(v["total"] for v in by_fold.values()),
            by_q=by_q, by_fold=by_fold)

    # price-source verification receipts (sha256 file match + derived-value match), read from the
    # committed diagnostic logs, not typed.
    diag_dir = os.path.join(ROOT, "research", "model", "diagnostics")
    sha_match_text = open(os.path.join(diag_dir, "verify_30m_sha256_match.log")).read()
    deriv_text = open(os.path.join(diag_dir, "verify_30m_derivation.log")).read()
    sha_m = re.search(r"match (\d+) mismatch (\d+) missing (\d+)", sha_match_text)
    deriv_m = re.search(r"exact matches: ([\d,]+)", deriv_text)
    deriv_mismatch_m = re.search(r"mismatches: (\d+)", deriv_text)
    price_verification = dict(
        sha256_match=int(sha_m.group(1)), sha256_mismatch=int(sha_m.group(2)),
        sha256_missing=int(sha_m.group(3)),
        sha256_total=int(sha_m.group(1)) + int(sha_m.group(2)) + int(sha_m.group(3)),
        derived_value_exact_matches=int(deriv_m.group(1).replace(",", "")),
        derived_value_mismatches=int(deriv_mismatch_m.group(1)),
    )

    cov = base_engine["coverage_by_fold"]
    data["method_data"] = dict(
        coverage_by_fold=cov,
        cross_check_by_variant=cross_check_by_variant,
        slippage_spread_share=base_engine["config"]["slippage_spread_share"],
        pooled_cost_share_diagnostic=base_numgen.get("pooled_cost_share_diagnostic"),
        price_verification=price_verification,
    )

    out_path = os.path.join(LOG_DIR, "s1_profit1_docx_data.json")
    json.dump(data, open(out_path, "w"), indent=2, default=str)
    log(f"[DOCXDATA] wrote {out_path}")
    log(f"[DOCXDATA] all24 rows={len(all24)} per_run_sections={len(per_run)} "
        f"variant_comparison rows={len(data['variant_comparison'])}")
    log("[DOCXDATA] done")


if __name__ == "__main__":
    main()
