"""Sweep every exit rule at once, and ask what earliness is worth under the winner.

Two things this answers that the single-configuration dataset could not:

  A. Is there ANY combination of (take-profit, stop, holding time) with
     positive expectancy? reversion_dataset.py measured exactly one rule set
     -- 80% of the gap, 2.5 sigma stop, 24h -- and found it loses 0.042 sigma
     per trade at every dislocation level. That is one point on a grid, and a
     losing point does not mean the grid is empty.

  B. Does entering EARLIER in a relationship's life actually pay? The whole
     point of spotting relationships sooner is to trade more of their life,
     but that premise has never been tested: it is possible that the early
     days of a relationship are the noisy ones and the money is in the middle.
     Every candidate trade is tagged with how many days the pair had already
     been continuously passing the gate, so expectancy can be read against
     relationship age under whichever exit rule wins.

HOW THE SWEEP AVOIDS RE-RUNNING PRICES PER COMBINATION:

Re-simulating 678k trades for each of ~200 rule combinations would be hours.
Instead each trade's forward path is reduced ONCE to first-passage times:
for every candidate take-profit level, the first bar that level is touched,
and likewise for every candidate stop level. Any (tp, stop, horizon) triple
is then decided by comparing three integers -- whichever barrier has the
smaller first-touch bar wins, and if neither lands inside the horizon it is a
timeout -- so the whole grid evaluates in seconds from stored integers.

Barrier ORDER is preserved by construction: comparing first-touch bars is
exactly "which was hit first", which is the thing a max-favourable /
max-adverse summary would have thrown away. A trade that spikes to the stop
on bar 2 and recovers by bar 40 is a loss here, as it is in life.

COSTS are charged, not ignored: ROUND_TRIP_COST_FRAC of notional is converted
into sigma units per row (a spread in log-price is already a return, so the
cost in sigma is cost / sigma) and subtracted from every trade, winners and
losers alike. A gross-positive rule that dies on costs is not a rule.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import itertools
import time
from pathlib import Path

import numpy as np
import pandas as pd

from data_loader import get_price_levels
from pair_analysis import _base_symbol, BARS_PER_DAY, RECENT_P_THRESHOLD
from reversion_dataset import (
    rolling_beta_alpha, ENTRY_WINDOW_BARS, MIN_ENTRY_SIGMA, PVALUES_PATH,
)

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = PROJECT_ROOT / "research" / "exit_sweep_paths.parquet"

# Longest holding period considered; the forward window must cover it.
MAX_HORIZON_HOURS = 72.0
MAX_HORIZON_BARS = int(MAX_HORIZON_HOURS * 60 / 30)

# Grids. take-profit as a fraction of the entry gap (0.8 = current live rule);
# stop in stationary sigma from entry (2.5 = current live rule).
TP_GRID = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
STOP_GRID = [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]
HORIZON_GRID_HOURS = [4, 8, 12, 24, 48, 72]

# Round-trip cost across both legs: taker fees plus slippage. Deliberately on
# the pessimistic side of the 0.2% used in the APE/DOGE note, because that
# figure ignored funding and assumed clean fills on a thin leg.
ROUND_TRIP_COST_FRAC = 0.0025

MIN_JOINT_BARS = ENTRY_WINDOW_BARS + MAX_HORIZON_BARS + BARS_PER_DAY


def _first_touch(mat: np.ndarray, level: float) -> np.ndarray:
    """First column index where mat >= level, per row; -1 if never.

    argmax on a boolean row returns 0 both for "touched at bar 0" and for
    "never touched", so the any() mask is required to tell those apart --
    without it every untouched trade would be recorded as an instant hit.
    """
    hit = mat >= level
    idx = hit.argmax(axis=1)
    return np.where(hit.any(axis=1), idx, -1)


def build_pair_paths(a: str, b: str, pair_df: pd.DataFrame) -> pd.DataFrame | None:
    """One row per candidate trade, reduced to first-passage integers."""
    pa = pair_df[a].to_numpy()
    pb = pair_df[b].to_numpy()
    idx = pair_df.index
    n = len(pa)
    if n < MIN_JOINT_BARS:
        return None

    beta, alpha = rolling_beta_alpha(pa, pb, ENTRY_WINDOW_BARS)
    spread_roll = pa - beta * pb - alpha
    s_roll = pd.Series(spread_roll)
    mu_roll = s_roll.rolling(ENTRY_WINDOW_BARS).mean().to_numpy()
    sg_roll = s_roll.rolling(ENTRY_WINDOW_BARS).std().to_numpy()

    day_end = pd.Series(np.arange(n), index=idx).groupby(idx.normalize()).last()
    ts, days = [], []
    for day, t in day_end.items():
        t = int(t)
        if t < ENTRY_WINDOW_BARS or t + MAX_HORIZON_BARS >= n:
            continue
        if not (np.isfinite(beta[t]) and np.isfinite(mu_roll[t]) and np.isfinite(sg_roll[t])):
            continue
        if sg_roll[t] <= 0:
            continue
        s0 = pa[t] - beta[t] * pb[t] - alpha[t]
        if abs((s0 - mu_roll[t]) / sg_roll[t]) < MIN_ENTRY_SIGMA:
            continue
        ts.append(t)
        days.append(day)
    if not ts:
        return None

    ts = np.array(ts)
    bt, at_ = beta[ts], alpha[ts]
    mu, sg = mu_roll[ts], sg_roll[ts]
    s0 = pa[ts] - bt * pb[ts] - at_
    gap = s0 - mu
    sign = np.sign(gap)

    # Forward matrix (n_trades, MAX_HORIZON_BARS) under frozen beta/alpha.
    offs = np.arange(1, MAX_HORIZON_BARS + 1)
    cols = ts[:, None] + offs[None, :]
    fwd = pa[cols] - bt[:, None] * pb[cols] - at_[:, None]

    # Favourable progress as a FRACTION of the entry gap (1.0 == reached mu),
    # and adverse excursion in sigma from entry. Both oriented so "larger is
    # further in that direction" regardless of which side of mu we entered.
    prog = (s0[:, None] - fwd) * sign[:, None] / np.abs(gap)[:, None]
    adv = (fwd - s0[:, None]) * sign[:, None] / sg[:, None]

    out = {
        "ticker_a": a, "ticker_b": b, "date": days,
        "z": (gap / sg), "sigma": sg, "mu": mu, "beta": bt,
    }
    for F in TP_GRID:
        out[f"tp_bar_{F}"] = _first_touch(prog, F)
    for S in STOP_GRID:
        out[f"stop_bar_{S}"] = _first_touch(adv, S)
    # Progress at each candidate horizon, for timeout P&L.
    for H in HORIZON_GRID_HOURS:
        hb = int(H * 60 / 30)
        out[f"prog_at_{H}h"] = prog[:, hb - 1]
    return pd.DataFrame(out)


def attach_relationship_age(df: pd.DataFrame, pvalues_path: Path = PVALUES_PATH) -> pd.DataFrame:
    """How many consecutive days the pair has already been passing the gate.

    0 means the gate turned on today -- the freshest possible entry, which is
    what "spot it earlier" is trying to buy more of. NaN means the gate was
    not passing that day at all, i.e. a trade the current system would never
    have taken; kept, not dropped, because those rows are exactly the ones
    that reveal whether the gate is leaving money on the table.
    """
    if not pvalues_path.exists():
        print("[WARN] p-values missing -- relationship age skipped")
        return df
    from coint_survival import SMOOTHED_LOOKBACK_WINDOWS
    pv = pd.read_parquet(pvalues_path)
    pv["date"] = pd.to_datetime(pv["date"]).dt.normalize()
    pv = pv.sort_values(["ticker_a", "ticker_b", "date"])
    pv["sm"] = (pv.groupby(["ticker_a", "ticker_b"])["p_value"]
                .transform(lambda s: s.rolling(SMOOTHED_LOOKBACK_WINDOWS,
                                               min_periods=SMOOTHED_LOOKBACK_WINDOWS).mean()))
    pv["passing"] = pv["sm"] < RECENT_P_THRESHOLD
    # Consecutive-day run length of `passing`, per pair.
    g = pv.groupby(["ticker_a", "ticker_b"])["passing"]
    blocks = (~pv["passing"]).groupby([pv["ticker_a"], pv["ticker_b"]]).cumsum()
    pv["age_days"] = pv.groupby(["ticker_a", "ticker_b", blocks]).cumcount()
    pv.loc[~pv["passing"], "age_days"] = np.nan
    return df.merge(pv[["ticker_a", "ticker_b", "date", "age_days", "passing", "p_value"]],
                    on=["ticker_a", "ticker_b", "date"], how="left")


def run(max_pairs: int | None = None, output_path: Path = OUTPUT_PATH) -> pd.DataFrame:
    print("[INFO] Loading price universe...")
    df = get_price_levels(align=False)
    tickers = df.columns.tolist()
    pairs = [(a, b) for a, b in itertools.combinations(tickers, 2)
             if _base_symbol(a) != _base_symbol(b)]
    if max_pairs:
        pairs = pairs[:max_pairs]
    print(f"[INFO] {len(pairs)} pairs, horizon window {MAX_HORIZON_BARS} bars")

    parts, t0 = [], time.time()
    step = max(1, len(pairs) // 10)
    for i, (a, b) in enumerate(pairs):
        pd_ = df[[a, b]].dropna()
        if len(pd_) < MIN_JOINT_BARS:
            continue
        r = build_pair_paths(a, b, pd_)
        if r is not None:
            parts.append(r)
        if (i + 1) % step == 0:
            print(f"  [{i+1}/{len(pairs)}] {time.time()-t0:.0f}s")
    out = pd.concat(parts, ignore_index=True)
    print(f"[INFO] {len(out)} candidate trades")
    out = attach_relationship_age(out)
    out.to_parquet(output_path, index=False)
    print(f"[INFO] Wrote {output_path}")
    return out


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(df: pd.DataFrame, F: float, S: float, H: int, charge_costs: bool = True):
    """P&L per trade, in sigma units, for one (take-profit, stop, horizon)."""
    hb = int(H * 60 / 30)
    tp_bar = df[f"tp_bar_{F}"].to_numpy()
    st_bar = df[f"stop_bar_{S}"].to_numpy()
    absz = df["z"].abs().to_numpy()

    tp_ok = (tp_bar >= 0) & (tp_bar < hb)
    st_ok = (st_bar >= 0) & (st_bar < hb)
    # A barrier not touched inside the horizon must not win a comparison
    # against one that was, so untouched is pushed beyond every real bar.
    tp_eff = np.where(tp_ok, tp_bar, np.inf)
    st_eff = np.where(st_ok, st_bar, np.inf)

    win = tp_ok & (tp_eff < st_eff)
    loss = st_ok & (st_eff <= tp_eff)
    timeout = ~win & ~loss

    pnl = np.empty(len(df))
    pnl[win] = F * absz[win]
    pnl[loss] = -S
    pnl[timeout] = df[f"prog_at_{H}h"].to_numpy()[timeout] * absz[timeout]

    if charge_costs:
        pnl = pnl - (ROUND_TRIP_COST_FRAC / df["sigma"].to_numpy())
    return pnl, win, loss, timeout


def sweep(df: pd.DataFrame, charge_costs: bool = True) -> pd.DataFrame:
    rows = []
    for F in TP_GRID:
        for S in STOP_GRID:
            for H in HORIZON_GRID_HOURS:
                pnl, win, loss, to = evaluate(df, F, S, H, charge_costs)
                rows.append({
                    "take_profit_frac": F, "stop_sigma": S, "horizon_h": H,
                    "n": len(df), "win_rate": win.mean() * 100,
                    "loss_rate": loss.mean() * 100, "timeout_rate": to.mean() * 100,
                    "mean_pnl_sigma": pnl.mean(), "median_pnl_sigma": np.median(pnl),
                    "total_pnl_sigma": pnl.sum(),
                })
    return pd.DataFrame(rows).sort_values("mean_pnl_sigma", ascending=False)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--max-pairs", type=int, default=None)
    args = ap.parse_args()
    if args.build:
        run(max_pairs=args.max_pairs)
    else:
        d = pd.read_parquet(OUTPUT_PATH)
        print(f"loaded {len(d)} candidate trades\n")
        s = sweep(d)
        print("=" * 90)
        print("TOP 15 exit configurations, net of costs (P&L in sigma units per trade)")
        print("=" * 90)
        print(s.head(15).to_string(index=False))
        print()
        print("current live configuration for comparison:")
        cur = s[(s.take_profit_frac == 0.8) & (s.stop_sigma == 2.5) & (s.horizon_h == 24)]
        print(cur.to_string(index=False))
