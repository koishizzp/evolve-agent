from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from evolve_agent.utils.logger import logger

from .base_tool import BaseTool


class EvolveProTool(BaseTool):
    """EvolvePro wrapper with config-driven command execution."""

    name = "evolvepro"
    description = "Few-shot active-learning workflow for protein engineering."

    def __init__(self, config: dict):
        super().__init__(config)
        evolvepro = config.get("evolvepro", {})
        self.root = Path(config["evolvepro_root"]).expanduser() if config.get("evolvepro_root") else Path(".")
        self.tmp_dir = self.ensure_dir(config["tmp_dir"])
        self.result_dir = self.ensure_dir(config["result_dir"])
        self.conda_env = str(evolvepro.get("conda_env") or "evolvepro")
        self.embedding_env = str(config.get("multievolve", {}).get("conda_env") or self.conda_env)
        self.timeout_seconds = int(evolvepro.get("timeout_seconds") or 7200)
        self.command_template = [str(item) for item in evolvepro.get("command", []) if str(item).strip()]
        self.output_filename = str(evolvepro.get("output_filename") or "evolvepro_recommendations.csv")

    def _run_cmd(self, cmd: list[str], step_name: str) -> subprocess.CompletedProcess:
        logger.info("[EvolvePro] %s: %s", step_name, self.command_text(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_seconds)
        logger.debug(result.stdout)
        if result.returncode != 0:
            logger.error(result.stderr)
            raise RuntimeError(f"{step_name} failed: {result.stderr.strip()}")
        return result

    def _preview_csv(self, csv_path: Path, rows: int = 5) -> str:
        with csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            selected = []
            for idx, row in enumerate(reader):
                if idx >= rows:
                    break
                selected.append(str(row))
        return "\n".join(selected)

    def run(self, input_data: dict) -> dict:
        fasta_path = input_data["fasta_path"]
        activity_csv = input_data.get("activity_csv_path")
        task = input_data.get("task", "")
        params = dict(input_data.get("params") or {})
        output_dir = self.ensure_dir(input_data.get("result_dir") or self.result_dir)
        result_csv = output_dir / self.output_filename

        template_values = {
            "root": str(self.root),
            "fasta_path": fasta_path,
            "activity_csv_path": activity_csv or "",
            "task": task,
            "output_dir": str(output_dir),
            "result_dir": str(output_dir),
            "output_csv": str(result_csv),
            "tmp_dir": str(self.tmp_dir),
            **params,
        }

        if not activity_csv:
            return {
                "success": False,
                "output": "",
                "error": "EvolvePro requires activity_csv_path for few-shot active learning.",
                "result_files": [],
            }

        try:
            commands: list[list[str]] = []
            if self.command_template:
                commands.append(self.format_command(self.command_template, template_values))
            else:
                process_script = self.root / "scripts" / "process" / "process_data.py"
                embedding_script = self.root / "scripts" / "plm" / "extract_embeddings.py"
                run_script = self.root / "scripts" / "exp" / "run_evolvepro.py"
                if not all(path.exists() for path in (process_script, embedding_script, run_script)):
                    raise RuntimeError(
                        "Unable to infer EvolvePro entrypoint. "
                        "Set evolvepro.command in config/config.yaml or EVOLVE_AGENT_EVOLVEPRO_COMMAND_JSON."
                    )

                process_out = self.tmp_dir / "evolvepro_processed.csv"
                embedding_out = self.tmp_dir / "evolvepro_embeddings.npy"
                commands.extend(
                    [
                        [
                            "conda",
                            "run",
                            "-n",
                            self.conda_env,
                            "python",
                            str(process_script),
                            "--fasta",
                            fasta_path,
                            "--activity-csv",
                            activity_csv,
                            "--output",
                            str(process_out),
                        ],
                        [
                            "conda",
                            "run",
                            "-n",
                            self.embedding_env,
                            "python",
                            str(embedding_script),
                            "--input",
                            str(process_out),
                            "--output",
                            str(embedding_out),
                        ],
                        [
                            "conda",
                            "run",
                            "-n",
                            self.conda_env,
                            "python",
                            str(run_script),
                            "--processed-csv",
                            str(process_out),
                            "--embeddings",
                            str(embedding_out),
                            "--output",
                            str(result_csv),
                        ],
                    ]
                )

            last_stdout = ""
            for index, command in enumerate(commands, start=1):
                last_stdout = self._run_cmd(command, f"Step{index}").stdout

            if not result_csv.exists():
                raise RuntimeError(f"EvolvePro finished without producing expected output: {result_csv}")

            preview = self._preview_csv(result_csv)
            return {
                "success": True,
                "output": f"EvolvePro finished. Top predictions:\n{preview}",
                "error": "",
                "result_files": [str(result_csv)],
                "command": [self.command_text(item) for item in commands],
                "stdout": last_stdout,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("EvolvePro execution failed")
            return {
                "success": False,
                "output": "",
                "error": (
                    f"EvolvePro execution failed: {exc}. "
                    "Check the conda environment, script paths, and evolvepro.command override."
                ),
                "result_files": [],
            }
