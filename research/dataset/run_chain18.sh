#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
mkdir -p research/datasets/l2
aws s3 sync s3://pair-trading-hl-289869684922/build8/full/ research/datasets/l2/ --region ap-northeast-1 --only-show-errors > $L/l2sync.log 2>&1
echo "synced $(ls research/datasets/l2/*_l2.parquet | wc -l) day tables, $(ls research/datasets/l2/*_l2_index.parquet | wc -l) index files" >> $L/l2sync.log
# the extractor's per-day duplicate / outside-day counts (the stdout files) in one log
grep -h "duplicate (coin, minute)" research/datasets/l2/*.stdout > $L/build8_l2_full_dups.log 2>&1
NPROC=7 python -u research/dataset/master_g8_run.py > $L/master_g8.log 2>&1
NPROC=7 python -u research/dataset/master_tests_g8.py > $L/master_tests_g8.log 2>&1
NPROC=7 python -u research/dataset/master_colreport.py coin > $L/master_colreport_coin.log 2>&1
NPROC=7 python -u research/dataset/master_colreport.py pair > $L/master_colreport_pair.log 2>&1
NPROC=7 python -u research/dataset/master_seams.py coin > $L/master_seams_coin.log 2>&1
NPROC=7 python -u research/dataset/master_seams.py pair > $L/master_seams_pair.log 2>&1
python -u research/dataset/master_release_checks.py > $L/master_release_checks.log 2>&1
python -u research/dataset/master_known.py > $L/master_known.log 2>&1
python -u research/dataset/master_eyeball.py > $L/master_eyeball.log 2>&1
echo "chain18 done" > $L/master_chain18_done.log
