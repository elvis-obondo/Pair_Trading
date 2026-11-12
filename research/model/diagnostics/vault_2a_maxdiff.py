"""HL-VAULT1 step 2a record (round 3 log): parse the mismatch tables the failed 2a check printed and report
the max |new - old| per horizon, the tolerance it was checked against, and the counts -- all read from the
log, nothing typed. Output: research/model/diagnostics/vault_2a_maxdiff.json (+ the .log from stdout), which
s1_vault_prevault_refit.py reads into the model JSON's known_gaps at 2b time.

LIMIT: the log's tables are printed by pandas at 6 decimals, so each max is accurate to ~1e-6 (and the
tables list only events OUTSIDE the tolerance; events inside it differ by less than the tolerance, so the
true max over all 428,849 events is the max printed here whenever any event was outside, as here).

    python research/model/diagnostics/vault_2a_maxdiff.py > research/model/diagnostics/vault_2a_maxdiff.log
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "..", "logs", "s1", "vault_pull", "vault-refit_i-095394542d9f95783.log")
OUT = os.path.join(HERE, "vault_2a_maxdiff.json")

lines = open(LOG).read().splitlines()
tol = None
counts = {}
rows = {}
for l in lines:
    m = re.search(r"\(a\) (p_\d+h): (\d+) events compared, (\d+) outside abs tolerance ([0-9.e+-]+)", l)
    if m:
        counts[m.group(1)] = dict(compared=int(m.group(2)), outside=int(m.group(3)))
        tol = float(m.group(4))
    p = l.split()
    if len(p) == 9 and p[0].isdigit() and p[2] == "0":
        try:
            vals = [float(x) for x in p[3:]]
        except ValueError:
            continue
        rows[p[1]] = vals            # keyed by event_id: the three tables overlap
horizons = ("p_2h", "p_5h", "p_10h")
res = dict(log=os.path.relpath(LOG, os.path.join(HERE, "..", "..", "..")), pred_abs_tol=tol,
           distinct_events_listed=len(rows), counts=counts,
           max_abs_diff={h: max(abs(v[k] - v[k + 3]) for v in rows.values()) for k, h in enumerate(horizons)})
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))
