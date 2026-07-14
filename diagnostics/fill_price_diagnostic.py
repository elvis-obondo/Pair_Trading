"""
Diagnostic: Cross-instrument fill-price defect in Nautilus Trader 1.228.0

Hypothesis: submitting two market orders as a single OrderList routes both
through the first instrument's matching engine, so the second leg fills at
the first instrument's price rather than its own.

Two instruments with non-overlapping price ranges are constructed so any
mis-routing produces an unambiguous wrong number. Run 1 uses a grouped
OrderList (same as production). If the bug reproduces, Run 2 repeats the
identical setup with two independent submit_order() calls so the only
changed variable is the submission method.

Creates no output files. Imports nothing from this project.
"""

from decimal import Decimal

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import CacheConfig, StrategyConfig
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.currencies import USDT, BTC, ETH
from nautilus_trader.model.enums import (
    AccountType,
    AggregationSource,
    BarAggregation,
    OmsType,
    OrderSide,
    PriceType,
)
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.trading.strategy import Strategy

# ---------------------------------------------------------------------------
# Price constants — ranges are disjoint by 38 points; no value satisfies both
# ---------------------------------------------------------------------------
A_BASE = 100.0
B_BASE = 50.0
A_RANGE = (90.0, 110.0)
B_RANGE = (40.0, 60.0)

# 2024-01-01 00:00:00 UTC in nanoseconds
_T0_NS = 1_704_067_200_000_000_000
_HOUR_NS = 3_600_000_000_000


# ---------------------------------------------------------------------------
# Instrument / bar helpers
# ---------------------------------------------------------------------------

def _make_instruments(venue: Venue):
    """Return (instr_a, instr_b) mirroring run_backtest.py field-for-field."""
    common = dict(
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
    instr_a = CryptoPerpetual(
        instrument_id=InstrumentId(Symbol("DIAG-A-USDT-SWAP"), venue),
        raw_symbol=Symbol("DIAG-A-USDT-SWAP"),
        base_currency=BTC,
        **common,
    )
    instr_b = CryptoPerpetual(
        instrument_id=InstrumentId(Symbol("DIAG-B-USDT-SWAP"), venue),
        raw_symbol=Symbol("DIAG-B-USDT-SWAP"),
        base_currency=ETH,
        **common,
    )
    return instr_a, instr_b


def _make_bar_type(instrument: CryptoPerpetual) -> BarType:
    return BarType(
        instrument_id=instrument.id,
        bar_spec=BarSpecification(1, BarAggregation.HOUR, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )


def _make_bars(instrument: CryptoPerpetual, bar_type: BarType, base_price: float, n: int = 8):
    """
    Build n bars whose OHLCV all sit firmly inside [base_price-2, base_price+2].
    Timestamps match across both instruments bar-for-bar (same T0 + i*HOUR).
    """
    prec = instrument.price_precision
    bars = []
    for i in range(n):
        ts = _T0_NS + i * _HOUR_NS
        bar = Bar(
            bar_type=bar_type,
            open=Price(base_price + 1.0, prec),
            high=Price(base_price + 2.0, prec),
            low=Price(base_price - 1.0, prec),
            close=Price(base_price + 0.5, prec),
            volume=Quantity(100.0, instrument.size_precision),
            ts_event=ts,
            ts_init=ts,
        )
        bars.append(bar)
    return bars


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

class DiagnosticStrategyConfig(StrategyConfig, frozen=True):
    instrument_id_a: InstrumentId
    instrument_id_b: InstrumentId
    bar_type_a: str
    bar_type_b: str
    use_order_list: bool = True


class DiagnosticStrategy(Strategy):
    """
    Fires exactly one trade on the first synchronized bar pair, then records
    every fill price keyed by instrument ID string.
    """

    def __init__(self, config: DiagnosticStrategyConfig):
        super().__init__(config)
        self._fired: bool = False
        self._fills: dict[str, float] = {}

    def on_start(self) -> None:
        self._bar_type_a = BarType.from_str(self.config.bar_type_a)
        self._bar_type_b = BarType.from_str(self.config.bar_type_b)
        self.subscribe_bars(self._bar_type_a)
        self.subscribe_bars(self._bar_type_b)

    def on_bar(self, bar: Bar) -> None:
        if self._fired:
            return
        bars_a = self.cache.bars(self._bar_type_a)
        bars_b = self.cache.bars(self._bar_type_b)
        if bars_a and bars_b:
            self._fired = True
            if self.config.use_order_list:
                self._submit_grouped()
            else:
                self._submit_separate()

    def _submit_grouped(self) -> None:
        order_a = self.order_factory.market(
            instrument_id=self.config.instrument_id_a,
            order_side=OrderSide.BUY,
            quantity=Quantity.from_str("1.0"),
        )
        order_b = self.order_factory.market(
            instrument_id=self.config.instrument_id_b,
            order_side=OrderSide.SELL,
            quantity=Quantity.from_str("1.0"),
        )
        order_list = self.order_factory.create_list([order_a, order_b])
        self.submit_order_list(order_list)

    def _submit_separate(self) -> None:
        order_a = self.order_factory.market(
            instrument_id=self.config.instrument_id_a,
            order_side=OrderSide.BUY,
            quantity=Quantity.from_str("1.0"),
        )
        order_b = self.order_factory.market(
            instrument_id=self.config.instrument_id_b,
            order_side=OrderSide.SELL,
            quantity=Quantity.from_str("1.0"),
        )
        self.submit_order(order_a)
        self.submit_order(order_b)

    def on_order_filled(self, event) -> None:
        self._fills[str(event.instrument_id)] = float(event.last_px)


# ---------------------------------------------------------------------------
# Engine builder
# ---------------------------------------------------------------------------

def run_diagnostic(use_order_list: bool) -> dict[str, float]:
    """
    Build a fresh engine, run it, return {instrument_id_str: fill_price}.
    Two independent calls produce independent results with no shared state.
    """
    venue = Venue("OKX")
    instr_a, instr_b = _make_instruments(venue)
    bar_type_a = _make_bar_type(instr_a)
    bar_type_b = _make_bar_type(instr_b)
    bars_a = _make_bars(instr_a, bar_type_a, A_BASE)
    bars_b = _make_bars(instr_b, bar_type_b, B_BASE)

    engine_config = BacktestEngineConfig(
        trader_id="DIAG-001",
        cache=CacheConfig(bar_capacity=100),
    )
    engine = BacktestEngine(config=engine_config)

    engine.add_venue(
        venue=venue,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USDT,
        starting_balances=[Money(10_000, USDT)],
    )
    engine.add_instrument(instr_a)
    engine.add_instrument(instr_b)
    engine.add_data(bars_a, sort=False)
    engine.add_data(bars_b, sort=False)
    engine.sort_data()

    strategy = DiagnosticStrategy(
        config=DiagnosticStrategyConfig(
            strategy_id="DIAG-STRAT-001",
            instrument_id_a=instr_a.id,
            instrument_id_b=instr_b.id,
            bar_type_a=str(bar_type_a),
            bar_type_b=str(bar_type_b),
            use_order_list=use_order_list,
        )
    )
    engine.add_strategy(strategy)
    engine.run()

    return strategy._fills


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _in_range(px: float, lo: float, hi: float) -> bool:
    return lo <= px <= hi


def analyze(fills: dict[str, float], label: str, id_a: str, id_b: str) -> tuple[bool, bool]:
    """
    Print a per-leg fill summary and return (a_correct, b_correct).
    'correct' means the leg filled within its own declared price range.
    """
    print(f"\n{'='*62}")
    print(f"  RUN: {label}")
    print(f"{'='*62}")

    def _report_leg(leg: str, instr_id: str, fill_range, other_range):
        lo, hi = fill_range
        o_lo, o_hi = other_range
        if instr_id not in fills:
            print(f"  Leg {leg}  ({instr_id})")
            print(f"    fill_px : NO FILL RECORDED — order did not execute")
            return False
        px = fills[instr_id]
        own_ok = _in_range(px, lo, hi)
        other_ok = _in_range(px, o_lo, o_hi)
        status = (
            "CORRECT (filled in own range)"
            if own_ok
            else f"BUG — filled in Instrument {'A' if leg == 'B' else 'B'}'s range"
            if other_ok
            else f"UNEXPECTED — in neither range"
        )
        print(f"  Leg {leg}  ({instr_id})")
        print(f"    fill_px : {px:.4f}")
        print(f"    own range [{lo}, {hi}]  →  {status}")
        return own_ok

    a_ok = _report_leg("A", id_a, A_RANGE, B_RANGE)
    b_ok = _report_leg("B", id_b, B_RANGE, A_RANGE)

    if a_ok and b_ok:
        verdict = "VERDICT: CORRECT — both legs filled in their own price ranges."
    elif not b_ok and a_ok:
        verdict = "VERDICT: BUG REPRODUCED — Leg B filled at Instrument A's price."
    elif not a_ok and b_ok:
        verdict = "VERDICT: BUG REPRODUCED — Leg A filled at Instrument B's price (unexpected direction)."
    else:
        verdict = "VERDICT: BOTH LEGS WRONG — neither leg filled in its own range."

    print(f"\n  {verdict}")
    return a_ok, b_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\nDIAGNOSTIC: Cross-instrument fill-price defect")
    print(f"  Instrument A  DIAG-A-USDT-SWAP  prices near {A_BASE}  (expected range {A_RANGE})")
    print(f"  Instrument B  DIAG-B-USDT-SWAP  prices near {B_BASE}  (expected range {B_RANGE})")

    # Derive the expected instrument ID strings from the constants used in run_diagnostic
    venue = Venue("OKX")
    _ia, _ib = _make_instruments(venue)
    ID_A = str(_ia.id)
    ID_B = str(_ib.id)

    # --- RUN 1: grouped OrderList (same as production strategy) ---
    fills1 = run_diagnostic(use_order_list=True)
    a1_ok, b1_ok = analyze(fills1, "OrderList (grouped — production pattern)", ID_A, ID_B)
    bug_in_run1 = not b1_ok

    if not bug_in_run1:
        print("\n" + "="*62)
        print("  FINAL CONCLUSION: Bug NOT reproduced with OrderList submission.")
        print("  The cross-instrument fill-price hypothesis is REFUTED.")
        print("  Do not run the second variation — investigate data or signal logic instead.")
        print("="*62)
    else:
        # --- RUN 2: separate submit_order calls (controlled variation) ---
        fills2 = run_diagnostic(use_order_list=False)
        a2_ok, b2_ok = analyze(fills2, "Separate (independent submit_order calls)", ID_A, ID_B)

        print("\n" + "="*62)
        print("  BISECT CONCLUSION")
        print("="*62)
        if bug_in_run1 and b2_ok:
            print("  Run 1 (OrderList):  BUG — Leg B filled at wrong price.")
            print("  Run 2 (Separate ):  CORRECT — Leg B filled at own price.")
            print()
            print("  >> OrderList routing is CONFIRMED as the cause of the defect.")
            print("  >> Switching to two independent submit_order() calls should fix it.")
        elif bug_in_run1 and not b2_ok:
            print("  Run 1 (OrderList):  BUG — Leg B filled at wrong price.")
            print("  Run 2 (Separate ):  BUG — Leg B still filled at wrong price.")
            print()
            print("  >> OrderList is EXONERATED.")
            print("  >> Both submission modes reproduce the defect.")
            print("  >> Root cause lies in instrument/venue/matching-engine construction,")
            print("     not in how orders are grouped. Redirect investigation there.")
        else:
            print("  Unexpected result pattern — check per-leg details above.")
        print("="*62)
