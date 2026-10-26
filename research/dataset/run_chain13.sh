#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
NPROC=7 python -u research/dataset/master_tests_g6.py --poison-only > $L/master_tests_g6_poison.log 2>&1
echo "chain13 done" > $L/master_chain13_done.log
