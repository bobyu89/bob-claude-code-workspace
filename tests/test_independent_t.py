"""Independent-samples t test. Reference: R's documented `sleep` Welch example
(t = -1.8608, df = 17.776, p = 0.07939, 95% CI [-3.3654832, 0.2054832]) and
Student version (df = 18, p = 0.07919)."""

import pytest

from conftest import (assert_same_numbers, check, make_workspace, requires_r, run_analysis,
                      write_dataset)

VARS = {"outcome": "extra", "group": "drug"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "sleep_long.csv")


def test_gate_a_requires_independence_confirmation(ws):
    run = ws.create_plan("independent-t-test", VARS)

    review = ws.method_review(run.id)
    assert check(review, "independence").verdict == "UNCERTAIN"
    assert check(review, "group_structure").verdict == "YES"
    assert run.plan["levels"] == {"group": ["drug1", "drug2"]}


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_engine_reproduces_known_welch_and_student_results(ws, engine):
    _, res = run_analysis(ws, "independent-t-test", VARS, engine)

    s = res["statistics"]
    assert [g["level"] for g in s["groups"]] == ["drug1", "drug2"]
    assert [g["n"] for g in s["groups"]] == [10, 10]
    assert s["mean_diff"] == pytest.approx(-1.58, abs=1e-9)
    assert s["welch"]["t"] == pytest.approx(-1.8608, abs=1e-4)
    assert s["welch"]["df"] == pytest.approx(17.776, abs=1e-3)
    assert s["welch"]["p"] == pytest.approx(0.07939, abs=1e-5)
    assert (s["welch"]["ci_lower"], s["welch"]["ci_upper"]) == pytest.approx((-3.3654832, 0.2054832), abs=1e-7)
    assert s["student"]["df"] == 18
    assert s["student"]["p"] == pytest.approx(0.07919, abs=1e-5)
    assert s["cohens_d"] == pytest.approx(-1.58 / ((1.789010**2 + 2.002249**2) / 2) ** 0.5, abs=1e-5)
    ids = [a["id"] for a in res["assumptions"]]
    assert ids == ["normality_by_group", "normality_by_group", "homogeneity_of_variance"]


@requires_r
def test_r_and_python_agree(ws):
    _, r = run_analysis(ws, "independent-t-test", VARS, "r")
    _, py = run_analysis(ws, "independent-t-test", VARS, "python")

    assert_same_numbers(r["statistics"], py["statistics"])
    assert_same_numbers(r["assumptions"], py["assumptions"])


def test_three_groups_block_plan(ws, tmp_path):
    write_dataset(ws, tmp_path, "three.csv", "score,arm\n1.5,a\n2.5,a\n3.5,b\n4.5,b\n5.5,c\n6.5,c\n")

    run = ws.create_plan("independent-t-test", {"outcome": "score", "group": "arm"}, dataset_id="three")

    assert run.status == "BLOCKED"
    assert "3" in check(ws.method_review(run.id), "group_structure").reason


def test_numeric_group_codes_with_missing_values(ws, tmp_path):
    write_dataset(ws, tmp_path, "coded.csv",
                  "score,arm\n1.5,1\n2.5,1\n3.25,1\n4.5,2\n5.5,2\n6.75,2\n7.0,\n")

    run, res = run_analysis(ws, "independent-t-test", {"outcome": "score", "group": "arm"}, "python",
                            dataset_id="coded")

    assert run.plan["levels"] == {"group": ["1", "2"]}
    assert res["statistics"]["n"] == 6


def test_report_uses_welch_and_passes_gate_b(ws):
    run, _ = run_analysis(ws, "independent-t-test", VARS, "python")

    text = ws.report(run.id).read_text(encoding="utf-8")

    assert "t(17.78) = -1.86, p = .079" in text
    assert "95% CI [-3.37, 0.21]" in text
    assert "未達統計顯著" in text
    assert check(ws.review(run.id), "assumptions_met").verdict == "YES"


def test_learning_notes_for_independent_t(ws):
    run, _ = run_analysis(ws, "independent-t-test", VARS, "python")

    ws.report(run.id, mode="learning")

    notes = (run.dir / "learning_notes.md").read_text(encoding="utf-8")
    assert "Welch" in notes and "extra" in notes and "drug1" in notes
