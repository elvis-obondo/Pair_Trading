"""HL-VAULT1 step 6 (brief docs/prompts/HL_VAULT1_RUN.md): the side-by-side table and the vault's own S1 lift and
calibration. REPORTED, NOT GATED: the brief has no pass/fail rule for the vault.

Inputs (all already on disk, nothing re-simulated):
  - the four numbers reports: test months (untagged = max_open 10, open20) and vault (vault_open10, vault_open20),
    written by s1_profit1_numbers_gen.py (PROFIT1_VAULT=1 for the vault ones);
  - the step-4 picks table (p_2h, p_5h, p_10h, p_cal_10h, pick_q), sha-checked against the reviewed file;
  - the vault labels (reach_2h/5h/10h, chance_10h, label_gap) through vault_loader -- the vault is opened here a
    second time for LABELS, as the brief's step 6 asks ("the vault's own S1 lift and calibration"); no setting of
    steps 4-5 changes;
  - s1d_report.json (test-month top-1% lift) and s1h_report.json (test-month deciles, picks) as the test-month
    reference, read not recomputed.

Rules fixed here before anything is run (no tuning):
  R1. Side-by-side: for each of the 24 runs (q x stop x fee), 10 metrics, 4 columns (test open10, test open20,
      vault open10, vault open20). Every cell is read from the numbers reports. Window lengths (cagr_n_days)
      are printed, because the vault is ~3 months and the test period ~7 months: equity and return are NOT
      per-month comparable and CAGR is a long extrapolation of a short window.
  R2. Lift = gap(top) - gap(all), gap = mean(reach_10h) - mean(chance_10h) (harness.lift). Two top sets: (a) the
      vault's own top 1% by p_10h (ceil(0.01 n), seeded random tie-break, S1-D's top_k_mask) and (b) the Rule A
      picks of step 4 (fold 7's cut-offs; q = 1%, 0.5%, 0.1%). Interval: harness.day_block_bootstrap, S1-D's
      settings (2,000 resamples, level 0.9875), one seed logged. Test-month reference: s1d_report.json top 1%.
  R3. Calibration at 2, 5 and 10 h: S1-H's R3 recipe (decile cut-offs from np.quantile(p, k/10), np.digitize, per
      bin n, mean predicted, actual reach rate) on ALL vault events, plus the top 1% by that horizon's own p
      and the Rule A picks. At 10 h also mean p_cal_10h (the step-4 isotonic map). No 2 h / 5 h isotonic map exists
      for the vault (step 4 fitted p_cal at 10 h only) and none is fitted here: raw p only at 2 h and 5 h.
      Test-month reference: s1h_report.json deciles (folds 1-7 pooled).
  R4. NUMBERS.md gets the section only with NUMGEN_APPEND=1 (after the checker has read the log). The excerpt file
      and the appended text are the same string.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
import harness as H  # noqa: E402
import vault_loader as VL  # noqa: E402 -- the only module allowed to read vault rows
import s1_profit1_numbers_gen as NG  # noqa: E402 -- PROFIT1_VAULT must be unset here; only VAULT_OPENED is used

LOG_DIR = os.path.join(HERE, "logs", "s1")
NUMBERS_DIR = os.path.join(ROOT, "research", "dislocation_model", "logs")
NUMBERS_MD = os.path.join(ROOT, "research", "dislocation_model", "NUMBERS.md")
PICKS = os.path.join(LOG_DIR, "s1_vault_picks.parquet")
EXPECTED_PICKS_SHA = "15b4f56cd66ad6b2a4e2bc056f03cf03febb519459491310d4f7745e50e44a72"   # same as s1_profit1.py
MARKER = "## [HL-VAULT1] Summary"
VAULT_OPENED = NG.VAULT_OPENED      # defined once, in s1_profit1_numbers_gen.py; asserted against the score log in known_gaps()
SEED = 20261112
N_RESAMPLES = 2000          # S1-D's settings
LEVEL = 0.9875
QS = (0.01, 0.005, 0.001)
HORIZONS = (2, 5, 10)
SOURCES = [("test_open10", "s1_profit1_numbers_report.json", "s1_profit1_report.json", 10),
           ("test_open20", "s1_profit1_numbers_report_open20.json", "s1_profit1_report_open20.json", 20),
           ("vault_open10", "s1_profit1_numbers_report_vault_open10.json", "s1_profit1_report_vault_open10.json", 10),
           ("vault_open20", "s1_profit1_numbers_report_vault_open20.json", "s1_profit1_report_vault_open20.json", 20)]
METRICS = [("final_equity", "final equity ($)", lambda r: r["final_equity"], "{:,.2f}"),
           ("total_return", "return", lambda r: r["total_return"], "{:.4f}"),
           ("cagr", "CAGR (annualised from the window)", lambda r: r["cagr"], "{:.4f}"),
           ("n_trades", "trades", lambda r: r["n_trades"], "{:,}"),
           ("win_rate", "win rate (exit at mu)", lambda r: r["win_rate"], "{:.4f}"),
           ("profit_factor", "profit factor", lambda r: r["profit_factor"], "{:.4f}"),
           ("sharpe", "Sharpe (daily, sqrt 365)", lambda r: r["sharpe"], "{:.3f}"),
           ("max_dd_pct", "max drawdown", lambda r: r["max_drawdown"]["max_dd_pct"], "{:.4f}"),
           ("min_dist_liq", "min distance to liquidation (account / maintenance)",
            lambda r: r["distance_to_liquidation_ratio"]["min"], "{:.4f}"),
           ("fee_share", "fee share of gross", lambda r: r["fee_share_of_gross"], "{:.4f}")]


def log(msg):
    print(msg, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def fmt(fmt_str, v):
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else fmt_str.format(v)


# ---------------------------------------------------------------------------
# Part 1: the side-by-side table (R1)
# ---------------------------------------------------------------------------
def side_by_side():
    reps = {}
    for name, nr, er, max_open in SOURCES:
        num = json.load(open(os.path.join(LOG_DIR, nr)))
        eng = json.load(open(os.path.join(LOG_DIR, er)))
        assert eng["config"]["max_open"] == max_open, f"{name}: engine max_open {eng['config']['max_open']} != {max_open}"
        assert eng["config"]["slippage_spread_share"] == 0.0 and eng["config"].get("min_abs_z", 0.0) == 0.0, name
        reps[name] = num
    keys = list(reps["vault_open10"]["runs"])
    for name in reps:
        assert list(reps[name]["runs"]) == keys, f"{name}: run keys differ"
    days = {name: sorted({r["cagr_n_days"] for r in reps[name]["runs"].values()}) for name in reps}
    for name in reps:
        log(f"[VREP] {name}: cagr_n_days {days[name]}, runs above the $1,000 start "
            f"{reps[name]['n_runs_above_start']}/{reps[name]['n_runs_total']}")
    out = {"keys": keys, "days": days, "above_start": {n: reps[n]["n_runs_above_start"] for n in reps}, "cells": {}}
    lines = ["### Side by side: test months vs vault, same 24 runs, both max_open",
             f"Test period {H.TEST_BLOCK_STARTS[1].date()} .. {H.TEST_BLOCK_ENDS[7].date()} (exclusive end); vault "
             f"{H.VAULT_START.date()} .. last vault event day. Window length in days (CAGR basis): "
             + ", ".join(f"{n} {days[n]}" for n in reps) + ". Equity and return are NOT per-month comparable "
             "(the vault is about 3 months, the test period about 7); CAGR extrapolates a short window. "
             "Runs ending above the $1,000 start: " + ", ".join(f"{n} {reps[n]['n_runs_above_start']}/"
                                                                 f"{reps[n]['n_runs_total']}" for n in reps) + ".", ""]
    for mkey, mlabel, getter, f in METRICS:
        lines.append(f"**{mlabel}**")
        lines.append("| q | stop | fee | test open10 | test open20 | vault open10 | vault open20 |")
        lines.append("|---|---|---|---|---|---|---|")
        for key in keys:
            r0 = reps["vault_open10"]["runs"][key]
            vals = [getter(reps[name]["runs"][key]) for name, *_ in SOURCES]
            out["cells"][f"{mkey}|{key}"] = vals
            lines.append(f"| {r0['q']} | {r0['stop']} | {r0['fee']} | " + " | ".join(fmt(f, v) for v in vals) + " |")
        lines.append("")
        log(f"[VREP] side-by-side table '{mlabel}': {len(keys)} rows")
    return lines, out


# ---------------------------------------------------------------------------
# Part 2: the vault's own lift and calibration (R2, R3)
# ---------------------------------------------------------------------------
def top_k_mask(scores, frac, rng):          # S1-D's, verbatim semantics
    n = len(scores)
    n_top = max(1, int(np.ceil(frac * n)))
    tie_key = rng.random(n)
    order = np.lexsort((tie_key, -np.asarray(scores)))
    mask = np.zeros(n, dtype=bool)
    mask[order[:n_top]] = True
    return mask


def load_vault_table():
    got = sha256(PICKS)
    log(f"[VREP] picks file sha256 {got} (expected {EXPECTED_PICKS_SHA})")
    assert got == EXPECTED_PICKS_SHA, "picks file != the reviewed step-4 output"
    picks = pd.read_parquet(PICKS)
    ev = VL.load_vault_events(columns=["reach_2h", "reach_5h"]).reset_index(drop=True)
    cols = ["event_id", "reach_2h", "reach_5h", "reach_10h", "chance_10h", "label_gap"]
    df = picks.merge(ev[cols], on="event_id", how="inner", validate="one_to_one")
    assert len(df) == len(picks) == len(ev), (len(df), len(picks), len(ev))
    assert int((df["label_gap"] != 0).sum()) == 0, "label_gap rows present; the picks table is the usable subset"
    for c in ("reach_2h", "reach_5h", "reach_10h", "chance_10h", "p_2h", "p_5h", "p_10h", "p_cal_10h"):
        assert df[c].notna().all(), c
    log(f"[VREP] vault table: {len(df):,} events, t0 {df['t0'].min()} .. {df['t0'].max()}")
    return df


def lift_row(df, mask, label, rng, base):
    reach, chance = df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy()
    day = df["t0"].dt.floor("D").to_numpy()
    point, lo, hi = H.day_block_bootstrap(day, mask, reach, chance, N_RESAMPLES, LEVEL, rng)
    top = df[mask]
    row = dict(label=label, n=int(mask.sum()), share=float(mask.mean()), mean_p_10h=float(top["p_10h"].mean()),
               mean_p_cal_10h=float(top["p_cal_10h"].mean()), reach_10h=float(top["reach_10h"].mean()),
               chance_10h=float(top["chance_10h"].mean()), gap=H.gap(reach[mask], chance[mask]),
               lift=float(point), lo=lo, hi=hi)
    assert abs(row["lift"] - (row["gap"] - base["gap_all"])) < 1e-12, "lift != gap(top) - gap(all)"
    log(f"[VREP] lift {label}: n={row['n']:,} ({row['share']:.4%}) reach {row['reach_10h']:.4f} chance "
        f"{row['chance_10h']:.4f} lift {row['lift']:.4f} [{lo:.4f}, {hi:.4f}]")
    return row


def lift_section(df, rng, top1):
    reach, chance = df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy()
    base = dict(n=len(df), reach_10h=float(reach.mean()), chance_10h=float(chance.mean()), gap_all=H.gap(reach, chance))
    log(f"[VREP] all vault events: n={base['n']:,} reach_10h {base['reach_10h']:.4f} chance_10h {base['chance_10h']:.4f} "
        f"gap {base['gap_all']:.4f}")
    rows = [lift_row(df, top1[10], "own top 1% by p_10h", rng, base)]
    for q in QS:
        rows.append(lift_row(df, df[f"pick_{q}"].to_numpy(), f"Rule A picks q={q}", rng, base))
    s1d = json.load(open(os.path.join(LOG_DIR, "s1d_report.json")))["item1_robustness"]["0.01"]
    ref = dict(point=s1d["pooled_point"], lo=s1d["pooled_lo"], hi=s1d["pooled_hi"], n_positive=s1d["n_positive"])
    log(f"[VREP] test-month reference (s1d_report.json item1, top 1%): lift {ref['point']:.4f} "
        f"[{ref['lo']:.4f}, {ref['hi']:.4f}], {ref['n_positive']}/{len(s1d['per_fold'])} folds positive")
    n_folds = len(s1d["per_fold"])
    lines = ["### Vault lift (S1's measure; reported, not gated)",
             f"gap = mean(reach_10h) - mean(chance_10h); lift = gap(top) - gap(all vault events). All {base['n']:,} vault "
             f"events: reach_10h {base['reach_10h']:.4f}, chance_10h {base['chance_10h']:.4f}, gap {base['gap_all']:.4f}. "
             f"Interval: day-block bootstrap, {N_RESAMPLES} resamples, level {LEVEL}, seed {SEED}. Test-month reference "
             f"(s1d_report.json, pooled top 1%, {n_folds} folds): lift {ref['point']:.4f} [{ref['lo']:.4f}, {ref['hi']:.4f}], "
             f"{ref['n_positive']}/{n_folds} folds positive.", "",
             "| set | n | share of vault events | mean p_10h | mean p_cal_10h | actual reach_10h | chance_10h | gap | lift | lo | hi |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['label']} | {r['n']:,} | {r['share']:.4%} | {r['mean_p_10h']:.4f} | {r['mean_p_cal_10h']:.4f} | "
                     f"{r['reach_10h']:.4f} | {r['chance_10h']:.4f} | {r['gap']:.4f} | {r['lift']:.4f} | {r['lo']:.4f} | "
                     f"{r['hi']:.4f} |")
    lines.append("")
    return lines, dict(base=base, rows=rows, s1d_ref=ref)


def calibration_section(df, top1):
    h_rep = json.load(open(os.path.join(LOG_DIR, "s1h_report.json")))
    folds_h = sorted(int(k) for k in h_rep["r4_picks"]["0.01"]["per_month"])
    assert folds_h == list(range(folds_h[0], folds_h[-1] + 1))
    fold_txt = f"folds {folds_h[0]}-{folds_h[-1]}"
    lines = ["### Vault calibration at 2 h, 5 h, 10 h (predicted vs actual; reported, not gated)",
             "Deciles are cut from the vault events' own p (S1-H's R3 recipe). Test-month columns are s1h_report.json's "
             f"R3 deciles ({fold_txt} pooled, out-of-fold test predictions of the per-fold models), read not recomputed; the "
             "vault is scored by the single pre-vault refit, a different fit, so the two sides are not the same model. "
             "2 h and 5 h have raw p only: step 4 fitted the isotonic map p_cal at 10 h only, and none is fitted here.", ""]
    out = {}
    for h in HORIZONS:
        p, y = df[f"p_{h}h"].to_numpy(), df[f"reach_{h}h"].to_numpy()
        cuts = np.quantile(p, np.arange(1, 10) / 10.0)
        bidx = np.digitize(p, cuts)
        r3 = h_rep["r3_calibration_deciles"][str(h)]["bins"]
        hdr = "| bucket | n | mean predicted | actual reach | actual - predicted |"
        if h == 10:
            hdr += " mean p_cal_10h | actual - p_cal |"
        hdr += " test-month mean predicted | test-month actual |"
        lines += [f"**{h} h**", hdr, "|---|" + "---|" * (hdr.count("|") - 2)]
        rows = []
        for b in range(10):
            m = bidx == b
            row = dict(bucket=f"decile {b}", n=int(m.sum()), pred=float(p[m].mean()), actual=float(y[m].mean()),
                       test_pred=r3[str(b)]["mean_raw"], test_actual=r3[str(b)]["actual_reach"])
            if h == 10:
                row["pcal"] = float(df.loc[m, "p_cal_10h"].mean())
            rows.append(row)
        sets = [("all vault events", np.ones(len(df), dtype=bool))]
        sets.append((f"own top 1% by p_{h}h", top1[h]))
        for q in QS:
            sets.append((f"Rule A picks q={q}", df[f"pick_{q}"].to_numpy()))
        for label, m in sets:
            row = dict(bucket=label, n=int(m.sum()), pred=float(p[m].mean()), actual=float(y[m].mean()),
                       test_pred=None, test_actual=None)
            if h == 10:
                row["pcal"] = float(df.loc[m, "p_cal_10h"].mean())
            if label.startswith("Rule A"):
                q = label.split("=")[1]
                pooled = h_rep["r4_picks"][q].get("pooled")
                if pooled is not None:
                    row["test_pred"], row["test_actual"] = pooled.get(f"mean_raw_{h}h"), pooled.get(f"actual_{h}h")
            rows.append(row)
        for r in rows:
            line = f"| {r['bucket']} | {r['n']:,} | {r['pred']:.4f} | {r['actual']:.4f} | {r['actual'] - r['pred']:+.4f} |"
            if h == 10:
                line += f" {r['pcal']:.4f} | {r['actual'] - r['pcal']:+.4f} |"
            line += f" {fmt('{:.4f}', r['test_pred'])} | {fmt('{:.4f}', r['test_actual'])} |"
            lines.append(line)
            log(f"[VREP] calib h={h} {r['bucket']}: n={r['n']:,} pred {r['pred']:.4f} actual {r['actual']:.4f}"
                + (f" p_cal {r['pcal']:.4f}" if h == 10 else ""))
        lines.append("")
        out[h] = rows
    return lines, out


def known_gaps():
    model = json.load(open(os.path.join(LOG_DIR, "s1_prevault_model.json")))
    settings = json.load(open(os.path.join(LOG_DIR, "s1_vault_picks_settings.json")))
    score_log = os.path.join(LOG_DIR, "vault_pull3", "vault-score_i-09ef2cd4868ff3b29.log")
    refit_log = os.path.join(LOG_DIR, "vault_pull2", "vault-refit_i-0eb1f51d55a4103b4.log")
    unseen = [ln.strip() for ln in open(score_log, errors="replace") if "events with at least one unseen leg" in ln]
    cdcap = [ln.strip() for ln in open(refit_log, errors="replace") if "inner CD sweep cap" in ln]
    assert len(unseen) == 1 and len(cdcap) == 1, (len(unseen), len(cdcap))
    shutdown = [ln for ln in open(score_log, errors="replace") if "Shutdown scheduled for" in ln]
    assert len(shutdown) == 1 and VAULT_OPENED in shutdown[0], (VAULT_OPENED, shutdown)
    lines = ["### Known gaps (vault run)",
             "- slippage excluded by the user's choice (legs are small): costs are a lower bound and results an upper bound.",
             "- max_leverage is today's snapshot (hindsight); maker fills are assumed to fill; liquidation is checked on 1-minute closes.",
             "- the vault was opened once (features in step 3, backtest in step 5, labels again here in step 6); no pass/fail rule; "
             "settings were frozen before any vault row was read."]
    lines += [f"- model JSON known_gaps: {g}" for g in model["known_gaps"]]
    lines += [f"- inner coordinate-descent cap: {cdcap[0]}",
              f"- {unseen[0]}",
              f"- p_cal pool: folds {settings['pool_folds']}, guard_inclusive={settings['guard_inclusive']}, n_fit "
              f"{settings['n_fit']:,} (S1-H's recipe literally, per the planner's ruling 2026-11-12; the brief's wording said "
              f"folds 1-7 and a strict guard)."]
    return lines


def main():
    log(f"[VREP] sha256 s1_vault_report.py {sha256(__file__)}")
    rng = np.random.default_rng(SEED)
    sbs_lines, sbs = side_by_side()
    df = load_vault_table()
    top1 = {h: top_k_mask(df[f"p_{h}h"].to_numpy(), 0.01, rng) for h in HORIZONS}     # drawn once, reused (checker 2)
    lift_lines, lift = lift_section(df, rng, top1)
    cal_lines, cal = calibration_section(df, top1)
    lines = [f"{MARKER} VAULT (opened once, {VAULT_OPENED}): test months vs vault, vault lift and calibration "
             f"(scripts s1_vault_report.py, s1_profit1_numbers_gen.py with PROFIT1_VAULT=1)", ""]
    lines += sbs_lines + lift_lines + cal_lines + known_gaps()
    json.dump(dict(side_by_side=sbs, lift=lift, calibration={str(k): v for k, v in cal.items()}),
              open(os.path.join(LOG_DIR, "s1_vault_report.json"), "w"), indent=2, default=str)
    text = "\n" + "\n".join(lines) + "\n"
    excerpt = os.path.join(NUMBERS_DIR, "s1_vault_report_section.md")
    open(excerpt, "w").write(text)
    log(f"[VREP] section written: {excerpt} (sha256 {sha256(excerpt)})")
    existing = open(NUMBERS_MD).read()
    if MARKER in existing:
        log(f"[VREP] NUMBERS.md already has {MARKER!r} -- not appending again")
    elif os.environ.get("NUMGEN_APPEND", "") != "1":
        log("[VREP] NUMGEN_APPEND not set: NUMBERS.md NOT appended (checker reviews the log first)")
    else:
        with open(NUMBERS_MD, "a") as f:
            f.write(text)
        log(f"[VREP] NUMBERS.md appended: {NUMBERS_MD}")
    assert open(excerpt).read() == text
    log("[VREP] done")


if __name__ == "__main__":
    main()
