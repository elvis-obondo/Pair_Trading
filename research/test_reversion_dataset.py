"""Correctness tests for reversion_dataset before running it at scale."""
import sys; sys.path.insert(0, "/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
import reversion_dataset as rd

fails = []
def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        fails.append(name)

# ---------------------------------------------------------------- barriers
print("=== barrier logic ===")
# gap > 0 (spread above mu): take profit is DOWNWARD, adverse is UPWARD
mu, sigma, s0 = 0.0, 1.0, 2.0          # z = +2
tp_level = s0 - 0.8 * (s0 - mu)        # = 0.4
adv_level = s0 + 2.5 * sigma           # = 4.5 -- 2.5 sigma FROM ENTRY, per
                                       # generate_exit_signal, not from mu

o, bars, frac = rd._forward_outcome(np.array([1.5, 1.0, 0.3]), s0, mu, sigma)
check("hits take-profit going down", o == "take_profit" and bars == 3, f"{o} bars={bars}")

# Crosses the stop first, then would have reverted -- stop must win.
o, _, _ = rd._forward_outcome(np.array([4.6, 0.1]), s0, mu, sigma)
check("adverse touched FIRST beats later take-profit", o == "adverse", o)

# A wobble to 2.4 is NOT a stop under the live rule (stop sits at 4.5); the
# old fixed-level-from-mu version wrongly stopped here.
o, _, _ = rd._forward_outcome(np.array([2.4, 0.1]), s0, mu, sigma)
check("wobble short of the stop still reaches take-profit", o == "take_profit", o)

o, _, frac = rd._forward_outcome(np.array([1.9, 1.8, 1.7]), s0, mu, sigma)
check("neither barrier -> timeout", o == "timeout", o)
check("timeout reversion_frac sensible", abs(frac - (2.0 - 1.7) / 2.0) < 1e-12, f"{frac:.4f}")

# gap < 0 (spread below mu): mirrored
s0n = -2.0
o, _, _ = rd._forward_outcome(np.array([-1.5, -0.3]), s0n, mu, sigma)
check("mirrored: take-profit going up", o == "take_profit", o)
o, _, _ = rd._forward_outcome(np.array([-4.6]), s0n, mu, sigma)
check("mirrored: adverse going down", o == "adverse", o)

# ---------------------------------------------------------------- rolling fit
print("\n=== rolling beta/alpha ===")
rng = np.random.default_rng(0)
b_true, a_true = 1.7, 0.5
x = np.cumsum(rng.normal(0, 0.01, 2000)) + 10
y = a_true + b_true * x + rng.normal(0, 1e-9, 2000)   # near-exact linear
beta, alpha = rd.rolling_beta_alpha(y, x, 200)
check("beta recovered on exact linear data", abs(beta[500] - b_true) < 1e-4, f"{beta[500]:.6f}")
check("alpha recovered", abs(alpha[500] - a_true) < 1e-3, f"{alpha[500]:.6f}")
check("pre-window positions are NaN (no partial fits)",
      np.isnan(beta[:199]).all() and np.isfinite(beta[199]))

# ---------------------------------------------------------------- look-ahead
print("\n=== look-ahead safety ===")
# Build a pair, compute rows. Then CORRUPT the future beyond a cutoff and
# confirm rows dated before the cutoff are unchanged.
n = rd.MIN_JOINT_BARS + 20 * rd.BARS_PER_DAY
idx = pd.date_range("2026-01-01", periods=n, freq="30min")
pa = np.cumsum(rng.normal(0, 0.01, n)) + 5
pb = np.cumsum(rng.normal(0, 0.01, n)) + 5
base = pd.DataFrame({"A": pa, "B": pb}, index=idx)
rows_clean = pd.DataFrame(rd.build_pair_rows("A", "B", base))

cut = n - 5 * rd.BARS_PER_DAY
corrupt = base.copy()
corrupt.iloc[cut:, 0] += 100.0           # violently change the future only
rows_corrupt = pd.DataFrame(rd.build_pair_rows("A", "B", corrupt))

cut_date = idx[cut].normalize()
# Rows whose ENTRY and whole horizon sit before the corruption must be identical.
safe_date = cut_date - pd.Timedelta(days=2)
lc = rows_clean[rows_clean["date"] < safe_date].reset_index(drop=True)
lk = rows_corrupt[rows_corrupt["date"] < safe_date].reset_index(drop=True)
same = lc.equals(lk)
check("rows before the corrupted future are bit-identical", same,
      f"{len(lc)} rows compared")
if not same and len(lc) == len(lk):
    for c in lc.columns:
        if not lc[c].equals(lk[c]):
            print(f"      differing column: {c}")

# ---------------------------------------------------------------- signal sanity
print("\n=== does the label detect real mean reversion? ===")
def ou_series(n, theta, sigma, seed):
    r = np.random.default_rng(seed)
    s = np.zeros(n)
    for i in range(1, n):
        s[i] = s[i-1] - theta * s[i-1] + r.normal(0, sigma)
    return s

# One synthetic pair yields only ~12 candidate days, far too few to assert a
# rate on. Pool many independent replicates instead so the comparison is
# powered; the first version of this test asserted >60% off n=12 and failed on
# sampling noise, not on a defect.
n = rd.MIN_JOINT_BARS + 60 * rd.BARS_PER_DAY
idx = pd.date_range("2026-01-01", periods=n, freq="30min")

def pooled_rate(kind, n_reps=25):
    lab = []
    for s in range(n_reps):
        common = np.cumsum(np.random.default_rng(1000 + s).normal(0, 0.01, n)) + 5
        if kind == "mr":
            sp = ou_series(n, 0.05, 0.01, 2000 + s)
        else:
            sp = np.cumsum(np.random.default_rng(3000 + s).normal(0, 0.01, n))
        d = pd.DataFrame({"A": common + sp, "B": common}, index=idx)
        r = pd.DataFrame(rd.build_pair_rows("A", "B", d))
        if len(r):
            lab.extend(r.loc[r["label_tp"].notna(), "label_tp"].tolist())
    return np.mean(lab) if lab else np.nan, len(lab)

tp_mr, n_mr = pooled_rate("mr")
tp_rw, n_rw = pooled_rate("rw")

print(f"  mean-reverting spread: {n_mr} candidates, take-profit rate {tp_mr:.1%}")
print(f"  random-walk spread   : {n_rw} candidates, take-profit rate {tp_rw:.1%}")
check("adequately powered", min(n_mr, n_rw) >= 150, f"n_mr={n_mr}, n_rw={n_rw}")
check("mean-reverting scores higher than random walk", tp_mr > tp_rw,
      f"{tp_mr:.1%} vs {tp_rw:.1%}")
# A genuine OU with half-life ~14 bars inside a 48-bar horizon should clear a
# coin flip comfortably; the random walk should not.
check("mean-reverting beats a coin flip", tp_mr > 0.55, f"{tp_mr:.1%}")
check("random walk does NOT beat a coin flip", tp_rw < 0.5, f"{tp_rw:.1%}")

print()
print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
