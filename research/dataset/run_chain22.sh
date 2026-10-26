#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
python -u research/dataset/master_drift_explain.py coin > $L/master_drift_explain_coin.log 2>&1
python -u research/dataset/master_drift_explain.py pair > $L/master_drift_explain_pair.log 2>&1
echo "chain22 done" > $L/master_chain22_done.log
