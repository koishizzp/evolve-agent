"""Environment-aware runtime settings for evolve-agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any

import yaml


def _load_env_file(path: str = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    file_path = Path(path)
    if not file_path.exists():
        return env

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _env_source() -> dict[str, str]:
    data = _load_env_file()
    data.update(os.environ)
    return data


def _env_get(data: dict[str, str], name: str, default: str | None = None) -> str | None:
    return data.get(name, default)


def _env_get_first(data: dict[str, str], names: list[str], default: str | None = None) -> str | None:
    for name in names:
        if name in data:
            return data[name]
    return default


def _to_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _to_optional_str(value: str | None, default: str | None = None) -> str | None:
    if value is None:
        return default
    cleaned = value.strip()
    return cleaned if cleaned else default


def _load_yaml_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw
    return {}


def _resolve_path(value: str | None, *, root: str | None, base_dir: Path) -> str | None:
    if value is None:
        return None
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    if root:
        return str(Path(root) / candidate)
    return str(base_dir / candidate)


def _parse_command(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        try:
            decoded = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [str(item) for item in decoded if str(item).strip()]
    return []


@dataclass(slots=True)
class Settings:
    app_name: str = "Evolve Agent"
    log_level: str = "INFO"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    request_timeout: int = 120

    api_host: str = "0.0.0.0"
    api_port: int = 8110
    config_path: str = "config/config.yaml"

    evolvepro_root: str | None = None
    multievolve_root: str | None = None
    multievolve_model_dir: str | None = None
    tmp_dir: str = "./tmp"
    result_dir: str = "./results"
    upload_dir: str = "./uploads"
    default_strategy: str = "multievolve"

    evolvepro_conda_env: str = "evolvepro"
    evolvepro_timeout_seconds: int = 7200
    evolvepro_command: list[str] = field(default_factory=list)
    multievolve_conda_env: str = "plm"
    multievolve_timeout_seconds: int = 7200
    multievolve_train_command: list[str] = field(default_factory=list)
    multievolve_propose_command: list[str] = field(default_factory=list)
    multievolve_checkpoint_path: str | None = None
    multievolve_protein_name: str | None = None
    multievolve_residues_to_mutate: str | None = None
    multievolve_number_mutations_per_variant: int = 4
    multievolve_num_samples: int = 64
    extra_config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls, config_path_override: str | None = None) -> "Settings":
        data = _env_source()
        defaults = cls()
        config_path = config_path_override or _env_get(data, "EVOLVE_AGENT_CONFIG", defaults.config_path) or defaults.config_path
        config_path_obj = Path(config_path)
        yaml_config = _load_yaml_config(config_path)
        config_dir = config_path_obj.parent if config_path_obj.parent != Path("") else Path.cwd()

        evolvepro_section = yaml_config.get("evolvepro", {}) if isinstance(yaml_config.get("evolvepro"), dict) else {}
        multievolve_section = yaml_config.get("multievolve", {}) if isinstance(yaml_config.get("multievolve"), dict) else {}

        evolvepro_root = _resolve_path(
            _env_get(data, "EVOLVE_AGENT_EVOLVEPRO_ROOT", _to_optional_str(yaml_config.get("evolvepro_root"))),
            root=None,
            base_dir=config_dir,
        )
        multievolve_root = _resolve_path(
            _env_get(data, "EVOLVE_AGENT_MULTIEVOLVE_ROOT", _to_optional_str(yaml_config.get("multievolve_root"))),
            root=None,
            base_dir=config_dir,
        )

        return cls(
            app_name=_env_get(data, "EVOLVE_AGENT_APP_NAME", defaults.app_name) or defaults.app_name,
            log_level=_env_get(data, "EVOLVE_AGENT_LOG_LEVEL", defaults.log_level) or defaults.log_level,
            llm_model=_env_get_first(data, ["EVOLVE_AGENT_LLM_MODEL", "OPENAI_MODEL"], defaults.llm_model)
            or defaults.llm_model,
            openai_api_key=_to_optional_str(_env_get_first(data, ["EVOLVE_AGENT_OPENAI_API_KEY", "OPENAI_API_KEY"])),
            openai_base_url=_to_optional_str(_env_get_first(data, ["EVOLVE_AGENT_OPENAI_BASE_URL", "OPENAI_BASE_URL"])),
            request_timeout=_to_int(_env_get(data, "EVOLVE_AGENT_REQUEST_TIMEOUT"), defaults.request_timeout),
            api_host=_env_get(data, "EVOLVE_AGENT_API_HOST", defaults.api_host) or defaults.api_host,
            api_port=_to_int(_env_get(data, "EVOLVE_AGENT_API_PORT"), defaults.api_port),
            config_path=config_path,
            evolvepro_root=evolvepro_root,
            multievolve_root=multievolve_root,
            multievolve_model_dir=_resolve_path(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_MODEL_DIR",
                    _to_optional_str(yaml_config.get("multievolve_model_dir")),
                ),
                root=None,
                base_dir=config_dir,
            ),
            tmp_dir=_resolve_path(
                _env_get(data, "EVOLVE_AGENT_TMP_DIR", yaml_config.get("tmp_dir", defaults.tmp_dir)),
                root=None,
                base_dir=config_dir,
            )
            or defaults.tmp_dir,
            result_dir=_resolve_path(
                _env_get(data, "EVOLVE_AGENT_RESULT_DIR", yaml_config.get("result_dir", defaults.result_dir)),
                root=None,
                base_dir=config_dir,
            )
            or defaults.result_dir,
            upload_dir=_resolve_path(
                _env_get(data, "EVOLVE_AGENT_UPLOAD_DIR", yaml_config.get("upload_dir", defaults.upload_dir)),
                root=None,
                base_dir=config_dir,
            )
            or defaults.upload_dir,
            default_strategy=_env_get(
                data,
                "EVOLVE_AGENT_DEFAULT_STRATEGY",
                yaml_config.get("default_strategy", defaults.default_strategy),
            )
            or defaults.default_strategy,
            evolvepro_conda_env=_env_get(
                data,
                "EVOLVE_AGENT_EVOLVEPRO_CONDA_ENV",
                evolvepro_section.get("conda_env", defaults.evolvepro_conda_env),
            )
            or defaults.evolvepro_conda_env,
            evolvepro_timeout_seconds=_to_int(
                _env_get(
                    data,
                    "EVOLVE_AGENT_EVOLVEPRO_TIMEOUT",
                    str(evolvepro_section.get("timeout_seconds", defaults.evolvepro_timeout_seconds)),
                ),
                defaults.evolvepro_timeout_seconds,
            ),
            evolvepro_command=_parse_command(
                _env_get(
                    data,
                    "EVOLVE_AGENT_EVOLVEPRO_COMMAND_JSON",
                    json.dumps(evolvepro_section.get("command", [])),
                )
            ),
            multievolve_conda_env=_env_get(
                data,
                "EVOLVE_AGENT_MULTIEVOLVE_CONDA_ENV",
                multievolve_section.get("conda_env", defaults.multievolve_conda_env),
            )
            or defaults.multievolve_conda_env,
            multievolve_timeout_seconds=_to_int(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_TIMEOUT",
                    str(multievolve_section.get("timeout_seconds", defaults.multievolve_timeout_seconds)),
                ),
                defaults.multievolve_timeout_seconds,
            ),
            multievolve_train_command=_parse_command(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_TRAIN_COMMAND_JSON",
                    json.dumps(multievolve_section.get("train_command", [])),
                )
            ),
            multievolve_propose_command=_parse_command(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_PROPOSE_COMMAND_JSON",
                    json.dumps(multievolve_section.get("propose_command", [])),
                )
            ),
            multievolve_checkpoint_path=_resolve_path(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_CHECKPOINT_PATH",
                    _to_optional_str(multievolve_section.get("checkpoint_path")),
                ),
                root=None,
                base_dir=config_dir,
            ),
            multievolve_protein_name=_to_optional_str(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_PROTEIN_NAME",
                    _to_optional_str(multievolve_section.get("protein_name")),
                )
            ),
            multievolve_residues_to_mutate=_to_optional_str(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_RESIDUES_TO_MUTATE",
                    _to_optional_str(multievolve_section.get("residues_to_mutate")),
                )
            ),
            multievolve_number_mutations_per_variant=_to_int(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_NUM_MUTATIONS",
                    str(
                        multievolve_section.get(
                            "number_mutations_per_variant",
                            defaults.multievolve_number_mutations_per_variant,
                        )
                    ),
                ),
                defaults.multievolve_number_mutations_per_variant,
            ),
            multievolve_num_samples=_to_int(
                _env_get(
                    data,
                    "EVOLVE_AGENT_MULTIEVOLVE_NUM_SAMPLES",
                    str(multievolve_section.get("num_samples", defaults.multievolve_num_samples)),
                ),
                defaults.multievolve_num_samples,
            ),
            extra_config={
                "evolvepro": dict(evolvepro_section),
                "multievolve": dict(multievolve_section),
            },
        )

    def to_agent_config(self) -> dict[str, Any]:
        return {
            "evolvepro_root": self.evolvepro_root,
            "multievolve_root": self.multievolve_root,
            "multievolve_model_dir": self.multievolve_model_dir,
            "tmp_dir": self.tmp_dir,
            "result_dir": self.result_dir,
            "upload_dir": self.upload_dir,
            "default_strategy": self.default_strategy,
            "evolvepro": {
                **self.extra_config.get("evolvepro", {}),
                "conda_env": self.evolvepro_conda_env,
                "timeout_seconds": self.evolvepro_timeout_seconds,
                "command": self.evolvepro_command,
            },
            "multievolve": {
                **self.extra_config.get("multievolve", {}),
                "conda_env": self.multievolve_conda_env,
                "timeout_seconds": self.multievolve_timeout_seconds,
                "train_command": self.multievolve_train_command,
                "propose_command": self.multievolve_propose_command,
                "checkpoint_path": self.multievolve_checkpoint_path,
                "protein_name": self.multievolve_protein_name,
                "residues_to_mutate": self.multievolve_residues_to_mutate,
                "number_mutations_per_variant": self.multievolve_number_mutations_per_variant,
                "num_samples": self.multievolve_num_samples,
            },
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
