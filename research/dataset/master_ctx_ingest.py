"""HL-MASTER1 shared raw pull: the asset_ctxs archive, one parquet per UTC day. No features here.

    python -u research/dataset/master_ctx_ingest.py > research/dataset/logs/master_ctx_ingest.log

SOURCE: s3://hyperliquid-archive/asset_ctxs/{YYYYMMDD}.csv.lz4 (us-east-1, requester-pays), 2023-05-20 .. 2026-10-23. Columns: time, coin, funding, open_interest, prev_day_px,
day_ntl_vlm, premium, oracle_px, mark_px, mid_px, impact_bid_px, impact_ask_px (one row per coin per snapshot). Nothing is filled or dropped; a day that is absent from the bucket is listed.
RUNS ON THE LAPTOP (the VM's S3 credentials cannot read hyperliquid-archive: 403): each day is downloaded, converted and uploaded to
s3://pair-trading-hl-289869684922/ctxs/{YYYYMMDD}.parquet (zstd; time as UTC datetime, coin as category) and deleted locally; _index.csv (date, rows, coins, first and last snapshot, snapshots) is uploaded too.
pt-research pulls them into research/datasets/ctxs/.
"""
import os, subprocess, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "research", "dislocation_model"))
import paths

OUT = os.path.join(os.environ.get("CTX_TMP", "/tmp/ctxs_tmp"))          # transient local folder (laptop); the parquet files go to S3 and are deleted locally
BUCKET = "s3://pair-trading-hl-289869684922/ctxs"
AWS = os.path.expanduser("~/.local/bin/aws") if os.path.exists(os.path.expanduser("~/.local/bin/aws")) else "aws"
FIRST, LAST = "2023-05-20", "2026-10-23"


def one(d):
    key = f"s3://hyperliquid-archive/asset_ctxs/{d}.csv.lz4"
    cmd = f"{AWS} s3 cp {key} - --request-payer requester --region us-east-1 --only-show-errors | lz4 -dc"
    p = subprocess.run(["bash", "-o", "pipefail", "-c", cmd], capture_output=True)
    if p.returncode != 0:
        return d, None, p.stderr.decode()[:200]
    import io
    df = pd.read_csv(io.BytesIO(p.stdout))
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["coin"] = df["coin"].astype("category")
    f = os.path.join(OUT, f"{d}.parquet")
    df.to_parquet(f, index=False, compression="zstd")
    u = subprocess.run([AWS, "s3", "cp", f, f"{BUCKET}/{d}.parquet", "--region", "ap-northeast-1", "--only-show-errors"], capture_output=True)
    os.remove(f)
    if u.returncode != 0:
        return d, None, "upload failed: " + u.stderr.decode()[:200]
    return d, (len(df), df.coin.nunique(), df.time.min(), df.time.max(), df.time.nunique()), ""


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    days = pd.date_range(FIRST, LAST, freq="D").strftime("%Y%m%d").tolist()
    rows, missing = [], []
    with Pool(int(os.environ.get("NPROC", 8))) as pool:
        for q, (d, info, err) in enumerate(pool.imap(one, days)):
            if info is None:
                missing.append((d, err))
            else:
                rows.append((d,) + info)
            if (q + 1) % 100 == 0:
                print(f"  {q + 1}/{len(days)} days  [{time.time() - t0:.0f}s]", flush=True)
    idx = pd.DataFrame(rows, columns=["date", "rows", "coins", "first", "last", "snapshots"])
    idx.to_csv(os.path.join(OUT, "_index.csv"), index=False)
    subprocess.run([AWS, "s3", "cp", os.path.join(OUT, "_index.csv"), f"{BUCKET}/_index.csv", "--region", "ap-northeast-1", "--only-show-errors"])
    print(f"[CTX] {len(idx)} of {len(days)} days downloaded; absent or failed: {len(missing)}  [{time.time() - t0:.0f}s]")
    for d, e in missing:
        print(f"  MISSING {d}: {e}")
    if len(idx):
        print(f"  rows total {idx.rows.sum():,}; coins per day min/median/max {idx.coins.min()} / {int(idx.coins.median())} / {idx.coins.max()}; snapshots per day min/median/max {idx.snapshots.min()} / {int(idx.snapshots.median())} / {idx.snapshots.max()}")
    low = idx[idx.snapshots < 0.9 * idx.snapshots.median()] if len(idx) else idx
    print(f"  days with < 90% of the median snapshot count: {len(low)}: " + ", ".join(f"{r.date}({r.snapshots})" for r in low.itertuples()))


if __name__ == "__main__":
    main()
