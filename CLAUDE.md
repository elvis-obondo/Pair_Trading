# Working rules for this project

## Stay on the plan

When a plan exists — the roadmap doc, a session brief, a decided order of items
— **the next action is the next item on that plan.** Not the most interesting
thing the last result suggested.

- A finding that points elsewhere is a **report, not a redirect.** State it in a
  line or two, say what it would imply, then carry on with the plan item.
  Changing the plan is the user's call and requires asking first.
- **Never chain experiments.** One result does not authorise the next script. If
  a second run is needed to interpret the first, that is a question to put to
  the user, not a thing to go and do.
- "Can we test X" means analyse existing data, not write a patch.
- Do not announce a conclusion that the plan's own next item would settle. Run
  the plan item first.

This rule exists because of a real session: a decided plan was followed for one
item, then abandoned for five unrequested analyses in a row, each justified by
the last. It produced a reported result built on a bug and a stated conclusion
that the next on-plan experiment contradicted.

## Every task goes through Code Checker

A separate Claude session reviews the building session's work. Session names
change often, so find the checker, builder and planner with `ListAgents`. The review loop runs between the two sessions without the
user.

- **Before running anything that takes more than a few minutes**, send the code
  and the docstring's decision rules for review. Before reporting a finished
  task, send the log, the NUMBERS.md section, and the diff for review.
- Send the text itself (the receiver can't open `@` paths): file paths, line
  ranges, the claims and the numbers they rest on.
- **The checker's findings are fixed without asking the user** when they are
  bugs, look-ahead, a number that doesn't match its log, a rule not applied as
  written, a missing receipt, or a wrong comparison baseline. Re-send until it
  passes, then report to the user with the checker's verdict included.
- **The loop does not widen the plan.** A fix that changes a decision rule,
  adds a run the brief didn't ask for, or would change a gate's verdict goes to
  the user. Disagreements the two sessions can't settle go to the user.
- The checker reviews; it does not assign work. Its suggestions for new
  analyses are reported to the user, not acted on.

## Every number comes from a script

Every figure in NUMBERS.md, a report or a write-up is printed by a script that reads a log or a saved
output file. Nothing is typed by hand. Cite the script and the file. (User, 2026-11-07, after hand-typed
pick counts were caught in S1-G.)

## Only the planner writes project memory

The planner session is the single keeper of the project's shared record: the
memory folder (`~/.claude/projects/-Users-elvisobondo-Pair-Trading/memory/`),
the decisions log in `docs/HYPERLIQUID_HANDOFF.md`, and
`docs/PLANNER_HANDOFF.md`.

- Builder and checker sessions do **not** write to the memory folder. Send
  decisions, rulings and findings worth keeping to the planner via SendMessage;
  the planner records them.
- Each session may keep its own role handoff (for example
  `docs/prompts/BUILDER_HANDOFF.md`) and the receipts its task requires
  (NUMBERS.md sections, logs, the brief's own outputs).
