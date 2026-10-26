"""HL-BUILD2 stage 2: per-day sparse minute rows -> dense per-coin 1m/30m bars + flow.

Usage: python build2_assemble.py DAYDIR OUTDIR [--test]
--test (pilot only): skip the full-window day-set assertion and build the
grid over the given days only. Run once per pilot day, each in its own DAYDIR
(the pilot days are not adjacent). Never used for D1.
DAYDIR holds stage 1's {D}.parquet, {D}_blocks.npz, {D}_meta.json for every day
of the window. OUTDIR gets futures/{COIN}-{1m,30m}.feather, flow/{COIN}.parquet,
missing_minutes.parquet and assemble_meta.json.

MISSING TIME (archive gaps are missing, not quiet). WINDOW: 2025-05-25 14:32
UTC, the minute of the archive's first fill (14:32:53.109; user / planner,
2026-10-15, moving the earlier 14:00 start) to the last day. A minute is missing
for EVERY coin when
 (a) its hour file is absent in both formats;
 (b) it overlaps a block_number gap. Blocks are checked day by day (each day's
     own 24 files; the day sets are asserted ordered and disjoint, and the
     boundary pair between days is gap-checked): a gap (b_prev, b_next) with
     b_next - b_prev > 1 marks the minutes overlapping the open interval
     (block_time[b_prev], block_time[b_next]). A block number recorded twice
     marks the open interval between its two copies (gap-fill: 706113001 on
     2025-08-23, 08:48:17 -> 08:57:37, no block between);
 (c) it lies in the format switch: the old format's last fill to the by-block
     format's first block (2025-07-27 08:45:48.7 -> 08:49:59.4);
 (d) it lies in an old-format file-edge hole: before 2025-07-27 there are no
     block numbers, so a hole shows only as consecutive hour files whose last
     fill (H) and first fill (H+1) are > 60 s apart (2025-06-08 09:44 -> 10:27,
     2025-07-19 09:53 -> 10:16); the window start is bounded the same way (the
     partial minute 14:32). Holes INSIDE an old file cannot be seen; the
     report-only count of market-wide empty old-format minutes covers them.
All intervals use one convention: minutes floor(start) .. floor(end - 1 ns).
Chain halts (consecutive block numbers > 60 s apart) are listed, not marked: a
paused chain cannot trade. GATE: missing minutes > 0.1% of the window's minutes
-> STOP (exit 2) before any bar is written.

COIN LIFE. From the first to the last minute with an on-book trade (n_trades >
0). Rows with only liquidation / backstop / ADL activity and no on-book trade
are NOT trades: they never start or end a life.

NO-TRADE MINUTES inside the life are real: close = previous close, open = high =
low = close, volume = notional = 0, flow sums 0, n_trades 0, top3_taker_share
NaN, mins_since_trade = minutes since the last trade minute (0 on a trade minute).

CLOSES, RULE (iii) (user, 2026-10-15). A close is NaN only when it is unknown.
The 1m close at t is the close of the last traded minute L <= t; it is VALID iff
no hole minute lies in [L, t]. Minute resolution, and [L, t] INCLUDES minute L:
stage 1 keeps minute aggregates, not each trade's second, so a hole sharing L's
minute with the last trade also invalidates the close (gap-fill, conservative).
So after a hole, no-trade minutes stay NaN until the next clean trade, and a
hole earlier in a bar, before its last trade, does not invalidate the close.
mins_since_trade is NaN wherever the close is.

HOLE MINUTES are flagged gap_in_bar = True (1m and 30m). On a hole minute the
BARS keep what was observed: open/high/low from its trades if it has any (else
the close, i.e. NaN), volume/notional the observed sum (0 if none). The FLOW
table is NaN on hole minutes, n_trades included. So a hole minute reads volume 0
in the bars but n_trades NaN in the flow: anyone summing volume or notional
must use gap_in_bar. No synthetic or interpolated price anywhere.

30m BARS from the 1m bars: close = the 1m close at H+29 (the same rule over the
bar, so "(last trade, H+30m]" across the bar boundary), mins_since_trade
likewise; open = the FIRST minute's open as it is (NaN when that minute is an
unknown hole minute); high max, low min, volume / notional sums; gap_in_bar =
any hole minute in the bar. Bars kept where the 30m window lies inside the
coin's life. Asserted on every bar (NaN == NaN): close == the 1m close at H+29,
open == the 1m open at H, high/low/volume/notional == the 1m resample.
"""
import glob, json, multiprocessing as mp, os, sys
import numpy as np, pandas as pd

# the archive's first file is 20250525/14, but its first fill is 14:32:53.109
# (build2_assemble_plain_receipt.log); the window starts at that minute (user /
# planner, 2026-10-15) and rule (d) marks the partial minute 14:32 missing
WINDOW_START = pd.Timestamp("2025-05-25 14:32", tz="UTC")
LAST_DAY = "20261013"
BLOCKS_FROM = pd.Timestamp("2025-07-27 08:00", tz="UTC")
GATE = 0.001
BAR = ["open", "high", "low", "close", "volume", "notional", "n_trades"]



G = {}            # shared state for the pool workers (set in main, inherited by fork)
PAR = int(os.environ.get("ASM_PAR", os.cpu_count() or 1))


def _split_day(d):
    """Pass A: one day's sparse rows -> _parts/{coin}/{d}.parquet."""
    x = pd.read_parquet(os.path.join(G["src"], f"{d}.parquet")); x["coin"] = x.coin.astype(str)
    for c, g in x.groupby("coin", sort=False):
        os.makedirs(os.path.join(G["parts"], c), exist_ok=True)
        g.drop(columns="coin").to_parquet(os.path.join(G["parts"], c, f"{d}.parquet"), index=False)
    return list(x.columns)

def main():
    src, out = sys.argv[1], sys.argv[2]
    days = sorted(os.path.basename(p)[:8] for p in glob.glob(os.path.join(src, "*_meta.json")))
    test = "--test" in sys.argv
    if test:
        grid = pd.DatetimeIndex([]).tz_localize("UTC")
        for d in days:
            a = max(pd.Timestamp(d, tz="UTC"), WINDOW_START)
            grid = grid.append(pd.date_range(a, pd.Timestamp(d, tz="UTC") + pd.Timedelta(minutes=1439), freq="1min"))
    else:
        want = pd.date_range("2025-05-25", LAST_DAY, freq="D").strftime("%Y%m%d")
        assert list(days) == list(want), f"day set != window: missing {sorted(set(want) - set(days))[:5]}"
        end = pd.Timestamp(LAST_DAY, tz="UTC") + pd.Timedelta(days=1)
        grid = pd.date_range(WINDOW_START, end - pd.Timedelta(minutes=1), freq="1min")
    miss = pd.Series(False, index=grid)
    meta = {"days": len(days), "window_minutes": len(grid)}

    # (a) hour files absent in both formats
    hm = []
    for d in days:
        m = json.load(open(os.path.join(src, f"{d}_meta.json")))
        for h in m["hours_missing"]:
            t = pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=h)
            if t + pd.Timedelta(hours=1) <= WINDOW_START: continue
            hm.append(str(t)); miss[max(t, WINDOW_START): t + pd.Timedelta(minutes=59)] = True
    meta["missing_hours"] = hm
    # (b) block gaps, day by day. Each day's npz holds only its OWN 24 hour files
    # (D-1 reads D/0 as next-day spill, not as own), so the day sets are ordered
    # and disjoint: asserted at every boundary, and the one boundary pair is
    # checked for a gap. Peak memory is one day's blocks, not 506M.
    # A block number recorded twice (build2_blockdup_check.log: 706113001 on
    # 2025-08-23 at 08:48:17 and 08:57:37, no block between) marks the minutes
    # overlapping the open interval between its two copies MISSING (gap-fill:
    # whether the chain halted or the archive lost them is unknown).
    gaps, dups, halts = [], [], []
    prev = None; first_blk_t = None; nblocks = 0; first_n = last_n = None

    def mark(a_ns, b_ns):
        a = pd.Timestamp(int(a_ns), tz="UTC"); b = pd.Timestamp(int(b_ns), tz="UTC")
        lo, hi = a.floor("1min"), (b - pd.Timedelta(1, "ns")).floor("1min")
        miss[lo:hi] = True
        return a, b, int((hi - lo) / pd.Timedelta(minutes=1)) + 1

    for d in days:
        z = np.load(os.path.join(src, f"{d}_blocks.npz"))
        n, t = z["number"], z["time_ns"]
        if not len(n):
            continue
        o = np.lexsort((t, n)); n, t = n[o], t[o]
        assert (np.diff(t) >= 0).all(), f"{d}: block_time decreases in (number, time) order"
        dd = np.flatnonzero(np.diff(n) == 0)
        assert not len(np.intersect1d(dd, dd + 1)), f"{d}: a block number recorded 3+ times"
        for i in dd:
            a, b, k = mark(t[i], t[i + 1])
            dups.append((int(n[i]), str(a), str(b), k, d))
        keep = np.r_[True, np.diff(n) != 0]; n, t = n[keep], t[keep]
        if prev is not None:
            assert n[0] > prev[0], f"{d}: first block {n[0]} <= previous day's last {prev[0]}"
            assert t[0] >= prev[1], f"{d}: first block_time precedes previous day's last"
            n = np.r_[prev[0], n]; t = np.r_[prev[1], t]   # include the boundary pair
        else:
            first_blk_t = int(t[0]); first_n = int(n[0])
        st = np.diff(n)
        for i in np.flatnonzero(st > 1):
            a, b, k = mark(t[i], t[i + 1])
            gaps.append((int(n[i]), int(n[i + 1]), str(a), str(b), int(st[i] - 1), d))
        dt_ = np.diff(t)
        for i in np.flatnonzero((st == 1) & (dt_ > 60 * 10**9)):      # report only
            halts.append((int(n[i]), str(pd.Timestamp(int(t[i]), tz="UTC")), str(pd.Timedelta(int(dt_[i]), "ns")), d))
        nblocks += len(n) - (prev is not None)
        prev = (int(n[-1]), int(t[-1])); last_n = int(n[-1])
    meta["duplicate_blocks"] = dups
    meta["halts_over_60s_report_only"] = halts
    meta["blocks_total"] = nblocks; meta["blocks_first_last"] = [first_n, last_n]
    # (d) old-format holes at file edges (user / planner, 2026-10-15, applying
    # "archive gaps are missing"): the old format has no block numbers, so a hole
    # shows only as consecutive hour files whose last fill (H) and first fill (H+1)
    # are > 60 s apart; that stretch is missing for every coin. The window's first
    # fill bounds the start the same way (WINDOW_START -> first fill).
    olds = []
    for d in days:
        if d > "20250727": break
        m = json.load(open(os.path.join(src, f"{d}_meta.json")))
        for name, n, _, *span in m["per_file"]:
            if name.startswith("old/") and span and span[0] is not None:
                _, dd, hh = name.split("/")
                if dd == d:                                   # own files only (D+1/0 is read twice)
                    olds.append((pd.Timestamp(dd, tz="UTC") + pd.Timedelta(hours=int(hh)), span[0], span[1]))
    olds.sort()
    old_holes = []
    if olds:
        a0 = pd.Timestamp(olds[0][1], unit="ms", tz="UTC")
        if a0 - WINDOW_START > pd.Timedelta(seconds=60) or a0.floor("1min") == WINDOW_START:
            lo, hi = WINDOW_START, (a0 - pd.Timedelta(1, "ns")).floor("1min")
            miss[lo:hi] = True
            old_holes.append((str(WINDOW_START), str(a0), int((hi - lo) / pd.Timedelta(minutes=1)) + 1, "window start"))
    for (h1, _, t1), (h2, t2, _) in zip(olds, olds[1:]):
        if h2 - h1 != pd.Timedelta(hours=1):
            continue                                          # a missing hour file is rule (a)
        if t2 - t1 > 60_000:
            a = pd.Timestamp(t1, unit="ms", tz="UTC"); b = pd.Timestamp(t2, unit="ms", tz="UTC")
            lo, hi = a.floor("1min"), (b - pd.Timedelta(1, "ns")).floor("1min")
            miss[lo:hi] = True
            old_holes.append((str(a), str(b), int((hi - lo) / pd.Timedelta(minutes=1)) + 1, f"{h1:%Y%m%d/%H} -> {h2:%H}"))
    meta["old_format_file_holes"] = old_holes
    # (c) the format switch: the old format's last fill to the by-block format's
    # first block is in neither file set (20250727: 08:45:48.7 -> 08:49:59.4,
    # build2_d0_overlap_0727.log); those minutes are missing for every coin
    old_last = None
    for d in days:
        m = json.load(open(os.path.join(src, f"{d}_meta.json")))
        for name, n, _, *span in m["per_file"]:          # pre-pilot-fix metas carry no span
            tmin, tmax = span if span else (None, None)
            if name.startswith("old/") and tmax is not None:
                old_last = tmax if old_last is None else max(old_last, tmax)
    if old_last is not None and first_blk_t is not None:
        first_blk = pd.Timestamp(first_blk_t, tz="UTC"); a = pd.Timestamp(old_last, unit="ms", tz="UTC")
        if first_blk > a:
            lo, hi = a.floor("1min"), (first_blk - pd.Timedelta(1, "ns")).floor("1min")
            miss[lo:hi] = True
            meta["format_switch_hole"] = [str(a), str(first_blk), int((hi - lo) / pd.Timedelta(minutes=1)) + 1]
    meta["block_gaps"] = len(gaps); meta["block_gap_list"] = gaps[:200]
    nm = int(miss.sum()); meta["missing_minutes"] = nm; meta["missing_share"] = nm / len(grid)
    # report only (no rule): old-format minutes with no perp fill in any coin. The
    # old format has no block numbers, so a hole inside it cannot be proven; BTC
    # alone trades nearly every minute, so a market-wide empty minute is suspect.
    oldmins = set()
    for d in days:
        if d > "20250727": break
        x = pd.read_parquet(os.path.join(src, f"{d}.parquet"), columns=["minute"])
        oldmins |= set(x.minute)
    old_end = pd.Timestamp("2025-07-27 08:45", tz="UTC")
    og = grid[grid < old_end]
    # report only: old-format files whose fills start > 60 s after the hour or end > 60 s before its end
    edges = []
    for d in days:
        if d > "20250727": break
        m = json.load(open(os.path.join(src, f"{d}_meta.json")))
        for name, n, _, *span in m["per_file"]:          # pre-pilot-fix metas carry no span
            tmin, tmax = span if span else (None, None)
            if not name.startswith("old/") or tmin is None: continue
            _, dd, hh = name.split("/")
            h0 = int((pd.Timestamp(dd, tz="UTC") + pd.Timedelta(hours=int(hh))).value // 10**6)
            if tmin - h0 > 60_000 or (h0 + 3_600_000) - tmax > 60_000:
                edges.append((name, n, str(pd.Timestamp(tmin, unit="ms")), str(pd.Timestamp(tmax, unit="ms"))))
    meta["old_format_short_files_report_only"] = edges
    meta["old_format_empty_minutes_report_only"] = int(sum(1 for t in og if t not in oldmins and not miss[t]))
    print(f"[GATE] missing minutes {nm:,} of {len(grid):,} = {100*nm/len(grid):.4f}% "
          f"(hours {len(hm)}, block gaps {len(gaps)}, duplicate blocks {len(dups)}, old-format file holes {len(old_holes)}, "
          f"format switch {meta.get('format_switch_hole')}), threshold {100*GATE:.1f}%", flush=True)
    os.makedirs(out, exist_ok=True)
    miss[miss].index.to_frame(name="minute").to_parquet(os.path.join(out, "missing_minutes.parquet"))
    if nm / len(grid) > GATE and test:
        print("[GATE] (--test: one-day grid, gate reported only; not a D1 verdict)")
    elif nm / len(grid) > GATE:
        json.dump(meta, open(os.path.join(out, "assemble_meta.json"), "w"), indent=1, default=str)
        print("[GATE] STOP: missing time exceeds 0.1% of the window"); sys.exit(2)

    # split by coin one day at a time (the whole window does not fit in memory)
    parts = os.path.join(out, "_parts"); os.makedirs(parts, exist_ok=True)
    G.update(src=src, parts=parts)
    with mp.get_context("fork").Pool(PAR) as pool:          # pass A: one day per task, distinct files
        allcols = pool.map(_split_day, days, chunksize=4)
    cols = allcols[0]
    assert all(c == cols for c in allcols), "day parquets disagree on columns"
    fdir = os.path.join(out, "futures"); wdir = os.path.join(out, "flow")
    os.makedirs(fdir, exist_ok=True); os.makedirs(wdir, exist_ok=True)
    # n_trades goes to the FLOW table (the brief lists it there), not the bars
    flowcols = ["n_trades"] + [c for c in cols if c not in ["coin", "minute"] + BAR]
    G.update(parts=parts, miss=miss, flowcols=flowcols, fdir=fdir, wdir=wdir, out=out)
    coins = {}; n30 = 0; nan30_ts = {}
    names = sorted(os.listdir(parts))
    with mp.get_context("fork").Pool(PAR) as pool:          # Linux; G is inherited by fork
        for c, cmeta, k30, ts in pool.imap_unordered(_coin, names, chunksize=1):
            coins[c] = cmeta; n30 += k30
            for t in ts:
                nan30_ts[t] = nan30_ts.get(t, 0) + 1
    coins = dict(sorted(coins.items()))
    meta["coins"] = coins; meta["bars_30m"] = n30
    meta["post_gap_nan_minutes_total"] = sum(v.get("post_gap_nan_minutes", 0) for v in coins.values())
    meta["nan_30m_close_rule_iii_total"] = sum(v.get("nan_30m_close_rule_iii", 0) for v in coins.values())
    meta["bars_30m_touching_a_hole_total"] = sum(v.get("bars_30m_touching_a_hole", 0) for v in coins.values())
    meta["nan_30m_close_timestamps"] = dict(sorted(nan30_ts.items()))   # timestamp -> coins with a NaN close there
    print(f"[RULE iii] 30m closes NaN: {meta['nan_30m_close_rule_iii_total']:,} (coin-bars); 30m bars touching a hole "
          f"(plain rule): {meta['bars_30m_touching_a_hole_total']:,}; distinct NaN-close timestamps {len(nan30_ts)}")
    __import__("shutil").rmtree(parts)
    json.dump(meta, open(os.path.join(out, "assemble_meta.json"), "w"), indent=1, default=str)
    print(f"[DONE] {sum(1 for v in coins.values() if v['trades'])} coins, {n30:,} 30m bars asserted")


def _coin(c):
    """One coin: its parts -> dense 1m/30m bars, flow, coin_month. Pass B of stage 2;
    coins are independent, so this runs in a process pool. Reads G (set in main)."""
    parts, miss, flowcols, fdir, wdir, out = (G[k] for k in ("parts", "miss", "flowcols", "fdir", "wdir", "out"))
    g = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(os.path.join(parts, c, "*.parquet")))])
    g = g.set_index("minute").sort_index()
    assert g.index.is_unique
    tr = g.index[g.n_trades > 0]
    if len(tr) == 0:
        return c, {"trades": 0}, 0, []
    life = pd.date_range(tr[0], tr[-1], freq="1min")
    x = g.reindex(life)
    mm = miss.reindex(life)
    assert not mm.isna().any(), f"{c}: life minutes outside the window grid"
    m = mm.to_numpy(bool)
    assert m.dtype == bool
    traded = (x.n_trades > 0).to_numpy()
    # RULE (iii) (user, 2026-10-15): a close is missing only if it is unknown.
    # The close at minute t is the last on-book trade at or before t (minute L).
    # It is VALID iff no missing minute lies in [L, t]. Minute resolution, so a
    # hole sharing minute L with the last trade also invalidates it (stage 1
    # keeps minute aggregates, not each trade's second: conservative).
    pos = np.arange(len(life))
    L = pd.Series(np.where(traded, pos, np.nan)).ffill().to_numpy()
    assert not np.isnan(L).any()                         # life starts on a trade
    L = L.astype(np.int64)
    cmiss = np.cumsum(m)
    before = np.where(L > 0, cmiss[np.maximum(L - 1, 0)], 0)
    valid = (cmiss - before) == 0                        # no missing minute in [L, t]
    obs_close = x.close.to_numpy(float)
    close = np.where(valid, obs_close[L], np.nan)
    notrade = ~traded & ~m
    x["close"] = close
    for k in ("open", "high", "low"):
        x[k] = np.where(traded, x[k], close)             # observed on traded minutes (flagged if in a hole)
    for k in ("volume", "notional", "n_trades"):
        x[k] = x[k].fillna(0.0)                          # observed; a hole minute is flagged by gap_in_bar
    x["gap_in_bar"] = m
    mst = (pos - L).astype(float)
    post_gap_nan = int((np.isnan(close) & ~m).sum())     # receipt: no-trade minutes after a hole, before the next trade
    x["mins_since_trade"] = np.where(valid, mst, np.nan)
    for k in flowcols:
        v = x[k]
        if k == "n_trades":
            x[k] = np.where(m, np.nan, v)
        elif k == "top3_taker_share":
            x[k] = np.where(m, np.nan, v)                 # NaN when no notional
        elif k == "twap_taker_usd":
            x[k] = np.where(m | (life < BLOCKS_FROM), np.nan, v.fillna(0.0))
        else:
            x[k] = np.where(m, np.nan, v.fillna(0.0))
    assert not np.isnan(close[traded & ~m & valid]).any()
    b1 = pd.DataFrame({"date": life.astype("datetime64[ms, UTC]")})
    for k in ["open", "high", "low", "close", "volume", "notional", "mins_since_trade"]:  # n_trades -> flow
        b1[k] = x[k].to_numpy(float)
    b1["gap_in_bar"] = m
    b1.to_feather(os.path.join(fdir, f"{c}-1m.feather"))
    # 30m: close = the 1m close at H+29 (the same rule over the bar); o/h/l/v/notional
    # from the minutes; gap_in_bar = any hole minute in the bar
    H = pd.date_range(life[0].ceil("30min"), life[-1] - pd.Timedelta(minutes=29), freq="30min")
    s = b1.set_index(pd.DatetimeIndex(life))
    grp = s.groupby(s.index.floor("30min"))
    # open = the FIRST minute's open as it is (NaN when that minute is an unknown
    # hole minute); groupby.first() would skip NaN and take a later minute's
    firsts = s.open[(s.index.minute % 30) == 0]
    a = pd.DataFrame({"open": firsts, "high": grp.high.max(), "low": grp.low.min(),
                      "volume": grp.volume.sum(), "notional": grp.notional.sum(),
                      "gap_in_bar": grp.gap_in_bar.any(), "n": grp.size()}).reindex(H)
    assert (a.n == 30).all()
    a["close"] = s.close.reindex(H + pd.Timedelta(minutes=29)).to_numpy()
    a["mins_since_trade"] = s.mins_since_trade.reindex(H + pd.Timedelta(minutes=29)).to_numpy()
    a = a[["open", "high", "low", "close", "volume", "notional", "mins_since_trade", "gap_in_bar", "n"]]
    # assertions on every bar against the 1m file (NaN == NaN)
    rs30 = s.resample("30min")
    assert np.array_equal(a.close.to_numpy(), s.close.reindex(H + pd.Timedelta(minutes=29)).to_numpy(), equal_nan=True), c
    assert np.array_equal(a.open.to_numpy(), s.open.reindex(H).to_numpy(), equal_nan=True), c
    for k, f in (("high", "max"), ("low", "min"), ("volume", "sum"), ("notional", "sum")):
        ref = getattr(rs30[k], f)().reindex(H).to_numpy()
        assert np.allclose(a[k].to_numpy(), ref, rtol=1e-12, atol=0, equal_nan=True), (c, k)
    nan30_iii = H[np.isnan(a.close.to_numpy())]
    nan30_plain = int((a.gap_in_bar.astype(bool) | np.isnan(a.close.to_numpy())).sum())
    b30 = a.drop(columns=["n"]).reset_index(names="date")
    b30["date"] = b30.date.astype("datetime64[ms, UTC]")
    b30.to_feather(os.path.join(fdir, f"{c}-30m.feather"))
    fl = x[flowcols].copy(); fl.insert(0, "date", life.astype("datetime64[ms, UTC]"))
    fl.to_parquet(os.path.join(wdir, f"{c}.parquet"), index=False)
    # per-coin per-month parquet (bars + flow) for the bucket
    cm = os.path.join(out, "coin_month", c); os.makedirs(cm, exist_ok=True)
    both = b1.merge(fl, on="date", how="left", validate="one_to_one")
    for mo, gm in both.groupby(both.date.dt.strftime("%Y-%m"), sort=True):
        gm.to_parquet(os.path.join(cm, f"{mo}.parquet"), index=False)
    cmeta = {"trades": int(g.n_trades.sum()), "first": str(tr[0]), "last": str(tr[-1]),
                "life_minutes": len(life), "trade_minutes": int(traded.sum()),
                "notrade_minutes": int(notrade.sum()), "missing_minutes": int(m.sum()),
                "nan_close_minutes": int(np.isnan(close).sum()), "post_gap_nan_minutes": post_gap_nan,
                "nan_30m_close_rule_iii": int(len(nan30_iii)), "bars_30m_touching_a_hole": nan30_plain,
                "bars_30m": int(len(H))}
    return c, cmeta, len(b30), [str(t) for t in nan30_iii]


if __name__ == "__main__":
    main()
