"""HL-BUILD2 D2: trade-built 1m bars vs Hyperliquid's own (trade-based) candles. Gate.

For every coin still listed (it trades in the bars' last day), over the overlap
of the candle API window (~5,000 1m candles back from now) and our bars:
  close_match  = share of 1m bars whose close == the candle close exactly
  volume_match = share whose volume is within 0.5% of the candle volume
compared on minutes where the candle exists and our close is finite. A candle
row is labelled by its open time `t`, the same convention as our bars.

DECISION RULE (from the brief, fixed before the run): close_match >= 99% for at
least 95% of coins -> PASS; else STOP and report. Every coin below 99% is listed.
"""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from adapters.hyperliquid_futures import HL_FUTURES_DIR

API = "https://api.hyperliquid.xyz/info"
COIN_GATE, SHARE_GATE, VOL_TOL = 0.99, 0.95, 0.005


def candles(coin, start, end):
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1m",
                       "startTime": int(start.timestamp() * 1000), "endTime": int(end.timestamp() * 1000)}}).encode()
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(API, body, {"Content-Type": "application/json"}), timeout=30) as r:
                rows = json.load(r)
            break
        except Exception as e:
            time.sleep(2 + 3 * k); err = e
    else:
        raise SystemExit(f"[ABORT] candle API failed for {coin}: {err}")
    if not rows:
        return pd.DataFrame(columns=["c", "v", "n"])
    d = pd.DataFrame({"c": [float(x["c"]) for x in rows], "v": [float(x["v"]) for x in rows],
                      "n": [int(x["n"]) for x in rows]},
                     index=pd.to_datetime([x["t"] for x in rows], unit="ms", utc=True))
    return d[~d.index.duplicated()].sort_index()


files = sorted(HL_FUTURES_DIR.glob("*-1m.feather"))
last = max(pd.read_feather(f, columns=["date"]).date.max() for f in files)
day0 = last.floor("D")
now = pd.Timestamp.now(tz="UTC")
print(f"[INFO] {len(files)} coins with 1m bars; bars end {last}; now {now}", flush=True)
rows = []
for f in files:
    coin = f.name[: -len("-1m.feather")]
    b = pd.read_feather(f).set_index("date")
    if b.index.max() < day0:
        continue                                   # not listed at the bars' end
    c = candles(coin, now - pd.Timedelta(days=4), last + pd.Timedelta(minutes=1)); time.sleep(0.25)
    j = b.join(c, how="inner")
    j = j[np.isfinite(j.close)]
    if not len(j):
        rows.append((coin, 0, np.nan, np.nan, np.nan, None, None, str(c.index.min()) if len(c) else None,
                     str(c.index.max()) if len(c) else None)); continue
    cm = float((j.close == j.c).mean())
    vm = float((np.abs(j.volume - j.v) <= VOL_TOL * j.v.abs().clip(lower=1e-12)).mean())
    traded = j.n > 0
    cmt = float((j.close[traded] == j.c[traded]).mean()) if traded.any() else np.nan
    rows.append((coin, len(j), cm, vm, cmt, str(j.index.min()), str(j.index.max()), str(c.index.min()), str(c.index.max())))
R = pd.DataFrame(rows, columns=["coin", "minutes", "close_match", "volume_match", "close_match_traded", "from", "to",
                              "candle_min", "candle_max"])
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "d2_candle_check.csv")
R.to_csv(out, index=False)
ok = R.close_match >= COIN_GATE
print(f"[D2] coins compared {len(R)}; minutes per coin median {R.minutes.median():.0f}; window {R['from'].min()} -> {R['to'].max()}")
print(f"[D2] candles returned: min {R.candle_min.min()} .. {R.candle_min.max()};  max {R.candle_max.min()} .. {R.candle_max.max()}  (overlap must reach {last})")
print("[D2] close_match quantiles: " + "  ".join(f"p{int(q*100)} {R.close_match.quantile(q):.4f}" for q in (0, .05, .5)))
print("[D2] volume_match quantiles: " + "  ".join(f"p{int(q*100)} {R.volume_match.quantile(q):.4f}" for q in (0, .05, .5)))
print(f"[D2] coins below {COIN_GATE:.0%} close match:")
print(R[~ok].sort_values("close_match").to_string(index=False))
print(f"[D2] GATE: {int(ok.sum())} of {len(R)} coins ({100*ok.mean():.1f}%) have >= {COIN_GATE:.0%} matching closes; need >= {SHARE_GATE:.0%}")
if ok.mean() < SHARE_GATE:
    print("[D2] STOP"); sys.exit(2)
print("[D2] PASS")
