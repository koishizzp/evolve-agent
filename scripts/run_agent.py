#!/usr/bin/env python
"""CLI 入口。"""

from __future__ import annotations

import argparse

from evolve_agent import EvolveAgent
from evolve_agent.utils import setup_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evolve-agent")
    parser.add_argument("--fasta", required=True, help="输入 FASTA 文件路径")
    parser.add_argument("--task", required=True, help="自然语言任务描述")
    parser.add_argument("--activity-csv", default=None, help="已有活性数据 CSV 路径")
    parser.add_argument("--output-dir", default="./outputs", help="输出目录")
    parser.add_argument("--verbose", action="store_true", help="详细日志模式")
    args = parser.parse_args()

    setup_logger(verbose=args.verbose)
    agent = EvolveAgent(config_path="config/config.yaml")
    agent.config["output_dir"] = args.output_dir

    summary = agent.run(
        user_input=args.task,
        fasta_path=args.fasta,
        activity_csv_path=args.activity_csv,
    )
    print("\n=== evolve-agent summary ===")
    print(summary)


if __name__ == "__main__":
    main()
