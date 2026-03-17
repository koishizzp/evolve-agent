"""EvolvePro 工具封装。"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from .base_tool import BaseTool
from evolve_agent.utils.logger import logger


class EvolveProTool(BaseTool):
    """适用于 few-shot 主动学习场景，
    需要少量实验活性数据（每轮 10-16 个变体），迭代优化单一或多属性蛋白质活性。"""

    name = "evolvepro"
    description = (
        "适用于 few-shot 主动学习场景，需要少量实验活性数据（每轮 10-16 个变体），"
        "迭代优化单一或多属性蛋白质活性。"
    )

    def __init__(self, config: dict):
        self.config = config
        self.root = Path(config["evolvepro_path"]).expanduser()
        self.tmp_dir = Path(config["tmp_dir"]).expanduser()
        self.output_dir = Path(config["output_dir"]).expanduser()
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _run_cmd(self, cmd: list[str], step_name: str) -> subprocess.CompletedProcess:
        """执行子命令并记录日志。"""
        logger.info(f"[EvolvePro] {step_name}: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        logger.debug(result.stdout)
        if result.returncode != 0:
            logger.error(result.stderr)
            raise RuntimeError(f"{step_name} failed: {result.stderr.strip()}")
        return result

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
        activity_csv = input_data.get("activity_csv_path")

        if not activity_csv:
            return {
                "success": False,
                "output": "",
                "error": "EvolvePro requires activity_csv_path for few-shot active learning.",
                "result_files": [],
            }

        try:
            # Step 1 - Process: 预处理 FASTA 与活性数据
            process_out = self.tmp_dir / "evolvepro_processed.csv"
            process_cmd = [
                "conda",
                "run",
                "-n",
                self.config["conda_env_evolvepro"],
                "python",
                str(self.root / "scripts" / "process" / "process_data.py"),
                "--fasta",
                fasta_path,
                "--activity-csv",
                activity_csv,
                "--output",
                str(process_out),
            ]
            self._run_cmd(process_cmd, "Step1 Process")

            # Step 2 - PLM Embedding: 提取 embedding（该步骤非常耗时）
            print("[EvolvePro] Step2 PLM Embedding started... this may take a long time.")
            logger.info("[EvolvePro] Step2 PLM Embedding started... this may take a long time.")
            embedding_out = self.tmp_dir / "evolvepro_embeddings.npy"
            embedding_cmd = [
                "conda",
                "run",
                "-n",
                self.config["conda_env_plm"],
                "python",
                str(self.root / "scripts" / "plm" / "extract_embeddings.py"),
                "--input",
                str(process_out),
                "--output",
                str(embedding_out),
            ]
            self._run_cmd(embedding_cmd, "Step2 PLM Embedding")

            # Step 3 - Run EVOLVEpro: 执行主模型
            result_csv = self.output_dir / "evolvepro_recommendations.csv"
            run_cmd = [
                "conda",
                "run",
                "-n",
                self.config["conda_env_evolvepro"],
                "python",
                str(self.root / "scripts" / "exp" / "run_evolvepro.py"),
                "--processed-csv",
                str(process_out),
                "--embeddings",
                str(embedding_out),
                "--output",
                str(result_csv),
            ]
            self._run_cmd(run_cmd, "Step3 Run EVOLVEpro")

            # Step 4 - 解析输出 CSV
            preview = self._preview_csv(result_csv)
            return {
                "success": True,
                "output": f"EvolvePro finished. Top predictions:\n{preview}",
                "error": "",
                "result_files": [str(result_csv)],
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("EvolvePro execution failed")
            return {
                "success": False,
                "output": "",
                "error": (
                    f"EvolvePro 执行失败: {exc}. "
                    "请检查 conda 环境、脚本路径、输入 CSV/FASTA 格式是否正确。"
                ),
                "result_files": [],
            }
