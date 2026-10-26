#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
NPROC=7 python -u research/dataset/master_tests_g6.py --poison-only > $L/master_tests_g6_poison.log 2>&1
python -u research/dataset/master_tests_g3.py > $L/master_tests_g3.log 2>&1
python -u research/dataset/master_tests_g2b.py > $L/master_tests_g2b.log 2>&1
echo "chain14 done" > $L/master_chain14_done.log
