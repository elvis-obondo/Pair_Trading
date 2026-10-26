"""HL-MASTER1 G6 orchestration: the leg rows of both units, parallel day chunks of master_g6.run_chunk, the net weights (G5's w_a), parquet output.

    python -u research/dataset/master_g6_run.py > research/dataset/logs/master_g6.log

Net columns: net(x) = wA x_A + wB x_B for the SHARES and MEANS (top1, top3, hhi, pers, twap, skill_mean, skill_cov, bot, topd, prior_forced, vault_push_share, vault_absorb_share; the ratio is netted too); the counts and USD
(nw_*, push_total_*) are kept per leg only (a weighted count is not a meaningful quantity). Coin unit: the coin leg only (a_).
skill_cov_p = the share of the population's pushing notional that comes from wallets with a defined (non-NaN) skill.
"""
import os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import master_g6 as G6
import paths

WORK = os.path.join(paths.DATASETS, "master", "work")
WDIR = os.path.join(paths.DATASETS, "wallet5")
MISSING = os.path.join(ROOT, "research", "hyperliquid", "logs", "build5_missing_minutes.parquet")
ROWS = os.path.join(WORK, "g6_rows.parquet")
TMP = os.path.join(WORK, "g6_tmp")
NO_NET = {"nw_all", "nw_human", "push_total_all", "push_total_human"}


def build_rows():
    parts = []
    for ui, u in enumerate(("pair", "coin")):
        E = pd.read_parquet(os.path.join(WORK, u, "events.parquet"), columns=["event_id", "ticker_a", "ticker_b", "entry_time", "d", "beta"])
        t0 = pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30)
        t0ms = G6.ms_of(t0)
        day = pd.to_datetime(E.entry_time).dt.floor("D").dt.strftime("%Y-%m-%d").to_numpy()
        d = E.d.to_numpy(float)
        parts.append(pd.DataFrame({"unit": np.int8(ui), "ev": np.arange(len(E), dtype=np.int64), "leg": np.int8(0), "coin": E.ticker_a.to_numpy(), "t0_ms": t0ms, "day": day, "s": d}))
        if u == "pair":
            parts.append(pd.DataFrame({"unit": np.int8(ui), "ev": np.arange(len(E), dtype=np.int64), "leg": np.int8(1), "coin": E.ticker_b.to_numpy(), "t0_ms": t0ms, "day": day,
                                       "s": -d * np.sign(E.beta.to_numpy(float))}))
    R = pd.concat(parts, ignore_index=True)
    R.to_parquet(ROWS, index=False)
    return R


def job(rng_days):
    d0, d1 = rng_days
    out = os.path.join(TMP)
    os.makedirs(out, exist_ok=True)
    f = os.path.join(out, f"g6_nf{G6.NF}_{d0.replace('-', '')}_{d1.replace('-', '')}.npz")
    if os.path.exists(f):
        return f
    rows = pd.read_parquet(ROWS, filters=[("day", ">=", d0), ("day", "<", d1)]).reset_index(drop=True)
    mm = pd.read_parquet(MISSING)
    holes = G6.ms_of(mm["minute"] if "minute" in mm else mm.iloc[:, 0])
    holes = np.unique((holes // G6.BIN_MS) * G6.BIN_MS)
    res = G6.run_chunk(rows, WDIR, holes, pd.Timestamp(d0), pd.Timestamp(d1))
    np.savez_compressed(f, unit=rows.unit.to_numpy(), ev=rows.ev.to_numpy(), leg=rows.leg.to_numpy(), res=res)
    return f


def main():
    t0 = time.time()
    R = build_rows()
    print(f"[G6] leg rows {len(R):,} (pair legs {int(((R.unit == 0)).sum()):,}, coin {int((R.unit == 1).sum()):,}); days {R.day.min()} .. {R.day.max()}  [{time.time() - t0:.0f}s]", flush=True)
    days = pd.date_range(R.day.min(), pd.Timestamp(R.day.max()) + pd.Timedelta(days=1), freq="D")
    edges = list(days[::10]) + [days[-1] + pd.Timedelta(days=1)]
    ranges = [(edges[i].strftime("%Y-%m-%d"), edges[i + 1].strftime("%Y-%m-%d")) for i in range(len(edges) - 1)]
    del R
    with Pool(int(os.environ.get("NPROC", 7))) as pool:
        files = []
        for q, f in enumerate(pool.imap_unordered(job, ranges)):
            files.append(f)
            print(f"  chunk {q + 1}/{len(ranges)} done  [{time.time() - t0:.0f}s]", flush=True)
    store = {}
    for u, n in (("pair", None), ("coin", None)):
        E = pd.read_parquet(os.path.join(WORK, u, "events.parquet"), columns=["event_id"])
        for lg in ((0, 1) if u == "pair" else (0,)):
            store[(u, lg)] = np.full((len(E), len(G6.WINS), G6.NF), np.nan, np.float32)
    for f in files:
        z = np.load(f)
        for ui, u in enumerate(("pair", "coin")):
            for lg in ((0, 1) if u == "pair" else (0,)):
                m = (z["unit"] == ui) & (z["leg"] == lg)
                store[(u, lg)][z["ev"][m]] = z["res"][m]
    sh = pd.read_parquet(os.path.join(WORK, "pair", "g5_shape.parquet"), columns=["w_a"]).w_a.to_numpy(float)
    names = [f"{nm}_{W}" for W in G6.WINS for nm in G6.NAMES]

    def frame(X, prefix, eid):
        cols = {f"{prefix}_{nm}_{W}": X[:, wi, G6.IX[nm]] for wi, W in enumerate(G6.WINS) for nm in G6.NAMES}
        df = pd.DataFrame(cols)
        df.insert(0, "event_id", eid)
        return df

    for u in ("pair", "coin"):
        E = pd.read_parquet(os.path.join(WORK, u, "events.parquet"), columns=["event_id"])
        eid = E.event_id.to_numpy()
        frame(store[(u, 0)], "a", eid).to_parquet(os.path.join(WORK, u, "g6_a.parquet"), index=False)
        if u == "pair":
            frame(store[(u, 1)], "b", eid).to_parquet(os.path.join(WORK, u, "g6_b.parquet"), index=False)
            XA, XB = store[(u, 0)].astype(np.float64), store[(u, 1)].astype(np.float64)
            wA = sh[:, None]
            wB = 1 - wA
            net = np.full(XA.shape, np.nan, np.float32)
            for nm, j in G6.IX.items():
                if nm in NO_NET:
                    continue
                xa, xb = XA[:, :, j], XB[:, :, j]
                a_ = np.where(wA > 0, wA * xa, 0.0); b_ = np.where(wB > 0, wB * xb, 0.0)
                bad = ((wA > 0) & ~np.isfinite(xa)) | ((wB > 0) & ~np.isfinite(xb)) | ~np.isfinite(wA)
                net[:, :, j] = np.where(bad, np.nan, a_ + b_)
            df = frame(net, "net", eid)
            df.drop(columns=[c for c in df.columns if any(c.startswith(f"net_{k}_") for k in NO_NET)]).to_parquet(os.path.join(WORK, u, "g6_net.parquet"), index=False)
        X = store[(u, 0)]
        print(f"[G6 {u}] written  [{time.time() - t0:.0f}s]")
        for nm in ("top1_all", "top1_human", "nw_all", "pers_all", "skill_mean_all", "skill_cov_all", "bot_all", "vault_push_share", "vault_absorb_ratio", "vault_absorb_share", "push_total_all"):
            for wi, W in ((1, 60), (3, 1440)):
                v = X[:, wi, G6.IX[nm]].astype(float)
                f = np.isfinite(v)
                print(f"  a_{nm}_{W:<5} NaN {100 * (~f).mean():6.2f}%  median {np.median(v[f]) if f.any() else np.nan:+.4g}  p5 {np.percentile(v[f], 5) if f.any() else np.nan:+.4g}  p95 {np.percentile(v[f], 95) if f.any() else np.nan:+.4g}")


if __name__ == "__main__":
    main()
