from pathlib import Path

import yaml

from evolve_agent.settings import Settings


def test_settings_from_env_resolves_paths_and_openai_aliases(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "evolvepro_root": str(tmp_path / "EvolvePro"),
                "multievolve_root": str(tmp_path / "MULTI-evolve"),
                "multievolve_model_dir": str(tmp_path / "MULTI-evolve" / "models"),
                "tmp_dir": "tmp",
                "result_dir": "results",
                "upload_dir": "uploads",
                "default_strategy": "multievolve",
                "evolvepro": {"conda_env": "evolvepro", "timeout_seconds": 111},
                "multievolve": {"conda_env": "plm", "num_samples": 32},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("EVOLVE_AGENT_CONFIG", str(config_path))

    settings = Settings.from_env()

    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.openai_api_key == "test-key"
    assert settings.tmp_dir == str(Path(tmp_path / "tmp"))
    assert settings.upload_dir == str(Path(tmp_path / "uploads"))
    assert settings.evolvepro_timeout_seconds == 111
    assert settings.multievolve_num_samples == 32
    assert settings.to_agent_config()["multievolve"]["num_samples"] == 32
