from evolve_agent.tools.evolvepro_tool import EvolveProTool


def test_evolvepro_requires_activity_csv(tmp_path):
    config = {
        "evolvepro_root": str(tmp_path),
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "out"),
        "evolvepro": {"conda_env": "evolvepro"},
        "multievolve": {"conda_env": "plm"},
    }
    tool = EvolveProTool(config)
    result = tool.run({"fasta_path": "dummy.fasta"})
    assert result["success"] is False
    assert "requires activity_csv_path" in result["error"]
