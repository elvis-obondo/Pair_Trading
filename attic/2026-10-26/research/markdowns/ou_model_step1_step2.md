# OU Model — Parameter Estimation and Residual Diagnostics
## Crypto Pairs Trading Research System | OKX Futures | 1h OHLCV

---

## 1. System Context

This system performs statistical pairs trading research on OKX crypto perpetual
futures, using freqtrade-sourced 1h OHLCV data stored as feather files under
`user_data/data/okx/futures/`. Log prices are used throughout (values are
`ln(close)`).

**Pipeline position:**

```
data_loader.py
    └── get_price_levels()              — log prices, datetime index, all tickers
pair_analysis.py
    └── compute_spread()                — OLS hedge ratio + residual spread
    └── half_life(), hurst_exponent()   — spread stationarity screening
    └── rolling_coint(), rolling_hedge_ratio() — stability filters
ou_model.py
    └── fit_ou()                        — OU parameter estimation (θ, μ, σ)
    └── ou_residual_diagnostics()       — residual quality tests
(future) sde_model.py
    └── entry/exit timing via continuous-time OU formulas
```

**30-day rolling window convention.** Crypto cointegration relationships are
regime-dependent. Structural breaks — project failures, exchange re-listings,
macro liquidity events — routinely destroy historical spread behaviour. The 30-day
window (~720 hourly bars) balances two constraints:

- Enough observations for stable OLS estimates (hedge ratio, OU slope)
- Short enough to reflect the current market regime

This convention is set in `pair_analysis.analyze_top_pairs()` (`days=30`) and
applied consistently in validation scripts via:

```python
cutoff = df.index.max() - pd.Timedelta(days=30)
df = df[df.index >= cutoff]
```

---

## 2. The OU Model — What It Is and Why

The spread $S_t$ between a cointegrated pair is modelled as an
Ornstein-Uhlenbeck (OU) process:

$$dS = -\theta(S - \mu)\,dt + \sigma\,dW$$

where $W$ is a standard Brownian motion.

### Parameter interpretations (trading terms)

| Parameter | Units | Trading meaning |
|-----------|-------|----------------|
| $\theta$ | per hour | Mean reversion speed. Higher $\theta$ → faster trade resolution. Half-life $= \ln(2)/\theta$ hours. |
| $\mu$ | spread units | Long-run equilibrium level. Entry signals are z-scores relative to $\mu$. |
| $\sigma$ | spread units $/ \sqrt{\text{hour}}$ | Noise magnitude. Sets expected P&L variance and minimum position size. |

### Discretised AR(1) regression

The Euler-Maruyama discretisation at $\Delta t = 1$ hour gives:

$$\Delta S_t = \underbrace{\theta\mu}_{c} + \underbrace{(-\theta)}_{\lambda} S_{t-1} + \varepsilon_t, \quad \varepsilon_t \sim \mathcal{N}(0, \sigma^2)$$

OLS on this AR(1) yields slope $\lambda$ and intercept $c$, from which:

$$\theta = -\lambda \quad (\text{requires } \lambda < 0)$$
$$\mu = c / \theta$$
$$\sigma = \text{std}(\hat{\varepsilon})$$

The condition $\theta > 0$ (equivalently $\lambda < 0$) is the mean reversion
guard. If OLS returns $\lambda \geq 0$, the spread is trending or unit-root and
the OU model does not apply.

### Time units and half-life

The bar frequency (1 hour) sets the natural time unit for $\theta$. Half-life
in days:

$$\text{half-life (days)} = \frac{\ln 2}{\theta \times 24}$$

Example — AVAX/LINK, last 30 days: $\theta = 0.0474$ → half-life $\approx 0.61$
days (≈15 hours). At this speed, mean-reversion trades are expected to resolve
intraday to overnight.

### Role in the pipeline

$\theta$, $\mu$, and $\sigma$ are the inputs to a future SDE-based entry/exit
timing model, which will compute optimal thresholds and expected holding times
using the closed-form properties of the OU process (e.g. first-passage time
distributions, stationary variance $\sigma^2 / 2\theta$).

---

## 3. Implementation — `ou_model.py`

### `OUParams` NamedTuple

```python
class OUParams(NamedTuple):
    theta: float  # mean reversion speed (per hour)
    mu: float     # long-run mean of the spread
    sigma: float  # volatility of the spread
```

Returns `OUParams(nan, nan, nan)` as the degenerate sentinel (not an exception),
so downstream vectorised code can propagate NaN without branching.

### `OUResidualDiagnostics` NamedTuple

```python
class OUResidualDiagnostics(NamedTuple):
    jb_stat:         float   # Jarque-Bera statistic
    jb_p:            float   # JB p-value (normality)
    lb_stat:         float   # Ljung-Box statistic at lb_lags
    lb_p:            float   # LB p-value (autocorrelation)
    skewness:        float   # third standardised moment
    excess_kurtosis: float   # fourth standardised moment minus 3
    theta_tstat:     float   # t-stat for H0: theta == 0
    theta_p:         float   # two-sided p-value for theta t-test
```

All NaN on degenerate inputs (fewer than 3 finite values, or zero spread
variance).

### `_fit_ou_internals(S) -> dict | None`

Private helper. Takes a pre-validated, finite-stripped float array (`len >= 3`)
and returns the raw OLS outputs needed by both `fit_ou` and
`ou_residual_diagnostics`. Returns `None` for degenerate spreads.

```python
def _fit_ou_internals(S: np.ndarray) -> dict | None:
    dS    = S[1:] - S[:-1]
    S_lag = S[:-1]
    lam, c    = np.polyfit(S_lag, dS, 1)
    residuals = dS - (c + lam * S_lag)
    n      = len(S_lag)
    sigma2 = np.sum(residuals ** 2) / (n - 2)   # unbiased: df = n - 2
    SS_lag = np.sum((S_lag - np.mean(S_lag)) ** 2)
    if SS_lag == 0:
        return None
    lam_se = float(np.sqrt(sigma2 / SS_lag))
    return {"lam": float(lam), "c": float(c), "residuals": residuals, "lam_se": lam_se}
```

The OLS standard error on $\lambda$ follows from first principles:

$$\text{SE}(\hat{\lambda}) = \sqrt{\frac{\hat{\sigma}^2}{SS_{lag}}}, \quad
\hat{\sigma}^2 = \frac{\sum \hat{\varepsilon}^2}{n - 2}$$

Two degrees of freedom are consumed by the intercept and slope coefficients.

The helper is private (`_` prefix) because it expects pre-cleaned input and its
return dict is an implementation detail — not part of the public API.

### `fit_ou(price_a, price_b) -> OUParams`

```python
def fit_ou(price_a: np.ndarray, price_b: np.ndarray) -> OUParams:
    spread, _beta = compute_spread(price_a, price_b)
    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:                    # need ≥2 differences for OLS
        return OUParams(nan, nan, nan)
    internals = _fit_ou_internals(S)
    if internals is None:             # degenerate spread (zero variance in lags)
        return OUParams(nan, nan, nan)
    lam, c = internals["lam"], internals["c"]
    theta = -lam
    if theta <= 0:                    # no mean reversion: λ ≥ 0
        return OUParams(nan, nan, nan)
    mu    = c / theta
    sigma = float(np.std(internals["residuals"]))   # ddof=0; see §4
    return OUParams(theta=theta, mu=mu, sigma=sigma)
```

### `ou_residual_diagnostics(price_a, price_b, lb_lags=48) -> OUResidualDiagnostics`

Follows the same spread pipeline as `fit_ou` but surfaces residuals for quality
testing. Does **not** gate on `theta > 0` — diagnostics are useful even when the
spread is non-mean-reverting (e.g., to confirm the AR(1) was correctly rejected).

Key computations:

**Jarque-Bera (normality):**
```python
jb_stat, jb_p = jarque_bera(residuals)
```

**Ljung-Box (autocorrelation):**
```python
lb_lags_actual = min(lb_lags, n // 2)
result  = acorr_ljungbox(residuals, lags=[lb_lags_actual], return_df=True)
lb_stat = float(result["lb_stat"].iloc[-1])
lb_p    = float(result["lb_pvalue"].iloc[-1])
```

**Skewness and excess kurtosis (numpy, no scipy.stats):**
```python
z               = (residuals - np.mean(residuals)) / np.std(residuals)
skewness        = float(np.mean(z ** 3))
excess_kurtosis = float(np.mean(z ** 4) - 3)
```

**Theta t-statistic:**
```python
theta_tstat = float(-lam / lam_se)          # note: lam < 0, -lam = theta > 0
theta_p     = float(2 * t_dist.sf(abs(theta_tstat), n - 2))
```

---

## 4. Key Design Decisions and Conventions

### `compute_spread` as single source of truth

All spread computation routes through `pair_analysis.compute_spread()`. The OU
module never reimplements OLS hedge ratio logic. This ensures the spread used for
parameter estimation is identical to the spread used in cointegration screening,
half-life filtering, and rolling diagnostics.

### Pure functions module

`ou_model.py` has no `__main__` block, no `print` statements, no file I/O, and
no pandas. Importable without side effects by notebooks, batch jobs, or live
strategy code.

### `_fit_ou_internals` — Option A vs Option B

**Option A (chosen):** private function returning a plain `dict`. The public
functions (`fit_ou`, `ou_residual_diagnostics`) own the spread cleaning, nan
guards, and return type logic. The helper handles only the linear algebra on
pre-validated inputs.

**Option B (rejected):** a new `OUInternals` NamedTuple as a public return type.
Rejected because internal regression coefficients are implementation details.
Exposing them as a public type creates API surface that downstream code could
depend on, making refactoring harder.

### ddof asymmetry: sigma uses 0, lam_se uses 2

- `sigma = np.std(residuals)` uses `ddof=0` (biased). `sigma` is a scale
  parameter in a trading formula, not a standalone population estimate. Using the
  numpy default avoids silent divergence from callers who apply `np.std`
  directly.
- `sigma2 = sum(residuals**2) / (n-2)` uses `ddof=2` (unbiased). This is the
  OLS variance estimate. The unbiased form is required for the SE formula to give
  correct t-statistics and confidence intervals.

### `return_df=True` for `acorr_ljungbox`

An earlier implementation used `return_df=False` and accessed the result as
`result[0][-1]`, `result[1][-1]`. The structure of the tuple return is not stable
across statsmodels minor versions — the array shapes and dtypes have changed
between releases. `return_df=True` always returns a DataFrame with named columns
`lb_stat` and `lb_pvalue`, which is the documented stable interface.

### Diagnostic design choices

**JB and Ljung-Box are complementary, not redundant.** JB tests distribution
shape (fat tails, skewness); Ljung-Box tests temporal structure (autocorrelation).
A spread can have white-noise but non-Gaussian residuals (passes LB, fails JB),
or Gaussian but autocorrelated residuals (passes JB, fails LB). Both failure
modes matter for different reasons: non-Gaussianity affects position sizing; auto-
correlation implies the AR(1) is misspecified.

**Ljung-Box lag default of 48.** Three crypto-specific reasons:
1. Typical half-lives in the target range (12–48h) mean any genuine autocorrelation
   in the residuals would appear within 48 lags.
2. OKX perpetuals have 8h funding rate settlements (3× per day). A 48-lag window
   covers exactly two full days — two full funding cycles — and captures any 24h
   or 8h harmonic structure.
3. With 720 hourly bars in a 30-day window, `n // 2 = 360`, so 48 lags is well
   within the safe region where the Ljung-Box chi-squared approximation holds.

**Skewness and excess kurtosis as raw diagnostics.** No PASS/FAIL threshold is
imposed because acceptable levels are strategy-dependent. A delta-neutral mean
reversion strategy can tolerate negative skewness differently than an options
strategy. The raw values are reported for the researcher to judge.

**Theta t-stat as primary significance gate.** `theta_p ≈ 0` is necessary
(though not sufficient) before trusting any OU-derived entry signal. A pair with
a visually nice spread but `theta_p = 0.3` should not be traded.

---

## 5. Validation Design

### Why the original theta=0.047 anchor was wrong

The original `validate_ou_diagnostics.py` asserted:
```python
abs(p.theta - 0.047) < 0.005   # for AVAX/LINK
```
against `get_price_levels()` with no date filter. This fails as a regression test
for two reasons:

1. **It tests market data, not code.** The assertion fails when market conditions
   change, not when the code is broken. A code bug that preserves the approximate
   theta value will silently pass.
2. **The anchor is unverifiable.** `theta=0.047` was a snapshot from an unspecified
   historical window. There is no way to confirm it was ever correct, or that it
   should hold in the future.

### Two-part validation approach

**Part 1: Synthetic OU process (code correctness)**

Simulates a spread with known parameters using Euler-Maruyama, then passes a
cointegrated price pair to `fit_ou` and checks parameter recovery:

```python
theta_true, mu_true, sigma_true = 0.05, 0.0, 0.003
n_steps = 720
np.random.seed(42)
# OU simulation
S = np.zeros(n_steps)
eps = np.random.normal(0, 1, n_steps)
for t in range(1, n_steps):
    S[t] = S[t-1] + theta_true * (mu_true - S[t-1]) + sigma_true * eps[t]
# Cointegrated pair: beta=1, alpha=0 by construction
price_b = np.cumsum(np.random.normal(0, 0.01, n_steps)) + 10.0
price_a = price_b + S
```

`price_a - price_b = S` exactly, so `compute_spread` recovers $S$ via OLS with
$\hat{\beta} \approx 1$, $\hat{\alpha} \approx 0$.

Tolerances and their justification:

| Parameter | Tolerance | Justification |
|-----------|-----------|---------------|
| theta | ±0.02 | AR(1) is upward-biased in finite samples (Stambaugh bias). n=720, θ=0.05 → ~26% upward bias is expected. |
| mu | ±0.5 | The spread is zero-mean by construction; small deviations arise from OLS absorbing the hedge ratio residuals. |
| sigma | ±0.002 | sigma=0.003; the ±67% tolerance is wide but sigma is recovered with negligible bias in practice. |

This test is market-condition independent. It will only fail if the OLS
computation or parameter recovery logic is broken.

**Part 2: Live pair, raw diagnostics only**

```python
cutoff = df.index.max() - pd.Timedelta(days=30)
df = df[df.index >= cutoff]
```

Live results are printed and inspected, no assertions. No specific market values
are stable enough to serve as regression anchors.

### The data window bug and its impact

Running `ou_residual_diagnostics` on full history vs. the last 30 days for the
same pair (AVAX/LINK):

| Metric | Full history | Last 30 days | Implication |
|--------|-------------|--------------|-------------|
| `excess_kurtosis` | 15.27 | 2.61 | Full history blends multiple volatility regimes → artificially fat tails |
| `lb_p` | 0.0000 | 0.0207 | Full history accumulates autocorrelation across regime boundaries |

The full-history fit is not wrong — it is answering a different question (what
has this pair done over its entire history). For a 30-day trading strategy, it is
the wrong question.

---

## 6. Validated Output — AVAX/LINK (last 30 days)

### Synthetic test results

```
Synthetic test:
  theta_true=0.0500  recovered=0.0629  diff=0.0129
  mu_true=0.0000     recovered=-0.0001  diff=0.0001
  sigma_true=0.0030  recovered=0.0030  diff=0.0000
Synthetic test: PASS
```

theta recovered at 0.0629 vs. true 0.05: a 26% upward bias, consistent with
known AR(1) finite-sample behaviour. sigma and mu recovered with negligible error.

### Live pair fit

```
theta=0.0474  mu=-0.0009  sigma=0.0027
implied half-life=0.61 days
```

### Residual diagnostics

```
jb_stat=203.8726    jb_p=0.0000
lb_stat=70.0130     lb_p=0.0207
skewness=-0.0384    excess_kurtosis=2.6057
theta_tstat=4.2516  theta_p=0.0000
```

### Plain-English interpretation

**Theta significance** (`theta_tstat=4.25`, `theta_p≈0`): mean reversion is
highly statistically significant. The null of no mean reversion ($\theta = 0$)
is rejected at any conventional level. This is the primary gate — passed.

**Fat tails** (`excess_kurtosis=2.61`, `jb_p≈0`): residuals are clearly
non-Gaussian. Excess kurtosis of 2.61 means extreme spread moves occur
materially more often than a Gaussian model predicts. The `sigma=0.0027` estimate
understates tail risk. Position sizing should apply a kurtosis adjustment — for
example, sizing to the 99th percentile of a $t$-distribution with the estimated
kurtosis rather than to $2\sigma$ of a Gaussian.

**Mild autocorrelation** (`lb_stat=70.01`, `lb_p=0.021`): residuals are not
fully white noise at 48 lags. The effect is marginal — the p-value is 0.021, not
near-zero — but present. The most likely explanation is the OKX 8h funding rate
settlement creating periodic spread pressure not captured by the AR(1). This does
not invalidate the model but suggests a small additional alpha in timing entries
to avoid the funding window.

**Near-zero skewness** (`skewness=-0.0384`): the residual distribution is nearly
symmetric. No systematic directional bias in spread movements; the model does not
have a structural short or long lean.

**Overall assessment:** AVAX/LINK passes as a trading candidate on the 30-day
window. Statistically significant mean reversion, sub-day half-life suitable for
intraday to overnight hold times. Known adjustments required before live use: (1)
kurtosis-aware position sizing, (2) awareness of funding window timing.

---

## 7. Known Limitations and Open Questions

1. **AR(1) as discrete OU approximation.** Euler-Maruyama at $\Delta t = 1h$
   introduces approximation error that grows with $\theta\Delta t$. For the
   target half-life range (0.5–2 days, $\theta \approx 0.014$–$0.058$), the
   error is negligible ($\theta\Delta t \ll 1$). At very high mean reversion
   ($\theta > 0.5$ per hour, half-life < 1.4 hours), the discrete model diverges
   from the continuous-time SDE.

2. **Finite-sample upward bias on $\hat{\theta}$.** AR(1) slope estimators are
   upward-biased (in magnitude) in finite samples — the "Stambaugh bias". The
   synthetic test demonstrated a 26% upward bias at $n=720$. The live estimate
   $\hat{\theta}=0.0474$ is an upper bound on the true mean reversion speed;
   actual half-lives are likely longer than the point estimate implies.

3. **Gaussian noise assumption violated.** `jb_p≈0` and `excess_kurtosis=2.61`
   confirm non-Gaussian residuals for AVAX/LINK. The $\sigma$ estimate and any
   derived confidence intervals underestimate extreme move probabilities. A
   $t$-distributed error model or GARCH volatility would be more accurate.

4. **Residual autocorrelation.** `lb_p=0.021` at 48 lags indicates the AR(1)
   does not fully capture spread dynamics. Potential extensions: ARMA(1, q),
   inclusion of a 24h/8h harmonic regressor for the funding rate, or regime-
   switching AR. Not implemented.

5. **In-sample only.** All diagnostics are computed on the same 30-day window
   used to fit the parameters. No walk-forward or expanding-window out-of-sample
   validation exists. Overfitting risk is low given model simplicity, but
   performance on unseen data is unconfirmed.

6. **Spread stationarity assumed, not tested within `fit_ou`.** The function does
   not run an ADF or KPSS test before fitting. It relies on the upstream
   cointegration filter in `pair_analysis` (Engle-Granger at 5% significance).
   Approximately 5% of pairs that reach `fit_ou` may be spuriously cointegrated.
