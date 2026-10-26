#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
NPROC=7 python -u research/dataset/master_tests_g6.py --indep-only > $L/master_tests_g6_indep2000.log 2>&1
echo "chain15 done" > $L/master_chain15_done.log
