"""`aistat plan --alternative-of RUN`: a new plan for the alternative method, same variables."""

import pytest

from aistat.errors import PlanError
from conftest import check, make_workspace, run_analysis

PAIRED = {"before": "drug1", "after": "drug2"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "sleep_wide.csv", "sleep_long.csv", "wards.csv", "textbook_xy.csv")


@pytest.mark.parametrize("method,dataset,variables,options,expected_method,expected_options", [
    ("paired-t-test", "sleep_wide", PAIRED, {"alpha": 0.01}, "wilcoxon-signed-rank", {}),
    ("independent-t-test", "sleep_long", {"outcome": "extra", "group": "drug"}, None, "mann-whitney-u", {}),
    ("chi-square", "wards", {"row": "ward", "column": "passed"}, None, "fisher-exact", {}),
    ("correlation", "textbook_xy", {"x": "hours", "y": "score"}, None, "correlation", {"method": "spearman"}),
])
def test_alternative_plan_keeps_dataset_and_variables(ws, method, dataset, variables, options,
                                                      expected_method, expected_options):
    original = ws.create_plan(method, variables, dataset_id=dataset, options=options)

    alt = ws.create_alternative_plan(original.id)

    plan = alt.plan
    assert alt.id != original.id
    assert plan["method"] == expected_method
    assert plan["variables"] == original.plan["variables"]
    assert plan["dataset_id"] == dataset
    assert plan["alternative_of"] == original.id
    assert plan["options"]["alpha"] == original.plan["options"]["alpha"]
    for key, value in expected_options.items():
        assert plan["options"][key] == value
    assert alt.status in ("JEV_GATE_A", "BLOCKED")
    assert ws.get_run(original.id).status == original.status


@pytest.mark.parametrize("method,dataset,variables,options", [
    ("descriptives", "sleep_wide", {"variables": "drug1"}, None),
    ("correlation", "textbook_xy", {"x": "hours", "y": "score"}, {"method": "spearman"}),
    ("wilcoxon-signed-rank", "sleep_wide", PAIRED, None),
])
def test_methods_without_alternative_are_rejected(ws, method, dataset, variables, options):
    run = ws.create_plan(method, variables, dataset_id=dataset, options=options)

    with pytest.raises(PlanError, match="替代"):
        ws.create_alternative_plan(run.id)


def test_chi_square_larger_than_two_by_two_has_no_fisher_alternative(ws, tmp_path):
    from conftest import write_dataset

    write_dataset(ws, tmp_path, "big.csv", "a,b\n" + "x,p\ny,q\nz,p\nx,q\ny,p\nz,q\n" * 3)
    run = ws.create_plan("chi-square", {"row": "a", "column": "b"}, dataset_id="big")

    with pytest.raises(PlanError, match="2 × 2"):
        ws.create_alternative_plan(run.id)


def test_gate_b_and_report_point_to_the_alternative_command(ws):
    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")

    reason = check(ws.review(run.id), "assumptions_met").reason
    text = ws.report(run.id).read_text(encoding="utf-8")

    command = f"aistat plan --alternative-of {run.id}"
    assert command in reason
    assert f"`{command}`" in text.split("## JEV")[0]


def test_original_run_files_are_untouched(ws):
    original = ws.create_plan("paired-t-test", PAIRED, dataset_id="sleep_wide")
    before = {p.name: p.read_bytes() for p in original.dir.iterdir() if p.is_file()}

    ws.create_alternative_plan(original.id)

    assert {p.name: p.read_bytes() for p in original.dir.iterdir() if p.is_file()} == before
