"""COSTS1 receipt: synthetic self-test of build9_l2_books.py (no AWS). Builds two unsorted hour files in the archive's line format (outer string "time", raw.data = {coin, time, levels}),
runs the extractor in --local mode and the merge, and asserts: minimum-exchange-time snapshot per wanted minute, NaN padding to 20 levels, a boundary minute present in two folders ends as one
row with the lowest snap_off_s, a wanted minute without a snapshot is counted (n_found < n_wanted), a missing file is an index row with status 'missing'.

    python -u research/hyperliquid/build9_selftest.py > research/hyperliquid/logs/build9_selftest.log
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
import orjson
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
root = tempfile.mkdtemp()
base5 = int(pd.Timestamp("2026-08-01 05:00:00", tz="UTC").timestamp() * 1000)
base6 = base5 + 3600_000


def snap(t, bid, ask, nl=3):
    lv = [[{"px": str(bid - i * 0.01), "sz": "10", "n": 1} for i in range(nl)], [{"px": str(ask + i * 0.01), "sz": "20", "n": 1} for i in range(nl)]]
    return orjson.dumps({"time": "2026-08-01T05:00:00.1", "ver_num": 1, "raw": {"channel": "l2Book", "data": {"coin": "TST", "time": t, "levels": lv}}})


def write(hour, snaps):
    d = os.path.join(root, "20260801", str(hour))
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "TST.raw"), "wb").write(b"\n".join(snap(t, b, a) for t, b, a in snaps) + b"\n")
    subprocess.run(["lz4", "-q", "-f", os.path.join(d, "TST.raw"), os.path.join(d, "TST.lz4")], check=True)


# folder hour 5: unsorted; minute 0 has 30 s and 5 s; minute 1 has 61 s; minute 2 has 125 s; the last snapshot (hour 6 minute 0, 0.4 s) sits in folder 5 (next-hour stamp in this folder)
write(5, [(base5 + 30000, 100.0, 100.2), (base5 + 5000, 101.0, 101.2), (base5 + 61000, 102.0, 102.2), (base5 + 125000, 103.0, 103.2), (base6 + 400, 104.0, 104.2)])
# folder hour 6: minute 0 at 2.0 s (later than the 0.4 s one in folder 5); minute 1 at 1 s
write(6, [(base6 + 2000, 105.0, 105.2), (base6 + 61000, 106.0, 106.2)])
m5, m6 = base5 // 60000, base6 // 60000
tg = pd.DataFrame([dict(coin="TST", day="20260801", hour=5, minutes=[m5, m5 + 1, m5 + 2, m5 + 7, m6], n_minutes=5),
                   dict(coin="TST", day="20260801", hour=6, minutes=[m6, m6 + 1], n_minutes=2),
                   dict(coin="NOFILE", day="20260801", hour=5, minutes=[m5], n_minutes=1)])
tg.to_parquet(os.path.join(root, "t.parquet"))
out = os.path.join(root, "out")
py = sys.executable
subprocess.run([py, "-u", os.path.join(HERE, "build9_l2_books.py"), os.path.join(root, "t.parquet"), out, "--workers", "2", "--local", root], check=True)
subprocess.run([py, "-u", os.path.join(HERE, "build9_l2_books.py"), "--merge", out], check=True)
B = pd.read_parquet(os.path.join(out, "books_all.parquet")).set_index("minute")
ix = pd.concat([pd.read_parquet(os.path.join(out, f)) for f in os.listdir(out) if f.startswith("index_")])
print(ix.to_string())
assert abs(B.loc[m5, "snap_off_s"] - 5.0) < 1e-9 and abs(B.loc[m5, "bid_px"][0] - 101.0) < 1e-9, "minimum exchange time in an unsorted file"
assert abs(B.loc[m5 + 1, "snap_off_s"] - 1.0) < 1e-9
assert abs(B.loc[m5 + 2, "snap_off_s"] - 5.0) < 1e-9
assert m5 + 7 not in B.index, "a minute without a snapshot must be absent, not invented"
assert abs(B.loc[m6, "snap_off_s"] - 0.4) < 1e-9 and B.loc[m6, "src_rel_hour"] == -1, "the 0.4 s snapshot in folder 5 beats the 2.0 s one in folder 6: kept row comes from the previous folder"
assert abs(B.loc[m6 + 1, "snap_off_s"] - 1.0) < 1e-9 and B.loc[m6 + 1, "src_rel_hour"] == 0
assert int(np.isnan(B.loc[m5, "bid_px"]).sum()) == 17 and B.loc[m5, "n_bid"] == 3
r5 = ix[(ix["coin"] == "TST") & (ix["hour"] == 5)].iloc[0]
assert r5["n_wanted"] == 5 and r5["n_found"] == 4, (r5["n_wanted"], r5["n_found"])
assert ix[ix["coin"] == "NOFILE"].iloc[0]["status"] == "missing"
print("[SELFTEST] PASS: minimum-time snapshot per minute (unsorted file), NaN padding, boundary minute merged to the lowest snap_off_s with its source folder, absent minute counted (4 found of 5 wanted in folder 5), missing file indexed")
