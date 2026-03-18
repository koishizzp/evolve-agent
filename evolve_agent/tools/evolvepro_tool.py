from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from typing import Any

from evolve_agent.utils import read_fasta
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
        self.default_process_script = self._clean_optional(evolvepro.get("process_script"))
        self.default_plm_script = self._clean_optional(
            evolvepro.get("plm_script") or evolvepro.get("embedding_script")
        )
        self.default_exp_script = self._clean_optional(evolvepro.get("exp_script"))
        self.default_result_glob = self._clean_optional(evolvepro.get("result_glob"))
        self.shell_executable = str(evolvepro.get("shell_executable") or "bash")
        params_section = evolvepro.get("params", {})
        self.default_params = dict(params_section) if isinstance(params_section, dict) else {}

    @staticmethod
    def _clean_optional(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

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

    def _resolve_repo_path(self, value: str | None) -> Path | None:
        if not value:
            return None
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
        return self.root / candidate

    @staticmethod
    def _script_supports_cli_args(script_path: Path) -> bool:
        try:
            content = script_path.read_text(encoding="utf-8")
        except OSError:
            return True
        lowered = content.lower()
        return any(token in lowered for token in ("argparse", "sys.argv", "click", "typer"))

    def _resolve_first_existing(self, candidates: list[str | None]) -> Path | None:
        for candidate in candidates:
            path = self._resolve_repo_path(candidate)
            if path and path.exists():
                return path
        return None

    def _resolve_result_path(self, value: str | None, output_dir: Path) -> Path | None:
        if not value:
            return None
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
        if candidate.parts and candidate.parts[0] in {"results", "result", "tmp", "data"}:
            return self.root / candidate
        return output_dir / candidate

    def _normalize_key(self, value: str | None) -> str:
        raw = self._clean_optional(value)
        if not raw:
            return ""
        return raw.lower().replace("-", "_").replace(" ", "_")

    def _command_for_script(self, script_path: Path, *, env_name: str) -> list[str]:
        suffix = script_path.suffix.lower()
        if suffix == ".py":
            return ["conda", "run", "-n", env_name, "python", str(script_path)]
        if suffix == ".sh":
            return ["conda", "run", "-n", env_name, self.shell_executable, str(script_path)]
        return ["conda", "run", "-n", env_name, str(script_path)]

    def _legacy_commands(self, *, fasta_path: str, activity_csv: str, result_csv: Path) -> list[list[str]] | None:
        process_script = self.root / "scripts" / "process" / "process_data.py"
        embedding_script = self.root / "scripts" / "plm" / "extract_embeddings.py"
        run_script = self.root / "scripts" / "exp" / "run_evolvepro.py"
        if not all(path.exists() for path in (process_script, embedding_script, run_script)):
            return None

        process_out = self.tmp_dir / "evolvepro_processed.csv"
        embedding_out = self.tmp_dir / "evolvepro_embeddings.npy"
        return [
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

    def _official_layout_detected(self) -> bool:
        scripts_root = self.root / "scripts"
        return (
            (scripts_root / "process" / "exp_process.py").exists()
            or (scripts_root / "process" / "dms_process.py").exists()
            or (scripts_root / "exp").exists()
            or (scripts_root / "plm").exists()
        )

    def _resolve_official_plm_script(self, params: dict[str, Any], embeddings_type: str | None) -> Path | None:
        explicit = self._clean_optional(params.get("plm_script") or params.get("embedding_script")) or self.default_plm_script
        if explicit:
            return self._resolve_repo_path(explicit)
        if not embeddings_type:
            return None
        normalized = self._normalize_key(embeddings_type)
        plm_dir = self.root / "scripts" / "plm"
        if not plm_dir.exists():
            return None
        preferred = [
            plm_dir / f"{embeddings_type}_exp.sh",
            plm_dir / f"{normalized}_exp.sh",
            plm_dir / f"{embeddings_type}.sh",
            plm_dir / f"{normalized}.sh",
        ]
        for candidate in preferred:
            if candidate.exists():
                return candidate
        return None

    def _resolve_official_exp_script(self, params: dict[str, Any], system_name: str | None) -> Path | None:
        explicit = self._clean_optional(params.get("exp_script")) or self.default_exp_script
        if explicit:
            return self._resolve_repo_path(explicit)
        if not system_name:
            return None
        exp_dir = self.root / "scripts" / "exp"
        if not exp_dir.exists():
            return None
        normalized = self._normalize_key(system_name)
        preferred = [
            exp_dir / f"{system_name}.py",
            exp_dir / f"{normalized}.py",
        ]
        for candidate in preferred:
            if candidate.exists():
                return candidate
        return None

    def _result_snapshot(self) -> dict[Path, float]:
        snapshots: dict[Path, float] = {}
        search_roots = [self.result_dir, self.root / "results", self.root / "output"]
        for search_root in search_roots:
            if not search_root.exists():
                continue
            for path in search_root.rglob("*.csv"):
                try:
                    snapshots[path.resolve()] = path.stat().st_mtime
                except OSError:
                    continue
        return snapshots

    def _discover_result(
        self,
        *,
        explicit_path: Path | None,
        output_dir: Path,
        before_snapshot: dict[Path, float] | None,
        result_glob: str | None,
    ) -> Path | None:
        if explicit_path and explicit_path.exists():
            return explicit_path

        candidates: list[Path] = []
        if result_glob:
            for path in self.root.glob(result_glob):
                if path.is_file() and path.suffix.lower() == ".csv":
                    candidates.append(path.resolve())

        if output_dir.exists():
            candidates.extend(path.resolve() for path in output_dir.glob("*.csv") if path.is_file())

        if result_glob or before_snapshot is not None:
            for search_root in (self.result_dir, self.root / "results", self.root / "output"):
                if search_root.exists():
                    candidates.extend(path.resolve() for path in search_root.rglob("*.csv") if path.is_file())

        unique_candidates = list(dict.fromkeys(candidates))
        if not unique_candidates:
            return None

        if before_snapshot is not None:
            changed = []
            for path in unique_candidates:
                try:
                    modified = path.stat().st_mtime
                except OSError:
                    continue
                previous = before_snapshot.get(path)
                if previous is None or modified > previous:
                    changed.append(path)
            if changed:
                unique_candidates = changed

        return max(unique_candidates, key=lambda path: path.stat().st_mtime)

    def _build_official_commands(
        self,
        *,
        fasta_record: dict[str, str],
        activity_csv: str,
        output_dir: Path,
        params: dict[str, Any],
    ) -> tuple[list[list[str]], Path | None, str | None]:
        protein_name = self._clean_optional(params.get("protein_name")) or fasta_record.get("id") or "protein"
        system_name = self._clean_optional(params.get("system_name")) or protein_name
        assay_name = self._clean_optional(params.get("assay_name"))
        embeddings_type = self._clean_optional(params.get("embeddings_type"))
        process_script = self._resolve_first_existing(
            [
                self._clean_optional(params.get("process_script")) or self.default_process_script,
                "scripts/process/exp_process.py",
                "scripts/process/dms_process.py",
            ]
        )
        plm_script = self._resolve_official_plm_script(params, embeddings_type)
        exp_script = self._resolve_official_exp_script(params, system_name)

        if not any(path and path.exists() for path in (process_script, plm_script, exp_script)):
            raise RuntimeError(
                "Detected an official-style EvolvePro scripts layout, but could not resolve runnable steps. "
                "Provide evolvepro.command or set evolvepro.process_script / plm_script / exp_script "
                "(or pass params.process_script / plm_script / exp_script)."
            )

        commands: list[list[str]] = []
        if process_script and process_script.exists():
            if self._script_supports_cli_args(process_script):
                missing = [
                    name
                    for name, value in (
                        ("protein_name", protein_name),
                        ("system_name", system_name),
                        ("embeddings_type", embeddings_type),
                    )
                    if not value
                ]
                if missing:
                    raise RuntimeError(
                        "Official EvolvePro preprocessing requires params/config values: "
                        + ", ".join(missing)
                        + "."
                    )
                process_output_dir = self._resolve_result_path(
                    self._clean_optional(params.get("process_output_dir")),
                    output_dir,
                )
                if process_output_dir is None:
                    process_output_dir = self.root / "data" / "exp" / "exp_data" / system_name
                process_output_dir.mkdir(parents=True, exist_ok=True)
                process_command = self._command_for_script(process_script, env_name=self.conda_env) + [
                    "--protein_name",
                    protein_name,
                    "--embeddings_type",
                    embeddings_type,
                    "--system_name",
                    system_name,
                    "--input_data_location",
                    activity_csv,
                    "--out_folder",
                    str(process_output_dir),
                ]
                if assay_name:
                    process_command.extend(["--assay_name", assay_name])
                commands.append(process_command)
            else:
                # Some EvolvePro forks ship a fixed experimental preprocessing script with no CLI.
                self.ensure_dir(self.root / "data" / "exp" / "wt_fasta")
                self.ensure_dir(self.root / "output" / "exp")
                self.ensure_dir(self.root / "output" / "exp_results")
                commands.append(self._command_for_script(process_script, env_name=self.conda_env))

        if plm_script and plm_script.exists():
            commands.append(self._command_for_script(plm_script, env_name=self.embedding_env))

        if exp_script and exp_script.exists():
            commands.append(self._command_for_script(exp_script, env_name=self.conda_env))

        explicit_result = self._resolve_result_path(
            self._clean_optional(params.get("result_file") or params.get("result_csv") or params.get("output_csv")),
            output_dir,
        )
        result_glob = self._clean_optional(params.get("result_glob")) or self.default_result_glob
        if not result_glob:
            result_glob = "output/**/*.csv"
        return commands, explicit_result, result_glob

    def run(self, input_data: dict) -> dict:
        fasta_path = input_data["fasta_path"]
        activity_csv = input_data.get("activity_csv_path")
        task = input_data.get("task", "")
        params = {**self.default_params, **dict(input_data.get("params") or {})}
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
            fasta_record = read_fasta(fasta_path)
            commands: list[list[str]]
            expected_result = result_csv
            result_glob: str | None = None
            before_snapshot: dict[Path, float] | None = None

            if self.command_template:
                commands = [self.format_command(self.command_template, template_values)]
            else:
                legacy_commands = self._legacy_commands(
                    fasta_path=fasta_path,
                    activity_csv=activity_csv,
                    result_csv=result_csv,
                )
                if legacy_commands is not None:
                    commands = legacy_commands
                elif self._official_layout_detected():
                    before_snapshot = self._result_snapshot()
                    commands, expected_result, result_glob = self._build_official_commands(
                        fasta_record=fasta_record,
                        activity_csv=activity_csv,
                        output_dir=output_dir,
                        params=params,
                    )
                else:
                    raise RuntimeError(
                        "Unable to infer EvolvePro entrypoint. "
                        "Set evolvepro.command in config/config.yaml or EVOLVE_AGENT_EVOLVEPRO_COMMAND_JSON."
                    )

            last_stdout = ""
            for index, command in enumerate(commands, start=1):
                last_stdout = self._run_cmd(command, f"Step{index}").stdout

            resolved_result = self._discover_result(
                explicit_path=expected_result,
                output_dir=output_dir,
                before_snapshot=before_snapshot,
                result_glob=result_glob,
            )
            if resolved_result is None or not resolved_result.exists():
                raise RuntimeError(
                    "EvolvePro finished without producing an identifiable CSV result. "
                    "Set params.result_file / params.result_glob or configure evolvepro.result_glob."
                )

            preview = self._preview_csv(resolved_result)
            return {
                "success": True,
                "output": f"EvolvePro finished. Top predictions:\n{preview}",
                "error": "",
                "result_files": [str(resolved_result)],
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
                    "Check the conda environment, script paths, result_glob/result_file, and evolvepro.command override."
                ),
                "result_files": [],
            }
