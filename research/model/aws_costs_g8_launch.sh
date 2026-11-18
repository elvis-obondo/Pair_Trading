#!/bin/bash
# COSTS1: Tokyo EC2 job that extracts the needed G8 L2-summary rows (diagnostics/costs_g8_extract.py) from s3://pair-trading-hl-289869684922/build8/full/ and writes them back
# to s3://pair-trading-hl-289869684922/costs1/g8/. Same region as the bucket (no transfer cost). On-demand c7g.large (2 vCPU, 4 GB), 20 GB disk, hard shutdown timer, shuts itself down (= terminates).
#
#   research/model/aws_costs_g8_launch.sh stage     # uploads the two payload files to s3://.../costs1/code/ and prints their sha256 (needs the user's yes)
#   research/model/aws_costs_g8_launch.sh launch    # runs the instance (needs the user's yes for THIS launch)
# The user-data re-checks both payload sha256 values (the launcher computes them from the local files at launch) and refuses to run on a mismatch.
set -euo pipefail
A="$HOME/.local/bin/aws --cli-read-timeout 60 --cli-connect-timeout 20"
R=ap-northeast-1
ACCT=289869684922
BKT=pair-trading-hl-$ACCT
ROLE=hl-build2-ec2
TYPE=${TYPE:-c7g.large}
TIMER=${TIMER:-40}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAY1="$HERE/diagnostics/costs_g8_extract.py"
PAY2="$HERE/logs/costs1/l2_targets_priority.parquet"
SHA1=$(shasum -a 256 "$PAY1" | cut -d' ' -f1)
SHA2=$(shasum -a 256 "$PAY2" | cut -d' ' -f1)
case "${1:-}" in
stage)
  $A s3 cp "$PAY1" s3://$BKT/costs1/code/costs_g8_extract.py --region $R --only-show-errors
  $A s3 cp "$PAY2" s3://$BKT/costs1/code/l2_targets_priority.parquet --region $R --only-show-errors
  echo "staged: costs_g8_extract.py sha256 $SHA1; l2_targets_priority.parquet sha256 $SHA2"
  ;;
launch)
  AMI=$($A ssm get-parameter --region $R --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
  UD=$(mktemp)
  cat > "$UD" <<EOT
#!/bin/bash
shutdown -h +$TIMER
exec > /var/log/g8x.log 2>&1
set -x
OUT=s3://$BKT/costs1/g8
up() { aws s3 cp /var/log/g8x.log \$OUT/ec2.log --region $R --only-show-errors || true; }
trap up EXIT
dnf install -y -q python3.11 python3.11-pip
python3.11 -m pip install -q pandas pyarrow numpy
mkdir -p /w && cd /w
aws s3 cp s3://$BKT/costs1/code/costs_g8_extract.py . --region $R --only-show-errors
aws s3 cp s3://$BKT/costs1/code/l2_targets_priority.parquet . --region $R --only-show-errors
echo "$SHA1  costs_g8_extract.py" | sha256sum -c - || { echo "SHA MISMATCH costs_g8_extract.py"; shutdown -h now; exit 1; }
echo "$SHA2  l2_targets_priority.parquet" | sha256sum -c - || { echo "SHA MISMATCH targets"; shutdown -h now; exit 1; }
date -u +%FT%TZ > start.txt
timeout 1800 python3.11 -u costs_g8_extract.py l2_targets_priority.parquet g8_rows.parquet --workdir /w/tmp > extract.log 2>&1
RC=\$?
echo "[G8X] exit status \$RC (124 = timeout)" >> extract.log
echo "extract exit \$RC"
date -u +%FT%TZ > end.txt
aws s3 cp g8_rows.parquet \$OUT/g8_rows.parquet --region $R --only-show-errors
aws s3 cp extract.log \$OUT/extract.log --region $R --only-show-errors
aws s3 cp start.txt \$OUT/start.txt --region $R --only-show-errors
aws s3 cp end.txt \$OUT/end.txt --region $R --only-show-errors
up
shutdown -h now
EOT
  SUB=$($A ec2 describe-subnets --region $R --filters Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
  ID=$($A ec2 run-instances --region $R --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
       --iam-instance-profile Name=$ROLE --instance-initiated-shutdown-behavior terminate \
       --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3,DeleteOnTermination=true}" \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=hl-costs1-g8x}]" \
       --user-data "file://$UD" --query 'Instances[0].InstanceId' --output text)
  rm -f "$UD"
  echo "launched $ID ($TYPE on-demand, $R) timer=${TIMER}min payload sha256 $SHA1 $SHA2"
  ;;
*) sed -n '2,9p' "$0"; exit 1 ;;
esac
