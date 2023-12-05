#!/bin/bash
set -euo pipefail

# this will return an exit status of 124 or 128 if the benchmark times out
timeout --kill-after=1s 1s cargo criterion --message-format=json 1>bench_results.json