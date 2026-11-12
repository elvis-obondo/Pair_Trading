"""HL-VAULT1 step 6 receipt: the NUMBERS.md change is additions only, and the appended text is the three section
files byte for byte, in order. Reads git HEAD's NUMBERS.md and the working copy; writes nothing."""
import hashlib, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
D = os.path.join(ROOT, "research", "dislocation_model")
head = subprocess.run(["git", "show", "HEAD:research/dislocation_model/NUMBERS.md"], cwd=ROOT, capture_output=True, check=True).stdout
now = open(os.path.join(D, "NUMBERS.md"), "rb").read()
parts = [os.path.join(D, "logs", f) for f in ("s1_profit1_numbers_excerpt_vault_open10.md",
         "s1_profit1_numbers_excerpt_vault_open20.md", "s1_vault_report_section.md")]
blocks = [open(p, "rb").read() for p in parts]
sh = lambda b: hashlib.sha256(b).hexdigest()
print(f"HEAD NUMBERS.md {len(head):,} bytes sha {sh(head)}")
print(f"now  NUMBERS.md {len(now):,} bytes sha {sh(now)}")
assert now.startswith(head), "HEAD text is not an exact prefix of the working copy: something was changed or removed"
tail = now[len(head):]
print(f"appended {len(tail):,} bytes, sha {sh(tail)}")
for p, b in zip(parts, blocks):
    print(f"  {os.path.relpath(p, ROOT)}: {len(b):,} bytes sha {sh(b)}")
assert tail == b"".join(blocks), "appended text != the three section files concatenated"
print("OK: additions only; appended text == excerpt_vault_open10 + excerpt_vault_open20 + s1_vault_report_section, byte for byte")
