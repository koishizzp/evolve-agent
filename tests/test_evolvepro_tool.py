import subprocess

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


def test_evolvepro_detects_official_scripts_layout(monkeypatch, tmp_path):
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">mlv\nMKTIIALSYIFCLVFA\n", encoding="utf-8")
    activity_csv = tmp_path / "activity.csv"
    activity_csv.write_text("mutant,score\nWT,1.0\n", encoding="utf-8")

    process_script = tmp_path / "scripts" / "process" / "exp_process.py"
    process_script.parent.mkdir(parents=True, exist_ok=True)
    process_script.write_text("import argparse\nprint('process')\n", encoding="utf-8")

    plm_script = tmp_path / "scripts" / "plm" / "esm2_15B_exp.sh"
    plm_script.parent.mkdir(parents=True, exist_ok=True)
    plm_script.write_text("echo plm\n", encoding="utf-8")

    exp_script = tmp_path / "scripts" / "exp" / "mlv.py"
    exp_script.parent.mkdir(parents=True, exist_ok=True)
    exp_script.write_text("print('exp')\n", encoding="utf-8")

    result_csv = tmp_path / "results" / "exp_data" / "mlv" / "predictions.csv"

    config = {
        "evolvepro_root": str(tmp_path),
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "out"),
        "evolvepro": {"conda_env": "evolvepro"},
        "multievolve": {"conda_env": "plm"},
    }
    tool = EvolveProTool(config)
    commands = []

    def fake_run(command, step_name):
        commands.append((step_name, command))
        if step_name == "Step3":
            result_csv.parent.mkdir(parents=True, exist_ok=True)
            result_csv.write_text("mutation,score\nA1V,0.8\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=f"{step_name} ok", stderr="")

    monkeypatch.setattr(tool, "_run_cmd", fake_run)

    result = tool.run(
        {
            "fasta_path": str(fasta),
            "activity_csv_path": str(activity_csv),
            "params": {
                "protein_name": "MLV",
                "system_name": "mlv",
                "embeddings_type": "esm2_15B",
            },
        }
    )

    assert result["success"] is True
    assert result["result_files"] == [str(result_csv)]
    assert len(commands) == 3
    assert commands[0][0] == "Step1"
    assert str(process_script) in commands[0][1]
    assert "--out_folder" in commands[0][1]
    assert any("data" in item for item in commands[0][1])
    assert commands[1][0] == "Step2"
    assert commands[1][1][-1] == str(plm_script)
    assert commands[2][0] == "Step3"
    assert commands[2][1][-1] == str(exp_script)
    assert "A1V" in result["output"]


def test_evolvepro_uses_config_default_params_and_output_root(monkeypatch, tmp_path):
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">seq\nMKTIIALSYIFCLVFA\n", encoding="utf-8")
    activity_csv = tmp_path / "activity.csv"
    activity_csv.write_text("mutant,score\nWT,1.0\n", encoding="utf-8")

    (tmp_path / "scripts" / "process").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "process" / "exp_process.py").write_text("print('process')\n", encoding="utf-8")
    (tmp_path / "scripts" / "plm").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "plm" / "esm2_15B_exp.sh").write_text("echo plm\n", encoding="utf-8")
    (tmp_path / "scripts" / "exp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "exp" / "t7_pol.py").write_text("print('exp')\n", encoding="utf-8")

    result_csv = tmp_path / "output" / "exp_results" / "t7_pol.csv"

    config = {
        "evolvepro_root": str(tmp_path),
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "out"),
        "evolvepro": {
            "conda_env": "evolvepro",
            "result_glob": "output/**/*.csv",
            "params": {
                "protein_name": "t7_pol",
                "system_name": "t7_pol",
                "embeddings_type": "esm2_15B",
            },
        },
        "multievolve": {"conda_env": "plm"},
    }
    tool = EvolveProTool(config)

    def fake_run(command, step_name):
        if step_name == "Step3":
            result_csv.parent.mkdir(parents=True, exist_ok=True)
            result_csv.write_text("mutation,score\nA2G,0.9\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=f"{step_name} ok", stderr="")

    monkeypatch.setattr(tool, "_run_cmd", fake_run)

    result = tool.run(
        {
            "fasta_path": str(fasta),
            "activity_csv_path": str(activity_csv),
        }
    )

    assert result["success"] is True
    assert result["result_files"] == [str(result_csv)]
    assert "A2G" in result["output"]


def test_evolvepro_supports_non_cli_exp_process(monkeypatch, tmp_path):
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">bxb1\nMKTIIALSYIFCLVFA\n", encoding="utf-8")
    activity_csv = tmp_path / "activity.csv"
    activity_csv.write_text("mutant,score\nWT,1.0\n", encoding="utf-8")

    process_script = tmp_path / "scripts" / "process" / "exp_process.py"
    process_script.parent.mkdir(parents=True, exist_ok=True)
    process_script.write_text("print('fixed preprocessing script')\n", encoding="utf-8")

    plm_script = tmp_path / "scripts" / "plm" / "esm2_15B_exp.sh"
    plm_script.parent.mkdir(parents=True, exist_ok=True)
    plm_script.write_text("echo plm\n", encoding="utf-8")

    exp_script = tmp_path / "scripts" / "exp" / "bxb1.py"
    exp_script.parent.mkdir(parents=True, exist_ok=True)
    exp_script.write_text("print('exp')\n", encoding="utf-8")

    result_csv = tmp_path / "output" / "exp_results" / "bxb1.csv"
    config = {
        "evolvepro_root": str(tmp_path),
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "out"),
        "evolvepro": {
            "conda_env": "evolvepro",
            "params": {
                "protein_name": "bxb1",
                "system_name": "bxb1",
                "embeddings_type": "esm2_15B",
            },
        },
        "multievolve": {"conda_env": "plm"},
    }
    tool = EvolveProTool(config)
    commands = []

    def fake_run(command, step_name):
        commands.append((step_name, command))
        if step_name == "Step3":
            result_csv.parent.mkdir(parents=True, exist_ok=True)
            result_csv.write_text("mutation,score\nA3V,0.7\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=f"{step_name} ok", stderr="")

    monkeypatch.setattr(tool, "_run_cmd", fake_run)

    result = tool.run(
        {
            "fasta_path": str(fasta),
            "activity_csv_path": str(activity_csv),
        }
    )

    assert result["success"] is True
    assert result["result_files"] == [str(result_csv)]
    assert commands[0][1] == ["conda", "run", "-n", "evolvepro", "python", str(process_script)]
    assert (tmp_path / "output" / "exp").exists()
    assert (tmp_path / "output" / "exp_results").exists()
