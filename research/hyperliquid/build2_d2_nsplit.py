"""HL-BUILD2 D2 diagnostic (existing data only): close match by the candle's trade count.

If the close mismatch is the tie order of same-millisecond fills, minutes whose
candle has ONE trade (n = 1) must match ~100% and the match must fall as n grows.
If n = 1 minutes mismatch too, the cause is something else (label, price source).
Also: when our close differs, is it equal to the candle's high or low (a
different trade of the same minute) or neither (a different price)?
"""
import json, os, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from adapters.hyperliquid_futures import HL_FUTURES_DIR

API = "https://api.hyperliquid.xyz/info"
R = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "d2_candle_check.csv"))


def candles(coin, start, end):
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1m",
                       "startTime": int(start.timestamp() * 1000), "endTime": int(end.timestamp() * 1000)}}).encode()
    for k in range(8):                                  # the API rate-limits (HTTP 429): back off
        try:
            with urllib.request.urlopen(urllib.request.Request(API, body, {"Content-Type": "application/json"}), timeout=30) as r:
                rows = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == 7: raise
            time.sleep(5 * (k + 1))
    d = pd.DataFrame({"c": [float(x["c"]) for x in rows], "h": [float(x["h"]) for x in rows],
                      "l": [float(x["l"]) for x in rows], "n": [int(x["n"]) for x in rows]},
                     index=pd.to_datetime([x["t"] for x in rows], unit="ms", utc=True))
    return d[~d.index.duplicated()]


out = []
end = pd.Timestamp("2026-10-14", tz="UTC")
for coin in R.coin:
    b = pd.read_feather(HL_FUTURES_DIR / f"{coin}-1m.feather").set_index("date")
    c = candles(coin, end - pd.Timedelta(days=4), end); time.sleep(1.0)
    j = b.join(c, how="inner"); j = j[np.isfinite(j.close) & (j.n > 0)]
    j["match"] = j.close == j.c
    j["nb"] = pd.cut(j.n, [0, 1, 5, 10**9], labels=["n=1", "n=2-5", "n>5"])
    j["is_hl"] = ~j.match & ((j.close == j.h) | (j.close == j.l))
    j["in_range"] = ~j.match & (j.close <= j.h) & (j.close >= j.l)
    out.append(j[["nb", "match", "is_hl", "in_range"]].assign(coin=coin))
X = pd.concat(out)
print(f"[NSPLIT] {X.coin.nunique()} coins, {len(X):,} traded minutes compared")
print(X.groupby("nb", observed=True).agg(minutes=("match", "size"), close_match=("match", "mean")).to_string())
mm = X[~X.match]
print(f"\n[MISMATCH] {len(mm):,} minutes: our close == candle high or low {100*mm.is_hl.mean():.1f}%; "
      f"within the candle's [low, high] {100*mm.in_range.mean():.1f}%; outside the range {100*(~mm.in_range).mean():.1f}%")
per = X[X.nb == "n=1"].groupby("coin").match.mean()
print(f"[N=1 per coin] close_match p0 {per.min():.4f}  p5 {per.quantile(.05):.4f}  p50 {per.median():.4f}")
