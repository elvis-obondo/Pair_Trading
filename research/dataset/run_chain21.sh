#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
python -u research/dataset/master_drift_explain.py coin > $L/master_drift_explain_coin.log 2>&1
python -u research/dataset/master_drift_explain.py pair > $L/master_drift_explain_pair.log 2>&1
NPROC=7 python -u research/dataset/master_tests_g8.py > $L/master_tests_g8.log 2>&1
echo "chain21 done" > $L/master_chain21_done.log
