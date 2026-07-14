"""
Diagnostic: Rolling OU parameter estimation during each AVAX/LINK trade hold.

Hypothesis under test: the relationship drifts mid-trade for losers (time_stop exits)
in a way detectable BEFORE the "cross-back bar", while winners (take_profit exits) do
not show the same shift at the equivalent point in their hold.

Linked to spread_path_diagnostic.py (frozen-coefficient path) but kept SEPARATE to
avoid any edit that silently blends frozen-beta and rolling-beta logic (L7 failure mode).
Shares load_trade_log() from spread_path_diagnostic; min-distance and cross-back bar
computations are duplicated here with comments pointing to the source.

Read-only. Writes no files.

CAVEAT (also printed at runtime):
Rolling theta and rolling reversion-probability partly re-encode the price path. A
360-bar trailing window that covers a diverged spread shows weaker mean-reversion
BECAUSE it diverged. These metrics are only meaningful as exit signals if they LEAD the
cross-back bar. A shift that coincides with or lags the cross-back is the price path
re-encoded into the parameter estimate, not a structural signal — and is too late to act
on (you would exit at the bottom, no better than the time stop).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import numpy as np
import pandas as pd

from research.data_loader import get_price_levels
from research.ou_model import fit_ou, ou_reversion_probability
from research.pair_analysis import compute_spread
from diagnostics.spread_path_diagnostic import load_trade_log

# --- constants (confirmed against source files) ---
F         = 0.20   # tau decay fraction: signal_generator.py:26
WINDOW    = 360    # trailing bars per fit: run_backtest.py:174 + pairs_strategy.py:102
PROB_GATE = 0.67   # reversion-probability gate: signal_generator.py:23
FIDELITY_TOL = 1e-6

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "research", "trade_log_dump.json",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cross_back_idx(
    spread_frozen: np.ndarray,
    min_dist_idx: int,
    entry_spread: float,
    entry_above_mu: bool,
) -> int | None:
    """First bar at or after min_dist_idx where frozen spread crosses back past
    entry_spread in the adverse direction. Returns None if it never crosses back."""
    for i in range(min_dist_idx, len(spread_frozen)):
        if entry_above_mu and spread_frozen[i] >= entry_spread:
            return i
        if not entry_above_mu and spread_frozen[i] <= entry_spread:
            return i
    return None


def _fmt_bar(idx: int | None, n: int) -> str:
    return f"{idx}" if idx is not None else "N/A"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    W = 140

    # ------------------------------------------------------------------
    # Load price data
    # ------------------------------------------------------------------
    df = get_price_levels()
    assert "AVAX" in df.columns, "AVAX column missing from get_price_levels()"
    assert "LINK" in df.columns, "LINK column missing from get_price_levels()"

    avax_all   = df["AVAX"].values
    link_all   = df["LINK"].values
    timestamps = df.index

    print(f"[INFO] Price data: {df.index[0]} → {df.index[-1]}  ({len(df)} bars)")
    print(f"[INFO] WINDOW={WINDOW}, F={F}, PROB_GATE={PROB_GATE}, FIDELITY_TOL={FIDELITY_TOL:.0e}")
    print()

    # ------------------------------------------------------------------
    # Load trade log
    # ------------------------------------------------------------------
    trade_log = load_trade_log(_LOG_PATH)

    # ------------------------------------------------------------------
    # Phase B: per-trade rolling computation
    # ------------------------------------------------------------------
    all_results = []

    for t in trade_log:
        num           = t["trade_num"]
        entry_spread  = t["entry_spread"]
        exit_spread   = t["exit_spread"]
        mu_entry      = t["mu_at_entry"]
        beta_entry    = t["beta_at_entry"]
        alpha_entry   = t["alpha_at_entry"]
        sigma_entry   = t["sigma_at_entry"]
        theta_entry   = t["theta_at_entry"]
        exit_reason   = t["exit_reason"]

        sigma_stationary_entry = sigma_entry / math.sqrt(2.0 * theta_entry)
        entry_above_mu         = (entry_spread > mu_entry)

        # Bar selection — mirrors spread_path_diagnostic.py:75-81
        entry_ts = pd.Timestamp(t["entry_time"])
        exit_ts  = pd.Timestamp(t["exit_time"])
        entry_global_idx = df.index.get_loc(entry_ts)
        exit_global_idx  = df.index.get_loc(exit_ts)

        n_hold = exit_global_idx - entry_global_idx + 1  # inclusive

        # Frozen spread for cross-back and min-dist — mirrors spread_path_diagnostic.py:86
        hold_slice   = slice(entry_global_idx, exit_global_idx + 1)
        spread_frozen = (
            avax_all[hold_slice]
            - alpha_entry
            - beta_entry * link_all[hold_slice]
        )

        # Min-distance bar — mirrors spread_path_diagnostic.py:126-128
        abs_dist_frozen = np.abs(spread_frozen - mu_entry) / sigma_stationary_entry
        min_dist_idx    = int(np.argmin(abs_dist_frozen))

        # Cross-back bar (new logic, not in spread_path_diagnostic.py)
        cb_idx = _cross_back_idx(spread_frozen, min_dist_idx, entry_spread, entry_above_mu)

        # Rolling computation, bar by bar
        rows = []
        for local_i in range(n_hold):
            g       = entry_global_idx + local_i
            w_start = g - WINDOW + 1

            if w_start < 0:
                rows.append(None)   # not enough history — flag and skip
                continue

            pa_w = avax_all[w_start : g + 1]
            pb_w = link_all[w_start : g + 1]

            _, beta_t, alpha_t = compute_spread(pa_w, pb_w)
            ou = fit_ou(pa_w, pb_w)

            if not math.isfinite(ou.theta) or ou.theta <= 0:
                rows.append({"bar": local_i, "ts": timestamps[g], "fit_failed": True})
                continue

            theta_t          = ou.theta
            mu_t             = ou.mu
            sigma_t          = ou.sigma
            half_life_t      = math.log(2.0) / theta_t
            sigma_stat_t     = sigma_t / math.sqrt(2.0 * theta_t)
            tau_t            = math.log(1.0 / F) / theta_t

            spread_frozen_t  = avax_all[g] - alpha_entry - beta_entry * link_all[g]
            spread_rolling_t = avax_all[g] - alpha_t     - beta_t     * link_all[g]

            dist_frozen_t  = abs(spread_frozen_t  - mu_entry) / sigma_stationary_entry
            dist_rolling_t = abs(spread_rolling_t - mu_t)     / sigma_stat_t

            prob_frozen_mu_t  = ou_reversion_probability(
                spread_frozen_t,  theta_t, mu_entry, sigma_t, tau_t)
            prob_rolling_mu_t = ou_reversion_probability(
                spread_rolling_t, theta_t, mu_t,     sigma_t, tau_t)

            rows.append({
                "bar":              local_i,
                "ts":               timestamps[g],
                "fit_failed":       False,
                "theta_t":          theta_t,
                "beta_t":           beta_t,
                "mu_t":             mu_t,
                "sigma_t":          sigma_t,
                "half_life_t":      half_life_t,
                "dist_frozen_t":    dist_frozen_t,
                "dist_rolling_t":   dist_rolling_t,
                "prob_frozen_mu_t": prob_frozen_mu_t,
                "prob_rolling_mu_t":prob_rolling_mu_t,
            })

        all_results.append({
            "trade":                  t,
            "rows":                   rows,
            "entry_global_idx":       entry_global_idx,
            "exit_global_idx":        exit_global_idx,
            "spread_frozen":          spread_frozen,
            "min_dist_idx":           min_dist_idx,
            "cb_idx":                 cb_idx,
            "entry_above_mu":         entry_above_mu,
            "sigma_stationary_entry": sigma_stationary_entry,
            "beta_entry":             beta_entry,
            "theta_entry":            theta_entry,
            "mu_entry":               mu_entry,
            "sigma_entry":            sigma_entry,
            "alpha_entry":            alpha_entry,
        })

    # ------------------------------------------------------------------
    # Phase C: Fidelity guard
    # ------------------------------------------------------------------
    print("=" * W)
    print("SECTION 1: FIDELITY GUARD")
    print(f"  At each trade's entry bar, rolling fit on trailing {WINDOW} bars must")
    print(f"  reproduce logged beta_at_entry and theta_at_entry within {FIDELITY_TOL:.0e}.")
    print(f"  Failure means the window is misaligned with what the strategy fit —")
    print(f"  every downstream trajectory is untrustworthy.")
    print("=" * W)

    hdr = (f"{'#':>2}  {'outcome':<12}  {'beta_entry':>12}  {'beta_rolling':>12}"
           f"  {'beta_diff':>10}  {'theta_entry':>12}  {'theta_rolling':>13}"
           f"  {'theta_diff':>10}  {'guard'}")
    print(hdr)
    print("-" * W)

    guard_failed = False
    for res in all_results:
        t    = res["trade"]
        num  = t["trade_num"]
        rows = res["rows"]
        entry_row = rows[0]

        if entry_row is None or entry_row.get("fit_failed"):
            print(f"{num:>2}  {t['exit_reason']:<12}  [FIT FAILED AT ENTRY BAR]  FAIL")
            guard_failed = True
            continue

        beta_diff  = abs(entry_row["beta_t"]  - res["beta_entry"])
        theta_diff = abs(entry_row["theta_t"] - res["theta_entry"])
        ok = (beta_diff < FIDELITY_TOL and theta_diff < FIDELITY_TOL)
        if not ok:
            guard_failed = True
        tag = "PASS" if ok else "FAIL"
        print(
            f"{num:>2}  {t['exit_reason']:<12}  "
            f"{res['beta_entry']:>12.8f}  {entry_row['beta_t']:>12.8f}  "
            f"{beta_diff:>10.2e}  "
            f"{res['theta_entry']:>12.8f}  {entry_row['theta_t']:>13.8f}  "
            f"{theta_diff:>10.2e}  {tag}"
        )

    if guard_failed:
        print()
        print("[STOP] Fidelity guard failed on one or more trades.")
        print("       Rolling window does not reproduce logged entry parameters.")
        print("       All downstream trajectory analysis is untrustworthy. Halting.")
        return

    print(f"  Overall: PASS — rolling {WINDOW}-bar window reproduces entry parameters for all 6 trades.")
    print()

    # ------------------------------------------------------------------
    # Section 2: Per-bar rolling tables (all 6 trades)
    # ------------------------------------------------------------------
    print("=" * W)
    print("SECTION 2: PER-BAR ROLLING PARAMETER TABLES")
    print("=" * W)

    for res in all_results:
        t          = res["trade"]
        num        = t["trade_num"]
        rows       = res["rows"]
        min_i      = res["min_dist_idx"]
        cb_i       = res["cb_idx"]

        print()
        print("=" * W)
        print(
            f"Trade {num}  ({t['exit_reason']})  "
            f"beta_entry={res['beta_entry']:.6f}  "
            f"theta_entry={res['theta_entry']:.6f}  "
            f"mu_entry={res['mu_entry']:.8f}  "
            f"sigma_stat_entry={res['sigma_stationary_entry']:.8f}"
        )
        print(
            f"  entry_spread={t['entry_spread']:.8f}  "
            f"min_dist_bar={min_i}  "
            f"cross_back_bar={'N/A' if cb_i is None else cb_i}"
        )
        print("-" * W)

        col_hdr = (
            f"{'bar':>4}  {'timestamp':<16}  "
            f"{'theta_t':>9}  {'beta_t':>9}  {'mu_t':>10}  {'half_life':>9}  "
            f"{'dist_frz':>8}  {'dist_rol':>8}  "
            f"{'prob_frz':>8}  {'prob_rol':>8}  flags"
        )
        print(col_hdr)
        print("-" * W)

        for row in rows:
            if row is None:
                continue
            i = row["bar"]
            flags = []
            if i == 0:             flags.append("[ENTRY]")
            if i == len(rows) - 1: flags.append("[EXIT]")
            if i == min_i:         flags.append("[MIN_MU]")
            if cb_i is not None and i == cb_i: flags.append("[CROSS_BACK]")
            flag_str = "  ".join(flags)

            if row.get("fit_failed"):
                print(f"{i:>4}  {str(row['ts']):<16}  [fit-failed]  {flag_str}")
                continue

            print(
                f"{i:>4}  {str(row['ts']):<16}  "
                f"{row['theta_t']:>9.6f}  {row['beta_t']:>9.6f}  "
                f"{row['mu_t']:>10.6f}  {row['half_life_t']:>9.2f}  "
                f"{row['dist_frozen_t']:>8.4f}  {row['dist_rolling_t']:>8.4f}  "
                f"{row['prob_frozen_mu_t']:>8.4f}  {row['prob_rolling_mu_t']:>8.4f}  "
                f"{flag_str}"
            )
        print("=" * W)

    # ------------------------------------------------------------------
    # Section 3: Per-trade summary
    # ------------------------------------------------------------------
    print()
    print("=" * W)
    print("SECTION 3: PER-TRADE PARAMETER DRIFT SUMMARY")
    print(f"  Reference bar: cross-back bar for losers, min-dist bar for winners.")
    print(f"  Lead-time test: is the first bar where prob_frozen_mu < {PROB_GATE} BEFORE"
          f" the reference bar?")
    print("=" * W)

    summaries = []

    for res in all_results:
        t     = res["trade"]
        num   = t["trade_num"]
        rows  = res["rows"]
        min_i = res["min_dist_idx"]
        cb_i  = res["cb_idx"]
        is_loser = (t["exit_reason"] == "time_stop")
        ref_i = cb_i if (is_loser and cb_i is not None) else min_i

        # beta/theta at entry and at reference bar
        entry_row = rows[0]
        ref_row   = rows[ref_i] if (ref_i < len(rows) and not rows[ref_i].get("fit_failed")) else None

        beta_entry  = entry_row["beta_t"]
        theta_entry = entry_row["theta_t"]

        if ref_row:
            beta_ref      = ref_row["beta_t"]
            theta_ref     = ref_row["theta_t"]
            beta_drift    = (beta_ref  - beta_entry)  / abs(beta_entry)  * 100.0
            theta_drift   = (theta_ref - theta_entry) / abs(theta_entry) * 100.0
        else:
            beta_ref   = theta_ref   = float("nan")
            beta_drift = theta_drift = float("nan")

        # Gap series at key bars
        def _gap(row):
            if row is None or row.get("fit_failed"):
                return float("nan"), float("nan")
            return (row["prob_frozen_mu_t"] - row["prob_rolling_mu_t"],
                    row["dist_frozen_t"]    - row["dist_rolling_t"])

        prob_gap_entry, dist_gap_entry = _gap(rows[0])
        prob_gap_min,   dist_gap_min   = _gap(rows[min_i] if min_i < len(rows) else None)
        prob_gap_ref,   dist_gap_ref   = _gap(ref_row)

        # First bar where prob_frozen_mu < PROB_GATE
        first_below_gate = None
        for row in rows:
            if row is None or row.get("fit_failed"):
                continue
            if row["prob_frozen_mu_t"] < PROB_GATE:
                first_below_gate = row["bar"]
                break

        if first_below_gate is not None and ref_i is not None:
            lead_bars = ref_i - first_below_gate
            leads = (lead_bars > 0)
        else:
            lead_bars = None
            leads     = None

        summaries.append({
            "num":              num,
            "exit_reason":      t["exit_reason"],
            "is_loser":         is_loser,
            "ref_label":        "cross-back" if (is_loser and cb_i is not None) else "min-dist",
            "ref_i":            ref_i,
            "cb_i":             cb_i,
            "min_i":            min_i,
            "beta_entry":       beta_entry,
            "beta_ref":         beta_ref,
            "beta_drift":       beta_drift,
            "theta_entry":      theta_entry,
            "theta_ref":        theta_ref,
            "theta_drift":      theta_drift,
            "first_below_gate": first_below_gate,
            "lead_bars":        lead_bars,
            "leads":            leads,
            "prob_gap_entry":   prob_gap_entry,
            "prob_gap_min":     prob_gap_min,
            "prob_gap_ref":     prob_gap_ref,
            "dist_gap_entry":   dist_gap_entry,
            "dist_gap_min":     dist_gap_min,
            "dist_gap_ref":     dist_gap_ref,
        })

        ref_label = "cross-back" if (is_loser and cb_i is not None) else "min-dist"
        print()
        print(f"Trade {num} ({t['exit_reason']})")
        print(f"  beta  : entry={beta_entry:.6f}  @{ref_label}({ref_i})={beta_ref:.6f}"
              f"  drift={beta_drift:+.2f}%")
        print(f"  theta : entry={theta_entry:.6f}  @{ref_label}({ref_i})={theta_ref:.6f}"
              f"  drift={theta_drift:+.2f}%")
        print(f"  prob_frozen_mu first below {PROB_GATE}: bar {_fmt_bar(first_below_gate, len(rows))}")
        if lead_bars is not None:
            sign = "LEADS" if leads else "LAGS/TIES"
            print(f"  vs {ref_label} bar {ref_i}: lead_bars={lead_bars}  → {sign}")
        else:
            print(f"  prob never crossed below {PROB_GATE} during hold  (or ref bar N/A)")
        print(f"  prob_gap (frz-rol) at entry={prob_gap_entry:+.4f}  min-dist={prob_gap_min:+.4f}"
              f"  ref={prob_gap_ref:+.4f}")
        print(f"  dist_gap (frz-rol) at entry={dist_gap_entry:+.4f}  min-dist={dist_gap_min:+.4f}"
              f"  ref={dist_gap_ref:+.4f}")

    # ------------------------------------------------------------------
    # Section 4: Cross-trade comparison
    # ------------------------------------------------------------------
    print()
    print("=" * W)
    print("SECTION 4: CROSS-TRADE COMPARISON")
    print("=" * W)

    losers  = [s for s in summaries if s["is_loser"]]
    winners = [s for s in summaries if not s["is_loser"]]

    # Tabular summary
    hdr = (f"{'Tr':>2}  {'outcome':<12}  {'ref_bar':<8}  "
           f"{'beta_drift%':>11}  {'theta_drift%':>12}  "
           f"{'1st<0.67':>8}  {'ref_bar':>7}  {'lead_bars':>9}  {'leads?':>6}")
    print(hdr)
    print("-" * W)

    def _row(s):
        fb  = _fmt_bar(s["first_below_gate"], 0)
        ref = _fmt_bar(s["ref_i"], 0)
        lb  = str(s["lead_bars"]) if s["lead_bars"] is not None else "N/A"
        ld  = ("YES" if s["leads"] else "NO") if s["leads"] is not None else "N/A"
        print(
            f"{s['num']:>2}  {s['exit_reason']:<12}  {s['ref_label']:<8}  "
            f"{s['beta_drift']:>+11.2f}  {s['theta_drift']:>+12.2f}  "
            f"{fb:>8}  {ref:>7}  {lb:>9}  {ld:>6}"
        )

    print("-- Losers --")
    for s in losers:
        _row(s)
    print("-- Winners (control) --")
    for s in winners:
        _row(s)

    print()

    # --- explicit paragraph ---
    def _safe(v, fmt=".2f"):
        return "N/A" if (v is None or not math.isfinite(v)) else format(v, fmt)

    loser_beta_drifts  = [s["beta_drift"]  for s in losers  if math.isfinite(s["beta_drift"])]
    winner_beta_drifts = [s["beta_drift"]  for s in winners if math.isfinite(s["beta_drift"])]
    loser_theta_drifts = [s["theta_drift"] for s in losers  if math.isfinite(s["theta_drift"])]
    winner_theta_drifts= [s["theta_drift"] for s in winners if math.isfinite(s["theta_drift"])]
    loser_leads        = [s["lead_bars"]   for s in losers  if s["lead_bars"] is not None]
    winner_leads       = [s["lead_bars"]   for s in winners if s["lead_bars"] is not None]

    loser_beta_range  = (f"[{min(loser_beta_drifts):+.2f}%, {max(loser_beta_drifts):+.2f}%]"
                         if loser_beta_drifts else "N/A")
    winner_beta_range = (f"[{min(winner_beta_drifts):+.2f}%, {max(winner_beta_drifts):+.2f}%]"
                         if winner_beta_drifts else "N/A")
    loser_theta_range  = (f"[{min(loser_theta_drifts):+.2f}%, {max(loser_theta_drifts):+.2f}%]"
                          if loser_theta_drifts else "N/A")
    winner_theta_range = (f"[{min(winner_theta_drifts):+.2f}%, {max(winner_theta_drifts):+.2f}%]"
                          if winner_theta_drifts else "N/A")

    loser_leads_led  = [lb for lb in loser_leads  if lb > 0]
    winner_leads_led = [lb for lb in winner_leads if lb > 0]

    # Overlap test
    def _overlaps(a_list, b_list):
        if not a_list or not b_list:
            return None
        return not (max(a_list) < min(b_list) or max(b_list) < min(a_list))

    beta_overlap  = _overlaps(loser_beta_drifts,  winner_beta_drifts)
    theta_overlap = _overlaps(loser_theta_drifts, winner_theta_drifts)
    lead_overlap  = _overlaps(loser_leads, winner_leads)

    # Lead time: does prob_frozen_mu<0.67 lead cross-back for ALL losers?
    all_losers_led = (len(loser_leads_led) == len(losers) and len(losers) > 0)
    any_winner_led = len(winner_leads_led) > 0

    if all_losers_led and not any_winner_led:
        verdict = "YES — prob_frozen_mu drops below 0.67 before the cross-back bar for all losers, and does NOT do so before the min-dist bar for any winner."
    elif all_losers_led and any_winner_led:
        verdict = "INCONCLUSIVE — prob_frozen_mu leads the cross-back for all losers but also leads the min-dist bar for at least one winner; the signal does not separate the two groups."
    elif not loser_leads_led:
        verdict = "NO — prob_frozen_mu does not lead the cross-back bar for any loser (signal arrives too late or never)."
    else:
        verdict = "INCONCLUSIVE — prob_frozen_mu leads the cross-back for some but not all losers."

    print("FINDING:")
    print(f"  Beta drift (entry→ref): losers={loser_beta_range}  winners={winner_beta_range}")
    print(f"    Ranges {'OVERLAP' if beta_overlap else 'DO NOT OVERLAP' if beta_overlap is not None else '(insufficient data)'}.")
    print(f"  Theta drift (entry→ref): losers={loser_theta_range}  winners={winner_theta_range}")
    print(f"    Ranges {'OVERLAP' if theta_overlap else 'DO NOT OVERLAP' if theta_overlap is not None else '(insufficient data)'}.")
    print(f"  Lead time (prob_frozen_mu<{PROB_GATE} vs reference bar):")
    print(f"    Losers  (cross-back ref): {loser_leads}  "
          f"({len(loser_leads_led)}/{len(losers)} led the cross-back)")
    print(f"    Winners (min-dist ref):   {winner_leads}  "
          f"({len(winner_leads_led)}/{len(winners)} led the min-dist bar)")
    print(f"    Lead ranges {'OVERLAP' if lead_overlap else 'DO NOT OVERLAP' if lead_overlap is not None else '(insufficient data)'}.")
    print()
    print(f"  VERDICT: {verdict}")
    print()
    print("  n=6 (3 losers / 3 winners), one 30-day window, one pair (AVAX/LINK).")
    print("  Directional only. Insufficient to justify a new exit rule on its own.")

    # ------------------------------------------------------------------
    # Section 5: Mandatory caveats
    # ------------------------------------------------------------------
    print()
    print("=" * W)
    print("SECTION 5: CAVEATS")
    print("=" * W)
    print()
    print("CAVEAT: Rolling theta and rolling reversion-probability partly re-encode the")
    print("        price path. A 360-bar trailing window that covers a diverged spread")
    print("        will show weaker mean-reversion BECAUSE the spread diverged. These")
    print("        metrics are only meaningful as early-exit signals if they LEAD the")
    print("        cross-back bar. A parameter shift that appears only at or after the")
    print("        cross-back is the price path re-encoded into the parameter estimate —")
    print("        not a structural signal, and too late to act on (you would exit at the")
    print("        bottom, no better than the time stop).")
    print()
    print("        n=6, one 30-day window, one pair. Directional only. Insufficient to")
    print("        justify a new exit rule on its own.")
    print("=" * W)


if __name__ == "__main__":
    main()
