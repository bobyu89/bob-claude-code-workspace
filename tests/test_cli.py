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
