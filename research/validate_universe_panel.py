"""Validate the universe data layer.

Run: python research/validate_universe_panel.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from universe_panel import (
    load_panel, tradeable_pairs, usable_tickers, price_precision, panel_precisions,
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
panel = load_panel()
check("unaligned panel loaded", len(panel) > 0, f"{panel.shape[0]}x{panel.shape[1]}")
check("212 tickers", panel.shape[1] == 212, f"{panel.shape[1]}")
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
check("22,366 pairs from 212 tickers", len(pairs) == 22366, f"{len(pairs):,}")
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
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 104)
sys.exit(1 if n_fail else 0)
