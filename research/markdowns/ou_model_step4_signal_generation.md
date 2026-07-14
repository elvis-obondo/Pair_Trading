# Step 4 — Entry Signal Generation
## Crypto Pairs Trading Research System | OKX Futures | 1h OHLCV

---

## 1. Purpose of Step 4

Steps 1–3 built the modelling layer: fitting OU parameters, characterising residual
quality, and computing forward-looking spread distributions and crossing probabilities.
Each of those produces a number. Step 4 decides what those numbers mean for a
trade entry.

**The problem Step 4 solves:** without a unified gate structure, every entry decision
requires manually inspecting theta significance, cointegration recency, volatility
regime, and reversion probability separately and combining them ad hoc. That process
is inconsistent, hard to backtest, and prone to confirmation bias (stopping when you
like the answer). A gate-based signal generator forces all checks to pass before any
entry is produced, and makes the pass/fail logic auditable.

**What Step 4 consumes from prior steps:**

| Source | What is consumed |
|--------|-----------------|
| `fit_ou` (Step 1) | $\theta$, $\mu$, $\sigma$ — the OU parameters that all gate computations depend on |
| `ou_residual_diagnostics` (Step 2) | `theta_p` — statistical significance of mean reversion |
| `ou_reversion_probability` (Step 3) | Forward crossing probability with known ~6–7pp overestimate vs hourly-bar execution |
| `trade_diagnostics.py` | `pre_entry_coint_check` and `spread_volatility_regime` — pre-entry regime checks |

**What Step 4 produces:** `generate_entry_signal` returns either `None` (any gate
failed — no trade) or a `dict` of entry metadata that a position manager in Step 5
can act on directly.

---

## 2. Prerequisite Refactor — `spread_volatility_regime`

Before building `signal_generator.py`, `spread_volatility_regime` in
`trade_diagnostics.py` was refactored. The new signal generator depends on the
refactored form.

### What the old function did

```python
# Old signature
def spread_volatility_regime(zscore: np.ndarray, window: int = 168) -> float:
    ...
    return current_std / full_std
```

Inputs were z-scores (not raw spread values). The denominator was `full_std` —
the standard deviation over the entire history passed in. The output was a ratio of
recent volatility to full-window volatility.

### Why it was refactored

Two problems with the old design:

1. **Self-referential denominator.** `full_std` is computed from the same data as
   `current_std`, so the ratio measures relative volatility within the passed-in
   window, not volatility relative to any model expectation. A spread that is
   uniformly volatile over the whole window returns a ratio near 1.0 regardless of
   whether that volatility is large or small.

2. **Wrong input type.** Accepting z-scores requires the caller to standardise the
   spread before passing it in, breaking the convention that `compute_spread` is the
   single source of truth for spread values. The signal generator works with raw
   spread values throughout; a z-score-accepting function would require a detour.

The fix: anchor the denominator to the fitted OU $\sigma$ from `fit_ou`. The function
now knows what "normal" volatility looks like in absolute terms, not relative to
itself.

### What changed

| Aspect | Old | New |
|--------|-----|-----|
| Input | `zscore: np.ndarray` (z-score values) | `spread: np.ndarray` (raw spread units) |
| New parameter | — | `sigma: float` — fitted OU $\sigma$ from `fit_ou` |
| Return | `current\_std / full\_std` | `log(current\_std / sigma)` |
| nan conditions | `len < window`, `full_std == 0` | `len < window`, `not isfinite(sigma)`, `sigma <= 0`, `current_std == 0` |

### The log ratio — why not raw ratio or normalised difference

**Raw ratio** $r = \text{current\_std} / \sigma$ is asymmetric: a ratio of 3.0
(3x elevated) is as far from 1.0 as a ratio of 1.0 is from $1/3$ — but the raw
ratio distances are 2.0 and 0.67. Thresholds set on a raw ratio treat elevated and
quiet regimes on different scales.

**Normalised difference** $(r - 1)/(r + 1)$ is bounded in $(-1, 1)$ but produces
thresholds with no intuitive interpretation. What does "greater than 0.5" mean in
volatility terms?

**Log ratio** $\ln(\text{current\_std} / \sigma)$ is symmetric around zero by
construction: a ratio of $k$ and a ratio of $1/k$ are equidistant from zero.
Zero means current volatility exactly matches the fitted model. The sign is directly
interpretable.

$$\text{regime} = \ln\!\left(\frac{\text{std}(S[-\text{window}:])}{\sigma}\right)$$

### Sign and magnitude interpretation

| Value | Meaning | current\_std relative to $\sigma$ |
|-------|---------|----------------------------------|
| $0.0$ | Neutral — model accurate | $1\times$ |
| $+0.4$ | Moderately elevated | $\approx 1.5\times$ |
| $+0.7$ | Significantly elevated | $\approx 2\times$ |
| $+1.1$ | Severely elevated | $\approx 3\times$ |
| $-0.7$ | Significantly quiet | $\approx 0.5\times$ |

The default Gate 5 threshold is 1.1 — below this, $\text{recent\_std} < 3\sigma$.

### No threshold baked in

`spread_volatility_regime` returns a float. It does not return `True/False`. This is
consistent with the pure functions philosophy documented in Step 1: the function
computes a quantity; the caller sets the strategy-level threshold. A backtest might
tighten to 0.7; a live strategy might loosen to 1.5 in low-volatility markets.

### Known limitation

$\sigma$ is fitted on the same 30-day window used for the regime check. If elevated
volatility is **persistent across the full 30-day window**, `fit_ou` absorbs that
volatility into a larger $\sigma$, deflating the log ratio back toward zero. The gate
catches short-lived volatility spikes relative to a stable baseline — it does not
detect a persistent regime shift where the spread has been continuously erratic.
This limitation is validated empirically in §6.

---

## 3. `signal_generator.py` — Design Decisions

### Why a new file

`signal_generator.py` imports from both `ou_model.py` and `trade_diagnostics.py`.
Placing `generate_entry_signal` in either of those files would create a one-way
dependency that risks a circular import as the system grows, and would mix model
fitting with entry logic in the same module. A separate file keeps the concerns
separated: `ou_model.py` fits and forecasts, `trade_diagnostics.py` runs pre-entry
checks, `signal_generator.py` combines them into a trade decision.

### Why individual float parameters over a config dict or dataclass

Each parameter has a specific type, a default with documented rationale, and a
direct role in one gate. A config dict or `SignalConfig` dataclass would add
abstraction without adding clarity. Individual parameters also make function
signatures self-documenting in IDE autocompletion and stack traces.

### Why `None` over a boolean flag or exception

`None` is the idiomatic Python sentinel for "no result." The caller can do:

```python
signal = generate_entry_signal(price_a, price_b)
if signal is not None:
    enter_trade(**signal)
```

A boolean flag (`did_signal_fire: bool`) forces a second call to retrieve the
metadata. An exception on gate failure conflates control flow with error handling
and forces the caller into a try/except block for a routine non-error condition.

### Why gate ordering matters

The five gates are not computationally equivalent. Cheapest first:

| Gate | Dominant cost |
|------|--------------|
| Input prep (Gate 1) | Array copy + boolean mask — negligible |
| Cointegration (Gate 2) | `statsmodels.coint` on 168 bars — ~10ms |
| OU fit (Gate 3) | `np.polyfit` on 700 bars — <1ms |
| Theta significance (Gate 4) | `_fit_ou_internals` + JB + Ljung-Box — ~10ms |
| Volatility regime (Gate 5) | `np.std` on 168 bars — negligible |
| Reversion probability (Gate 6) | `norm.cdf` — negligible |

In practice the order is mostly cost-driven. Cointegration (Gate 2) and theta
diagnostics (Gate 4) are the two expensive calls; they gate on the cheapest
checks first (input prep and OU fit validity).

---

## 4. The Six Gates — `generate_entry_signal`

```python
def generate_entry_signal(
    price_a: np.ndarray,
    price_b: np.ndarray,
    coint_p_threshold: float = 0.10,
    regime_threshold: float = 1.1,
    prob_threshold: float = 0.67,
    theta_p_threshold: float = 0.05,
    take_profit_pct: float = 0.80,
    f: float = 0.20,
) -> dict | None:
```

---

### Gate 1 — Input preparation

```python
spread_arr, _ = compute_spread(price_a, price_b)
S = np.asarray(spread_arr, dtype=float)
S = S[np.isfinite(S)]
if len(S) < 3:
    return None
S0 = float(S[-1])
```

Not a strategy filter — a data quality guard. `compute_spread` uses OLS and returns
a full-length array; non-finite values can arise from missing price data. `S` after
stripping is the clean spread used in all subsequent computations. `len(S) < 3`
is the minimum for any downstream OLS (two differences needed for the AR(1)).

**Trading meaning:** if fewer than 3 finite spread observations exist, the pair has
no tradeable history on this window.

---

### Gate 2 — Cointegration check

```python
coint_p = pre_entry_coint_check(price_a, price_b)   # window=168 default
if np.isnan(coint_p) or coint_p > coint_p_threshold:
    return None
```

Default: `coint_p_threshold=0.10`.

`pre_entry_coint_check` runs Engle-Granger cointegration on the last 168 bars (7
days). The 30-day pair screening in `pair_analysis.analyze_top_pairs` already
filtered on full-window cointegration. This gate asks a different question: is the
cointegrating relationship still intact in the most recent 7 days?

**Trading meaning:** the pair passed long-run screening but may be breaking down
right now. A p-value above 10% on the last 168 bars means the spread is not
behaving as cointegrated in the current regime — enter here and you are relying on
a relationship that may no longer exist.

---

### Gate 3 — OU fit validity

```python
params = fit_ou(price_a, price_b)
if np.isnan(params.theta):
    return None
```

`fit_ou` returns `OUParams(nan, nan, nan)` when the AR(1) slope is non-negative
(spread is trending or flat). `np.isnan(params.theta)` catches all degenerate cases
documented in Step 1: fewer than 3 finite values, zero variance in lagged spread,
or fitted $\hat{\lambda} \geq 0$.

**Trading meaning:** the spread does not mean-revert in this window. Without a
positive $\theta$, every downstream formula — crossing probability, expected
reversion time, take-profit level — is undefined or misleading. No trade.

---

### Gate 4 — Theta significance

```python
diag = ou_residual_diagnostics(price_a, price_b)
if np.isnan(diag.theta_p) or diag.theta_p > theta_p_threshold:
    return None
```

Default: `theta_p_threshold=0.05`.

`theta_p` is the two-sided p-value for $H_0: \theta = 0$ from the AR(1) t-test
(computed in `ou_residual_diagnostics` — see Step 2). Gate 3 checks that $\hat{\theta} > 0$;
Gate 4 checks that this estimate is statistically distinguishable from zero.

A spread can have $\hat{\theta} = 0.002$ with $p = 0.4$ — technically positive
mean reversion, but indistinguishable from noise at $n=720$. This gate blocks such
cases.

**Trading meaning:** mean reversion may be a sampling artefact rather than a
structural feature. Entering on an insignificant $\theta$ is equivalent to trading
on noise. AVAX/LINK clears this gate easily (`theta_p≈0`, `theta_tstat=4.25` per
Step 2 validation).

---

### Gate 5 — Volatility regime

```python
regime = spread_volatility_regime(S, params.sigma)
if np.isnan(regime) or regime > regime_threshold:
    return None
```

Default: `regime_threshold=1.1` (approximately $3\times\sigma$ in recent std).

Uses the refactored `spread_volatility_regime` documented in §2. At `regime > 1.1`,
the recent spread is more than 3 standard deviations wilder than the fitted OU noise
parameter. In this regime, the OU parameters are unreliable — the model was fitted
on a calmer baseline than what the spread is currently doing.

**Trading meaning:** the spread is too erratic relative to model expectations.
The $\sigma$ used in all probability computations was estimated from the 30-day
baseline; if current volatility is $3\times$ that baseline, the confidence intervals
and crossing probabilities from Step 3 are meaningless. See §6 for the known
limitation on persistent volatility.

---

### Gate 6 — Reversion probability

```python
tau  = np.log(1.0 / f) / params.theta
prob = ou_reversion_probability(S0, params.theta, params.mu, params.sigma, tau)
if np.isnan(prob) or prob < prob_threshold:
    return None
```

Default: `prob_threshold=0.67`, `f=0.20`.

**The horizon $\tau$:** rather than a fixed calendar horizon, $\tau$ is derived from
$f$ — the fraction of the initial deviation expected to remain at end of hold:

$$\tau = \frac{\ln(1/f)}{\theta}$$

With $f=0.20$: this is the time for the deterministic drift to decay the deviation to
20% of its original size — i.e., 80% of the move captured by pure drift alone. For
$\theta=0.0474$: $\tau = \ln(5)/0.0474 \approx 33.9$ hours.

**The threshold 0.67:** targets a true crossing probability of approximately 60%.
Step 3 Monte Carlo validation established that `ou_reversion_probability` (reflection
principle) overestimates the hourly-bar-observable crossing rate by ~6–7pp for
AVAX/LINK parameters. Setting the gate at 0.67 analytical corresponds to
$0.67 - 0.067 \approx 0.60$ empirical probability of hitting $\mu$ within $\tau$.
This is not a break-even calculation — it is an entry confidence floor. Empirical
calibration against backtests is needed to validate whether 0.60 true probability
is sufficient given position sizing and transaction costs.

**Trading meaning:** insufficient analytical confidence that the trade will reach
its target within the holding horizon. Below 0.67, the spread is not displaced
far enough, $\theta$ is too slow, or $\sigma$ is too large for the position to be
worth taking at the default risk parameters.

---

## 5. Entry Signal Return Dict

When all gates pass, `generate_entry_signal` returns:

```python
{
    "entry_spread":            float(S0),
    "reversion_probability":   float(prob),
    "expected_reversion_time": float(np.log(1.0 / f) / params.theta),
    "mu_at_entry":             float(params.mu),
    "sigma_at_entry":          float(params.sigma),
    "take_profit_level":       float(S0 - take_profit_pct * (S0 - params.mu)),
    "regime_log_ratio":        float(regime),
}
```

---

**`entry_spread`** — `float(S[-1])`, the last finite spread value at signal time.

The reference point for everything downstream: take-profit distance, P&L tracking,
and post-trade spread path analysis. Stored as a float rather than a z-score to
avoid the z-score instability problem documented in §2.

---

**`reversion_probability`** — output of `ou_reversion_probability`.

Entry confidence metric. The analytical value; recall the ~6–7pp overestimate
from Step 3. A reported probability of 0.80 corresponds to approximately 0.73
empirical probability of crossing $\mu$ within $\tau$ hours at hourly bar resolution.
Stored in the dict for use as a position sizing weight in Step 5 (higher probability
→ larger allocation, up to the full Kelly fraction).

---

**`expected_reversion_time`** — $\ln(1/f) / \theta$ in hours.

This equals $\tau$ by construction: both `tau` (used in `ou_reversion_probability`)
and `expected_reversion_time` (stored in the dict) are computed from the same
formula. They are the same quantity. The name conveys its use in Step 5 as the
primary time stop: if the spread has not reverted within `expected_reversion_time`
hours, the position is at or past its expected resolution window and should be
reviewed or exited.

*Note:* this is not the same as `ou_expected_reversion_time` from Step 3, which uses
a mathematical tolerance $\epsilon$ and ignores $\sigma$. The Step 4 quantity is a
trading-appropriate horizon derived from $f$.

---

**`mu_at_entry`** — `params.mu`, fitted OU long-run mean.

The target the spread is expected to revert to. Used directly in `take_profit_level`
and in post-trade analysis to assess whether the fitted $\mu$ shifted over the
holding period (indicating a regime change during the trade).

---

**`sigma_at_entry`** — `params.sigma`, fitted OU noise parameter.

The noise level at entry time. Primary input to Step 5 position sizing. **Important
caveat from Step 2:** excess kurtosis of 2.61 for AVAX/LINK means `sigma_at_entry`
understates tail risk. Position sizing in Step 5 must apply a kurtosis adjustment —
$\sigma$ alone predicts extreme move frequencies consistent with a Gaussian; actual
extremes are materially more frequent.

Stored at entry because `sigma` can shift between entry and exit, and post-trade
attribution needs the value that was used to size the position.

---

**`take_profit_level`** — $S_0 - \alpha(S_0 - \mu)$ where $\alpha = \texttt{take\_profit\_pct}$.

$$\text{TP} = S_0 - 0.80\,(S_0 - \mu)$$

This formula handles both directions without conditioning:

- $S_0 > \mu$ (spread above mean): $S_0 - \mu > 0$, so TP is below $S_0$, above $\mu$.
- $S_0 < \mu$ (spread below mean): $S_0 - \mu < 0$, so TP is above $S_0$, below $\mu$.

In both cases, the take-profit is 80% of the way from entry to $\mu$. The final
20% of the move is intentionally excluded: as the spread approaches $\mu$, the
deterministic drift weakens ($e^{-\theta\tau}$ shrinks) while noise is constant.
The risk/reward of holding for the last 20% is materially worse than the first 80%.

**Sanity check:** `pct_captured = abs(S0 - TP) / abs(S0 - mu) = 0.8000` (validated
to four decimal places in `validate_signal_generator.py`).

---

**`regime_log_ratio`** — output of `spread_volatility_regime` at entry time.

Not used in the entry decision (Gate 5 already passed it). Stored for post-trade
analysis: by filtering backtested trades by `regime_log_ratio`, Step 6 can assess
whether trades entered in elevated-regime conditions (e.g., `regime > 0.7`) have
worse outcomes than calm-regime trades. This is the primary use case for storing
a Gate 5 output that already passed.

---

### 5.1 Alpha propagation refactor — `compute_spread`

`compute_spread` in `pair_analysis.py` previously returned `(spread, beta)` where
`beta` is the OLS hedge ratio. It now returns `(spread, beta, alpha)` where `alpha`
is the OLS intercept.

**Why alpha was not surfaced before:** the original callers only needed the spread
and the hedge ratio. `np.polyfit` returns both slope and intercept simultaneously
(`beta, alpha = np.polyfit(price_b, price_a, 1)`), but `alpha` was discarded at the
return statement. The refactor costs nothing — no computation is added; the existing
variable is simply included in the return tuple.

**Why alpha must be surfaced:** `generate_exit_signal` needs to reconstruct the
current spread using the coefficients frozen at entry:

$$\text{current\_spread} = \text{price\_a} - \alpha_{\text{entry}} - \beta_{\text{entry}} \times \text{price\_b}$$

Without `alpha` in the return, there is no source of truth for the intercept at
entry time. Re-running OLS at exit to obtain it would re-estimate the intercept
on new data — defeating the purpose of freezing the hedge ratio.

**Rationale for not refactoring `compute_spread` beyond the return statement:**
the function is called in many places and the change must be mechanical and
auditable. The body of `compute_spread` is unchanged; only the return statement is
extended.

**Six call sites across five files were updated to unpack three values:**

| File | Function | Old | New |
|------|----------|-----|-----|
| `ou_model.py` | `fit_ou` | `spread, _beta = compute_spread(...)` | `spread, _beta, _alpha = compute_spread(...)` |
| `ou_model.py` | `ou_residual_diagnostics` | `spread, _beta = compute_spread(...)` | `spread, _beta, _alpha = compute_spread(...)` |
| `signal_generator.py` | `generate_entry_signal` | `spread_arr, _ = compute_spread(...)` | `spread_arr, beta, alpha = compute_spread(...)` |
| `pair_analysis.py` | `analyze_top_pairs` | `spread, _ = compute_spread(...)` | `spread, _beta, _alpha = compute_spread(...)` |
| `spread_visualiser.py` | `compute_zscore_series` | `spread_arr, _ = compute_spread(...)` | `spread_arr, _beta, _alpha = compute_spread(...)` |
| `validate_signal_generator.py` | regime gate test | `noisy_spread, _ = compute_spread(...)` | `noisy_spread, _beta, _alpha = compute_spread(...)` |
| `playground.py` | two call sites | `..., _ = compute_spread(...)` | `..., _beta, _alpha = compute_spread(...)` |

The `_` prefix convention for `_beta` and `_alpha` marks them as intentionally
unused at that call site. In `generate_entry_signal`, the names are `beta` and
`alpha` without prefix because they are used in the return dict.

---

### 5.2 Updated entry signal dict — all ten fields

Three fields were added to the entry signal dict to support `generate_exit_signal`:
`beta_at_entry`, `alpha_at_entry`, and `theta_at_entry`. The complete ten-field dict is:

```python
{
    "entry_spread":            float(S0),
    "reversion_probability":   float(prob),
    "expected_reversion_time": float(np.log(1.0 / f) / params.theta),
    "mu_at_entry":             float(params.mu),
    "sigma_at_entry":          float(params.sigma),
    "take_profit_level":       float(S0 - take_profit_pct * (S0 - params.mu)),
    "regime_log_ratio":        float(regime),
    "beta_at_entry":           float(beta),
    "alpha_at_entry":          float(alpha),
    "theta_at_entry":          float(params.theta),
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `entry_spread` | `float` | Spread value at signal time (spread units) |
| `reversion_probability` | `float` | Analytical $P(\text{cross}\,\mu\text{ within }\tau)$, $[0,1]$ |
| `expected_reversion_time` | `float` | $\ln(1/f)/\theta$ in hours (~34h for AVAX/LINK) |
| `mu_at_entry` | `float` | Fitted OU long-run mean (spread units) |
| `sigma_at_entry` | `float` | Fitted OU noise parameter (spread units per $\sqrt{\text{hour}}$) |
| `take_profit_level` | `float` | $S_0 - 0.80(S_0 - \mu)$ (spread units) |
| `regime_log_ratio` | `float` | $\log(\text{recent\_std}/\sigma)$ at entry (dimensionless) |
| `beta_at_entry` | `float` | OLS hedge ratio, frozen at entry |
| `alpha_at_entry` | `float` | OLS intercept, frozen at entry |
| `theta_at_entry` | `float` | Fitted OU mean reversion speed (per hour), frozen at entry |

`beta_at_entry`, `alpha_at_entry`, and `theta_at_entry` were added to support
`generate_exit_signal`. `theta_at_entry` will also be useful in Step 7 rolling
recalibration to compare entry $\theta$ against current $\theta$ as a measure of
model stability over the holding period.

---

### 5.3 Validation Results

#### Gate isolation tests

**Test 1 — Gate 2 (cointegration) fires on random walks:**

```python
np.random.seed(0)
rw_a = np.cumsum(np.random.normal(0, 1, 500)) + 100
rw_b = np.cumsum(np.random.normal(0, 1, 500)) + 100
result = generate_entry_signal(rw_a, rw_b)
# Expected: None
```

**PASS.** Two independent random walks have no cointegrating relationship.
The Engle-Granger p-value on the last 168 bars far exceeds 0.10.

---

**Test 2 — Gate 5 (volatility regime) fires on genuinely elevated volatility:**

```python
params = fit_ou(price_a, price_b)
np.random.seed(1)
noisy_a = price_a + np.random.normal(0, params.sigma * 10, len(price_a))
result = generate_entry_signal(noisy_a, price_b)          # default thresholds
noisy_spread, _ = compute_spread(noisy_a, price_b)
actual_regime = spread_volatility_regime(noisy_spread, params.sigma)
# actual_regime = 2.3458 > 1.1 → PASS
```

**PASS.** The gate fires naturally (not via a forced threshold override).

**The noise scaling rationale:** the noise is added at $10\times\sigma$ (the fitted
baseline noise). This must be large enough to overpower the sigma adaptation problem:

`fit_ou` fits $\sigma$ from `std(residuals)` on the same data that includes the
added noise. If noise is added at a moderate level (e.g., $2\times\sigma$), the
fitted $\sigma$ absorbs the new noise, and the log ratio deflates toward zero — the
gate self-cancels on persistent volatility that has been present across the full
30-day window. This is the documented known limitation (§2): `spread_volatility_regime`
detects short-lived spikes against a stable baseline, not regime-wide elevated
volatility. At $10\times\sigma$, the noise added in the test is so large that even
after sigma re-fitting, the recent-window std remains materially above the new
(inflated) sigma.

The original test design used `price_a.std() * 5` noise and `regime_threshold=-999.0`
to force the gate — a weak test that verified the gate code executed but not that
the gate correctly identified elevated volatility. The revised design removed the
forced threshold. The $10\times\sigma$ scaling was chosen specifically to ensure
the regime ratio survives sigma adaptation while keeping the underlying AVAX/LINK
cointegration structure intact enough for Gates 2–4 to pass.

---

**Test 3 — Gate 6 (reversion probability) fires at impossibly high threshold:**

```python
result = generate_entry_signal(price_a, price_b, prob_threshold=0.9999)
# Expected: None
```

**PASS.** No realistic OU crossing probability reaches 0.9999. Gate 6 blocks
all entries.

---

#### Live signal — AVAX/LINK (last 30 days)

```
Signal generated for AVAX/LINK:
  entry_spread:            -0.011564
  reversion_probability:   0.8047
  expected_reversion_time: 33.95 hours
  mu_at_entry:             -0.000856
  sigma_at_entry:          0.002722
  take_profit_level:       -0.002998
  regime_log_ratio:        0.8001
```

**Plain-English interpretation:**

**`entry_spread = -0.011564`:** AVAX/LINK spread is at -0.0116, approximately
$3.9\sigma$ below the fitted $\mu$ of -0.000856. The spread has dislocated
significantly from equilibrium. In terms of the stationary distribution
($\sigma_\infty = \sigma/\sqrt{2\theta} \approx 0.00884$), this is about $1.2$
stationary standard deviations below $\mu$ — a moderate-to-large dislocation.

**`reversion_probability = 0.8047`:** 80.5% analytical probability of crossing $\mu$
within the 33.95h horizon. After adjusting for the ~6.7pp discretisation bias from
Step 3, the empirical probability is approximately 73.8%. Well above the 0.67 gate.

**`expected_reversion_time = 33.95 hours`:** $\ln(5)/\theta = \ln(5)/0.0474 \approx 33.9$h —
the point at which 80% of the initial deviation has been absorbed by mean-reversion
drift alone. This is the primary time stop horizon for Step 5: if the spread has
not reached `take_profit_level` within ~34 hours, the position is outside its
expected window.

**`mu_at_entry = -0.000856`:** slightly shifted from the Step 2 validated value of
-0.0009, consistent with the 30-day rolling window updating as time passes.

**`sigma_at_entry = 0.002722`:** consistent with Step 2 ($\sigma = 0.0027$).
Understates tail risk (kurtosis 2.61, Step 2). Step 5 position sizing must adjust.

**`take_profit_level = -0.002998`:** target exit at 80% reversion. The spread needs
to move from -0.011564 to -0.002998, a move of 0.008566 in spread units — about
$3.1\sigma$ of travel. This will complete when the spread is back in the
$[-0.003, -0.001]$ range near $\mu$.

**`regime_log_ratio = 0.8001`:** recent spread std is $e^{0.80} \approx 2.2\times$
the fitted $\sigma$. Moderately elevated regime — below the 1.1 threshold but
indicating active market conditions. The pair passed Gate 5, but the stored value
flags this entry as a "elevated regime" trade for post-trade filtering in Step 6.

---

#### Take-profit sanity check

```
S0=-0.011564  mu=-0.000856  tp=-0.002998
pct_captured=0.8000
PASS
```

The formula $\text{TP} = S_0 - 0.80(S_0 - \mu)$ is verified to four decimal places.

---

## 6. `generate_exit_signal`

### 6.1 Design rationale

`generate_exit_signal` is a stateless pure function. The caller tracks
`hours_elapsed` — the function receives it as a scalar float and does no state
management of its own. The entry signal dict flows in as input and is never modified.
The function returns a dict with `exit_reason` and metadata if an exit condition
fires, or `None` if none fire.

This design follows the same philosophy as `generate_entry_signal`: no side effects,
no mutation of inputs, all thresholds exposed as parameters, caller decides what to
do with the result.

The original design had two exit conditions: take profit and time stop. A third —
the adverse move stop — was added subsequently (see §6.3). The gate structure
enforces a strict priority order: time stop is unconditional and checked first;
adverse move is checked second; take profit is checked last.

---

### 6.2 Frozen coefficients — why not re-estimate OLS at exit

When a trade is entered, a specific hedge ratio $\beta$ is locked in. That ratio
defines the actual position: $X$ units of asset A against $Y$ units of asset B,
where $Y = X \times \beta_{\text{entry}}$. The dollar P&L of the trade at any point
depends on how the spread — defined with those specific weights — has moved since
entry.

Re-estimating $\beta$ at exit time (i.e., re-running OLS on the price history
available at exit) would produce a different intercept $\alpha$ and hedge ratio
$\beta$. The "spread" computed with those new coefficients is a different quantity
from the spread the position is actually tracking. Using it for P&L accounting
introduces a measurement inconsistency that corrupts the backtest.

The current spread at exit is reconstructed as:

$$\text{current\_spread} = \text{current\_price\_a} - \alpha_{\text{entry}} - \beta_{\text{entry}} \times \text{current\_price\_b}$$

`current_price_a` and `current_price_b` are **scalars** — the latest log prices —
not arrays. The exit function does not run OLS. `alpha_at_entry` and `beta_at_entry`
are read directly from the entry signal dict.

**Option A (re-estimate at exit)** was considered and rejected. It is cheaper to
implement superficially — no need to propagate alpha through the pipeline — but
introduces a measurement inconsistency that corrupts P&L accounting in the backtest.
The spread baseline shifts at exit time, making `pnl_pct` meaningless.

**Option B (frozen coefficients)** is correct for tracking an open trade. The hedge
ratio is the one that was executed; the P&L is measured against the spread as
defined at entry. This is why `alpha_at_entry` and `beta_at_entry` were added to
the entry signal dict (§5.1).

---

### 6.3 Gate structure — three gates in order

#### Gate 1 — Time stop (unconditional)

```python
if hours_elapsed >= max_hours:
    return _exit("time_stop")
```

Fires when `hours_elapsed >= expected_reversion_time`. Checked first because it is
unconditional — a trade that has also hit take-profit distance but exceeded the
maximum hours is reported as `"time_stop"`, not `"take_profit"`.

**Rationale:** trust the model's horizon. The OU parameters were estimated with a
specific $\theta$, and `expected_reversion_time = ln(1/f)/theta` is the model's
predicted time for the spread to complete 80% of its reversion. Holding past this
horizon means the model's forecast is stale — the spread has not reverted in the
time the model expected it to. Exiting unconditionally respects the model's
self-stated validity window.

#### Gate 2 — Adverse move stop

```python
sigma_stationary = entry_signal["sigma_at_entry"] / np.sqrt(2.0 * entry_signal["theta_at_entry"])
stop_distance    = stop_sigma * sigma_stationary

if entry_spread > mu:
    if current_spread >= entry_spread + stop_distance:
        return _exit("adverse_move")
else:
    if current_spread <= entry_spread - stop_distance:
        return _exit("adverse_move")
```

Fires when the spread has moved `stop_sigma * sigma_stationary` further from $\mu$
since entry. Default `stop_sigma = 2.5`.

**Why `sigma_stationary` not raw `sigma`:** raw $\sigma$ is the per-hour noise
parameter — the standard deviation of $dS$ over one hour. `sigma_stationary =
sigma / sqrt(2 * theta)` is the long-run stationary standard deviation of the OU
process itself — the spread's equilibrium volatility. A stop scaled by $\sigma$
per hour would be sensitive to the model's noise estimate at the wrong timescale.
A 2.5 $\sigma_{\text{stationary}}$ adverse move places the current spread at an
extreme that is genuinely inconsistent with the fitted OU process, not just noisy
on an hourly basis.

**Why 2.5 default:** crypto spreads have excess kurtosis of approximately 2.6
(validated for AVAX/LINK in Step 2), meaning $2.0\,\sigma_{\text{stationary}}$
adverse moves occur more frequently than a Gaussian would predict. Setting
`stop_sigma = 2.0` would fire too frequently on normal OU noise. The 2.5 default
is chosen to protect against genuine model failure — a spread that has moved to an
extreme inconsistent with the OU process — while tolerating normal OU fluctuations.
Flagged for empirical calibration in Step 6.

**Direction check:** mirrors the take-profit direction. If the spread entered above
$\mu$ (expecting downward reversion), the adverse move is further upward. If the
spread entered below $\mu$ (expecting upward reversion), the adverse move is further
downward.

#### Gate 3 — Take profit

```python
if entry_spread > mu:
    if current_spread <= take_profit:
        return _exit("take_profit")
else:
    if current_spread >= take_profit:
        return _exit("take_profit")
```

Direction is derived from the sign of `entry_spread - mu_at_entry`:

- `entry_spread > mu`: spread above long-run mean, expecting downward reversion.
  Fires when `current_spread <= take_profit_level`.
- `entry_spread <= mu`: spread below long-run mean, expecting upward reversion.
  Fires when `current_spread >= take_profit_level`.

`take_profit_level = S0 - 0.80 * (S0 - mu)` captures 80% of the move back to $\mu$.
The formula handles both directions without conditioning (see §5 `take_profit_level`).

---

### 6.4 Function signature

```python
def generate_exit_signal(
    current_price_a: float,
    current_price_b: float,
    entry_signal: dict,
    hours_elapsed: float,
    stop_sigma: float = 2.5,
) -> dict | None:
```

---

### 6.5 Exit signal return dict

```python
def _exit(reason: str) -> dict:
    return {
        "exit_reason":    reason,
        "current_spread": float(current_spread),
        "entry_spread":   float(entry_spread),
        "pnl_pct":        float(pnl_pct),
        "stop_sigma":     float(stop_sigma),
    }
```

| Field | Type | Meaning |
|-------|------|---------|
| `exit_reason` | `str` | `"take_profit"`, `"time_stop"`, or `"adverse_move"` |
| `current_spread` | `float` | Spread at exit decision time, reconstructed with frozen coefficients (spread units) |
| `entry_spread` | `float` | Carried from `entry_signal` unchanged (spread units) |
| `pnl_pct` | `float` | $\lvert\text{current\_spread} - \text{entry\_spread}\rvert\,/\,\lvert\text{entry\_spread} - \mu\rvert$ |
| `stop_sigma` | `float` | `stop_sigma` value active for this trade — present in all exits for backtest traceability |

**Note on `pnl_pct`:** values greater than 1.0 are possible on adverse move exits —
the spread has moved further from $\mu$ than the entry displacement. `pnl_pct` is
not bounded in $[0, 1]$ and cannot be interpreted as a fraction of the target move
on all exit types. Downstream code in Step 6 must handle this.

`stop_sigma` is included in all exit dicts — not just `adverse_move` — so the
backtest always knows what stop was active for a given trade when comparing outcomes
across different stop configurations.

---

### 6.6 Validation — six synthetic tests

All tests use hardcoded synthetic entry signals. `expected_reversion_time = 34.0`,
`sigma_at_entry = 0.002722`, `theta_at_entry = 0.0474` shared across all tests.
Beta = 1.0, alpha = 0.0 in all tests, so `current_spread = current_price_a - 0.0 - 1.0 * current_price_b = current_price_a` when `current_price_b = 0.0`.

---

**Test 1 — take profit fires, spread above mu:**

- `entry_spread = 0.010`, `mu = -0.001`, `take_profit = 0.002`, `hours_elapsed = 10.0`
- `current_spread = 0.001`
- Time stop: $10.0 < 34.0$ — does not fire
- Adverse move: $0.001 < 0.010 + 0.02209$ — does not fire
- Take profit: $0.001 \leq 0.002$ — fires
- $\text{pnl\_pct} = |0.001 - 0.010| / |0.010 - (-0.001)| = 0.009/0.011 \approx 0.8182$
- **Result: PASS**

---

**Test 2 — take profit fires, spread below mu:**

- `entry_spread = -0.010`, `mu = -0.001`, `take_profit = -0.002`, `hours_elapsed = 10.0`
- `current_spread = -0.001`
- Time stop: $10.0 < 34.0$ — does not fire
- Adverse move: $-0.001 > -0.010 - 0.02209$ — does not fire
- Take profit: $-0.001 \geq -0.002$ — fires
- $\text{pnl\_pct} = |-0.001 - (-0.010)| / |-0.010 - (-0.001)| = 0.009/0.009 = 1.0000$
- **Result: PASS**

---

**Test 3 — time stop fires unconditionally:**

- `entry_spread = 0.010`, `mu = -0.001`, `take_profit = 0.002`, `hours_elapsed = 34.0`
- `current_spread = 0.009` — has not reached take profit (0.009 > 0.002)
- Time stop: $34.0 \geq 34.0$ — fires before take profit check
- $\text{pnl\_pct} = |0.009 - 0.010| / |0.010 - (-0.001)| = 0.001/0.011 \approx 0.0909$
- **Result: PASS**

---

**Test 4 — no exit condition met:**

- `entry_spread = 0.010`, `mu = -0.001`, `take_profit = 0.002`, `hours_elapsed = 10.0`
- `current_spread = 0.008`
- Time stop: $10.0 < 34.0$ — does not fire
- Adverse move: $0.008 < 0.010 + 0.02209 = 0.03209$ — does not fire
- Take profit: $0.008 > 0.002$ — does not fire
- **Result: `None` — PASS**

---

**Test 5 — adverse move fires, spread above mu:**

- `entry_spread = 0.010`, `mu = -0.001`, `sigma_at_entry = 0.002722`, `theta_at_entry = 0.0474`
- $\sigma_{\text{stationary}} = 0.002722 / \sqrt{2 \times 0.0474} \approx 0.00884$
- $\text{stop\_distance} = 2.5 \times 0.00884 \approx 0.02209$
- $\text{stop\_level} = 0.010 + 0.02209 = 0.03209$
- `current_spread = 0.033`, `hours_elapsed = 10.0`
- Time stop: $10.0 < 34.0$ — does not fire
- Adverse move: $0.033 \geq 0.03209$ — fires
- $\text{pnl\_pct} = |0.033 - 0.010| / |0.010 - (-0.001)| = 0.023/0.011 \approx 2.0909$
- **Result: PASS**

---

**Test 6 — adverse move fires, spread below mu:**

- `entry_spread = -0.010`, `mu = -0.001`, `sigma_at_entry = 0.002722`, `theta_at_entry = 0.0474`
- $\text{stop\_level} = -0.010 - 0.02209 = -0.03209$
- `current_spread = -0.033`, `hours_elapsed = 10.0`
- Time stop: $10.0 < 34.0$ — does not fire
- Adverse move: $-0.033 \leq -0.03209$ — fires
- $\text{pnl\_pct} = |-0.033 - (-0.010)| / |-0.010 - (-0.001)| = 0.023/0.009 \approx 2.5556$
- **Result: PASS**

---

## 7. Step 4.5 — OU Model Visual Diagnostic

### 7.1 Purpose

Step 4.5 adds an OU model overlay to `spread_visualiser.py` to visually verify that
the SDE model describes the spread well. Prior to this step, there was no point in
the system where the fitted OU parameters were checked visually against the actual
spread behaviour. The validate scripts check the math of OU functions in isolation;
they do not check whether the model is a good description of a specific pair's spread.

Quantitative gates (Steps 1–4) can pass while the model is a poor visual fit — for
example, when the spread has two distinct volatility regimes within the 30-day window
and the fitted parameters represent a blend of both. The visual overlay provides a
qualitative sanity check that the quantitative gates cannot.

---

### 7.2 What was added to `spread_visualiser.py`

**`compute_zscore_series` updated:** previously returned only the z-score series.
Now returns `(zscore, spread_mean, spread_std)` — needed to convert OU model outputs
from raw spread units to z-score units for overlay on the z-score chart.

**`fit_ou` called fresh per pair inside `plot_all_pairs`:** not reused from
`analyze_top_pairs`. The OU fit in `analyze_top_pairs` operates on the full pair
history; the visualiser uses a 30-day filtered window. A fresh fit on the plotted
data ensures the overlay parameters are consistent with what is shown.

**Per subplot, when OU fit succeeds (`ou_ok = not np.isnan(ou.theta)`):**

- **Mu line:** $\mu_z = (\mu - \text{spread\_mean}) / \text{spread\_std}$, drawn as
  a thin dashed dark-grey horizontal line. Replaces the zero line.

- **Stationary envelope:** two dashed orange horizontal lines at
  $\mu \pm 2\,\sigma_{\text{stationary}}$ in z-score units, where
  $\sigma_{\text{stationary}} = \sigma / \sqrt{2\theta}$. The spread should spend
  approximately 95% of its time between these lines under the stationary OU
  distribution.

**If OU fit fails:** subplot title shows `[OU fit failed — overlay skipped]`;
the z-score line still plots normally.

**What was removed:** the zero line (`ax.axhline(0, ...)`), the ±1.0 threshold
dotted lines, and the red shading above/below ±1.0. These were heuristic signal
references; the OU overlay replaces them with model-derived quantities.

---

### 7.3 Design decisions

Three band options were considered for the OU overlay:

**Option 1 — Fixed CI from current bar:** compute `ou_confidence_interval(S0, theta, mu, sigma, tau)`
from the last spread value and plot a single confidence interval centred on the
current bar. Shows the model's current view only, not calibration quality over the
full window.

**Option 2 — Rolling CI at every bar:** compute a confidence interval at every bar
over the 30-day window. Visually cluttered (~720 band computations rendered as
overlapping segments), and mixes in-sample fitted parameters with a rolling forecast
that was never actually made at those historical bar times. Contaminated.

**Option 3 — Rolling CI at tau-spaced anchor points:** tried first — rendered as
constant-width segments that shifted vertically. Correct mathematically but harder
to read than expected. The reason: `ou_spread_std(theta, sigma, tau)` depends only
on $\theta$, $\sigma$, and $\tau$ — not on $S_0$. Band width is constant regardless
of where the spread is. The segments convey no information that two flat lines cannot
convey more cleanly.

**Option 4 — Stationary envelope (chosen):** two flat horizontal lines at
$\mu \pm 2\,\sigma_{\text{stationary}}$ where $\sigma_{\text{stationary}} = \sigma / \sqrt{2\theta}$.
Shows the long-run equilibrium range the spread should occupy 95% of the time under
the stationary OU distribution. Clean, model-theoretic, directly interpretable.
The key question — "is the spread's actual variability consistent with what the OU
model predicts?" — is answered at a glance by checking whether the spread stays
within the orange lines.

---

### 7.4 What the chart shows and its limitations

The stationary envelope answers a single question: **is the spread's observed
variability consistent with what the OU model predicts?**

- If the spread regularly breaks outside the orange lines, $\sigma$ is understated
  — the model's noise parameter is too low for actual spread behaviour.
- If the spread never reaches the orange lines, $\sigma$ may be overstated — the
  spread is quieter than the fitted process.

**Mu line in z-score space:** the mu line will always appear near zero by
construction. The z-score is defined as $(\text{spread} - \text{spread\_mean}) / \text{spread\_std}$,
and $\mu$ is the OU long-run mean which is close to `spread_mean` for a
well-fitted process. The mu line carries limited visual information in z-score space
and is nearly identical to the removed zero line. It is more informative in raw spread
units. A future visualisation step may plot the spread in raw units with the OU
overlay directly.

**Known limitation — in-sample:** the stationary envelope is derived from parameters
fitted on the same 30-day window being plotted. It cannot detect overfitting to that
window. A pair whose $\sigma$ is inflated because the spread was volatile during the
plot window will show a wide envelope that accommodates that volatility by
construction. A proper out-of-sample check requires fitting on an earlier window
and overlaying on a later one — deferred to Step 6.

---

### 7.5 Observations from live pairs (current 30-day window)

**DOT/LINK ($\theta = 0.0599$, $\sigma_{\text{stat}} = 0.0115$):**

The spread oscillates within the stationary envelope for most of the window with
several excursions beyond $\pm 2\,\sigma_{\text{stationary}}$, consistent with the
fat tails documented in Step 2 (excess kurtosis ~2.6). The OU model appears to
describe this pair credibly — the envelope captures the bulk of spread variation
and the excursions are at the expected frequency for a leptokurtic process.

**AVAX/LINK ($\theta = 0.0474$, $\sigma_{\text{stat}} = 0.0088$):**

The spread is well-contained within the stationary envelope for most of the window.
Consistent with the validated parameters from Steps 2 and 3. The OU model appears
to describe this pair credibly. The narrow envelope relative to DOT/LINK reflects
the lower fitted $\sigma_{\text{stationary}}$.

**APT/SNX ($\theta = 0.0546$, $\sigma_{\text{stat}} = 0.0206$):**

The spread spent approximately the first 10 days at $+2$ to $+4$ z-scores — a
sustained excursion well outside the stationary envelope. It then shifted to ranging
between $-1$ and $+1$ for the remainder of the window. This is a classic mid-window
regime change: two visually distinct modes, with the OU model fitted across both.

`sigma_stationary = 0.0206` is the largest of the three pairs — the OU fit absorbed
the regime shift as elevated volatility, inflating $\sigma$ and producing a wider
envelope that accommodates the first-half excursion. The quantitative gates still
pass (the pair is flagged as tradeable), but the visual overlay immediately reveals
a structural issue the gates do not catch: the pair had two distinct regimes during
the fitting window and the OU parameters represent neither cleanly.

This pair should be treated with extra skepticism even if it passes all quantitative
gates. The in-sample limitation of the stationary envelope (§7.4) is directly
observable here.

---

## 8. Known Limitations and Items for Empirical Calibration

1. **Regime gate limitation: persistent volatility, not spikes.** `spread_volatility_regime`
   detects recent-window std elevated above the fitted $\sigma$ baseline. Because
   $\sigma$ is estimated from the same 30-day window, a pair that has been consistently
   volatile throughout the window will have a high fitted $\sigma$ and a log ratio near
   zero — the gate does not fire. The gate catches volatility spikes, not regime shifts.
   A separate regime-detection layer (e.g. GARCH or rolling $\sigma$ trend) would be
   needed to address this.

2. **`prob_threshold=0.67` is not empirically calibrated.** The value is analytically
   derived from the Step 3 ~6.7pp overestimate adjusted to target ~0.60 true crossing
   probability. Whether 0.60 empirical crossing probability is the right entry floor —
   given this system's transaction costs, position sizing, and stop structure — is
   untested. Step 6 backtest is required to calibrate.

3. **`f=0.20` (80% capture) is a starting point.** Smaller $f$ (e.g., 0.10) means a
   longer holding horizon, more path uncertainty, and higher probability — but also
   more exposure to regime shifts. Larger $f$ (e.g., 0.50) shortens the horizon and
   reduces probability. The choice is untested against the empirical reversion
   distribution.

4. **Time stop is implemented in `generate_exit_signal` as Gate 1.** The default
   horizon is `expected_reversion_time = ln(1/f)/theta` hours. Whether this horizon
   is empirically optimal — given the actual distribution of reversion times across
   backtested trades — is untested. Step 6 backtest required to calibrate.

5. **Adverse move stop is implemented in `generate_exit_signal` as Gate 2,** scaled
   by $\sigma_{\text{stationary}} = \sigma / \sqrt{2\theta}$ with default
   `stop_sigma = 2.5`. The 2.5 default is logic-derived not empirically calibrated:
   chosen to avoid stopping out on normal OU noise given fat tails (excess kurtosis
   ~2.6), where $2.0\,\sigma_{\text{stationary}}$ adverse moves occur more frequently
   than Gaussian would predict. Flagged for empirical calibration in Step 6.

6. **`sigma_at_entry` understates tail risk.** Step 2 excess kurtosis of 2.61 for
   AVAX/LINK means the true P&L distribution has heavier tails than Gaussian $\sigma$
   implies. Position sizing in Step 5 must account for this — e.g., by sizing to the
   99th percentile of a $t$-distribution or applying a kurtosis scaling factor.

7. **Two-barrier first passage not handled.** The probability gate uses a single barrier
   at $\mu$ (profit target). A realistic entry also has an implicit stop-loss barrier.
   The probability of reaching $\mu$ before a stop at $S_\text{stop}$ — the two-sided
   first-passage problem — is not computed. Noted for future extension (Step 4 or 5).

8. **`measure_approach_speeds` not integrated.** The function in `trade_diagnostics.py`
   does not map naturally onto the probability-based entry framework: it operates on
   historical z-scores and signal indices, not on current spread values and OU parameters.
   It has not been deprecated — it may become useful in Step 6 for characterising
   approach speed distributions across backtested trades — but it is not part of the
   signal generation pipeline.

9. **`conditional_half_life` not integrated.** Useful as a sanity check against
   `expected_reversion_time`: if the empirical conditional half-life (mean excursion
   duration above threshold) is materially longer than $\tau$, the OU model may be
   overstating mean reversion speed. Not integrated because 30 days of data produces
   too few resolved excursions for the estimate to be meaningful at the target
   threshold levels.

10. **Duplicate computation in the gate sequence.** Gates 3 and 4 both call their
    respective functions on the same price data, and both internally call `_fit_ou_internals`.
    The OLS is computed twice. Not a correctness issue — both calls are side-effect-free
    — but a performance cost if the signal generator is called at high frequency or
    across many pairs. A shared `internals` cache would halve the OLS work.

11. **`stop_sigma=2.5` is not empirically calibrated.** The default is derived from
    reasoning about fat-tailed crypto spread distributions and normal OU fluctuation
    ranges. The empirically correct value depends on the actual distribution of adverse
    moves in the data and the relationship between stop tightness and overall strategy
    P&L. Step 6 backtest is required. `stop_sigma` is recorded in all exit dicts to
    make this calibration tractable.

12. **`sigma_stationary` as stop scaling unit is an assumption.** Using
    $\sigma / \sqrt{2\theta}$ as the stop unit assumes the spread's long-run stationary
    distribution is the right reference for "how far is too far." An alternative is to
    scale by the empirical spread std over the 30-day window. The two will differ when
    the OU fit is imperfect. Not tested.

13. **`pnl_pct` on adverse move exits exceeds 1.0.** This is correct by construction
    — the spread has moved further from $\mu$ than the entry displacement — but it
    means `pnl_pct` is not bounded in $[0, 1]$ and cannot be interpreted as a fraction
    of the target move on all exits. Downstream code in Step 6 must handle this.

14. **Mu line in z-score visualisation carries limited information.** Because the
    z-score is defined as $(\text{spread} - \text{spread\_mean}) / \text{spread\_std}$
    and $\mu$ is close to `spread_mean` by construction, $\mu$ in z-score space will
    always be near zero. The mu line is visually nearly identical to a zero line. More
    informative in raw spread units. Consider plotting spread in raw units with OU
    overlay for a future visualisation step.

15. **Step 4.5 OU overlay is in-sample.** The stationary envelope is derived from
    parameters fitted on the same 30-day window being plotted. It cannot detect
    overfitting to that window. A proper out-of-sample check requires fitting on an
    earlier window and overlaying on a later one — deferred to Step 6.

16. **No helper function for trade direction yet.** Trade direction (long spread or
    short spread) is derivable from $\text{sign}(\text{entry\_spread} - \mu_{\text{entry}})$
    but is not explicitly stored in the entry signal dict or exposed as a helper
    function. A `get_spread_direction(entry_signal) -> int` helper returning $+1$
    (spread above $\mu$, short) or $-1$ (spread below $\mu$, long) will be added to
    `signal_generator.py` in Step 6 when the backtester needs it. Agreed to use a
    helper function rather than adding a new dict field to avoid polluting the entry
    signal with a derived quantity.
