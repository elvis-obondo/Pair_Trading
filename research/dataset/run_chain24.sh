#!/bin/bash
cd ~/Pair_Trading
L=research/dataset/logs
LOCK=/tmp/run_chain24.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "run_chain24.sh already running (lock held): refusing a second launch" >&2
  exit 1
fi
NPROC=7 python -u research/dataset/master_partz.py pair > $L/master_partz_pair.log 2>&1
NPROC=7 python -u research/dataset/master_partz.py coin > $L/master_partz_coin.log 2>&1
echo "chain24 done" > $L/master_chain24_done.log
