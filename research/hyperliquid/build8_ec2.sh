#!/bin/bash
# HL-MASTER1 (G8 raw pass): run build8_l2.py over a list of days on one EC2 machine in us-east-2 (the archive is in us-east-1 and requester-pays;
# EC2 is denied in us-east-1 by the account's SCP), write the per-day tables to our bucket (ap-northeast-1), terminate itself.
#
#   research/hyperliquid/build8_ec2.sh launch NAME TYPE PAR TIMER_MIN DAY...
# ONDEMAND=1 for on-demand (default spot). A hard `shutdown -h +TIMER_MIN` is the first thing the machine does; the run ends with `shutdown -h now`;
# instance-initiated shutdown = terminate. Output: s3://pair-trading-hl-<acct>/build8/NAME/{DAY}_l2.parquet, {DAY}_l2_index.parquet, ec2.log.
set -euo pipefail
A="$HOME/.local/bin/aws --cli-read-timeout 60 --cli-connect-timeout 20"
R=us-east-2
BR=ap-northeast-1
ACCT=289869684922
BKT=pair-trading-hl-$ACCT
ROLE=hl-build2-ec2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "${ONDEMAND:-0}" = 1 ]; then MARKET_OPTS=(); else
  MARKET_OPTS=(--instance-market-options 'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}'); fi
VOL=${VOL:-30}
case "${1:-}" in
launch)
  NAME=$2; TYPE=$3; PAR=$4; TIMER=$5; shift 5; DAYS="$*"
  $A s3 cp "$HERE/build8_l2.py" s3://$BKT/build8/code/build8_l2.py --region $BR --only-show-errors
  $A s3 cp "$HERE/coins.csv" s3://$BKT/build8/code/coins.csv --region $BR --only-show-errors
  AMI=$($A ssm get-parameter --region $R --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
  UD=$(mktemp)
  cat > "$UD" <<EOT
#!/bin/bash
shutdown -h +$TIMER
exec > /var/log/build8.log 2>&1
set -x
OUT=s3://$BKT/build8/$NAME
up() { aws s3 cp /var/log/build8.log \$OUT/ec2.log --region $BR --only-show-errors || true; }
trap up EXIT
dnf install -y -q lz4 python3.11 python3.11-pip time
python3.11 -m pip install -q orjson pandas pyarrow numpy boto3
mkdir -p /w/out && cd /w
for f in build8_l2.py coins.csv; do aws s3 cp s3://$BKT/build8/code/\$f . --region $BR --only-show-errors; done
export OMP_NUM_THREADS=1 AWS_DEFAULT_REGION=$R
nproc; free -g
date -u +%FT%TZ > start.txt
(while true; do sleep 600; aws s3 sync /w/out \$OUT/ --region $BR --only-show-errors; done) &      # partial results survive a timer shutdown
printf '%s\n' $DAYS | xargs -P $PAR -I{} sh -c '/usr/bin/time -v python3.11 -u build8_l2.py {} /w/out --coins coins.csv > /w/out/{}.stdout 2> /w/out/{}.time; echo "{} exit \$?"'
date -u +%FT%TZ > end.txt
cp start.txt end.txt /w/out/
aws s3 cp /w/out \$OUT/ --recursive --region $BR --only-show-errors
up
shutdown -h now
EOT
  SUB=$($A ec2 describe-subnets --region $R --filters Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
  ID=$($A ec2 run-instances --region $R --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
       --iam-instance-profile Name=$ROLE --instance-initiated-shutdown-behavior terminate \
       ${MARKET_OPTS[@]+"${MARKET_OPTS[@]}"} \
       --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=$VOL,VolumeType=gp3,DeleteOnTermination=true}" \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=hl-build8-$NAME}]" \
       --user-data "file://$UD" --query 'Instances[0].InstanceId' --output text)
  rm -f "$UD"
  echo "launched $ID ($TYPE, $([ "${ONDEMAND:-0}" = 1 ] && echo on-demand || echo spot)) name=$NAME par=$PAR timer=${TIMER}min days=$DAYS"
  ;;
*) sed -n '2,8p' "$0"; exit 1 ;;
esac
