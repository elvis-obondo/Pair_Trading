"""HL-MASTER1 G6: wallet concentration, skill and vault shares at t0, per LEG (the net version is joined later), windows 30 / 60 / 360 / 1440 minutes. Features only. STANDALONE (numpy / pandas / pyarrow only) so it runs on the VM or on AWS.

    python -u master_g6.py rows.parquet WALLET_DIR OUT_DIR MISSING.parquet FIRST_DAY LAST_DAY    (one chunk of UTC days: trigger days in [FIRST_DAY, LAST_DAY))

rows.parquet: one row per (unit, event, leg): unit (0 pair, 1 coin), ev (row position in that unit's event table), leg (0 = A, 1 = B), coin, t0_ms (epoch ms of t0 = T + 30 min), day (UTC day of the bar label T, as 'YYYY-MM-DD'), s (push sign +1 / -1).
WALLET_DIR: build 5's {YYYYMMDD}_wallet_bin.parquet (T1) and _wallet_day.parquet (T2) from s3://pair-trading-hl-289869684922/build5/full2/.

Definitions (docs/DATASET_DICTIONARY.md, G6). Pushing side: taker buys if s > 0, sells if s < 0 (T1 on-book, one-taker rule). Window [t0 - W, t0): whole 5-minute bins, bins < t0 only. Populations: ALL wallets and HUMAN =
all wallets except the four HLP liquidator wallets and the vault leader (VAULTS below). Per population p and window:
  top1_p, top3_p, hhi_p, nw_p, pers_p (share from the coin's 10 largest taker wallets by the trailing 7 UTC days ending before the trigger's day, >= 3 days; ranked within the population), twap_p (population TWAP USD / its
  taker notional, NaN before 2025-07-27 08:00), skill_mean_p, skill_cov_p, bot_p, topd_p, prior_forced_p (skill from T2 days strictly before the trigger's day: trailing 30-day closed_pnl / volume x n_fills / (n_fills + 5000), NaN with
  < 5 active days; deciles of skill over wallets active on the day before; prior_forced = any own liquidation in the 30 days), push_total_p (USD).
  Not per population: vault_push_share (vault + leader pushing-side taker USD / push_total_all) vault_absorb_ratio (the four vaults' absorbed USD on the side opposite the push / push_total_all, >= 0, unbounded) and vault_absorb_share = absorbed / (absorbed + push_total_all) in [0, 1] (the default).
A window that reaches before 2025-05-25 14:35 or touches a missing minute, or a push_total of 0, gives NaN shares; nw = 0 when push_total = 0 and the window is valid.
"""
import os, sys, time
import numpy as np
import pandas as pd

BIN_MS = 300_000
WINS = (30, 60, 360, 1440)
K_SHRINK, TRAIL_SKILL, TRAIL_PERS, MIN_ACTIVE, MIN_PERS_DAYS = 5000.0, 30, 7, 5, 3
TWAP_FROM_MS = int(pd.Timestamp("2025-07-27 08:00", tz="UTC").value // 10**6)
DATA_START_MS = int(pd.Timestamp("2025-05-25 14:35", tz="UTC").value // 10**6)
VAULTS = ["0xb0a55f13d22f66e6d495ac98113841b2326e9540", "0x2e3d94f0562703b25c83308a05046ddaf9a8dd14", "0x5e177e5e39c0f4e421f5865a6d8beed8d921cb70",
          "0x2ed5c4484ea3ff8b57d5f2fb152a40d9f2b68308", "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"]
FEATS = ["top1", "top3", "hhi", "nw", "pers", "twap", "skill_mean", "skill_cov", "bot", "topd", "prior_forced"]
NAMES = [f"{f}_{p}" for p in ("all", "human") for f in FEATS] + ["push_total_all", "push_total_human", "vault_push_share", "vault_absorb_ratio", "vault_absorb_share"]
NF = len(NAMES)
IX = {n: i for i, n in enumerate(NAMES)}


def dstr(d):
    return d.strftime("%Y%m%d")


def load_t1(wdir, day):
    p = os.path.join(wdir, f"{dstr(day)}_wallet_bin.parquet")
    if not os.path.exists(p):
        return None
    return pd.read_parquet(p, columns=["wallet", "coin", "bin", "taker_buy_usd", "taker_sell_usd", "twap_usd", "absorbed_buy_usd", "absorbed_sell_usd"])


def load_t2(wdir, day):
    p = os.path.join(wdir, f"{dstr(day)}_wallet_day.parquet")
    if not os.path.exists(p):
        return None
    return pd.read_parquet(p, columns=["wallet", "volume_usd", "closed_pnl_usd", "n_forced_events", "n_fills"])


def ms_of(ts):
    t = pd.to_datetime(ts)
    if getattr(t, "dt", None) is not None and t.dt.tz is not None:
        t = t.dt.tz_localize(None)
    return ((t - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1)).to_numpy().astype(np.int64)


def pop_feats(wid, push, both, tw, tw_nan, skill, cuts, forced30, pers_set):
    """The 11 per-population features + push_total for one window slice (arrays already restricted to the population)."""
    out = np.full(12, np.nan, np.float32)
    pt = float(push.sum())
    out[11] = pt
    if pt <= 0:
        out[3] = 0.0
        return out
    uw, inv = np.unique(wid, return_inverse=True)
    sw = np.bincount(inv, weights=push)
    pos = sw > 0
    sh = sw / pt
    srt = np.sort(sh)[::-1]
    out[0], out[1], out[2], out[3] = srt[0], srt[:3].sum(), float((sh ** 2).sum()), float(pos.sum())
    if pers_set is not None:
        out[4] = float(sw[np.isin(uw, pers_set)].sum() / pt)
    tb = float(both.sum())
    if not tw_nan and tb > 0:
        out[5] = float(tw.sum() / tb)
    sk = skill[uw]
    have = np.isfinite(sk) & pos
    if have.any():
        out[6] = float((sk[have] * sw[have]).sum() / sw[have].sum())
    out[7] = float(sw[have].sum() / pt)
    if cuts is not None:
        lo, hi = cuts
        out[8] = float(sw[np.isfinite(sk) & (sk <= lo)].sum() / pt)
        out[9] = float(sw[np.isfinite(sk) & (sk >= hi)].sum() / pt)
    out[10] = float(sw[forced30[uw] > 0].sum() / pt)
    return out


def run_chunk(rows, wdir, holes_ms, a, b):
    """rows: DataFrame restricted to trigger days in [a, b). Returns (positions in `rows`, result array (n, 4, NF))."""
    t0 = time.time()
    days_need = pd.date_range(a - pd.Timedelta(days=TRAIL_SKILL + 1), b - pd.Timedelta(days=1), freq="D")
    t2 = {d: load_t2(wdir, d) for d in days_need}
    t2 = {d: x for d, x in t2.items() if x is not None}
    allw = pd.Index(pd.unique(pd.concat([x.wallet for x in t2.values()], ignore_index=True)))
    nw_ids = len(allw)
    vault_ids = np.array([i for i in allw.get_indexer(VAULTS) if i >= 0], dtype=np.int64)
    is_vault = np.zeros(nw_ids + 1, bool)
    is_vault[vault_ids] = True
    T2i = {d: (allw.get_indexer(x.wallet), x.volume_usd.to_numpy(float), x.closed_pnl_usd.to_numpy(float), x.n_forced_events.to_numpy(float), x.n_fills.to_numpy(float)) for d, x in t2.items()}
    coins = rows.coin.to_numpy()
    s_all = rows.s.to_numpy(float)
    t0ms = rows.t0_ms.to_numpy(np.int64)
    dayv = pd.to_datetime(rows.day).to_numpy()
    res = np.full((len(rows), len(WINS), NF), np.nan, np.float32)
    for D in pd.date_range(a, b - pd.Timedelta(days=1), freq="D"):
        ridx = np.flatnonzero(dayv == np.datetime64(D.tz_localize(None) if D.tzinfo else D))
        if len(ridx) == 0:
            continue
        vol = np.zeros(nw_ids); pnl = np.zeros(nw_ids); nf = np.zeros(nw_ids); fo = np.zeros(nw_ids); act = np.zeros(nw_ids)
        for k in range(1, TRAIL_SKILL + 1):
            dd = D - pd.Timedelta(days=k)
            if dd in T2i:
                ix, v, p, f, n = T2i[dd]
                np.add.at(vol, ix, v); np.add.at(pnl, ix, p); np.add.at(fo, ix, f); np.add.at(nf, ix, n); np.add.at(act, ix, 1.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            skill = np.where((act >= MIN_ACTIVE) & (vol > 0), pnl / vol * nf / (nf + K_SHRINK), np.nan)
        cuts = None
        prev = D - pd.Timedelta(days=1)
        if prev in T2i:
            sp = skill[T2i[prev][0]]
            sp = sp[np.isfinite(sp)]
            if len(sp) >= 100:
                cuts = (float(np.percentile(sp, 10)), float(np.percentile(sp, 90)))
        frames = [x for x in (load_t1(wdir, D - pd.Timedelta(days=1)), load_t1(wdir, D)) if x is not None]
        T1 = pd.concat(frames, ignore_index=True)
        wid = allw.get_indexer(T1.wallet)
        assert (wid >= 0).all()
        ccodes, cnames = pd.factorize(T1.coin.astype(str))
        binms = ms_of(T1.bin)
        order = np.lexsort((binms, ccodes))
        c_o, b_o, w_o = ccodes[order], binms[order], wid[order]
        buy, sell = T1.taker_buy_usd.to_numpy(float)[order], T1.taker_sell_usd.to_numpy(float)[order]
        twp, ab, asl = T1.twap_usd.to_numpy(float)[order], T1.absorbed_buy_usd.to_numpy(float)[order], T1.absorbed_sell_usd.to_numpy(float)[order]
        key = c_o.astype(np.int64) * (1 << 42) + b_o // BIN_MS
        cmap = {c: i for i, c in enumerate(cnames)}
        # persistent sets per coin, for the two populations: trailing 7 days ending before D
        parts, have_days = [], 0
        for k in range(1, TRAIL_PERS + 1):
            x = load_t1(wdir, D - pd.Timedelta(days=k))
            if x is not None:
                have_days += 1
                parts.append(x.assign(n=x.taker_buy_usd + x.taker_sell_usd).groupby(["coin", "wallet"], observed=True).n.sum().reset_index())
        pers_all, pers_hum = {}, {}
        if have_days >= MIN_PERS_DAYS:
            pp = pd.concat(parts).groupby(["coin", "wallet"], observed=True).n.sum().reset_index()
            pp["coin"] = pp.coin.astype(str)
            pp["wid"] = allw.get_indexer(pp.wallet)
            pp = pp[pp.wid >= 0]
            for tag, d_ in (("all", pers_all), ("hum", pers_hum)):
                q = pp if tag == "all" else pp[~is_vault[pp.wid.to_numpy()]]
                q = q.assign(r=q.groupby("coin").n.rank(ascending=False, method="first"))
                q = q[q.r <= 10]
                for c, g in q.groupby("coin"):
                    d_[c] = g.wid.to_numpy()
        else:
            pers_all = pers_hum = None
        for r in ridx:
            c = coins[r]
            s = s_all[r]
            o_ms = int(t0ms[r])
            for wi, W in enumerate(WINS):
                lo_ms, hi_ms = o_ms - W * 60_000, o_ms
                if lo_ms < DATA_START_MS:
                    continue
                if ((holes_ms >= lo_ms) & (holes_ms < hi_ms)).any():
                    continue
                if c not in cmap:
                    cols = None
                else:
                    ci = cmap[c]
                    i0 = np.searchsorted(key, ci * (1 << 42) + lo_ms // BIN_MS)
                    i1 = np.searchsorted(key, ci * (1 << 42) + hi_ms // BIN_MS)
                    cols = slice(i0, i1)
                if cols is None or cols.stop <= cols.start:
                    w = np.zeros(0, np.int64); pu = np.zeros(0); bo = np.zeros(0); tw = np.zeros(0); aa = np.zeros(0)
                else:
                    w = w_o[cols]
                    pu = buy[cols] if s > 0 else sell[cols]
                    bo = buy[cols] + sell[cols]
                    tw = twp[cols]
                    aa = (asl[cols] if s > 0 else ab[cols])                      # absorbed USD on the side OPPOSITE the push
                vmask = is_vault[w] if len(w) else np.zeros(0, bool)
                tw_nan = bool(np.isnan(tw).any()) if len(tw) else (hi_ms - 60_000 < TWAP_FROM_MS)
                pa = pop_feats(w, pu, bo, tw, tw_nan, skill, cuts, fo, None if pers_all is None else pers_all.get(c, None))
                hm = ~vmask
                ph = pop_feats(w[hm], pu[hm], bo[hm], tw[hm], tw_nan, skill, cuts, fo, None if pers_hum is None else pers_hum.get(c, None))
                row = res[r, wi]
                row[:11], row[IX["push_total_all"]] = pa[:11], pa[11]
                row[11:22], row[IX["push_total_human"]] = ph[:11], ph[11]
                tot = pa[11]
                if tot > 0:
                    row[IX["vault_push_share"]] = float(pu[vmask].sum() / tot)
                    vab = float(aa[vmask].sum())
                    row[IX["vault_absorb_ratio"]] = vab / tot                  # unbounded: the vaults' absorbed USD can exceed the pushing taker USD (as backstop_ratio in G5)
                    row[IX["vault_absorb_share"]] = vab / (vab + tot)          # bounded in [0, 1]: absorbed / (absorbed + pushing)
        print(f"  [{a.date()}..{b.date()}] day {D.date()} rows {len(ridx)}  [{time.time() - t0:.0f}s]", flush=True)
    return res


def main():
    rows_f, wdir, out, miss, d0, d1 = sys.argv[1:7]
    a, b = pd.Timestamp(d0), pd.Timestamp(d1)
    rows = pd.read_parquet(rows_f)
    rows = rows[(pd.to_datetime(rows.day) >= a) & (pd.to_datetime(rows.day) < b)].reset_index(drop=True)
    mm = pd.read_parquet(miss)
    holes = ms_of(mm["minute"] if "minute" in mm else mm.iloc[:, 0])
    holes = np.unique((holes // BIN_MS) * BIN_MS)
    res = run_chunk(rows, wdir, holes, a, b)
    os.makedirs(out, exist_ok=True)
    np.savez_compressed(os.path.join(out, f"g6_{a:%Y%m%d}_{b:%Y%m%d}.npz"), unit=rows.unit.to_numpy(np.int8), ev=rows.ev.to_numpy(np.int64), leg=rows.leg.to_numpy(np.int8), res=res)
    print(f"[G6 chunk] {len(rows):,} rows -> {out}")


if __name__ == "__main__":
    main()
