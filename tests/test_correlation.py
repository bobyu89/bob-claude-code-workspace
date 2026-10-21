"""Correlation. Textbook data x = 1..5, y = (2, 4, 5, 4, 5): SSxy = 6, SSx = 10, SSy = 6,
so r = 6 / √60 = √.6 = .7746, t = r√(3 / (1 − r²)) = 2.1213, df = 3."""

import math

import pytest

from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis

VARS = {"x": "hours", "y": "score"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "textbook_xy.csv")


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_pearson_matches_hand_computation(ws, engine):
    _, res = run_analysis(ws, "correlation", VARS, engine)

    s = res["statistics"]
    assert s["method"] == "pearson"
    assert s["r"] == pytest.approx(math.sqrt(0.6), abs=1e-12)
    assert s["t"] == pytest.approx(0.6 / math.sqrt(0.08), abs=1e-9)
    assert s["df"] == 3
    assert s["p"] == pytest.approx(0.1240, abs=1e-4)
    assert s["ci_lower"] < 0 < s["r"] < s["ci_upper"] < 1
    assert [a["variable"] for a in res["assumptions"]] == ["hours", "score"]


@requires_r
@pytest.mark.parametrize("method", ["pearson", "spearman"])
def test_r_and_python_agree(ws, method):
    _, r = run_analysis(ws, "correlation", VARS, "r", options={"method": method})
    _, py = run_analysis(ws, "correlation", VARS, "python", options={"method": method})

    assert_same_numbers(r["statistics"], py["statistics"])
    assert_same_numbers(r["assumptions"], py["assumptions"])


def test_spearman_has_no_ci_and_no_normality_check(ws):
    run, res = run_analysis(ws, "correlation", VARS, "python", options={"method": "spearman"})

    assert res["statistics"]["ci_lower"] is None
    assert res["assumptions"] == []
    assert run.plan["assumptions"] == []


def test_pearson_on_ordinal_variable_needs_confirmation(ws):
    ws.set_variable_level("textbook_xy", "rank_item", "ordinal")

    run = ws.create_plan("correlation", {"x": "hours", "y": "rank_item"})

    assert check(ws.method_review(run.id), "correlation_type").verdict == "UNCERTAIN"
    assert "spearman" in check(ws.method_review(run.id), "correlation_type").reason


def test_invalid_correlation_method_is_rejected(ws):
    from aistat.errors import PlanError

    with pytest.raises(PlanError, match="kendall"):
        ws.create_plan("correlation", VARS, options={"method": "kendall"})


def test_report_apa_correlation(ws):
    run, _ = run_analysis(ws, "correlation", VARS, "python")

    text = ws.report(run.id).read_text(encoding="utf-8")

    assert "r(3) = .77, p = .124, 95% CI [-.34, .98]" in text
    assert "未達統計顯著" in text


def test_learning_notes_read_the_interval_for_pearson(ws):
    run, res = run_analysis(ws, "correlation", VARS, "python")
    ws.report(run.id, mode="learning")

    s = res["statistics"]
    contains = s["ci_lower"] <= 0 <= s["ci_upper"]
    notes = (run.dir / "learning_notes.md").read_text(encoding="utf-8")
    assert ("區間包含 0" if contains else "區間不包含 0") in notes
