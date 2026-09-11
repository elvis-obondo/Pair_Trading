"""Sweep ENTRY as well as exit, with out-of-sample validation as the headline.

The earlier 294-combination sweep held entry fixed at |z| >= 1.0 and varied
only the three exit numbers. That leaves the most obvious lever untested:
cost per trade is flat (~0.086 sigma) regardless of how stretched the spread
is at entry, while gross profit scales with the gap, so a wider entry should
have a structurally better profit-to-cost ratio even at a lower win rate.

Grid now: entry floor x entry ceiling x take-profit x stop x horizon.
The ceiling exists because a very large dislocation may be a broken
relationship rather than an extreme opportunity, and pooling those with
genuine stretches would hide either effect.

With thousands of combinations, in-sample best is meaningless -- some
configuration always looks good. So the reported answer is: pick on train,
score on test, and also report the hindsight-best on test as the ceiling no
real process could beat.
"""
import sys
sys.path.insert(0, "/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
import exit_sweep as es

ENTRY_FLOORS = [1.0, 1.5, 2.0, 2.5, 3.0]
ENTRY_CEILS = [2.0, 3.0, 5.0, np.inf]

d = pd.read_parquet("/Users/elvisobondo/Pair_Trading/research/exit_sweep_paths.parquet")
d["date"] = pd.to_datetime(d["date"])
d = d.sort_values("date").reset_index(drop=True)
d["absz"] = d["z"].abs()
cut = int(len(d) * 0.65)
train, test = d.iloc[:cut], d.iloc[cut:]
print(f"train {len(train)} trades to {train.date.max().date()}")
print(f"test  {len(test)} trades from {test.date.min().date()}\n")


def sweep_all(df):
    rows = []
    for lo in ENTRY_FLOORS:
        for hi in ENTRY_CEILS:
            if hi <= lo:
                continue
            sub = df[(df.absz >= lo) & (df.absz < hi)]
            if len(sub) < 2000:
                continue
            for F in es.TP_GRID:
                for S in es.STOP_GRID:
                    for H in es.HORIZON_GRID_HOURS:
                        pnl, w, l, t = es.evaluate(sub, F, S, H, True)
                        gross, _, _, _ = es.evaluate(sub, F, S, H, False)
                        rows.append({
                            "entry_min": lo, "entry_max": hi,
                            "tp": F, "stop": S, "h": H, "n": len(sub),
                            "win%": w.mean() * 100,
                            "net_sigma": pnl.mean(),
                            "gross_sigma": gross.mean(),
                            # what actually matters: % of notional
                            "net_pct_notional": (pnl * sub["sigma"]).mean() * 100,
                            "gross_pct_notional": (gross * sub["sigma"]).mean() * 100,
                        })
    return pd.DataFrame(rows)


s_tr = sweep_all(train)
print(f"evaluated {len(s_tr)} combinations\n")
print("=" * 100)
print("TOP 10 ON TRAIN (by net % of notional)")
print("=" * 100)
top = s_tr.sort_values("net_pct_notional", ascending=False).head(10)
print(top.round(4).to_string(index=False))

print()
print("=" * 100)
print("THOSE SAME CONFIGS, OUT OF SAMPLE")
print("=" * 100)
out = []
for _, r in top.iterrows():
    sub = test[(test.absz >= r.entry_min) & (test.absz < r.entry_max)]
    if len(sub) < 200:
        continue
    pnl, w, l, t = es.evaluate(sub, r.tp, r.stop, int(r.h), True)
    gross, _, _, _ = es.evaluate(sub, r.tp, r.stop, int(r.h), False)
    out.append({"entry": f"{r.entry_min}-{r.entry_max}", "tp": r.tp, "stop": r.stop,
                "h": int(r.h), "n_test": len(sub), "win%": w.mean() * 100,
                "train_net_pct": r.net_pct_notional,
                "OOS_gross_pct": (gross * sub["sigma"]).mean() * 100,
                "OOS_net_pct": (pnl * sub["sigma"]).mean() * 100})
o = pd.DataFrame(out)
print(o.round(4).to_string(index=False))

print()
print("=" * 100)
print("CEILING CHECK -- best config chosen ON the test set (hindsight, unbeatable)")
print("=" * 100)
s_te = sweep_all(test)
b = s_te.sort_values("net_pct_notional", ascending=False).head(5)
print(b.round(4).to_string(index=False))
print()
bg = s_te.sort_values("gross_pct_notional", ascending=False).head(3)
print("best GROSS on test:")
print(bg[["entry_min", "entry_max", "tp", "stop", "h", "n", "win%",
          "gross_pct_notional", "net_pct_notional"]].round(4).to_string(index=False))
