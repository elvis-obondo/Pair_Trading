#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
GAPS=1 python -u research/dataset/master_coin_rewalk.py > $L/master_coin_gaps.log 2>&1
echo "chain20 done" > $L/master_chain20_done.log
