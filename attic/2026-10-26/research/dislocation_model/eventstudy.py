"""HL-EVENT1 Part A4: does flow precede the trigger? Events minus matched controls.

    python -u research/dislocation_model/eventstudy.py

Everything below is FIXED before any result is read. Descriptive columns (all events) are for display;
the TEST is on the held-out halves only. CUT 2026-05-25; HO1 = event days before 2026-08-15, HO2 from
2026-08-15; an event's day is the UTC date of its trigger bar label T.

SERIES (8): imb, forced, open, close, top3, wallets, volume, twap (eventflow.py; each signed so that
positive = pushing the coin the way it dislocated). WINDOWS (5): P1 [-60,0), P2 [-360,-60), P3 [-1440,-360),
C6 [-360,0), C24 [-1440,0) minutes relative to t = 0 = T + 30 min.

STATISTIC. For an event with a finite value and at least one control with a finite value in control set k:
diff = event value - mean of its controls' values (matched, per event). The cell is the mean diff over the
events of a period, with a day-clustered 95% interval (300 resamples of event days).

CELLS: 8 series x 5 windows x 2 control sets x 2 held-out halves = 160. At 95% two-sided the expected number
of cells whose interval excludes zero by chance is 8.0 (4.0 per sign). A FINDING for a (series, window, set) =
the same sign and an interval excluding zero in BOTH halves. Expected directions (stated now, versus set 1
only): forced, volume, imb and open ELEVATED before triggers (+). Versus set 2 the differences are reported
without a sign assumption; close, top3, wallets and twap have no stated direction either. A finding in the
OPPOSITE direction to the stated one is reported as such, not as a pass.
The residual price (resid), the benchmark move (mk_idx) and the market liquidation ratio (mk_liq) are not
among the 8 tested series; resid is shown in the profile (it is large by construction: the trigger is a large
residual move).
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
from envelope import HO_BOUNDARY

TESTED = ["imb", "forced", "open", "close", "top3", "wallets", "volume", "twap"]
EXPECT_UP = {"imb", "forced", "open", "volume"}
N_BOOT = 300
OUT_TABLE = os.path.join(paths.DATASETS, "ev_table.parquet")
PNG = os.path.join(paths.RESEARCH, "dislocation_model", "logs", "hl4_profile.png")


def event_table():
    EV = pd.read_parquet(ce.EVENTS)
    T = np.load(ef.OUT_TARGET)
    for k in ("reach", "depth", "chance", "fin", "t_reach", "vol_48", "vol_48_1m", "nmiss_1m", "e_err"):
        EV[k] = T[k]
    EV["day"] = pd.to_datetime(EV["T"]).dt.floor("D")
    EV["vol_rank"] = EV.groupby("coin")["vol48"].rank(pct=True)
    EV["hour_c"] = EV["hour"]
    EV["weekday"] = (pd.to_datetime(EV["T"]) + pd.Timedelta(minutes=30)).dt.dayofweek
    EV.to_parquet(OUT_TABLE)
    return EV


def paired_diff(x_ev, x_pr, link_ev, nev):
    """Per-event (event value - mean of its finite control values); NaN where undefined."""
    fin = np.isfinite(x_pr)
    s = np.bincount(link_ev[fin], weights=x_pr[fin], minlength=nev)
    n = np.bincount(link_ev[fin], minlength=nev)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = np.where(n > 0, s / n, np.nan)
    return x_ev - m


def cell(diff, day, mask, rng):
    ok = mask & np.isfinite(diff)
    if ok.sum() < 30:
        return np.nan, np.nan, np.nan, int(ok.sum())
    d, v = day[ok], diff[ok]
    ud, inv = np.unique(d, return_inverse=True)
    sm = np.bincount(inv, weights=v); ct = np.bincount(inv).astype(float)
    pick = rng.integers(0, len(ud), size=(N_BOOT, len(ud)))
    bm = sm[pick].sum(1) / ct[pick].sum(1)
    lo, hi = np.percentile(bm, [2.5, 97.5])
    return float(v.mean()), float(lo), float(hi), int(ok.sum())


def main():
    t0 = time.time()
    EV = event_table()
    PR = pd.read_parquet(ce.PAIRS)
    Z = np.load(ef.OUT_SERIES)
    SEV, SPR = Z["ev"], Z["pr"]
    nev = len(EV)
    day = EV["day"].to_numpy()
    cut = np.datetime64(harness.CUT)
    per = {"fit": day < cut, "HO1": (day >= cut) & (day < HO_BOUNDARY), "HO2": day >= HO_BOUNDARY}
    ev_of_link = PR["event"].to_numpy(int)
    print("=" * 118)
    print("HL-EVENT1 PART A -- events and matched controls")
    print("=" * 118)
    ce.report(EV, PR, pd.read_parquet(ce.STATS_TABLE))
    fin = EV["fin"].to_numpy(bool)
    print()
    print(f"  TARGET population (build 3's rule: the 1-minute window finite for the coin and the benchmark): "
          f"{int(fin.sum()):,} of {int(EV.has_outcome.sum()):,} events with a 10h outcome window; lost to holes "
          f"{int(EV.has_outcome.sum() - fin.sum()):,} ({100 * (1 - fin.sum() / max(EV.has_outcome.sum(), 1)):.2f}%)")
    r, c = EV.reach.to_numpy(bool), EV.chance.to_numpy(float)
    for lbl, m in (("all", fin), ("fit", fin & per["fit"]), ("HO1", fin & per["HO1"]), ("HO2", fin & per["HO2"]),
                   ("|z| < 2", fin & (EV.z.abs() < 2)), ("|z| 2-3", fin & (EV.z.abs() >= 2) & (EV.z.abs() < 3)),
                   ("|z| >= 3", fin & (EV.z.abs() >= 3))):
        print(f"    {lbl:<10} n {int(m.sum()):>8,}  reach {r[m].mean():.4f}  mean chance {np.nanmean(c[m]):.4f}  gap {r[m].mean() - np.nanmean(c[m]):+.4f}")
    print(f"  1-minute path check: entry z reproduced, max abs error {np.nanmax(EV.e_err):.2e}")
    cells = 8 * 5 * 2 * 2
    print()
    print(f"CELLS: 8 series x 5 windows x 2 control sets x 2 held-out halves = {cells}; expected by chance at 95% two-sided: "
          f"{0.05 * cells:.1f} ({0.025 * cells:.1f} per sign)")
    rng = np.random.default_rng(20261015)
    res = {}
    print(f"  {'series':<8}{'win':<5}{'set':<4}{'fit (display)':>26}{'HO1':>30}{'HO2':>30}   verdict")
    for s in TESTED:
        si = ef.SER.index(s)
        for w in ef.WN:
            wi = ef.WN.index(w)
            for k in (1, 2):
                m = (PR["set"].to_numpy() == k)
                x_pr = np.full(len(PR), np.nan)
                x_pr[m] = SPR[m, si, wi]
                diff = paired_diff(SEV[:, si, wi].astype(float), x_pr, ev_of_link, nev)
                row = {pn: cell(diff, day, pm, rng) for pn, pm in per.items()}
                res[(s, w, k)] = row
                f = lambda t: f"{t[0]:+.4f} [{t[1]:+.4f},{t[2]:+.4f}] n={t[3]:,}"
                a, b = row["HO1"], row["HO2"]
                both_pos = a[1] > 0 and b[1] > 0
                both_neg = a[2] < 0 and b[2] < 0
                verdict = "FINDING +" if both_pos else "FINDING -" if both_neg else ""
                if verdict and k == 1 and s in EXPECT_UP:
                    verdict += " (as stated)" if both_pos else " (OPPOSITE to stated)"
                print(f"  {s:<8}{w:<5}{k:<4}{f(row['fit']):>26}{f(a):>30}{f(b):>30}   {verdict}")
    hits = [(k_, "+") for k_, r_ in res.items() if r_["HO1"][1] > 0 and r_["HO2"][1] > 0] + \
           [(k_, "-") for k_, r_ in res.items() if r_["HO1"][2] < 0 and r_["HO2"][2] < 0]
    one_half = sum(1 for r_ in res.values() for h in ("HO1", "HO2") if r_[h][1] > 0 or r_[h][2] < 0)
    print()
    print(f"  CELLS with an interval excluding zero (either half, either sign): {one_half} of {cells} "
          f"(expected by chance {0.05 * cells:.1f}); FINDINGS (both halves, same sign): {len(hits)} of 40 (series x window x set)")
    print(f"  chance baseline for a both-halves finding: 40 units x 2 signs x 0.025^2 = {40 * 2 * 0.025 ** 2:.2f} expected by chance "
          f"(under independence), against {len(hits)} found")
    for (s, w, k), sg in hits:
        print(f"    FINDING {sg}: {s} {w} vs set {k}")
    print()
    print("  Q1 SUMMARY, one line per series (set 1, held-out halves; '+' = elevated before triggers)")
    for s in TESTED:
        parts = []
        for w in ef.WN:
            r_ = res[(s, w, 1)]
            sg = "+" if (r_["HO1"][1] > 0 and r_["HO2"][1] > 0) else "-" if (r_["HO1"][2] < 0 and r_["HO2"][2] < 0) else \
                 "~" if (r_["HO1"][1] > 0 or r_["HO2"][1] > 0 or r_["HO1"][2] < 0 or r_["HO2"][2] < 0) else "0"
            parts.append(f"{w}:{sg}")
        print(f"    {s:<8}" + "  ".join(parts) + "   (+ / - both halves, ~ one half, 0 neither)")
    plot_profile()
    print(f"  [{time.time() - t0:.0f}s]")


def plot_profile():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    P = np.load(ef.OUT_PROFILE)
    ctr = ef.EDGES + ef.WIDTH / 2.0
    fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=False)
    names = ["net taker imbalance (signed by d)", "forced share on the pushing side", "residual price (signed by d), 30-minute bars"]
    for gi, (lbl, col) in enumerate((("events", "k"), ("controls, set 1", "tab:blue"), ("controls, set 2 (near-miss)", "tab:orange"))):
        for si in range(2):
            with np.errstate(invalid="ignore", divide="ignore"):
                y = P[f"g{gi}_sum"][si] / P[f"g{gi}_cnt"][si]
            ax[si].plot(ctr, y, color=col, lw=1, label=lbl)
        with np.errstate(invalid="ignore", divide="ignore"):
            yp = P[f"g{gi}_psum"] / P[f"g{gi}_pcnt"]
        ax[2].plot(P["bark"] * 30 + 30 * 0, yp, color=col, lw=1, marker=".", label=lbl)
    for a_, nm in zip(ax, names):
        a_.axvline(0, color="grey", lw=0.5); a_.set_title(nm); a_.set_xlabel("minutes relative to t = 0 (T + 30 min)")
    ax[0].legend()
    plt.tight_layout()
    plt.savefig(PNG, dpi=110)
    print(f"  [WROTE] {os.path.relpath(PNG, paths.RESEARCH)}")


if __name__ == "__main__":
    main()
