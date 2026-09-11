"""Portfolio simulation over gate count, position count, and position SIZING.

WHY THIS REPLACES THE SCRATCH VERSION

The first portfolio simulation varied one gate (`passing`, gate 1 of six) and
two position counts, and gave every trade the same $600 notional. All three
were wrong in the same direction -- they hid where the risk actually comes
from. This sweeps:

  GATES        "at least k of the 5 boolean entry gates", k = 0..5, using
               entry_gates.parquet. Gate 3 (minimum deviation) is NOT one of
               the five: it is the entry threshold, swept separately, because
               folding the parameter under test into the pass/fail count would
               make the result uninterpretable.

  CONCURRENCY  1..20 simultaneous positions, with positions genuinely
               occupying a slot until their own exit bar, so a long holding
               rule crowds out later candidates the way it does in life.

  SIZING       the part that actually decides whether the account survives.

WHY SIZING DOMINATES

At a 1-sigma stop the loss is 2.6% of notional on the median pair and 13.6% at
the 99th percentile -- a 5x spread in dollar risk between two trades that look
identical on screen. Under a fixed $600 notional that spread passes straight
through to the account: the median stop costs $16, the p99 stop costs $81, and
nothing about the signal chose that. Sizing off the stop distance removes it:

  fixed       notional = CAPITAL_PER_TRADE * LEVERAGE_CAP      (current rule)
  vol_fixed   notional = RISK_DOLLARS / stop_pct               (constant $ risk)
  vol_frac    notional = risk_frac * equity / stop_pct         (compounding)

Under both vol rules leverage becomes an OUTPUT, not an input: a tight-stop
pair gets a bigger position, a wide-stop pair a smaller one, and the dollar
loss if the stop fills is the same either way. Notional is capped at
LEVERAGE_CAP * (equity / max_concurrent) so the rule can never ask for more
leverage than OKX allows on the equity that position is entitled to.

STOP SLIPPAGE: a stop is an intention, not a fill. STOP_SLIP inflates the
modelled stop loss so sizing is not calibrated against a perfect fill it will
not get. Setting it to 1.0 reproduces the optimistic earlier numbers.

RUIN: equity is checked every day and a run that reaches zero is over. A mean
per-trade number cannot express that, which is why every table here reports
P(ruin) next to the return.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import exit_sweep as es

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = os.path.join(PROJECT_ROOT, "research", "exit_sweep_paths.parquet")
GATES = os.path.join(PROJECT_ROOT, "research", "entry_gates.parquet")

MEASURED_COST = 0.000993          # live round trip, 7 completed trades
START_EQUITY = 300.0
LEVERAGE_CAP = 20.0               # user: "the leverage stays at 20x"
CAPITAL_PER_TRADE = 30.0          # the fixed rule's equity slice
# Stop fill quality, as a multiple of the intended stop distance. 1.0 means
# stops fill exactly at the level.
#
# This defaults to 1.0 -- NO assumption -- because the alternative is to bake a
# number nobody measured into every result. An earlier version of this file set
# it to 1.25 on my own judgement and reported the output as the finding; that
# one invented constant flipped the headline from +0.358% to -0.310% per trade,
# which is the whole conclusion, decided by a guess.
#
# What the data actually says: the live ledger contains exactly ONE adverse_move
# exit (GALA/UMA, 2026-08-18). Its intended stop distance was 0.0249 in spread
# units and it travelled 0.0404 before filling -- 1.62x, overshooting the level
# by 62% of the stop distance inside a single 30-minute bar. That is worse than
# 1.25, not better. But n=1 is not a basis for a default, so slippage is swept
# as an explicit axis instead (see the slippage table in run_risk_sweep) and
# every headline number is quoted at 1.0 with the sensitivity stated next to it.
#
# The sign of the result depends on this number. Treat any single-slippage
# figure as incomplete.
STOP_SLIP = 1.0
BARS_PER_DAY = 48                 # 30m bars

# Live thresholds from generate_entry_signal's defaults.
COINT_P, THETA_P, REGIME, PROB = 0.10, 0.05, 1.1, 0.60


def load(require_gates=True):
    d = pd.read_parquet(PATHS)
    d["date"] = pd.to_datetime(d["date"])
    d["absz"] = d["z"].abs()

    if os.path.exists(GATES):
        g = pd.read_parquet(GATES)
        g["date"] = pd.to_datetime(g["date"])
        d = d.merge(g, on=["ticker_a", "ticker_b", "date"], how="left")
    elif require_gates:
        raise FileNotFoundError(
            GATES + " -- run research/entry_gates_dataset.py first")
    else:
        for c in ["theta", "theta_p", "regime", "rev_prob",
                  "dev_sigma", "sigma_stationary"]:
            d[c] = np.nan

    # Gate 2 (OU fit) is a prerequisite for gates 4/5/6, so a non-finite theta
    # fails all of them. An uncomputed gate is not a passed gate.
    d["g_coint"] = d["passing"].fillna(False).astype(bool)
    d["g_oufit"] = d["theta"].notna() & (d["theta"] > 0)
    d["g_theta"] = d["theta_p"].notna() & (d["theta_p"] <= THETA_P)
    d["g_regime"] = d["regime"].notna() & (d["regime"] <= REGIME)
    d["g_prob"] = d["rev_prob"].notna() & (d["rev_prob"] >= PROB)
    d["n_gates"] = (d.g_coint.astype(int) + d.g_oufit.astype(int)
                    + d.g_theta.astype(int) + d.g_regime.astype(int)
                    + d.g_prob.astype(int))

    dw = d[d.absz >= 3.0].groupby("date").size().rename("n_wide")
    d = d.merge(dw, on="date", how="left")
    d["n_wide"] = d["n_wide"].fillna(0)
    return d.sort_values("date").reset_index(drop=True)


def outcome(sub, F, S, H, cost=MEASURED_COST):
    """Net % of notional, exit bar, win flag, and the stop's planned size.

    stop_pct is the fourth return because it is what the vol sizing rules
    divide by -- the whole point is that it varies by pair.
    """
    hb = int(H * 60 / 30)
    tp, st = sub["tp_bar_%s" % F].to_numpy(), sub["stop_bar_%s" % S].to_numpy()
    absz, sig = sub["absz"].to_numpy(), sub["sigma"].to_numpy()
    tp_ok, st_ok = (tp >= 0) & (tp < hb), (st >= 0) & (st < hb)
    tp_e = np.where(tp_ok, tp, np.inf)
    st_e = np.where(st_ok, st, np.inf)
    win = tp_ok & (tp_e < st_e)
    loss = st_ok & (st_e <= tp_e)
    to = ~win & ~loss
    pnl = np.empty(len(sub))
    pnl[win] = F * absz[win]
    pnl[loss] = -S * STOP_SLIP
    pnl[to] = sub["prog_at_%dh" % H].to_numpy()[to] * absz[to]
    net_pct = pnl * sig * 100 - cost * 100
    exit_bar = np.minimum(np.where(np.isinf(tp_e), hb, tp_e),
                          np.where(np.isinf(st_e), hb, st_e))
    stop_pct = S * STOP_SLIP * sig * 100
    return net_pct, exit_bar, win, stop_pct


def simulate(cand, max_concurrent, sizing="fixed", risk_frac=0.02,
             risk_dollars=6.0, n_sims=400, seed=0, rank_by=None):
    """Walk the test window day by day holding simultaneous positions.

    Returns (final equity multiples, max drawdowns, ruin rate, median realised
    gross leverage).
    """
    by_day = {dt: g for dt, g in cand.groupby("date")}
    days = sorted(by_day)
    rng = np.random.default_rng(seed)
    finals, dds, levs = [], [], []
    ruins = 0

    for _ in range(n_sims):
        equity = peak = START_EQUITY
        maxdd = 0.0
        open_slots = []                    # (free_day_idx, pnl_dollars, margin)
        used_margin = 0.0

        for i, dt in enumerate(days):
            still = []
            for free_at, pnl, marg in open_slots:
                if free_at <= i:
                    equity += pnl
                    used_margin -= marg
                else:
                    still.append((free_at, pnl, marg))
            open_slots = still

            if equity <= 0:
                ruins += 1
                equity = 0.0
                break
            peak = max(peak, equity)
            maxdd = max(maxdd, (peak - equity) / peak)

            free = max_concurrent - len(open_slots)
            if free <= 0:
                continue
            g = by_day[dt]
            k = min(free, len(g))
            if rank_by is None:
                pick = g.sample(k, random_state=int(rng.integers(1_000_000_000)))
            else:
                # Deliberate selection instead of random. Ranking by a feature
                # that scales the payoff (spread volatility above all) inflates
                # the per-trade percent without improving the bet, so the only
                # honest test of a ranking rule is what it does to the account,
                # ruin included -- which is why this lives in the simulator and
                # not in a per-trade average.
                col, asc, pool_mult = rank_by
                gg = g[np.isfinite(g[col])]
                if len(gg) < k:
                    gg = g
                # Shortlist then sample, rather than taking the top k outright.
                # Deterministic top-k makes every simulation identical, which
                # collapses the distribution: p5, median and p95 all land on the
                # same number and "P(ruin) 0%" means one path survived, not that
                # ruin is unlikely. Sampling k from a shortlist of pool_mult*k
                # keeps the selection effect while leaving the run stochastic,
                # and is closer to reality anyway -- the exact top pick is not
                # always fillable.
                pool = gg.sort_values(col, ascending=asc).head(max(k, int(pool_mult * k)))
                pick = pool.sample(min(k, len(pool)),
                                   random_state=int(rng.integers(1_000_000_000)))

            for net_pct, xb, stop_pct in zip(pick.net_pct.to_numpy(),
                                             pick.exit_bar.to_numpy(),
                                             pick.stop_pct.to_numpy()):
                if sizing == "fixed":
                    notional = CAPITAL_PER_TRADE * LEVERAGE_CAP
                else:
                    if not np.isfinite(stop_pct) or stop_pct <= 0:
                        continue
                    budget = (risk_frac * equity
                              if sizing in ("vol_frac", "vol_20x")
                              else risk_dollars)
                    notional = budget / (stop_pct / 100.0)
                    if sizing != "vol_20x":
                        # vol_frac/vol_fixed also refuse to let one position
                        # take more than its even share of the 20x budget.
                        notional = min(notional,
                                       LEVERAGE_CAP * equity / max_concurrent)
                    # vol_20x drops that per-position ceiling. Every position
                    # still runs at exactly LEVERAGE_CAP (margin below is
                    # notional/20 by construction, so leverage is 20x on all
                    # three vol rules -- the ceiling was never about leverage,
                    # it was about concentration). The only thing left holding
                    # size back is the margin check: total posted margin cannot
                    # exceed equity, which caps the whole book at 20x gross.
                margin = notional / LEVERAGE_CAP
                if used_margin + margin > equity:
                    continue
                used_margin += margin
                levs.append(notional / equity)
                days_held = max(1, int(np.ceil(xb / BARS_PER_DAY)))
                open_slots.append((i + days_held,
                                   net_pct / 100.0 * notional, margin))

        for _, pnl, _ in open_slots:
            equity += pnl
        finals.append(max(equity, 0.0) / START_EQUITY)
        dds.append(maxdd)

    return (np.array(finals), np.array(dds), ruins / n_sims,
            float(np.median(levs)) if levs else float("nan"))


def prep(d, split, mask_fn, F, S, H, min_rows=100):
    te = mask_fn(d[d.date >= split]).copy()
    if len(te) < min_rows:
        return None
    net, xb, win, sp = outcome(te, F, S, H)
    te["net_pct"], te["exit_bar"], te["win"], te["stop_pct"] = net, xb, win, sp
    return te


def pick_config(tr):
    """Best mean-net exit rule on the TRAIN split only."""
    best, cfg = -1e9, (1.0, 1.0, 24)
    for F in es.TP_GRID:
        for S in es.STOP_GRID:
            for H in es.HORIZON_GRID_HOURS:
                n, _, _, _ = outcome(tr, F, S, H)
                if len(n) and n.mean() > best:
                    best, cfg = n.mean(), (F, S, H)
    return cfg
