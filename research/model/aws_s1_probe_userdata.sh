#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/s1-probe.log > /dev/console) 2>&1

# Planner's ruling, S1 review round 6, attempt 3 (console-output capture stalled silently in attempt 2,
# after setup completed cleanly -- no error, no result either): sync the logs to S3 every 60s and once
# more before shutdown, poll S3 instead of the console. The role already has PutObject on this bucket
# (checker accepted using it for this one prefix only, tmp/probe/logs/<instance-id>/ -- the rest of the
# job still never writes/deletes anywhere else in the bucket).
#
# Checker's blocking fixes, round 2: (1) `curl -s` alone to the metadata endpoint returns a 401 error
# PAGE (still exit 0) when IMDSv2 is required -- that error text would silently become INSTANCE_ID, and
# every upload would then fail silently. Use an IMDSv2 token (PUT .../api/token) with `curl -sf` (fails
# loudly on a bad response), falling back to `hostname` if even that fails. (2) The background loop must
# not start before AWS_BIN points at a REAL binary -- started too early, it keeps the empty/wrong value
# in its subshell forever and never uploads anything, which is exactly the blindness this attempt exists
# to fix. Moved to start right after the venv's aws is confirmed working, not at the top of the script.
TOKEN=$(curl -sf --max-time 3 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null) || TOKEN=""
if [ -n "$TOKEN" ]; then
  INSTANCE_ID=$(curl -sf --max-time 3 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null) || INSTANCE_ID=""
else
  INSTANCE_ID=""
fi
[ -n "$INSTANCE_ID" ] || INSTANCE_ID="$(hostname)-$(date +%s)"
echo "[S1-AWS-PROBE] instance id for the log prefix: $INSTANCE_ID"
LOG_PREFIX="s3://pair-trading-hl-289869684922/tmp/probe/logs/${INSTANCE_ID}/"
AWS_BIN=""

sync_logs() {
  if [ -z "$AWS_BIN" ] || [ ! -x "$AWS_BIN" ]; then
    echo "[S1-AWS-PROBE] sync_logs: AWS_BIN not ready yet, skipping this cycle"
    return 0
  fi
  if ! "$AWS_BIN" s3 cp /var/log/s1-probe.log "${LOG_PREFIX}s1-probe.log" --region ap-northeast-1 >/dev/null 2>&1; then
    echo "[S1-AWS-PROBE] sync_logs: s1-probe.log upload FAILED"
  fi
  if [ -f /tmp/build_cache.log ]; then
    if ! "$AWS_BIN" s3 cp /tmp/build_cache.log "${LOG_PREFIX}build_cache.log" --region ap-northeast-1 >/dev/null 2>&1; then
      echo "[S1-AWS-PROBE] sync_logs: build_cache.log upload FAILED"
    fi
  fi
}

finalize() {
  local exit_code=$?
  echo "[S1-AWS-PROBE] finalize: exit_code=$exit_code $(date -u)"
  sync_logs
  sleep 120   # planner's ruling: let the last S3 copy actually land before the instance disappears
  sync_logs
  shutdown -h now
}
trap finalize EXIT

shutdown -h +90 &   # outer hard safety net, independent of finalize's own 120s wait + shutdown

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y python3-venv python3-pip curl

# venv + pip (S1 review round 6): recent Ubuntu's system pip refuses a bare `pip3 install`
# ("externally-managed-environment"); a venv sidesteps that for everything, including the AWS CLI itself
# (pip's pure-python awscli, not apt's package, which does not exist on recent Ubuntu).
python3 -m venv /opt/v
/opt/v/bin/pip install -q numpy scipy pandas pyarrow threadpoolctl awscli
AWS_BIN=/opt/v/bin/aws
PY=/opt/v/bin/python
echo "[S1-AWS-PROBE] python: $($PY --version) numpy: $($PY -c 'import numpy; print(numpy.__version__)')"

# Background loop starts only now that AWS_BIN is a real, working binary (checker's fix) -- it inherits
# the EXIT trap by default, so `trap - EXIT` clears that inside the subshell: the loop's own (eventual,
# harmless) death at shutdown must never ALSO call finalize a second time.
( trap - EXIT; while true; do sleep 60; sync_logs; done ) &

mkdir -p /root/Pair_Trading
cd /root/Pair_Trading

EXPECTED_SHA=0aee906d2120c8635b02f755fc180055d0944800e7aa031c88090a3a1f27f500
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/tmp/probe/${EXPECTED_SHA}.tar.gz /tmp/payload.tar.gz
ACTUAL_SHA=$(sha256sum /tmp/payload.tar.gz | awk '{print $1}')
echo "[S1-AWS-PROBE] payload sha256: $ACTUAL_SHA (expected $EXPECTED_SHA)"
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
  echo "[S1-AWS-PROBE] PAYLOAD SHA MISMATCH -- aborting, not extracting"
  exit 1
fi
tar xzf /tmp/payload.tar.gz -C /root/Pair_Trading/
echo "[S1-AWS-PROBE] payload extracted: $(date -u)"

for f in research/model/harness.py research/model/inputs_v1_pair.csv research/model/hazard_logistic.py \
         research/model/s1_preprocess.py research/model/s1_aws_thread_timing.py \
         research/model/build_cache_v1_pair.py; do
  echo "[S1-AWS-PROBE] sha256 $f: $(sha256sum $f | awk '{print $1}')"
done

mkdir -p research/datasets/master/work/pair research/datasets/master/versions/v1
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/MANIFEST.json research/datasets/master/versions/v1/MANIFEST.json
$AWS_BIN s3 cp s3://pair-trading-hl-289869684922/master/versions/v1/CHANGELOG.md research/datasets/master/versions/v1/CHANGELOG.md
$AWS_BIN s3 sync --quiet s3://pair-trading-hl-289869684922/master/versions/v1/pair/ research/datasets/master/work/pair/
echo "[S1-AWS-PROBE] v1 data pulled (GET/sync only, no write/delete call issued against the master data -- read-only there; the ONLY writes anywhere are the log copies to tmp/probe/logs/, approved for this probe): $(date -u)"
du -sh research/datasets/master/work/pair/

if ! PATH=/opt/v/bin:$PATH $PY -u research/model/build_cache_v1_pair.py > /tmp/build_cache.log 2>&1; then
  BUILD_EXIT=1
else
  BUILD_EXIT=0
fi
tail -n 30 /tmp/build_cache.log
echo "[S1-AWS-PROBE] cache build exit=$BUILD_EXIT: $(date -u)"
if [ $BUILD_EXIT -ne 0 ]; then
  echo "[S1-AWS-PROBE] CACHE BUILD FAILED -- stopping, nothing further to time"
  exit 1
fi

# ONE parallel layer only (checker's established principle, S1 review round 6): hazard_nll_grad's own
# ThreadPoolExecutor-over-chunks is the sole parallelism layer here; BLAS itself is pinned to 1 thread so
# each chunk's GEMV inside a Python thread doesn't ALSO try to spawn its own BLAS threads.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

PATH=/opt/v/bin:$PATH $PY -u research/model/s1_aws_thread_timing.py
echo "[S1-AWS-PROBE] ALL DONE: $(date -u)"
