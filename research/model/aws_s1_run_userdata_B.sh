#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/s1-run.log > /dev/console) 2>&1

# HL-MODEL1 S1 Step 2, real 2-machine run. Same S3-log-sync/IMDSv2/venv pattern as the proven AWS probe
# (aws_s1_probe_userdata.sh, attempt 3), with these changes for the real run:
#   1. Syncs the whole output directory (research/model/logs/s1/), not just the stdout log -- the per-fold
#      receipts (grid.json, coefs.csv, test_predictions.csv, val_permutation_importance.csv, done.json)
#      must survive even if the instance is reclaimed (spot) before a manual pull.
#   2. The S3 prefix is keyed by MACHINE ROLE (A/B), not instance-id (checker's blocking finding: a spot
#      reclaim gives the replacement a NEW instance id, so an instance-id-keyed prefix would start from an
#      empty outputs/ and redo every already-finished fold, at hours of paid compute each). Before running
#      s1_run.py, this role's prefix is synced BACK into research/model/logs/s1/ first, so its own
#      restart-safe done-marker check has something to see. A spot reclaim still needs a MANUAL relaunch
#      -- nothing here relaunches automatically; the fix only makes a manual relaunch not redo finished work.
#   3. The outer hard safety net is 36h (2160 min), not 90 min -- sized from the Checker's worst-case
#      projection (~29h on 1 machine; each machine here does ~half the folds, worst case ~14.5h), plus
#      margin, since the Checker's own GramBuildTooSlow tripwire (research/model/s1_newton.py) already
#      stops a MISCONFIGURED machine fast -- this net is only for a LEGITIMATELY slow but still-running job.
#
# FOLDS is substituted per machine before launch: "7,4,3,0" (machine A) or "6,5,2,1" (machine B) --
# balanced by real train-event count (~10.64M each), biggest fold first on each so the tripwire fires
# early (planner's ruling, checked against the checker's own balance proposal with real per-fold counts).
# MACHINE_ROLE is "A" or "B" -- the S3 log/output prefix is keyed by THIS, not by instance-id (checker's
# blocking finding: a spot reclaim gives the replacement instance a NEW id, so an instance-id-keyed prefix
# would start from an empty outputs/ and redo every fold the terminated instance had already finished, at
# hours of paid compute each). The instance id still goes into the log TEXT for provenance, just not the
# S3 path.
FOLDS="6,5,2,1"
MACHINE_ROLE="B"

TOKEN=$(curl -sf --max-time 3 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null) || TOKEN=""
if [ -n "$TOKEN" ]; then
  INSTANCE_ID=$(curl -sf --max-time 3 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null) || INSTANCE_ID=""
else
  INSTANCE_ID=""
fi
[ -n "$INSTANCE_ID" ] || INSTANCE_ID="$(hostname)-$(date +%s)"
echo "[S1-RUN-AWS] instance id: $INSTANCE_ID, machine role: $MACHINE_ROLE, folds=$FOLDS"
LOG_PREFIX="s3://pair-trading-hl-289869684922/s1_run/logs/${MACHINE_ROLE}/"
AWS_BIN=""

sync_logs() {
  if [ -z "$AWS_BIN" ] || [ ! -x "$AWS_BIN" ]; then
    echo "[S1-RUN-AWS] sync_logs: AWS_BIN not ready yet, skipping this cycle"
    return 0
  fi
  if ! "$AWS_BIN" s3 cp /var/log/s1-run.log "${LOG_PREFIX}s1-run_${INSTANCE_ID}.log" --region ap-northeast-1 >/dev/null 2>&1; then
    echo "[S1-RUN-AWS] sync_logs: s1-run.log upload FAILED"
  fi
  if [ -f /tmp/build_cache.log ]; then
    if ! "$AWS_BIN" s3 cp /tmp/build_cache.log "${LOG_PREFIX}build_cache_${INSTANCE_ID}.log" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[S1-RUN-AWS] sync_logs: build_cache.log upload FAILED"
    fi
  fi
  if [ -d /root/Pair_Trading/research/model/logs/s1 ]; then
    if ! "$AWS_BIN" s3 sync --quiet /root/Pair_Trading/research/model/logs/s1/ "${LOG_PREFIX}outputs/" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[S1-RUN-AWS] sync_logs: outputs/ sync FAILED"
    fi
  fi
}

finalize() {
  local exit_code=$?
  echo "[S1-RUN-AWS] finalize: exit_code=$exit_code $(date -u)"
  sync_logs
  sleep 120
  sync_logs
  shutdown -h now
}
trap finalize EXIT

shutdown -h +2160 &   # outer hard safety net (36h), independent of finalize's own wait + shutdown

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y python3-venv python3-pip curl

python3 -m venv /opt/v
/opt/v/bin/pip install -q numpy scipy pandas pyarrow threadpoolctl awscli
AWS_BIN=/opt/v/bin/aws
PY=/opt/v/bin/python
echo "[S1-RUN-AWS] python: $($PY --version) numpy: $($PY -c 'import numpy; print(numpy.__version__)')"

( trap - EXIT; while true; do sleep 60; sync_logs; done ) &

mkdir -p /root/Pair_Trading
cd /root/Pair_Trading

EXPECTED_SHA="759f71e5e19fae01d50ec396bf56dcfb4d66c8493377df5067b8655321c63213"
$AWS_BIN s3 cp "s3://pair-trading-hl-289869684922/s1_run/${EXPECTED_SHA}.tar.gz" /tmp/payload.tar.gz
ACTUAL_SHA=$(sha256sum /tmp/payload.tar.gz | awk '{print $1}')
echo "[S1-RUN-AWS] payload sha256: $ACTUAL_SHA (expected $EXPECTED_SHA)"
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
  echo "[S1-RUN-AWS] PAYLOAD SHA MISMATCH -- aborting, not extracting"
  exit 1
fi
tar xzf /tmp/payload.tar.gz -C /root/Pair_Trading/
echo "[S1-RUN-AWS] payload extracted: $(date -u)"

for f in research/model/harness.py research/model/inputs_v1_pair.csv research/model/hazard_logistic.py \
         research/model/s1_preprocess.py research/model/s1_model.py research/model/s1_newton.py \
         research/model/s1_run.py research/model/build_cache_v1_pair.py; do
  echo "[S1-RUN-AWS] sha256 $f: $(sha256sum $f | awk '{print $1}')"
done

mkdir -p research/datasets/master/work/pair research/datasets/master/versions/v1
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/MANIFEST.json research/datasets/master/versions/v1/MANIFEST.json
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/CHANGELOG.md research/datasets/master/versions/v1/CHANGELOG.md
$AWS_BIN s3 sync --quiet s3://pair-trading-hl-289869684922/master/versions/v1/pair/ research/datasets/master/work/pair/
echo "[S1-RUN-AWS] v1 data pulled (GET/sync only, read-only against master data; the only writes anywhere are the log/output copies to s1_run/logs/${MACHINE_ROLE}/, this run's own approved prefix): $(date -u)"
du -sh research/datasets/master/work/pair/

if ! PATH=/opt/v/bin:$PATH $PY -u research/model/build_cache_v1_pair.py > /tmp/build_cache.log 2>&1; then
  BUILD_EXIT=1
else
  BUILD_EXIT=0
fi
tail -n 30 /tmp/build_cache.log
echo "[S1-RUN-AWS] cache build exit=$BUILD_EXIT: $(date -u)"
if [ $BUILD_EXIT -ne 0 ]; then
  echo "[S1-RUN-AWS] CACHE BUILD FAILED -- stopping, nothing further to run"
  exit 1
fi

# ONE parallel layer baseline (checker's established principle): hazard_nll_grad's own
# ThreadPoolExecutor-over-chunks is the default parallel layer; BLAS is pinned to 1 thread everywhere
# EXCEPT inside s1_newton.build_hessian_blocks' own threadpoolctl.threadpool_limits(64) scope around the
# Gram build, which overrides this baseline for just that block (committed 9209a96).
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

# Restart-safety across a spot reclaim (checker's blocking finding): pull back whatever this role's
# machine already finished BEFORE running s1_run.py, so its restart-safe done-marker check actually has
# something to see. A fresh machine with nothing in S3 yet just syncs an empty prefix -- harmless.
mkdir -p research/model/logs/s1
if ! "$AWS_BIN" s3 sync --quiet "${LOG_PREFIX}outputs/" research/model/logs/s1/ --region ap-northeast-1; then
  echo "[S1-RUN-AWS] WARNING: pull-back sync from ${LOG_PREFIX}outputs/ failed -- if this role has finished folds in S3, they will NOT be recognized and may be redone"
fi
FOUND_MARKERS=$(ls research/model/logs/s1/fold*_done.json 2>/dev/null || true)
if [ -n "$FOUND_MARKERS" ]; then
  echo "[S1-RUN-AWS] restored done markers from ${LOG_PREFIX}outputs/: $FOUND_MARKERS"
else
  echo "[S1-RUN-AWS] no done markers found at ${LOG_PREFIX}outputs/ -- starting this role's folds from scratch"
fi

PATH=/opt/v/bin:$PATH $PY -u research/model/s1_run.py --folds "$FOLDS"
echo "[S1-RUN-AWS] ALL DONE: $(date -u)"
