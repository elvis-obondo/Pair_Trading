#!/bin/bash
# HL-MASTER1 (G7 raw pass): run build7_oi.py over a list of days on one EC2 machine in ap-northeast-1, check each
# day's T1 against that day's flow table (build 2 d3 stage-1 output), write to our bucket, terminate itself.
#
#   research/hyperliquid/build7_ec2.sh launch NAME TYPE PAR TIMER_MIN DAY...
# Setup, the role and `check` are build2_ec2.sh's. ONDEMAND=1 for on-demand. A hard `shutdown -h +TIMER_MIN`
# is the first thing the machine does; the run ends with `shutdown -h now`; instance-initiated shutdown = terminate.
set -euo pipefail
A="$HOME/.local/bin/aws --cli-read-timeout 60 --cli-connect-timeout 20"
R=ap-northeast-1
ACCT=289869684922
BKT=pair-trading-hl-$ACCT
ROLE=hl-build2-ec2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "${ONDEMAND:-0}" = 1 ]; then MARKET_OPTS=(); else
  MARKET_OPTS=(--instance-market-options 'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}'); fi
FLOWSRC=${FLOWSRC:-build2/d3/day}
VOL=${VOL:-60}
case "${1:-}" in
launch)
  NAME=$2; TYPE=$3; PAR=$4; TIMER=$5; shift 5; DAYS="$*"
  for f in build2_fills.py build5_wallets.py build7_oi.py; do $A s3 cp "$HERE/$f" s3://$BKT/build7/code/$f --region $R --only-show-errors; done
  $A s3 cp "$HERE/logs/build2_listing.txt" s3://$BKT/build7/code/listing.txt --region $R --only-show-errors
  $A s3 cp "$HERE/logs/build5_missing_minutes.parquet" s3://$BKT/build7/code/build5_missing_minutes.parquet --region $R --only-show-errors
  AMI=$($A ssm get-parameter --region $R --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
  UD=$(mktemp)
  cat > "$UD" <<EOT
#!/bin/bash
shutdown -h +$TIMER
exec > /var/log/build7.log 2>&1
set -x
OUT=s3://$BKT/build7/$NAME
up() { aws s3 cp /var/log/build7.log \$OUT/ec2.log --region $R --only-show-errors || true; }
trap up EXIT
dnf install -y -q lz4 python3.11 python3.11-pip time
python3.11 -m pip install -q orjson pandas pyarrow numpy
mkdir -p /w/out /w/flow && cd /w
for f in build2_fills.py build5_wallets.py build7_oi.py listing.txt build5_missing_minutes.parquet; do aws s3 cp s3://$BKT/build7/code/\$f . --region $R --only-show-errors; done
export HL_LISTING=/w/listing.txt HL_MISSING=/w/build5_missing_minutes.parquet OMP_NUM_THREADS=1 AWS_DEFAULT_REGION=$R
nproc; free -g
date -u +%FT%TZ > start.txt
printf '%s\n' $DAYS | xargs -P $PAR -I{} sh -c 'aws s3 cp s3://$BKT/$FLOWSRC/{}.parquet /w/flow/{}.parquet --region $R --only-show-errors; /usr/bin/time -v python3.11 -u build7_oi.py {} /w/out --flow /w/flow > /w/out/{}.stdout 2> /w/out/{}.time; echo "{} exit \$?"' | tee /w/out/exits.txt
date -u +%FT%TZ > end.txt
cp start.txt end.txt /w/out/
aws s3 cp /w/out \$OUT/ --recursive --region $R --only-show-errors
up
shutdown -h now
EOT
  SUB=$($A ec2 describe-subnets --region $R --filters Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
  ID=$($A ec2 run-instances --region $R --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
       --iam-instance-profile Name=$ROLE --instance-initiated-shutdown-behavior terminate \
       ${MARKET_OPTS[@]+"${MARKET_OPTS[@]}"} \
       --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=$VOL,VolumeType=gp3,DeleteOnTermination=true}" \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=hl-build7-$NAME}]" \
       --user-data "file://$UD" --query 'Instances[0].InstanceId' --output text)
  rm -f "$UD"
  echo "launched $ID ($TYPE, $([ "${ONDEMAND:-0}" = 1 ] && echo on-demand || echo spot)) name=$NAME par=$PAR timer=${TIMER}min days=$DAYS"
  ;;
*) sed -n '2,8p' "$0"; exit 1 ;;
esac
