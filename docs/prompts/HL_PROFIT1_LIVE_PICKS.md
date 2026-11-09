# HL-PROFIT1: do the logistic model's live picks make money? (brief, 2026-11-08)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Results to NUMBERS.md `[HL-PROFIT1]`. Written for NEW sessions: read CLAUDE.md, docs/PLANNER_HANDOFF.md section 3
and this brief first.

**Decided by the user 2026-11-07:** profit work starts on the logistic model's live picks, which lifts the
"profit waits for a pass" rule for this scope only. The S1 gate stays FAIL, and the vault stays locked.

## Background, in one paragraph
S1 (penalised logistic, hazard framing) ranks pair dislocations by the chance of reaching mu within 10 h. A live
cut-off (S1-F Rule A: an event is a pick if p_10h >= the top-q% quantile of the previous test block's p_10h)
keeps the edge. At q = 1% / 0.5% / 0.1%: lift 0.078 / 0.090 / 0.109, with median 110 / 50 / 8 picks a day (S1-G).
The raw probabilities are too high at the top. Isotonic recalibration fitted on earlier test months fixes them
(top 1% at 10 h: 67.9% corrected against 67.7% actual; S1-H). Reaching mu is not profit; this brief measures the money.

## Data (all already in v1; no new data)
- Picks: Rule A at q = 1%, 0.5% and 0.1%, test folds 1-7, rebuilt from
  `research/model/logs/s1/fold*_test_predictions.csv`. Assert the per-fold n against
  `s1g_report.json` (g7 cutoff_table).
- Payoff columns, defined in `research/dataset/master_labels.py` lines 21-28 and `docs/DATASET_DICTIONARY.md` line 31.
  For a stop s in {0p5, 1p0, 2p0, none} sigma beyond entry: outcome_s (+1 mu first, -1 stopped first, 0 neither
  within 10 h), gross_s (the move at the exit minute, in sigma, overshoot included; mark-to-market at 600 min if
  neither), net_s_taker = gross_s - fee_sigma_taker, and net_s_maker likewise. Fees: 0.099% (taker) or 0.0495%
  (maker) of the position per round trip, legs sized 1 : |beta|.
- Also needed: sigma, beta, t0, ticker_a and ticker_b, and the isotonic-corrected p_10h. Rebuild it with S1-H's
  method or read it from S1-H's outputs, whichever the S1-H code saved.
- The GCP VM is stopped. Read only the needed columns from S3, read-only.

## P1. Per-trade economics (descriptive; nothing chosen on these numbers)
For each q, and for each stop s (0.5, 1, 2, none) x fee (taker, maker):
- n; the share ending at mu, at the stop and at the time-out; the mean, median and quartiles of net in sigma;
  the mean win and the mean loss; the profit factor (sum of wins / |sum of losses|).
- **Return on capital:** net x sigma / (1 + |beta|), the log return per unit of TOTAL notional (both legs).
  Give its mean and median, and its sum per UTC day (median and mean over days, zero-pick days counted).
- **Interval:** the mean net per trade with a 98.75% day-block bootstrap (2,000 resamples, whole UTC days, the
  harness method).
- By month (folds 1-7): n, mean net, and the share of months with mean net > 0.
- The same table for ALL usable events of folds 1-7, as the no-model baseline.
- All of this is reported, not chosen. The stop, fee level or q that looks best is a lead for P2, not a decision.

## P2. Expected value from the corrected probability (descriptive)
- For each pick: EV = p_cal x (the mean win at that stop) - (1 - p_cal) x (the mean loss), with the mean win and
  mean loss fitted on EARLIER test months only (expanding, with the t0 + 10 h look-ahead guard of S1-H).
- Picks in 5 groups of EV (quintiles over the picks): mean EV against the actual mean net, per stop and fee.
  Does the EV ranking line up with what was realised?

## Known gaps (state them in the report; do not model them in P1-P2)
- **Funding** over the hold (up to 10 h) is not in net_*. Funding values are in the inputs; flag its likely size.
- **Slippage and fills:** net_* assumes fills at the 1-minute close. Maker fills are not guaranteed.
- **Overlap and capital:** picks overlap (the top 1% has up to 346 open at once, and one coin up to 129). P1 is
  per-trade. A portfolio rule (caps per coin and in total) is a later step.
- **Liquidation and leverage** are not modelled (see memory okx-era-lessons).

## Process
Every number is printed by a script, and the NUMBERS section is written by a generator script (CLAUDE.md).
Checker review of the script before it runs, then of the log, the NUMBERS section and the diff. One script for
P1 and P2. Then STOP and report to the planner with the checker's verdict. No vault. No refit of S1.
