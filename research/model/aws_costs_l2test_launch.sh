#!/bin/bash
# COSTS1 validation pull: the raw 20-level books of the 32 test files (20 fixed + 12 least-liquid rule; research/model/diagnostics/costs_l2_test_targets.py list) on ONE small EC2 in us-east-2
# (the archive is in us-east-1, requester-pays; EC2 is denied in us-east-1 by the account's SCP), then merge, then upload to our bucket and shut down (= terminate).
#
#   research/model/aws_costs_l2test_launch.sh stage    # uploads build9_l2_books.py and l2_targets_test20.parquet to s3://.../costs1/code/ (needs the user's yes)
#   research/model/aws_costs_l2test_launch.sh launch   # runs the instance (needs the user's yes for THIS launch)
# Guards: `shutdown -h +TIMER` first; python under `timeout 900`; the extractor's own caps --max-bytes 200 MB and --max-seconds 600; payload sha256 re-checked on the machine.
# Output: s3://pair-trading-hl-<acct>/costs1/l2test/{books_all.parquet, books_*.parquet, index_*.parquet, merge.log, run.log, ec2.log, start.txt, end.txt}.
# Cost: 32 files x about 0.1 to 0.5 MB (about 16 MB) cross-region from us-east-1 at about $0.02 per GB, plus a c7g.large on-demand for well under an hour (about $0.07 per hour).
set -euo pipefail
A="$HOME/.local/bin/aws --cli-read-timeout 60 --cli-connect-timeout 20"
R=us-east-2
BR=ap-northeast-1
ACCT=289869684922
BKT=pair-trading-hl-$ACCT
ROLE=hl-build2-ec2
TYPE=${TYPE:-c7g.large}
TIMER=${TIMER:-30}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAY1="$HERE/../hyperliquid/build9_l2_books.py"
PAY2="$HERE/logs/costs1/l2_targets_test20.parquet"
SHA1=$(shasum -a 256 "$PAY1" | cut -d' ' -f1)
SHA2=$(shasum -a 256 "$PAY2" | cut -d' ' -f1)
case "${1:-}" in
stage)
  $A s3 cp "$PAY1" s3://$BKT/costs1/code/build9_l2_books.py --region $BR --only-show-errors
  $A s3 cp "$PAY2" s3://$BKT/costs1/code/l2_targets_test20.parquet --region $BR --only-show-errors
  echo "staged: build9_l2_books.py sha256 $SHA1; l2_targets_test20.parquet sha256 $SHA2"
  ;;
launch)
  AMI=$($A ssm get-parameter --region $R --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --query Parameter.Value --output text)
  UD=$(mktemp)
  cat > "$UD" <<EOT
#!/bin/bash
shutdown -h +$TIMER
exec > /var/log/l2test.log 2>&1
set -x
OUT=s3://$BKT/costs1/l2test
up() { aws s3 cp /var/log/l2test.log \$OUT/ec2.log --region $BR --only-show-errors || true; }
trap up EXIT
dnf install -y -q lz4 python3.11 python3.11-pip
python3.11 -m pip install -q orjson pandas pyarrow numpy boto3
mkdir -p /w && cd /w
aws s3 cp s3://$BKT/costs1/code/build9_l2_books.py . --region $BR --only-show-errors
aws s3 cp s3://$BKT/costs1/code/l2_targets_test20.parquet . --region $BR --only-show-errors
echo "$SHA1  build9_l2_books.py" | sha256sum -c - || { echo "SHA MISMATCH build9_l2_books.py"; shutdown -h now; exit 1; }
echo "$SHA2  l2_targets_test20.parquet" | sha256sum -c - || { echo "SHA MISMATCH targets"; shutdown -h now; exit 1; }
export AWS_DEFAULT_REGION=$R
date -u +%FT%TZ > start.txt
timeout 900 python3.11 -u build9_l2_books.py l2_targets_test20.parquet out --workers 2 --max-bytes 200000000 --max-seconds 600 > run.log 2>&1
RC=\$?
echo "[B9] exit status \$RC (124 = timeout)" >> run.log
python3.11 -u build9_l2_books.py --merge out > merge.log 2>&1 || echo "[B9] merge failed" >> merge.log
date -u +%FT%TZ > end.txt
aws s3 cp out \$OUT/ --recursive --region $BR --only-show-errors
for f in run.log merge.log start.txt end.txt; do aws s3 cp \$f \$OUT/\$f --region $BR --only-show-errors; done
up
shutdown -h now
EOT
  SUB=$($A ec2 describe-subnets --region $R --filters Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
  ID=$($A ec2 run-instances --region $R --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
       --iam-instance-profile Name=$ROLE --instance-initiated-shutdown-behavior terminate \
       --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3,DeleteOnTermination=true}" \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=hl-costs1-l2test}]" \
       --user-data "file://$UD" --query 'Instances[0].InstanceId' --output text)
  rm -f "$UD"
  echo "launched $ID ($TYPE on-demand, $R) timer=${TIMER}min payload sha256 $SHA1 $SHA2"
  ;;
*) sed -n '2,9p' "$0"; exit 1 ;;
esac
