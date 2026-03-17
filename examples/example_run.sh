#!/usr/bin/env bash
python scripts/run_agent.py \
  --fasta examples/example_input.fasta \
  --task "优化这个蛋白的酶活性，优先考虑冷启动探索" \
  --verbose
