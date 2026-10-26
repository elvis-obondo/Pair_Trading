"""HL-MASTER1 G7 raw pass: open interest change from EVERY fill, maker-side open/close dollars, and the HLP vault inventory. One UTC day of fills -> per coin-minute tables.

Usage: python build7_oi.py YYYYMMDD OUTDIR [--local DIR] [--flow DIR]
Reads the day exactly as build5_wallets.read_day does (same source, perps-only filter, hour-boundary rule, window start, execution-order seq; (tid, wallet) dedupe). Writes for day D:
  OUTDIR/{D}_oi.parquet     one row per (coin, minute) with any fill:
      oi_delta_coin   sum over EVERY fill (both parties, maker and taker; liquidation, ADL, Net Child Vaults included) of 1/2 (|p'| - |p|), p = startPosition, p' = p + sz (buy) or p - sz (sell),
                      in coin units.  Total gross position = 2 x open interest, so this is exactly the open-interest change of the minute.
      oi_delta_usd    the same x the fill's price, summed
      n_fills
      {taker,maker}_{open,close}_{buy,sell}_usd_pos   opening / closing dollars by the fill's side, POSITION-based: the closing part of a fill is min(|p|, sz) when the fill
                      is against the wallet's position, the rest opens (flips split). The taker totals are reconciled against the flow table's dir-based open/close columns.
  OUTDIR/{D}_vault.parquet  per (vault wallet, coin, minute): first start position, last end position, n_fills, for the HLP vault wallets listed in VAULTS (positions persist between fills)
  OUTDIR/{D}_b7_meta.json   counts, checks (tids whose buy size differs from the sell size; flow reconciliation), timings
"""
import json, os, sys, time
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build2_fills as b2
import build5_wallets as b5

# the four backstop absorbers (build 5, T3) and the vault leader address, as confirmed by the user 2026-10-24
VAULTS = ["0xb0a55f13d22f66e6d495ac98113841b2326e9540", "0x2e3d94f0562703b25c83308a05046ddaf9a8dd14", "0x5e177e5e39c0f4e421f5865a6d8beed8d921cb70",
          "0x2ed5c4484ea3ff8b57d5f2fb152a40d9f2b68308", "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"]


def tables(F, wal, day):
    out = {}
    F = F.sort_values("fmt_block", ascending=False, kind="stable")
    dup = F.duplicated(["tid", "wallet"], keep="first")
    out["dedupe_removed"] = int(dup.sum())
    F = F[~dup]
    assert out["dedupe_removed"] == 0 or day == b2.OVERLAP_DAY, f"{out['dedupe_removed']} duplicates outside the overlap day"
    sgn = np.where(F.side, 1.0, -1.0)
    p0 = F.start.to_numpy()
    p1 = p0 + sgn * F.sz.to_numpy()
    doi = 0.5 * (np.abs(p1) - np.abs(p0))
    against = (sgn * p0) < 0                                         # the fill reduces the wallet's absolute position
    close_sz = np.where(against, np.minimum(np.abs(p0), F.sz.to_numpy()), 0.0)
    px = F.px.to_numpy()
    F = F.assign(minute=(F.time // 60_000) * 60_000, doi=doi, doi_usd=doi * px, close_usd=close_sz * px, open_usd=(F.sz.to_numpy() - close_sz) * px, p0=p0, p1=p1)
    cols = {"doi": "oi_delta_coin", "doi_usd": "oi_delta_usd"}
    g = F.groupby(["coin", "minute"], sort=True)
    oi = pd.DataFrame({"oi_delta_coin": g.doi.sum(), "oi_delta_usd": g.doi_usd.sum(), "n_fills": g.size().astype(np.int32)})
    for who, m in (("taker", F.crossed), ("maker", ~F.crossed)):
        for kind in ("open", "close"):
            for sd, sm in (("buy", F.side), ("sell", ~F.side)):
                v = F[f"{kind}_usd"].where(m & sm, 0.0)
                oi[f"{who}_{kind}_{sd}_usd_pos"] = v.groupby([F.coin, F.minute]).sum()
    out["oi"] = oi.reset_index()
    # like-for-like totals for the flow-table reconciliation: the flow table counts a taker fill only if its tid has exactly one taker AND the taker's dir is on-book
    tk = F.groupby("tid").crossed.sum()
    badt = set(tk.index[tk != 1])
    cnt = F.crossed & ~F.tid.isin(badt) & F.dir.isin(b2.ONBOOK)
    out["onbook_pos"] = {f"{kind}_{sd}": float(F[f"{kind}_usd"].where(cnt & sm, 0.0).sum()) for kind in ("open", "close") for sd, sm in (("buy", F.side), ("sell", ~F.side))}
    out["taker_all_pos"] = {f"{kind}_{sd}": float(F[f"{kind}_usd"].where(F.crossed & sm, 0.0).sum()) for kind in ("open", "close") for sd, sm in (("buy", F.side), ("sell", ~F.side))}
    # each trade has equal buy and sell size: count tids whose sizes differ
    bs = F.assign(sg=np.where(F.side, F.sz, -F.sz)).groupby("tid").sg.sum()
    out["tids"] = int(len(bs))
    unb_ix = bs.index[(bs.abs() > 1e-6 * F.groupby("tid").sz.max().reindex(bs.index))]
    out["tids_unbalanced"] = int(len(unb_ix))
    U = F[F.tid.isin(unb_ix)]
    out["unbalanced_usd"] = float((U.px * U.sz).sum())
    out["unbalanced_detail"] = [dict(tid=int(r.tid), coin=str(r.coin), time_ms=int(r.time), wallet=str(wal[int(r.wallet)]), side="B" if r.side else "A", sz=float(r.sz), px=float(r.px),
                                     dir=str(r.dir), crossed=bool(r.crossed), format="block" if r.fmt_block else "old") for r in U.head(60).itertuples()]
    out["sum_oi_delta_coin_abs"] = float(np.abs(oi.oi_delta_coin).sum())
    # vault inventory
    vw = [i for i, w in enumerate(wal) if w.lower() in VAULTS]
    V = F[F.wallet.isin(vw)].sort_values(["time", "seq"], kind="stable")      # execution order (the dedupe sort put block-format rows first)
    gv = V.groupby(["wallet", "coin", "minute"], sort=True)
    vt = pd.DataFrame({"start_position": gv.p0.first(), "end_position": gv.p1.last(), "n_fills": gv.size().astype(np.int32)}).reset_index()
    # continuity: for consecutive minutes of one (wallet, coin) the next start position must equal the previous end position
    same = (vt.wallet.to_numpy()[1:] == vt.wallet.to_numpy()[:-1]) & (vt.coin.to_numpy()[1:] == vt.coin.to_numpy()[:-1])
    gap_ = np.abs(vt.start_position.to_numpy()[1:] - vt.end_position.to_numpy()[:-1])
    tol = 1e-9 * np.maximum(1.0, np.abs(vt.end_position.to_numpy()[:-1])) + 1e-9
    viol = same & (gap_ > tol)
    out["vault_consecutive_pairs"] = int(same.sum())
    out["vault_continuity_violations"] = int(viol.sum())
    out["vault_continuity_max_gap"] = float(gap_[same].max()) if same.any() else 0.0
    assert not viol.any(), f"vault position continuity broken on {int(viol.sum())} of {int(same.sum())} consecutive minutes (max gap {gap_[same].max():.3e})"
    vt["wallet"] = np.asarray(wal)[vt.wallet.to_numpy()]
    out["vault"] = vt
    out["perp_fills"] = int(len(F))
    return out


def check_flow(onbook_pos, taker_all, flow_path):
    """Taker open/close dollars, position-based, against the flow table's dir-based columns, summed over the day. Like-for-like (the flow table's own rule: one-taker tids, on-book dir) and all taker fills."""
    fl = pd.read_parquet(flow_path)
    res = {}
    for k in onbook_pos:
        kind, sd = k.split("_")
        b = float(fl[f"{kind}_{sd}_usd"].sum())
        res[f"taker_{k}"] = (onbook_pos[k], b, (onbook_pos[k] - b) / max(abs(b), 1.0), (taker_all[k] - b) / max(abs(b), 1.0))
    return res


def main():
    day, out = sys.argv[1], sys.argv[2]
    local = sys.argv[sys.argv.index("--local") + 1] if "--local" in sys.argv else None
    flow = sys.argv[sys.argv.index("--flow") + 1] if "--flow" in sys.argv else None
    have = b2.exists_map(local) if local else b2.load_listing(os.environ["HL_LISTING"])
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    F, wal, n_all = b5.read_day(day, have, local)
    R = tables(F, wal, day)
    meta = {"day": day, "fills_read_incl_spill": n_all, "read_s": round(time.time() - t0, 1)}
    meta.update({k: v for k, v in R.items() if k not in ("oi", "vault", "onbook_pos", "taker_all_pos")})
    if flow:
        meta["flow_check"] = check_flow(R["onbook_pos"], R["taker_all_pos"], os.path.join(flow, f"{day}.parquet"))
    R["oi"]["minute"] = pd.to_datetime(R["oi"].minute, unit="ms", utc=True)
    R["vault"]["minute"] = pd.to_datetime(R["vault"].minute, unit="ms", utc=True)
    R["oi"]["coin"] = R["oi"].coin.astype("category")
    sizes = {}
    for nm, t in (("oi", R["oi"]), ("vault", R["vault"])):
        p = os.path.join(out, f"{day}_{nm}.parquet")
        t.to_parquet(p, index=False, compression="zstd")
        sizes[nm] = {"rows": int(len(t)), "bytes": os.path.getsize(p)}
    meta.update(sizes=sizes, total_s=round(time.time() - t0, 1),
                peak_rss_mb=round(__import__("resource").getrusage(__import__("resource").RUSAGE_SELF).ru_maxrss / (1 if sys.platform == "linux" else 1024) / 1024, 1))
    json.dump(meta, open(os.path.join(out, f"{day}_b7_meta.json"), "w"), indent=1, default=str)
    print(json.dumps(meta, default=str))


if __name__ == "__main__":
    main()
