# COSTS1 entry delay: engine change write-up (text only, nothing run, no code changed)

## What the delay means
The pick is made at wall-clock minute t0, as today. The order fills d minutes later (d = 1, 5, 15). Signals and picks stay exactly as saved, so there is no look-ahead.

## Exact engine changes (s1_profit1.py)
- compute_move_paths: start the 601-minute window at label t0-1+d. The entry spread becomes P[d] (the spread at the delayed fill). The move is measured from P[d]: move = -(P - P[d]) x s, so the target distance (z_abs in run_one) becomes |P[d]| and stops are measured from P[d]. The assert max |move[0]| < 1e-6 is re-pointed at the new entry.
- Gap and no-data status is evaluated on the shifted 601-minute window. Events near the end of a data period, or with a gap in the new window, drop out. They are counted as a new status.
- Skip rule at the delayed fill (PROPOSED; the planner and the user decide the rule): skip the pick if the spread has already crossed mu or its sign has flipped. The alternative is to enter anyway and measure. If skipping is chosen, a new counter is added to the skip table next to the engine's current reasons (book_full, margin, min_order, below_floor, liquidated_minute).
- run_one: the pick is admitted at cur_minute = t0+d. Sizing uses the account value at t0+d, not t0. Book occupancy and margin change. This is a real engine change, not a relabel.
- Because the book is almost always full, moving each admission by d minutes changes which picks get a free slot. Saved d = 0 skips for q 1% / no stop / taker: test open10 27,488 of 35,629 picks (admitted 8,078, book_full 27,488, min_order 63); vault open10 10,010 book_full (admitted 3,789, min_order 148). So some delayed trades are not in the saved trade set at all.
- Position fields: start_label, last_funding_h and the slippage lookup (label0) move to the fill minute t0+d. The 600-minute timeout runs from the delayed fill.
- dir_a, dir_b, la, lb: unchanged in form, but computed from the sign of the spread at the delayed fill.
- Trade log: keep the pick time t0 and add the fill time as its own column. costs_analysis, the G8 targets and every COSTS1 join today use t0 as both the pick time and the entry minute. They would need the fill time for entries (reference price = close of the label before the fill; the maker window starts at the fill).
- Cross-check: the v1 label check does not apply for d > 0. Replace it with a d = 0 regression: the new code at d = 0 must reproduce the saved trades exactly (same trade count, same net to the cent).
- Output tags carry a _delay{d} suffix so saved d = 0 files are never overwritten.
- COSTS1 re-run needs a new G8 extraction of BOTH entry and exit windows, scoped to the delayed run's trades. The existing extract covers [t0-1, t0+15] per saved pick. A fill at t0+d needs [t0+d-1, t0+d+W]: the maker windows (W = 5 and 15) fall outside for any d > 0, the plus-one-minute neighbour falls outside at d = 15, and only the taker own-minute entry is covered, and only for d <= 14 and only for trades that are also in the saved set. Exit windows move with the fill. That is a Tokyo pull: it needs spend and the user's own yes.

## Time (measured: the four saved 24-tag engine runs)

| Run | tags in log | engine log time (s) |
|---|---:|---:|
| vault open10 | 24 | 498 |
| vault open20 | 24 | 630 |
| test open10 | 24 | 1011 |
| test open20 | 24 | 1339 |

Sum of the four saved 24-tag runs: 3478 s (58.0 min). This is the only measured number. The logs hold one total per 24-tag run and no per-tag time. Total divided by 24 would be an average that includes loading, and q 1% is the heaviest tag, so a per-tag figure cannot be bounded from the logs.

**Not estimated:** the engine time for a delayed COSTS1 re-run. The d = 0 regression (needed anyway) will measure it. **Builder guess, not measured:** about half a day of code, plus one checker round, plus the new G8 extraction and the COSTS1 re-run and re-report (cost not estimated).
