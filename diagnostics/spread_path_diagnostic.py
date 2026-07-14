"""
Diagnostic: Per-bar spread-path reconstruction for the six AVAX/LINK backtest trades.

Reconstructs the intra-trade spread at every hourly bar using frozen entry-time
coefficients (beta, alpha, mu, sigma, theta from the trade log). Classifies each
trade as monotone-divergence, toward-then-reversed, or clean-revert.

Read-only. Writes no files.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import math
import numpy as np
import pandas as pd

from research.data_loader import get_price_levels

TAKE_PROFIT_PCT = 0.80   # default in signal_generator.generate_entry_signal
STOP_SIGMA      = 2.5
MONO_TOLERANCE  = 0.10   # σ drop below entry abs-dist required to be non-monotone


def load_trade_log(log_path: str) -> list[dict]:
    with open(log_path) as fh:
        return json.load(fh)


def main() -> None:
    # ------------------------------------------------------------------
    # Load price data
    # ------------------------------------------------------------------
    df = get_price_levels()
    print(f"[INFO] Price data columns : {list(df.columns)}")
    print(f"[INFO] Index range        : {df.index[0]} -> {df.index[-1]}")
    print(f"[INFO] Total bars         : {len(df)}")
    print()

    assert "AVAX" in df.columns, "AVAX column not found in get_price_levels() output"
    assert "LINK" in df.columns, "LINK column not found in get_price_levels() output"

    # ------------------------------------------------------------------
    # Load trade log
    # ------------------------------------------------------------------
    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "research", "trade_log_dump.json",
    )
    trade_log = load_trade_log(log_path)

    # ------------------------------------------------------------------
    # Compute phase — iterate all trades, accumulate results
    # ------------------------------------------------------------------
    results = []
    fidelity_failed = False
    adverse_breached = False

    for t in trade_log:
        num            = t["trade_num"]
        entry_spread   = t["entry_spread"]
        exit_spread    = t["exit_spread"]
        mu             = t["mu_at_entry"]
        beta           = t["beta_at_entry"]
        alpha          = t["alpha_at_entry"]
        sigma          = t["sigma_at_entry"]
        theta          = t["theta_at_entry"]
        hours_held          = t["hours_held"]
        exit_reason         = t["exit_reason"]
        deviation_sigma_log = t["deviation_sigma"]
        reversion_prob      = t["reversion_probability"]

        sigma_stationary  = sigma / math.sqrt(2.0 * theta)
        take_profit_level = entry_spread - TAKE_PROFIT_PCT * (entry_spread - mu)
        entry_above_mu    = (entry_spread > mu)

        # --- bar selection ---
        entry_ts = pd.Timestamp(t["entry_time"])
        exit_ts  = pd.Timestamp(t["exit_time"])
        bars = df.loc[
            (df.index >= entry_ts) & (df.index <= exit_ts),
            ["AVAX", "LINK"],
        ].dropna()

        n_bars = len(bars)

        # --- spread reconstruction ---
        spread_t = bars["AVAX"].values - alpha - beta * bars["LINK"].values

        # --- acceptance criterion 1: reconstruction fidelity ---
        entry_diff = abs(spread_t[0]  - entry_spread)
        exit_diff  = abs(spread_t[-1] - exit_spread)
        fidelity_ok = (entry_diff < 1e-6 and exit_diff < 1e-6)
        if not fidelity_ok:
            print(f"[FAIL] Trade {num} reconstruction fidelity:")
            print(f"  entry: logged={entry_spread:.10f}  recon={spread_t[0]:.10f}"
                  f"  diff={entry_diff:.2e}")
            print(f"  exit:  logged={exit_spread:.10f}  recon={spread_t[-1]:.10f}"
                  f"  diff={exit_diff:.2e}")
            fidelity_failed = True
            results.append(None)
            continue

        # --- acceptance criterion 2: bar count ---
        expected_bars = int(hours_held) + 1
        bar_count_ok  = (n_bars == expected_bars)

        # --- per-bar metrics ---
        signed_dist_sigma_t = (spread_t - mu) / sigma_stationary
        abs_dist_sigma_t    = np.abs(signed_dist_sigma_t)

        if entry_above_mu:
            adverse_t = (spread_t - entry_spread) / sigma_stationary
        else:
            adverse_t = (entry_spread - spread_t) / sigma_stationary

        # --- acceptance criterion 3: adverse stop consistency ---
        max_adverse     = float(np.max(adverse_t))
        max_adverse_idx = int(np.argmax(adverse_t))
        max_adverse_ts  = bars.index[max_adverse_idx]
        if max_adverse >= STOP_SIGMA:
            print(f"[FAIL] Trade {num}: max adverse = {max_adverse:.4f}σ >= {STOP_SIGMA}σ")
            adverse_breached = True

        # --- summary statistics ---
        entry_abs_dist_sigma = abs(entry_spread - mu) / sigma_stationary
        exit_abs_dist_sigma  = abs(exit_spread  - mu) / sigma_stationary
        min_abs_dist_sigma   = float(np.min(abs_dist_sigma_t))
        min_abs_dist_idx     = int(np.argmin(abs_dist_sigma_t))
        min_abs_dist_ts      = bars.index[min_abs_dist_idx]
        toward_mu_drop       = entry_abs_dist_sigma - min_abs_dist_sigma

        if entry_above_mu:
            touched_tp = bool(np.any(spread_t <= take_profit_level))
        else:
            touched_tp = bool(np.any(spread_t >= take_profit_level))

        # first bar index where tp is touched (for flag in per-bar table)
        if touched_tp:
            if entry_above_mu:
                tp_touch_idx = int(np.argmax(spread_t <= take_profit_level))
            else:
                tp_touch_idx = int(np.argmax(spread_t >= take_profit_level))
        else:
            tp_touch_idx = None

        # --- classification ---
        if toward_mu_drop <= MONO_TOLERANCE:
            classification = "monotone-divergence"
        elif touched_tp and exit_reason == "take_profit":
            classification = "clean-revert"
        else:
            classification = "toward-then-reversed"

        results.append({
            "trade"              : t,
            "bars"               : bars,
            "spread_t"           : spread_t,
            "signed_dist_sigma_t": signed_dist_sigma_t,
            "abs_dist_sigma_t"   : abs_dist_sigma_t,
            "adverse_t"          : adverse_t,
            "sigma_stationary"   : sigma_stationary,
            "take_profit_level"  : take_profit_level,
            "entry_above_mu"     : entry_above_mu,
            "n_bars"             : n_bars,
            "expected_bars"      : expected_bars,
            "bar_count_ok"       : bar_count_ok,
            "fidelity_ok"        : fidelity_ok,
            "entry_diff"         : entry_diff,
            "exit_diff"          : exit_diff,
            "entry_abs_dist_sigma": entry_abs_dist_sigma,
            "exit_abs_dist_sigma" : exit_abs_dist_sigma,
            "min_abs_dist_sigma"  : min_abs_dist_sigma,
            "min_abs_dist_idx"    : min_abs_dist_idx,
            "min_abs_dist_ts"     : min_abs_dist_ts,
            "max_adverse"         : max_adverse,
            "max_adverse_idx"     : max_adverse_idx,
            "max_adverse_ts"      : max_adverse_ts,
            "toward_mu_drop"      : toward_mu_drop,
            "touched_tp"          : touched_tp,
            "tp_touch_idx"        : tp_touch_idx,
            "classification"      : classification,
            "deviation_sigma_log" : deviation_sigma_log,
            "reversion_prob"      : reversion_prob,
        })

    # ------------------------------------------------------------------
    # Hard stop on failures
    # ------------------------------------------------------------------
    if fidelity_failed:
        print("\n[STOP] Reconstruction fidelity failed on one or more trades. Halting.")
        return
    if adverse_breached:
        print("\n[STOP] Adverse stop breached on one or more trades. Halting.")
        return

    # ------------------------------------------------------------------
    # Section 1: Acceptance criteria
    # ------------------------------------------------------------------
    W = 130
    print("=" * W)
    print("ACCEPTANCE CRITERIA")
    print("=" * W)

    # --- Criterion 1: Fidelity ---
    print("\nCriterion 1 — Reconstruction fidelity (entry and exit bar, tol=1e-6):")
    all_fid_ok = True
    for r in results:
        num = r["trade"]["trade_num"]
        ok  = r["fidelity_ok"]
        all_fid_ok = all_fid_ok and ok
        tag = "PASS" if ok else "FAIL"
        print(f"  Trade {num}: {tag}  "
              f"entry_diff={r['entry_diff']:.2e}  exit_diff={r['exit_diff']:.2e}")
    print(f"  Overall: {'PASS' if all_fid_ok else 'FAIL'}")

    # --- Criterion 2: Bar counts ---
    print("\nCriterion 2 — Bar count (expected = hours_held + 1):")
    all_bar_ok = True
    for r in results:
        num = r["trade"]["trade_num"]
        ok  = r["bar_count_ok"]
        all_bar_ok = all_bar_ok and ok
        tag = "PASS" if ok else "FAIL"
        print(f"  Trade {num}: {tag}  expected={r['expected_bars']}  actual={r['n_bars']}")
    print(f"  Overall: {'PASS' if all_bar_ok else 'FAIL'}")

    # --- Criterion 3: Adverse consistency ---
    print("\nCriterion 3 — Adverse stop consistency (no bar >= 2.5σ from entry):")
    all_adv_ok = True
    for r in results:
        num = r["trade"]["trade_num"]
        ok  = (r["max_adverse"] < STOP_SIGMA)
        all_adv_ok = all_adv_ok and ok
        tag = "PASS" if ok else "FAIL"
        print(f"  Trade {num}: {tag}  max_adverse={r['max_adverse']:.4f}σ "
              f"@ bar {r['max_adverse_idx']} ({r['max_adverse_ts']})")
    print(f"  Overall: {'PASS' if all_adv_ok else 'FAIL'}")

    # ------------------------------------------------------------------
    # Section 2: 6-trade summary table
    # ------------------------------------------------------------------
    print()
    print("=" * W)
    print("TRADE SUMMARY")
    print("=" * W)
    hdr = (
        f"{'#':>2}  {'reason':<12}  {'entry_σ':>7}  {'exit_σ':>6}  "
        f"{'min_σ':>5}  {'min@bar':>5}  {'min@ts':<16}  "
        f"{'tp?':>3}  {'max_adv_σ':>9}  {'adv@bar':>7}  {'adv@ts':<16}  "
        f"{'adv≥2.5?':>8}  classification"
    )
    print(hdr)
    print("-" * W)
    for r in results:
        t   = r["trade"]
        num = t["trade_num"]
        print(
            f"{num:>2}  {t['exit_reason']:<12}  "
            f"{r['entry_abs_dist_sigma']:>7.4f}  {r['exit_abs_dist_sigma']:>6.4f}  "
            f"{r['min_abs_dist_sigma']:>5.4f}  {r['min_abs_dist_idx']:>5d}  "
            f"{str(r['min_abs_dist_ts']):<16}  "
            f"{'YES' if r['touched_tp'] else 'NO':>3}  "
            f"{r['max_adverse']:>9.4f}  {r['max_adverse_idx']:>7d}  "
            f"{str(r['max_adverse_ts']):<16}  "
            f"{'NO':>8}  {r['classification']}"
        )
    print("=" * W)

    # ------------------------------------------------------------------
    # Section 3: Full per-bar tables (all 6 trades)
    # ------------------------------------------------------------------
    for r in results:
        t                 = r["trade"]
        num               = t["trade_num"]
        bars              = r["bars"]
        spread_t          = r["spread_t"]
        signed_dist       = r["signed_dist_sigma_t"]
        adverse_t         = r["adverse_t"]
        sigma_stat        = r["sigma_stationary"]
        tp_level          = r["take_profit_level"]
        min_idx           = r["min_abs_dist_idx"]
        max_adv_idx       = r["max_adverse_idx"]
        tp_touch_idx      = r["tp_touch_idx"]

        print()
        print("=" * W)
        print(
            f"Trade {num}  ({t['exit_reason']})  "
            f"σ_stat={sigma_stat:.8f}  "
            f"tp_level={tp_level:.8f}  "
            f"entry_spread={t['entry_spread']:.8f}  "
            f"mu={t['mu_at_entry']:.8f}"
        )
        print("-" * W)
        col_hdr = (
            f"{'bar':>4}  {'timestamp':<16}  {'spread_t':>12}  "
            f"{'dist_mu_σ(signed)':>18}  {'adverse_σ':>10}  flags"
        )
        print(col_hdr)
        print("-" * W)
        for i, (ts, sp, sd, adv) in enumerate(
            zip(bars.index, spread_t, signed_dist, adverse_t)
        ):
            flags = []
            if i == 0:
                flags.append("[ENTRY]")
            if i == len(bars) - 1:
                flags.append("[EXIT]")
            if i == min_idx:
                flags.append("[MIN_MU]")
            if i == max_adv_idx:
                flags.append("[MAX_ADV]")
            if tp_touch_idx is not None and i == tp_touch_idx:
                flags.append("[TP_TOUCH]")
            flag_str = "  ".join(flags)
            print(
                f"{i:>4}  {str(ts):<16}  {sp:>12.6f}  "
                f"{sd:>18.4f}  {adv:>10.4f}  {flag_str}"
            )
        print("=" * W)

    # ------------------------------------------------------------------
    # Section 4: Explicit classifications
    # ------------------------------------------------------------------
    print()
    print("=" * W)
    print("EXPLICIT CLASSIFICATIONS")
    print("=" * W)

    REASONS = {
        "monotone-divergence":  (
            "abs-dist-from-mu never dropped more than {tol}σ below entry "
            "(spread moved away from mu the whole hold)"
        ),
        "toward-then-reversed": (
            "abs-dist-from-mu dropped {drop:.2f}σ below entry value "
            "(moved meaningfully toward mu), then reversed before completing revert"
        ),
        "clean-revert":         (
            "abs-dist-from-mu dropped {drop:.2f}σ below entry, "
            "spread touched take-profit level, exited via take_profit"
        ),
    }

    for r in results:
        t   = r["trade"]
        num = t["trade_num"]
        cls = r["classification"]
        if cls == "monotone-divergence":
            reason_str = REASONS[cls].format(tol=MONO_TOLERANCE)
        else:
            reason_str = REASONS[cls].format(drop=r["toward_mu_drop"])

        print(f"\nTrade {num} ({t['exit_reason']}): {cls}")
        print(f"  entry_abs_dist={r['entry_abs_dist_sigma']:.4f}σ  "
              f"exit_abs_dist={r['exit_abs_dist_sigma']:.4f}σ  "
              f"min_abs_dist={r['min_abs_dist_sigma']:.4f}σ "
              f"(bar {r['min_abs_dist_idx']}, {r['min_abs_dist_ts']})  "
              f"toward_mu_drop={r['toward_mu_drop']:.4f}σ")
        print(f"  take_profit_level={r['take_profit_level']:.8f}  "
              f"touched: {'YES' if r['touched_tp'] else 'NO'}  "
              f"max_adverse={r['max_adverse']:.4f}σ")
        print(f"  → {reason_str}")

    # ------------------------------------------------------------------
    # Section 5: One-line overall comparison
    # ------------------------------------------------------------------
    losers  = [r for r in results if r["trade"]["exit_reason"] == "time_stop"]
    winners = [r for r in results if r["trade"]["exit_reason"] == "take_profit"]

    loser_classes  = [r["classification"] for r in losers]
    winner_classes = [r["classification"] for r in winners]

    loser_drops   = [r["toward_mu_drop"] for r in losers]
    winner_drops  = [r["toward_mu_drop"] for r in winners]
    loser_tp      = [r["touched_tp"]      for r in losers]

    print()
    print("=" * W)
    print("OVERALL COMPARISON")
    print("=" * W)
    print(
        f"Losers  (1,2,4): classifications={loser_classes}  "
        f"toward_mu_drops={[round(d,3) for d in loser_drops]}  "
        f"tp_touched={loser_tp}"
    )
    print(
        f"Winners (3,5,6): classifications={winner_classes}  "
        f"toward_mu_drops={[round(d,3) for d in winner_drops]}  "
        f"tp_touched={[r['touched_tp'] for r in winners]}"
    )
    print("=" * W)

    # ------------------------------------------------------------------
    # Section 6: Entry fingerprint — all six trades, winners vs. losers
    # ------------------------------------------------------------------
    print()
    print("=" * W)
    print("SECTION 6: ENTRY FINGERPRINT — ALL SIX TRADES")
    print("=" * W)
    print("Note: n=6 (3 losers / 3 winners), one 30-day window on one pair.")
    print("      Group statistics are directional only; with n=3 per group,")
    print("      apparent separations may be noise. Read ranges, not conclusions.")
    print()

    # Per-trade fingerprint table
    hdr = (f"{'Tr':>2}  {'Outcome':<13}  {'RevProb':>7}  {'DevSig':>6}  "
           f"{'HalfLife':>8}  {'MinDistMu':>9}  {'TpTch':>5}  "
           f"{'HrsToMin':>8}  {'HrsHeld':>7}")
    sep = "-" * len(hdr)
    print(hdr)
    print(sep)

    for r in results:
        t          = r["trade"]
        num        = t["trade_num"]
        outcome    = t["exit_reason"]
        rev_prob   = r["reversion_prob"]
        dev_sig    = r["deviation_sigma_log"]
        theta      = t["theta_at_entry"]
        half_life  = math.log(2) / theta
        min_dist   = r["min_abs_dist_sigma"]
        tp_touch   = "YES" if r["touched_tp"] else "NO"
        hrs_to_min = r["min_abs_dist_idx"]
        hrs_held   = t["hours_held"]
        print(
            f"{num:>2}  {outcome:<13}  {rev_prob:>7.4f}  {dev_sig:>6.3f}  "
            f"{half_life:>8.2f}h  {min_dist:>9.4f}  {tp_touch:>5}  "
            f"{hrs_to_min:>8}  {hrs_held:>7.1f}"
        )

    print()

    # Grouped summary
    losers  = [r for r in results if r["trade"]["exit_reason"] == "time_stop"]
    winners = [r for r in results if r["trade"]["exit_reason"] == "take_profit"]

    def _group_stats(group, key_fn):
        vals = [key_fn(r) for r in group]
        return min(vals), float(np.median(vals)), max(vals)

    metrics = [
        ("reversion_probability", lambda r: r["reversion_prob"]),
        ("deviation_sigma",       lambda r: r["deviation_sigma_log"]),
        ("half_life_hours",       lambda r: math.log(2) / r["trade"]["theta_at_entry"]),
        ("min_dist_from_mu_sig",  lambda r: r["min_abs_dist_sigma"]),
        ("hours_to_min",          lambda r: r["min_abs_dist_idx"]),
        ("hours_held",            lambda r: r["trade"]["hours_held"]),
    ]

    col_w = 26
    print(f"{'Metric':<22}  {'Losers (time_stop)':<{col_w}}  {'Winners (take_profit)':<{col_w}}")
    print(f"{'':22}  {'min / median / max':<{col_w}}  {'min / median / max':<{col_w}}")
    print("-" * (22 + 2 + col_w + 2 + col_w))
    for name, fn in metrics:
        lmin, lmed, lmax = _group_stats(losers,  fn)
        wmin, wmed, wmax = _group_stats(winners, fn)
        lstr = f"{lmin:.3f} / {lmed:.3f} / {lmax:.3f}"
        wstr = f"{wmin:.3f} / {wmed:.3f} / {wmax:.3f}"
        print(f"{name:<22}  {lstr:<{col_w}}  {wstr:<{col_w}}")

    print()
    print("Overlap analysis (loser range vs winner range — do the intervals intersect?):")
    for name, fn in metrics:
        lmin, _, lmax = _group_stats(losers,  fn)
        wmin, _, wmax = _group_stats(winners, fn)
        overlap = not (lmax < wmin or wmax < lmin)
        tag = "OVERLAP" if overlap else "non-overlapping"
        print(f"  {name:<22}: losers [{lmin:.3f}, {lmax:.3f}]  winners [{wmin:.3f}, {wmax:.3f}]  → {tag}")

    print()
    print("Caveat: This is one 30-day window on one pair. With n=3 per group,")
    print("        apparent separations may be noise. Values are directional only.")
    print("=" * W)


if __name__ == "__main__":
    main()
