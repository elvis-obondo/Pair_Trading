import os, sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import pandas as pd
import numpy as np
from decimal import Decimal

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

# FEATHER PATHS
avax_path = os.path.join(project_root,
    "user_data/data/okx/futures/AVAX_USDT_USDT-1h-futures.feather")
link_path = os.path.join(project_root,
    "user_data/data/okx/futures/LINK_USDT_USDT-1h-futures.feather")

# STEP 1 — LOAD AND FILTER TO LAST 30 DAYS
avax_df = pd.read_feather(avax_path)
link_df = pd.read_feather(link_path)

for df in [avax_df, link_df]:
    df.sort_values("date", ascending=True, inplace=True)
    df.reset_index(drop=True, inplace=True)

avax_df = avax_df[avax_df["close"].notna() & (avax_df["close"] > 0)].reset_index(drop=True)
link_df = link_df[link_df["close"].notna() & (link_df["close"] > 0)].reset_index(drop=True)

avax_cutoff = avax_df["date"].max() - pd.Timedelta(days=30)
link_cutoff = link_df["date"].max() - pd.Timedelta(days=30)
avax_df = avax_df[avax_df["date"] >= avax_cutoff].reset_index(drop=True)
link_df = link_df[link_df["date"] >= link_cutoff].reset_index(drop=True)

print(f"[INFO] AVAX bars after 30-day filter: {len(avax_df)}")
print(f"[INFO] LINK bars after 30-day filter: {len(link_df)}")
print(f"[INFO] AVAX date range: {avax_df['date'].iloc[0]} -> {avax_df['date'].iloc[-1]}")
print(f"[INFO] LINK date range: {link_df['date'].iloc[0]} -> {link_df['date'].iloc[-1]}")

# STEP 2 — DEFINE INSTRUMENTS
venue = Venue("OKX")

avax_instrument = CryptoPerpetual(
    instrument_id=InstrumentId(Symbol("AVAX-USDT-SWAP"), venue),
    raw_symbol=Symbol("AVAX-USDT-SWAP"),
    base_currency=Currency.from_str("AVAX"),
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

link_instrument = CryptoPerpetual(
    instrument_id=InstrumentId(Symbol("LINK-USDT-SWAP"), venue),
    raw_symbol=Symbol("LINK-USDT-SWAP"),
    base_currency=Currency.from_str("LINK"),
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

# STEP 3 — DEFINE BAR TYPES
avax_bar_type = BarType(
    instrument_id=avax_instrument.id,
    bar_spec=BarSpecification(1, BarAggregation.HOUR, PriceType.LAST),
    aggregation_source=AggregationSource.EXTERNAL,
)
link_bar_type = BarType(
    instrument_id=link_instrument.id,
    bar_spec=BarSpecification(1, BarAggregation.HOUR, PriceType.LAST),
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

avax_bars = make_bars(avax_df, avax_bar_type, avax_instrument)
link_bars = make_bars(link_df, link_bar_type, link_instrument)

print(f"[INFO] AVAX Bar objects: {len(avax_bars)}")
print(f"[INFO] LINK Bar objects: {len(link_bars)}")

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
    starting_balances=[Money(1_000, USDT)],
)

# STEP 7 — ADD INSTRUMENTS AND DATA
engine.add_instrument(avax_instrument)
engine.add_instrument(link_instrument)

engine.add_data(avax_bars, sort=False)
engine.add_data(link_bars, sort=False)
engine.sort_data()

# STEP 8 — CONFIGURE AND ADD STRATEGY
strategy = PairsStrategy(config=PairsStrategyConfig(
    strategy_id="PAIRS-001",
    instrument_id_a=avax_instrument.id,
    instrument_id_b=link_instrument.id,
    bar_type_a=str(avax_bar_type),
    bar_type_b=str(link_bar_type),
    min_bars=360,
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
