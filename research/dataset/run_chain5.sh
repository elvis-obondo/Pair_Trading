#!/bin/bash
# HL-MASTER1: G9a (with _seg), OI level, funding check, G7, G5 and their tests, in one chain on pt-research (nothing is synced while it runs).
cd ~/Pair_Trading
L=research/dataset/logs
mkdir -p research/datasets/fundinghist research/datasets/oi
aws s3 cp s3://pair-trading-hl-289869684922/fundinghist/ research/datasets/fundinghist/ --recursive --region ap-northeast-1 --only-show-errors > $L/master_chain5_pull.log 2>&1
aws s3 cp s3://pair-trading-hl-289869684922/build7/oifull/ research/datasets/oi/ --recursive --exclude '*' --include '*_vault.parquet' --region ap-northeast-1 --only-show-errors >> $L/master_chain5_pull.log 2>&1
ls research/datasets/fundinghist | wc -l >> $L/master_chain5_pull.log
python -u research/dataset/master_g9a.py > $L/master_g9a.log 2>&1
python -u research/dataset/master_tests_g9a.py > $L/master_tests_g9a.log 2>&1
python -u research/dataset/master_oi.py level 0 > $L/master_oi_level.log 2>&1
python -u research/dataset/master_funding_check.py > $L/master_funding_check.log 2>&1
python -u research/dataset/master_g7.py > $L/master_g7.log 2>&1
python -u research/dataset/master_tests_g7.py > $L/master_tests_g7.log 2>&1
NPROC=6 python -u research/dataset/master_g5_run.py > $L/master_g5.log 2>&1
NPROC=8 python -u research/dataset/master_tests_g5.py > $L/master_tests_g5.log 2>&1
echo "chain5 done" > $L/master_chain5_done.log
