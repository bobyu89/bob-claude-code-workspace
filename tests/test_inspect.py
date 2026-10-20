import csv

import pytest

from aistat.errors import AistatError
from aistat.workspace import Workspace

DATA = (
    "sid,ward,likert,score,const\n"
    "1,A,1,10.5,x\n"
    "2,B,2,,x\n"
    "3,A,3,,x\n"
    "4,B,4,,x\n"
    "5,A,5,9.25,x\n"
    "5,A,5,9.25,x\n"
)


@pytest.fixture
def ws(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    src = tmp_path / "survey.csv"
    src.write_text(DATA, encoding="utf-8")
    ws.import_dataset(src)
    return ws


def issue_codes(inspection, variable=None):
    return {i.code for i in inspection.issues if variable is None or i.variable == variable}


def test_inspect_flags_quality_problems(ws):
    result = ws.inspect("survey")

    assert "high_missing" in issue_codes(result, "score")
    assert "constant" in issue_codes(result, "const")
    assert "duplicate_rows" in issue_codes(result)
    assert "ambiguous_level" in issue_codes(result, "likert")
    assert "possible_id" not in issue_codes(result, "sid")  # sid has a duplicated value


def test_inspect_flags_unique_integer_column_as_possible_id(tmp_path):
    ws = Workspace.init(tmp_path / "proj")
    src = tmp_path / "ids.csv"
    src.write_text("patient_no,bp\n101,120\n102,130\n103,125\n104,140\n105,135\n106,128\n107,131\n108,122\n",
                   encoding="utf-8")
    ws.import_dataset(src)

    assert "possible_id" in issue_codes(ws.inspect("ids"), "patient_no")


def test_inspect_includes_preview_rows(ws):
    result = ws.inspect("survey", preview_rows=2)

    assert len(result.preview) == 2
    assert list(result.preview.columns) == ["sid", "ward", "likert", "score", "const"]


def test_quality_report_markdown_lists_issues_and_dataset_hash(ws):
    md = ws.quality_report("survey")

    assert ws.get_dataset("survey").sha256 in md
    assert "score" in md and "缺失" in md
    assert "重複" in md


def test_user_can_correct_measurement_level(ws):
    ws.set_variable_level("survey", "likert", "scale")

    var = ws.get_dictionary("survey")["likert"]
    assert (var.level, var.level_source, var.ambiguous) == ("scale", "user", False)
    assert "ambiguous_level" not in issue_codes(ws.inspect("survey"), "likert")


@pytest.mark.parametrize("var,level,message", [("nope", "scale", "找不到變項"), ("likert", "interval", "測量尺度")])
def test_set_level_rejects_invalid_input(ws, var, level, message):
    with pytest.raises(AistatError, match=message):
        ws.set_variable_level("survey", var, level)


def test_export_dictionary_csv(ws, tmp_path):
    out = tmp_path / "data_dictionary.csv"

    ws.export_dictionary("survey", out)

    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [r["name"] for r in rows] == ["sid", "ward", "likert", "score", "const"]
    assert rows[3]["n_missing"] == "3"
    assert rows[3]["level"] == "scale"
