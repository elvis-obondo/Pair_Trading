"""Validate the universe data layer.

Run: python research/validate_universe_panel.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from universe_panel import (
    load_panel, tradeable_pairs, usable_tickers, price_precision, panel_precisions,
    drop_forming_bars, FACTOR_ONLY, _base_symbol,
)
from rolling_spread import min_bars_required

n_pass = n_fail = 0


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':56s} {detail[:30]:32s} {'PASS' if ok else 'FAIL'}")


print("=" * 104)
print("1. align=False keeps the history; align=True would destroy it")
print("=" * 104)
# drop_forming_bars, not load_panel() raw: the newest bar is only present for
# whichever instruments have ticked into it since it opened, and leaving it in
# takes the universe from 22,366 pairs to 2,775. The section at the bottom tests
# that behaviour directly; every section above it needs a closed panel to assert
# against at all.
panel = drop_forming_bars(load_panel())
check("unaligned panel loaded", len(panel) > 0, f"{panel.shape[0]}x{panel.shape[1]}")
# 214 columns, 212 tradeable: BTC and ETH are carried for factor construction
# only (universe_panel.FACTOR_ONLY) and never formed into a pair. The pair
# count below is C(212,2), so it doubles as the test that the guard holds.
check("214 tickers", panel.shape[1] == 214, f"{panel.shape[1]}")
check("212 of them tradeable",
      len([c for c in panel.columns if _base_symbol(c) not in FACTOR_ONLY]) == 212,
      f"{len([c for c in panel.columns if _base_symbol(c) not in FACTOR_ONLY])}")
check("spans well over a year", len(panel) > 500 * 48, f"{len(panel)/48:.0f} days")

# The trap, demonstrated rather than asserted in a comment: the frame-wide
# dropna that align=True performs.
aligned_rows = int(panel.dropna(how="any").shape[0])
check("align=True would collapse the panel",
      aligned_rows < len(panel) * 0.2,
      f"{aligned_rows/48:.0f}d of {len(panel)/48:.0f}d")
newest = panel.notna().idxmax().sort_values().iloc[-1]
check("one late listing sets that intersection", True, str(newest.date()))

print()
print("=" * 104)
print("2. Pair enumeration")
print("=" * 104)
tk = usable_tickers(panel.tail(min_bars_required(0.5)))
pairs = tradeable_pairs(tk)
check("22,366 pairs from the 212 tradeable", len(pairs) == 22366, f"{len(pairs):,}")
check("no pair repeats", len(set(pairs)) == len(pairs), f"{len(set(pairs)):,} unique")
check("no self-pairs", all(a != b for a, b in pairs))
check("unordered (no (b,a) duplicate of an (a,b))",
      not (set(pairs) & {(b, a) for a, b in pairs}))
# The _base_symbol exclusion: dormant today, must still work.
check("same-underlying pairs excluded",
      len(tradeable_pairs(["ARB", "ARB_SPOT", "SOL"])) == 2,
      str(tradeable_pairs(["ARB", "ARB_SPOT", "SOL"])))

print()
print("=" * 104)
print("3. usable_tickers screens out short/gappy legs")
print("=" * 104)
need = min_bars_required(0.5)
tail = panel.tail(need)
check("tail tickers all have a complete window",
      all(tail[t].notna().sum() == need for t in tk), f"{len(tk)} usable")
check("a panel shorter than one requirement yields nothing",
      usable_tickers(panel.tail(need - 1)) == [], "empty")

print()
print("=" * 104)
print("4. Per-ticker precision — the bug that zeroed five tickers")
print("=" * 104)
prec = panel_precisions(panel)
zeroed = []
for t in ("BONK", "PEPE", "SHIB", "FLOKI", "NEIRO", "HMSTR", "API3", "BNB"):
    if t not in panel.columns:
        continue
    v = panel[t].to_numpy(dtype=float)
    mn = float(np.exp(v[np.isfinite(v)].min()))
    p, inc = prec[t]
    survives = round(mn, p) > 0
    old_survives = round(mn, 4) > 0       # the hardcoded price_precision=4
    if not old_survives:
        zeroed.append(t)
    print(f"    {t:6s} min={mn:.3e}  precision {p:2d} (tick {inc:.0e})  "
          f"survives new={survives}  survives old(4dp)={old_survives}")
    check(f"  {t} does not round to zero", survives, f"round={round(mn, p):.3e}")
check("the old hardcoded 4dp DID zero some tickers", len(zeroed) > 0,
      ",".join(zeroed))

check("precision is clamped to a sane range",
      all(2 <= p <= 12 for p, _ in prec.values()),
      f"{min(p for p,_ in prec.values())}..{max(p for p,_ in prec.values())}")
check("degenerate price falls back safely", price_precision(0.0) == (8, 1e-8))
check("NaN price falls back safely", price_precision(float('nan')) == (8, 1e-8))

print()
print("=" * 104)
print("5. Forming bars are dropped before the tail is taken")
print("=" * 104)

# A 30-minute bar stamped 14:00 closes at 14:30. Download at 14:27 and the
# exchange returns that bar only for instruments that have ticked into it so far
# -- 75 of 212, measured on 2026-09-12. Two failures at once: the other 137 lose
# their complete 671-bar tail and drop out (22,366 pairs -> 2,775), and the 75
# that survive are screened on a close price that is not a close. The first is
# loud once you look at the pair count; the second is invisible.
idx = pd.date_range("2026-09-01", periods=40, freq="30min")
full = pd.DataFrame(np.random.randn(40, 20).cumsum(axis=0), index=idx,
                    columns=[f"T{i}" for i in range(20)])
partial = full.copy()
partial.iloc[-1, 5:] = np.nan          # only 5 of 20 ticked into the last bar

trimmed = drop_forming_bars(partial)
check("the forming bar is dropped", len(trimmed) == 39, f"{len(trimmed)} rows")
check("the last kept bar is the closed one", trimmed.index[-1] == idx[-2],
      str(trimmed.index[-1])[-8:])
check("every ticker is restored", trimmed.iloc[-1].notna().all(), "20/20")
check("a fully populated panel is untouched", len(drop_forming_bars(full)) == 40,
      f"{len(drop_forming_bars(full))} rows")

two = partial.copy()
two.iloc[-2, 5:] = np.nan
check("two consecutive partial bars both go", len(drop_forming_bars(two)) == 38,
      f"{len(drop_forming_bars(two))} rows")

# A delisting removes a column outright rather than punching a hole in one bar,
# so coverage compared against recent neighbours must not read it as partial.
delisted = full.copy()
delisted.iloc[:, 19] = np.nan
check("a delisted instrument does not trigger trimming",
      len(drop_forming_bars(delisted)) == 40, f"{len(drop_forming_bars(delisted))} rows")
check("a one-row panel is returned as-is",
      len(drop_forming_bars(full.iloc[:1])) == 1, "1 row")

# The live panel, which is what actually broke.
check("the live panel yields the full universe once trimmed",
      len(tradeable_pairs(usable_tickers(panel.tail(min_bars_required(0.5))))) == 22366,
      f"{len(tradeable_pairs(usable_tickers(panel.tail(min_bars_required(0.5))))):,} pairs")

print()
print("=" * 104)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 104)
sys.exit(1 if n_fail else 0)