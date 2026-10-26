> **CANCELLED/PARKED (user, 2026-10-24): only the master dataset (build 7) proceeds. Kept for its design, which later model work reuses.**

# Builder prompt: build 4b — rolling rerun of build 4's coin-level tests

**QUEUED (user, 2026-10-15). Start only after build 6 has passed Code Checker.** Builds on
`[HL-EVENT1]` (build 4; scripts `hl4_tests.py`, `hl4_after.py`, `hl4_impact.py`, `eventstudy.py`)
and the "Rolling (walk-forward) test" section of `docs/prompts/HL_BUILD6_FULL_POPULATION.md`. Do
exactly this; nothing else. Be frugal with messages.

## Why
Build 4 scored its coin-level tests (74,607 events) on one cut (2026-05-25; HO1/HO2). Its main
result: ALL feature groups help rank reverters (about 2 points fewer flags to catch 80%), the
beyond-chance gap improves +0.007 to +0.012 and stays negative. User rule (2026-10-15): anything that
fits a model is scored by the rolling walk-forward. This checks whether that small gain holds across
periods, not only in one 5-month window.

## What to run (design unchanged, scoring changed)
- **Part B tests** exactly as build 4 (same events, controls not needed, same features and groups,
  same 270-cell design counted per the pooled measures, same models and leaf grid as build 4, same
  reference): scored by the rolling design from build 6 — expanding window, first test block ~180
  days after the first event, 30-day blocks, 1-day embargo before each test and validation block,
  settings chosen per fold on that fold's validation, pooled and per-fold scoring, pooled
  permutation null (20 seeds, whole-day shuffle), finding = pooled interval excludes zero in the good
  direction AND same sign in >= 2/3 of folds.
- **Impact model refit per fold** on that fold's fit period (build 4's frozen version leaked into
  earlier folds). Report the frozen version beside it.
- **Part C2 (delayed decision at +60 min)** under the same rolling design.
- **B4 strong-event cut** repeated per fold-pooled.
- **Q1 stability, descriptive:** month-by-month series of the events-minus-controls difference for
  imbalance, opening push, forced share and volume at P1 and C6 (set 1), with day-clustered bands.
  No split needed (nothing is fitted).
- Report the single-cut result for ALL and KEPT next to the rolling one in one line, and the per-fold
  series of the reference gap and ALL's gain.

## Review and receipts
Code Checker ("Code Checker 2"; check `ListAgents`) reviews the per-fold refit code and the
embargo before the run, and log + NUMBERS.md + diff before reporting. Logs `hl4b_*.log`;
NUMBERS.md section `[HL-EVENT2]`. Cloud only (bigger machine allowed, auto-terminate with a hard
timer, cost no object). Final report plain and short: rolling vs single-cut for ALL, KEPT and each
group; whether the ranking gain holds in >= 2/3 of folds; the checker's verdict; files changed.
