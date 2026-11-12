# HL-PROFIT1-H: do the 2 h and 5 h predictions tell us which picks revert fast? (brief, 2026-11-11)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker. Runs on the laptop while HL-VAULT1 step 2
runs on AWS. **Test months only (folds 1-7); no vault row.** Descriptive only: no exit rule or filter is chosen here;
anything it suggests is a lead for later, tested on fresh data.

## Data (all held)
- Picks: Rule A on raw p_10h, q = 1%, 0.5%, 0.1%, folds 1-7 (assert n vs s1g_report.json as before).
- p_2h, p_5h, p_10h per pick, and their isotonic-corrected versions (S1-H's method and look-ahead guard).
- v1 labels: reach_2h/5h/10h, minutes_to_mu.
- Net return per trade (net / notional) from the base HL-PROFIT1 trade logs, stop = none, both fees (only picks
  that were traded).

## Questions
1. **Ranking per horizon.** For each horizon h, quintiles of corrected p_h among the picks: n, actual reach_h,
   mean corrected p_h. Does each horizon rank its own outcome?
2. **Speed, for p_2h AND p_5h (both, same tables).** Quintiles of corrected p_2h, and separately of corrected
   p_5h: median and mean minutes_to_mu (among those that reach), share reaching within 2 h / 5 h / 10 h, mean
   holding minutes and mean net/notional of the traded ones.
3. **Extra information beyond p_10h, for p_2h AND p_5h.** Within each p_10h quintile, split by p_2h above/below
   its median, and separately by p_5h above/below its median: reach_10h, minutes_to_mu, net/notional. Does either
   add anything once p_10h is known?
4. **What an earlier exit would have meant (descriptive):** for traded picks, the share still open at 2 h and 5 h,
   and their eventual outcome, split by corrected p_2h / p_5h quintile. No rule chosen.

## Process
One script, every number printed by it, a tagged NUMBERS.md section ("## [HL-PROFIT1 horizons]"). Checker review
before it runs and of the log and section after. Must not use the laptop's cleaned-price files in a way that
conflicts with the vault backtest later (read-only). Report to the planner.
