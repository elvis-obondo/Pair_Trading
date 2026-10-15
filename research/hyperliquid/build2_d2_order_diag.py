"""HL-BUILD2 D2 diagnostic: tie-break by tid (D1) vs by execution order (seq), one day.

Usage: python build2_d2_order_diag.py TID_DAY.parquet SEQ_DAY.parquet
Both are stage-1 outputs for 2026-10-13: TID from D1 (tie-break tid), SEQ from
the rerun with the execution-order tie-break. Compared on the minutes where a
candle exists with n > 0 and stage 1 has an on-book bar (the raw per-minute
close; no hole on this day, so rule (iii) does not enter).

DECISION RULE (planner, 2026-10-15): if SEQ gives >= 99% close matches for
>= 95% of coins, the tie-break becomes execution order and stages 1 + 2 rerun for
the whole window; otherwise STOP and report both match rates.
"""
import json, sys, time, urllib.error, urllib.request
import numpy as np, pandas as pd

API = "https://api.hyperliquid.xyz/info"
tid = pd.read_parquet(sys.argv[1]); seq = pd.read_parquet(sys.argv[2])
day0 = pd.Timestamp("2026-10-13", tz="UTC"); day1 = day0 + pd.Timedelta(days=1)


def candles(coin):
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1m",
                       "startTime": int(day0.timestamp() * 1000), "endTime": int(day1.timestamp() * 1000)}}).encode()
    for k in range(8):                                  # the API rate-limits (HTTP 429): back off
        try:
            with urllib.request.urlopen(urllib.request.Request(API, body, {"Content-Type": "application/json"}), timeout=30) as r:
                rows = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == 7: raise
            time.sleep(5 * (k + 1))
    d = pd.DataFrame({"c": [float(x["c"]) for x in rows], "o": [float(x["o"]) for x in rows],
                      "v": [float(x["v"]) for x in rows], "n": [int(x["n"]) for x in rows]},
                     index=pd.to_datetime([x["t"] for x in rows], unit="ms", utc=True))
    return d[~d.index.duplicated()]


rows = []; cov = []
coins = sorted(set(tid.coin) & set(seq.coin))
print(f"[ORDER] coins in both day files {len(coins)} (TID {tid.coin.nunique()}, SEQ {seq.coin.nunique()}); D2 compared 178")
for c in coins:
    k = candles(c); time.sleep(1.0)
    if len(k):
        cov.append((k.index.min(), k.index.max()))
        # the API keeps the newest ~5,000 minutes: the whole day must still be in it
        assert k.index.min() <= day0 + pd.Timedelta(minutes=30) and k.index.max() >= day1 - pd.Timedelta(minutes=30), (c, k.index.min(), k.index.max())  # 30-min slack: a thin coin may lack the edge minutes; truncation would cut hours
    k = k[(k.index >= day0) & (k.index < day1) & (k.n > 0)]
    a = tid[tid.coin == c].set_index("minute"); b = seq[seq.coin == c].set_index("minute")
    j = k.join(a[["open", "close", "volume"]], how="inner").join(b[["open", "close"]].add_suffix("_seq"), how="inner")
    if not len(j): continue
    rows.append((c, len(j), (j.close == j.c).mean(), (j.close_seq == j.c).mean(),
                 (j.open == j.o).mean(), (j.open_seq == j.o).mean(),
                 (np.abs(j.volume - j.v) <= 0.005 * j.v).mean()))
R = pd.DataFrame(rows, columns=["coin", "minutes", "close_tid", "close_seq", "open_tid", "open_seq", "volume"])
print(f"[ORDER] candle coverage: min {min(a for a, _ in cov)} .. {max(a for a, _ in cov)}; max {min(b for _, b in cov)} .. {max(b for _, b in cov)}")
R.to_csv("research/hyperliquid/logs/build2_d2_order_diag.csv", index=False)
q = lambda s: "  ".join(f"p{p} {s.quantile(p/100):.4f}" for p in (0, 5, 50))
print(f"[ORDER] 2026-10-13, {len(R)} coins, median {R.minutes.median():.0f} traded minutes")
for col in ("close_tid", "close_seq", "open_tid", "open_seq", "volume"):
    print(f"  {col:10s} {q(R[col])}   coins >= 99%: {int((R[col] >= .99).sum())} of {len(R)}")
ok = (R.close_seq >= .99).mean()
print(f"[ORDER] GATE (seq): {int((R.close_seq >= .99).sum())} of {len(R)} coins ({100*ok:.1f}%) >= 99% close match; need >= 95%")
print("[ORDER] PASS" if ok >= .95 else "[ORDER] STOP")
print(R[R.close_seq < .99].sort_values("close_seq").head(20).to_string(index=False))
