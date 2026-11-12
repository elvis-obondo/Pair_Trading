"""HL-VAULT1 2 h / 5 h isotonic follow-up receipt: the NUMBERS.md change vs git HEAD is additions only and the appended
text equals the section file byte for byte. Reads only; writes nothing."""
import hashlib, os, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
D = os.path.join(ROOT, "research", "dislocation_model")
head = subprocess.run(["git", "show", "HEAD:research/dislocation_model/NUMBERS.md"], cwd=ROOT, capture_output=True, check=True).stdout
now = open(os.path.join(D, "NUMBERS.md"), "rb").read()
sec = open(os.path.join(D, "logs", "s1_vault_iso_2h5h_section.md"), "rb").read()
sh = lambda b: hashlib.sha256(b).hexdigest()
print(f"HEAD NUMBERS.md {len(head):,} bytes sha {sh(head)}\nnow  NUMBERS.md {len(now):,} bytes sha {sh(now)}")
assert now.startswith(head), "HEAD text is not an exact prefix of the working copy"
tail = now[len(head):]
print(f"appended {len(tail):,} bytes sha {sh(tail)}; section file {len(sec):,} bytes sha {sh(sec)}")
assert tail == sec, "appended text != section file"
print("OK: additions only; appended text == s1_vault_iso_2h5h_section.md, byte for byte")
