"""MULTI-evolve 工具封装。"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from .base_tool import BaseTool
from evolve_agent.utils.logger import logger


class MultiEvolveTool(BaseTool):
    """适用于一轮 ML 引导的多突变体工程，结合蛋白语言模型和上位性建模，
    预测协同突变组合，适合无或少量实验数据的初始探索阶段。"""

    name = "multievolve"
    description = (
        "适用于一轮 ML 引导的多突变体工程，结合蛋白语言模型和上位性建模，"
        "预测协同突变组合，适合无或少量实验数据的初始探索阶段。"
    )

    def __init__(self, config: dict):
        self.config = config
        self.root = Path(config["multievolve_path"]).expanduser()
        self.output_dir = Path(config["output_dir"]).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _preview_csv(self, csv_path: Path, rows: int = 5) -> str:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            selected = []
            for idx, row in enumerate(reader):
                if idx >= rows:
                    break
                selected.append(str(row))
        return "\n".join(selected)

    def run(self, input_data: dict) -> dict:
        fasta_path = input_data["fasta_path"]
        result_csv = self.output_dir / "multievolve_recommendations.csv"

        # TODO: 请根据服务器实际安装方式替换下面命令。
        # 例如：python /path/to/MULTI-evolve/main.py --fasta ... --output ...
        cmd = [
            "conda",
            "run",
            "-n",
            self.config["conda_env_plm"],
            "python",
            str(self.root / "run_multievolve.py"),
            "--fasta",
            fasta_path,
            "--output",
            str(result_csv),
        ]

        try:
            logger.info(f"[MULTI-evolve] Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.debug(result.stdout)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())

            preview = self._preview_csv(result_csv)
            return {
                "success": True,
                "output": f"MULTI-evolve finished. Top predictions:\n{preview}",
                "error": "",
                "result_files": [str(result_csv)],
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("MULTI-evolve execution failed")
            return {
                "success": False,
                "output": "",
                "error": (
                    f"MULTI-evolve 执行失败: {exc}. "
                    "请检查 CLI 命令参数、conda 环境、模型权重与输入 FASTA。"
                ),
                "result_files": [],
            }
