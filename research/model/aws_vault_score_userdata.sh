#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/vault-score.log > /dev/console) 2>&1

# HL-VAULT1 step 3 (docs/prompts/HL_VAULT1_RUN.md): ONE machine, ONE scoring script
# (research/model/s1_vault_score.py): builds the feature cache (same as step 2b), then scores the vault with
# the saved pre-vault model. Features only; no label/outcome column is read. Same pattern as the step-2b
# userdata (aws_vault_userdata.sh).
# PAYLOAD_SHA256 must be filled in at packaging time (tar the repo, sha256sum it, upload to
# s3://pair-trading-hl-289869684922/s1_vault/<sha>.tar.gz) -- same discipline as the S1 run's own
# EXPECTED_SHA. Left as a placeholder here deliberately: packaging happens right before launch, not at
# script-review time, so this sha is never stale between review and use.
PAYLOAD_SHA256="8f5da6354fc486cb8ceaa253b077033246e18ed80d023143fbcaac5c64cf69a0"

# Checker's fix (2026-11-10), round 2: the first launch used an Amazon Linux AMI against a script written
# for Ubuntu (apt-get), and died in the first second with "apt-get: command not found" -- finalize() ran,
# but AWS_BIN was still "" so sync_logs() skipped, and NOTHING reached S3; only aws ec2 get-console-output
# (fetched after termination) had the real error. OS guard, first thing, before anything else can fail:
if ! grep -qi ubuntu /etc/os-release 2>/dev/null; then
  echo "[VAULTSCORE-AWS] OS GUARD: /etc/os-release is not Ubuntu -- $(cat /etc/os-release 2>/dev/null | head -3) -- aborting before apt-get"
  exit 1
fi

TOKEN=$(curl -sf --max-time 3 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null) || TOKEN=""
if [ -n "$TOKEN" ]; then
  INSTANCE_ID=$(curl -sf --max-time 3 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null) || INSTANCE_ID=""
else
  INSTANCE_ID=""
fi
[ -n "$INSTANCE_ID" ] || INSTANCE_ID="$(hostname)-$(date +%s)"
echo "[VAULTSCORE-AWS] instance id: $INSTANCE_ID"
LOG_PREFIX="s3://pair-trading-hl-289869684922/s1_vault/score_logs/"
AWS_BIN=""

sync_logs() {
  local bin="$AWS_BIN"
  if [ -z "$bin" ] || [ ! -x "$bin" ]; then
    # checker's fix: fall back to any `aws` already on PATH (the base Ubuntu AMI may have one; if not,
    # this still reports clearly instead of silently skipping every cycle until AWS_BIN is set later).
    bin="$(command -v aws || true)"
  fi
  if [ -z "$bin" ]; then
    echo "[VAULTSCORE-AWS] sync_logs: no aws binary available yet (neither AWS_BIN nor PATH) -- skipping this "
    echo "[VAULTSCORE-AWS] sync_logs: cycle; if the run never gets further, 'aws ec2 get-console-output' is the only record"
    return 0
  fi
  if ! "$bin" s3 cp /var/log/vault-score.log "${LOG_PREFIX}vault-score_${INSTANCE_ID}.log" --region ap-northeast-1 >/dev/null 2>&1; then
    echo "[VAULTSCORE-AWS] sync_logs: vault-score.log upload FAILED"
  fi
  if [ -f /tmp/build_cache.log ]; then
    if ! "$bin" s3 cp /tmp/build_cache.log "${LOG_PREFIX}score_build_cache_${INSTANCE_ID}.log" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[VAULTSCORE-AWS] sync_logs: build_cache.log upload FAILED"
    fi
  fi
  if [ -d /root/Pair_Trading/research/model/logs/s1 ]; then
    if ! "$bin" s3 sync --quiet /root/Pair_Trading/research/model/logs/s1/ "${LOG_PREFIX}outputs/" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[VAULTSCORE-AWS] sync_logs: outputs/ sync FAILED"
    fi
  fi
}

finalize() {
  local exit_code=$?
  echo "[VAULTSCORE-AWS] finalize: exit_code=$exit_code $(date -u)"
  sync_logs
  sleep 120
  sync_logs
  shutdown -h now
}
trap finalize EXIT

# Outer hard safety net: 3h (180 min). Step 2b took 2043 s end to end including the cache build; scoring
# 1.28M events adds minutes.
shutdown -h +180 &

export DEBIAN_FRONTEND=noninteractive
# Round 1 of step 3 died here: one mirror fetch failed ("Connection failed [IP: ...]", apt-get exit 100) and
# set -e ended the run (nothing else had started). Retry the whole apt step up to 5 times, with apt's own
# per-fetch retries, before giving up.
apt_ok=0
for attempt in 1 2 3 4 5; do
  if apt-get update -qq -o Acquire::Retries=5 && apt-get install -qq -y --fix-missing -o Acquire::Retries=5 python3-venv python3-pip curl; then
    apt_ok=1; break
  fi
  echo "[VAULTSCORE-AWS] apt attempt $attempt failed -- retrying in 20s"; sleep 20
done
[ "$apt_ok" = 1 ] || { echo "[VAULTSCORE-AWS] apt failed 5 times -- aborting"; exit 1; }

python3 -m venv /opt/v
pip_ok=0
for attempt in 1 2 3 4 5; do
  if /opt/v/bin/pip install -q --retries 5 numpy scipy pandas pyarrow threadpoolctl awscli; then pip_ok=1; break; fi
  echo "[VAULTSCORE-AWS] pip attempt $attempt failed -- retrying in 20s"; sleep 20
done
[ "$pip_ok" = 1 ] || { echo "[VAULTSCORE-AWS] pip failed 5 times -- aborting"; exit 1; }
AWS_BIN=/opt/v/bin/aws
PY=/opt/v/bin/python
echo "[VAULTSCORE-AWS] python: $($PY --version) numpy: $($PY -c 'import numpy; print(numpy.__version__)')"

( trap - EXIT; while true; do sleep 60; sync_logs; done ) &

mkdir -p /root/Pair_Trading
cd /root/Pair_Trading

$AWS_BIN s3 cp "s3://pair-trading-hl-289869684922/s1_vault/score_payload_${PAYLOAD_SHA256}.tar.gz" /tmp/payload.tar.gz
ACTUAL_SHA=$(sha256sum /tmp/payload.tar.gz | awk '{print $1}')
echo "[VAULTSCORE-AWS] payload sha256: $ACTUAL_SHA (expected $PAYLOAD_SHA256)"
if [ "$ACTUAL_SHA" != "$PAYLOAD_SHA256" ]; then
  echo "[VAULTSCORE-AWS] PAYLOAD SHA MISMATCH -- aborting, not extracting"
  exit 1
fi
tar xzf /tmp/payload.tar.gz -C /root/Pair_Trading/
echo "[VAULTSCORE-AWS] payload extracted: $(date -u)"

for f in research/model/harness.py research/model/inputs_v1_pair.csv research/model/hazard_logistic.py \
         research/model/s1_preprocess.py research/model/s1_model.py research/model/s1_newton.py \
         research/model/s1_run.py research/model/vault_loader.py research/model/s1_vault_score.py research/model/build_cache_v1_pair.py \
         research/model/b5_profile.py research/dataset/master_manifest.py research/dislocation_model/paths.py \
         research/hyperliquid/coins.csv research/model/logs/s1/s1_prevault_model.json research/model/logs/s1/s1_prevault_model_w.npy research/model/logs/s1/s1_vault_coverage_check.log; do
  echo "[VAULTSCORE-AWS] sha256 $f: $(sha256sum $f | awk '{print $1}')"
done

mkdir -p research/datasets/master/work/pair research/datasets/master/versions/v1
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/MANIFEST.json research/datasets/master/versions/v1/MANIFEST.json
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/CHANGELOG.md research/datasets/master/versions/v1/CHANGELOG.md
$AWS_BIN s3 sync --quiet s3://pair-trading-hl-289869684922/master/versions/v1/pair/ research/datasets/master/work/pair/
echo "[VAULTSCORE-AWS] v1 data pulled (GET/sync only, read-only against master data; the scoring script reads vault FEATURES only): $(date -u)"
du -sh research/datasets/master/work/pair/

if ! PATH=/opt/v/bin:$PATH $PY -u research/model/build_cache_v1_pair.py > /tmp/build_cache.log 2>&1; then
  BUILD_EXIT=1
else
  BUILD_EXIT=0
fi
tail -n 30 /tmp/build_cache.log
echo "[VAULTSCORE-AWS] cache build exit=$BUILD_EXIT: $(date -u)"
if [ $BUILD_EXIT -ne 0 ]; then
  echo "[VAULTSCORE-AWS] CACHE BUILD FAILED -- stopping, nothing further to run"
  exit 1
fi

# ONE parallel layer baseline (same established principle as the S1 run): BLAS pinned to 1 thread
# everywhere except inside s1_newton.build_hessian_blocks' own threadpoolctl scope around the Gram
# build (GRAM_BLAS_THREADS=64, tuned for r7i.16xlarge -- unchanged here).
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

# The saved model and the coverage-check log come in the payload tarball (checked by sha in the loop above);
# s1_vault_score.py itself checks the model files against the reviewed shas.
PATH=/opt/v/bin:$PATH $PY -u research/model/s1_vault_score.py
echo "[VAULTSCORE-AWS] ALL DONE: $(date -u)"
