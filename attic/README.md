# attic — quarantine, not a graveyard

Nothing here was deleted. Everything was moved with `git mv` on 2026-10-06, in one
commit, so every step is a one-line revert and a mistake shows up as a failing
validator rather than as silence.

**Deletion is a separate decision on a separate day.** Do not `git rm` anything in
here as a tidying pass.

## The rule that governed the move

Git makes code recoverable. What is not recoverable is knowing *why* something is
not worth retrying. So nothing was moved until its findings were written down
somewhere durable — and for everything here that place is `docs/STATE.md`.

Where a file's result existed nowhere but a terminal, it was **re-run first** and
its log saved. That applies to `attrib`, `horizon`, `leakcheck` and `robust` in
`modelling_scratch/` — four results that would have been lost, one of which
(`leakcheck`) overturned the only passing cell of the whole modelling phase.

## What is here

### `docs/` — five superseded handoffs

Consolidated into `docs/STATE.md`. Read that first; come here for the detail it
compresses.

    SESSION_HANDOFF.md          the old general handoff. Its headline (+0.2826 sigma
                                gross edge) is CONTRADICTED -- see STATE.md section 2.
                                Its closed list, traps and cost constants all survive.
    BACKTEST_HANDOFF.md         backtest/live divergences. Section 3a (stop_monitor
                                never calls evaluate_exits) and 3b (validate_exit_
                                tolerance fails 13/14) are STILL OPEN -- STATE.md
                                section 8. The 2026-09-29 accuracy bugs are fixed.
    SCANNER_SESSION_HANDOFF.md  the scanner build spec. Its build list is built. Its
                                settled-config table is stale (stop 0.5 vs the live
                                1.0) and its "+0.806% per trade, 8.4% win rate" is a
                                different measurement basis from everything since.
                                Section 6c is still cited from portfolio.py and
                                signal_generator.py.
    HANDOFF.md                  the single-pair nautilus system, deleted 2026-09-12.
                                Already self-marked RETIRED. Kept because five live
                                modules cite its ledger-corruption incident, and
                                CLOUD_DEPLOY cites its MIN_BARS cold-start gap.
    kalman_changepoint_         a go/no-go spec for change-point detection and a
      experiment_spec.md        Kalman/state-space OU. Both are about tracking
                                theta and mu better. Theta is quantitatively broken
                                and direction is closed on seven lines, so the
                                premise is gone. Never built.

Two docs were NOT moved. `docs/VM_HANDOFF.md` and `docs/CLOUD_DEPLOY.md` carry
operational detail nothing else does — VM setup, deploy steps, retention caps, and
a dated incident history — and they stay live.

### `research/` — two modules

    backfill_equity.py      rebuilt the equity curve from ticks and the ledger for
                            time already elapsed. One-time job; its window closed
                            with RETAIN_TICK_DAYS. Method recorded in STATE.md
                            section 7.
    reversion_analysis.py   asked whether a model could beat the detector at picking
                            reverting spreads, and whether it fired earlier.
                            Superseded: direction is closed. The earliness question
                            and its 113,460 unused pre-detection rows are recorded
                            in STATE.md section 7.

### `modelling_scratch/` — the 2026-10-04 modelling phase

Fifty-seven files, each with its log where one exists. These are the one-off
analyses, not pipeline. The pipeline was promoted to
`research/dislocation_model/` and the datasets to `research/datasets/`.

They were rescued from a session-scoped temp directory that was about to be
garbage-collected, and they hardcode that dead path — **they will not run without
path edits.** Use `research/dislocation_model/harness.py` instead.

Four of them are the sources of the harness that is now one module:
`nonlinear.py`, `extscore.py`, `buckets.py`, `control.py`. They are kept as the
evidence for why it is one module: `nonlinear.py` carries the CI indexing bug, and
`nonlinear.log` next to `nonlinear2.log` is the before-and-after. See the
`harness.py` docstring.

`NUMBERS.md` was **not** left here. It is every number of the phase with M/A
provenance and a WITHDRAWN section, and it was promoted to
`research/dislocation_model/NUMBERS.md`.
