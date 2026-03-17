from evolve_agent.tools.evolvepro_tool import EvolveProTool


def test_evolvepro_requires_activity_csv(tmp_path):
    config = {
        "evolvepro_path": str(tmp_path),
        "tmp_dir": str(tmp_path / "tmp"),
        "output_dir": str(tmp_path / "out"),
        "conda_env_evolvepro": "evolvepro",
        "conda_env_plm": "plm",
    }
    tool = EvolveProTool(config)
    result = tool.run({"fasta_path": "dummy.fasta"})
    assert result["success"] is False
    assert "requires activity_csv_path" in result["error"]
