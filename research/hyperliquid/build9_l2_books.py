"""COSTS1 extractor: for a list of (coin, UTC hour) archive files and the minutes wanted from each, keep the raw 20-level book of the snapshot with the minimum exchange time
inside every wanted minute, so any order size can be walked offline.

    python -u build9_l2_books.py TARGETS.parquet OUT_DIR [--workers N] [--shard K/M] [--limit L] [--flush F] [--local DIR] [--max-bytes B] [--max-seconds S]
    python -u build9_l2_books.py --merge OUT_DIR

TARGETS.parquet = research/model/logs/costs1/l2_targets_priority.parquet (columns coin, day 'YYYYMMDD', hour, minutes = epoch minutes floor(exchange ms / 60000), n_minutes).
Source s3://hyperliquid-archive/market_data/{day}/{hour}/l2Book/{COIN}.lz4 (requester pays; us-east-1; run from the laptop or from EC2 in us-east-2, the account's SCP denies us-east-1 EC2).
With --local DIR the files are read from DIR/{day}/{hour}/{COIN}.lz4 instead (used by the self-test; no AWS).

Per file: lz4 -dc, find the exchange time of every line (as build8_l2.py), group by minute, and for each WANTED minute that has at least one snapshot take the snapshot with the MINIMUM
exchange time (ties: earliest line) and parse only that line. One output row per (coin, minute) PER FILE READ (a boundary minute can come from two hour files because the folder hour is the node's receive clock); `--merge OUT_DIR`
then writes books_all.parquet with ONE row per (coin, minute): the lowest snap_off_s over the files that supplied it (asserted unique), and prints, for the boundary minutes
(minute of hour 0, 1, 58, 59), which folder hour supplied the minimum (own hour / previous / next) so the direction of the folder lag is settled by data.
  coin, src_day, src_hour (the folder that held the row), minute, snap_off_s (seconds into the minute), n_bid, n_ask (levels stored, <= 20), crossed (best bid >= best ask),
  bid_px[20], bid_sz[20], ask_px[20], ask_sz[20]   (float64, best first, NaN padded; sz in coin units, as the archive stores it)
Also writes one index row per file: coin, day, hour, bytes, n_snapshots, n_wanted, n_found, n_nonmonotone, status ('ok' | 'missing' | 'fail:<reason>'), so a missing file or minute is
counted, never silent. Resume: shards are written every --flush files as books_{shard}_{part}.parquet and index_{shard}_{part}.parquet; a rerun skips files already in an index.

Circuit breakers (standing rule): an exclusive lock on OUT_DIR/.lock (a second process refuses to start), --max-seconds (wall clock; flush and stop), --max-bytes (cumulative downloaded
bytes; flush and stop). Output goes to OUT_DIR only (planned: research/model/logs/costs1/l2_books/, untracked, an estimated 0.3 to 1 GB parquet for the full list; free disk is about 20 GB);
each downloaded file is deleted right after parsing.

Nothing here decides a cost or a fill: it only copies books. Throttle: each worker keeps one boto3 client; no retry beyond boto3's default (a failed file is an index row with status fail).
"""
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd
import orjson

BUCKET = "hyperliquid-archive"
NL = 20


def arrs(levels):
    px = np.full(NL, np.nan)
    sz = np.full(NL, np.nan)
    k = min(len(levels), NL)
    for i in range(k):
        px[i] = float(levels[i]["px"])
        sz[i] = float(levels[i]["sz"])
    return px, sz, k


_S3 = None


def s3():
    global _S3
    if _S3 is None:
        import boto3
        _S3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    return _S3


def one_file(job):
    coin, day, hour, minutes, local = job
    want = set(minutes)
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "f.lz4")
    nbytes = 0
    try:
        if local:
            path = os.path.join(local, day, str(hour), f"{coin}.lz4")
            if not os.path.exists(path):
                return coin, day, hour, [], dict(bytes=0, n_snapshots=0, n_wanted=len(want), n_found=0, n_nonmonotone=0, status="missing")
            nbytes = os.path.getsize(path)
        else:
            key = f"market_data/{day}/{hour}/l2Book/{coin}.lz4"
            try:
                s3().download_file(BUCKET, key, path, ExtraArgs={"RequestPayer": "requester"})
            except Exception as e:                      # a missing key is a 404; anything else is a failure
                msg = str(e)
                st = "missing" if ("404" in msg or "Not Found" in msg) else "fail:" + msg[:80]
                return coin, day, hour, [], dict(bytes=0, n_snapshots=0, n_wanted=len(want), n_found=0, n_nonmonotone=0, status=st)
            nbytes = os.path.getsize(path)
        raw = subprocess.run(["lz4", "-dc", path], capture_output=True, check=True).stdout
        lines = [ln for ln in raw.split(b"\n") if ln]
        ms = np.empty(len(lines), np.int64)
        for k, ln in enumerate(lines):
            i = ln.find(b'"time":', 40)                 # exchange time inside raw.data; the outer "time" is a string before position 40
            ms[k] = int(ln[i + 7:i + 20])
        mins = ms // 60000
        nonmono = int((np.diff(ms) < 0).sum())
        order = np.lexsort((np.arange(len(ms)), ms))
        best = {}
        for k in order:
            m = int(mins[k])
            if m in want and m not in best:
                best[m] = k
        rows = []
        for m, k in best.items():
            d = orjson.loads(lines[k])["raw"]["data"]
            bids, asks = d["levels"]
            bp, bs, nb = arrs(bids)
            ap, a_s, na = arrs(asks)
            crossed = float(nb > 0 and na > 0 and not bp[0] < ap[0])
            rows.append(dict(coin=coin, src_day=day, src_hour=hour, minute=m, snap_off_s=(ms[k] - m * 60000) / 1000.0, n_bid=nb, n_ask=na, crossed=crossed, bid_px=bp, bid_sz=bs, ask_px=ap, ask_sz=a_s))
        return coin, day, hour, rows, dict(bytes=nbytes, n_snapshots=len(lines), n_wanted=len(want), n_found=len(best), n_nonmonotone=nonmono, status="ok")
    except Exception as e:
        return coin, day, hour, [], dict(bytes=nbytes, n_snapshots=0, n_wanted=len(want), n_found=0, n_nonmonotone=0, status="fail:" + repr(e)[:80])
    finally:
        try:
            if not local and os.path.exists(path):
                os.remove(path)
            os.rmdir(tmp)
        except OSError:
            pass


def flush(out_dir, shard, part, rows, index):
    if rows:
        pd.DataFrame(rows).to_parquet(os.path.join(out_dir, f"books_{shard}_{part:04d}.parquet"), index=False)
    pd.DataFrame(index).to_parquet(os.path.join(out_dir, f"index_{shard}_{part:04d}.parquet"), index=False)


def merge(out_dir):
    fs = sorted(f for f in os.listdir(out_dir) if f.startswith("books_") and f != "books_all.parquet")
    B = pd.concat([pd.read_parquet(os.path.join(out_dir, f)) for f in fs], ignore_index=True)
    day_h = (pd.to_datetime(B["src_day"], format="%Y%m%d", utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(hours=1)
    own = (B["minute"] // 60) - (day_h + B["src_hour"].astype(int))
    B["src_rel_hour"] = (-own).astype(int)             # folder hour minus the minute's own hour: 0 own, -1 previous folder, +1 next folder
    n0 = len(B)
    B = B.sort_values(["coin", "minute", "snap_off_s"], kind="stable")
    dup = int(B.duplicated(["coin", "minute"]).sum())
    bd = B[(B["minute"] % 60).isin([0, 1, 58, 59])]
    rel = bd.groupby(["coin", "minute"])["src_rel_hour"].apply(lambda s: tuple(sorted(set(s)))).value_counts().to_dict()
    B = B.drop_duplicates(["coin", "minute"], keep="first").reset_index(drop=True)
    assert not B.duplicated(["coin", "minute"]).any()
    kept = B[(B["minute"] % 60).isin([0, 1, 58, 59])]["src_rel_hour"].value_counts().to_dict()
    B.to_parquet(os.path.join(out_dir, "books_all.parquet"), index=False)
    print(f"[B9 MERGE] {len(fs)} shard files, {n0:,} rows, {dup:,} duplicate (coin, minute) rows dropped (lowest snap_off_s kept), {len(B):,} unique rows")
    print(f"[B9 MERGE] boundary minutes (minute of hour 0, 1, 58, 59): folders that held each (coin, minute) as sets of (folder hour - own hour): {rel}")
    print(f"[B9 MERGE] boundary minutes, folder that supplied the kept (minimum) snapshot, folder hour - own hour: {kept}")
    print(f"[B9 MERGE] snap_off_s over all kept rows: median {B['snap_off_s'].median():.2f}, p90 {B['snap_off_s'].quantile(0.9):.2f}, max {B['snap_off_s'].max():.2f}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--merge":
        return merge(args[1])
    targets, out_dir = args[0], args[1]
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    workers, flush_n, limit = int(opt("--workers", 8)), int(opt("--flush", 2000)), opt("--limit")
    k_, m_ = (int(x) for x in opt("--shard", "0/1").split("/"))
    local = opt("--local")
    max_bytes, max_seconds = float(opt("--max-bytes", "inf")), float(opt("--max-seconds", "inf"))
    shard = f"{k_}of{m_}"
    os.makedirs(out_dir, exist_ok=True)
    import fcntl
    lock = open(os.path.join(out_dir, ".lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("[B9] another build9 process holds the lock on this OUT_DIR; refusing to start")
    T = pd.read_parquet(targets)
    T = T.iloc[k_::m_].reset_index(drop=True)
    if limit:
        T = T.iloc[:int(limit)]
    done = set()
    for f in os.listdir(out_dir):
        if f.startswith(f"index_{shard}_"):
            ix = pd.read_parquet(os.path.join(out_dir, f))
            done |= set(zip(ix["coin"], ix["day"], ix["hour"]))
    part = len([f for f in os.listdir(out_dir) if f.startswith(f"index_{shard}_")])
    jobs = [(r.coin, r.day, int(r.hour), list(r.minutes), local) for r in T.itertuples() if (r.coin, r.day, int(r.hour)) not in done]
    print(f"[B9] shard {shard}: {len(T):,} files in the shard, {len(jobs):,} to do (resume skipped {len(T) - len(jobs):,}), workers {workers}", flush=True)
    t0 = time.time()
    rows, index, n, total_bytes, stop_why = [], [], 0, 0, None
    with Pool(workers) as pool:
        for coin, day, hour, r, st in pool.imap_unordered(one_file, jobs, chunksize=4):
            rows += r
            index.append(dict(coin=coin, day=day, hour=hour, **st))
            n += 1
            total_bytes += st["bytes"]
            if total_bytes > max_bytes or time.time() - t0 > max_seconds:
                stop_why = f"cap reached: {total_bytes / 1e9:.2f} GB downloaded (cap {max_bytes / 1e9:.2f}), {time.time() - t0:.0f}s (cap {max_seconds:.0f})"
                pool.terminate()
                break
            if len(index) >= flush_n:
                flush(out_dir, shard, part, rows, index)
                part += 1
                rows, index = [], []
                print(f"[B9] {n:,}/{len(jobs):,} files [{time.time() - t0:.0f}s]", flush=True)
    if index:
        flush(out_dir, shard, part, rows, index)
    print(f"[B9] {'STOPPED: ' + stop_why if stop_why else 'done'} {n:,} files, {total_bytes / 1e9:.3f} GB compressed downloaded, in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
