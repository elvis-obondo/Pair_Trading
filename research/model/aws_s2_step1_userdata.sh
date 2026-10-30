#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/s2-step1.log > /dev/console) 2>&1

# HL-MODEL1 S2 Step 1: boosted-tree sizing, one machine, one script (s2_tree_timing.py). Same proven
# S3-log-sync/IMDSv2/venv pattern as the S1 probe (aws_s1_probe_userdata.sh, attempt 3) and the S1 real
# run (aws_s1_run_userdata_template.sh) -- reused, not rebuilt. This is a timing/sizing run only: no
# per-fold output directory to sync back (s2_tree_timing.py's only output is its own stdout log), and no
# FOLDS/MACHINE_ROLE split since Step 1 runs on fold 7 alone, one machine.
TOKEN=$(curl -sf --max-time 3 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null) || TOKEN=""
if [ -n "$TOKEN" ]; then
  INSTANCE_ID=$(curl -sf --max-time 3 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null) || INSTANCE_ID=""
else
  INSTANCE_ID=""
fi
[ -n "$INSTANCE_ID" ] || INSTANCE_ID="$(hostname)-$(date +%s)"
echo "[S2-STEP1-AWS] instance id: $INSTANCE_ID"
LOG_PREFIX="s3://pair-trading-hl-289869684922/s2_step1/logs/${INSTANCE_ID}/"
AWS_BIN=""

sync_logs() {
  if [ -z "$AWS_BIN" ] || [ ! -x "$AWS_BIN" ]; then
    echo "[S2-STEP1-AWS] sync_logs: AWS_BIN not ready yet, skipping this cycle"
    return 0
  fi
  if ! "$AWS_BIN" s3 cp /var/log/s2-step1.log "${LOG_PREFIX}s2-step1.log" --region ap-northeast-1 >/dev/null 2>&1; then
    echo "[S2-STEP1-AWS] sync_logs: s2-step1.log upload FAILED"
  fi
  if [ -f /tmp/build_cache.log ]; then
    if ! "$AWS_BIN" s3 cp /tmp/build_cache.log "${LOG_PREFIX}build_cache.log" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[S2-STEP1-AWS] sync_logs: build_cache.log upload FAILED"
    fi
  fi
}

finalize() {
  local exit_code=$?
  echo "[S2-STEP1-AWS] finalize: exit_code=$exit_code $(date -u)"
  sync_logs
  sleep 120   # let the last S3 copy land before the instance disappears (S1 probe's ruling)
  sync_logs
  shutdown -h now
}
trap finalize EXIT

shutdown -h +240 &   # outer hard safety net (4h): a sizing run on one fold, not the 36h real S1/S2 run

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y python3-venv python3-pip curl libgomp1

python3 -m venv /opt/v
/opt/v/bin/pip install -q numpy scipy pandas pyarrow threadpoolctl awscli lightgbm==4.7.0
AWS_BIN=/opt/v/bin/aws
PY=/opt/v/bin/python
echo "[S2-STEP1-AWS] python: $($PY --version) numpy: $($PY -c 'import numpy; print(numpy.__version__)')"
# checker's fix round 1 (launch review): a failed import inside $(...) does not stop the script under
# set -e -- this runs on its own line so a broken lightgbm install fails loudly HERE, before the data
# pull and cache build, not partway through the real run.
$PY -c 'import lightgbm; print("[S2-STEP1-AWS] lightgbm:", lightgbm.__version__)'

( trap - EXIT; while true; do sleep 60; sync_logs; done ) &

mkdir -p /root/Pair_Trading
cd /root/Pair_Trading

EXPECTED_SHA="fdd2f50481a92539addb0cb9f32bcf916192a7d14c54143eab1774af020b35df"
$AWS_BIN s3 cp "s3://pair-trading-hl-289869684922/s2_step1/${EXPECTED_SHA}.tar.gz" /tmp/payload.tar.gz
ACTUAL_SHA=$(sha256sum /tmp/payload.tar.gz | awk '{print $1}')
echo "[S2-STEP1-AWS] payload sha256: $ACTUAL_SHA (expected $EXPECTED_SHA)"
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
  echo "[S2-STEP1-AWS] PAYLOAD SHA MISMATCH -- aborting, not extracting"
  exit 1
fi
tar xzf /tmp/payload.tar.gz -C /root/Pair_Trading/
echo "[S2-STEP1-AWS] payload extracted: $(date -u)"

for f in research/model/harness.py research/model/inputs_v1_pair.csv research/model/b5_profile.py \
         research/model/s2_tree_timing.py research/model/build_cache_v1_pair.py; do
  echo "[S2-STEP1-AWS] sha256 $f: $(sha256sum $f | awk '{print $1}')"
done

mkdir -p research/datasets/master/work/pair research/datasets/master/versions/v1
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/MANIFEST.json research/datasets/master/versions/v1/MANIFEST.json
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/CHANGELOG.md research/datasets/master/versions/v1/CHANGELOG.md
$AWS_BIN s3 sync --quiet s3://pair-trading-hl-289869684922/master/versions/v1/pair/ research/datasets/master/work/pair/
echo "[S2-STEP1-AWS] v1 data pulled (GET/sync only, read-only against master data; the only writes anywhere are the log copies to s2_step1/logs/${INSTANCE_ID}/, this run's own approved prefix): $(date -u)"
du -sh research/datasets/master/work/pair/

if ! PATH=/opt/v/bin:$PATH $PY -u research/model/build_cache_v1_pair.py > /tmp/build_cache.log 2>&1; then
  BUILD_EXIT=1
else
  BUILD_EXIT=0
fi
tail -n 30 /tmp/build_cache.log
echo "[S2-STEP1-AWS] cache build exit=$BUILD_EXIT: $(date -u)"
if [ $BUILD_EXIT -ne 0 ]; then
  echo "[S2-STEP1-AWS] CACHE BUILD FAILED -- stopping, nothing further to time"
  exit 1
fi

# s2_tree_timing.py sets its own LightGBM num_threads (physical-core assumption, logged by the script
# itself); no BLAS/OMP pinning needed here -- LightGBM is the only parallel layer this run touches.
PATH=/opt/v/bin:$PATH $PY -u research/model/s2_tree_timing.py
echo "[S2-STEP1-AWS] ALL DONE: $(date -u)"
