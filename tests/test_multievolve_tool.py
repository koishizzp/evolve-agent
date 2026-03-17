from evolve_agent.tools.multievolve_tool import MultiEvolveTool


def test_multievolve_handles_missing_checkpoint(tmp_path):
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">seq\nMKTIIALSYIFCLVFA\n", encoding="utf-8")
    (tmp_path / "p2_propose.py").write_text("print('placeholder')\n", encoding="utf-8")

    config = {
        "multievolve_root": str(tmp_path),
        "multievolve_model_dir": str(tmp_path / "models"),
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "out"),
        "multievolve": {"conda_env": "plm"},
    }
    tool = MultiEvolveTool(config)
    result = tool.run({"fasta_path": str(fasta)})
    assert result["success"] is False
    assert "checkpoint_path" in result["error"]
