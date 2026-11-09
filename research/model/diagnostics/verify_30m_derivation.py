import os, sys
import numpy as np
import pandas as pd

BUILD2_CACHE = "/Users/elvisobondo/Pair_Trading/research/model/logs/profit1/build2_1m_cache"
LOCAL_30M = "/Users/elvisobondo/Pair_Trading/user_data/data/hyperliquid/futures"

coins = sorted(c[:-len("-1m.feather")] for c in os.listdir(BUILD2_CACHE) if c.endswith("-1m.feather"))
total_bars = 0
total_match = 0
total_mismatch = 0
coin_mismatches = []

for coin in coins:
    f1m = os.path.join(BUILD2_CACHE, f"{coin}-1m.feather")
    f30 = os.path.join(LOCAL_30M, f"{coin}-30m.feather")
    if not os.path.exists(f30):
        continue
    d1 = pd.read_feather(f1m, columns=["date", "close"])
    d1["date"] = pd.to_datetime(d1["date"], utc=True)
    s1 = d1.set_index("date")["close"]
    d30 = pd.read_feather(f30, columns=["date", "close"])
    d30["date"] = pd.to_datetime(d30["date"], utc=True)
    # derive: close_30m[H] = close_1m[H+29]
    derived = s1.reindex(d30["date"] + pd.Timedelta(minutes=29)).to_numpy()
    actual = d30["close"].to_numpy()
    n = len(actual)
    match = np.array_equal(derived, actual, equal_nan=True)
    # count elementwise too
    eq = (derived == actual) | (np.isnan(derived) & np.isnan(actual))
    n_match = int(eq.sum())
    total_bars += n
    total_match += n_match
    total_mismatch += (n - n_match)
    if n_match != n:
        coin_mismatches.append((coin, n - n_match, n))

print(f"coins checked: {len(coins)}")
print(f"total 30m bars compared: {total_bars:,}")
print(f"exact matches: {total_match:,}")
print(f"mismatches: {total_mismatch:,}")
print("coins with any mismatch:", coin_mismatches[:20])
