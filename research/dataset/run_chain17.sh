#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
python -u research/dataset/master_coin_rewalk.py > $L/master_coin_rewalk.log 2>&1
STORED=1 python -u research/dataset/master_coin_rewalk.py > $L/master_coin_rewalk_stored.log 2>&1
echo "chain17 done" > $L/master_chain17_done.log
