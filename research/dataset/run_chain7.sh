#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
python -u research/dataset/master_tests_g7.py > $L/master_tests_g7.log 2>&1
NPROC=8 python -u research/dataset/master_tests_g5.py > $L/master_tests_g5.log 2>&1
echo "chain7 done" > $L/master_chain7_done.log
