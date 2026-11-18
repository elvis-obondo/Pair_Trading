"""COSTS1: extract the G8 L2-summary rows needed by the cost analysis from the daily tables in S3. Runs on a small EC2 in ap-northeast-1 (the bucket's own region, no egress cost).

    python -u costs_g8_extract.py TARGETS.parquet OUT_PARQUET [--bucket B] [--prefix build8/full] [--region R] [--workdir DIR]

TARGETS.parquet = research/model/logs/costs1/l2_targets_priority.parquet (coin, day, hour, minutes[epoch minutes]). The wanted set is the UNION of its (coin, minute) pairs: every minute of the entry window
[t0-1, t0+15] and the exit window [exit-1, exit+15] of both legs of the priority trades. A minute belongs to the G8 daily file of its own UTC day (the G8 builder keeps only rows inside the day).
For each day: `aws s3 cp s3://B/PREFIX/{day}_l2.parquet`, keep rows whose (coin, minute) is wanted, delete the file. Output: one parquet with the G8 columns for the wanted rows, plus a log line per day with
n wanted, n found; a day file that is missing is printed and counted, never silent. Nothing is modelled here.
"""
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

args = sys.argv[1:]
targets, out = args[0], args[1]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
bucket = opt("--bucket", "pair-trading-hl-289869684922")
prefix = opt("--prefix", "build8/full")
region = opt("--region", "ap-northeast-1")
work = opt("--workdir", "/tmp/g8x")
os.makedirs(work, exist_ok=True)
T = pd.read_parquet(targets)
pairs = pd.DataFrame({"coin": np.repeat(T["coin"].to_numpy(), T["n_minutes"].to_numpy()), "minute": np.concatenate([np.asarray(m, dtype=np.int64) for m in T["minutes"]])})
assert len(pairs) == int(T["n_minutes"].sum()), "exploded minutes list does not match the sum of n_minutes"
pairs = pairs.drop_duplicates()
pairs["day"] = pd.to_datetime(pairs["minute"] * 60, unit="s", utc=True).dt.strftime("%Y%m%d")
print(f"[G8X] wanted (coin, minute) pairs {len(pairs):,}; days {pairs['day'].nunique()}; coins {pairs['coin'].nunique()}", flush=True)
t0 = time.time()
frames, n_missing, tot_found = [], 0, 0
for k, (day, g) in enumerate(pairs.groupby("day")):
    p = os.path.join(work, f"{day}_l2.parquet")
    r = subprocess.run(["aws", "s3", "cp", f"s3://{bucket}/{prefix}/{day}_l2.parquet", p, "--region", region, "--only-show-errors"], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(p):
        n_missing += 1
        print(f"[G8X] {day}: day file MISSING or failed ({r.stderr.strip()[:120]}); wanted {len(g):,}; cause of every missing minute: day file missing", flush=True)
        continue
    d = pd.read_parquet(p)
    m = d.merge(g[["coin", "minute"]], on=["coin", "minute"], how="inner")
    assert not m.duplicated(["coin", "minute"]).any(), f"{day}: duplicate (coin, minute) in the G8 table"
    frames.append(m)
    tot_found += len(m)
    os.remove(p)
    print(f"[G8X] {day}: wanted {len(g):,}, found {len(m):,}, missing {len(g) - len(m):,} (cause: minute absent from an existing day file) [{time.time() - t0:.0f}s]", flush=True)
D = pd.concat(frames, ignore_index=True)
D.to_parquet(out, index=False)
print(f"[G8X] done: days with a missing file {n_missing}; wanted {len(pairs):,}, found {tot_found:,} ({tot_found / len(pairs):.2%}); wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB) in {time.time() - t0:.0f}s", flush=True)
