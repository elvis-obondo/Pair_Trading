"""HL-MASTER1 G7 raw pull: Hyperliquid's public fundingHistory (hourly funding rate and premium) for every coin, once, to S3. No features here. Runs on the laptop (internet).

    python -u research/dataset/master_funding.py > research/dataset/logs/master_funding.log

POST https://api.hyperliquid.xyz/info {"type":"fundingHistory","coin":C,"startTime":ms,"endTime":ms} -> up to 500 rows {coin, fundingRate, premium, time}; the row stamped at hour H reports the
hour that ENDED at H (so a feature at t0 uses the last row with time <= t0 and nothing later). Window pulled: 2025-05-15 (a week before the data window, for the 7-day means) to now, for every
coin in research/hyperliquid/coins.csv (234). Paged by the last returned time + 1 ms. Throttled with back-off on HTTP 429. Output: s3://pair-trading-hl-289869684922/fundinghist/{coin}.parquet
(time as UTC datetime, fundingRate, premium as float64) and _index.csv (coin, rows, first, last).
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error
import pandas as pd

AWS = os.path.expanduser("~/.local/bin/aws")
BUCKET = "s3://pair-trading-hl-289869684922/fundinghist"
START = int(pd.Timestamp("2025-05-15", tz="UTC").value // 10**6)


def post(body, tries=10):
    for k in range(tries):
        try:
            req = urllib.request.Request("https://api.hyperliquid.xyz/info", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except urllib.error.HTTPError as e:
            time.sleep(10 + 10 * k if e.code == 429 else 3 + 3 * k)
        except Exception:
            time.sleep(3 + 3 * k)
    raise RuntimeError(f"failed: {body}")


def pull(coin, end_ms):
    rows, start = [], START
    while start < end_ms:
        d = post({"type": "fundingHistory", "coin": coin, "startTime": start, "endTime": end_ms})
        if not d:
            break
        rows += d
        last = max(r["time"] for r in d)
        if last < start or len(d) < 500:
            break
        start = last + 1
        time.sleep(0.15)
    return rows


def main():
    t0 = time.time()
    coins = sorted(pd.read_csv("research/hyperliquid/coins.csv").coin)
    end_ms = int(pd.Timestamp.now(tz="UTC").value // 10**6)
    idx = []
    for i, c in enumerate(coins):
        rows = pull(c, end_ms)
        if rows:
            df = pd.DataFrame(rows)
            df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
            df["fundingRate"] = df.fundingRate.astype(float)
            df["premium"] = df.premium.astype(float)
            df = df.drop_duplicates("time").sort_values("time")[["time", "fundingRate", "premium"]]
            f = f"/tmp/fund_{c}.parquet"
            df.to_parquet(f, index=False)
            subprocess.run([AWS, "s3", "cp", f, f"{BUCKET}/{c}.parquet", "--region", "ap-northeast-1", "--only-show-errors"], check=True)
            os.remove(f)
            idx.append((c, len(df), df.time.min(), df.time.max()))
        else:
            idx.append((c, 0, None, None))
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(coins)} coins, {sum(r[1] for r in idx):,} rows  [{time.time() - t0:.0f}s]", flush=True)
    I = pd.DataFrame(idx, columns=["coin", "rows", "first", "last"])
    I.to_csv("/tmp/fund_index.csv", index=False)
    subprocess.run([AWS, "s3", "cp", "/tmp/fund_index.csv", f"{BUCKET}/_index.csv", "--region", "ap-northeast-1", "--only-show-errors"], check=True)
    print(f"[FUNDING] {int((I.rows > 0).sum())} of {len(I)} coins with rows, {I.rows.sum():,} rows in total; first {I['first'].min()}, last {I['last'].max()}; coins with no rows: " + ", ".join(I.coin[I.rows == 0]))
    print(f"  rows per coin: median {int(I.rows.median())}, max {int(I.rows.max())}  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
