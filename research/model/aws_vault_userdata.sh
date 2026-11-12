#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/vault-refit.log > /dev/console) 2>&1

# HL-VAULT1 step 2b ONLY (docs/prompts/HL_VAULT1_RUN.md): ONE machine, ONE script
# (research/model/s1_vault_prevault_refit.py) -- the pre-vault refit. Round 3 ran the former 2a (fold 0
# reproduction check); the user's 2026-11-11 decision accepted it as solver-level agreement, so 2a is
# no longer in the script.
#
# Same S3-log-sync/IMDSv2/venv pattern as the proven S1 run (aws_s1_run_userdata_A.sh/_B.sh), reduced to
# one machine, one script, no FOLDS/MACHINE_ROLE split (there is nothing to balance across machines here).
#
# PAYLOAD_SHA256 must be filled in at packaging time (tar the repo, sha256sum it, upload to
# s3://pair-trading-hl-289869684922/s1_vault/<sha>.tar.gz) -- same discipline as the S1 run's own
# EXPECTED_SHA. Left as a placeholder here deliberately: packaging happens right before launch, not at
# script-review time, so this sha is never stale between review and use.
PAYLOAD_SHA256="a82e2d901189dec5654cff56371f07efc5d34275690434f56634f9058aee0660"

# Checker's fix (2026-11-10), round 2: the first launch used an Amazon Linux AMI against a script written
# for Ubuntu (apt-get), and died in the first second with "apt-get: command not found" -- finalize() ran,
# but AWS_BIN was still "" so sync_logs() skipped, and NOTHING reached S3; only aws ec2 get-console-output
# (fetched after termination) had the real error. OS guard, first thing, before anything else can fail:
if ! grep -qi ubuntu /etc/os-release 2>/dev/null; then
  echo "[VAULT-AWS] OS GUARD: /etc/os-release is not Ubuntu -- $(cat /etc/os-release 2>/dev/null | head -3) -- aborting before apt-get"
  exit 1
fi

TOKEN=$(curl -sf --max-time 3 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null) || TOKEN=""
if [ -n "$TOKEN" ]; then
  INSTANCE_ID=$(curl -sf --max-time 3 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null) || INSTANCE_ID=""
else
  INSTANCE_ID=""
fi
[ -n "$INSTANCE_ID" ] || INSTANCE_ID="$(hostname)-$(date +%s)"
echo "[VAULT-AWS] instance id: $INSTANCE_ID"
LOG_PREFIX="s3://pair-trading-hl-289869684922/s1_vault/logs/"
AWS_BIN=""

sync_logs() {
  local bin="$AWS_BIN"
  if [ -z "$bin" ] || [ ! -x "$bin" ]; then
    # checker's fix: fall back to any `aws` already on PATH (the base Ubuntu AMI may have one; if not,
    # this still reports clearly instead of silently skipping every cycle until AWS_BIN is set later).
    bin="$(command -v aws || true)"
  fi
  if [ -z "$bin" ]; then
    echo "[VAULT-AWS] sync_logs: no aws binary available yet (neither AWS_BIN nor PATH) -- skipping this "
    echo "[VAULT-AWS] sync_logs: cycle; if the run never gets further, 'aws ec2 get-console-output' is the only record"
    return 0
  fi
  if ! "$bin" s3 cp /var/log/vault-refit.log "${LOG_PREFIX}vault-refit_${INSTANCE_ID}.log" --region ap-northeast-1 >/dev/null 2>&1; then
    echo "[VAULT-AWS] sync_logs: vault-refit.log upload FAILED"
  fi
  if [ -f /tmp/build_cache.log ]; then
    if ! "$bin" s3 cp /tmp/build_cache.log "${LOG_PREFIX}build_cache_${INSTANCE_ID}.log" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[VAULT-AWS] sync_logs: build_cache.log upload FAILED"
    fi
  fi
  if [ -d /root/Pair_Trading/research/model/logs/s1 ]; then
    if ! "$bin" s3 sync --quiet /root/Pair_Trading/research/model/logs/s1/ "${LOG_PREFIX}outputs/" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[VAULT-AWS] sync_logs: outputs/ sync FAILED"
    fi
  fi
}

finalize() {
  local exit_code=$?
  echo "[VAULT-AWS] finalize: exit_code=$exit_code $(date -u)"
  sync_logs
  sleep 120
  sync_logs
  shutdown -h now
}
trap finalize EXIT

# Outer hard safety net: 12h (720 min). Sized generously above the estimate of ~7.4h (2b only, scaled from
# fold 7's measured timing; 2a is dropped) on an
# r7i.16xlarge-class machine (scaled from fold 7's own measured timing and
# row count), leaving ~2.7h of margin for a slower-than-expected run before the net fires. This only protects against a run that is
# legitimately still going but far slower than planned.
shutdown -h +720 &

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y python3-venv python3-pip curl

python3 -m venv /opt/v
/opt/v/bin/pip install -q numpy scipy pandas pyarrow threadpoolctl awscli
AWS_BIN=/opt/v/bin/aws
PY=/opt/v/bin/python
echo "[VAULT-AWS] python: $($PY --version) numpy: $($PY -c 'import numpy; print(numpy.__version__)')"

( trap - EXIT; while true; do sleep 60; sync_logs; done ) &

mkdir -p /root/Pair_Trading
cd /root/Pair_Trading

$AWS_BIN s3 cp "s3://pair-trading-hl-289869684922/s1_vault/${PAYLOAD_SHA256}.tar.gz" /tmp/payload.tar.gz
ACTUAL_SHA=$(sha256sum /tmp/payload.tar.gz | awk '{print $1}')
echo "[VAULT-AWS] payload sha256: $ACTUAL_SHA (expected $PAYLOAD_SHA256)"
if [ "$ACTUAL_SHA" != "$PAYLOAD_SHA256" ]; then
  echo "[VAULT-AWS] PAYLOAD SHA MISMATCH -- aborting, not extracting"
  exit 1
fi
tar xzf /tmp/payload.tar.gz -C /root/Pair_Trading/
echo "[VAULT-AWS] payload extracted: $(date -u)"

for f in research/model/harness.py research/model/inputs_v1_pair.csv research/model/hazard_logistic.py \
         research/model/s1_preprocess.py research/model/s1_model.py research/model/s1_newton.py \
         research/model/s1_run.py research/model/s1_vault_prevault_refit.py research/model/build_cache_v1_pair.py \
         research/model/b5_profile.py research/dataset/master_manifest.py research/dislocation_model/paths.py \
         research/hyperliquid/coins.csv research/model/diagnostics/vault_2a_maxdiff.json; do
  echo "[VAULT-AWS] sha256 $f: $(sha256sum $f | awk '{print $1}')"
done

mkdir -p research/datasets/master/work/pair research/datasets/master/versions/v1
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/MANIFEST.json research/datasets/master/versions/v1/MANIFEST.json
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/CHANGELOG.md research/datasets/master/versions/v1/CHANGELOG.md
$AWS_BIN s3 sync --quiet s3://pair-trading-hl-289869684922/master/versions/v1/pair/ research/datasets/master/work/pair/
echo "[VAULT-AWS] v1 data pulled (GET/sync only, read-only against master data -- step 2 never reads a vault row, only search-period data through t0 < VAULT_START - EMBARGO): $(date -u)"
du -sh research/datasets/master/work/pair/

if ! PATH=/opt/v/bin:$PATH $PY -u research/model/build_cache_v1_pair.py > /tmp/build_cache.log 2>&1; then
  BUILD_EXIT=1
else
  BUILD_EXIT=0
fi
tail -n 30 /tmp/build_cache.log
echo "[VAULT-AWS] cache build exit=$BUILD_EXIT: $(date -u)"
if [ $BUILD_EXIT -ne 0 ]; then
  echo "[VAULT-AWS] CACHE BUILD FAILED -- stopping, nothing further to run"
  exit 1
fi

# ONE parallel layer baseline (same established principle as the S1 run): BLAS pinned to 1 thread
# everywhere except inside s1_newton.build_hessian_blocks' own threadpoolctl scope around the Gram
# build (GRAM_BLAS_THREADS=64, tuned for r7i.16xlarge -- unchanged here).
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

# We also need fold7_done.json (the SELECTED settings this script reads; 2a was dropped, so no fold 0
# files) already present under research/model/logs/s1/ -- it is small (under 1 KB) and already available
# locally, so it is included in the payload tarball at packaging time, not pulled from S3 here.
if [ ! -f research/model/logs/s1/fold7_done.json ]; then
  echo "[VAULT-AWS] MISSING fold7_done.json in the payload -- aborting"
  exit 1
fi

PATH=/opt/v/bin:$PATH $PY -u research/model/s1_vault_prevault_refit.py
echo "[VAULT-AWS] ALL DONE: $(date -u)"
