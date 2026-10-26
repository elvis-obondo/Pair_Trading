#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
NPROC=7 python -u research/dataset/master_g6_run.py > $L/master_g6.log 2>&1
NPROC=7 python -u research/dataset/master_tests_g6.py > $L/master_tests_g6.log 2>&1
python -u research/dataset/master_funding_check.py > $L/master_funding_check.log 2>&1
NPROC=8 python -u research/dataset/master_tests_g5.py > $L/master_tests_g5.log 2>&1
echo "chain11 done" > $L/master_chain11_done.log
