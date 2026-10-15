#!/bin/bash
# HL-BUILD2: launch one EC2 machine in ap-northeast-1 that runs build2_fills.py
# over a list of days, writes outputs to our bucket, and terminates itself.
#
#   research/hyperliquid/build2_ec2.sh setup              bucket + IAM role (idempotent)
#   research/hyperliquid/build2_ec2.sh launch NAME TYPE PAR TIMER_MIN DAY...
#   research/hyperliquid/build2_ec2.sh check              instances still running (want none)
#
# SAFETY (brief, Part D): instance-initiated shutdown = TERMINATE; a hard
# `shutdown -h +TIMER_MIN` is the FIRST thing the machine does; the run ends with
# `shutdown -h now`. Spot, one-time. Quota on this account: 5 vCPU (spot and
# on-demand), so at most a 4-vCPU machine.
set -euo pipefail
# timeouts so a refused or stalled API call fails fast (one launch hung 15 min in describe-subnets)
A="$HOME/.local/bin/aws --cli-read-timeout 60 --cli-connect-timeout 20"
R=ap-northeast-1
ACCT=289869684922
BKT=pair-trading-hl-$ACCT
ROLE=hl-build2-ec2
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# spot by default; ONDEMAND=1 launches on-demand (after a spot capacity interruption)
if [ "${ONDEMAND:-0}" = 1 ]; then MARKET_OPTS=(); else
  MARKET_OPTS=(--instance-market-options 'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}'); fi

case "${1:-}" in
setup)
  $A s3api head-bucket --bucket $BKT --region $R 2>/dev/null \
    || $A s3api create-bucket --bucket $BKT --region $R --create-bucket-configuration LocationConstraint=$R
  $A s3api put-public-access-block --bucket $BKT --region $R \
    --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  if ! $A iam get-role --role-name $ROLE >/dev/null 2>&1; then
    $A iam create-role --role-name $ROLE --assume-role-policy-document \
      '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
    $A iam put-role-policy --role-name $ROLE --policy-name s3 --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[
      {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::hl-mainnet-node-data\",\"arn:aws:s3:::hl-mainnet-node-data/*\"]},
      {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::$BKT\",\"arn:aws:s3:::$BKT/*\"]}]}"
    $A iam create-instance-profile --instance-profile-name $ROLE >/dev/null
    $A iam add-role-to-instance-profile --instance-profile-name $ROLE --role-name $ROLE
    sleep 10   # profile propagation
  fi
  echo "bucket $BKT and role $ROLE ready"
  ;;

launch)
  NAME=$2; TYPE=$3; PAR=$4; TIMER=$5; shift 5; DAYS="$*"
  $A s3 cp "$HERE/build2_fills.py" s3://$BKT/build2/code/build2_fills.py --region $R --only-show-errors
  $A s3 cp "$HERE/logs/build2_listing.txt" s3://$BKT/build2/code/listing.txt --region $R --only-show-errors
  AMI=$($A ssm get-parameter --region $R --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
  UD=$(mktemp)
  cat > "$UD" <<EOF
#!/bin/bash
shutdown -h +$TIMER
exec > /var/log/build2.log 2>&1
set -x
OUT=s3://$BKT/build2/$NAME
up() { aws s3 cp /var/log/build2.log \$OUT/ec2.log --region $R --only-show-errors || true; }
trap up EXIT
dnf install -y -q lz4 python3.11 python3.11-pip time
python3.11 -m pip install -q orjson pandas pyarrow numpy
mkdir -p /w/out && cd /w
aws s3 cp s3://$BKT/build2/code/build2_fills.py . --region $R --only-show-errors
aws s3 cp s3://$BKT/build2/code/listing.txt . --region $R --only-show-errors
export HL_LISTING=/w/listing.txt OMP_NUM_THREADS=1 AWS_DEFAULT_REGION=$R
nproc; free -g
date -u +%FT%TZ > start.txt
printf '%s\n' $DAYS | xargs -P $PAR -I{} sh -c '/usr/bin/time -v python3.11 -u build2_fills.py {} /w/out > /w/out/{}.stdout 2> /w/out/{}.time; echo "{} exit \$?"' | tee /w/out/stage1_exits_part.txt
date -u +%FT%TZ > end.txt
cp start.txt end.txt /w/out/
aws s3 cp /w/out \$OUT/ --recursive --region $R --only-show-errors
up
shutdown -h now
EOF
  SUB=$($A ec2 describe-subnets --region $R --filters Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
  ID=$($A ec2 run-instances --region $R --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
       --iam-instance-profile Name=$ROLE --instance-initiated-shutdown-behavior terminate \
       ${MARKET_OPTS[@]+"${MARKET_OPTS[@]}"} \
       --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=60,VolumeType=gp3,DeleteOnTermination=true}' \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=hl-build2-$NAME}]" \
       --user-data "file://$UD" --query 'Instances[0].InstanceId' --output text)
  rm -f "$UD"
  echo "launched $ID ($TYPE, spot) name=$NAME par=$PAR timer=${TIMER}min days=$DAYS"
  ;;

launch-d1)
  # Stage 1 over every day of the window (PAR in parallel), then stage 2 on the
  # same machine; uploads day outputs, the assembled futures/flow/coin_month and
  # all logs. A stage-2 gate STOP (exit 2) still uploads its meta and logs.
  NAME=$2; TYPE=$3; PAR=$4; TIMER=$5; FIRST=$6; LAST=$7
  for f in build2_fills.py build2_assemble.py; do
    $A s3 cp "$HERE/$f" s3://$BKT/build2/code/$f --region $R --only-show-errors; done
  $A s3 cp "$HERE/logs/build2_listing.txt" s3://$BKT/build2/code/listing.txt --region $R --only-show-errors
  AMI=$($A ssm get-parameter --region $R --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
  UD=$(mktemp)
  cat > "$UD" <<EOF
#!/bin/bash
shutdown -h +$TIMER
exec > /var/log/build2.log 2>&1
set -x
OUT=s3://$BKT/build2/$NAME
up() { aws s3 cp /var/log/build2.log \$OUT/ec2.log --region $R --only-show-errors || true; }
trap up EXIT
dnf install -y -q lz4 python3.11 python3.11-pip time
python3.11 -m pip install -q orjson pandas pyarrow numpy
mkdir -p /w/day /w/asm && cd /w
for f in build2_fills.py build2_assemble.py listing.txt; do aws s3 cp s3://$BKT/build2/code/\$f . --region $R --only-show-errors; done
export HL_LISTING=/w/listing.txt OMP_NUM_THREADS=1 AWS_DEFAULT_REGION=$R
python3.11 -c "import pandas as pd; print('\n'.join(pd.date_range('$FIRST','$LAST',freq='D').strftime('%Y%m%d')))" > days.txt
wc -l days.txt
date -u +%FT%TZ > /w/day/stage1_start.txt
xargs -P $PAR -I{} sh -c '/usr/bin/time -v python3.11 -u build2_fills.py {} /w/day > /w/day/{}.stdout 2> /w/day/{}.time; echo "{} exit \$?"' < days.txt | tee /w/day/stage1_exits.txt
date -u +%FT%TZ > /w/day/stage1_end.txt
aws s3 cp /w/day \$OUT/day/ --recursive --region $R --only-show-errors
if grep -qv ' exit 0$' /w/day/stage1_exits.txt; then echo "STAGE 1 FAILURES"; grep -v ' exit 0$' /w/day/stage1_exits.txt; up; shutdown -h now; exit 1; fi
/usr/bin/time -v python3.11 -u build2_assemble.py /w/day /w/asm > /w/asm_stdout.txt 2> /w/asm_time.txt; echo "stage2 exit \$?"
cp /w/asm_stdout.txt /w/asm_time.txt /w/asm/ || true
aws s3 cp /w/asm \$OUT/asm/ --recursive --region $R --only-show-errors
up
shutdown -h now
EOF
  SUB=$($A ec2 describe-subnets --region $R --filters Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
  ID=$($A ec2 run-instances --region $R --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
       --iam-instance-profile Name=$ROLE --instance-initiated-shutdown-behavior terminate \
       ${MARKET_OPTS[@]+"${MARKET_OPTS[@]}"} \
       --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=120,VolumeType=gp3,DeleteOnTermination=true}' \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=hl-build2-$NAME}]" \
       --user-data "file://$UD" --query 'Instances[0].InstanceId' --output text)
  rm -f "$UD"
  echo "launched $ID ($TYPE, spot) name=$NAME par=$PAR timer=${TIMER}min days=$FIRST..$LAST"
  ;;

launch-resume)
  # Re-run stage 1 for the given DAYS only, reusing every other day's outputs
  # already in s3://.../build2/NAME/day/, then stage 2 over the full window.
  # The rerun days' outputs and exits replace the old ones in NAME/day/.
  NAME=$2; TYPE=$3; PAR=$4; TIMER=$5; shift 5; DAYS="$*"
  for f in build2_fills.py build2_assemble.py; do
    $A s3 cp "$HERE/$f" s3://$BKT/build2/code/$f --region $R --only-show-errors; done
  AMI=$($A ssm get-parameter --region $R --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
  UD=$(mktemp)
  cat > "$UD" <<EOF
#!/bin/bash
shutdown -h +$TIMER
exec > /var/log/build2.log 2>&1
set -x
OUT=s3://$BKT/build2/$NAME
up() { aws s3 cp /var/log/build2.log \$OUT/ec2_resume.log --region $R --only-show-errors || true; }
trap up EXIT
dnf install -y -q lz4 python3.11 python3.11-pip time
python3.11 -m pip install -q orjson pandas pyarrow numpy
mkdir -p /w/day /w/asm && cd /w
for f in build2_fills.py build2_assemble.py listing.txt; do aws s3 cp s3://$BKT/build2/code/\$f . --region $R --only-show-errors; done
aws s3 cp \$OUT/day/ /w/day/ --recursive --region $R --only-show-errors
export HL_LISTING=/w/listing.txt OMP_NUM_THREADS=1 AWS_DEFAULT_REGION=$R
if [ -n "$DAYS" ]; then
printf '%s\n' $DAYS | xargs -P $PAR -I{} sh -c '/usr/bin/time -v python3.11 -u build2_fills.py {} /w/day > /w/day/{}.stdout 2> /w/day/{}.time; echo "{} exit \$?"' | tee /w/day/resume_exits.txt
python3.11 - <<'PY'
ex = dict(l.split(" exit ") for l in open("/w/day/stage1_exits.txt").read().split("\n") if " exit " in l)
ex.update(dict(l.split(" exit ") for l in open("/w/day/resume_exits.txt").read().split("\n") if " exit " in l))
open("/w/day/stage1_exits.txt", "w").write("".join(f"{d} exit {r}\n" for d, r in sorted(ex.items())))
print(len(ex), "days;", sum(r != "0" for r in ex.values()), "non-zero")
PY
for d in $DAYS; do aws s3 cp /w/day/ \$OUT/day/ --recursive --exclude '*' --include "\$d*" --region $R --only-show-errors; done
aws s3 cp /w/day/stage1_exits.txt \$OUT/day/ --region $R --only-show-errors
aws s3 cp /w/day/resume_exits.txt \$OUT/day/ --region $R --only-show-errors
else
echo "stage 1 reused: \$(wc -l < /w/day/stage1_exits.txt) days, \$(grep -vc ' exit 0\$' /w/day/stage1_exits.txt) non-zero"
fi
if grep -qv ' exit 0$' /w/day/stage1_exits.txt; then echo "STAGE 1 FAILURES"; grep -v ' exit 0$' /w/day/stage1_exits.txt; up; shutdown -h now; exit 1; fi
ASM_PAR=$PAR /usr/bin/time -v python3.11 -u build2_assemble.py /w/day /w/asm > /w/asm_stdout.txt 2> /w/asm_time.txt; echo "stage2 exit \$?"
cp /w/asm_stdout.txt /w/asm_time.txt /w/asm/ || true
aws s3 cp /w/asm \$OUT/asm/ --recursive --region $R --only-show-errors
up
shutdown -h now
EOF
  SUB=$($A ec2 describe-subnets --region $R --filters Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
  ID=$($A ec2 run-instances --region $R --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
       --iam-instance-profile Name=$ROLE --instance-initiated-shutdown-behavior terminate \
       ${MARKET_OPTS[@]+"${MARKET_OPTS[@]}"} \
       --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=120,VolumeType=gp3,DeleteOnTermination=true}' \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=hl-build2-$NAME-resume}]" \
       --user-data "file://$UD" --query 'Instances[0].InstanceId' --output text)
  rm -f "$UD"
  echo "launched $ID ($TYPE, $([ "${ONDEMAND:-0}" = 1 ] && echo on-demand || echo spot)) resume name=$NAME par=$PAR timer=${TIMER}min days=$DAYS"
  ;;

check)
  $A ec2 describe-instances --region $R --filters Name=instance-state-name,Values=pending,running,stopping \
     --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,LaunchTime]' --output text
  ;;
*) sed -n '2,12p' "$0"; exit 1 ;;
esac
