"""HL-BUILD2 rerun: merge the stage-1 parts into one day/ prefix for stage 2.

Usage: python build2_merge_parts.py NAME PART [PART ...]
Reads s3://pair-trading-hl-289869684922/build2/NAME/PART/stage1_exits_part.txt for
every part and refuses to merge unless:
  - the parts' day sets are contiguous date ranges with no overlap;
  - together they hold every day 2025-05-25..2026-10-13 exactly once (507);
  - every day exited 0;
  - every day has its three outputs (.parquet, _blocks.npz, _meta.json).
Then copies each day's files server side to build2/NAME/day/ and writes
build2/NAME/day/stage1_exits.txt. A lost or failed part is relaunched alone;
this never runs on partial parts.
"""
import subprocess, sys
import pandas as pd

AWS = ["/Users/elvisobondo/.local/bin/aws", "--region", "ap-northeast-1", "--cli-read-timeout", "60"]
B = "s3://pair-trading-hl-289869684922/build2"
name, parts = sys.argv[1], sys.argv[2:]
want = list(pd.date_range("2025-05-25", "2026-10-13", freq="D").strftime("%Y%m%d"))


def run(*a):
    return subprocess.run(AWS + list(a), check=True, capture_output=True, text=True).stdout


ex, ranges, files = {}, [], {}
for p in parts:
    txt = run("s3", "cp", f"{B}/{name}/{p}/stage1_exits_part.txt", "-")
    e = dict(l.split(" exit ") for l in txt.split("\n") if " exit " in l)
    dup = set(e) & set(ex)
    assert not dup, f"{p}: days already in another part: {sorted(dup)[:5]}"
    ex.update(e)
    ds = sorted(e)
    ranges.append((ds[0], ds[-1], p))
    assert ds == want[want.index(ds[0]): want.index(ds[-1]) + 1], f"{p}: day set is not a contiguous range"
    ls = run("s3", "ls", f"{B}/{name}/{p}/")
    files[p] = {l.split()[-1] for l in ls.splitlines() if l.strip()}
ranges.sort()
for (a0, a1, pa), (b0, b1, pb) in zip(ranges, ranges[1:]):
    assert want.index(b0) == want.index(a1) + 1, f"{pa} -> {pb}: ranges not adjacent ({a1} -> {b0})"
assert sorted(ex) == want, f"day set != window: missing {sorted(set(want) - set(ex))[:5]}"
bad = {d: r for d, r in ex.items() if r != "0"}
assert not bad, f"non-zero exits: {bad}"
for a0, a1, p in ranges:
    for d in want[want.index(a0): want.index(a1) + 1]:
        for f in (f"{d}.parquet", f"{d}_blocks.npz", f"{d}_meta.json"):
            assert f in files[p], f"{p}: {f} missing"
print(f"[MERGE] parts {[(a, b, p) for a, b, p in ranges]}: {len(ex)} days, all exit 0, 3 files each")
for a0, a1, p in ranges:
    run("s3", "cp", f"{B}/{name}/{p}/", f"{B}/{name}/day/", "--recursive", "--only-show-errors",
        "--exclude", "*", "--include", "2*")
open("/tmp/stage1_exits.txt", "w").write("".join(f"{d} exit {ex[d]}\n" for d in want))
run("s3", "cp", "/tmp/stage1_exits.txt", f"{B}/{name}/day/stage1_exits.txt", "--only-show-errors")
ls = run("s3", "ls", f"{B}/{name}/day/")
n = {k: sum(1 for l in ls.splitlines() if l.split()[-1].endswith(k)) for k in (".parquet", "_blocks.npz", "_meta.json")}
print(f"[MERGE] {B}/{name}/day/: {n}  + stage1_exits.txt (507 x exit 0)")
assert all(v == 507 for v in n.values()), n
