#!/usr/bin/env bash

python main.py run \
  examples/example_input.fasta \
  --task "优化这个蛋白的活性，优先考虑冷启动探索" \
  --json-out results/example_run.json
