"""HL-BUILD1 B0: what instant does an asset_ctxs row stamped T describe?

Gate before any bar is built. Hyperliquid's candle API (last ~5,000 1m candles
per coin) is the reference: each candle is labelled by its OPEN time t and its
close `c` is the last trade price at t+1m.

MEASURE. For each coin, m[T] = mid_px of the asset_ctxs row stamped T, and
c[t] = close of the 1m candle opened at t. Log returns over one minute,
r_m[T] = ln m[T] - ln m[T-1m] and r_c[t] = ln c[t] - ln c[t-1m], each only where
both minutes exist (no return spans a hole). Then corr(r_m[T], r_c[T+L]) for
L in -2..+2 minutes. Best L = argmax correlation.

  L = -1  ->  row T is the state at T, i.e. the close of the 1m bar labelled T-1m
  L =  0  ->  row T is the close of the bar labelled T (state at T+1m)

DECISION RULE (from the brief, fixed before the run): the same best L for all of
BTC, ETH, SOL, HYPE, DOGE -> use it to set the label (row T goes to the bar
labelled T+L). Coins disagree -> STOP and report.

GAP-FILL (stated before running). The brief asks for "the most recent full day
of asset_ctxs". Every day inside the candle window (2026-10-11..14) is partial in
the archive (build1_raw_coverage.log: 20261012 = 00:00-10:52, 20261013 =
00:00-06:42); the last full day, 20261003, is outside the window. So the test
uses every asset_ctxs minute of 20261012 and 20261013 that the candle window
covers. The rule is unchanged.
"""
import io, json, os, subprocess, sys, time, urllib.request
import numpy as np, pandas as pd

CACHE = os.path.expanduser("~/.cache/hl_asset_ctxs")
DAYS = ["20261012", "20261013"]
COINS = ["BTC", "ETH", "SOL", "HYPE", "DOGE"]
LAGS = range(-2, 3)
API = "https://api.hyperliquid.xyz/info"


def ctx_mid(day):
    raw = subprocess.run(["lz4", "-dc", os.path.join(CACHE, f"{day}.csv.lz4")],
                         check=True, capture_output=True).stdout
    d = pd.read_csv(io.BytesIO(raw), usecols=["time", "coin", "mid_px"])
    d = d[d.coin.isin(COINS)]
    d["time"] = pd.to_datetime(d.time, utc=True)
    return d


def candles(coin, start, end):
    body = json.dumps({"type": "candleSnapshot",
                       "req": {"coin": coin, "interval": "1m",
                               "startTime": int(start.timestamp() * 1000),
                               "endTime": int(end.timestamp() * 1000)}}).encode()
    req = urllib.request.Request(API, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.load(r)
    c = pd.Series([float(x["c"]) for x in rows],
                  index=pd.to_datetime([x["t"] for x in rows], unit="ms", utc=True))
    return c[~c.index.duplicated()].sort_index()


def minute_returns(s):
    """ln-returns on a full minute grid; NaN wherever either minute is missing."""
    g = pd.date_range(s.index.min(), s.index.max(), freq="1min")
    v = np.log(s.reindex(g))
    return v.diff()


ctx = pd.concat([ctx_mid(d) for d in DAYS])
print(f"[INFO] asset_ctxs {DAYS}: {ctx.time.nunique()} stamps, "
      f"{ctx.time.min()} -> {ctx.time.max()}", flush=True)
best = {}
for coin in COINS:
    m = ctx[ctx.coin == coin].set_index("time").mid_px.sort_index()
    c = candles(coin, m.index.min() - pd.Timedelta("10min"), m.index.max() + pd.Timedelta("10min"))
    time.sleep(0.5)
    if not (c.index.min() <= m.index.min() and c.index.max() >= m.index.max()):
        print(f"  !!! CANDLES DO NOT COVER THE ctx SPAN: candles {c.index.min()} -> {c.index.max()}, "
              f"ctx {m.index.min()} -> {m.index.max()}")
    rm, rc = minute_returns(m), minute_returns(c)
    cov = rm.index.intersection(rc.index)
    print(f"\n{coin}: ctx minutes {len(m)}, candles {len(c)} "
          f"({c.index.min()} -> {c.index.max()}), overlap {len(cov)}")
    out = {}
    for L in LAGS:
        x = rm
        y = rc.reindex(rm.index + pd.Timedelta(minutes=L))
        y.index = rm.index
        ok = x.notna() & y.notna()
        out[L] = (np.corrcoef(x[ok], y[ok])[0, 1], int(ok.sum()))
        print(f"  L={L:+d}  corr {out[L][0]:+.4f}  n {out[L][1]}")
    best[coin] = max(out, key=lambda k: out[k][0])
    r = sorted((v[0] for v in out.values()), reverse=True)
    print(f"  best L = {best[coin]:+d}   margin over second-best {r[0]-r[1]:.4f}   n {out[best[coin]][1]}")

print(f"\n[B0] best lag per coin: {best}")
if len(set(best.values())) == 1:
    L = next(iter(best.values()))
    print(f"[B0] PASS: all 5 agree on L={L:+d}. Row stamped T -> 1m bar labelled T{L:+d}m.")
else:
    print("[B0] STOP: coins disagree on the best lag.")
    sys.exit(2)
