"""HL-TARGET2: slim copy of the G8 order-book table (coin, minute, mid, spread_bp, crossed) from S3, one file per day.
READ-ONLY on S3 (list + ranged column reads; no S3 write, no instance launch). Only the 5 needed columns of each day file are fetched (parquet column projection: the 5 columns are 12.9% of the compressed bytes
of the 11 local sample day files, so about 1.5 GB is transferred instead of 11.5 GB: ESTIMATE); the raw file is never written to disk, so there is nothing to delete.
Resumable: a day whose slim file exists is skipped. Needs the user's own yes for the data transfer.
Output: research/model/logs/s2/g8_slim/{day}.parquet and logs/s2/g8_slim_manifest.json (days, rows, bytes, sha256 of the sorted day list).
Usage: python s2_g8_slim.py [--dry]   (--dry lists the keys and prints the count and total size, downloads nothing)
"""
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import time

import boto3
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
OUT = os.path.join(MODEL, "logs", "s2", "g8_slim") + os.sep
BUCKET, PREFIX, REGION = "pair-trading-hl-289869684922", "build8/full/", "ap-northeast-1"
EXPECT_DAYS = 496    # DATASET_DICTIONARY.md G8 section: 496 day tables
COLS = ["coin", "minute", "mid", "spread_bp", "crossed"]


def log(m):
    print(m, flush=True)


def main():
    dry = "--dry" in sys.argv
    log(f"[G8SLIM] script sha256 {hashlib.sha256(open(__file__, 'rb').read()).hexdigest()[:12]}; s3://{BUCKET}/{PREFIX}; dry={dry}")
    s3 = boto3.client("s3", region_name=REGION)
    fs = pafs.S3FileSystem(region=REGION)
    keys = []
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIX):
        for o in pg.get("Contents", []):
            if o["Key"].endswith("_l2.parquet"):
                keys.append((o["Key"], o["Size"]))
    keys.sort()
    tot = sum(s for _, s in keys)
    log(f"[G8SLIM] day files in S3: {len(keys)} (expected {EXPECT_DAYS}); total {tot / 1e9:.2f} GB; first {keys[0][0]}, last {keys[-1][0]}")
    assert len(keys) == EXPECT_DAYS, f"expected {EXPECT_DAYS} day files, found {len(keys)}"
    if dry:
        return
    os.makedirs(OUT, exist_ok=True)
    todo = [(k, sz) for k, sz in keys if not os.path.exists(OUT + os.path.basename(k)[:8] + ".parquet")]
    log(f"[G8SLIM] already slimmed {len(keys) - len(todo)}; to do {len(todo)}")
    t0 = time.time()

    def work(ks):
        k, sz = ks
        day = os.path.basename(k)[:8]
        t = pq.read_table(f"{BUCKET}/{k}", columns=COLS, filesystem=fs)
        d = t.to_pandas()
        assert not d.duplicated(["coin", "minute"]).any(), f"{day}: duplicate (coin, minute)"
        d["crossed"] = (d["crossed"] == 1).astype("uint8")
        d["minute"] = d["minute"].astype("int32")
        d["spread_bp"] = d["spread_bp"].astype("float32")
        d["mid"] = d["mid"].astype("float64")
        pq.write_table(pa.Table.from_pandas(d[COLS], preserve_index=False), OUT + day + ".parquet.tmp", compression="zstd")
        os.replace(OUT + day + ".parquet.tmp", OUT + day + ".parquet")        # an interrupted write never leaves a truncated .parquet that the resume check would skip
        return day, len(d)

    done = 0
    with cf.ThreadPoolExecutor(4) as ex:
        for day, n in ex.map(work, todo):
            done += 1
            if done % 25 == 0 or done == len(todo):
                log(f"[G8SLIM] {done}/{len(todo)} days, last {day} ({n:,} rows), {time.time() - t0:.0f}s")
    files = sorted(f for f in os.listdir(OUT) if f.endswith(".parquet"))
    assert len(files) == EXPECT_DAYS, f"{len(files)} slim files, expected {EXPECT_DAYS}"
    rows = sum(pq.ParquetFile(OUT + f).metadata.num_rows for f in files)
    size = sum(os.path.getsize(OUT + f) for f in files)
    man = dict(days=len(files), first=files[0][:8], last=files[-1][:8], rows=rows, bytes=size, day_list_sha256=hashlib.sha256(",".join(f[:8] for f in files).encode()).hexdigest())
    json.dump(man, open(os.path.join(MODEL, "logs", "s2", "g8_slim_manifest.json"), "w"), indent=1)
    log(f"[G8SLIM] done: {man}; total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
