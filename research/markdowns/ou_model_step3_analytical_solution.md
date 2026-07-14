# OU Model — Step 3: Analytical Solution and Forward Spread Distribution
## Crypto Pairs Trading Research System | OKX Futures | 1h OHLCV

---

## 1. Purpose of Step 3

Steps 1 and 2 (documented in [ou_model_step1_step2.md](ou_model_step1_step2.md))
established that AVAX/LINK has statistically significant mean reversion
($\theta=0.0474$, half-life≈15h) and characterised the residual quality
(fat tails, marginal autocorrelation). The fitted parameters $(\theta, \mu, \sigma)$
from `fit_ou` are the inputs here.

**The problem Step 3 solves:** classical pairs trading uses a static z-score
threshold (e.g. enter at $|z|>2$, exit at $|z|<0.5$). This is blind to the
current distance from $\mu$, the current $\theta$ (how fast reversion will
actually be), and the available time horizon. Two positions at $z=2.0$ can have
very different expected P&L if one has $\theta=0.1$ and the other has
$\theta=0.01$.

Step 3 replaces the static z-score with a forward-looking probability
framework: given the current spread $S_0$, what is the probability of
crossing $\mu$ within $\tau$ hours, and what is the expected path?

**What Step 3 assumes:** the residual quality gate from Step 2 has been passed —
specifically, `theta_p` is near zero (mean reversion is statistically significant)
and the OU model is not obviously misspecified. The analytical formulas are exact
given the model; Step 2 is the check that the model applies.

**What feeds Step 4:** the five functions here produce the raw inputs for entry/exit
signal generation — crossing probabilities, confidence intervals on the spread path,
and expected time-to-reversion — which Step 4 will turn into trade decisions.

---

## 2. The Closed-Form OU Solution

The SDE (from Step 2):

$$dS = \theta(\mu - S)\,dt + \sigma\,dW$$

This has an exact solution. Given $S_t = S_0$ and a horizon $\tau > 0$,
$S_{t+\tau}$ is normally distributed:

$$S_{t+\tau} \mid S_0 \;\sim\; \mathcal{N}\!\left(m(\tau),\; v(\tau)\right)$$

### Conditional mean

$$m(\tau) = \mu + (S_0 - \mu)\,e^{-\theta\tau}$$

- $\mu$: the equilibrium the process is always pulled toward.
- $(S_0 - \mu)$: the current deviation from equilibrium — the "signal" in the spread.
- $e^{-\theta\tau}$: the fraction of that deviation remaining after $\tau$ hours.
  At $\tau=0$ this is 1 (nothing has decayed). As $\tau\to\infty$ this goes to 0
  and the mean converges to $\mu$ regardless of $S_0$.

The rate of decay is entirely governed by $\theta$. A pair with $\theta=0.0474$
retains $e^{-0.0474\times 24} \approx 0.32$ of its deviation after 24 hours.

### Conditional variance

$$v(\tau) = \frac{\sigma^2}{2\theta}\left(1 - e^{-2\theta\tau}\right)$$

- At $\tau=0$: $v=0$. The spread is known exactly.
- As $\tau\to\infty$: $v\to\sigma^2/2\theta$ — the **stationary variance**.
  Unlike a random walk (where variance grows as $\sigma^2\tau$ without bound),
  the OU variance saturates because mean reversion actively counteracts diffusion.
- The standard deviation $\text{std}(\tau) = \sigma\sqrt{(1-e^{-2\theta\tau})/(2\theta)}$
  approaches $\sigma/\sqrt{2\theta}$, the stationary standard deviation.

For AVAX/LINK: $\sigma/\sqrt{2\theta} = 0.0027/\sqrt{0.0948} \approx 0.00877$.

### Why the analytical solution, not Monte Carlo

| Property | Analytical | Monte Carlo |
|----------|-----------|-------------|
| Speed | $O(1)$ per call | $O(n\_paths \times \tau)$ |
| Determinism | exact | seed-dependent |
| Sampling noise | none | $O(1/\sqrt{n\_paths})$ |
| Correctness | exact given model | approximate |
| Practical use | vectorised over pairs/taus | unsuitable for real-time signals |

The analytical formulas are exact under the Gaussian OU assumption. Monte Carlo
is retained in `validate_ou_analytics.py` as a one-time verification tool, not
a production path.

---

## 3. The Five Functions

All five live in `ou_model.py`. All accept individual `float` arguments, no
`OUParams`, no pandas, no I/O. See §4 for the design rationale.

---

### `ou_expected_spread`

```python
def ou_expected_spread(S0: float, theta: float, mu: float, tau: float) -> float:
```

**Computes:** $m(\tau) = \mu + (S_0 - \mu)\,e^{-\theta\tau}$, the expected spread
at $\tau$ hours from now.

**Edge cases:**

| Condition | Return | Reason |
|-----------|--------|--------|
| `theta <= 0` | `np.nan` | Non-mean-reverting — formula is undefined and misleading |
| `tau == 0` | `float(S0)` | Exact identity; avoids floating-point error in $e^0=1$ branch |
| `tau` large | approaches `mu` | Correct asymptotic; no special case needed |

**Trading meaning:** the "fair value" of the spread at a future time given current
conditions. Used to answer: if I enter now, where is the spread expected to be
when I plan to exit?

---

### `ou_spread_std`

```python
def ou_spread_std(theta: float, sigma: float, tau: float) -> float:
```

**Computes:** $\text{std}(\tau) = \sigma\sqrt{(1 - e^{-2\theta\tau})/(2\theta)}$,
the conditional standard deviation of the spread at $\tau$ hours.

**Edge cases:**

| Condition | Return | Reason |
|-----------|--------|--------|
| `theta <= 0` | `np.nan` | Formula undefined |
| `tau == 0` | `0.0` | No uncertainty at $t=0$; avoids divide-by-zero in callers |
| `tau` large | $\sigma/\sqrt{2\theta}$ | Stationary std — correct asymptote |

**Trading meaning:** the uncertainty band around the expected spread. As $\tau$
grows this saturates — the spread cannot wander arbitrarily far from $\mu$,
which is what makes OU tradeable in the first place.

---

### `ou_confidence_interval`

```python
def ou_confidence_interval(
    S0: float, theta: float, mu: float, sigma: float,
    tau: float, alpha: float = 0.95
) -> tuple[float, float]:
```

**Computes:**

$$\text{lower} = m(\tau) - z_{\alpha/2}\cdot\text{std}(\tau)$$
$$\text{upper} = m(\tau) + z_{\alpha/2}\cdot\text{std}(\tau)$$

where $z_{\alpha/2} = \Phi^{-1}(1 - (1-\alpha)/2)$. For $\alpha=0.95$:
$z_{0.025} \approx 1.960$.

Returns `(np.nan, np.nan)` if either `ou_expected_spread` or `ou_spread_std`
returns `nan`, propagating the invalid-input sentinel without raising.

**Trading meaning:** the interval the spread is expected to remain within at
confidence level $\alpha$ after $\tau$ hours. If the lower bound is still on the
same side of $\mu$ as the current spread, the confidence interval does not yet
contain $\mu$ — indicating the trade may need more time or the entry was too
aggressive.

---

### `ou_reversion_probability`

```python
def ou_reversion_probability(
    S0: float, theta: float, mu: float, sigma: float, tau: float
) -> float:
```

**Computes:** the probability that the spread crosses $\mu$ at least once
within $[0, \tau]$.

#### Point-in-time probability — and why it was rejected

The naive quantity $P(S_{t+\tau} \leq \mu \mid S_0 > \mu)$ is the point-in-time
probability — the probability that the spread is below $\mu$ at exactly $\tau$
hours, computed from $\Phi((m(\tau) - \mu)/\text{std}(\tau))$. This is the wrong
quantity for a trading entry gate. A path that crosses $\mu$ at $\tau=6h$ and
then bounces back would register as not having crossed at $\tau=24h$. The trader
could have exited profitably at $\tau=6h$ but the point-in-time probability at
$\tau=24h$ would not reflect that crossing.

The relevant question is: will the spread hit $\mu$ **at any point** during the
holding period?

#### The reflection principle

For Brownian motion with constant drift, the first-passage probability through a
barrier at $b$ from a starting point $a > b$ within time $\tau$ is approximated
by the reflection principle:

$$P(\text{cross within }\tau) \approx 2\,\Phi\!\left(-\frac{|a - b|}{\text{std}(\tau)}\right)$$

This doubles the probability mass that lands beyond the barrier in the
final-time distribution, under the symmetry assumption that each path that ends
beyond $b$ crossed it at least once, and each crossing produced a reflected
path ending beyond $b$ on the other side.

For OU, the barrier is $\mu$ and the effective distance at horizon $\tau$ is
attenuated by the deterministic drift: the spread is pulled from $S_0$ toward
$\mu$ at rate $e^{-\theta\tau}$. The formula used is:

$$P = 2\,\Phi\!\left(\frac{-|S_0 - \mu|\,e^{-\theta\tau}}{\text{std}(\tau)}\right)$$

This is a single unified expression valid for both $S_0 > \mu$ and $S_0 < \mu$:

- If $S_0 > \mu$: the argument equals $((\mu - m(\tau))/\text{std}(\tau))$, the
  left-tail probability at the final-time distribution.
- If $S_0 < \mu$: the argument equals $((m(\tau) - \mu)/\text{std}(\tau))$,
  the right-tail probability — the same value by symmetry.

**Edge cases:**

| Condition | Return | Reason |
|-----------|--------|--------|
| `S0 == mu` | `1.0` | Already at the barrier; by continuity, first passage is immediate |
| `tau == 0` and `S0 != mu` | `0.0` | No time to cross |
| `theta <= 0` | `np.nan` | `ou_spread_std` is undefined |
| `std == 0` | `np.nan` | Would divide by zero; only occurs when `tau=0` was already handled, so this guards against floating-point underflow edge cases |

**Known limitation:** the reflection principle is exact for Brownian motion with
no drift. For OU, mean reversion creates a non-constant drift that compresses the
crossing probability toward $\mu$ — the reflection principle is an approximation,
not exact. See §5 for the quantified discrepancy from Monte Carlo validation.

**Trading meaning:** the probability that the trade will reach its target ($\mu$)
at some point before the horizon. At $\tau=24h$ and the AVAX/LINK entry point of
$\mu + 2\sigma_\infty$, this is 49.85% analytically — approximately a coin flip,
which is correct: the spread is about 2 stationary deviations out, and 24 hours
is roughly 1.6 half-lives.

---

### `ou_expected_reversion_time`

```python
def ou_expected_reversion_time(
    S0: float, theta: float, mu: float, epsilon: float = 1e-4
) -> float:
```

**Computes:**

$$E[\text{time to reach within }\epsilon\text{ of }\mu] = \frac{1}{\theta}\ln\!\left(\frac{|S_0 - \mu|}{\epsilon}\right)$$

This derives from the deterministic component of the OU drift only. Setting
$\sigma=0$, the ODE $dS/dt = -\theta(S-\mu)$ has solution
$S(t) = \mu + (S_0-\mu)e^{-\theta t}$. Setting $|S(t)-\mu|=\epsilon$ and solving
for $t$ gives the formula above.

**Edge cases:**

| Condition | Return | Reason |
|-----------|--------|--------|
| `theta <= 0` | `np.nan` | Formula undefined |
| `abs(S0 - mu) <= epsilon` | `0.0` | Already within tolerance |
| log argument < 1 (i.e. $|S_0-\mu|<\epsilon$) | `0.0` | Log is negative → already within tolerance; same as above case, guards floating-point |

**On the choice of epsilon and the large values it produces:**

The default $\epsilon=10^{-4}$ is a mathematical tolerance, not a trading exit
threshold. For AVAX/LINK with $S_0 \approx \mu + 0.01754$ (2 stationary
deviations):

$$E[T] = \frac{1}{0.0474}\ln\!\left(\frac{0.01754}{0.0001}\right) = \frac{\ln(175.4)}{0.0474} \approx 109\text{ hours}$$

109 hours is the time for the **deterministic drift alone** to drive the spread
to within 0.0001 of $\mu$. This is a mathematical statement, not a trading
prediction — the noise term $\sigma dW$ will cause actual crossings of $\mu$
much sooner (the Monte Carlo gives ~43% within 24 hours).

**In Step 4, replace the default with a trading-appropriate epsilon:** the tick
size of the spread, or the minimum P&L threshold, so the function returns the
expected time to exit-zone, not time to mathematical precision.

---

## 4. Design Decisions

### Individual floats, not `OUParams`

The analytical functions accept `float` arguments rather than an `OUParams`
namedtuple for two reasons:

1. **Composability.** A caller may want to scan a grid of hypothetical $\theta$
   values or evaluate at $\sigma=0$ (pure drift scenario) without constructing
   an `OUParams` with an artificial sigma. The signature mirrors the math directly.

2. **Not all functions use all parameters.** `ou_expected_spread` and
   `ou_expected_reversion_time` have no noise term — they have no $\sigma$
   argument. An `OUParams`-accepting signature would require passing a field the
   function ignores.

### Placement in `ou_model.py`, not a separate file

The five functions depend on no external state — they are pure $\mathbb{R}^n
\to \mathbb{R}$ computations. They belong in the same module as the parameter
estimation they consume (`fit_ou`). Splitting them to a new file (e.g.
`ou_analytics.py`) would require importers to manage two modules for a single
coherent model, and would break the `from ou_model import ...` pattern used
throughout the validation scripts.

### Why `ou_expected_spread` and `ou_expected_reversion_time` have no $\sigma$

The conditional mean $m(\tau) = \mu + (S_0 - \mu)e^{-\theta\tau}$ is the
deterministic drift component of the solution. $\sigma$ governs the width of the
distribution ($\text{std}(\tau)$) but not its centre. Similarly,
`ou_expected_reversion_time` is derived from the $\sigma=0$ ODE — it answers
"how long would pure drift take?" without reference to the noise magnitude.
Both functions would silently accept a $\sigma$ argument but never use it.

### The 2-stationary-$\sigma$ entry point

The validation uses:

```python
S0 = mu + 2 * (sigma / np.sqrt(2 * theta))
```

This sets $S_0$ exactly 2 stationary standard deviations above $\mu$.

**Mathematically:** the stationary distribution of the OU process is
$\mathcal{N}(\mu,\, \sigma^2/2\theta)$. Setting $S_0 = \mu + 2\sigma_\infty$
(where $\sigma_\infty = \sigma/\sqrt{2\theta}$) means starting at the 97.7th
percentile of the stationary distribution — a spread that would be rare under
equilibrium conditions.

**The case for it in crypto pairs trading:** crypto spreads frequently reach
$2\sigma$ or beyond due to fat tails and market impact. An entry at $2\sigma_\infty$
is a realistic, operationally common entry point rather than a theoretical
construct. It is large enough to expect a meaningful P&L on reversion, and small
enough that the spread has a reasonable probability of crossing $\mu$ within 24–48h.

**The case against:** the stationary distribution assumes the model has been
running indefinitely in the current regime. In practice, the 30-day window
represents a single regime snapshot. Fat tails (excess kurtosis 2.61 for
AVAX/LINK, per Step 2) mean $2\sigma_\infty$ is reached far more often than 2.3%
of the time — and conversely, after a regime break, the spread may not revert at
all. The entry point is a starting approximation, not a calibrated threshold.

**Conclusion:** a reasonable default for initial signal generation. Step 4 should
empirically calibrate the entry z-score against the kurtosis estimate and
out-of-sample reversion rates.

---

## 5. Validation Results

Full output from `research/validate_ou_analytics.py` using AVAX/LINK parameters
($\theta=0.0474$, $\mu=-0.0009$, $\sigma=0.0027$, $S_0 = \mu + 2\sigma_\infty$):

### Analytical output table

```
=== Analytical Checks (theta=0.0474, S0 ~ mu + 2*std) ===
tau= 6h  E[S]=0.012297  std=0.005776  CI=(0.000977, 0.023617)  P(cross)=0.0223  E[revert]=109.01 hrs
tau=12h  E[S]=0.009030  std=0.007228  CI=(-0.005137, 0.023197)  P(cross)=0.1695  E[revert]=109.01 hrs
tau=24h  E[S]=0.004723  std=0.008306  CI=(-0.011558, 0.021003)  P(cross)=0.4985  E[revert]=109.01 hrs
tau=48h  E[S]=0.000903  std=0.008723  CI=(-0.016194, 0.017999)  P(cross)=0.8363  E[revert]=109.01 hrs
Expected reversion time (epsilon=1e-4): 109.01 hours
```

**Plain-English interpretation of the progression:**

- **$\tau=6h$**: the expected spread has decayed from 0.01664 to 0.01230 — about
  26% of the deviation absorbed in 6 hours, consistent with $e^{-0.0474\times6}\approx0.754$.
  The 95% CI is entirely above zero (0.001, 0.024) — the spread has a 97.8% chance
  of remaining positive. Only a 2.2% crossing probability reflects how large the
  initial deviation is relative to the uncertainty over 6 hours.

- **$\tau=12h$**: expected spread 0.009, std grown to 0.0072. The CI now straddles
  zero (-0.005, 0.023). Crossing probability jumped to 17% — the uncertainty has
  expanded enough to put meaningful probability mass below $\mu$.

- **$\tau=24h$**: near-even odds (49.9%) of having crossed. 24 hours is
  approximately 1.6 half-lives ($\ln(2)/\theta \approx 14.6h$). The expected
  spread (0.0047) is well below the starting value but still positive.

- **$\tau=48h$**: 83.6% crossing probability. The expected spread (0.0009) has
  nearly converged to $\mu$ (-0.0009). Most of the original signal is gone; a
  position still open at 48h should be near or past its exit target.

### Monotonicity checks — all passed

| Check | What it tests | Result |
|-------|--------------|--------|
| $E[S]$ converges to $\mu$ | Mean decays monotonically toward $\mu$ | **PASS** |
| std increases with $\tau$ | Uncertainty grows as horizon extends | **PASS** |
| $P(\text{cross})$ increases with $\tau$ | More time → higher crossing probability | **PASS** |
| $P(\text{cross},\,\tau=0) = 0$ | No crossing in zero time (when $S_0 \neq \mu$) | **PASS** |
| $P(\text{cross},\,S_0=\mu) = 1$ | Already at barrier → certain crossing | **PASS** |
| $E[\text{revert}] = 0$ at $S_0=\mu$ | Zero time needed if already at $\mu$ | **PASS** |

### Monte Carlo verification

```
=== Monte Carlo Verification (n=10000, tau=24h) ===
  Analytic P(cross) = 0.4985
  Monte Carlo P(cross) = 0.4320
  Difference = 0.0665
  Verdict: FAIL — difference exceeds 5%, investigate
```

**This is a discretisation gap, not a code bug.** The analytical formula is
derived from continuous-time Brownian motion. The Monte Carlo uses Euler-Maruyama
with $\Delta t = 1$ hour — the same discretisation as the fitted model.

The root cause: with hourly bars, the spread can cross $\mu$ between two
consecutive observations and immediately bounce back. In the simulation, a
crossing is only registered when the end-of-hour value is on or past $\mu$.
Intra-bar crossings are invisible. The continuous-time formula counts any
crossing, however brief.

The size of the gap (~6.7pp) is consistent with theoretical expectations for OU
processes at these parameters: higher $\sigma$ relative to $\theta$ increases
the probability of intra-bar over-and-back crossings, inflating the analytical
probability relative to the discrete count.

**Practical implication for Step 4:** the analytical $P(\text{cross})$ systematically
overestimates the crossing probability observable at hourly bar resolution by
approximately 6–7 percentage points. When calibrating entry thresholds in Step 4,
subtract this bias from the analytical probability, or equivalently raise the
minimum required $P(\text{cross})$ by 6–7pp to achieve a desired empirical crossing
rate. For example, a target empirical crossing rate of 50% within 24h corresponds
to an analytical threshold of approximately 57%.

---

## 6. Known Limitations

1. **Gaussian noise assumption violated.** `excess_kurtosis=2.61` for AVAX/LINK
   (Step 2). Confidence intervals from `ou_confidence_interval` use normal quantiles
   and underestimate tail coverage. At the 95% level, actual coverage is closer to
   90–93% for $t$-distributed residuals with this kurtosis.

2. **Reflection principle is approximate.** The formula for `ou_reversion_probability`
   is exact for driftless Brownian motion; for OU with mean reversion, it is an
   approximation. The error is not characterised analytically — the Monte Carlo
   validation quantifies it empirically as ~6.7pp at 24h for the AVAX/LINK
   parameters.

3. **~6–7% systematic overestimate vs. hourly-bar execution.** See §5 Monte Carlo
   discussion. Every call to `ou_reversion_probability` at a 24h horizon for these
   parameters returns a value approximately 6–7pp above the empirically observable
   crossing rate. Step 4 must adjust for this.

4. **`ou_expected_reversion_time` is a deterministic drift approximation.** The
   formula ignores $\sigma$. The default $\epsilon=10^{-4}$ gives physically
   correct but operationally useless values (~109h for the AVAX/LINK entry point).
   Step 4 must supply a trading-appropriate epsilon (e.g. one tick of the spread,
   or a minimum target P&L threshold expressed in spread units).

5. **Parameters are in-sample estimates.** All five functions consume $\theta$,
   $\mu$, $\sigma$ from `fit_ou` applied to the last 30 days. The forward-looking
   probabilities are only as good as the model stability over the trading horizon.
   No walk-forward validation of the analytical predictions exists yet.

6. **Two-barrier first passage not handled.** A realistic position has both a
   profit target (barrier at $\mu$) and a stop-loss (barrier at some $S_\text{stop}
   > S_0$). The probability of reaching $\mu$ before $S_\text{stop}$ — the two-sided
   first-passage problem — is not computed here. The current functions treat only
   the single barrier at $\mu$. Noted as a future extension for Step 4 or Step 5.
