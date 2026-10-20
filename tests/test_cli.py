from typer.testing import CliRunner

from aistat.cli import app

runner = CliRunner()


def invoke(ws_dir, *args):
    return runner.invoke(app, ["--workspace", str(ws_dir), *args])


def test_init_import_and_list_datasets(tmp_path):
    ws_dir = tmp_path / "proj"
    csv = tmp_path / "scores.csv"
    csv.write_text("pre,post\n10,12\n11,15\n", encoding="utf-8")

    assert invoke(ws_dir, "init").exit_code == 0
    imported = invoke(ws_dir, "import", str(csv))
    listed = invoke(ws_dir, "datasets")

    assert imported.exit_code == 0, imported.output
    assert "scores" in imported.output
    assert "scores" in listed.output and "2" in listed.output


def test_user_errors_exit_nonzero_without_traceback(tmp_path):
    ws_dir = tmp_path / "proj"
    invoke(ws_dir, "init")

    result = invoke(ws_dir, "import", str(tmp_path / "nope.csv"))

    assert result.exit_code == 1
    assert "找不到檔案" in result.output
    assert "Traceback" not in result.output


def test_commands_outside_workspace_point_to_init(tmp_path):
    result = invoke(tmp_path, "datasets")

    assert result.exit_code == 1
    assert "aistat init" in result.output


def test_inspect_dictionary_set_and_export(tmp_path):
    ws_dir = tmp_path / "proj"
    csv = tmp_path / "s.csv"
    csv.write_text("item,score\n1,10.5\n2,11.25\n3,9.5\n4,8.0\n", encoding="utf-8")
    invoke(ws_dir, "init")
    invoke(ws_dir, "import", str(csv))

    inspected = invoke(ws_dir, "inspect", "--report", str(tmp_path / "q.md"))
    set_level = invoke(ws_dir, "dictionary", "set", "item", "--level", "nominal")
    exported = invoke(ws_dir, "dictionary", "export", str(tmp_path / "dd.csv"))

    assert inspected.exit_code == 0, inspected.output
    assert "ambiguous_level" in inspected.output
    assert "資料品質報告" in (tmp_path / "q.md").read_text(encoding="utf-8")
    assert set_level.exit_code == 0, set_level.output
    assert exported.exit_code == 0
    assert "item" in (tmp_path / "dd.csv").read_text(encoding="utf-8")


def test_plan_approve_analyze_via_cli(tmp_path):
    from conftest import GOLDEN

    ws_dir = tmp_path / "proj"
    invoke(ws_dir, "init")
    invoke(ws_dir, "import", str(GOLDEN / "sleep_wide.csv"))

    planned = invoke(ws_dir, "plan", "--method", "paired-t-test", "--var", "before=drug1", "--var", "after=drug2")
    run_id = next(w for w in planned.output.split() if w.startswith("RUN_"))
    refused = invoke(ws_dir, "analyze", run_id, "--engine", "python")
    approved = invoke(ws_dir, "approve", run_id, "--confirm", "pairing_structure")
    analyzed = invoke(ws_dir, "analyze", run_id, "--engine", "python")
    status = invoke(ws_dir, "status", run_id)
    runs = invoke(ws_dir, "runs")

    assert planned.exit_code == 0, planned.output
    assert "[UNCERTAIN] pairing_structure" in planned.output
    assert refused.exit_code == 1 and "核准" in refused.output
    assert approved.exit_code == 0, approved.output
    assert analyzed.exit_code == 0, analyzed.output
    assert "t(9) = 4.06, p = .003" in analyzed.output
    assert "EXECUTED" in status.output and "USER_APPROVAL" in status.output
    assert run_id in runs.output


def test_plan_rejects_malformed_var_option(tmp_path):
    ws_dir = tmp_path / "proj"
    invoke(ws_dir, "init")

    result = invoke(ws_dir, "plan", "--method", "paired-t-test", "--var", "drug1")

    assert result.exit_code == 1
    assert "role=欄位" in result.output


def _executed_run(tmp_path):
    from conftest import GOLDEN

    ws_dir = tmp_path / "proj"
    invoke(ws_dir, "init")
    invoke(ws_dir, "import", str(GOLDEN / "sleep_wide.csv"))
    planned = invoke(ws_dir, "plan", "--method", "paired-t-test", "--var", "before=drug1", "--var", "after=drug2")
    run_id = next(w for w in planned.output.split() if w.startswith("RUN_"))
    invoke(ws_dir, "approve", run_id, "--confirm", "pairing_structure")
    invoke(ws_dir, "analyze", run_id, "--engine", "python")
    return ws_dir, run_id


def test_review_and_report_via_cli(tmp_path):
    ws_dir, run_id = _executed_run(tmp_path)
    bad = tmp_path / "bad.md"
    bad.write_text("t(9) = 9.99, p = .000\n", encoding="utf-8")

    reviewed = invoke(ws_dir, "review", run_id)
    refused = invoke(ws_dir, "report", run_id, "--draft", str(bad))
    reported = invoke(ws_dir, "report", run_id, "--mode", "learning", "--lang", "zh")

    assert reviewed.exit_code == 0, reviewed.output
    assert "[YES] values_traceable" in reviewed.output
    assert refused.exit_code == 1 and "values_traceable" in refused.output
    assert reported.exit_code == 0, reported.output
    assert "statistical_report.md" in reported.output and "learning_notes.md" in reported.output


def test_export_and_rerun_via_cli(tmp_path):
    ws_dir, run_id = _executed_run(tmp_path)
    invoke(ws_dir, "report", run_id)

    rerun = invoke(ws_dir, "rerun", run_id)
    exported = invoke(ws_dir, "export", run_id)

    assert rerun.exit_code == 0 and "一致" in rerun.output
    assert exported.exit_code == 0, exported.output
    assert (ws_dir / "exports" / f"{run_id}.zip").is_file()
