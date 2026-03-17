from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from evolve_agent.utils import read_fasta
from evolve_agent.utils.logger import logger

from .base_tool import BaseTool


class MultiEvolveTool(BaseTool):
    """MULTI-evolve wrapper with sane defaults for p1/p2 workflows."""

    name = "multievolve"
    description = "Single-round ML-guided multi-mutant proposal workflow."

    def __init__(self, config: dict):
        super().__init__(config)
        section = config.get("multievolve", {})
        self.root = Path(config["multievolve_root"]).expanduser() if config.get("multievolve_root") else Path(".")
        self.model_dir = (
            Path(config["multievolve_model_dir"]).expanduser()
            if config.get("multievolve_model_dir")
            else None
        )
        self.tmp_dir = self.ensure_dir(config["tmp_dir"])
        self.result_dir = self.ensure_dir(config["result_dir"])
        self.conda_env = str(section.get("conda_env") or "plm")
        self.timeout_seconds = int(section.get("timeout_seconds") or 7200)
        self.train_command_template = [str(item) for item in section.get("train_command", []) if str(item).strip()]
        self.propose_command_template = [str(item) for item in section.get("propose_command", []) if str(item).strip()]
        self.output_filename = str(section.get("output_filename") or "multievolve_recommendations.csv")
        self.default_checkpoint_path = section.get("checkpoint_path")
        self.default_protein_name = section.get("protein_name")
        self.default_residues_to_mutate = section.get("residues_to_mutate")
        self.default_num_mutations = int(section.get("number_mutations_per_variant") or 4)
        self.default_num_samples = int(section.get("num_samples") or 64)

    def _preview_csv(self, csv_path: Path, rows: int = 5) -> str:
        with csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            selected = []
            for idx, row in enumerate(reader):
                if idx >= rows:
                    break
                selected.append(str(row))
        return "\n".join(selected)

    def _run_cmd(self, command: list[str], step_name: str) -> subprocess.CompletedProcess:
        logger.info("[MULTI-evolve] %s: %s", step_name, self.command_text(command))
        result = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds)
        logger.debug(result.stdout)
        if result.returncode != 0:
            logger.error(result.stderr)
            raise RuntimeError(f"{step_name} failed: {result.stderr.strip()}")
        return result

    def run(self, input_data: dict) -> dict:
        fasta_path = input_data["fasta_path"]
        activity_csv = input_data.get("activity_csv_path")
        params = dict(input_data.get("params") or {})
        fasta_record = read_fasta(fasta_path)
        protein_name = str(params.get("protein_name") or self.default_protein_name or fasta_record["id"] or "protein")
        residues_to_mutate = params.get("residues_to_mutate") or self.default_residues_to_mutate
        num_mutations = int(params.get("number_mutations_per_variant") or self.default_num_mutations)
        num_samples = int(params.get("num_samples") or self.default_num_samples)
        output_dir = self.ensure_dir(input_data.get("result_dir") or self.result_dir)
        result_csv = output_dir / self.output_filename
        checkpoint_path = params.get("checkpoint_path") or self.default_checkpoint_path

        template_values = {
            "root": str(self.root),
            "fasta_path": fasta_path,
            "activity_csv_path": activity_csv or "",
            "protein_name": protein_name,
            "protein_sequence": fasta_record["sequence"],
            "residues_to_mutate": residues_to_mutate or "",
            "number_mutations_per_variant": num_mutations,
            "num_samples": num_samples,
            "output_dir": str(output_dir),
            "result_dir": str(output_dir),
            "output_csv": str(result_csv),
            "checkpoint_path": checkpoint_path or "",
            "llm_model_path": str(self.model_dir) if self.model_dir else "",
            "tmp_dir": str(self.tmp_dir),
            **params,
        }

        try:
            commands: list[list[str]] = []
            command_texts: list[str] = []

            if self.train_command_template and activity_csv:
                commands.append(self.format_command(self.train_command_template, template_values))

            if self.propose_command_template:
                commands.append(self.format_command(self.propose_command_template, template_values))
            else:
                train_script = self.root / "p1_train.py"
                propose_script = self.root / "p2_propose.py"

                if activity_csv and train_script.exists():
                    if not self.model_dir:
                        raise RuntimeError(
                            "MULTI-evolve training requires multievolve_model_dir / EVOLVE_AGENT_MULTIEVOLVE_MODEL_DIR."
                        )
                    checkpoint_dir = output_dir / "multievolve_checkpoint"
                    checkpoint_dir.mkdir(parents=True, exist_ok=True)
                    checkpoint_path = str(checkpoint_dir)
                    template_values["checkpoint_path"] = checkpoint_path
                    commands.append(
                        [
                            "conda",
                            "run",
                            "-n",
                            self.conda_env,
                            "python",
                            str(train_script),
                            "--data_path",
                            activity_csv,
                            "--model_path",
                            str(self.model_dir),
                            "--protein_name",
                            protein_name,
                            "--number_mutations_per_variant",
                            str(num_mutations),
                            "--save_checkpoint_path",
                            checkpoint_path,
                        ]
                    )

                if propose_script.exists():
                    if not checkpoint_path:
                        raise RuntimeError(
                            "MULTI-evolve needs either activity_csv_path to train a checkpoint "
                            "or multievolve.checkpoint_path / EVOLVE_AGENT_MULTIEVOLVE_CHECKPOINT_PATH."
                        )
                    if not self.model_dir:
                        raise RuntimeError(
                            "MULTI-evolve requires multievolve_model_dir / EVOLVE_AGENT_MULTIEVOLVE_MODEL_DIR."
                        )
                    propose_cmd = [
                        "conda",
                        "run",
                        "-n",
                        self.conda_env,
                        "python",
                        str(propose_script),
                        "--checkpoint_path",
                        str(checkpoint_path),
                        "--llm_model_path",
                        str(self.model_dir),
                        "--protein_sequence",
                        fasta_record["sequence"],
                        "--protein_name",
                        protein_name,
                        "--number_of_mutations_per_variant",
                        str(num_mutations),
                        "--num_samples",
                        str(num_samples),
                        "--output_path",
                        str(result_csv),
                    ]
                    if residues_to_mutate:
                        propose_cmd.extend(["--residues_to_mutate", str(residues_to_mutate)])
                    commands.append(propose_cmd)
                else:
                    legacy_script = self.root / "run_multievolve.py"
                    if not legacy_script.exists():
                        raise RuntimeError(
                            "Unable to infer MULTI-evolve entrypoint. "
                            "Set multievolve.propose_command in config/config.yaml or EVOLVE_AGENT_MULTIEVOLVE_PROPOSE_COMMAND_JSON."
                        )
                    commands.append(
                        [
                            "conda",
                            "run",
                            "-n",
                            self.conda_env,
                            "python",
                            str(legacy_script),
                            "--fasta",
                            fasta_path,
                            "--output",
                            str(result_csv),
                        ]
                    )

            last_stdout = ""
            for index, command in enumerate(commands, start=1):
                command_texts.append(self.command_text(command))
                last_stdout = self._run_cmd(command, f"Step{index}").stdout

            if not result_csv.exists():
                raise RuntimeError(f"MULTI-evolve finished without producing expected output: {result_csv}")

            preview = self._preview_csv(result_csv)
            return {
                "success": True,
                "output": f"MULTI-evolve finished. Top predictions:\n{preview}",
                "error": "",
                "result_files": [str(result_csv)],
                "command": command_texts,
                "stdout": last_stdout,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("MULTI-evolve execution failed")
            return {
                "success": False,
                "output": "",
                "error": (
                    f"MULTI-evolve execution failed: {exc}. "
                    "Check checkpoint_path, model dir, conda env, and multievolve.propose_command override."
                ),
                "result_files": [],
            }
