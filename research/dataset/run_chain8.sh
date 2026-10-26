#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
NPROC=6 python -u research/dataset/master_g5_run.py > $L/master_g5.log 2>&1
NPROC=8 python -u research/dataset/master_tests_g5.py > $L/master_tests_g5.log 2>&1
python -u research/dataset/master_tests_g7.py --fund-only > $L/master_tests_g7_fund.log 2>&1
echo "chain8 done" > $L/master_chain8_done.log
