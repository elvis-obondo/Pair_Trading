"""HL-MASTER1 G7: derivatives state at t0 (open interest, funding, premium, minute-level ctx versions) and the vault inventory. Features only; both units.

    python -u research/dataset/master_g7.py > research/dataset/logs/master_g7.log

UNITS. asset_ctxs open_interest = the sum of |positions| over both sides = 2 x one-sided OI (planner ruling 2026-10-25); EVERY OI column here is in asset_ctxs units (gross), converted to USD with the
1-minute close labelled T + 29. One-sided OI = half. The reconstructed level (master_oi.py level stage, gate passed) adds UNITS x the fills-based change to the last observed value.
Cutoff o = the minute index of t0; a minute label m <= o - 1 is the last one a feature may use. Every column is per leg (a_ = leg A, b_ = leg B; coin unit: a_ = the coin) and, for the pair unit, d_<col> = a_ - b_.
OBSERVED OI (source asset_ctxs only; no reconstruction): oi_obs_usd = (last observed OI at or before o-1) x close; oi_obs_age = minutes since that observation; NaN when no observation within 120 minutes (limit set before
  looking at results); oi_obs_chg_{1h,6h,24h,7d} = value / value W earlier - 1 using the same rule at both ends.
RECONSTRUCTED OI: oi_rec_usd = the level path (observed anchor + fills-based change) x close at o-1; oi_rec_age = minutes since the anchor; oi_rec_in_gap = 1 if the anchor is more than 60 minutes old;
  oi_rec_chg_{1h,6h,24h,7d}; oi_over_taker_24h = oi_rec_usd / the 24 h taker notional.
FILLS-BASED CHANGE: oi_delta_{1h,6h,24h} = the sum of UNITS x oi_delta_coin over [o-W, o), in USD at the close, divided by oi_rec_usd (relative); the 24 h column is drift-exposed (median drift of the reconstruction against
  observed OI was 0 after the units definition, but the column is a plain flow quantity and is NaN if the window holds a hole minute).
FUNDING / PREMIUM (public fundingHistory API, one source across the window): the row stamped at hour H reports the hour that ENDED at H; at t0 only rows with time < t0 are used (a row stamped a few milliseconds after
  an hour mark is NOT available at that mark): fund_last, fund_mean_8h, fund_mean_24h, fund_mean_7d (means of the rows stamped within the last 8 / 24 / 168 hours (by time), NaN if fewer than 75% of the hours are present), prem_last, prem_chg_1h, prem_chg_24h
  (premium now minus 1 / 24 hours earlier), fund_age_h (hours since the last row).
MINUTE-LEVEL asset_ctxs (separate from the above; NaN where no snapshot within 5 minutes, never filled): ctx_funding_inst, ctx_premium_inst, ctx_basis = mark / oracle - 1, ctx_impact_spread_bp = 1e4 x (impact ask - impact bid) / mid,
  ctx_age_min.
VAULT INVENTORY (the four HLP liquidator wallets and, separately, the vault leader 0xdfc24b...; positions persist between fills; before a wallet's first fill in the window its position is the start position of that fill, and a wallet with no fill is 0): vault_net_usd = the signed net position of the four vaults at o-1 x close; vault_gross_usd =
  sum of |position|; vault_leader_usd; vault_share_of_oi = vault_gross_usd / oi_rec_usd (both gross); vault_net_chg_{1h,6h,24h} = vault_net_usd minus its value W earlier (USD).
OUTPUT: research/datasets/master/work/{pair,coin}/g7.parquet
"""
import os, sys, time, glob
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths
import flowfeat as ff
import master_oi as O

WORK = os.path.join(paths.DATASETS, "master", "work")
OI_LEVEL = os.path.join(paths.DATASETS, "oi_level")
OI_DIR = os.path.join(paths.DATASETS, "oi")
FUND = os.path.join(paths.DATASETS, "fundinghist")
CTX = os.path.join(paths.DATASETS, "ctxs")
UNITS = O.UNITS
OBS_LIMIT = 120
CTX_LIMIT = 5
BACKSTOP = ["0xb0a55f13d22f66e6d495ac98113841b2326e9540", "0x2e3d94f0562703b25c83308a05046ddaf9a8dd14", "0x5e177e5e39c0f4e421f5865a6d8beed8d921cb70", "0x2ed5c4484ea3ff8b57d5f2fb152a40d9f2b68308"]
LEADER = "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"
WCH = {"1h": 60, "6h": 360, "24h": 1440, "7d": 10080}
LEG_COLS = (["oi_obs_usd", "oi_obs_age"] + [f"oi_obs_chg_{k}" for k in WCH] + ["oi_rec_usd", "oi_rec_age", "oi_rec_in_gap"] + [f"oi_rec_chg_{k}" for k in WCH] + ["oi_over_taker_24h"]
            + ["oi_delta_1h", "oi_delta_6h", "oi_delta_24h"]
            + ["fund_last", "fund_mean_8h", "fund_mean_24h", "fund_mean_7d", "prem_last", "prem_chg_1h", "prem_chg_24h", "fund_age_h"]
            + ["ctx_funding_inst", "ctx_premium_inst", "ctx_basis", "ctx_impact_spread_bp", "ctx_age_min"]
            + ["vault_net_usd", "vault_gross_usd", "vault_leader_usd", "vault_share_of_oi", "vault_net_chg_1h", "vault_net_chg_6h", "vault_net_chg_24h"])
DIFF_COLS = [c for c in LEG_COLS if c not in ("oi_rec_in_gap",)]


def ffill_limit(a, limit):
    """Value of the last non-NaN at or before each index and its age in minutes; NaN beyond `limit` minutes."""
    m = np.arange(len(a))
    last = np.maximum.accumulate(np.where(np.isfinite(a), m, -1))
    age = np.where(last >= 0, m - last, np.nan)
    val = np.where((last >= 0) & (age <= limit), a[np.clip(last, 0, None)], np.nan)
    return val, np.where(np.isfinite(val), age, np.nan)


def load_ctx_dense(coins):
    """minute arrays (float32) of the ctx fields per coin from the day files."""
    need = ["funding", "premium", "oracle_px", "mark_px", "mid_px", "impact_bid_px", "impact_ask_px"]
    D = {c: {k: np.full(ff.N, np.nan, np.float32) for k in need} for c in coins}
    for f in sorted(os.listdir(CTX)):
        if not f.endswith(".parquet") or f.startswith("_"):
            continue
        d = pd.read_parquet(os.path.join(CTX, f), columns=["time", "coin"] + need)
        t = pd.to_datetime(d.time)
        on = ((t.dt.second == 0) & (t.dt.microsecond == 0)).to_numpy()
        d = d[on]
        m = O.minutes(d.time)
        ok = (m >= 0) & (m < ff.N)
        d, m = d[ok], m[ok]
        cc = d.coin.astype(str).to_numpy()
        for c in np.unique(cc):
            if c not in D:
                continue
            sel = cc == c
            for k in need:
                D[c][k][m[sel]] = d[k].to_numpy(np.float32)[sel]
    return D


def load_fund(c):
    p = os.path.join(FUND, f"{c}.parquet")
    if not os.path.exists(p):
        return None
    d = pd.read_parquet(p)
    return O.minutes(d.time), d.fundingRate.to_numpy(float), d.premium.to_numpy(float)


def vault_arrays(coins):
    """per coin: signed net position (4 backstop vaults), gross, leader (coin units) as dense forward-filled minute arrays."""
    parts = []
    for f in sorted(glob.glob(os.path.join(OI_DIR, "*_vault.parquet"))):
        parts.append(pd.read_parquet(f, columns=["wallet", "coin", "minute", "start_position", "end_position"]))
    V = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["wallet", "coin", "minute", "end_position"])
    V["m"] = O.minutes(V.minute)
    V["wallet"] = V.wallet.str.lower()
    out = {}
    for c, g in V.groupby(V.coin.astype(str)):
        if c not in coins:
            continue
        net, gross, lead = np.zeros(ff.N), np.zeros(ff.N), np.zeros(ff.N)
        for w, gw in g.groupby("wallet"):
            gw = gw.sort_values("m")
            pos = np.full(ff.N, np.nan)
            okm = gw.m.to_numpy() >= 0
            pos[gw.m.to_numpy()[okm]] = gw.end_position.to_numpy()[okm]
            f0 = int(gw.m.to_numpy()[okm][0]) if okm.any() else -1
            if f0 >= 1:
                pos[f0 - 1] = gw.start_position.to_numpy()[okm][0]              # the position before the wallet's first fill in the window
            last = np.maximum.accumulate(np.where(np.isfinite(pos), np.arange(ff.N), -1))
            p = np.where(last >= 0, pos[np.clip(last, 0, None)], 0.0)             # a position persists after its last fill
            if w in BACKSTOP:
                net += p; gross += np.abs(p)
            elif w == LEADER:
                lead += p
        out[c] = (net, gross, lead)
    return out


def leg_g7(c, o, A):
    """All leg columns of coin c at cutoffs o (n,). A: dict of the coin's arrays. Reads indices <= o - 1 only."""
    n = len(o)
    m = o - 1
    out = {}
    px = A["close"]
    price = px[m]
    # observed and reconstructed OI
    obs_val, obs_age = A["obs_val"], A["obs_age"]
    out["oi_obs_usd"] = obs_val[m] * price
    out["oi_obs_age"] = obs_age[m]
    for lab, W in WCH.items():
        mm = m - W
        ok = mm >= 0
        a, b = obs_val[m], obs_val[np.clip(mm, 0, None)]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"oi_obs_chg_{lab}"] = np.where(ok & (b > 0), a / b - 1, np.nan)
    lvl, since = A["lvl"], A["since"]
    out["oi_rec_usd"] = lvl[m] * price
    out["oi_rec_age"] = since[m]
    out["oi_rec_in_gap"] = np.where(np.isfinite(since[m]), (since[m] > 60).astype(float), np.nan)
    for lab, W in WCH.items():
        mm = m - W
        ok = mm >= 0
        a, b = lvl[m], lvl[np.clip(mm, 0, None)]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"oi_rec_chg_{lab}"] = np.where(ok & (b > 0), a / b - 1, np.nan)
    tk = A["tk24"][m]
    with np.errstate(invalid="ignore", divide="ignore"):
        out["oi_over_taker_24h"] = np.where(tk > 0, out["oi_rec_usd"] / tk, np.nan)
        for lab, W in (("1h", 60), ("6h", 360), ("24h", 1440)):
            ok = (o - W >= 0) & (A["hole_cs"][o] - A["hole_cs"][np.clip(o - W, 0, None)] == 0)
            d = UNITS * (A["cd"][o] - A["cd"][np.clip(o - W, 0, None)]) * price
            out[f"oi_delta_{lab}"] = np.where(ok & (out["oi_rec_usd"] > 0), d / out["oi_rec_usd"], np.nan)
    # funding / premium
    ft, fr, fp = A["fund"]
    if ft is not None and len(ft):
        pos = np.searchsorted(ft, o - 1, side="right") - 1                     # last row with minute label <= o - 1, i.e. time < t0
        has = pos >= 0
        pc = np.clip(pos, 0, None)
        age_h = np.where(has, (o - ft[pc]) / 60.0, np.nan)
        out["fund_last"] = np.where(has, fr[pc], np.nan)
        out["prem_last"] = np.where(has, fp[pc], np.nan)
        out["fund_age_h"] = age_h
        cs = np.concatenate([[0.0], np.cumsum(np.nan_to_num(fr))])
        cn = np.concatenate([[0], np.cumsum(np.isfinite(fr))])
        for lab, k in (("8h", 8), ("24h", 24), ("7d", 168)):
            lo = np.searchsorted(ft, ft[pc] - 60 * k, side="right")                 # the rows stamped within the last k hours (by time, not by position)
            cnt = cn[pc + 1] - cn[lo]
            out[f"fund_mean_{lab}"] = np.where(has & (cnt >= 0.75 * k), (cs[pc + 1] - cs[lo]) / np.maximum(cnt, 1), np.nan)
        for lab, k in (("1h", 1), ("24h", 24)):
            pk = np.clip(pc - k, 0, None)
            out[f"prem_chg_{lab}"] = np.where(has & (pos - k >= 0) & (np.abs(ft[pc] - ft[pk] - 60 * k) <= 5), fp[pc] - fp[pk], np.nan)
    else:
        for k in ("fund_last", "prem_last", "fund_age_h", "fund_mean_8h", "fund_mean_24h", "fund_mean_7d", "prem_chg_1h", "prem_chg_24h"):
            out[k] = np.full(n, np.nan)
    # minute-level ctx
    C = A["ctx"]
    out["ctx_funding_inst"], out["ctx_premium_inst"], out["ctx_basis"], out["ctx_impact_spread_bp"], out["ctx_age_min"] = (C[k][m] for k in ("funding", "premium", "basis", "spread", "age"))
    # vault
    if A["vault"] is not None:
        net, gross, lead = A["vault"]
        out["vault_net_usd"] = net[m] * price
        out["vault_gross_usd"] = gross[m] * price
        out["vault_leader_usd"] = lead[m] * price
        with np.errstate(invalid="ignore", divide="ignore"):
            out["vault_share_of_oi"] = np.where(out["oi_rec_usd"] > 0, out["vault_gross_usd"] / out["oi_rec_usd"], np.nan)
        for lab, W in (("1h", 60), ("6h", 360), ("24h", 1440)):
            mm = np.clip(m - W, 0, None)
            out[f"vault_net_chg_{lab}"] = np.where(m - W >= 0, out["vault_net_usd"] - net[mm] * px[mm], np.nan)
    else:
        for k in ("vault_net_usd", "vault_gross_usd", "vault_leader_usd", "vault_share_of_oi", "vault_net_chg_1h", "vault_net_chg_6h", "vault_net_chg_24h"):
            out[k] = np.where(np.isfinite(price), 0.0, np.nan)             # no vault fills for this coin: zero inventory
    return out


def load_raw_coin(c, ctx, cd_all, holes, vaults):
    """Everything leg_g7 needs for one coin as RAW arrays (no derived statistics)."""
    import evmarket as em
    R = {"lc": em.load_lc(c)}
    p = os.path.join(paths.DATASETS, "oi_level", f"{c}.parquet")
    R["obs_dense"] = O_obs_dense(c)
    R["cd"] = cd_all.get(c, np.zeros(ff.N + 1))
    R["hole_cs"] = holes
    fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date", "taker_buy_usd", "taker_sell_usd"])
    R["tn"] = ff.dense(fl, "taker_buy_usd") + ff.dense(fl, "taker_sell_usd")
    R["fund"] = load_fund(c) or (None, None, None)
    R["ctx"] = ctx[c]
    R["vault"] = vaults.get(c)
    return R


_OBS = {}


def O_obs_dense(c):
    """observed OI by minute (coin units; NaN where no snapshot), from asset_ctxs."""
    if not _OBS:
        _OBS.update(O.load_obs())
    return _OBS.get(c, np.full(ff.N, np.nan))


def assemble(R):
    """Derived arrays from the raw ones (pure)."""
    A = {"close": np.exp(R["lc"])}
    obs = R["obs_dense"]
    level, obs_last, since = O.level_path(obs, R["cd"])
    A["obs_val"] = np.where(since <= OBS_LIMIT, obs_last, np.nan)
    A["obs_age"] = np.where(since <= OBS_LIMIT, since, np.nan)
    A["lvl"], A["since"] = level, since
    A["cd"], A["hole_cs"] = R["cd"], R["hole_cs"]
    cs, nc = ff.cum_nan(R["tn"])
    tk24 = np.full(ff.N, np.nan)
    o_ = np.arange(1440, ff.N + 1)
    tk24[o_ - 1] = np.where((nc[o_] - nc[o_ - 1440]) == 0, cs[o_] - cs[o_ - 1440], np.nan)      # 24 h taker notional ending with minute o - 1
    A["tk24"] = tk24
    A["fund"] = R["fund"]
    X = R["ctx"]
    C = {}
    for k in ("funding", "premium"):
        C[k], age = ffill_limit(X[k].astype(np.float64), CTX_LIMIT)
    C["age"] = age
    ora, _ = ffill_limit(X["oracle_px"].astype(np.float64), CTX_LIMIT)
    mrk, _ = ffill_limit(X["mark_px"].astype(np.float64), CTX_LIMIT)
    mid, _ = ffill_limit(X["mid_px"].astype(np.float64), CTX_LIMIT)
    ib, _ = ffill_limit(X["impact_bid_px"].astype(np.float64), CTX_LIMIT)
    ia, _ = ffill_limit(X["impact_ask_px"].astype(np.float64), CTX_LIMIT)
    with np.errstate(invalid="ignore", divide="ignore"):
        C["basis"] = mrk / ora - 1
        C["spread"] = 1e4 * (ia - ib) / mid
    A["ctx"] = C
    A["vault"] = R["vault"]
    return A


def main():
    t0 = time.time()
    holes = O.hole_flags()
    units = {u: pd.read_parquet(os.path.join(WORK, u, "events.parquet"), columns=["event_id", "ticker_a", "ticker_b", "entry_time"]) for u in ("pair", "coin")}
    coins = sorted(set(units["pair"].ticker_a) | set(units["pair"].ticker_b) | set(units["coin"].ticker_a))
    print(f"[G7] {len(coins)} coins; loading ctx minute arrays ...", flush=True)
    ctx = load_ctx_dense(coins)
    print(f"[G7] ctx loaded  [{time.time() - t0:.0f}s]", flush=True)
    cd_all = O.load_delta()
    vaults = vault_arrays(set(coins))
    print(f"[G7] fills deltas and vault inventories loaded ({len(vaults)} coins with vault fills)  [{time.time() - t0:.0f}s]", flush=True)
    res = {u: {lg: {k: np.full(len(E), np.nan) for k in LEG_COLS} for lg in (("a", "b") if u == "pair" else ("a",))} for u, E in units.items()}
    for ci, c in enumerate(coins):
        A = assemble(load_raw_coin(c, ctx, cd_all, holes, vaults))
        for u, E in units.items():
            o_all = ff.minute_index(pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30))
            for lg, col in (("a", "ticker_a"), ("b", "ticker_b")) if u == "pair" else (("a", "ticker_a"),):
                sel = np.flatnonzero((E[col] == c).to_numpy())
                if not len(sel):
                    continue
                r = leg_g7(c, o_all[sel], A)
                for k, v in r.items():
                    res[u][lg][k][sel] = v
        if (ci + 1) % 20 == 0:
            print(f"  coin {ci + 1}/{len(coins)}  [{time.time() - t0:.0f}s]", flush=True)
    for u, E in units.items():
        G = {"event_id": E.event_id.to_numpy()}
        for lg, d in res[u].items():
            for k, v in d.items():
                G[f"{lg}_{k}"] = v.astype(np.float32)
        if u == "pair":
            for k in DIFF_COLS:
                G[f"d_{k}"] = (res[u]["a"][k] - res[u]["b"][k]).astype(np.float32)
        G = pd.DataFrame(G)
        G.to_parquet(os.path.join(WORK, u, "g7.parquet"), index=False)
        print(f"[G7 {u}] {len(G):,} rows x {len(G.columns) - 1} columns  [{time.time() - t0:.0f}s]")
        for k in ("oi_obs_usd", "oi_obs_age", "oi_rec_usd", "oi_rec_age", "oi_rec_chg_24h", "oi_over_taker_24h", "oi_delta_24h", "fund_last", "fund_mean_24h", "prem_last", "prem_chg_24h", "fund_age_h",
                  "ctx_funding_inst", "ctx_basis", "ctx_impact_spread_bp", "vault_net_usd", "vault_gross_usd", "vault_share_of_oi", "vault_net_chg_24h"):
            v = G[f"a_{k}"].to_numpy(float)
            f = np.isfinite(v)
            print(f"  a_{k:<22} NaN {100 * (~f).mean():6.2f}%  median {np.median(v[f]) if f.any() else np.nan:+.4g}  p5 {np.percentile(v[f], 5) if f.any() else np.nan:+.4g}  p95 {np.percentile(v[f], 95) if f.any() else np.nan:+.4g}")
        m = pd.to_datetime(E.entry_time).dt.to_period("M")
        print("  NaN share by month (a_oi_obs_usd, a_oi_rec_usd, a_fund_last, a_ctx_funding_inst):")
        print(G.assign(m=m.values).groupby("m")[["a_oi_obs_usd", "a_oi_rec_usd", "a_fund_last", "a_ctx_funding_inst"]].agg(lambda s: s.isna().mean()).round(4).to_string())


if __name__ == "__main__":
    main()
