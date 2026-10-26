# Step 5 — Position Sizing
## Crypto Pairs Trading Research System | OKX Futures | 1h OHLCV

---

## 1. Purpose of Step 5

Steps 1–4 built the full signal pipeline: pair screening, OU fitting, entry signal
generation (five gates), exit signal generation (three gates). Every output of that
pipeline was in spread units or dimensionless quantities — crossing probabilities,
log volatility ratios, z-scores. No dollar amounts anywhere.

Step 5 answers the question: given a valid entry signal, how much capital do we deploy?

**The design goal:** size each trade so that a worst-case stop-out — the adverse move
gate in `generate_exit_signal` firing at exactly `stop_sigma * sigma_stationary` from
entry — costs exactly a fixed fraction of total capital. Dollar risk per trade is
constant. Position size varies with market conditions.

**Single pair constraint:** the system trades one pair at a time. Capital is either
fully deployed in one open trade or idle. No simultaneous positions. This simplifies
the sizing problem: there is no cross-trade capital allocation to manage. A new
signal that fires while a trade is open is skipped.

---

## 2. Design Decisions

### 2.1 Fixed risk budget over fixed fraction

Two candidate approaches were considered.

**Fixed fraction:** deploy the same fraction of capital on every trade regardless of
spread conditions. Simple, but ignores that different trades have different risk
profiles — a pair with high `sigma_stationary` is riskier per unit notional than one
with low `sigma_stationary`.

**Fixed risk budget:** fix the dollar amount risked per trade (e.g. 1% of capital) and
let the position size follow from current market conditions. The fraction deployed
varies trade to trade, but the dollar loss on a worst-case stop-out is always the same.

Fixed risk budget was chosen. Rationale: you are controlling what actually matters
— how much you lose when wrong — not an arbitrary notional fraction. The fraction is
a derived output, not a fixed input.

Note: varying position size by signal quality (e.g. scaling up on higher
`reversion_probability`) was explicitly deferred. It only adds value if the quality
signal is actually predictive of outcomes, which is untested. Step 6 backtest is
required before revisiting. Fixed risk budget keeps sizing as a clean, isolated
variable for Step 6.

---

### 2.2 sigma_stationary as the risk unit

Two candidates for measuring spread risk:

**Raw sigma:** the per-step OU noise parameter in spread units per $\sqrt{\text{hour}}$.
Rejected because it ignores mean reversion speed. Two spreads with identical $\sigma$
but different $\theta$ have very different risk profiles — the slow-reverting spread
can drift much further before pulling back. $\sigma$ alone is misleading as a risk unit.

**sigma_stationary:** $\sigma_{\text{stat}} = \sigma / \sqrt{2\theta}$, the standard
deviation of the spread's stationary distribution. This is where the spread spends
most of its time in the long run. It accounts for both noise level and reversion speed
correctly. A $2.5\,\sigma_{\text{stat}}$ adverse move means the spread has reached a
level that is extreme relative to its own long-run behaviour — a meaningful signal of
model failure.

`sigma_stationary` was chosen. It is already the unit used by the adverse move stop
in `generate_exit_signal`, which means the position sizer and the exit signal share
a common risk language.

---

### 2.3 No kurtosis scalar

A kurtosis scalar on `sigma_stationary` was proposed and then rejected after careful
reasoning. The argument for it: crypto spreads have excess kurtosis ~2.6, so
`sigma_stationary` understates tail risk, and the effective risk unit should be
inflated by a factor derived from the Cornish-Fisher adjustment (~1.3x at the 97.5th
percentile).

The argument against: `stop_sigma=2.5` was already chosen in Step 4 specifically
because of fat tails. It was pushed out from 2.0 to tolerate the higher frequency of
large spread moves under a leptokurtic distribution without premature stop-outs.
Adding a separate kurtosis multiplier to the sizer would double-count an adjustment
already baked into the stop placement.

The correct time to address slippage through the stop — the actual residual tail risk
— is Step 6, with real trade outcomes to measure against. A made-up multiplier now
would project false precision.

---

### 2.4 Leg sizing — Option A

The spread is defined as:

$$\text{spread} = \text{price}_A - \alpha - \beta \cdot \text{price}_B$$

where $\beta$ is the OLS hedge ratio in log-price space. To respect this relationship
in dollar terms, leg A is treated as the base notional and leg B is derived from
$\beta$:

$$\text{leg\_a\_notional} = f \cdot C$$
$$\text{leg\_b\_notional} = \beta \cdot f \cdot C$$
$$\text{total\_deployed} = f \cdot C \cdot (1 + \beta)$$

where $f$ is the fraction and $C$ is total capital.

Two alternatives were considered and rejected:

**Dollar-neutral (equal notionals):** set both legs to $N$ dollars regardless of
$\beta$. Rejected because it ignores the hedge ratio entirely. The actual log-price
movements would not cancel the way the OLS regression assumed, producing a spread
that drifts relative to the model.

**Fixed total capital:** split $N$ between legs so total deployed is always $N$.
Rejected because it shrinks leg A notional as $\beta$ grows, which is unintuitive
and inconsistent with treating leg A as the base.

**Sign convention:** `leg_b_notional` may be negative when $\beta < 0$. This is
correct — it means the direction on leg B is reversed. `abs(beta)` is never taken.
Masking the sign would silently produce wrong trade directions.

---

### 2.5 stop_sigma sync requirement

`compute_position_size` takes a `stop_sigma` parameter (default 2.5) that must match
the `stop_sigma` passed to `generate_exit_signal` for the same trade. If they differ,
the position is sized to a stop level that is not where the exit fires — the dollar
risk guarantee breaks. The function does not enforce the match. The caller is
responsible. This is documented in the docstring and must be enforced by the
backtester in Step 6.

---

### 2.6 Pure functions module

`position_sizer.py` follows the same conventions as all other pure function modules
in the system: no pandas, no printing, no plotting, no file I/O, no `__main__` block.
Takes individual floats extracted from the entry signal dict, not the dict structure
itself beyond the three fields it reads. Returns values. Caller decides what to do
with them.

---

## 3. compute_position_size — Specification

### 3.1 Function signature

```python
def compute_position_size(
    entry_signal: dict,
    capital: float,
    risk_budget_pct: float = 0.01,
    stop_sigma: float = 2.5,
) -> dict | None:
```

---

### 3.2 Parameters

| Parameter | Type | Units | Meaning |
|---|---|---|---|
| `entry_signal` | dict | — | Dict from `generate_entry_signal`. Three fields read: `sigma_at_entry`, `theta_at_entry`, `beta_at_entry`. All others ignored. |
| `capital` | float | dollars | Total capital. Must be finite and strictly positive. |
| `risk_budget_pct` | float | dimensionless | Fraction of capital to risk per trade. Default 0.01 (1%). Must be finite and strictly positive. |
| `stop_sigma` | float | $\sigma_{\text{stat}}$ units | Stop distance multiplier. Default 2.5. Must match `generate_exit_signal`. Must be finite and strictly positive. |

---

### 3.3 Implementation steps

$$\sigma_{\text{stat}} = \frac{\sigma}{\sqrt{2\theta}}$$

$$\text{risk\_unit} = \text{stop\_sigma} \times \sigma_{\text{stat}}$$

$$f = \frac{\text{risk\_budget\_pct}}{\text{risk\_unit}}$$

$$\text{leg\_a\_notional} = f \cdot C \qquad \text{leg\_b\_notional} = \beta \cdot f \cdot C \qquad \text{total\_deployed} = f \cdot C \cdot (1 + \beta)$$

---

### 3.4 Return dict — five fields

| Field | Type | Units | Meaning |
|---|---|---|---|
| `leg_a_notional` | float | dollars | Notional on leg A. Always positive when inputs are valid. |
| `leg_b_notional` | float | dollars | Notional on leg B, scaled by $\beta$. May be negative when $\beta < 0$. Correct — do not take abs. |
| `total_deployed` | float | dollars | `leg_a_notional + leg_b_notional`. May be less than `leg_a_notional` when $\beta < 0$. |
| `fraction` | float | dimensionless | Fraction of capital on leg A. Derived output, not a fixed input. |
| `sigma_stationary` | float | spread units | $\sigma / \sqrt{2\theta}$. Carried through for backtest traceability and Step 6 calibration. |

---

### 3.5 None return conditions

Returns `None` if any of the following hold:

- `sigma_at_entry` is not finite or $\leq 0$
- `theta_at_entry` is not finite or $\leq 0$
- `beta_at_entry` is not finite
- `capital` is not finite or $\leq 0$
- `risk_budget_pct` is not finite or $\leq 0$
- `stop_sigma` is not finite or $\leq 0$
- `risk_unit <= 0` (safety guard; should not occur given the above)

All six input conditions are evaluated before returning `None` — no short-circuit on
first failure.

---

## 4. Validation — validate_position_sizer.py

Three synthetic tests. No live data. No fitting functions. All inputs hardcoded.

**Shared synthetic entry signal:**

```python
entry_signal = {
    "sigma_at_entry": 0.002722,
    "theta_at_entry": 0.0474,
    "beta_at_entry":  1.2,
    "entry_spread":   0.010,   # not read by function
    "mu_at_entry":   -0.001,   # not read by function
}
```

---

### Test 1 — Normal case: all five fields verified

Parameters: `capital=100_000`, `risk_budget_pct=0.01`, `stop_sigma=2.5`

Hand-computed expected values:

$$\sigma_{\text{stat}} = \frac{0.002722}{\sqrt{2 \times 0.0474}} = \frac{0.002722}{\sqrt{0.0948}} \approx \frac{0.002722}{0.307923} \approx 0.008841$$

$$\text{risk\_unit} = 2.5 \times 0.008841 \approx 0.022101$$

$$f = \frac{0.01}{0.022101} \approx 0.452456$$

$$\text{leg\_a} = 0.452456 \times 100{,}000 \approx 45{,}245.57$$

$$\text{leg\_b} = 1.2 \times 45{,}245.57 \approx 54{,}294.68$$

$$\text{total} = 45{,}245.57 + 54{,}294.68 \approx 99{,}540.25$$

Tolerances: $< 0.01$ for dollar fields, $< 10^{-6}$ for dimensionless fields. All
five fields: PASS.

Note on `total_deployed`: the value $\approx 99{,}540$ on \$100k capital is not an
error. It follows from $f \cdot C \cdot (1 + \beta) = 0.452456 \times 100{,}000
\times 2.2$. The trade deploys nearly full capital because $\beta = 1.2$ means leg B
is 120% of leg A.

---

### Test 2 — Degenerate inputs return None

Three sub-cases, each using a fresh dict copy — shared dict never mutated:

| Sub-case | Modification | Expected | Result |
|---|---|---|---|
| A | `theta_at_entry = 0.0` | None | PASS |
| B | `sigma_at_entry = np.nan` | None | PASS |
| C | `capital = -50_000.0` | None | PASS |

---

### Test 3 — stop_sigma sensitivity: wider stop → smaller fraction

$$\text{stop\_sigma} = 2.0 \Rightarrow f \approx 0.565570$$
$$\text{stop\_sigma} = 3.0 \Rightarrow f \approx 0.377046$$

Wider stop $\Rightarrow$ larger `risk_unit` $\Rightarrow$ smaller fraction needed to
keep dollar risk fixed. Direction check: PASS.

---

## 5. Capital Convention for Backtesting

Step 5 was validated at \$100k for arithmetic clarity. The backtest in Step 6 will
run at \$1,000 capital. At that scale:

- `risk_budget_pct=0.01` means \$10 risked per stop-out
- Typical `leg_a_notional` ≈ \$452, `leg_b_notional` ≈ \$543, `total_deployed` ≈ \$995
  on the AVAX/LINK parameters
- The system is essentially fully invested when a trade is open
- When a trade is open and a new signal fires, the signal is skipped — capital is not
  available. The backtester must enforce this.
- P&L per trade will be in the range of single to low tens of dollars. The absolute
  numbers are small; the research goal is validating edge, not scale. The system
  scales linearly with capital.

---

## 6. Known Limitations and Items for Empirical Calibration in Step 6

1. **`risk_budget_pct=0.01` is a starting point.** The 1% default is a conventional
   starting point, not an empirically derived optimum. Whether 1% risk per trade is
   appropriate given the strategy's win rate, average hold time, and signal frequency
   is untested. Step 6 backtest required.

2. **`stop_sigma` sync is unenforced.** The position sizer and exit signal generator
   share a `stop_sigma` parameter that must agree. The function does not enforce this.
   If they drift apart in the backtester, the dollar risk guarantee silently breaks.
   Step 6 must enforce sync explicitly.

3. **`leg_b_notional` sign convention requires backtester awareness.** A negative
   `leg_b_notional` means leg B is short. The backtester must correctly interpret the
   sign when computing P&L — a loss on a short leg is a gain when the spread moves
   adversely, and vice versa.

4. **`total_deployed` near full capital at typical parameters.** With $\beta \approx 1.2$
   (AVAX/LINK), total deployed is approximately $2.2 \times \text{leg\_a\_notional}$,
   which is nearly full capital at `risk_budget_pct=0.01`. Different pairs with
   different $\beta$ will produce different capital utilisation. The backtester should
   track this per trade.

5. **Transaction costs not modelled.** OKX perpetual futures fees (approximately 0.02%
   maker / 0.05% taker) are not included in the position sizer or anywhere in the
   pipeline. At \$1k capital, fee costs of \$0.20–\$0.50 per leg per trade are
   meaningful relative to expected P&L per trade. Step 6 must model costs even
   approximately, or results will be misleadingly optimistic.

6. **Fraction can exceed 1.0 on low-volatility pairs.** If `sigma_stationary` is very
   small, `risk_unit` is very small, and `fraction = risk_budget_pct / risk_unit` can
   exceed 1.0 — implying more than 100% of capital on leg A alone. The function does
   not cap `fraction`. The backtester must guard against this, either by capping
   fraction at a maximum or by rejecting trades where `total_deployed > capital`.
