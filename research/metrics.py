"""
Canonical, single-source-of-truth performance metrics for trade_pool.parquet
(and, compatibly, trade_pool_gap.parquet -- same schema plus a gap_days
column). Replaces every ad hoc Sharpe/win-rate/etc. calculation done
per-backtest before this module existed.

Read-only: nothing here writes to either pool file. Callers pass in an
already-loaded DataFrame (see load_pool()) and get metrics back -- no side
effects, no new discovery scans, no new backtests.

Every metric is reported three ways, always all three, never just one:
  - pooled: computed directly across every trade in the slice, as if it
    were one combined ledger.
  - per_pair_avg: computed per pair first, then averaged (unweighted mean)
    across ALL pairs, including ones flagged low_n. A pair with 1 trade
    counts the same as a pair with 30 in this average.
  - per_pair_avg_filtered: the same per-pair average, but excluding pairs
    whose own n_trades is below min_trades_for_stable_metrics before
    averaging. Added because per_pair_avg's ratio metrics (Sharpe, Sortino)
    can be dominated by a single low-n pair whose near-zero return variance
    produces an outsized value -- confirmed concretely: at gap=0, one pair
    (AR/NEIRO, n=2, both trades landing within ~8 points of return of each
    other) alone pushed per_pair_avg's Sharpe to 320+ and Sortino to a
    similar order of magnitude. per_pair_avg_filtered is shown ALONGSIDE
    per_pair_avg, never in place of it -- dropping low-n pairs is itself a
    choice with a cost (less coverage, and a real thing happened in those
    trades even if the ratio built from 2 of them isn't trustworthy).
pooled and per_pair_avg can disagree with each other too -- confirmed
empirically in the gap-window sweep (2026-08): gap=3's pooled win rate was
the highest of that sweep while its per-pair-averaged win rate was the
lowest, because a handful of pairs picked up extra winning trades at gap=3
without more pairs actually becoming profitable. Reporting only one view
risks missing exactly that kind of divergence, so MetricsReport always
carries all three -- there is no "just give me the number" path through
this module.

Max drawdown definition (confirmed with the user before implementing):
cumulative realized_pnl_net, trades ordered by exit_time, peak-to-trough in
dollars. Pooled: one combined equity curve across every trade in the slice
(all pairs, all windows, interleaved by real exit_time) -- answers "worst
peak-to-trough if this whole machine had run as one combined ledger".
Per-pair-avg: the same calculation run separately within each pair's own
exit_time-ordered trade sequence, then averaged across pairs.

Return figure -- IMPORTANT, changed after the module's first version: every
return-based metric here (avg_return_pct, sharpe, sortino) is computed on
`true_return_pct`, NOT on the pool's `pnl_pct` column:

    true_return_pct = realized_pnl_net /
        ((filled_qty_a*entry_px_a + filled_qty_b*entry_px_b) / cfg_LEVERAGE)
        * 100

This is dollar P&L over the actual margin at risk for that trade (combined
entry notional divided by the account leverage active for that run) -- a
real leveraged capital return. `pnl_pct` (the pool's own field) is NOT a
return at all: traced through research/signal_generator.py, it's
`abs(current_spread - entry_spread) / abs(entry_spread - mu_at_entry)` --
a dimensionless "fraction of the reversion distance traveled," unsigned, no
dollars or capital anywhere in it. Using it as a return proxy (this module's
original version did) was a bug, found and confirmed by tracing the
sizing/fill code directly -- see the conversation this fix came from. It is
kept in every MetricsResult as `avg_reversion_capture_ratio`, clearly
separated from the return fields, because it's still a legitimate signal-
quality diagnostic (how far price traveled relative to the model's own
distance-to-mean estimate) -- it's just not P&L.

Sharpe / Sortino (confirmed with the user before implementing): trade-level,
not time-annualized -- most slices here don't have enough trades or span
for annualization to mean anything.
  sharpe  = mean(true_return_pct) / std(true_return_pct, ddof=1)
  sortino = mean(true_return_pct) / sqrt(mean(min(true_return_pct, 0)**2))
            (downside deviation computed over ALL trades, target return = 0,
            not just over the losing trades)

Sortino's inf handling (confirmed with the user before implementing): a pair
with zero losing trades has downside_dev=0, so its own sortino is +inf --
not a large finite number the way a near-zero-variance Sharpe is, an actual
infinity. Such pairs are EXCLUDED from per_pair_avg / per_pair_avg_filtered's
sortino average (not capped, not given a substitute value) -- but that
exclusion is counted and exposed on the MetricsResult itself
(`sortino_excluded_inf_pairs`, split into `..._low_n` and `..._high_n`), not
just visible by cross-referencing the per-pair table. `..._high_n` in particular means a pair cleared min_trades_for_stable_metrics
and STILL has zero losses -- a genuine "no losses yet" pair, not a
small-sample artifact; worth a second look whenever it's nonzero. Checked
against the full pool at the time this was added: NOT always 0 --
discovery_end_date=2026-07-22 has exactly one such pair, DATA/OL (n=6,
win_rate=1.0, sortino=inf despite clearing the n=5 threshold), which is why
this needed a real field instead of an assumption that filtering by n alone
would always be enough.

Low-n handling (confirmed with the user before implementing): every metric
is always computed and returned -- nothing is hidden or suppressed. Ratio-
based metrics (sharpe, sortino, profit_factor, max_drawdown*) get a
`low_n=True` flag on the MetricsResult when the sample behind them is small
(threshold: `min_trades_for_stable_metrics`, default 5 -- trades for the
pooled view, distinct pairs for the per-pair-averaged view). `.fmt()`
renders that as a "(low-n, n=X)" suffix for print output; the raw numeric
fields are untouched either way.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Fields rendered with a "(low-n, ...)" caveat suffix when low_n is set --
# the metrics whose reliability actually degrades with few samples. win_rate,
# avg_return_pct, avg_realized_pnl_net, expectancy, avg_reversion_capture_ratio
# print plainly regardless of n.
_RATIO_FIELDS = ("sharpe", "sortino", "profit_factor", "max_drawdown", "max_drawdown_pct")

# All numeric fields on MetricsResult, in report order.
_METRIC_FIELDS = (
    "win_rate", "avg_return_pct", "avg_realized_pnl_net", "expectancy",
    "profit_factor", "max_drawdown", "max_drawdown_pct", "sharpe", "sortino",
    "avg_reversion_capture_ratio",
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def normalize_trades(df: pd.DataFrame) -> pd.DataFrame:
    """The minimal normalization every function in this module relies on:
      - entry_time/exit_time parsed to real datetimes (stored as plain
        strings in the parquet, not a datetime dtype)
      - a `pair` column added as f"{instrument_a}/{instrument_b}" (verified
        against the current pool: the a/b assignment never flips for the
        same two tickers, so this is a stable, order-consistent pair key)
      - a `true_return_pct` column -- the real capital-level return, see
        module docstring for the formula and why it replaces `pnl_pct` as
        the return figure used everywhere in this module.
    Does not filter or aggregate anything. Exposed separately from
    load_pool() so callers that already have trades in memory (e.g.
    batch_backtest.py, before they've been written to the pool file) can
    normalize without a round trip through parquet.
    """
    df = df.copy()
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df["pair"] = df["instrument_a"] + "/" + df["instrument_b"]
    margin_at_risk = (
        (df["filled_qty_a"] * df["entry_px_a"] + df["filled_qty_b"] * df["entry_px_b"])
        / df["cfg_LEVERAGE"]
    )
    df["true_return_pct"] = df["realized_pnl_net"] / margin_at_risk * 100
    return df


def load_pool(path: str | Path) -> pd.DataFrame:
    """Load a trade pool parquet (trade_pool.parquet or trade_pool_gap.parquet)
    and apply normalize_trades(). Purely read-only against the file on disk.
    """
    return normalize_trades(pd.read_parquet(path))


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class MetricsResult:
    """Metrics for one slice of trades, computed as a single combined ledger.
    Used both for the pooled view (the whole slice at once) and, once per
    pair, as the building block for the per-pair-averaged view -- see
    MetricsReport."""
    n_trades: int
    n_pairs: int
    win_rate: float
    avg_return_pct: float       # true capital-level return, mean(true_return_pct) -- see module docstring
    avg_realized_pnl_net: float
    expectancy: float          # alias of avg_realized_pnl_net -- P&L per trade, dollars
    profit_factor: float       # gross profit / gross loss; inf if zero losers, nan if zero trades either side
    max_drawdown: float        # dollars, peak-to-trough on the exit_time-ordered equity curve
    max_drawdown_pct: float | None  # % of running peak; None if the curve never went positive
    sharpe: float                # mean(true_return_pct) / std(true_return_pct, ddof=1), not annualized
    sortino: float               # mean(true_return_pct) / downside_deviation(true_return_pct), not annualized
    avg_reversion_capture_ratio: float  # mean(pool's pnl_pct) -- diagnostic only, NOT a return; see module docstring
    low_n: bool                  # True if the sample behind this result is below the configured threshold
    # Sortino-specific: on pooled/per-pair-own results (a single ledger) these
    # are always 0 -- "excluded pairs" only means something when this result
    # IS an average across pairs (per_pair_avg / per_pair_avg_filtered). A
    # pair's own sortino is +inf when it has zero losing trades (no downside
    # deviation to divide by); such pairs are excluded (not capped, not
    # estimated) from the average, per explicit instruction. See module
    # docstring for why this needed a visible count instead of silent exclusion.
    sortino_excluded_inf_pairs: int = 0       # total pairs dropped from this average's sortino because their own sortino was inf
    sortino_excluded_inf_pairs_low_n: int = 0   # of those, how many were ALSO low_n (the "artifact" case)
    sortino_excluded_inf_pairs_high_n: int = 0  # of those, how many cleared the trade-count threshold anyway --
                                                  # a genuine "no losses yet" pair, not a low-n artifact; flagged separately

    def fmt(self, field: str) -> str:
        """String value for one field, with a "(low-n, n=X)" suffix appended
        when low_n is set AND the field is one of the ratio-based metrics
        (sharpe/sortino/profit_factor/max_drawdown*) -- the others always
        print plainly."""
        val = getattr(self, field)
        if val is None:
            s = "n/a"
        elif isinstance(val, float) and math.isnan(val):
            s = "nan"
        elif isinstance(val, float) and math.isinf(val):
            s = "inf"
        elif isinstance(val, float):
            s = f"{val:.4f}"
        else:
            s = str(val)
        if self.low_n and field in _RATIO_FIELDS:
            s += f" (low-n, n={self.n_trades})"
        return s


@dataclass
class MetricsReport:
    """Three views of one slice, always together -- see module docstring for
    why this module never hands back just one of them.
      - pooled: every trade in the slice as one combined ledger.
      - per_pair_avg: per-pair-first, then averaged across ALL pairs
        (unweighted mean), including pairs flagged low_n.
      - per_pair_avg_filtered: same, but excluding pairs whose OWN n_trades
        is below min_trades_for_stable_metrics -- a cleaner read when a
        handful of low-n pairs are distorting per_pair_avg's ratio metrics
        (confirmed: this happens to Sharpe and Sortino both -- see module
        docstring). Shown alongside per_pair_avg, never in place of it."""
    pooled: MetricsResult
    per_pair_avg: MetricsResult
    per_pair_n: int                        # distinct pairs that went into per_pair_avg (all pairs)
    per_pair_avg_filtered: MetricsResult
    per_pair_avg_filtered_n: int           # distinct pairs that went into per_pair_avg_filtered (non-low-n only)
    per_pair_table: pd.DataFrame | None = None  # one row per pair's own MetricsResult; only when requested


# ---------------------------------------------------------------------------
# Core per-slice computation
# ---------------------------------------------------------------------------

def _empty_result() -> MetricsResult:
    nan = float("nan")
    return MetricsResult(
        n_trades=0, n_pairs=0, win_rate=nan, avg_return_pct=nan,
        avg_realized_pnl_net=nan, expectancy=nan, profit_factor=nan,
        max_drawdown=nan, max_drawdown_pct=None, sharpe=nan, sortino=nan,
        avg_reversion_capture_ratio=nan, low_n=True,
    )


def _single_slice_metrics(df: pd.DataFrame, min_trades_for_stable_metrics: int) -> MetricsResult:
    """All metrics for one already-filtered slice of trades, treated as one
    combined ledger."""
    n_trades = len(df)
    if n_trades == 0:
        return _empty_result()

    n_pairs = df["pair"].nunique()
    win_rate = (df["realized_pnl_net"] > 0).mean()
    avg_return_pct = df["true_return_pct"].mean()
    avg_realized_pnl_net = df["realized_pnl_net"].mean()
    expectancy = avg_realized_pnl_net
    avg_reversion_capture_ratio = df["pnl_pct"].mean()  # diagnostic only -- not a return, see module docstring

    gross_profit = df.loc[df["realized_pnl_net"] > 0, "realized_pnl_net"].sum()
    gross_loss = -df.loc[df["realized_pnl_net"] < 0, "realized_pnl_net"].sum()
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = float("inf")  # every trade a winner (or breakeven), no losers to divide by
    else:
        profit_factor = float("nan")  # no P&L on either side

    # Max drawdown -- cumulative realized_pnl_net, ordered by exit_time,
    # peak-to-trough in dollars (definition confirmed with user, see module docstring).
    ordered = df.sort_values("exit_time")
    equity = ordered["realized_pnl_net"].cumsum()
    running_peak = equity.cummax()
    drawdown = running_peak - equity
    max_drawdown = drawdown.max()
    peak_positive = running_peak > 0
    if peak_positive.any():
        max_drawdown_pct = (drawdown[peak_positive] / running_peak[peak_positive]).max() * 100
    else:
        max_drawdown_pct = None  # curve never had a positive peak to draw down from

    return_pct_vals = df["true_return_pct"]
    if n_trades >= 2 and return_pct_vals.std(ddof=1) > 0:
        sharpe = return_pct_vals.mean() / return_pct_vals.std(ddof=1)
    else:
        sharpe = float("nan")

    downside = return_pct_vals.clip(upper=0)
    downside_dev = math.sqrt((downside ** 2).mean())
    if downside_dev > 0:
        sortino = return_pct_vals.mean() / downside_dev
    elif (return_pct_vals > 0).all():
        sortino = float("inf")  # no losing trades at all
    else:
        sortino = float("nan")

    return MetricsResult(
        n_trades=n_trades, n_pairs=n_pairs, win_rate=win_rate,
        avg_return_pct=avg_return_pct, avg_realized_pnl_net=avg_realized_pnl_net,
        expectancy=expectancy, profit_factor=profit_factor,
        max_drawdown=max_drawdown, max_drawdown_pct=max_drawdown_pct,
        sharpe=sharpe, sortino=sortino,
        avg_reversion_capture_ratio=avg_reversion_capture_ratio,
        low_n=n_trades < min_trades_for_stable_metrics,
        # This IS a single ledger (one pair, or the whole pooled slice), not
        # an average across pairs -- no exclusion concept applies here.
        sortino_excluded_inf_pairs=0, sortino_excluded_inf_pairs_low_n=0,
        sortino_excluded_inf_pairs_high_n=0,
    )


def _mean_ignore_inf(s: pd.Series) -> float:
    """Unweighted mean, excluding +/-inf entries (e.g. a pair with zero
    losing trades has profit_factor=inf -- included, it would poison the
    whole average into inf). NaNs (e.g. sharpe on an n=1 pair) are already
    excluded by pandas' default skipna mean."""
    finite = s[~s.isin([float("inf"), float("-inf")])]
    return finite.mean() if len(finite) else float("nan")


def _average_table(table: pd.DataFrame, min_trades_for_stable_metrics: int) -> MetricsResult:
    """Unweighted mean of each numeric field across the rows of `table` (one
    row per pair's own MetricsResult, as built by _average_per_pair). Shared
    by both the all-pairs and non-low-n-only variants of the per-pair-averaged
    view -- the only difference between them is which rows are in `table`.

    Sortino exclusion counting: a pair with sortino=inf (zero losing trades)
    is excluded from the average by _mean_ignore_inf, per explicit
    instruction not to cap or substitute a value. That exclusion is counted
    here and split into low_n vs. not, so a caller reading this MetricsResult
    alone -- without cross-referencing the per-pair table -- can see it. When
    `table` is already the non-low-n-filtered set (per_pair_avg_filtered's
    call), every row has low_n=False by construction, so
    sortino_excluded_inf_pairs_low_n is always 0 there and any exclusion
    counted is automatically a genuine "cleared the trade-count bar but still
    has zero losses" pair, not a low-n artifact."""
    n_pairs = len(table)

    is_inf_sortino = table["sortino"].isin([float("inf"), float("-inf")]) if n_pairs else pd.Series([], dtype=bool)
    sortino_excluded = int(is_inf_sortino.sum())
    sortino_excluded_low_n = int((is_inf_sortino & table["low_n"]).sum()) if n_pairs else 0
    sortino_excluded_high_n = sortino_excluded - sortino_excluded_low_n

    return MetricsResult(
        n_trades=int(table["n_trades"].sum()),  # total underlying trades (not averaged -- a count, not a rate)
        n_pairs=n_pairs,
        win_rate=_mean_ignore_inf(table["win_rate"]),
        avg_return_pct=_mean_ignore_inf(table["avg_return_pct"]),
        avg_realized_pnl_net=_mean_ignore_inf(table["avg_realized_pnl_net"]),
        expectancy=_mean_ignore_inf(table["expectancy"]),
        profit_factor=_mean_ignore_inf(table["profit_factor"]),
        max_drawdown=_mean_ignore_inf(table["max_drawdown"]),
        max_drawdown_pct=(
            _mean_ignore_inf(table["max_drawdown_pct"].astype(float))
            if table["max_drawdown_pct"].notna().any() else None
        ),
        sharpe=_mean_ignore_inf(table["sharpe"]),
        sortino=_mean_ignore_inf(table["sortino"]),
        avg_reversion_capture_ratio=_mean_ignore_inf(table["avg_reversion_capture_ratio"]),
        # This variant's own sample size is "how many pairs went into it",
        # not raw trade count -- so low_n compares n_pairs against the same
        # threshold, deliberately not n_trades.
        low_n=n_pairs < min_trades_for_stable_metrics,
        sortino_excluded_inf_pairs=sortino_excluded,
        sortino_excluded_inf_pairs_low_n=sortino_excluded_low_n,
        sortino_excluded_inf_pairs_high_n=sortino_excluded_high_n,
    )


def _average_per_pair(
    df: pd.DataFrame, min_trades_for_stable_metrics: int,
) -> tuple[MetricsResult, int, MetricsResult, int, pd.DataFrame]:
    """Computes _single_slice_metrics per pair, then takes the unweighted
    mean of each numeric field across pairs -- two ways:
      - all pairs (existing behavior)
      - non-low-n pairs only: pairs whose OWN n_trades cleared
        min_trades_for_stable_metrics, i.e. table["low_n"] is False for that
        pair. This exists because a single 2-trade pair with near-zero
        return variance can dominate the all-pairs average's Sharpe/Sortino
        (confirmed: AR/NEIRO alone pushed gap=0's per-pair-avg Sharpe to
        320+ -- see the conversation this was added from) -- the filtered
        variant shows what the average looks like without those pairs
        distorting it. Both are always returned side by side; neither
        replaces the other.

    Returns (avg_all, n_pairs_all, avg_filtered, n_pairs_filtered,
    per_pair_table) -- per_pair_table carries one row per pair with its own
    full MetricsResult (not just the average, and NOT pre-filtered), for
    callers doing a same-pair cross-slice comparison."""
    if len(df) == 0:
        empty = _empty_result()
        return empty, 0, empty, 0, pd.DataFrame()

    pair_rows = []
    for pair, sub in df.groupby("pair"):
        r = _single_slice_metrics(sub, min_trades_for_stable_metrics)
        pair_rows.append({"pair": pair, **r.__dict__})
    table = pd.DataFrame(pair_rows)

    avg_all = _average_table(table, min_trades_for_stable_metrics)

    filtered_table = table[~table["low_n"]]
    n_pairs_filtered = len(filtered_table)
    avg_filtered = (
        _average_table(filtered_table, min_trades_for_stable_metrics)
        if n_pairs_filtered > 0 else _empty_result()
    )

    return avg_all, len(table), avg_filtered, n_pairs_filtered, table


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_metrics(
    df: pd.DataFrame,
    *,
    discovery_end_date: str | list[str] | tuple[str, str] | None = None,
    gap_days: int | list[int] | None = None,
    pairs: list[str] | list[tuple[str, str]] | None = None,
    exit_reason: str | list[str] | None = None,
    cfg_filters: dict | None = None,
    min_trades_for_stable_metrics: int = 5,
    return_per_pair_detail: bool = False,
) -> MetricsReport:
    """Filters `df` (as returned by load_pool()) down to the requested slice,
    then computes both the pooled and per-pair-averaged MetricsResult for it.
    Pure filtering + arithmetic on an in-memory DataFrame -- no I/O.

    discovery_end_date: a single "YYYY-MM-DD" string, a list of them (any
        match), or a (start, end) tuple treated as an inclusive date range.
    gap_days: only meaningful against trade_pool_gap.parquet -- raises
        ValueError if `df` has no gap_days column. Single int, list, or None.
    pairs: list of "A/B" strings or (a, b) tuples. Matched regardless of
        which side is A vs B.
    exit_reason: single value or list, matched against the exit_reason column.
    cfg_filters: dict of {column_name: value} equality filters against any
        cfg_* column (e.g. {"cfg_ENABLE_COINT_GATE": True}).
    min_trades_for_stable_metrics: threshold behind the `low_n` flag on both
        results in the returned report (see MetricsResult / module docstring).
    return_per_pair_detail: when True, the report's per_pair_table is
        populated with one row per pair's own full metrics.
    """
    sliced = df

    if discovery_end_date is not None:
        if isinstance(discovery_end_date, tuple):
            start, end = discovery_end_date
            sliced = sliced[(sliced["discovery_end_date"] >= start) & (sliced["discovery_end_date"] <= end)]
        elif isinstance(discovery_end_date, list):
            sliced = sliced[sliced["discovery_end_date"].isin(discovery_end_date)]
        else:
            sliced = sliced[sliced["discovery_end_date"] == discovery_end_date]

    if gap_days is not None:
        if "gap_days" not in sliced.columns:
            raise ValueError(
                "gap_days filter given but this DataFrame has no gap_days column -- "
                "load_pool trade_pool_gap.parquet, not trade_pool.parquet."
            )
        if isinstance(gap_days, list):
            sliced = sliced[sliced["gap_days"].isin(gap_days)]
        else:
            sliced = sliced[sliced["gap_days"] == gap_days]

    if pairs is not None:
        wanted: set[str] = set()
        for p in pairs:
            if isinstance(p, tuple):
                a, b = p
            else:
                a, b = p.split("/", 1)
            wanted.add(f"{a}/{b}")
            wanted.add(f"{b}/{a}")
        sliced = sliced[sliced["pair"].isin(wanted)]

    if exit_reason is not None:
        if isinstance(exit_reason, list):
            sliced = sliced[sliced["exit_reason"].isin(exit_reason)]
        else:
            sliced = sliced[sliced["exit_reason"] == exit_reason]

    if cfg_filters:
        for col, val in cfg_filters.items():
            sliced = sliced[sliced[col] == val]

    pooled = _single_slice_metrics(sliced, min_trades_for_stable_metrics)
    (per_pair_avg, per_pair_n, per_pair_avg_filtered, per_pair_avg_filtered_n,
     per_pair_table) = _average_per_pair(sliced, min_trades_for_stable_metrics)

    return MetricsReport(
        pooled=pooled,
        per_pair_avg=per_pair_avg,
        per_pair_n=per_pair_n,
        per_pair_avg_filtered=per_pair_avg_filtered,
        per_pair_avg_filtered_n=per_pair_avg_filtered_n,
        per_pair_table=per_pair_table if return_per_pair_detail else None,
    )


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def format_report(report: MetricsReport, title: str | None = None) -> str:
    """Human-readable pooled / per-pair-avg (all pairs) / per-pair-avg
    (non-low-n pairs only) summary, all three always side by side -- see
    module docstring for why this module never prints just one view."""
    lines = []
    if title:
        lines.append(title)
    p, a, f = report.pooled, report.per_pair_avg, report.per_pair_avg_filtered
    lines.append(
        f"  n_trades={p.n_trades}  n_pairs={p.n_pairs}  "
        f"(per-pair avg over {report.per_pair_n} pairs; "
        f"non-low-n-only avg over {report.per_pair_avg_filtered_n} pairs)"
    )
    lines.append(
        f"  Sortino exclusions (pairs with sortino=inf, dropped not capped): "
        f"per-pair-avg (all)={a.sortino_excluded_inf_pairs} "
        f"(low-n: {a.sortino_excluded_inf_pairs_low_n}, "
        f"high-n/no-losses-yet: {a.sortino_excluded_inf_pairs_high_n})  |  "
        f"per-pair-avg (non-low-n)={f.sortino_excluded_inf_pairs} "
        f"(high-n/no-losses-yet: {f.sortino_excluded_inf_pairs_high_n})"
    )
    lines.append(f"  {'metric':<24}{'pooled':<26}{'per-pair-avg (all)':<26}{'per-pair-avg (non-low-n)':<26}")
    for field in _METRIC_FIELDS:
        lines.append(f"  {field:<24}{p.fmt(field):<26}{a.fmt(field):<26}{f.fmt(field):<26}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Part 3 -- metrics over time across existing windows (no new backtests)
# ---------------------------------------------------------------------------

def metrics_by_window(df: pd.DataFrame, group_col: str = "discovery_end_date", **filters) -> pd.DataFrame:
    """One row per distinct value of group_col (sorted ascending), each with
    that slice's pooled and per-pair-averaged metrics flattened into columns
    (pooled_win_rate, per_pair_avg_win_rate, ...). Pure computation against
    an already-loaded DataFrame -- never triggers discovery or a backtest,
    runs in well under a second at current pool sizes.

    Any of compute_metrics's filter kwargs (gap_days, pairs, exit_reason,
    cfg_filters, min_trades_for_stable_metrics) can be passed through
    **filters and are applied identically to every group's slice. Do not
    also pass group_col itself as a filter kwarg -- it's supplied per row.
    """
    if group_col not in df.columns:
        raise ValueError(f"{group_col!r} is not a column in this DataFrame")

    rows = []
    for val in sorted(df[group_col].dropna().unique()):
        report = compute_metrics(df, **{group_col: val}, **filters)
        row = {group_col: val, "per_pair_n": report.per_pair_n,
               "per_pair_avg_filtered_n": report.per_pair_avg_filtered_n}
        for prefix, result in (
            ("pooled", report.pooled),
            ("per_pair_avg", report.per_pair_avg),
            ("per_pair_avg_filtered", report.per_pair_avg_filtered),
        ):
            for field in ("n_trades", "n_pairs", *_METRIC_FIELDS, "low_n",
                          "sortino_excluded_inf_pairs", "sortino_excluded_inf_pairs_low_n",
                          "sortino_excluded_inf_pairs_high_n"):
                row[f"{prefix}_{field}"] = getattr(result, field)
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).parent.parent
    pool_path = PROJECT_ROOT / "research" / "trade_pool.parquet"
    gap_pool_path = PROJECT_ROOT / "research" / "trade_pool_gap.parquet"

    if pool_path.exists():
        print(f"=== {pool_path.name}: metrics by discovery_end_date ===")
        df = load_pool(pool_path)
        table = metrics_by_window(df, "discovery_end_date")
        cols = ["discovery_end_date", "pooled_n_trades", "pooled_n_pairs",
                "pooled_win_rate", "per_pair_avg_win_rate",
                "pooled_avg_return_pct", "per_pair_avg_avg_return_pct",
                "pooled_sharpe", "per_pair_avg_sharpe", "per_pair_avg_filtered_sharpe",
                "pooled_sortino", "per_pair_avg_sortino", "per_pair_avg_filtered_sortino"]
        print(table[cols].to_string(index=False))
        print()

    if gap_pool_path.exists():
        print(f"=== {gap_pool_path.name}: metrics by gap_days ===")
        gdf = load_pool(gap_pool_path)
        table = metrics_by_window(gdf, "gap_days")
        cols = ["gap_days", "pooled_n_trades", "pooled_n_pairs",
                "pooled_win_rate", "per_pair_avg_win_rate",
                "pooled_avg_return_pct", "per_pair_avg_avg_return_pct",
                "pooled_sharpe", "per_pair_avg_sharpe", "per_pair_avg_filtered_sharpe",
                "pooled_sortino", "per_pair_avg_sortino", "per_pair_avg_filtered_sortino"]
        print(table[cols].to_string(index=False))
