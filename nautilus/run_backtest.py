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
from research.pair_analysis import analyze_top_pairs, get_tradeable_pairs

# CONFIG — single source of truth for timeframe/capital/lookback
TIMEFRAME = "30m"
BAR_HOURS = 0.5
LOOKBACK_DAYS = 30
CAPITAL = 1000.0        # real starting account balance (Money passed to add_venue)
TRADE_CAPITAL = 100.0   # per-trade budget: both legs combined, at 1x, before leverage
RISK_BUDGET_PCT = 0.05  # unused while TARGET_LEVERAGE is set below (leverage-target mode)
# Position sizing: combined notional (both legs) = TARGET_LEVERAGE * TRADE_CAPITAL,
# split leg_a/leg_b by |beta|. Set to None to fall back to RISK_BUDGET_PCT-based
# risk-budget sizing (which uses CAPITAL, not TRADE_CAPITAL) instead.
TARGET_LEVERAGE = 50.0
# Account leverage for the MARGIN venue — the not-to-exceed margin ceiling.
# Must stay above TARGET_LEVERAGE. Nautilus defaults MARGIN accounts to 10x if
# left unset — set explicitly here so it's a visible, deliberate choice rather
# than an implicit engine default.
LEVERAGE = Decimal(75)
# Preserves the original 360-bars-of-720-at-1h split (15d lookback / 15d
# live-trading window within the 30-day backtest), rescaled to 30m bars.
MIN_BARS = int(round(15 * 24 / BAR_HOURS))
# Experiment: skip the live rolling-window cointegration re-check (Gate 1),
# relying only on the one-time whole-window test done at pair selection.
# Toggle back to True to restore it — see generate_entry_signal's docstring
# for why these two checks are not redundant.
ENABLE_COINT_GATE = False

# STEP 0 — PAIR SELECTION
# pairs_strategy.py only builds CryptoPerpetual instruments, and only OKX
# futures tickers have raw OHLCV feather files on disk (the normalized spot/
# LST store only keeps date+close) — so the candidate pair must be
# futures/futures, not just cointegration-ranked.
summary = analyze_top_pairs(top_n=20, days=LOOKBACK_DAYS)
tradeable = get_tradeable_pairs(summary)

manifest_path = Path(project_root) / "user_data" / "normalized" / "manifest.json"
with open(manifest_path) as f:
    manifest = json.load(f)


def _is_futures(ticker: str) -> bool:
    return manifest.get(ticker, {}).get("instrument_type") == "futures"


futures_tradeable = tradeable[
    tradeable["ticker_a"].map(_is_futures) & tradeable["ticker_b"].map(_is_futures)
]
if futures_tradeable.empty:
    raise RuntimeError(
        "No futures/futures tradeable pair found among the top candidates — "
        "the Nautilus harness only supports OKX perpetual futures legs. "
        "Try raising top_n in analyze_top_pairs() or widening the tradeable filters."
    )

chosen = futures_tradeable.iloc[0]
ticker_a, ticker_b = chosen.ticker_a, chosen.ticker_b
print(
    f"[INFO] Auto-selected pair: {ticker_a}/{ticker_b} "
    f"(p_value={chosen.p_value}, half_life_hours={chosen.half_life_hours}, "
    f"hurst={chosen.hurst}, coint_stability={chosen.coint_stability})"
)

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

a_cutoff = a_df["date"].max() - pd.Timedelta(days=LOOKBACK_DAYS)
b_cutoff = b_df["date"].max() - pd.Timedelta(days=LOOKBACK_DAYS)
a_df = a_df[a_df["date"] >= a_cutoff].reset_index(drop=True)
b_df = b_df[b_df["date"] >= b_cutoff].reset_index(drop=True)

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
