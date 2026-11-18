"""Process receipt for the no-bounce section: the order of three events in this builder session, read from the session transcript's own timestamps (UTC).
  1. the checker's message 'section 10 review (no code yet)' and the planner's message with the rulings on the G8 fallback, the gross-ratio bands and the 'close vs mid gap' label;
  2. the first smoke run (event-level statistics only; no trade table);
  3. the smoke run that first printed the vault trade table (it ran the rewritten reprice()).
Writes logs/costs1/process_times.json. Reads only the transcript file given as the first argument (default: this session's)."""
import json
import os
import sys

MODEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.claude/projects/-Users-elvisobondo-Pair-Trading/3db1dc3b-155f-4e2e-b272-f41423fe3a71.jsonl")
KEYS = {"checker_review_no_code": ("Checker: section 10 review (no code yet)", "attachment"), "planner_rulings": ("Planner rulings on the no-bounce rules", "attachment"),
        "first_smoke_event_level": ("smoke.py", "assistant"), "smoke_with_vault_trade_table": ("smoke2.py", "assistant")}
out = {}
for l in open(F):
    try:
        o = json.loads(l)
    except Exception:
        continue
    s = json.dumps(o)
    for k, (needle, typ) in KEYS.items():
        if k not in out and o.get("type") == typ and needle in s and o.get("timestamp"):
            out[k] = o["timestamp"]
assert set(out) == set(KEYS), out
json.dump(out, open(os.path.join(MODEL, "logs", "costs1", "process_times.json"), "w"), indent=1)
for k, v in out.items():
    print(f"[PROCESS] {k}: {v}")
