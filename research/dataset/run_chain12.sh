#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
rm -f research/datasets/master/work/g6_tmp/g6_2*.npz        # chunks of the 26-column build: replaced, not reused
NPROC=7 python -u research/dataset/master_g6_run.py > $L/master_g6.log 2>&1
NPROC=7 python -u research/dataset/master_tests_g6.py > $L/master_tests_g6.log 2>&1
echo "chain12 done" > $L/master_chain12_done.log
