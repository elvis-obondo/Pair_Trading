# Experiment spec: change-point detection & Kalman filter go/no-go

Handoff document for a new session. Purpose of both experiments: **decide whether
to build these at all**, not to build them. Neither should touch the live
selection/backtest/trading pipeline. Everything here is scratchpad/prototype work
that ends in a report with numbers, not a shipped feature.

Context you need: this project trades cointegrated crypto futures pairs
(`research/pair_analysis.py`, `research/ou_model.py`, `research/signal_generator.py`).
An OU model is fit per pair on a rolling ~30-day window (1441 bars at 30-min
frequency) to estimate mean-reversion speed (theta), long-run mean (mu), and
volatility (sigma). Student-t residuals and Monte Carlo reversion-probability
estimation were already added this week (done, working, not part of this spec).
Two follow-on ideas are still open:

1. **Change-point detection** — formally detect when a pair's cointegration
   relationship broke down, instead of relying on a fixed recent-window check.
2. **Kalman filter / state-space OU** — track theta/mu as continuously-updating
   latent states instead of refitting on a fixed window.

Both were flagged as "conditionally okay — depends on something we haven't
checked yet." This spec is those checks.

---

## How much input this needs from the user, and how much is a safe default

Read this before starting. The three items that originally needed the user's
input (dependency choice, decision-rule thresholds, convergence tolerance) have
already been asked and confirmed — see below, don't re-ask them. Items marked
**[DEFAULT]** were never blocking — proceed with the stated choice, don't ask.
The user has said explicitly that they want to be closely involved in
implementation choices for work like this, though — if something comes up
during the experiments that isn't already decided here, surface it rather than
guessing, same standing guidance that applied to the OU/Monte Carlo work this
spec follows on from.

**Resolved already — confirmed by the user, proceed on these without re-asking:**
- **`ruptures` is approved as a dependency.** Add it (`pip install ruptures`,
  and to whatever requirements file this project uses) rather than hand-rolling
  CUSUM. Use its Pelt or Binseg method for Experiment 1's detector.
- **The go/no-go thresholds below are confirmed, not just starting guesses**:
  detection lag under ~3-5 days (median, across positive controls) with
  rare/absent false positives on negative controls → build it. Kalman filter
  convergence under ~20-25% of the 30-day window, with the required EWMA
  comparison (Step 5 of Experiment 2) showing meaningfully better post-convergence
  tracking → build it. Otherwise, don't.
- **The ±15% tolerance band for "converged"** in the Kalman experiment (Step 4)
  is confirmed.

Still worth a sanity check mid-run rather than blind adherence: if the numbers
come back right at the edge of a threshold (e.g., convergence at 24% of the
window, or detection lag at 4 days), that's a genuine judgment call, not an
auto-pass/auto-fail — flag it in the report rather than mechanically applying
the cutoff.

**[DEFAULT] — proceed without asking:**
- Which specific pairs to use as positive/negative controls (derived
  procedurally from live diagnostics, described below, not hand-picked).
- The synthetic-data parameter ranges for the Kalman filter experiment (pulled
  from real fitted values on current data, described below).
- Implementation language/libraries otherwise (numpy/scipy, matching the rest
  of `research/`).
- Where output goes: scratchpad first. Nothing gets written into
  `research/pair_analysis.py`, `research/ou_model.py`, or `research/signal_generator.py`
  as part of this spec. If either experiment says "build it," that's a
  separate, later task with its own review.

**One data gotcha to know before starting**: RLS was removed from the whitelist
and its feather files deleted this week (turnover below the $450k liquidity
floor). RLS/ZK was this session's best-characterized example of a real
cointegration breakdown (broke down ~July 24, one blip July 31, stayed broken).
**Don't depend on that specific historical example being available** — the
procedure below re-derives fresh positive/negative control pairs from whatever
data currently exists, precisely so this experiment doesn't silently fail or
(worse) silently use stale/wrong data if RLS's files are gone. If RLS's raw
feather data is still needed for some reason, it would have to be re-downloaded
via the existing `freqtrade download-data` tooling — don't assume it's on disk.

---

## Experiment 1: Change-point detection

**Question to answer**: can a change-point detector reliably flag a real
cointegration breakdown, and how many days of lag does it take to do so — measured
against real data, not synthetic.

### Step 1 — Get a diagnosed pool with the fine-grained trace available

Run a walk-forward selection (`research/run_all.py`, or call
`analyze_top_pairs()` directly) to get the full diagnosed `summary` DataFrame —
not just the tradeable-filtered output. Use `end_date` at least a few weeks in
the past so there's holdout data after it to inspect, same walk-forward pattern
already used throughout this project.

### Step 2 — Procedurally pick positive and negative controls

From the full `summary` table:
- **Positive controls (likely-broken pairs)**: `coint_stability >= 0.5` AND
  `recent_cointegrated == False`. This is the exact signature a real breakdown
  produces — decent historical cointegration score, but the recent-window check
  fails. Pick the top 3-5 by `coint_stability` (highest historical score makes
  the "this used to work" story clearest).
- **Negative controls (stable throughout)**: `coint_stability >= 0.75` AND
  `recent_cointegrated == True`. Pick 3-5.

### Step 3 — Build the fine-grained trace per selected pair

For each of the 6-10 pairs selected above, compute the daily-stride rolling
cointegration p-value series — this already exists, reuse it directly:

```python
from pair_analysis import rolling_coint, BARS_PER_DAY
roll_p_fine = rolling_coint(price_a, price_b, window=7*BARS_PER_DAY, stride=BARS_PER_DAY)
```

Use as much history as is available for the pair (up to the ~47-66 day ceiling
most tickers have — checked this week, don't assume more exists), not just the
30-day selection window, so there's enough post-break data to test detection lag
against.

### Step 4 — Label the positive controls by eye

For each positive-control pair, plot or print the p-value trace and identify
(by inspection, same way RLS/ZK's July 24 break was identified this week) the
approximate day the relationship broke down. This eyeballed date is the ground
truth the detector gets scored against. If a "positive control" pair's trace
doesn't actually show a clear break on inspection, drop it and pick another —
don't force a label onto ambiguous data.

### Step 5 — Implement the detector(s)

Simplest defensible option: CUSUM on the p-value series (or on
`-log10(p-value)`, which behaves better numerically since p-values are bounded
in [0,1] and CUSUM assumes roughly-continuous-scale data). If the dependency
question above is resolved in favor of a library, `ruptures` (Pelt or Binseg
method) is the standard choice and saves implementation time. Whichever is
used, it needs a size parameter (how much data after a candidate breakpoint is
needed to confirm it) — expose that as a tunable, since Step 6 sweeps it.

### Step 6 — Score it

For each positive control: measure the lag, in days, between the eyeballed
break date and the date the detector actually flags it. Report the distribution
(min/median/max across the 3-5 positive controls), not just one number — lag
will vary by how sharp each break is.

For each negative control: does the detector flag anything at all? Report
false-positive count and, if any, how "confident" the false alarm looked
relative to the true positives (a detector that flags real breaks with high
confidence and stable pairs with low confidence is more usable than one where
the two look similar).

### Decision rule (confirmed)

If median detection lag is under ~3-5 days AND false positives on negative
controls are rare/absent, that's a green light to build it as a real monitoring
tool (start as a standalone daily check the user reads, not something wired
into live trading decisions automatically — lower-risk integration path). If
lag is comparable to "however long it'd take a human to notice by eyeballing
the diagnostics table anyway," or false positives are frequent, that's a signal
to not invest further without rethinking the method or the size parameter —
report that outcome honestly, don't tune the threshold after the fact to
manufacture a pass.

---

## Experiment 2: Kalman filter convergence

**Question to answer**: does a Kalman-filtered theta/mu estimate converge fast
enough, relative to the ~30-day window this project actually has, to be worth
building over the much simpler EWMA alternative — with a real head-to-head
comparison, not just "does it converge in isolation."

### Step 1 — Pull realistic parameters from real data, don't invent them

Call `fit_ou()` (`research/ou_model.py`) on 8-10 real pairs from a current
selection run — a mix of fast and slow half-lives, matching the actual observed
range this project has seen (roughly 7-40+ hours, per this week's diagnostics —
pull the real numbers fresh rather than trusting that range verbatim). Record
each pair's (theta, mu, sigma). This is the parameter grid Step 2 simulates
from — grounded in what this project's data actually looks like, not made-up
textbook values.

### Step 2 — Simulate synthetic OU paths

For each (theta, mu, sigma) triple from Step 1, simulate a synthetic spread
path at 30-min bar frequency, at least 1441 bars long (matching the real
window), using the same discretization the project's own fitting assumes:

```
S[t+1] = S[t] + theta * (mu - S[t]) * dt + sigma * sqrt(dt) * innovation[t]
```

Run this **twice per parameter set** — once with Gaussian innovations, once
with Student-t innovations (matching this week's fat-tail finding, df in the
range already being fit on real data). The Kalman filter is provably optimal
only under Gaussian noise; running both tells you how much worse it degrades
under the noise this project's data actually has, not just how it performs on
the textbook case.

### Step 3 — Implement the filter as time-varying-coefficient regression, not a naive parameter filter

Important framing, get this right or the experiment tests the wrong thing: the
goal is to track theta and the AR(1) intercept as **states that follow a random
walk**, with the spread's own AR(1) relationship as the (linear!) observation
equation:

```
observation:      dS[t] = c[t] + lam[t] * S[t-1] + noise
state transition:  c[t] = c[t-1] + process_noise
                  lam[t] = lam[t-1] + process_noise
```

This is linear-Gaussian in the state (`c[t]`, `lam[t]`) given `S[t-1]` as the
time-varying observation coefficient — a standard Kalman filter applies
directly, no extended/unscented filter needed. (This is, not coincidentally,
the same mathematical idea the original live pair's name — RLS, recursive least
squares — refers to; a Kalman filter here is RLS's more general form.) `theta`
recovers from `lam` the same way the existing `fit_ou()` already does
(`theta_raw = -lam`).

Process-noise magnitude (how much the filter believes `c`/`lam` can drift per
bar) is the key tunable — start with something small and let Step 4's
convergence measurement tell you if it needs adjusting, don't hand-pick a value
that's designed to converge fast.

### Step 4 — Measure convergence, precisely defined

Start the filter from an uninformed initial state (e.g., `lam=0`). Track the
filtered `theta` estimate bar-by-bar. Define "converged" as: the first bar after
which the filtered estimate stays within **±15%** of the true theta for the rest
of the series (confirmed tolerance). Record that bar count, convert to days
(÷48 bars/day at 30-min bars).

Do this across every (theta, mu, sigma) pair from Step 1, for both Gaussian and
Student-t innovations. Report the distribution of convergence times, not a
single number — expect faster-reverting (higher theta) pairs to converge
quicker than slow ones, and that pattern is itself useful information, not noise
to average away.

### Step 5 — Required comparison: EWMA on the same synthetic data

Implement the EWMA alternative (exponentially-weighted re-estimation of the same
`c`/`lam`, decay constant your choice, document what you picked) and run it on
the identical synthetic paths from Step 2. Measure the same thing — how quickly
and how accurately it tracks the true theta — using a comparable error metric
(e.g., tracking error over the last 20% of the series, once both methods should
have stabilized). This comparison is the actual point of the experiment. "Kalman
converges in N days" isn't decision-useful on its own; "Kalman converges in N
days and tracks true theta with X% less error than EWMA once both have
stabilized" is.

### Decision rule (confirmed)

Compute average convergence time as a fraction of the 30-day window. If it's
under roughly 20-25% of the window on the realistic parameter grid, and the
EWMA comparison shows Kalman tracking meaningfully more accurately once
converged, that's a case for building it. If convergence eats a large fraction
of the window, or EWMA tracks about as well once you account for its own
effective lag, that's a case for sticking with EWMA and not taking on the added
complexity. Report whichever answer the numbers give — this experiment is
explicitly allowed to conclude "don't build this."

---

## What to hand back

For each experiment: the measured numbers (detection lag distribution and
false-positive count for #1; convergence-time distribution and the EWMA
comparison for #2), the code used to produce them (scratchpad, not committed),
and an explicit recommendation against the decision rules above — but flag any
place a decision-rule threshold drove the recommendation, since those thresholds
are this session's starting guesses, not settled. Do not proceed to building
either feature into the real pipeline as part of this task, even if the numbers
look good — that's a separate, explicitly-scoped follow-up.
