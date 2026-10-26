#!/bin/bash
# HL-FLOW1 Part 0 on pt-research: pull the d3 outputs, compare with the d2 ones, and only
# if every check passes replace flow/ and futures/. Count and bytes against S3 first.
set -euo pipefail
cd ~/Pair_Trading
B=s3://pair-trading-hl-289869684922/build2/d3/asm
rm -rf research/hyperliquid/flow_d3 user_data/data/hyperliquid/futures_d3
mkdir -p research/hyperliquid/flow_d3 user_data/data/hyperliquid/futures_d3
aws s3 cp $B/flow/ research/hyperliquid/flow_d3/ --recursive --only-show-errors
aws s3 cp $B/futures/ user_data/data/hyperliquid/futures_d3/ --recursive --only-show-errors
aws s3 cp $B/missing_minutes.parquet research/hyperliquid/missing_minutes.parquet --only-show-errors
echo "flow_d3 local: $(ls research/hyperliquid/flow_d3 | wc -l) files $(cat research/hyperliquid/flow_d3/* | wc -c) B"
echo "flow_d3 s3:    $(aws s3 ls $B/flow/ --recursive --summarize | grep Total | tr '\n' ' ')"
echo "futures_d3 local: $(ls user_data/data/hyperliquid/futures_d3 | wc -l) files $(cat user_data/data/hyperliquid/futures_d3/* | wc -c) B"
echo "futures_d3 s3:    $(aws s3 ls $B/futures/ --recursive --summarize | grep Total | tr '\n' ' ')"
python -u research/hyperliquid/build3_flow_compare.py research/hyperliquid/flow research/hyperliquid/flow_d3 \
    user_data/data/hyperliquid/futures user_data/data/hyperliquid/futures_d3
echo "COMPARE PASSED -> swapping"
rm -rf research/hyperliquid/flow user_data/data/hyperliquid/futures
mv research/hyperliquid/flow_d3 research/hyperliquid/flow
mv user_data/data/hyperliquid/futures_d3 user_data/data/hyperliquid/futures
echo "SWAP-DONE flow: $(ls research/hyperliquid/flow | wc -l) files; futures: $(ls user_data/data/hyperliquid/futures | wc -l) files"
