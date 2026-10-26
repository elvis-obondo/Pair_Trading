"""HL-MASTER1 G8 raw pass: per coin-minute order-book summary from the archive l2Book snapshots.

    python -u build8_l2.py YYYYMMDD OUT_DIR [--coins coins.csv] [--hours 0-23]

Source s3://hyperliquid-archive/market_data/{YYYYMMDD}/{H}/l2Book/{COIN}.lz4 (requester pays). One line per snapshot (~0.55 s apart): outer "time" (receive time) and
raw.data = {coin, time (exchange ms), levels: [bids (best first), asks (best first)]}, 20 levels per side.

Row = (coin, minute m) = the snapshot with the MINIMUM exchange time in minute m (label m = floor(exchange ms / 60000)). A feature read for "the last minute before t0" is the snapshot taken at
the start of that minute, which is before t0. Columns (float32, NaN when the book side is empty or the quantity is beyond the 20 levels):
  mid, spread_bp, snap_off_s (seconds into the minute), crossed (1 when best bid >= best ask: then every other quantity of the row is NaN),
  bid_d{10,25,50}, ask_d{10,25,50}   USD (price x size) of levels within that many bp of mid, per side
  trunc_bid_{10,25,50}, trunc_ask_{10,25,50}  1 when the 20th level is still inside the band, so the depth is a lower bound
  imb_{10,25,50}   (bid_d - ask_d) / (bid_d + ask_d), NaN when both are 0
  book_reach_{bid,ask}_bp  bp from mid to the last stored level per side (the continuous version of the trunc flags)
  slip_buy_1k, slip_sell_1k  bp versus mid of the average fill price to buy / sell $1,000 (no position will exceed $1k; user 2026-10-25), walking the levels (NaN when the 20 levels hold less)
Also writes {day}_l2_index.parquet: one row per (coin, hour) file found, with the snapshots in it, non-monotone steps, gap median / max (ms), crossed rows, and the minutes with a row (so a missing file is not a missing book).
"""
import os, sys, time, subprocess, tempfile
import numpy as np
import pandas as pd
import orjson

BUCKET = "hyperliquid-archive"
BANDS = (10, 25, 50)
SLIPS = (1_000.0,)
COLS = (["mid", "spread_bp", "snap_off_s", "crossed"] + [f"{s}_d{b}" for s in ("bid", "ask") for b in BANDS] + [f"trunc_{s}_{b}" for s in ("bid", "ask") for b in BANDS]
        + [f"imb_{b}" for b in BANDS] + ["slip_buy_1k", "slip_sell_1k", "book_reach_bid_bp", "book_reach_ask_bp"])


def side_arrays(lv):
    px = np.array([float(x["px"]) for x in lv])
    sz = np.array([float(x["sz"]) for x in lv])
    return px, sz


def slip(px, sz, mid, usd, buy):
    if len(px) == 0:
        return np.nan
    cum = np.cumsum(px * sz)
    if cum[-1] < usd:
        return np.nan
    k = int(np.searchsorted(cum, usd))
    prev = cum[k - 1] if k > 0 else 0.0
    base = (sz[:k].sum() + (usd - prev) / px[k])
    avg = usd / base
    return ((avg / mid - 1.0) if buy else (1.0 - avg / mid)) * 1e4


def snap_row(d, off_s):
    bids, asks = d["levels"]
    out = dict.fromkeys(COLS, np.nan)
    out["snap_off_s"] = off_s
    if not bids or not asks:
        return out
    bp, bs = side_arrays(bids)
    ap, a_s = side_arrays(asks)
    if not bp[0] < ap[0]:                            # locked or crossed book: mid, spread and slippage are meaningless -> flagged, everything else NaN
        out["crossed"] = 1.0
        return out
    out["crossed"] = 0.0
    mid = 0.5 * (bp[0] + ap[0])
    out["mid"] = mid
    out["spread_bp"] = (ap[0] - bp[0]) / mid * 1e4
    dist_b = (mid - bp) / mid * 1e4
    dist_a = (ap - mid) / mid * 1e4
    for b in BANDS:
        db = float((bp * bs)[dist_b <= b].sum())
        da = float((ap * a_s)[dist_a <= b].sum())
        out[f"bid_d{b}"], out[f"ask_d{b}"] = db, da
        out[f"trunc_bid_{b}"] = float(len(bp) >= 20 and dist_b[-1] <= b)
        out[f"trunc_ask_{b}"] = float(len(ap) >= 20 and dist_a[-1] <= b)
        out[f"imb_{b}"] = (db - da) / (db + da) if db + da > 0 else np.nan
    out["book_reach_bid_bp"], out["book_reach_ask_bp"] = float(dist_b[-1]), float(dist_a[-1])      # bp from mid to the 20th (last stored) level: how far the stored book reaches
    for u, nm in zip(SLIPS, ("1k",)):
        out[f"slip_buy_{nm}"] = slip(ap, a_s, mid, u, True)
        out[f"slip_sell_{nm}"] = slip(bp, bs, mid, u, False)
    return out


def hour_file(path):
    """(rows, stats) for one hour file. Row per exchange minute = the snapshot with the MINIMUM exchange time in that minute (not the first line, in case a file is not sorted).
    stats = (n_snapshots, n_nonmonotone, median_gap_ms, max_gap_ms, n_crossed)."""
    raw = subprocess.run(["lz4", "-dc", path], capture_output=True, check=True).stdout
    lines = [ln for ln in raw.split(b"\n") if ln]
    ms = np.empty(len(lines), np.int64)
    for k, ln in enumerate(lines):
        i = ln.find(b'"time":', 40)                  # the exchange time inside raw.data (the outer "time" is a string and sits before position 40)
        ms[k] = int(ln[i + 7:i + 20])
    gaps = np.diff(ms)
    nonmono = int((gaps < 0).sum())
    mins = ms // 60000
    order = np.lexsort((np.arange(len(ms)), ms))     # by exchange time, ties by line order
    seen, rows, ncross = set(), [], 0
    for k in order:
        m = int(mins[k])
        if m in seen:
            continue
        seen.add(m)
        d = orjson.loads(lines[k])["raw"]["data"]
        r = snap_row(d, (ms[k] - m * 60000) / 1000.0)
        r["minute"] = m
        ncross += int(r["crossed"] == 1.0)
        rows.append(r)
    stats = (len(lines), nonmono, float(np.median(gaps)) if len(gaps) else np.nan, float(gaps.max()) if len(gaps) else np.nan, ncross)
    return rows, stats


def main():
    day = sys.argv[1]
    out_dir = sys.argv[2]
    coins_csv = sys.argv[sys.argv.index("--coins") + 1] if "--coins" in sys.argv else None
    hrs = range(24)
    if "--hours" in sys.argv:
        a, b = sys.argv[sys.argv.index("--hours") + 1].split("-")
        hrs = range(int(a), int(b) + 1)
    wanted = set(pd.read_csv(coins_csv)["coin"]) if coins_csv else None
    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-2"))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    frames, index = [], []
    tmp = tempfile.mkdtemp()
    nbytes = 0
    for h in hrs:
        pre = f"market_data/{day}/{h}/l2Book/"
        keys = []
        for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=pre, RequestPayer="requester"):
            keys += [(o["Key"], o["Size"]) for o in pg.get("Contents", [])]
        for key, size in keys:
            coin = key.rsplit("/", 1)[1][:-4]
            if wanted is not None and coin not in wanted:
                continue
            p = os.path.join(tmp, "f.lz4")
            s3.download_file(BUCKET, key, p, ExtraArgs={"RequestPayer": "requester"})
            nbytes += size
            try:
                rows, st = hour_file(p)
            except Exception as e:
                print(f"  FAIL {key}: {e}", flush=True)
                index.append((coin, h, size, -1, 0, -1, np.nan, np.nan, -1))
                continue
            index.append((coin, h, size, st[0], len(rows), st[1], st[2], st[3], st[4]))
            if rows:
                df = pd.DataFrame(rows)
                df.insert(0, "coin", coin)
                frames.append(df)
        print(f"  hour {h}: {len(keys)} files [{time.time() - t0:.0f}s]", flush=True)
    if frames:
        D = pd.concat(frames, ignore_index=True)
        D["minute"] = D["minute"].astype(np.int64)
        # (a) one row per (coin, minute) per day: a minute can appear in two hour files (a snapshot stamped in the next hour sits in this hour's file); keep the MINIMUM exchange time.
        D["_t"] = D["minute"] * 60 + D["snap_off_s"].astype(np.float64)
        D = D.sort_values(["coin", "minute", "_t"], kind="stable")
        dup = int(D.duplicated(["coin", "minute"]).sum())
        D = D.drop_duplicates(["coin", "minute"], keep="first").drop(columns="_t").reset_index(drop=True)
        # (b) every label inside the UTC day; rows outside (spillover from a neighbouring day's hour file) are dropped and counted: that day's own files carry those minutes
        d0 = int(pd.Timestamp(day).value // 10**9 // 60)
        inside = (D["minute"] >= d0) & (D["minute"] < d0 + 1440)
        spill = int((~inside).sum())
        D = D[inside].reset_index(drop=True)
        assert not D.duplicated(["coin", "minute"]).any()
        print(f"  [L2 {day}] duplicate (coin, minute) rows resolved (minimum exchange time kept): {dup:,}; rows outside the day dropped: {spill:,}", flush=True)
        for c in COLS:
            D[c] = D[c].astype(np.float32) if c != "mid" else D[c].astype(np.float64)
        D.to_parquet(os.path.join(out_dir, f"{day}_l2.parquet"), index=False)
    pd.DataFrame(index, columns=["coin", "hour", "bytes", "n_snapshots", "n_minutes", "n_nonmonotone", "gap_median_ms", "gap_max_ms", "n_crossed"]).to_parquet(os.path.join(out_dir, f"{day}_l2_index.parquet"), index=False)
    print(f"[L2 {day}] {len(index)} files, {nbytes / 1e9:.2f} GB compressed, {sum(len(f) for f in frames):,} coin-minutes [{time.time() - t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
