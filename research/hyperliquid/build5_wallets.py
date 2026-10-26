"""HL-BUILD5 stage 1: one UTC day of Hyperliquid fills -> the wallet tables T1, T2, T3.

Usage: python build5_wallets.py YYYYMMDD OUTDIR [--local DIR] [--flow DIR]
Same source, perps-only filter, hour-boundary rule, window start, execution-order seq and
(tid, wallet) dedupe as build2_fills.py (imported, not re-derived). Writes, for day D:
  OUTDIR/{D}_wallet_bin.parquet   T1: one row per (wallet, coin, 5-minute UTC bin) with any activity
  OUTDIR/{D}_wallet_day.parquet   T2: one row per wallet
  OUTDIR/{D}_vault.parquet        T3: per-wallet absorbed backstop USD and ADL-taker USD for the day
  OUTDIR/{D}_b5_meta.json         counts, bytes, timings, assertion results
With --flow DIR (build 2 stage-1 outputs) the T1 sums are checked against that day's flow table.

T1 COLUMNS (USD = px x sz; bin label = bin OPEN; the day is cut at 00:00 UTC, bins divide 1440):
  taker_buy_usd, taker_sell_usd, open_buy_usd, open_sell_usd, close_buy_usd, close_sell_usd,
  twap_usd, n_taker_fills : the wallet's own TAKER fills (crossed = true) under the flow table's
      rule - the tid has exactly one taker and the taker's dir is one of the six on-book dirs -
      so that the sum over wallets equals the flow table's columns. Opening / closing split as
      build2_fills.py (flips: closing part min(|startPosition|, sz)). twap_usd is NaN before
      2025-07-27 08:00.
  other_taker_usd : taker fills NOT counted above (off-book dir, or a tid with 0 or 2 takers), so
      that nothing is dropped from the table.
  forced_long_usd, forced_short_usd : the wallet's own forced legs (liquidation.liquidatedUser ==
      the fill's wallet) with an on-book dir, taker or maker; side A closes a long -> long. EVERY
      forced fill, so a tid with two liquidated wallets keeps both (build2 keeps one per tid;
      the difference is logged as forced_extra_vs_flow).
  maker_usd : the wallet's non-crossed fills of any dir.
  hole : the bin touches a missing minute (build 2 stage 2's list, build5_missing_minutes.parquet).
T2: volume_usd (all fills), taker_share (taker USD / volume), closed_pnl_usd (sum of closedPnl),
  fees_usd (sum of fee), n_coins, n_forced_events (distinct tids of the wallet's own forced fills),
  forced_usd, n_fills.
T3: per wallet and day, absorbed_backstop_usd = USD of its fills with a dir starting "Liquidated" when
  the wallet is not the liquidated user (both fills of a backstop tid carry that dir; first version of
  this table looked for the other dirs and read ADL'd wallets instead - fixed 2026-10-15);
  T1 gets absorbed_buy_usd / absorbed_sell_usd (the absorber's side) for the same fills;
  adl_taker_usd = USD of its crossed fills with dir "Auto-Deleveraging". Candidates are named from
  these in the report; no address is hard-coded.
"""
import json, os, sys, time
from collections import defaultdict
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build2_fills as b2

BIN_MS = 300_000
MISSING = os.environ.get("HL_MISSING", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "build5_missing_minutes.parquet"))


def read_day(day, have, local):
    """Rows of every perp fill of UTC day `day`, as build2_fills.main() reads them, with the extra fields."""
    d0 = pd.Timestamp(day, tz="UTC"); d0ms = int(d0.value // 10**6); d1ms = d0ms + 24 * b2.HOUR_MS
    nxt = (d0 + pd.Timedelta(days=1)).strftime("%Y%m%d")
    plan = [(fmt, day, h) for h in range(24) for fmt in ("block", "old") if (fmt, day, h) in have]
    plan += [(fmt, nxt, 0) for fmt in ("block", "old") if (fmt, nxt, 0) in have]
    if not any((f, nxt, 0) in have for f in ("block", "old")) and day != b2.LAST_DAY:
        raise SystemExit(f"[ABORT] {nxt}/0 is not in the listing: {day}'s spill-over fills would be lost")
    chunks = defaultdict(list); wid, cid, did = {}, {}, {}
    seq = 0; n_all = 0
    for fmt, dd, h in plan:
        fh = int((pd.Timestamp(dd, tz="UTC") + pd.Timedelta(hours=h)).value // 10**6)
        p = b2.open_hour(fmt, dd, h, local)
        cols = defaultdict(list)
        for line in p.stdout:
            o = b2.loads(line)
            ev = o["events"] if fmt == "block" else (o,)
            for w, f in ev:
                n_all += 1
                t = f["time"]; off = t - fh
                if not (-b2.HOUR_MS <= off < b2.HOUR_MS):
                    raise SystemExit(f"[ABORT] fill time {t} outside [hour-1h, hour+1h) of {fmt}/{dd}/{h}")
                if t < d0ms or t >= d1ms or t < b2.WINDOW_START_MS:
                    continue
                c = f["coin"]
                if b2.category(c) != "perp":
                    continue
                liq = f.get("liquidation")
                lu = liq.get("liquidatedUser") if liq else None
                cols["wallet"].append(wid.setdefault(w, len(wid))); cols["coin"].append(cid.setdefault(c, len(cid)))
                cols["px"].append(float(f["px"])); cols["sz"].append(float(f["sz"]))
                cols["side"].append(f["side"] == "B"); cols["time"].append(t)
                cols["start"].append(float(f["startPosition"])); cols["dir"].append(did.setdefault(f["dir"], len(did)))
                cols["crossed"].append(bool(f["crossed"])); cols["tid"].append(f["tid"])
                cols["twap"].append(f.get("twapId") is not None)
                cols["forced"].append(lu is not None and lu == w)
                cols["liq_user"].append(-1 if lu is None else wid.setdefault(lu, len(wid)))
                cols["pnl"].append(float(f.get("closedPnl") or 0.0)); cols["fee"].append(float(f.get("fee") or 0.0))
                cols["fmt_block"].append(fmt == "block"); cols["seq"].append(seq); seq += 1
        for k, dt_ in (("wallet", np.int32), ("coin", np.int16), ("px", np.float64), ("sz", np.float64), ("side", bool),
                       ("time", np.int64), ("start", np.float64), ("dir", np.int8), ("crossed", bool), ("tid", np.int64),
                       ("twap", bool), ("forced", bool), ("liq_user", np.int32), ("pnl", np.float64), ("fee", np.float64),
                       ("fmt_block", bool), ("seq", np.int64)):
            chunks[k].append(np.asarray(cols[k], dt_))
        del cols
        rc = p.wait()
        if rc != 0:
            raise SystemExit(f"[ABORT] read of {fmt}/{dd}/{h} failed rc={rc}")
    F = pd.DataFrame({k: np.concatenate(v) for k, v in chunks.items()})
    inv = lambda m: np.array(sorted(m, key=m.get), dtype=object)
    wal = inv(wid)
    F["coin"] = pd.Categorical.from_codes(F.coin.astype(int), inv(cid)).astype(str)
    F["dir"] = pd.Categorical.from_codes(F.dir.astype(int), inv(did)).astype(str)
    return F, wal, n_all


def tables(F, day):
    """T1, T2, T3 (wallet as an integer code; the caller maps codes to addresses)."""
    out = {}
    n_raw = len(F)
    F = F.sort_values("fmt_block", ascending=False, kind="stable")
    dup = F.duplicated(["tid", "wallet"], keep="first")
    out["dedupe_removed"] = int(dup.sum())
    F = F[~dup]
    assert out["dedupe_removed"] == 0 or day == b2.OVERLAP_DAY, f"{out['dedupe_removed']} duplicates outside the overlap day"
    F = F.assign(usd=F.px * F.sz, bin=(F.time // BIN_MS) * BIN_MS)
    tk = F.groupby("tid").crossed.sum()
    bad = set(tk.index[tk != 1])
    onbook_dir = F.dir.isin(b2.ONBOOK)
    # ---- taker side, the flow table's rule
    cnt = F.crossed & ~F.tid.isin(bad) & onbook_dir
    T = F[cnt]
    flip = T.dir.isin({"Long > Short", "Short > Long"})
    close_sz = np.where(flip, np.minimum(T.start.abs(), T.sz), np.where(T.dir.str.startswith("Close"), T.sz, 0.0))
    close_usd = close_sz * T.px
    open_usd = T.usd - close_usd
    T = T.assign(buy=np.where(T.side, T.usd, 0.0), sell=np.where(T.side, 0.0, T.usd),
                 open_buy=np.where(T.side, open_usd, 0.0), open_sell=np.where(T.side, 0.0, open_usd),
                 close_buy=np.where(T.side, close_usd, 0.0), close_sell=np.where(T.side, 0.0, close_usd),
                 twap_usd=np.where(T.twap, T.usd, 0.0), n=1)
    key = ["wallet", "coin", "bin"]
    g = T.groupby(key, sort=True)
    t1 = pd.DataFrame({"taker_buy_usd": g.buy.sum(), "taker_sell_usd": g.sell.sum(),
                       "open_buy_usd": g.open_buy.sum(), "open_sell_usd": g.open_sell.sum(),
                       "close_buy_usd": g.close_buy.sum(), "close_sell_usd": g.close_sell.sum(),
                       "twap_usd": g.twap_usd.sum(), "n_taker_fills": g.n.sum()})
    # ---- taker fills not counted above
    O = F[F.crossed & ~cnt]
    t1 = t1.join(O.groupby(key).usd.sum().rename("other_taker_usd"), how="outer")
    # ---- forced legs: every one, taker or maker, on-book dir
    Fo = F[F.forced & onbook_dir & ~F.tid.isin(bad)]
    fl = Fo.assign(lu=np.where(~Fo.side, Fo.usd, 0.0), su=np.where(Fo.side, Fo.usd, 0.0)).groupby(key)
    t1 = t1.join(pd.DataFrame({"forced_long_usd": fl.lu.sum(), "forced_short_usd": fl.su.sum()}), how="outer")
    t1 = t1.join(F[~F.crossed].groupby(key).usd.sum().rename("maker_usd"), how="outer")
    fz = [c for c in t1.columns]
    t1[fz] = t1[fz].fillna(0.0)
    # build 2's forced total keeps one forced fill per tid; ours keeps all
    Fd = Fo.drop_duplicates("tid")
    out["forced_extra_vs_flow_usd"] = float(Fo.usd.sum() - Fd.usd.sum())
    out["_forced_dedup"] = Fd
    # ---- T2
    gd = F.groupby("wallet")
    tk_usd = F[F.crossed].groupby("wallet").usd.sum()
    ff = F[F.forced]
    t2 = pd.DataFrame({"volume_usd": gd.usd.sum(), "closed_pnl_usd": gd.pnl.sum(), "fees_usd": gd.fee.sum(),
                       "n_coins": gd.coin.nunique(), "n_fills": gd.size().astype(np.int32)})
    t2["taker_share"] = tk_usd.reindex(t2.index).fillna(0.0) / t2.volume_usd
    gf = ff.groupby("wallet")
    t2["n_forced_events"] = gf.tid.nunique().reindex(t2.index).fillna(0).astype(np.int32)
    t2["forced_usd"] = gf.usd.sum().reindex(t2.index).fillna(0.0)
    t2 = t2.reset_index()
    # ---- T3. In a backstop liquidation BOTH fills of the tid carry a dir starting "Liquidated" (pilot, raw
    # fills of 2025-10-10 21h: the liquidated user's fill and the absorbing wallet's fill, method "backstop").
    # The absorber is the Liquidated-dir fill whose wallet is not the liquidated user.
    L = F[F.dir.str.startswith("Liquidated")]
    liq_tids = L.tid.unique()
    absb = L[L.wallet != L.liq_user]
    t3 = pd.DataFrame({"absorbed_backstop_usd": absb.groupby("wallet").usd.sum()})
    ad = F[F.crossed & (F.dir == "Auto-Deleveraging")].groupby("wallet").usd.sum().rename("adl_taker_usd")
    t3 = t3.join(ad, how="outer").fillna(0.0).reset_index()
    Ab = absb.assign(ab=np.where(absb.side, absb.usd, 0.0), asl=np.where(absb.side, 0.0, absb.usd)).groupby(key)
    t1 = t1.join(pd.DataFrame({"absorbed_buy_usd": Ab.ab.sum(), "absorbed_sell_usd": Ab.asl.sum()}), how="left").fillna(0.0)
    t1["n_taker_fills"] = t1.n_taker_fills.astype(np.int32)
    t1 = t1.reset_index() if "wallet" not in t1.columns else t1
    out["liquidated_dir_counts"] = {k: int(v) for k, v in L.dir.value_counts().items()}
    out["liquidated_tids"] = int(len(liq_tids))
    out["forced_dir_counts"] = {k: int(v) for k, v in ff.dir.value_counts().items()}
    out["forced_fills"] = int(len(ff)); out["forced_fills_offbook_dir"] = int((ff.dir.isin(b2.ONBOOK) == False).sum())
    out["t1"], out["t2"], out["t3"] = t1, t2, t3
    out["absorbed_usd_t1_vs_t3"] = float(t1.absorbed_buy_usd.sum() + t1.absorbed_sell_usd.sum() - t3.absorbed_backstop_usd.sum())
    out["perp_fills"] = int(len(F)); out["bad_tids"] = len(bad)
    return out


def ms_of(ts):
    """Epoch milliseconds of a timestamp column, whatever datetime unit pandas holds."""
    return ((pd.to_datetime(ts, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).to_numpy().astype(np.int64)


def hole_bins(day):
    mm = pd.read_parquet(MISSING)
    assert len(mm) == 114, f"missing-minutes file has {len(mm)} rows, build 2 stage 2 reports 114"
    col = mm["minute"] if "minute" in mm else mm.iloc[:, 0]
    ms = ms_of(col)
    d0 = int(pd.Timestamp(day, tz="UTC").value // 10**6)
    ms = ms[(ms >= d0) & (ms < d0 + 86_400_000)]
    return set(((ms // BIN_MS) * BIN_MS).tolist())


def check_flow(t1, forced_dedup, flow_path):
    """Sum over wallets of T1 per (coin, bin) vs the flow table of the same day, same bins."""
    fl = pd.read_parquet(flow_path)
    fl["bin"] = (ms_of(fl.minute) // BIN_MS) * BIN_MS
    pairs = {"taker_buy_usd": "taker_buy_usd", "taker_sell_usd": "taker_sell_usd", "open_buy_usd": "open_buy_usd",
             "open_sell_usd": "open_sell_usd", "close_buy_usd": "close_buy_usd", "close_sell_usd": "close_sell_usd"}
    A = fl.groupby(["coin", "bin"])[[*pairs.values(), "twap_taker_usd", "liq_forced_long_usd", "liq_forced_short_usd"]].sum(min_count=1)
    B = t1.groupby(["coin", "bin"])[[*pairs.keys(), "twap_usd", "forced_long_usd", "forced_short_usd"]].sum()
    Fd = forced_dedup.assign(lu=np.where(~forced_dedup.side, forced_dedup.usd, 0.0), su=np.where(forced_dedup.side, forced_dedup.usd, 0.0))
    Bd = Fd.groupby(["coin", "bin"])[["lu", "su"]].sum()
    res = {}
    allk = A.index.union(B.index)
    A = A.reindex(allk); B = B.reindex(allk); Bd = Bd.reindex(allk)
    for a, b in [*pairs.items(), ("twap_taker_usd", "twap_usd")]:
        x, y = A[a].to_numpy(float), B[b].to_numpy(float)
        both_nan = np.isnan(x)                                   # twap before 2025-07-27 08:00 is NaN in the flow table
        d = np.where(both_nan, 0.0, np.nan_to_num(x) - np.nan_to_num(y))
        res[b] = float(np.abs(d).max())
    for a, b in (("liq_forced_long_usd", "lu"), ("liq_forced_short_usd", "su")):
        res[b + "_dedup"] = float(np.abs(np.nan_to_num(A[a].to_numpy(float)) - np.nan_to_num(Bd[b].to_numpy(float))).max())
    res["rows_flow_bins"] = int(len(A)); res["rows_t1_bins"] = int(t1.groupby(["coin", "bin"]).ngroups)
    res["total_taker_usd_flow"] = float((A.taker_buy_usd + A.taker_sell_usd).sum())
    res["total_taker_usd_t1"] = float((B.taker_buy_usd + B.taker_sell_usd).sum())
    return res


def main():
    day, out = sys.argv[1], sys.argv[2]
    local = sys.argv[sys.argv.index("--local") + 1] if "--local" in sys.argv else None
    flow = sys.argv[sys.argv.index("--flow") + 1] if "--flow" in sys.argv else None
    have = b2.exists_map(local) if local else b2.load_listing(os.environ["HL_LISTING"])
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    F, wal, n_all = read_day(day, have, local)
    t_read = time.time() - t0
    R = tables(F, day)
    t1, t2, t3 = R["t1"], R["t2"], R["t3"]
    meta = {"day": day, "fills_read_incl_spill": n_all, "read_s": round(t_read, 1)}
    meta.update({k: v for k, v in R.items() if not k.startswith("_") and k not in ("t1", "t2", "t3")})
    hb = hole_bins(day)
    t1["hole"] = t1.bin.isin(hb)
    meta["hole_flagged_bins"] = int(t1.hole.sum()); meta["hole_bins_in_day"] = len(hb)
    meta["totals_usd"] = {c: float(t1[c].sum()) for c in ("other_taker_usd", "maker_usd", "forced_long_usd", "forced_short_usd")}
    meta["totals_usd"]["taker_onbook_usd"] = float((t1.taker_buy_usd + t1.taker_sell_usd).sum())
    meta["maker_over_onbook_taker"] = meta["totals_usd"]["maker_usd"] / max(meta["totals_usd"]["taker_onbook_usd"], 1.0)
    top = t3.sort_values("absorbed_backstop_usd", ascending=False).head(10)
    tot = float(t3.absorbed_backstop_usd.sum())
    meta["t3_top10"] = [(w, float(a), float(a) / tot if tot else 0.0) for w, a in zip(wal[top.wallet.to_numpy()], top.absorbed_backstop_usd)]
    meta["t3_total_absorbed_usd"] = tot
    if flow:
        meta["flow_check"] = check_flow(t1, R["_forced_dedup"], os.path.join(flow, f"{day}.parquet"))
        fc = meta["flow_check"]
        worst = max(v for k, v in fc.items() if k not in ("rows_flow_bins", "rows_t1_bins", "total_taker_usd_flow", "total_taker_usd_t1"))
        assert worst < 1e-3, f"T1 does not reconcile with the flow table: {fc}"
    for t in (t1, t2, t3):
        t["wallet"] = wal[t.wallet.to_numpy()]
    t1["bin"] = pd.to_datetime(t1.bin, unit="ms", utc=True)
    t1.loc[t1.bin < pd.Timestamp("2025-07-27 08:00", tz="UTC"), "twap_usd"] = np.nan
    t1["coin"] = t1.coin.astype("category")
    sizes = {}
    for nm, t in (("wallet_bin", t1), ("wallet_day", t2), ("vault", t3)):
        p = os.path.join(out, f"{day}_{nm}.parquet")
        t.to_parquet(p, index=False, compression="zstd")
        sizes[nm] = {"rows": int(len(t)), "bytes": os.path.getsize(p)}
    meta.update(sizes=sizes, distinct_wallets=int(t2.wallet.nunique()), distinct_wallet_coin_bins=int(len(t1)),
                total_s=round(time.time() - t0, 1),
                peak_rss_mb=round(__import__("resource").getrusage(__import__("resource").RUSAGE_SELF).ru_maxrss
                                  / (1 if sys.platform == "linux" else 1024) / 1024, 1))
    json.dump(meta, open(os.path.join(out, f"{day}_b5_meta.json"), "w"), indent=1, default=str)
    print(json.dumps(meta, default=str))


if __name__ == "__main__":
    main()
