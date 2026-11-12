"""HL-VAULT1 step 2 receipt: S3 copies of the vault picks/predictions vs the local files, sha256 of the bytes.
Read-only on S3 (downloads to a scratch dir, nothing written to S3, nothing deleted)."""
import hashlib, os, subprocess, sys, tempfile
B = "s3://pair-trading-hl-289869684922/s1_vault"
HERE = os.path.dirname(os.path.abspath(__file__))
S1 = os.path.join(os.path.dirname(HERE), "logs", "s1")
PAIRS = [("outputs/s1_vault_picks.parquet", os.path.join(S1, "s1_vault_picks.parquet")),
         ("outputs/s1_vault_picks_all.parquet", os.path.join(S1, "s1_vault_picks_all.parquet")),
         ("score_logs/outputs/s1_vault_predictions.parquet", os.path.join(S1, "vault_pull3", "s1_vault_predictions.parquet"))]
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
ok = True
with tempfile.TemporaryDirectory(dir=sys.argv[1] if len(sys.argv) > 1 else None) as d:
    for key, local in PAIRS:
        dst = os.path.join(d, os.path.basename(key))
        subprocess.run(["aws", "s3", "cp", f"{B}/{key}", dst, "--only-show-errors"], check=True)
        a, b = sha(local), sha(dst)
        print(f"{key}\n  local {a}\n  s3    {b}\n  {'MATCH' if a == b else 'MISMATCH'}  bytes local {os.path.getsize(local):,} s3 {os.path.getsize(dst):,}")
        ok &= a == b
print("ALL MATCH" if ok else "MISMATCH FOUND")
sys.exit(0 if ok else 1)
