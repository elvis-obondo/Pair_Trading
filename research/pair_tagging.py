"""
Pair-type tagging: derives a `pair_type` label for a (ticker_a, ticker_b)
pair from each leg's instrument_type in manifest.json, so a screening
run's survivors can be grouped by pair_type downstream (e.g. "are
cointegration hits concentrated in basis-affected spot_perp pairs, or
clean spot_spot ones?").

Pure metadata: this module does NOT touch cointegration/OU/screening
math, and is not called from pair_analysis.py's math path. It's the
honesty instrument for the deferred interpretation step.

Basis note: a spot_perp pair carries embedded SPOT-PERP BASIS in its
spread (funding-rate-driven divergence between an instrument's spot price
and its own or a related perpetual futures price). This is a real
economic effect layered on top of any genuine mean reversion, not a bug --
but it means a spot_perp cointegration hit should not be read the same way
as a spot_spot one until basis is separately accounted for. Hence tagging
it, not filtering it out (mixed pairs are allowed by design -- see
research/adapters/okx_spot.py).
"""
import json
from pathlib import Path

VALID_INSTRUMENT_TYPES = {"spot", "futures", "lst"}

# Canonical pair_type label components and their ordering priority.
# Concatenation order is spot < perp(futures) < lst, e.g.:
#   spot+futures -> "spot_perp" (not "perp_spot")
#   futures+futures -> "perp_perp"
#   spot+spot -> "spot_spot"
_LABEL = {"spot": "spot", "futures": "perp", "lst": "lst"}
_PRIORITY = {"spot": 0, "futures": 1, "lst": 2}


def load_instrument_types(manifest_path: Path) -> dict[str, str]:
    """Read manifest.json and return {ticker: instrument_type}.

    Tickers with no instrument_type recorded (e.g. a manifest written by
    an adapter version that predates this field) are omitted -- callers
    should treat a missing entry as "unknown", not silently assume a type.
    """
    if not manifest_path.exists():
        return {}
    with open(manifest_path) as f:
        manifest = json.load(f)
    return {
        ticker: info["instrument_type"]
        for ticker, info in manifest.items()
        if "instrument_type" in info
    }


def derive_pair_type(instrument_type_a: str, instrument_type_b: str) -> str:
    """Derive a pair_type label from two legs' instrument types.

    Order-independent: derive_pair_type("spot", "futures") ==
    derive_pair_type("futures", "spot") == "spot_perp".

    Returns one of: spot_spot, spot_perp, perp_perp, spot_lst, perp_lst,
    lst_lst.

    Raises
    ------
    ValueError
        If either instrument_type is not one of {"spot", "futures", "lst"}.
    """
    for t in (instrument_type_a, instrument_type_b):
        if t not in VALID_INSTRUMENT_TYPES:
            raise ValueError(
                f"Unknown instrument_type {t!r}; expected one of {sorted(VALID_INSTRUMENT_TYPES)}"
            )
    ordered = sorted([instrument_type_a, instrument_type_b], key=lambda t: _PRIORITY[t])
    return "_".join(_LABEL[t] for t in ordered)


def tag_pairs(pairs: list[tuple[str, str]], instrument_types: dict[str, str]) -> list[dict]:
    """Attach a pair_type to each (ticker_a, ticker_b) pair.

    Parameters
    ----------
    pairs : list of (ticker_a, ticker_b) tuples, e.g. from
        itertools.combinations(tickers, 2) as pair_analysis.py builds.
    instrument_types : {ticker: instrument_type}, e.g. from
        load_instrument_types().

    Returns
    -------
    list of dicts: {"ticker_a", "ticker_b", "pair_type"}. A pair with
    either leg missing from `instrument_types` gets pair_type=None rather
    than raising -- the manifest and the live universe can legitimately
    drift out of sync (partial re-syncs, tests), and that shouldn't crash
    a screening run.
    """
    tagged = []
    for a, b in pairs:
        type_a = instrument_types.get(a)
        type_b = instrument_types.get(b)
        pair_type = None if (type_a is None or type_b is None) else derive_pair_type(type_a, type_b)
        tagged.append({"ticker_a": a, "ticker_b": b, "pair_type": pair_type})
    return tagged
