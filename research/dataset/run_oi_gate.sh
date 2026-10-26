#!/bin/bash
# HL-MASTER1 G7: pull the fills-based OI deltas, run the timestamp-lag check, then the gate with the L* it finds (stops if L* < 0 or the gate fails).
cd ~/Pair_Trading
L=research/dataset/logs
mkdir -p research/datasets/oi
aws s3 cp s3://pair-trading-hl-289869684922/build7/oifull/ research/datasets/oi/ --recursive --exclude '*' --include '*_oi.parquet' --region ap-northeast-1 --only-show-errors > $L/master_oi_pull.log 2>&1
du -sh research/datasets/oi >> $L/master_oi_pull.log; ls research/datasets/oi | wc -l >> $L/master_oi_pull.log
python -u research/dataset/master_oi.py lag > $L/master_oi_lag.log 2>&1 || { echo "lag stage stopped"; exit 3; }
LSTAR=$(grep -o 'L\* = -\?[0-9]*' $L/master_oi_lag.log | tail -1 | sed 's/L\* = //')
echo "L* = $LSTAR" > $L/master_oi_lstar.log
python -u research/dataset/master_oi.py gate $LSTAR > $L/master_oi_gate.log 2>&1
echo "gate exit $?" >> $L/master_oi_gate.log
python -u research/dataset/master_tests_g4.py > $L/master_tests_g4.log 2>&1
