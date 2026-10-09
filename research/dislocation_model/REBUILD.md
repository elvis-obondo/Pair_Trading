# Rebuilding the dislocation datasets

The datasets in `research/datasets/` are 93MB and **not tracked**. This file is
the part that is in git: the recipe. The bytes only need to be on disk.

They were produced on 2026-10-04 in a session-scoped temp directory and promoted
here on 2026-10-06 before they were garbage-collected. Nothing else in the repo
could have regenerated them, because nothing else recorded the commands.

## Prerequisites

`user_data/data/` must be populated — it is not tracked either. Refresh it with
`scripts/update_data.sh`, and always pass an explicit `--end-date` downstream: one
partially-formed trailing 30m bar silently cuts the universe from 212 tickers to 17.

## The commands, in order

Each one depends on the one before it.

### 1. `disloc.npz` + `disloc_meta.parquet` — about 30s

    .venv/bin/python research/dislocation_model/mkdisloc.py

60,000 dislocations: 3,000 pairs x up to 20 triggers each, stride-sampled across
each pair's own history, from the 30-minute panel (36,172 bars x 212 tickers,
2024-09-11 to 2026-10-04). Per row: a 336-bar fit window and 21 outcome steps,
both in sigma units of the entry bar's frozen geometry.

    windows   (60000, 336)  float32   the 7-day fit window, ending AT the entry bar
    outcomes  (60000, 21)   float32   entry bar plus 20 x 30min = 10 hours ahead
    meta                              ticker_a/b, entry_time, bar_index, z_at_entry,
                                      beta, alpha, mu, sigma, r2, pair_triggers_true, day

**It is not deterministic across a changed panel.** The pair draw is seeded
(`default_rng(20261004)`) but it permutes `universe_panel.tradeable_pairs(cols)`,
so a panel with new listings yields a different sample. A rebuild reproduces the
published numbers only on the same panel. If the numbers move, suspect this first.

> **A rebuild today will NOT reproduce the promoted datasets.** `universe_panel.py`
> has an uncommitted change (as of 2026-10-06) adding `FACTOR_ONLY = {BTC, ETH}`:
> the two are carried in the panel for market-factor construction and excluded
> from pair formation, and leading rows that exist only because a FACTOR_ONLY
> ticker reaches further back are trimmed. Both move `tradeable_pairs` and the
> panel's extent, so both move the sampled pairs. The promoted datasets predate
> it. Expect the split counts (41,936 / 18,064) to shift, and re-read
> `validate_dislocation_harness.py` as a change detector rather than a pass/fail
> when they do.
>
> Measured 2026-10-06, the gap is already visible:
>
>     promoted datasets came from   36,172 bars x 212 tickers, 753 days
>     the panel today loads         36,215 bars x 214 tickers, 754 days
>
> `validate_universe_panel.py` fails one assertion on exactly this ("212 tickers:
> 214") and that assertion belongs to the FACTOR_ONLY change, not to this
> pipeline. Settle the ticker count before rebuilding, or the rebuilt dataset
> will not be comparable to any number in `NUMBERS.md` or `docs/STATE.md`.

**The invariant that makes it trustworthy.** `(spread[i]-mu_i)/sigma_i` IS `z[i]`
by definition, so `windows[:,-1]` and `outcomes[:,0]` must both equal `z_at_entry`
exactly. The script asserts it and `validate_dislocation_harness.py` re-checks it.
An off-by-one bar in either window breaks this and nothing else would catch it.

### 2. `envfeat.npz` — about 2 min

    .venv/bin/python research/dislocation_model/envfeat.py

Five environment features, 60,000 x 5 float32 plus a names list. Joined onto the
EXISTING `disloc_meta.parquet` row-for-row by position — it does NOT rebuild
disloc.npz, for the determinism reason above.

    vol_48      mean |30-minute spread change| over the last 48 window bars, in sigma
    vratio      step sd / level sd over the last 96 bars, normalised so iid gives 1
    vol_slope   sd of steps over the last 16 bars / sd over the prior 32
    sandwich    mean per-bar gap between the leg-high/low spread bound and the
                close-to-close spread move, last 96 bars, in sigma
    off_mark    hedge-weighted mean |close - mark| across both legs, last 96 bars' time

The first three come from `windows` and `meta` alone. `sandwich` reads the raw
30-minute high/low feathers; `off_mark` reads the 1-hour mark feathers. Both do
their own grid snap and log transform to match the panel, because the normalized
store carries `close` only.

`vratio`'s iid divisor is `IID_VRATIO_DIVISOR[96] = 3.396899`, SIMULATED, not
derived. The analytic `sqrt((n^2-1)/(6n))` = 3.999783 normalises the ratio of
expectations and is 17.7% too large for the expectation of a ratio. If you change
`RATIO_BARS`, the constant must be re-simulated — `iid_vratio_norm` will do it for
an unknown n, and the validator checks the result on a fresh seed.

Deterministic given `disloc.npz` and the panel: the validator asserts a rebuild is
bit-identical to the stored matrix. Saved runs are in `logs/`.

**Steps 2 and 3 used to be `extfeat.npz` and `wave_full.npz`.** Both were removed
on 2026-10-09 along with `external.py` and `wave_full.py` (now in
`attic/research/`). They were built against the 212-ticker / 36,172-bar panel and
were stale as well as superseded.

## Checking a rebuild

    .venv/bin/python research/validate_dislocation_harness.py

It asserts the split (41,936 / 18,064 over 667 / 79 days), the alignment
invariant, and — for the feature matrix — row-for-row join alignment, no
lookahead per row, the sandwich bound ordering, sign-folding invariance, and
per-column finiteness counts and percentiles. If the split counts move, the panel
changed — see the determinism note above.

The old published-cell assertion (WINDOW / regression / 10h = -0.0104) was retired
with `window_features` on 2026-10-09. It ran through a function that no longer
exists, and keeping a dead function alive to satisfy a test is not a trade this
project makes.

## What is NOT here

The one-off analysis scripts from the modelling phase are in
`attic/modelling_scratch/`, with their logs. Their findings are in
`docs/STATE.md`; the scripts themselves are not part of the pipeline and are not
expected to run against a rebuilt dataset without path edits.
