"""HL-MASTER1 G7: the API funding/premium series against asset_ctxs at the hour marks, BEFORE the API columns are used (brief). STOP rule fixed here before looking: correlation < 0.9 on the funding rate -> STOP.

    python -u research/dataset/master_funding_check.py > research/dataset/logs/master_funding_check.log

fundingHistory row stamped at hour H (a few ms after) reports the hour that ENDED at H. asset_ctxs `funding` is the snapshot's funding rate and `premium` its premium. For every coin and every hour mark H with both
an API row and a ctx snapshot at H - L (L = 0, 1, 2, 5, 10, 30, 59 minutes before the mark; the snapshot stamped at the hour itself is L = 0): correlation and median absolute difference of the funding rates (pooled over
coins and hours, and the share of coin-hours with an exact match to 1e-9) and of the premiums, for the L with the highest funding correlation. Only hours with complete ctx days. Reports the coins with the lowest correlation.
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g7 as G7
import master_oi as O
import flowfeat as ff
import paths


def main():
    t0 = time.time()
    coins = sorted(f[:-8] for f in os.listdir(G7.FUND) if f.endswith(".parquet"))
    ctx = G7.load_ctx_dense(coins)
    print(f"[FUNDING CHECK] {len(coins)} coins with API history; ctx loaded [{time.time() - t0:.0f}s]", flush=True)
    LAGS = (0, 1, 2, 5, 10, 30, 59)
    pool = {L: ([], [], [], []) for L in LAGS}
    percoin = {}
    for c in coins:
        d = pd.read_parquet(os.path.join(G7.FUND, f"{c}.parquet"))
        m = O.minutes(d.time)
        hour = m[(m >= 0) & (m < ff.N)]
        dd = d[(m >= 0) & (m < ff.N)]
        # stamp rounds to the hour mark: keep rows within 2 minutes of an hour mark
        for L in LAGS:
            idx = hour - L
            ok = idx >= 0
            cf, cp = ctx[c]["funding"][idx[ok]].astype(float), ctx[c]["premium"][idx[ok]].astype(float)
            af, ap = dd.fundingRate.to_numpy(float)[ok], dd.premium.to_numpy(float)[ok]
            g = np.isfinite(cf) & np.isfinite(af)
            pool[L][0].append(af[g]); pool[L][1].append(cf[g]); pool[L][2].append(ap[g & np.isfinite(cp)]); pool[L][3].append(cp[g & np.isfinite(cp)])
            if L == 0:
                percoin[c] = np.corrcoef(af[g], cf[g])[0, 1] if g.sum() > 50 and af[g].std() > 0 and cf[g].std() > 0 else np.nan
    best = None
    print(f"  {'L':>3}{'pairs':>12}{'corr funding':>15}{'median |diff|':>16}{'exact match':>13}{'corr premium':>15}{'median |diff| prem':>20}")
    for L in LAGS:
        af, cf, ap, cp = (np.concatenate(x) for x in pool[L])
        r = np.corrcoef(af, cf)[0, 1]
        rp = np.corrcoef(ap, cp)[0, 1] if len(ap) > 10 else np.nan
        print(f"  {L:>3}{len(af):>12,}{r:>15.5f}{np.median(np.abs(af - cf)):>16.3e}{100 * np.mean(np.abs(af - cf) < 1e-9):>12.2f}%{rp:>15.5f}{np.median(np.abs(ap - cp)) if len(ap) else np.nan:>20.3e}")
        if best is None or r > best[1]:
            best = (L, r)
    # per-coin correlation and exact-match share at the BEST lag (a pooled correlation can hide coins that disagree)
    pcb, exb = {}, {}
    for c in coins:
        d = pd.read_parquet(os.path.join(G7.FUND, f"{c}.parquet"))
        m = O.minutes(d.time)
        ok = (m >= 0) & (m < ff.N)
        idx = m[ok] - best[0]
        af = d.fundingRate.to_numpy(float)[ok]
        cf = ctx[c]["funding"][np.clip(idx, 0, None)].astype(float)
        g = np.isfinite(cf) & np.isfinite(af) & (idx >= 0)
        if g.sum() > 50:
            pcb[c] = np.corrcoef(af[g], cf[g])[0, 1] if af[g].std() > 0 and cf[g].std() > 0 else np.nan
            exb[c] = float(np.mean(np.abs(af[g] - cf[g]) < 1e-9))
    pcb, exb = pd.Series(pcb).sort_values(), pd.Series(exb)
    print(f"[FUNDING CHECK] per-coin at the best L = {best[0]}: correlation median {pcb.median():.5f}, 5% {pcb.quantile(.05):.5f}, min {pcb.min():.5f} ({pcb.index[0]}); coins below 0.99: {int((pcb < 0.99).sum())} of {len(pcb)}: "
          + ", ".join(f"{c} {v:.4f}" for c, v in pcb.head(8).items()) + f"; exact-match share per coin median {100 * exb.median():.1f}%, lowest " + ", ".join(f"{c} {100 * v:.1f}%" for c, v in exb.sort_values().head(5).items()))
    print("[FUNDING CHECK] the >= 0.9 rule (fixed before looking) gates FUNDING only; premium is reported, not gated (the API premium is an hourly average, the ctx premium is instantaneous)")
    pc = pd.Series(percoin).sort_values()
    print(f"[FUNDING CHECK] best L = {best[0]} (corr {best[1]:.5f}); per-coin correlation at L = 0: median {pc.median():.4f}; lowest: " + ", ".join(f"{c} {v:.3f}" for c, v in pc.head(8).items()))
    ok = best[1] >= 0.9
    print(f"[FUNDING CHECK] {'PASS' if ok else 'STOP'}: the best correlation is {best[1]:.5f} (rule: >= 0.9)  [{time.time() - t0:.0f}s]")
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
