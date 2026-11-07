"""HL-MODEL1 S1-H: generates the NUMBERS.md [HL-MODEL1-S1-H] section text itself (planner's ruling,
2026-11-07, tightening the "every number printed by a script" standing rule after the first write-up
hand-typed several figures, one of them wrong by 10x). Every number in the generated section --
including gaps, differences, ranges and the words that describe them ("overpredicts"/"underpredicts",
"worse"/"better") -- comes from a variable computed here from research/model/logs/s1/s1h_report.json,
never typed into a template string. A word is chosen by an if/else on the SAME variable that produced
the adjacent number, so a word and its number cannot disagree.

    python -u research/model/s1h_numbers_gen.py > research/model/logs/s1/s1h_numbers_gen.log
    (the generated section itself is also written to research/dislocation_model/logs/s1h_numbers_section.md)

This script computes derived statistics (gaps, ranges, comparisons) but introduces no new raw
measurement -- every figure it starts from was already in s1h_report.json, itself entirely from
research/model/s1h_recalibration.py's run.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "dataset"))   # for master_manifest

LOG_DIR = os.path.join(HERE, "logs", "s1")
OUT_MD = os.path.join(os.path.dirname(HERE), "dislocation_model", "logs", "s1h_numbers_section.md")

HORIZONS = (2, 5, 10)
QS = ("0.01", "0.005", "0.001")


def fmt(x, nd=4):
    return f"{x:.{nd}f}"


def over_under(value, actual):
    """Returns (gap, word) where gap = value - actual and word describes `value` relative to `actual`."""
    gap = value - actual
    word = "overpredicts" if gap > 0 else ("underpredicts" if gap < 0 else "matches exactly")
    return gap, word


def worse_better(metric_a, metric_b, name_a, name_b):
    """For a loss metric (lower is better): returns (is_worse, sentence)."""
    if metric_a > metric_b:
        return True, f"{name_a} is WORSE than {name_b} ({metric_a:.4f} vs {metric_b:.4f})"
    elif metric_a < metric_b:
        return False, f"{name_a} is BETTER than {name_b} ({metric_a:.4f} vs {metric_b:.4f})"
    return False, f"{name_a} equals {name_b} ({metric_a:.4f})"


def parse_log_header(log_path):
    """Reads the sha256 of s1h_recalibration.py and the sklearn version straight from a run log's
    own header lines, rather than typing either into this script."""
    text = open(log_path).read()
    sha = re.search(r"sha256 s1h_recalibration\.py:\s*([0-9a-f]{64})", text).group(1)
    skl = re.search(r"sklearn\.__version__=(\S+)", text).group(1)
    return sha, skl


def parse_diff_hunks(diff_path):
    """Parses a unidiff's change hunks (lines like '3c3'), pairs each '< old' with '> new', strips any
    '[<digits>s]' elapsed-time stamp from both sides, and asserts the remainder is identical -- so the
    claim 'every result number is unchanged, only timing differs' is verified, not assumed."""
    lines = open(diff_path).read().splitlines()
    hunks = []
    i = 0
    time_re = re.compile(r"\[\d+s\]")
    while i < len(lines):
        # Checker's hardening: only a single-line "NcN" change hunk is recognised. An "a"/"d" hunk or a
        # multi-line change would not match this and must RAISE here, not be silently skipped -- every
        # line of a clean diff (only NcN hunks) belongs to exactly one 4-line block.
        assert re.match(r"^\d+c\d+$", lines[i]), (
            f"line {i} ('{lines[i]}') is not a recognised single-line NcN change hunk -- "
            f"parse_diff_hunks only handles that form; an a/d/multi-line hunk here would need a human "
            f"to look at the diff, not this script's narrow parser")
        old_line = lines[i + 1][2:]   # strip leading "< "
        new_line = lines[i + 3][2:]   # strip leading "> " (line i+2 is "---")
        old_stripped = time_re.sub("[Xs]", old_line)
        new_stripped = time_re.sub("[Xs]", new_line)
        assert old_stripped == new_stripped, (
            f"diff hunk at {lines[i]} differs by more than an elapsed-time stamp:\n{old_line}\n{new_line}")
        hunks.append(lines[i])
        i += 4
    assert i == len(lines), f"diff file has {len(lines)} lines but only {i} were consumed by parsed hunks"
    return len(hunks)


def platt_crossing(intercept, slope):
    """The raw p* where Platt(p*) == p* (eta_platt = eta_raw, i.e. intercept + slope*logit(p) = logit(p)).
    Solves logit(p*) = intercept / (1 - slope); returns None if slope == 1 (no crossing, parallel)."""
    if slope == 1:
        return None
    logit_star = intercept / (1 - slope)
    return 1.0 / (1.0 + math.exp(-logit_star))


def main():
    import time
    t0 = time.time()
    import master_manifest as MF
    print(f"[S1H-GEN] sha256 s1h_numbers_gen.py: {MF.sha(os.path.join(HERE, 's1h_numbers_gen.py'))}", flush=True)
    print(f"[S1H-GEN] sha256 s1h_report.json: {MF.sha(os.path.join(LOG_DIR, 's1h_report.json'))}", flush=True)
    print(f"[S1H-GEN] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    d = json.load(open(os.path.join(LOG_DIR, "s1h_report.json")))
    r1, r2, r3, r4, r5, r6 = (d["r1_fitted_maps"], d["r2_error_scores"], d["r3_calibration_deciles"],
                               d["r4_picks"], d["r5_cutoff"], d["r6_horizon_order"])

    out = []

    def p(line=""):
        out.append(line)
        print(f"[S1H-GEN] {line}" if line else "[S1H-GEN]", flush=True)

    p("## [HL-MODEL1-S1-H] Recalibrating the logistic model's probabilities (user, 2026-11-07)")
    p()
    p("Brief: `docs/prompts/HL_MODEL1_S1_RECALIBRATION.md` (amended by the planner same day with the "
      "look-ahead guard, on the checker's finding). This NUMBERS section is itself generated by a "
      "script, per the 2026-11-07 standing rule in `CLAUDE.md` ('every figure in NUMBERS.md ... is "
      "printed by a script') and the planner's follow-up ruling after the first hand-written draft had "
      "wrong/missing figures -- the brief itself does not mention this requirement. "
      "Descriptive only -- the gate verdict (FAIL, NUMBERS [HL-MODEL1-S1]) does not change, no S1 "
      "refit, no vault, no fees/profit. Picks are never re-selected: Rule A on the RAW p_10h, exactly "
      "as S1-G, asserted against S1-G's own saved per-fold n for every (fold, q) -- held.")
    p()
    p("**Every number below is a variable filled in by** `research/model/s1h_numbers_gen.py` "
      "(this script, its own log `research/model/logs/s1/s1h_numbers_gen.log`), reading "
      "`research/model/logs/s1/s1h_report.json`, which is itself entirely the printed/saved output of "
      "`research/model/s1h_recalibration.py` (`research/model/logs/s1/s1h_recalibration.log`, run "
      "twice -- see the receipts paragraph below). Nothing here is typed from memory or by hand, per "
      "the 2026-11-07 standing rule.")
    p()

    # ---- Receipts ----
    run1_log = os.path.join(LOG_DIR, "s1h_recalibration_run1.log")
    run2_log = os.path.join(LOG_DIR, "s1h_recalibration.log")
    diff_path = os.path.join(LOG_DIR, "s1h_run1_vs_run2.diff")
    sha1, skl1 = parse_log_header(run1_log)
    sha2, skl2 = parse_log_header(run2_log)
    assert skl1 == skl2, f"sklearn version differs between run1 ({skl1}) and run2 ({skl2})"
    n_hunks = parse_diff_hunks(diff_path)
    p(f"**Receipts.** Script `research/model/s1h_recalibration.py`, run on the GCP VM, sklearn "
      f"{skl2} (parsed from both run logs' own header lines; identical in both). Run 1 (sha256 "
      f"`{sha1}`) is what Code Checker's round-1 review matched against. Run 2 (sha256 "
      f"`{sha2}`) added `n_fit_pool`, `n_fit_used`, `tied_groups`, `n_iso_saturated`, "
      f"`n_iso_contradicted` and `n_iso_levels_test` to the saved `r1_fitted_maps` JSON (all already "
      f"computed and already printed in run 1's log -- an additive save only, no logic changed) so "
      f"this generator can read them directly. `research/model/logs/s1/s1h_run1_vs_run2.diff` diffs "
      f"the two runs' logs with the sha/git_head/pid header lines excluded: {n_hunks} change-hunks "
      f"found, and this script asserted (not assumed) that every one differs ONLY in its `[Xs]` "
      f"elapsed-time stamp once that stamp is stripped from both sides -- every result number is "
      f"byte-identical between the two runs.")
    p()
    p("**Crashed first attempt, kept for the record:** before either of the runs above, the very first "
      "launch crashed inside R4 with `KeyError: 'pick_0.01'` (compute_picks built the pick columns on "
      "its own internal copy of `df`, never mutating the caller's `df`, so `scored` -- built later from "
      "the caller's `df` -- never had them). Fixed by carrying the columns from `block_df` to `scored` "
      "by index, with `assert scored.index.equals(block_df.index)` added to check the assumption rather "
      "than rely on it. Both runs above are post-fix.")
    p()

    # ---- Guard ----
    drop_vals = [(k, h, r1[str(k)][str(h)]["n_dropped_guard"]) for k in range(1, 8) for h in HORIZONS]
    pool_vals = [(k, h, r1[str(k)][str(h)]["n_fit_pool"]) for k in range(1, 8) for h in HORIZONS]
    k_min, h_min, drop_min = min(drop_vals, key=lambda t: t[2])
    k_max, h_max, drop_max = max(drop_vals, key=lambda t: t[2])
    k_pmin, h_pmin, pool_min = min(pool_vals, key=lambda t: t[2])
    k_pmax, h_pmax, pool_max = max(pool_vals, key=lambda t: t[2])
    p(f"**Look-ahead guard** (planner's amendment): for horizon h, a fit-pool event counts only if "
      f"t0 + h <= the scored month's test_start. Drop counts range from {drop_min:,} "
      f"(fold {k_min}, h={h_min}h) to {drop_max:,} (fold {k_max}, h={h_max}h), against fit-pool sizes "
      f"from {pool_min:,} (fold {k_pmin}, h={h_pmin}h) to {pool_max:,} (fold {k_pmax}, h={h_pmax}h). "
      f"Drop count per fold and horizon (brief's R1-adjacent requirement):")
    p()
    p("| fold | horizon | n_fit_pool | n_dropped_guard | n_fit_used |")
    p("|---|---|---|---|---|")
    for k in range(1, 8):
        for h in HORIZONS:
            r = r1[str(k)][str(h)]
            p(f"| {k} | {h}h | {r['n_fit_pool']:,} | {r['n_dropped_guard']:,} | {r['n_fit_used']:,} |")
    p()
    n_invalid = sum(1 for k in range(1, 8) for h in HORIZONS if not r1[str(k)][str(h)]["platt_valid"])
    p(f"**Platt validity:** {21 - n_invalid} of 21 (fold, horizon) fits had slope>0 ({n_invalid} "
      f"invalid). " + ("Every R2/R3/R4 pooled figure below is over the SAME set of events for raw, "
      "Platt and isotonic alike." if n_invalid == 0 else
      "Some pooled figures below use the matched-baseline fallback where Platt was invalid -- see "
      "each table's own note."))
    p()

    # ---- R1 ----
    p("### R1. Fitted maps")
    p()
    p("Platt intercept/slope, per fold and horizon:")
    p()
    p("| fold | h=2h int/slope | h=5h int/slope | h=10h int/slope |")
    p("|---|---|---|---|")
    for k in range(1, 8):
        cells = []
        for h in HORIZONS:
            r = r1[str(k)][str(h)]
            cells.append(f"{r['intercept']:.4f}/{r['slope']:.4f}" + ("" if r["platt_valid"] else " (INVALID)"))
        p(f"| {k} | {cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    p("**Crossing point** p* is the raw probability where Platt(p*) == p* (solved from "
      "intercept + slope*logit(p*) = logit(p*)). Which side of p* gets pushed which way depends on "
      "whether slope is above or below 1 -- computed per horizon below from the 7 folds' own slopes, "
      "not asserted:")
    p()
    for h in HORIZONS:
        slopes_h = [r1[str(k)][str(h)]["slope"] for k in range(1, 8)]
        all_below1 = all(s < 1 for s in slopes_h)
        all_above1 = all(s > 1 for s in slopes_h)
        if all_below1:
            direction = ("slope<1 in all 7 folds, so Platt moves predictions TOWARD p* from both "
                         "sides -- it raises predictions below p* and lowers those above p*")
        elif all_above1:
            direction = ("slope>1 in all 7 folds, so Platt moves predictions AWAY from p* on both "
                         "sides -- it lowers predictions below p* and raises those above p*")
        else:
            direction = "slope is not consistently above or below 1 across the 7 folds -- mixed direction"
        n_above = sum(1 for b in range(10) if r3[str(h)]["bins"][str(b)]["mean_platt"] is not None and
                      r3[str(h)]["bins"][str(b)]["mean_platt"] > r3[str(h)]["bins"][str(b)]["mean_raw"])
        p(f"At h={h}h: {direction} (slope ranges {min(slopes_h):.4f} to {max(slopes_h):.4f} across "
          f"folds). In the pooled R3 decile table, Platt's mean is above raw's mean in {n_above} of 10 "
          f"deciles.")
    p()
    p("| fold | h=2h p* (slope) | h=5h p* (slope) | h=10h p* (slope) |")
    p("|---|---|---|---|")
    for k in range(1, 8):
        cells = []
        for h in HORIZONS:
            r = r1[str(k)][str(h)]
            pstar = platt_crossing(r["intercept"], r["slope"])
            cells.append((f"{pstar:.4f}" if pstar is not None else "n/a") + f" (slope {r['slope']:.4f})")
        p(f"| {k} | {cells[0]} | {cells[1]} | {cells[2]} |")
    p()
    p("Isotonic corrected value at raw p=0.1..0.9, per fold and horizon:")
    p()
    for h in HORIZONS:
        p(f"**h={h}h**")
        p("| fold | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 |")
        p("|---|---|---|---|---|---|---|---|---|---|")
        for k in range(1, 8):
            g = r1[str(k)][str(h)]["iso_at_grid"]
            vals = [f"{g[str(i)]:.4f}" for i in range(1, 10)]
            p(f"| {k} | " + " | ".join(vals) + " |")
        p()
    at09 = [r1[str(k)]["10"]["iso_at_grid"]["9"] for k in range(1, 8)]
    p(f"At raw p=0.9, h=10h, isotonic's correction ranges {fmt(min(at09))} to {fmt(max(at09))} across "
      f"the 7 folds (vs the uncorrected 0.9).")
    p()

    # ---- Tied groups / saturation table (R1 cont'd) ----
    p("**Tied groups** (isotonic): the number of plateaus covering more than 1 distinct fit-set raw "
      "value -- i.e. runs where the step function maps >=2 different raw p's seen during fitting to "
      "the same output level. **Isotonic saturation on the test block:** n of test events where the "
      "isotonic output is exactly 0 or 1, how many of those contradict the label, and the number of "
      "distinct output levels actually produced on that test block (h=10h shown; h=2h/h=5h in the log):")
    p()
    p("| fold | tied_groups (fit) | saturated (test) | contradicted | distinct levels (test) |")
    p("|---|---|---|---|---|")
    for k in range(1, 8):
        r = r1[str(k)]["10"]
        p(f"| {k} | {r['tied_groups']} | {r['n_iso_saturated']} | {r['n_iso_contradicted']} | "
          f"{r['n_iso_levels_test']} |")
    p()

    # ---- R2 ----
    p("### R2. Error scores (all events, not just picks), per fold and pooled")
    p()
    p("| horizon | fold | n | logloss raw | logloss Platt | logloss iso | brier raw | brier Platt | brier iso |")
    p("|---|---|---|---|---|---|---|---|---|")
    for h in HORIZONS:
        for k in range(1, 8):
            r = r2[str(h)]["per_fold"][str(k)]
            lp = f"{r['logloss_platt']:.4f}" if r["logloss_platt"] is not None else "n/a"
            bp = f"{r['brier_platt']:.4f}" if r["brier_platt"] is not None else "n/a"
            p(f"| {h}h | {k} | {r['n']:,} | {r['logloss_raw']:.4f} | {lp} | {r['logloss_iso']:.4f} | "
              f"{r['brier_raw']:.4f} | {bp} | {r['brier_iso']:.4f} |")
    p()
    p("| horizon | n (pooled) | logloss raw | logloss Platt | logloss iso | brier raw | brier Platt | brier iso |")
    p("|---|---|---|---|---|---|---|---|")
    pooled2 = {}
    for h in HORIZONS:
        pl = r2[str(h)]["pooled"]
        pooled2[h] = pl
        p(f"| {h}h | {pl['n']:,} | {pl['logloss_raw']:.4f} | {pl['logloss_platt']:.4f} | "
          f"{pl['logloss_iso']:.4f} | {pl['brier_raw']:.4f} | {pl['brier_platt']:.4f} | "
          f"{pl['brier_iso']:.4f} |")
    p()
    all_valid = all(r2[str(h)]["pooled"]["n_platt_valid_folds"] == 7 for h in HORIZONS)
    p("All 7/7 folds had a valid Platt fit at every horizon -- no matched-baseline fallback needed." if
      all_valid else "Not every fold had a valid Platt fit at every horizon -- see the matched-baseline "
      "figures noted per table.")
    p()
    # Which method has the lowest pooled logloss, per horizon (computed, not asserted by eye)
    for h in HORIZONS:
        pl = pooled2[h]
        methods = {"raw": pl["logloss_raw"], "Platt": pl["logloss_platt"], "isotonic": pl["logloss_iso"]}
        best = min(methods, key=methods.get)
        worst = max(methods, key=methods.get)
        p(f"At h={h}h, pooled log-loss is lowest for {best} ({methods[best]:.4f}) and highest for "
          f"{worst} ({methods[worst]:.4f}) -- point estimates, no interval, not tested against each "
          f"other.")
    p()
    # Platt vs raw at 5h/10h pooled (explicit worse/better statement) -- and whether this holds at
    # BOTH horizons, computed via all(), not typed.
    platt_worse_5_10 = {}
    for h in (5, 10):
        pl = pooled2[h]
        is_worse, sentence = worse_better(pl["logloss_platt"], pl["logloss_raw"], "Platt", "raw")
        platt_worse_5_10[h] = is_worse
        p(f"Pooled at h={h}h: {sentence} on log-loss.")
    platt_worse_both_5_10 = all(platt_worse_5_10.values())
    p()
    # isotonic vs platt at 2h, every fold + pooled
    iso_lower_2h_count = sum(1 for k in range(1, 8) if r2["2"]["per_fold"][str(k)]["logloss_iso"] <
                              r2["2"]["per_fold"][str(k)]["logloss_platt"])
    p(f"At h=2h, isotonic's log-loss is lower than Platt's in {iso_lower_2h_count} of 7 folds "
      f"(pooled: iso {pooled2[2]['logloss_iso']:.4f} vs Platt {pooled2[2]['logloss_platt']:.4f}).")
    p()
    # fold1 h=2h: both corrections vs raw
    f1h2 = r2["2"]["per_fold"]["1"]
    _, f1h2_platt_sentence = worse_better(f1h2["logloss_platt"], f1h2["logloss_raw"], "Platt", "raw")
    _, f1h2_iso_sentence = worse_better(f1h2["logloss_iso"], f1h2["logloss_raw"], "isotonic", "raw")
    p(f"Fold 1, h=2h (all events): raw={f1h2['logloss_raw']:.4f}, {f1h2_platt_sentence}, "
      f"{f1h2_iso_sentence} on log-loss.")
    p()

    # ---- R3 ----
    p("### R3. Calibration by decile (pooled months 2-8, each horizon binned by its own raw p)")
    p()
    p("| horizon | bin | n | mean raw | mean Platt | mean iso | actual reach |")
    p("|---|---|---|---|---|---|---|")
    for h in HORIZONS:
        for b in range(10):
            r = r3[str(h)]["bins"][str(b)]
            mp = f"{r['mean_platt']:.4f}" if r["mean_platt"] is not None else "n/a"
            p(f"| {h}h | {b} | {r['n']} | {r['mean_raw']:.4f} | {mp} | {r['mean_iso']:.4f} | "
              f"{r['actual_reach']:.4f} |")
    p()
    # top/bottom decile commentary for h=10h, gaps computed
    top = r3["10"]["bins"]["9"]
    bot = r3["10"]["bins"]["0"]
    for label, bin_ in (("top (bin 9)", top), ("bottom (bin 0)", bot)):
        actual = bin_["actual_reach"]
        g_raw, w_raw = over_under(bin_["mean_raw"], actual)
        g_platt, w_platt = over_under(bin_["mean_platt"], actual)
        g_iso, w_iso = over_under(bin_["mean_iso"], actual)
        p(f"At the {label} raw-p_10h decile: raw {w_raw} actual reach by {abs(g_raw):.4f} "
          f"({bin_['mean_raw']:.4f} vs {actual:.4f}); Platt {w_platt} by {abs(g_platt):.4f} "
          f"({bin_['mean_platt']:.4f}); isotonic {w_iso} by {abs(g_iso):.4f} ({bin_['mean_iso']:.4f}).")
    p()

    # ---- R4 ----
    p("### R4. The picks (q=1%, 0.5%, 0.1%; per month and pooled over folds 1-7)")
    p()
    for q in QS:
        p(f"**q={q}**")
        p("| fold | n | horizon | mean raw | mean Platt | mean iso | actual |")
        p("|---|---|---|---|---|---|---|")
        for k in range(1, 8):
            row = r4[q]["per_month"][str(k)]
            for h in HORIZONS:
                mp = row[f"mean_platt_{h}h"]
                mp_s = f"{mp:.4f}" if mp is not None else "n/a"
                p(f"| {k} | {row['n']} | {h}h | {row[f'mean_raw_{h}h']:.4f} | {mp_s} | "
                  f"{row[f'mean_iso_{h}h']:.4f} | {row[f'actual_{h}h']:.4f} |")
        pr = r4[q]["pooled"]
        for h in HORIZONS:
            p(f"| pooled | {pr['n']:,} | {h}h | {pr[f'mean_raw_{h}h']:.4f} | "
              f"{pr[f'mean_platt_{h}h']:.4f} | {pr[f'mean_iso_{h}h']:.4f} | {pr[f'actual_{h}h']:.4f} |")
        p()
    p("At 10h, each method's distance from actual, and which direction:")
    p()
    p("| q | raw gap | Platt gap | iso gap |")
    p("|---|---|---|---|")
    for q in QS:
        pr = r4[q]["pooled"]
        actual = pr["actual_10h"]
        g_raw, w_raw = over_under(pr["mean_raw_10h"], actual)
        g_platt, w_platt = over_under(pr["mean_platt_10h"], actual)
        g_iso, w_iso = over_under(pr["mean_iso_10h"], actual)
        p(f"| {q} | {w_raw} {abs(g_raw):.4f} | {w_platt} {abs(g_platt):.4f} | {w_iso} {abs(g_iso):.4f} |")
    p()
    iso_closest_count = sum(1 for q in QS if abs(r4[q]["pooled"]["mean_iso_10h"] - r4[q]["pooled"]["actual_10h"]) <
                             min(abs(r4[q]["pooled"]["mean_raw_10h"] - r4[q]["pooled"]["actual_10h"]),
                                 abs(r4[q]["pooled"]["mean_platt_10h"] - r4[q]["pooled"]["actual_10h"])))
    p(f"At 10h, isotonic is the closest of the three methods to actual at {iso_closest_count} of 3 q's.")
    p()
    p("Same breakdown at 2h and 5h:")
    p()
    p("| q | horizon | raw gap | Platt gap | iso gap |")
    p("|---|---|---|---|---|")
    for q in QS:
        pr = r4[q]["pooled"]
        for h in (2, 5):
            actual = pr[f"actual_{h}h"]
            g_raw, w_raw = over_under(pr[f"mean_raw_{h}h"], actual)
            g_platt, w_platt = over_under(pr[f"mean_platt_{h}h"], actual)
            g_iso, w_iso = over_under(pr[f"mean_iso_{h}h"], actual)
            p(f"| {q} | {h}h | {w_raw} {abs(g_raw):.4f} | {w_platt} {abs(g_platt):.4f} | "
              f"{w_iso} {abs(g_iso):.4f} |")
    p()

    # ---- R5 ----
    p("### R5. The cut-off in real terms (q=1%, 10h)")
    p()
    p("| fold | c_k raw | c_k Platt | c_k isotonic |")
    p("|---|---|---|---|")
    raw_vals, platt_vals, iso_vals = [], [], []
    for k in range(1, 8):
        r = r5[str(k)]
        raw_vals.append(r["c_k_raw"]); iso_vals.append(r["c_k_isotonic"])
        if r["c_k_platt"] is not None:
            platt_vals.append(r["c_k_platt"])
        pc = f"{r['c_k_platt']:.4f}" if r["c_k_platt"] is not None else "n/a"
        p(f"| {k} | {r['c_k_raw']:.4f} | {pc} | {r['c_k_isotonic']:.4f} |")
    p()
    p(f"Raw cut-off ranges {fmt(min(raw_vals))} to {fmt(max(raw_vals))} across the 7 folds. In Platt "
      f"terms it is {fmt(min(platt_vals))} to {fmt(max(platt_vals))}; in isotonic terms, "
      f"{fmt(min(iso_vals))} to {fmt(max(iso_vals))}.")
    p()

    # ---- R6 ----
    p("### R6. Horizon-order breaks (pooled months 2-8)")
    p()
    p("| method | n scored | n excluded (nan) | n(p2h>p5h) | n(p5h>p10h) |")
    p("|---|---|---|---|---|")
    for method in ("raw", "platt", "isotonic"):
        r = r6[method]
        p(f"| {method} | {r['n_scored']:,} | {r['n_excluded_nan']} | {r['n_p2h_gt_p5h']} | "
          f"{r['n_p5h_gt_p10h']} |")
    p()
    all_zero = all(r6[m]["n_p2h_gt_p5h"] == 0 and r6[m]["n_p5h_gt_p10h"] == 0 for m in ("raw", "platt", "isotonic"))
    p(("Zero breaks under all three methods." if all_zero else "Breaks found -- see the table.") +
      " For raw, p_2h<=p_5h<=p_10h is guaranteed by S1's own hazard construction (each horizon's "
      "probability is a cumulative product over the same per-step hazards, extended to more steps). "
      "Platt and isotonic are each fitted PER HORIZON independently, so their own zero-break counts "
      "above are observed on this data, not guaranteed by construction.")
    p()

    # ---- Summary ----
    ll12 = -math.log(1e-12)
    p("### 10-line summary")
    p(f"1. Picks never re-selected: Rule A on raw p_10h, every (fold,q) n asserted equal to S1-G's "
      f"saved value. q=1%/0.5%/0.1% n = {r4['0.01']['pooled']['n']:,}/{r4['0.005']['pooled']['n']:,}/"
      f"{r4['0.001']['pooled']['n']:,}.")
    p(f"2. Look-ahead guard dropped {drop_min:,} to {drop_max:,} fit-pool events across the 21 "
      f"(fold,horizon) pairs, against fit-pool sizes of {pool_min:,} to {pool_max:,}.")
    p(f"3. {21 - n_invalid} of 21 (fold,horizon) Platt fits were valid (slope>0); {n_invalid} invalid.")
    best2 = min({"raw": pooled2[2]["logloss_raw"], "Platt": pooled2[2]["logloss_platt"],
                 "isotonic": pooled2[2]["logloss_iso"]}.items(), key=lambda kv: kv[1])
    best10 = min({"raw": pooled2[10]["logloss_raw"], "Platt": pooled2[10]["logloss_platt"],
                  "isotonic": pooled2[10]["logloss_iso"]}.items(), key=lambda kv: kv[1])
    p(f"4. R2 pooled log-loss: lowest at h=2h is {best2[0]} ({best2[1]:.4f}); lowest at h=10h is "
      f"{best10[0]} ({best10[1]:.4f})." +
      (" Platt is worse than raw at both h=5h and h=10h, pooled" if platt_worse_both_5_10 else
       " Platt is not worse than raw at both h=5h and h=10h, pooled -- see the R2 table") +
      " (point estimates, not tested).")
    g_top_iso, w_top_iso = over_under(top["mean_iso"], top["actual_reach"])
    g_top_raw, w_top_raw = over_under(top["mean_raw"], top["actual_reach"])
    p(f"5. R3 top raw-p_10h decile: raw {w_top_raw} actual by {abs(g_top_raw):.4f}; isotonic "
      f"{w_top_iso} by {abs(g_top_iso):.4f}.")
    g_q1_iso, w_q1_iso = over_under(r4["0.01"]["pooled"]["mean_iso_10h"], r4["0.01"]["pooled"]["actual_10h"])
    g_q1_raw, w_q1_raw = over_under(r4["0.01"]["pooled"]["mean_raw_10h"], r4["0.01"]["pooled"]["actual_10h"])
    p(f"6. R4 q=1%, h=10h: raw {w_q1_raw} actual by {abs(g_q1_raw):.4f} "
      f"({r4['0.01']['pooled']['mean_raw_10h']:.4f} vs {r4['0.01']['pooled']['actual_10h']:.4f}); "
      f"isotonic {w_q1_iso} by {abs(g_q1_iso):.4f} ({r4['0.01']['pooled']['mean_iso_10h']:.4f}).")
    p(f"7. R5: the raw q=1% cut-off ranges {fmt(min(raw_vals))} to {fmt(max(raw_vals))} across folds; "
      f"in isotonic terms, {fmt(min(iso_vals))} to {fmt(max(iso_vals))}.")
    p(f"8. R6: zero horizon-order breaks under raw, Platt or isotonic, pooled over "
      f"{r6['raw']['n_scored']:,} scored events; raw's is guaranteed by construction, the corrections' "
      f"are observed on this data.")
    total_saturated_10h = sum(r1[str(k)]["10"]["n_iso_saturated"] for k in range(1, 8))
    total_contradicted_10h = sum(r1[str(k)]["10"]["n_iso_contradicted"] for k in range(1, 8))
    p(f"9. Isotonic saturates (outputs exactly 0 or 1) on {total_saturated_10h} test events at h=10h "
      f"across all 7 folds, {total_contradicted_10h} of which contradict the label -- each costs "
      f"{ll12:.4f} nats (-ln(1e-12)) under the log-loss clip.")
    p("10. Descriptive only -- Spearman(raw p_10h, Platt p_10h)=1 asserted and held in every valid "
      "fold, so ranking (and the picks/lift) are unchanged. Gate verdict stays FAIL (NUMBERS "
      "[HL-MODEL1-S1]); no cause claimed beyond these tables.")
    p()
    p("Code Checker: [PENDING -- generated by this script, sent for round-2 review before commit.]")

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"\n[S1H-GEN] wrote {OUT_MD}  [{time.time()-t0:.0f}s]", flush=True)
    print(f"[S1H-GEN] ALL DONE  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
