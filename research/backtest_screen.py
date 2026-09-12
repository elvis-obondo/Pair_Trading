"""Pre-compute the z-screen for a whole backtest window, once per pair.

WHY THIS EXISTS

scanner.scan() is the live path: at one bar, screen every pair. A backtest calls
it once per bar, and that recomputes each pair's entire 671-bar rolling history
from scratch every time. Over a 6-month window that is the same work repeated
8,640 times -- measured at 20.4 hours, against 30 seconds for one pass per pair.

So the backtest screens in bulk and the live scanner screens per bar. They must
agree exactly, and they do for a reason that is checked rather than assumed:
rolling_spread_stats never looks forward (validate_rolling_spread asserts that
truncating the future leaves earlier bars unchanged), so a statistic computed
in one full pass equals the one computed from the trailing window at that bar.
validate_backtest_screen.py asserts the equality directly against
generate_entry_signal.

WHAT IS NOT PRE-COMPUTED

theta. It costs ~1.4ms per fit and is only needed for candidates that are
actually ranked for a free slot -- a minority of bars once the book fills. It is
fitted lazily during the walk, by the same code path and with the same frozen
beta/alpha the live scanner uses.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gc
import time

import numpy as np
import pandas as pd

from ou_model import fit_ou_ewma
from rolling_spread import rolling_spread_stats, entry_window_bars, min_bars_required

SCREEN_COLUMNS = ["bar", "ticker_a", "ticker_b", "entry_spread", "mu_at_entry",
                  "sigma_at_entry", "z_at_entry", "beta_at_entry", "alpha_at_entry"]


def build_screen(panel: pd.DataFrame, pairs, first_eval_bar: int,
                 min_deviation_sigma: float = 3.0, bar_hours: float = 0.5,
                 progress_every: int = 4000) -> pd.DataFrame:
    """Every (bar, pair) at or beyond the entry threshold, for the whole window.

    Returns one row per candidate OPPORTUNITY -- the same pair appears once for
    every bar it stays dislocated, because each of those bars is a moment the
    strategy could have entered.

    Rows are float32 where it is safe: at 4M rows the frame is the memory
    constraint, and the geometry is carried at full precision only where the
    exit arithmetic reads it back.
    """
    arrays = {t: panel[t].to_numpy(dtype=float) for t in panel.columns}
    out = []
    t0 = time.time()
    for k, (a, b) in enumerate(pairs, 1):
        pa, pb = arrays.get(a), arrays.get(b)
        if pa is None or pb is None:
            continue
        r = rolling_spread_stats(pa, pb, bar_hours)
        z = r.z
        hit = np.flatnonzero(np.isfinite(z[first_eval_bar:])
                             & (np.abs(z[first_eval_bar:]) >= min_deviation_sigma))
        if not len(hit):
            continue
        idx = hit + first_eval_bar
        out.append(pd.DataFrame({
            "bar": idx.astype(np.int32),
            "ticker_a": a, "ticker_b": b,
            "entry_spread": r.spread[idx], "mu_at_entry": r.mu[idx],
            "sigma_at_entry": r.sigma[idx], "z_at_entry": r.z[idx],
            "beta_at_entry": r.beta[idx], "alpha_at_entry": r.alpha[idx],
        }))
        if progress_every and k % progress_every == 0:
            el = time.time() - t0
            rows = sum(len(d) for d in out)
            print(f"  screened {k:,}/{len(pairs):,} pairs  {rows:,} candidate rows  "
                  f"{el:.0f}s eta {el/k*(len(pairs)-k):.0f}s", flush=True)

    if not out:
        return pd.DataFrame(columns=SCREEN_COLUMNS)
    d = pd.concat(out, ignore_index=True)
    del out
    gc.collect()
    d["ticker_a"] = d["ticker_a"].astype("category")
    d["ticker_b"] = d["ticker_b"].astype("category")
    return d.sort_values("bar", kind="stable").reset_index(drop=True)


def theta_at(arrays: dict, a: str, b: str, bar: int, beta: float, alpha: float,
             bar_hours: float = 0.5) -> float:
    """theta for one candidate, identical to generate_entry_signal's Step 3.

    Same window, same frozen beta/alpha, same fit_df=False. A failed fit returns
    NaN and does NOT decline the candidate -- theta ranks, it does not gate.
    """
    w = entry_window_bars(bar_hours)
    lo = bar - w + 1
    if lo < 0:
        return float("nan")
    wa, wb = arrays[a][lo:bar + 1], arrays[b][lo:bar + 1]
    try:
        p = fit_ou_ewma(wa, wb, bar_hours=bar_hours,
                        spread=wa - beta * wb - alpha, fit_df=False)
    except (ValueError, np.linalg.LinAlgError):
        return float("nan")
    return float(p.theta) if np.isfinite(p.theta) and p.theta > 0 else float("nan")


def rank_bar(rows: pd.DataFrame, arrays: dict, take_profit_pct: float = 1.0,
             bar_hours: float = 0.5) -> pd.DataFrame:
    """Fit theta for one bar's candidates and rank them, NaN last.

    Mirrors scanner.scan()'s output contract so Portfolio.fill_slots cannot tell
    the two apart.
    """
    if not len(rows):
        return rows
    d = rows.copy()
    d["theta_at_entry"] = [
        theta_at(arrays, r.ticker_a, r.ticker_b, int(r.bar),
                 r.beta_at_entry, r.alpha_at_entry, bar_hours)
        for r in d.itertuples(index=False)]
    d["take_profit_level"] = (d.entry_spread
                              - take_profit_pct * (d.entry_spread - d.mu_at_entry))
    return d.sort_values("theta_at_entry", ascending=False,
                         na_position="last").reset_index(drop=True)
