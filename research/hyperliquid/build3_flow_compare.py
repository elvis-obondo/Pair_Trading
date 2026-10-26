"""HL-FLOW1 Part 0: the regenerated flow table against the HL-BUILD2 one.

Usage: python build3_flow_compare.py OLD_FLOW_DIR NEW_FLOW_DIR OLD_FUT_DIR NEW_FUT_DIR
For every coin file:
  - every column the old flow file has is BIT-identical in the new one (float64,
    NaN == NaN, same dates, same row count);
  - the new columns open_buy_usd, open_sell_usd, close_buy_usd, close_sell_usd
    exist, and on every non-NaN row open_buy + open_sell == open_taker_usd and
    close_buy + close_sell == close_taker_usd (rtol 1e-9, atol 1e-6 USD: the two
    sides are summed in a different grouping), and are NaN exactly where
    open_taker_usd is NaN;
  - the 1m and 30m bar files are bit-identical to the old ones (same code, same
    tie-break; nothing in the bars may change).
Exits 2 on any difference.
"""
import os, sys
import numpy as np, pandas as pd

old, new, fold, fnew = sys.argv[1:5]
NEW = ["open_buy_usd", "open_sell_usd", "close_buy_usd", "close_sell_usd"]
files = sorted(f for f in os.listdir(old) if f.endswith(".parquet"))
assert files == sorted(f for f in os.listdir(new) if f.endswith(".parquet")), "coin sets differ"
bad, rows, maxerr = [], 0, 0.0
for f in files:
    a = pd.read_parquet(os.path.join(old, f)); b = pd.read_parquet(os.path.join(new, f))
    if len(a) != len(b) or not a["date"].equals(b["date"]):
        bad.append((f, "dates/rows")); continue
    rows += len(a)
    for c in a.columns:
        x, y = a[c].to_numpy(), b[c].to_numpy()
        same = np.array_equal(x, y, equal_nan=True) if x.dtype.kind == "f" else np.array_equal(x, y)
        if not same:
            bad.append((f, c))
    assert all(c in b.columns for c in NEW), f"{f}: new columns missing"
    for t, p, q in (("open_taker_usd", "open_buy_usd", "open_sell_usd"), ("close_taker_usd", "close_buy_usd", "close_sell_usd")):
        tot = b[t].to_numpy(float); s = b[p].to_numpy(float) + b[q].to_numpy(float)
        assert np.array_equal(np.isnan(tot), np.isnan(s)), f"{f}: {p}/{q} NaN pattern differs from {t}"
        m = np.isfinite(tot)
        assert np.allclose(s[m], tot[m], rtol=1e-9, atol=1e-6), f"{f}: {p}+{q} != {t}"
        maxerr = max(maxerr, float(np.abs(s[m] - tot[m]).max()) if m.any() else 0.0)
nb = 0
for f in sorted(os.listdir(fold)):
    if not f.endswith(".feather"): continue
    a = pd.read_feather(os.path.join(fold, f)); b = pd.read_feather(os.path.join(fnew, f)); nb += 1
    if not a.equals(b):
        bad.append((f, "bars"))
assert nb == len([f for f in os.listdir(fnew) if f.endswith(".feather")]), "bar file sets differ"
print(f"[FLOWCMP] {len(files)} coin flow files, {rows:,} rows: existing columns bit-identical except {len(bad)} differences")
print(f"[FLOWCMP] new columns present in all files; sum identities hold on every non-NaN row, max abs err {maxerr:.2e} USD")
print(f"[FLOWCMP] {nb} bar files compared (1m and 30m)")
for b_ in bad[:20]:
    print("  DIFF", b_)
sys.exit(2 if bad else 0)
