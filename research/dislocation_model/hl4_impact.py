"""HL-EVENT1 Part B1: the flow impact model, fitted on the FIT PERIOD only, then frozen.

    python -u research/dislocation_model/hl4_impact.py

MODEL. 30-minute bars, all 204 non-factor coins pooled, coin fixed effects (within-coin demeaning of
every variable): y = coin residual return / the coin's trailing residual volatility, on
  imb  = (taker buy - taker sell) / (taker buy + taker sell) over the bar's 30 minutes
  frc  = (forced short-covering buys - forced long liquidations) / taker notional over the same minutes
(both ratios in [-1, 1], so already normalised). The residual return of bar b is r_coin(b) - beta(b-1) *
r_benchmark(b), with beta(b-1) the rolling beta known BEFORE the bar; the volatility scale is the std of
the 48 residual returns at bars b-48..b-1 (eventflow.py writes both per coin to ev_bars/). A bar is used
when every input is finite and the scale is positive, and only if its day is before CUT (2026-05-25).
Coefficients and coin intercepts are FROZEN and never refit on held-out data.

AT A TRIGGER (bar b, last 4 bars b-3..b, all inputs finite):
  predicted = sum_k (alpha_coin + b_imb * imb_k + b_frc * frc_k) * scale_k       (log units)
  actual    = sum_k residual_k
  explained_share = clip( (d * predicted) / (d * actual), -1, 2 ), NaN when |actual| < 1e-12
  unexplained_move = d * (actual - predicted) / sigma_event                        (sigma units)
d = sign(z): positive = in the direction the coin dislocated. The held-out R2 of the frozen model is printed
for display only.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import harness
import paths
import coinevents as ce
import eventflow as ef

OUT = os.path.join(paths.DATASETS, "ev_impact.npz")


def load_bars(coin):
    z = np.load(os.path.join(ef.BAR_DIR, f"{coin}.npz"))
    return {k: z[k] for k in z.files}


def design(b):
    ok = np.isfinite(b["resid"]) & np.isfinite(b["volscale"]) & (b["volscale"] > 0) & np.isfinite(b["imb"]) & np.isfinite(b["forced"])
    y = np.where(ok, b["resid"] / np.where(b["volscale"] > 0, b["volscale"], np.nan), np.nan)
    return ok, y, b["imb"], b["forced"]


def main():
    t0 = time.time()
    EV = pd.read_parquet(ce.EVENTS)
    panel, idx, V, cols = ce.load_panel()
    bar_day = idx.floor("D").to_numpy()
    cut = np.datetime64(harness.CUT)
    coins = sorted(EV.coin.unique())
    Xs, ys, cs, ds = [], [], [], []
    stats = {}
    for c in coins:
        b = load_bars(c)
        ok, y, x1, x2 = design(b)
        m = ok & (bar_day < cut)
        if m.sum() < 200:
            continue
        stats[c] = (y[m].mean(), x1[m].mean(), x2[m].mean())
        Xs.append(np.column_stack([x1[m] - stats[c][1], x2[m] - stats[c][2]])); ys.append(y[m] - stats[c][0])
        cs.append(np.full(int(m.sum()), len(stats) - 1)); ds.append(bar_day[m])
    X, y = np.vstack(Xs), np.concatenate(ys)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1 - ((y - X @ beta) ** 2).sum() / (y ** 2).sum()
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * ((y - X @ beta) ** 2).sum() / (len(y) - 2 - len(stats)))
    alpha = {c: stats[c][0] - beta[0] * stats[c][1] - beta[1] * stats[c][2] for c in stats}
    print(f"[IMPACT] fit period (bars before {pd.Timestamp(cut).date()}): {len(y):,} bars, {len(stats)} coins")
    print(f"  coefficients (per unit of the normalised regressor, in units of the coin's residual volatility): "
          f"imbalance {beta[0]:+.4f} (se {se[0]:.4f}), signed forced flow {beta[1]:+.4f} (se {se[1]:.4f}); within-coin R2 {r2:.4f}")
    # held-out R2 of the frozen model, display only
    ssr = sst = 0.0
    nho = 0
    for c in stats:
        b = load_bars(c)
        ok, yy, x1, x2 = design(b)
        m = ok & (bar_day >= cut)
        if m.any():
            e = yy[m] - (alpha[c] + beta[0] * x1[m] + beta[1] * x2[m])
            ssr += (e ** 2).sum(); sst += ((yy[m] - yy[m].mean()) ** 2).sum(); nho += int(m.sum())
    print(f"  frozen model on held-out bars (display only): {nho:,} bars, R2 {1 - ssr / sst:.4f}")
    # ------------------------------------------------------------ at the triggers
    nev = len(EV)
    expl = np.full(nev, np.nan); unexp = np.full(nev, np.nan)
    for c in coins:
        ev = EV[EV.coin == c]
        if c not in stats:
            continue
        b = load_bars(c)
        ok, yy, x1, x2 = design(b)
        pred = (alpha[c] + beta[0] * x1 + beta[1] * x2) * b["volscale"]
        bars = ev["bar"].to_numpy(int)
        k4 = bars[:, None] - np.arange(4)[None, :]
        good = (k4.min(1) >= 0) & ok[np.clip(k4, 0, len(ok) - 1)].all(1)
        P_ = np.where(good, pred[np.clip(k4, 0, len(pred) - 1)].sum(1), np.nan)
        A_ = np.where(good, b["resid"][np.clip(k4, 0, len(pred) - 1)].sum(1), np.nan)
        d = ev["d"].to_numpy(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            share = np.where(np.abs(A_) >= 1e-12, np.clip((d * P_) / (d * A_), -1, 2), np.nan)
            un = d * (A_ - P_) / ev["sigma"].to_numpy(float)
        expl[ev.event_id.to_numpy()], unexp[ev.event_id.to_numpy()] = share, un
    np.savez_compressed(OUT, explained_share=expl, unexplained_move=unexp, coef=beta, alpha_coins=np.array(list(alpha)),
                        alpha_vals=np.array(list(alpha.values())))
    print(f"  at the triggers: explained_share finite for {int(np.isfinite(expl).sum()):,} of {nev:,} events "
          f"(median {np.nanmedian(expl):.3f}, p10 {np.nanpercentile(expl, 10):.3f}, p90 {np.nanpercentile(expl, 90):.3f}; "
          f"{100 * np.nanmean(expl >= 1.999):.1f}% clipped at 2, {100 * np.nanmean(expl <= -0.999):.1f}% at -1); "
          f"unexplained_move median {np.nanmedian(unexp):+.3f} sigma, p10 {np.nanpercentile(unexp, 10):+.3f}, p90 {np.nanpercentile(unexp, 90):+.3f}  "
          f"[{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
