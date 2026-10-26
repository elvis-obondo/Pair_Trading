#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
NPROC=8 python -u research/dataset/master_tests_g5.py > $L/master_tests_g5.log 2>&1
echo "chain9 done" > $L/master_chain9_done.log
