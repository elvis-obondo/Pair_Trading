"""HL-BUILD2 stage 1: one UTC day of Hyperliquid fills -> per-minute bars + flow.

Usage: python build2_fills.py YYYYMMDD OUTDIR [--local DIR]
Reads raw fills from s3://hl-mainnet-node-data (requester-pays, ap-northeast-1)
or, with --local, from DIR/{fmt}/{YYYYMMDD}/{H}.lz4. Writes, for day D:
  OUTDIR/{D}.parquet       one row per (coin, minute) that has any fill: bar + flow
  OUTDIR/{D}_blocks.npz    block_number and block_time of every block read (D's own files)
  OUTDIR/{D}_meta.json     counts, checks, drops, timings
Stage 2 (build2_assemble.py) makes the dense per-coin grid; nothing here fills.

SOURCE FILES. Old format node_fills/hourly (2025-05-25..2025-07-27, one JSON
[wallet, fill] per line) and by-block node_fills_by_block/hourly (2025-07-27..,
one block per line with events [[wallet, fill], ...]). Every (day, hour) file
that exists in EITHER format is read; on 2025-07-27 hour 8 exists in both.

HOUR BOUNDARY (build2_d_sample_check.log). Folder hour is the node's clock, not
the fill time: 20260708/21 holds 24 fills timed 20:59:59.8. So fills are
bucketed by their own `time`, day D reads D/0..23 AND (D+1)/0, and keeps only
fills with time in [D, D+1). Fills of D-1 found in D/0 are dropped here and
picked up by D-1's read of D/0. ASSERTION: every fill in a file lies in
[folder hour - 1h, folder hour + 1h); otherwise the D/0..23 + (D+1)/0 read
could miss a fill, and the run aborts. Max early / late offsets are logged.

WINDOW. Fills before 2025-05-25 14:00 UTC (the archive's first file; user,
2026-10-14) are dropped here. Stage 2's window starts later, at 14:32, the
minute of the first fill (14:32:53.109; planner, 2026-10-15). The two starts
differ harmlessly: no fill exists between 14:00 and 14:32:53, and stage 1 was
already run with 14:00.

UNIVERSE. Perps only: names starting with '@' or containing '/' (spot; '/' is
PURR/USDC, spot pair 0), starting with '#' (outcome markets), or containing ':'
(HIP-3) are dropped (user / planner, 2026-10-14; '#' and '/' apply the existing
"crypto perps only" decision, not a rule change). Any remaining name outside
[A-Za-z0-9] aborts the run before it can reach a filename. Every name with a
Buy/Sell dir and every '/' name is still listed in the meta. Dropped fill counts and taker notional are reported per category.

DEDUPE. Keep one fill per (tid, wallet), preferring the by-block copy (it
carries twapId). Duplicates removed are counted.

TRADES. One trade = the fills sharing a tid. Price and volume come from the
taker fill (crossed == true). Trades with 0 or 2 takers are counted and
reported, never silently used: a 0-taker trade has no taker fill and so cannot
enter OHLCV; a 2-taker trade's tid is excluded from OHLCV and flow and counted.

ON-BOOK. Only trades whose taker fill dir is one of Open Long, Close Long, Open
Short, Close Short, Long > Short, Short > Long set the price. Every other taker
dir is off-book and kept out of OHLCV; counted by dir with notional.

BARS (per coin, per minute T = floor(time / 60 s), label = bar OPEN): taker
on-book fills in (time, seq) order, seq = EXECUTION order = the fill's position
in the files as read (file order, then line order, then event order within a
block). All fills of a block share one ms time, so the tie-break decides open
and close. It was tid in the brief; tid does not follow execution order
(build2_d2_candles.log: 91% close match, 100% volume match), corrected
2026-10-15 (planner: a bug in the brief, not a new decision). open = first px,
close = last px, high/low,
volume = sum sz (coin units), notional = sum px*sz, n_trades = count.

FLOW (per coin, per minute; raw dollars):
  taker_buy_usd / taker_sell_usd : on-book taker notional, side B / A
  n_taker_wallets                : distinct on-book taker wallets
  top3_taker_share               : top-3 taker wallets' share of on-book taker notional
  open_taker_usd / close_taker_usd : from the taker dir; flips split with the
                                   closing part min(|startPosition|, sz), rest opens
  liq_forced_long_usd / _short_usd : forced legs (liquidation.liquidatedUser == the
                                   fill's own wallet) with an on-book dir, taker or
                                   maker, once per tid; side A closes a long -> long,
                                   side B closes a short -> short
  backstop_liq_usd               : trades with any fill dir starting "Liquidated", once per tid
  adl_usd                        : trades with any fill dir "Auto-Deleveraging", once per tid
  twap_taker_usd                 : on-book taker notional with twapId not null; NaN for
                                   minutes before 2025-07-27 08:00 (old format has no twapId)
No look-ahead: a minute's row uses only fills whose time lies in that minute.
"""
import gc, json, os, subprocess, sys, time
from collections import Counter, defaultdict
import numpy as np, pandas as pd

try:
    import orjson
    loads = orjson.loads
except ImportError:
    loads = json.loads

BUCKET = "hl-mainnet-node-data"
FMT = {"old": "node_fills/hourly", "block": "node_fills_by_block/hourly"}
FIRST_OLD, LAST_OLD, FIRST_BLOCK = "20250525", "20250727", "20250727"
WINDOW_START_MS = int(pd.Timestamp("2025-05-25 14:00", tz="UTC").value // 10**6)
TWAP_FROM_MS = int(pd.Timestamp("2025-07-27 08:00", tz="UTC").value // 10**6)
ONBOOK = {"Open Long", "Close Long", "Open Short", "Close Short", "Long > Short", "Short > Long"}
HOUR_MS = 3_600_000
LAST_DAY = "20261013"            # the window's last day (yesterday at build time)
OVERLAP_DAY = "20250727"         # hour 8 exists in both formats


PERP_NAME = __import__("re").compile(r"[A-Za-z0-9]+")


def category(c):
    if c.startswith("@") or "/" in c: return "spot@"
    if c.startswith("#"): return "outcome#"
    if ":" in c: return "hip3"
    if not PERP_NAME.fullmatch(c):
        raise SystemExit(f"[ABORT] perp-category coin name {c!r} is outside [A-Za-z0-9]: it would reach a filename")
    return "perp"


def open_hour(fmt, day, h, local):
    if local:
        p = os.path.join(local, fmt, day, f"{h}.lz4")
        if not os.path.exists(p): return None
        return subprocess.Popen(["lz4", "-dc", p], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    key = f"s3://{BUCKET}/{FMT[fmt]}/{day}/{h}.lz4"
    cmd = f"aws s3 cp {key} - --request-payer requester --region ap-northeast-1 --only-show-errors | lz4 -dc"
    return subprocess.Popen(["bash", "-o", "pipefail", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def exists_map(local):
    """(fmt, day, hour) that exist. From a listing so a missing file is never a silent empty read."""
    have = set()
    if local:
        for fmt in FMT:
            for d in os.listdir(os.path.join(local, fmt)) if os.path.isdir(os.path.join(local, fmt)) else []:
                for f in os.listdir(os.path.join(local, fmt, d)):
                    have.add((fmt, d, int(f.split(".")[0])))
        return have
    raise RuntimeError("pass a listing file via HL_LISTING env for s3 mode")


def load_listing(path):
    have = set()
    for l in open(path):
        p = l.split()
        if len(p) < 4: continue
        k = p[3].split("/")
        fmt = "old" if k[0] == "node_fills" else "block"
        have.add((fmt, k[2], int(k[3].split(".")[0])))
    return have


def main():
    day, out = sys.argv[1], sys.argv[2]
    local = sys.argv[sys.argv.index("--local") + 1] if "--local" in sys.argv else None
    have = exists_map(local) if local else load_listing(os.environ["HL_LISTING"])
    os.makedirs(out, exist_ok=True)
    d0 = pd.Timestamp(day, tz="UTC"); d0ms = int(d0.value // 10**6); d1ms = d0ms + 24 * HOUR_MS
    nxt = (d0 + pd.Timedelta(days=1)).strftime("%Y%m%d")
    plan = [(fmt, day, h) for h in range(24) for fmt in ("block", "old") if (fmt, day, h) in have]
    plan += [(fmt, nxt, 0) for fmt in ("block", "old") if (fmt, nxt, 0) in have]
    nh0 = any((f, nxt, 0) in have for f in ("block", "old"))
    if not nh0 and day != LAST_DAY:
        raise SystemExit(f"[ABORT] {nxt}/0 is not in the listing: {day}'s spill-over fills would be lost")
    hours_present = sorted({h for (_, dd, h) in plan if dd == day})
    meta = {"day": day, "files": [f"{f}/{d}/{h}" for f, d, h in plan],
            "hours_present": len(hours_present), "next_h0_present": nh0, "hours_missing": [h for h in range(24) if h not in hours_present]}

    # perp fills, after the time filter. Lists per file, packed into numpy at the end
    # of each file; wallet / coin / dir interned to int codes to bound memory.
    chunks = defaultdict(list); wid, cid, did = {}, {}, {}
    seq = 0                                            # execution order across the day's reads
    drops = Counter(); drop_usd = Counter(); bs_dirs = Counter(); slash = Counter()
    blocks_n, blocks_t = [], []
    max_early = max_late = 0; nfill_total = 0; t0 = time.time(); per_file = []
    for fmt, dd, h in plan:
        fh = int((pd.Timestamp(dd, tz="UTC") + pd.Timedelta(hours=h)).value // 10**6)
        p = open_hour(fmt, dd, h, local); tf = time.time(); n = 0; tmin = tmax = None
        own = dd == day
        cols = defaultdict(list)
        for line in p.stdout:
            o = loads(line)
            if fmt == "block":
                if own:
                    blocks_n.append(o["block_number"]); blocks_t.append(o["block_time"])
                ev = o["events"]
            else:
                ev = (o,)
            for w, f in ev:
                n += 1
                t = f["time"]
                tmin = t if tmin is None or t < tmin else tmin; tmax = t if tmax is None or t > tmax else tmax
                off = t - fh
                if off < 0: max_early = max(max_early, -off)
                elif off >= HOUR_MS: max_late = max(max_late, off - HOUR_MS + 1)
                if not (-HOUR_MS <= off < HOUR_MS):      # [folder hour - 1h, folder hour + 1h)
                    raise SystemExit(f"[ABORT] fill time {t} outside [hour-1h, hour+1h) of {fmt}/{dd}/{h}")
                if t < d0ms or t >= d1ms or t < WINDOW_START_MS:
                    continue
                c = f["coin"]; cat = category(c)
                d_ = f["dir"]
                if d_ in ("Buy", "Sell"): bs_dirs[c] += 1
                if "/" in c: slash[c] += 1
                if cat != "perp":
                    drops[cat] += 1
                    if f["crossed"]: drop_usd[cat] += float(f["px"]) * float(f["sz"])
                    continue
                liq = f.get("liquidation")
                cols["wallet"].append(wid.setdefault(w, len(wid))); cols["coin"].append(cid.setdefault(c, len(cid)))
                cols["px"].append(float(f["px"])); cols["sz"].append(float(f["sz"]))
                cols["side"].append(f["side"] == "B"); cols["time"].append(t)
                cols["start"].append(float(f["startPosition"])); cols["dir"].append(did.setdefault(d_, len(did)))
                cols["crossed"].append(bool(f["crossed"])); cols["tid"].append(f["tid"])
                cols["twap"].append(f.get("twapId") is not None)
                cols["forced"].append(liq is not None and liq.get("liquidatedUser") == w)
                cols["fmt_block"].append(fmt == "block")
                cols["seq"].append(seq); seq += 1
        for k, dt_ in (("wallet", np.int32), ("coin", np.int16), ("px", np.float64), ("sz", np.float64),
                       ("side", bool), ("time", np.int64), ("start", np.float64), ("dir", np.int8),
                       ("crossed", bool), ("tid", np.int64), ("twap", bool), ("forced", bool), ("fmt_block", bool),
                       ("seq", np.int64)):
            chunks[k].append(np.asarray(cols[k], dt_))
        del cols
        rc = p.wait()
        if rc != 0:
            raise SystemExit(f"[ABORT] read of {fmt}/{dd}/{h} failed rc={rc} {p.stderr.read()[:300] if p.stderr else ''}")
        nfill_total += n; per_file.append((f"{fmt}/{dd}/{h}", n, round(time.time() - tf, 1), tmin, tmax))
    meta.update(read_s=round(time.time() - t0, 1), fills_read=nfill_total, per_file=per_file,
                max_early_ms=max_early, max_late_ms=max_late,
                dropped_fills=dict(drops), dropped_taker_usd={k: round(v, 2) for k, v in drop_usd.items()},
                buy_sell_dir_names=dict(bs_dirs.most_common()), slash_names=dict(slash))

    F = pd.DataFrame({k: np.concatenate(v) if v else np.zeros(0) for k, v in chunks.items()}); del chunks; gc.collect()
    inv = lambda m: np.array(sorted(m, key=m.get), dtype=object)
    F["coin"] = pd.Categorical.from_codes(F.coin.astype(int), inv(cid))
    F["dir"] = pd.Categorical.from_codes(F.dir.astype(int), inv(did)).astype(str)
    n_raw = len(F)
    F = F.sort_values("fmt_block", ascending=False, kind="stable")
    dup = F.duplicated(["tid", "wallet"], keep="first")
    meta["dedupe_removed"] = int(dup.sum())
    meta["dedupe_removed_by_hour"] = {int(k): int(v) for k, v in
                                      ((F.time[dup] // HOUR_MS) % 24).value_counts().items()}
    F = F[~dup]
    assert n_raw - len(F) == meta["dedupe_removed"]
    # (tid, wallet) assumes no wallet on both sides of a tid; outside the format
    # overlap any duplicate would be a self-trade silently losing a leg
    assert meta["dedupe_removed"] == 0 or day == OVERLAP_DAY, f"{meta['dedupe_removed']} duplicates outside the overlap day"
    assert not F.duplicated(["tid", "wallet"]).any()
    F["usd"] = F.px * F.sz
    F["minute"] = (F.time // 60_000) * 60_000

    # takers per tid
    tk = F.groupby("tid").crossed.sum()
    meta["tids"] = int(len(tk)); meta["tids_by_takers"] = {int(k): int(v) for k, v in tk.value_counts().items()}
    bad = set(tk.index[tk != 1])
    T = F[F.crossed & ~F.tid.isin(bad)]
    onb = T.dir.isin(ONBOOK)
    off = T[~onb]
    meta["offbook_by_dir"] = {d: {"trades": int(len(g)), "usd": round(float(g.usd.sum()), 2)}
                              for d, g in off.groupby("dir")}
    B = T[onb].sort_values(["coin", "time", "seq"], kind="stable")

    # forced-leg sanity: forced fills are half the liquidation-flagged ones is a sample fact; log counts
    meta["forced_fills"] = int(F.forced.sum())

    key = ["coin", "minute"]
    g = B.groupby(key, sort=True, observed=True)
    bars = pd.DataFrame({"open": g.px.first(), "high": g.px.max(), "low": g.px.min(), "close": g.px.last(),
                         "volume": g.sz.sum(), "notional": g.usd.sum(), "n_trades": g.size()})
    B = B.assign(buy=np.where(B.side, B.usd, 0.0), sell=np.where(B.side, 0.0, B.usd))
    flip = B.dir.isin({"Long > Short", "Short > Long"})
    closing_sz = np.where(flip, np.minimum(B.start.abs(), B.sz),
                          np.where(B.dir.str.startswith("Close"), B.sz, 0.0))
    B = B.assign(close_usd=closing_sz * B.px)
    B = B.assign(open_usd=B.usd - B.close_usd, twap_usd=np.where(B.twap, B.usd, 0.0))
    g = B.groupby(key, sort=True, observed=True)
    flow = pd.DataFrame({"taker_buy_usd": g.buy.sum(), "taker_sell_usd": g.sell.sum(),
                         "n_taker_wallets": g.wallet.nunique(),
                         "open_taker_usd": g.open_usd.sum(), "close_taker_usd": g.close_usd.sum(),
                         "twap_taker_usd": g.twap_usd.sum()})
    w = B.groupby(key + ["wallet"], sort=False, observed=True).usd.sum().reset_index()
    w = w.sort_values(key + ["usd"], ascending=[True, True, False])
    top3 = w.groupby(key, observed=True).head(3).groupby(key, observed=True).usd.sum()
    flow["top3_taker_share"] = top3 / bars.notional
    # forced legs on the book, once per tid
    Fo = F[F.forced & F.dir.isin(ONBOOK) & ~F.tid.isin(bad)].drop_duplicates("tid")
    meta["forced_offbook_dir_fills"] = int((F.forced & ~F.dir.isin(ONBOOK)).sum())
    fl = Fo.assign(lu=np.where(~Fo.side, Fo.usd, 0.0), su=np.where(Fo.side, Fo.usd, 0.0)).groupby(key, observed=True)
    liq = pd.DataFrame({"liq_forced_long_usd": fl.lu.sum(), "liq_forced_short_usd": fl.su.sum()})
    bk = F[F.dir.str.startswith("Liquidated")].drop_duplicates("tid").groupby(key, observed=True).usd.sum().rename("backstop_liq_usd")
    ad = F[F.dir == "Auto-Deleveraging"].drop_duplicates("tid").groupby(key, observed=True).usd.sum().rename("adl_usd")
    R = bars.join(flow, how="outer").join(liq, how="outer").join(bk, how="outer").join(ad, how="outer")
    fz = [c for c in R.columns if c not in ("open", "high", "low", "close", "top3_taker_share")]
    R[fz] = R[fz].fillna(0.0)
    R.loc[R.index.get_level_values("minute") < TWAP_FROM_MS, "twap_taker_usd"] = np.nan
    R = R.reset_index()
    R["minute"] = pd.to_datetime(R.minute, unit="ms", utc=True)
    R.to_parquet(os.path.join(out, f"{day}.parquet"), index=False)
    bn = np.asarray(blocks_n, np.int64)
    bt = pd.to_datetime(pd.Series(blocks_t, dtype=str), utc=True, format="ISO8601").astype("int64").to_numpy() if blocks_t else np.zeros(0, np.int64)
    np.savez_compressed(os.path.join(out, f"{day}_blocks.npz"), number=bn, time_ns=bt)
    if len(bn):
        s = np.sort(bn); st = np.diff(s)
        meta["blocks"] = {"n": int(len(bn)), "first": int(s[0]), "last": int(s[-1]),
                          "dups": int((st == 0).sum()), "gaps": int((st > 1).sum()),
                          "missing_blocks": int((st[st > 1] - 1).sum())}
    meta.update(perp_fills=int(len(F)), onbook_trades=int(len(B)), rows=int(len(R)),
                coins=int(R.coin.nunique()), total_s=round(time.time() - t0, 1),
                peak_rss_mb=round(__import__("resource").getrusage(__import__("resource").RUSAGE_SELF).ru_maxrss
                                  / (1 if sys.platform == "linux" else 1024) / 1024, 1))
    json.dump(meta, open(os.path.join(out, f"{day}_meta.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in meta.items() if k not in ("per_file", "files")}, default=str))


if __name__ == "__main__":
    main()
