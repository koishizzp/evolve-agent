from evolve_agent.tools.multievolve_tool import MultiEvolveTool


def test_multievolve_handles_failure(tmp_path):
    config = {
        "multievolve_path": str(tmp_path),
        "output_dir": str(tmp_path / "out"),
        "conda_env_plm": "plm",
    }
    tool = MultiEvolveTool(config)
    result = tool.run({"fasta_path": "dummy.fasta"})
    assert result["success"] is False
    assert "执行失败" in result["error"]
