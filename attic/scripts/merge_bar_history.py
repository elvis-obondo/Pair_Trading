#!/usr/bin/env python3
"""Merges a ticker's full local canonical OHLCV history with whatever partial
history a cloud VM has already accumulated live, producing a single feather
file ready to drop into the VM's paper_live/ cache.

Why this exists: DataObserver (nautilus/data_cache.py) prefers local history
over an OKX backfill request, but OKX's historical-bar request caps at 300
candles and DataObserver never issues a follow-up request to fill the rest.
A pair switch on a VM with no local cache therefore gets stuck at ~300 bars,
short of the 720 MIN_BARS needs, and has to wait ~8 days accumulating bars
one at a time from the live feed before the strategy can evaluate its first
signal. See docs/CLOUD_DEPLOY.md for the full incident writeup. The laptop
never hit this because it always had the full canonical dataset on disk;
scripts/check_vm.sh switch uses this script to give the VM the same head
start.

Usage: merge_bar_history.py TICKER CANONICAL_FEATHER VM_PAPER_LIVE_FEATHER_OR_EMPTY OUTPUT_FEATHER
  CANONICAL_FEATHER: path to user_data/data/okx/futures/{ticker}_USDT_USDT-30m-futures.feather
                      (may not exist -- not every ticker is guaranteed to be downloaded)
  VM_PAPER_LIVE_FEATHER_OR_EMPTY: path to a pulled-down copy of the VM's existing
                      paper_live cache for this ticker, or "" if there isn't one
  OUTPUT_FEATHER: where to write the merged result
"""
import sys
from pathlib import Path

import pandas as pd

ticker, canonical_path, vm_path, out_path = sys.argv[1:5]

frames = []
if Path(canonical_path).exists():
    frames.append(pd.read_feather(canonical_path)[["date", "open", "high", "low", "close", "volume"]])
if vm_path and Path(vm_path).exists():
    frames.append(pd.read_feather(vm_path))

if not frames:
    print(f"{ticker}: no local canonical history and no existing VM cache -- "
          f"nothing to merge, OKX's capped cold-start backfill will apply "
          f"(expect a ~1-week wait before this pair can evaluate a signal)")
    sys.exit(1)

merged = (
    pd.concat(frames, ignore_index=True)
    .drop_duplicates(subset="date", keep="last")
    .sort_values("date")
    .reset_index(drop=True)
)
merged.to_feather(out_path)
print(f"{ticker}: merged {len(merged)} bars ({merged['date'].min()} -> {merged['date'].max()}) -> {out_path}")
