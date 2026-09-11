"""
PAIR SELECTION: TICKER_A/TICKER_B below are hardcoded rather than picked by
re-running the cointegration scan on every run (that scan is slow and its
result doesn't change between backtest runs since it reads the same static
feather files). To pick a new pair:
  1. Run `python research/pair_analysis.py` (or call analyze_top_pairs() /
     get_tradeable_pairs() directly) to see the current "Tradeable
     candidates" table.
  2. Pick a futures/futures pair from that table (check
     user_data/normalized/manifest.json — both tickers need
     instrument_type == "futures"; pairs_strategy.py only builds
     CryptoPerpetual instruments, and only OKX futures tickers have raw
     OHLCV feather files on disk).
  3. Update TICKER_A and TICKER_B below to the chosen pair's bare underlying
     symbols (e.g. "SNX", not "SNX_USDT_USDT" or "SNX-USDT-SWAP").
  4. Update LAST_SELECTED_DATE and LAST_SELECTED_STATS so it's obvious at a
     glance how stale the pair is.
"""
import os, sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import json
import pandas as pd
import numpy as np
from decimal import Decimal
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import CacheConfig
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.currencies import Currency
from nautilus_trader.model.enums import (
    AccountType, OmsType, BarAggregation, PriceType, AggregationSource
)

from nautilus_trader.model.objects import Price, Quantity, Money
from nautilus_trader.model.data import Bar, BarType, BarSpecification

from nautilus.pairs_strategy import PairsStrategy, PairsStrategyConfig

# CONFIG — single source of truth for timeframe/capital/lookback
TIMEFRAME = "30m"
BAR_HOURS = 0.5
# Walk-forward is the default: 15d MIN_BARS warm-up + 7-day holdout week,
# matching research/run_all.py's WALKFORWARD_DAYS_BACK=7 -- backtests the
# same window selection was blind to. Edit directly for a different window
# (45 = the old full 15d warm-up + 30d evaluation, no holdout).
LOOKBACK_DAYS = 22
CAPITAL = 300.0        # real starting account balance (Money passed to add_venue)
TRADE_CAPITAL = 30.0   # per-trade budget: both legs combined, at 1x, before leverage
RISK_BUDGET_PCT = 0.05  # unused while TARGET_LEVERAGE is set below (leverage-target mode)
# Position sizing: combined notional (both legs) = TARGET_LEVERAGE * TRADE_CAPITAL,
# split leg_a/leg_b by |beta|. Set to None to fall back to RISK_BUDGET_PCT-based
# risk-budget sizing (which uses CAPITAL, not TRADE_CAPITAL) instead.
TARGET_LEVERAGE = 20.0
# Account leverage for the MARGIN venue — the not-to-exceed margin ceiling.
# Must stay above TARGET_LEVERAGE. Nautilus defaults MARGIN accounts to 10x if
# left unset — set explicitly here so it's a visible, deliberate choice rather
# than an implicit engine default.
LEVERAGE = Decimal(20)
# Rolling history the strategy carries -- NOT a one-off warm-up. pairs_strategy
# re-slices bars[:min_bars] on every bar, so this is the estimation window in
# force at every signal evaluation, and it is also the gate that blocks trading
# until that many bars exist. Within a LOOKBACK_DAYS window, the tradeable span
# is therefore (LOOKBACK_DAYS - MIN_BARS days).
#
# Was 15 days (720 bars at 30m), which is far more than any gate consumes:
#     Gate 1 cointegration   336 bars (7d)   <- the real binding requirement
#     Gate 5 volatility regime 336 bars (7d)
#     Gate 2 EWMA OU fit     ~58 bars (~29h) effective. The decay half-life is
#                            max(20, 2 x reference_halflife_bars); measured
#                            fitted half-lives are 2.2-5.7h (~5 bars), so the
#                            20-bar floor binds and the fit never sees anything
#                            like 720 bars of information regardless.
#     Gate 4 static theta    uses whatever window it is handed
#
# So 384 of the 720 bars bought nothing for gates 1, 2 and 5 while costing 8
# days of every backtest's tradeable span -- the APE/DOGE run advertised as 22
# days actually traded 6. Dropping to 336 doubles the evaluation window (7d ->
# 14d) on identical data. The one real cost is Gate 4's sample size, and Gate 4
# is the gate already flagged as testing the static OU fit rather than the EWMA
# fit the trade decision uses, so it was measuring the wrong theta either way.
MIN_BARS = int(round(7 * 24 / BAR_HOURS))
# Experiment: skip the live rolling-window cointegration re-check (Gate 1),
# relying only on the one-time whole-window test done at pair selection.
# Toggle back to True to restore it — see generate_entry_signal's docstring
# for why these two checks are not redundant.
# Env override for one-off A/B runs without editing this file: ENABLE_COINT_GATE=false
ENABLE_COINT_GATE = os.environ.get("ENABLE_COINT_GATE", "true").strip().lower() != "false"

# Entry/exit geometry, overridable so the current live settings and the
# sweep-derived alternative can be A/B'd on identical data without editing
# code between runs. Defaults reproduce the current live behaviour.
#   current : MIN_DEVIATION_SIGMA=1.0 TAKE_PROFIT_PCT=0.8 STOP_SIGMA=2.5 MAX_HOLD_HOURS=(unset)
#   sweep   : MIN_DEVIATION_SIGMA=3.0 TAKE_PROFIT_PCT=1.0 STOP_SIGMA=2.0 MAX_HOLD_HOURS=72
MIN_DEVIATION_SIGMA = float(os.environ.get("MIN_DEVIATION_SIGMA", "1.0"))
TAKE_PROFIT_PCT = float(os.environ.get("TAKE_PROFIT_PCT", "0.80"))
STOP_SIGMA = float(os.environ.get("STOP_SIGMA", "2.5"))
_mh = os.environ.get("MAX_HOLD_HOURS", "").strip()
MAX_HOLD_HOURS = float(_mh) if _mh else None
# Gate 2's OU fit is EWMA-only (fit_ou_ewma) as of 2026-08-20 -- was an A/B
# toggle against the static full-window fit (fit_ou), removed after backtest
# evidence favored EWMA; see signal_generator.py's generate_entry_signal and
# ou_model.py's EWMA_HALFLIFE_MULTIPLIER. The env-var-driven OU_ESTIMATOR/
# EWMA_MULTIPLIER toggle that used to live here is gone with it -- re-add
# from git history (this file's prior revisions) if that comparison needs
# to be rerun; the sweep scripts/results that produced this decision are at
# research/run_ab_sweep2.sh, run_ab_sweep3.sh, and ab_sweep{2,3}_results.csv.

# Optional override for where the per-run trade log JSON gets written (see
# PairsStrategyConfig.trade_log_output_path / pairs_strategy.py's on_stop()).
# None (default, unset): unchanged behavior -- always
# research/trade_log_dump.json, same fixed path as before this existed. Set
# by scripts/batch_backtest.py to a unique per-pair temp path so multiple
# pairs in one batch never clobber each other or a concurrent solo run.
TRADE_LOG_OUTPUT_PATH = os.environ.get("TRADE_LOG_OUTPUT_PATH")

# STEP 0 — PAIR SELECTION (hardcoded — see module docstring for how to refresh this)
TICKER_A = "API3"
TICKER_B = "SOPH"
LAST_SELECTED_DATE = "2026-08-20"
LAST_SELECTED_STATS = "p_value=0.0000, half_life_hours=9.6, coint_stability=0.5, recent_cointegrated=True"

# Env var overrides for sweeping multiple candidates without hand-editing this
# file per run -- e.g. PAIR_A=DATA PAIR_B=MOVE python nautilus/run_backtest.py.
# Unset by default, so TICKER_A/TICKER_B above stay the single source of
# truth for a normal one-off run.
TICKER_A = os.environ.get("PAIR_A", TICKER_A)
TICKER_B = os.environ.get("PAIR_B", TICKER_B)

ticker_a, ticker_b = TICKER_A, TICKER_B

manifest_path = Path(project_root) / "user_data" / "normalized" / "manifest.json"
with open(manifest_path) as f:
    manifest = json.load(f)

for t in (ticker_a, ticker_b):
    if manifest.get(t, {}).get("instrument_type") != "futures":
        raise RuntimeError(
            f"Hardcoded ticker {t!r} is not a futures instrument in manifest.json — "
            f"check TICKER_A/TICKER_B in run_backtest.py."
        )

print(
    f"[INFO] Hardcoded pair: {ticker_a}/{ticker_b} "
    f"(selected {LAST_SELECTED_DATE}, {LAST_SELECTED_STATS})"
)
if os.environ.get("BACKTEST_START_DATE"):
    print(f"[INFO] Backtest window anchor: BACKTEST_START_DATE={os.environ['BACKTEST_START_DATE']} "
          f"(window = [start, start+{LOOKBACK_DAYS}d])")
else:
    print(f"[INFO] Backtest end date: {os.environ.get('BACKTEST_END_DATE') or '(latest available)'}")

# Machine-readable snapshot of every constant above that governs this run --
# printed once, here, so a caller (scripts/batch_backtest.py) can capture the
# EXACT config that produced a given trade log by parsing this line out of
# captured stdout, rather than hand-copying/duplicating these constants
# elsewhere and risking drift (the failure mode research/run_all.py's own
# comments already flag for a hand-copied filter mask). maker_fee/taker_fee
# mirror the Decimal literals hardcoded in make_instrument() below -- not
# module-level constants themselves, so they're listed here explicitly.
_config_snapshot = {
    "TIMEFRAME": TIMEFRAME,
    "BAR_HOURS": BAR_HOURS,
    "LOOKBACK_DAYS": LOOKBACK_DAYS,
    "CAPITAL": CAPITAL,
    "TRADE_CAPITAL": TRADE_CAPITAL,
    "RISK_BUDGET_PCT": RISK_BUDGET_PCT,
    "TARGET_LEVERAGE": TARGET_LEVERAGE,
    "LEVERAGE": float(LEVERAGE),
    "MIN_BARS": MIN_BARS,
    "ENABLE_COINT_GATE": ENABLE_COINT_GATE,
    # Entry/exit geometry -- printed so a run's log proves which parameter set
    # actually executed. A/B results are worthless if the config that produced
    # them cannot be read back off the run itself.
    "MIN_DEVIATION_SIGMA": MIN_DEVIATION_SIGMA,
    "TAKE_PROFIT_PCT": TAKE_PROFIT_PCT,
    "STOP_SIGMA": STOP_SIGMA,
    "MAX_HOLD_HOURS": MAX_HOLD_HOURS,
    "maker_fee": 0.0002,
    "taker_fee": 0.0005,
    "BACKTEST_START_DATE": os.environ.get("BACKTEST_START_DATE"),
    "BACKTEST_END_DATE": os.environ.get("BACKTEST_END_DATE"),
}
print(f"[CONFIG] {json.dumps(_config_snapshot)}")

# FEATHER PATHS
a_path = os.path.join(
    project_root, "user_data/data/okx/futures",
    f"{ticker_a}_USDT_USDT-{TIMEFRAME}-futures.feather",
)
b_path = os.path.join(
    project_root, "user_data/data/okx/futures",
    f"{ticker_b}_USDT_USDT-{TIMEFRAME}-futures.feather",
)

# STEP 1 — LOAD AND FILTER TO LAST 30 DAYS
a_df = pd.read_feather(a_path)
b_df = pd.read_feather(b_path)

for df in [a_df, b_df]:
    df.sort_values("date", ascending=True, inplace=True)
    df.reset_index(drop=True, inplace=True)

a_df = a_df[a_df["close"].notna() & (a_df["close"] > 0)].reset_index(drop=True)
b_df = b_df[b_df["close"].notna() & (b_df["close"] > 0)].reset_index(drop=True)

# BACKTEST_END_DATE env var (optional, e.g. "2026-08-05") anchors the
# LOOKBACK_DAYS window to a specific historical date instead of each
# ticker's own latest bar -- lets the same pair be backtested over a few
# different historical windows (not just "the most recent N days") to check
# whether a result holds up across time, not just in the one window it was
# first observed in. None (default): unchanged behavior, ends at "now".
#
# BACKTEST_START_DATE env var (optional, e.g. "2026-08-01") is the other way
# to anchor the window: instead of ending AT a date, the window STARTS at
# it and runs forward LOOKBACK_DAYS. Exists for gap-window evaluation
# (scripts/batch_backtest.py's GAP_DAYS) -- simulating "discovery found this
# pair on day X, waited N days, then started trading on data discovery never
# saw" (window = [X+N, X+N+LOOKBACK_DAYS]), as opposed to BACKTEST_END_DATE's
# [X-LOOKBACK_DAYS, X], which mostly overlaps whatever window discovery
# itself scanned. Mutually exclusive with BACKTEST_END_DATE -- setting both
# is almost certainly a mistake (unclear which anchor should win), so this
# raises rather than silently picking one.
_end_date_str = os.environ.get("BACKTEST_END_DATE")
_start_date_str = os.environ.get("BACKTEST_START_DATE")
if _end_date_str and _start_date_str:
    raise RuntimeError(
        "Both BACKTEST_END_DATE and BACKTEST_START_DATE are set -- ambiguous, "
        "pick one. BACKTEST_END_DATE anchors the window to end at a date; "
        "BACKTEST_START_DATE anchors it to start at one."
    )

if _start_date_str:
    a_cutoff = pd.Timestamp(_start_date_str, tz="UTC")
    b_cutoff = pd.Timestamp(_start_date_str, tz="UTC")
    a_end = a_cutoff + pd.Timedelta(days=LOOKBACK_DAYS)
    b_end = b_cutoff + pd.Timedelta(days=LOOKBACK_DAYS)
else:
    a_end = pd.Timestamp(_end_date_str, tz="UTC") if _end_date_str else a_df["date"].max()
    b_end = pd.Timestamp(_end_date_str, tz="UTC") if _end_date_str else b_df["date"].max()
    a_cutoff = a_end - pd.Timedelta(days=LOOKBACK_DAYS)
    b_cutoff = b_end - pd.Timedelta(days=LOOKBACK_DAYS)
a_df = a_df[(a_df["date"] >= a_cutoff) & (a_df["date"] <= a_end)].reset_index(drop=True)
b_df = b_df[(b_df["date"] >= b_cutoff) & (b_df["date"] <= b_end)].reset_index(drop=True)

print(f"[INFO] {ticker_a} bars after {LOOKBACK_DAYS}-day filter: {len(a_df)}")
print(f"[INFO] {ticker_b} bars after {LOOKBACK_DAYS}-day filter: {len(b_df)}")
print(f"[INFO] {ticker_a} date range: {a_df['date'].iloc[0]} -> {a_df['date'].iloc[-1]}")
print(f"[INFO] {ticker_b} date range: {b_df['date'].iloc[0]} -> {b_df['date'].iloc[-1]}")

# STEP 2 — DEFINE INSTRUMENTS
venue = Venue("OKX")


def make_instrument(ticker: str) -> CryptoPerpetual:
    symbol = f"{ticker}-USDT-SWAP"
    return CryptoPerpetual(
        instrument_id=InstrumentId(Symbol(symbol), venue),
        raw_symbol=Symbol(symbol),
        base_currency=Currency.from_str(ticker),
        quote_currency=USDT,
        settlement_currency=USDT,
        is_inverse=False,
        price_precision=4,
        size_precision=1,
        price_increment=Price.from_str("0.0001"),
        size_increment=Quantity.from_str("0.1"),
        multiplier=Quantity.from_str("1"),
        lot_size=Quantity.from_str("0.1"),
        max_quantity=None,
        min_quantity=Quantity.from_str("0.1"),
        max_notional=None,
        min_notional=None,
        max_price=None,
        min_price=None,
        margin_init=Decimal("0.02"),
        margin_maint=Decimal("0.01"),
        maker_fee=Decimal("0.0002"),
        taker_fee=Decimal("0.0005"),
        ts_event=0,
        ts_init=0,
    )


a_instrument = make_instrument(ticker_a)
b_instrument = make_instrument(ticker_b)

# STEP 3 — DEFINE BAR TYPES
a_bar_type = BarType(
    instrument_id=a_instrument.id,
    bar_spec=BarSpecification(30, BarAggregation.MINUTE, PriceType.LAST),
    aggregation_source=AggregationSource.EXTERNAL,
)
b_bar_type = BarType(
    instrument_id=b_instrument.id,
    bar_spec=BarSpecification(30, BarAggregation.MINUTE, PriceType.LAST),
    aggregation_source=AggregationSource.EXTERNAL,
)

# STEP 4 — CONSTRUCT BAR OBJECTS
def make_bars(df, bar_type, instrument):
    bars = []
    for row in df.itertuples():
        ts = int(pd.Timestamp(row.date).value)
        bar = Bar(
            bar_type=bar_type,
            open=Price(float(row.open), instrument.price_precision),
            high=Price(float(row.high), instrument.price_precision),
            low=Price(float(row.low), instrument.price_precision),
            close=Price(float(row.close), instrument.price_precision),
            volume=Quantity(float(row.volume), instrument.size_precision),
            ts_event=ts,
            ts_init=ts,
        )
        bars.append(bar)
    return bars


a_bars = make_bars(a_df, a_bar_type, a_instrument)
b_bars = make_bars(b_df, b_bar_type, b_instrument)

print(f"[INFO] {ticker_a} Bar objects: {len(a_bars)}")
print(f"[INFO] {ticker_b} Bar objects: {len(b_bars)}")

# STEP 5 — BUILD ENGINE
config = BacktestEngineConfig(
    trader_id="BACKTESTER-001",
    cache=CacheConfig(bar_capacity=1000),
)
engine = BacktestEngine(config=config)

# STEP 6 — ADD VENUE
engine.add_venue(
    venue=venue,
    oms_type=OmsType.NETTING,
    account_type=AccountType.MARGIN,
    base_currency=USDT,
    starting_balances=[Money(CAPITAL, USDT)],
    default_leverage=LEVERAGE,
)

# STEP 7 — ADD INSTRUMENTS AND DATA
engine.add_instrument(a_instrument)
engine.add_instrument(b_instrument)

engine.add_data(a_bars, sort=False)
engine.add_data(b_bars, sort=False)
engine.sort_data()

# STEP 8 — CONFIGURE AND ADD STRATEGY
strategy = PairsStrategy(config=PairsStrategyConfig(
    strategy_id="PAIRS-001",
    instrument_id_a=a_instrument.id,
    instrument_id_b=b_instrument.id,
    bar_type_a=str(a_bar_type),
    bar_type_b=str(b_bar_type),
    min_bars=MIN_BARS,
    bar_hours=BAR_HOURS,
    capital=TRADE_CAPITAL,
    risk_budget_pct=RISK_BUDGET_PCT,
    target_leverage=TARGET_LEVERAGE,
    enable_coint_gate=ENABLE_COINT_GATE,
    min_deviation_sigma=MIN_DEVIATION_SIGMA,
    take_profit_pct=TAKE_PROFIT_PCT,
    stop_sigma=STOP_SIGMA,
    max_hold_hours=MAX_HOLD_HOURS,
    trade_log_output_path=TRADE_LOG_OUTPUT_PATH,
))
engine.add_strategy(strategy)

# STEP 9 — RUN
print("[INFO] Running backtest engine...")
engine.run()
print("[INFO] Engine run complete.")

# STEP 10 — PRINT SUMMARY
print(f"[INFO] Backtest complete.")
print(f"[INFO] Account balance: "
      f"{engine.portfolio.account(venue).balance_total(USDT)}")
