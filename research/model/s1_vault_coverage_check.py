"""HL-VAULT1 step 1 (brief docs/prompts/HL_VAULT1_RUN.md): coverage check on the vault window, with NO
vault labels or outcomes read -- only vault_loader.load_vault_event_dates() (events.parquet, geometry and
dates only) and the existing s1_profit1.py cache helpers for build2 1m prices, ctxs (funding/impact) and
fundinghist. Sizes every day of the vault window for:
  1. v1 pair events (count only -- from events.parquet, no label_gap/outcome/net/gross).
  2. build2 d3/asm 1m price coverage (fraction of that day's 1,440 minutes with a finite, non-gap close)
     for every coin involved in a vault event.
  3. ctxs (funding + impact spread source) day availability.
  4. fundinghist coin availability.
Nothing is filled or imputed. Gaps are printed and reported to the planner before step 2 runs.

    python -u research/model/s1_vault_coverage_check.py > research/model/logs/s1/s1_vault_coverage_check.log
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
sys.path.insert(0, os.path.join(ROOT, "research"))
import vault_loader as VL  # noqa: E402
import s1_profit1 as S1P  # noqa: E402 -- reuses the already-reviewed cache helpers, not reimplemented


def log(msg):
    print(msg, flush=True)


def day_strs(d0, d1):
    return pd.date_range(d0, d1, freq="D").strftime("%Y%m%d").tolist()


def per_day_event_counts(vault_ev, days):
    vault_ev = vault_ev.copy()
    vault_ev["day"] = vault_ev["t0"].dt.strftime("%Y%m%d")
    counts = vault_ev.groupby("day").size()
    return {d: int(counts.get(d, 0)) for d in days}


def per_day_build2_coverage(dense_price, days):
    """Per coin, per day: fraction of that day's 1,440 minutes with a finite, non-true-gap close.
    Day entirely outside the coin's own [lo, lo+n) range counts as covered=0/total=1440 (no data, not
    silently skipped)."""
    out = {}
    for coin, d in dense_price.items():
        lo, gap = d["lo"], d["gap"]
        n = len(gap)
        rows = {}
        for day in days:
            day_ts = np.datetime64(pd.Timestamp(day, tz=None), "m")
            off = int((day_ts - lo) / np.timedelta64(1, "m"))
            lo_i, hi_i = max(off, 0), min(off + 1440, n)
            if hi_i > lo_i:
                covered = int((~gap[lo_i:hi_i]).sum())
            else:
                covered = 0
            rows[day] = covered  # out of 1440
        out[coin] = rows
    return out


def main():
    t0 = pd.Timestamp.now()
    log(f"[VAULTCOV] start {t0.isoformat()}")

    # 1. v1 pair events, count only (no labels/outcomes).
    vault_ev = VL.load_vault_event_dates()
    d0, d1 = vault_ev["t0"].min().normalize(), vault_ev["t0"].max().normalize()
    days = day_strs(d0, d1)
    log(f"[VAULTCOV] vault window: {d0.date()} to {d1.date()} ({len(days)} days), "
        f"{len(vault_ev):,} pair events total")

    coins = sorted(set(vault_ev["ticker_a"]) | set(vault_ev["ticker_b"]))
    log(f"[VAULTCOV] {len(coins)} distinct coins across all vault events")

    event_counts = per_day_event_counts(vault_ev, days)
    log("[VAULTCOV] per-day v1 pair event counts:")
    for day in days:
        log(f"[VAULTCOV]   {day}: {event_counts[day]:,} events")
    zero_event_days = [d for d in days if event_counts[d] == 0]
    if zero_event_days:
        log(f"[VAULTCOV] GAP: {len(zero_event_days)} day(s) with 0 pair events: {zero_event_days}")

    # 2. ctxs (funding + impact spread source), day availability.
    failed_ctxs_days = S1P.ensure_ctxs_cached(days)
    log(f"[VAULTCOV] ctxs: {len(days) - len(failed_ctxs_days)}/{len(days)} days available, "
        f"{len(failed_ctxs_days)} failed/missing: {failed_ctxs_days}")

    # 3. fundinghist, coin availability.
    no_fund_coins = S1P.ensure_fundinghist_cached(coins)
    log(f"[VAULTCOV] fundinghist: {len(coins) - len(no_fund_coins)}/{len(coins)} coins available, "
        f"{len(no_fund_coins)} missing: {no_fund_coins}")

    # 4. build2 d3/asm 1m prices, per coin per day.
    no_build2_coins = S1P.ensure_build2_1m_cached(coins)
    log(f"[VAULTCOV] build2 1m: {len(coins) - len(no_build2_coins)}/{len(coins)} coins available, "
        f"{len(no_build2_coins)} missing: {no_build2_coins}")

    have_build2 = [c for c in coins if c not in no_build2_coins]
    dense_price, _ = S1P.build_dense_price(have_build2)
    day_cov = per_day_build2_coverage(dense_price, days)

    log("[VAULTCOV] per-day build2 1m price coverage (minutes covered / 1,440, summed over coins "
        "with data; pct = covered / (coins_with_data * 1,440)):")
    gap_days = []
    for day in days:
        covered = sum(day_cov[c][day] for c in have_build2)
        total = len(have_build2) * 1440
        pct = covered / total if total else 0.0
        log(f"[VAULTCOV]   {day}: {covered:,}/{total:,} = {pct:.4f}")
        if pct < 1.0:
            gap_days.append((day, pct))

    log(f"[VAULTCOV] GAP: {len(gap_days)}/{len(days)} days have build2 coverage < 1.0 "
        f"(worst 10 shown): {sorted(gap_days, key=lambda x: x[1])[:10]}")

    log(f"[VAULTCOV] SUMMARY -- gaps to report to the planner before step 2:")
    log(f"[VAULTCOV]   zero-event days: {len(zero_event_days)}")
    log(f"[VAULTCOV]   ctxs missing days: {len(failed_ctxs_days)}")
    log(f"[VAULTCOV]   fundinghist missing coins: {len(no_fund_coins)}")
    log(f"[VAULTCOV]   build2 missing coins entirely: {len(no_build2_coins)}")
    log(f"[VAULTCOV]   days with build2 coverage < 1.0: {len(gap_days)}/{len(days)}")
    log(f"[VAULTCOV] done  [{(pd.Timestamp.now()-t0).total_seconds():.0f}s]")


if __name__ == "__main__":
    main()
