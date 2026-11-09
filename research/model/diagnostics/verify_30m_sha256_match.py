import os, hashlib

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

D3DIR = "/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/5ff3441a-0d64-466c-982e-cf713e87dda7/scratchpad/d3_30m"
LOCALDIR = "user_data/data/hyperliquid/futures"

match = mismatch = missing = 0
mismatches = []
for f in sorted(os.listdir(LOCALDIR)):
    if not f.endswith("-30m.feather"):
        continue
    lp, dp = os.path.join(LOCALDIR, f), os.path.join(D3DIR, f)
    if not os.path.exists(dp):
        missing += 1
        continue
    if sha(lp) == sha(dp):
        match += 1
    else:
        mismatch += 1
        mismatches.append(f)

print("match", match, "mismatch", mismatch, "missing", missing)
print("mismatches (first 20):", mismatches[:20])
