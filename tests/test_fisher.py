"""Fisher's exact test (2 × 2). Lady tasting tea: [[3, 1], [1, 3]].

p = 34/70 (two-sided). Conditional MLE odds ratio and 95% CI computed with 40-digit
arithmetic (mpmath): 6.40831965820 [0.211735595447, 626.243530589]. R's fisher.test
reports an upper bound of 621.93 because its root finder stops at ~1e-4.
"""

import pytest

from aistat.errors import InvalidState
from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis, write_dataset

VARS = {"row": "guess", "column": "truth"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "tea_tasting.csv", "wards.csv")


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_lady_tasting_tea(ws, engine):
    _, res = run_analysis(ws, "fisher-exact", VARS, engine, dataset_id="tea_tasting")

    s = res["statistics"]
    assert s["observed"] == [[3, 1], [1, 3]]
    assert s["p"] == pytest.approx(34 / 70, abs=1e-12)
    assert s["odds_ratio"] == pytest.approx(6.40831965820, rel=1e-9)
    assert s["ci_lower"] == pytest.approx(0.211735595447, rel=1e-9)
    assert s["ci_upper"] == pytest.approx(626.243530589, rel=1e-9)


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_zero_cell_gives_boundary_estimate(ws, tmp_path, engine):
    rows = ["a,b"] + ["x,y"] * 5 + ["z,w"] * 4 + ["z,y"] * 1
    write_dataset(ws, tmp_path, "zero.csv", "\n".join(rows) + "\n")

    _, res = run_analysis(ws, "fisher-exact", {"row": "a", "column": "b"}, engine, dataset_id="zero")

    s = res["statistics"]
    assert s["observed"] == [[0, 5], [4, 1]]  # rows x, z; columns w, y
    assert s["odds_ratio"] == 0
    assert s["ci_lower"] == 0
    assert 0 < s["ci_upper"] < 1


@requires_r
def test_r_and_python_agree(ws):
    _, r = run_analysis(ws, "fisher-exact", VARS, "r", dataset_id="tea_tasting")
    _, py = run_analysis(ws, "fisher-exact", VARS, "python", dataset_id="tea_tasting")

    assert_same_numbers(r["statistics"], py["statistics"])


def test_more_than_two_categories_is_blocked(ws, tmp_path):
    write_dataset(ws, tmp_path, "three.csv", "a,b\nx,y\nx,w\nz,y\nq,w\nq,y\nz,w\n")

    run = ws.create_plan("fisher-exact", {"row": "a", "column": "b"}, dataset_id="three")

    assert run.status == "BLOCKED"
    assert check(ws.method_review(run.id), "group_structure").verdict == "NO"
    with pytest.raises(InvalidState):
        ws.approve(run.id, confirm=["independence"])


def test_report_apa_and_passes_gate_b(ws):
    run, _ = run_analysis(ws, "fisher-exact", VARS, "python", dataset_id="tea_tasting")

    text = ws.report(run.id, mode="learning").read_text(encoding="utf-8")

    assert "Fisher's exact test" in text
    assert "p = .486, OR = 6.41, 95% CI [0.21, 626.24]" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")


def test_learning_notes_read_the_interval_not_the_p_value(ws, tmp_path):
    # [[0, 3], [5, 1]]: two-sided p = .048 but the 95% CI [0, 1.44] still contains 1
    rows = ["a,b"] + ["x,y"] * 3 + ["z,w"] * 5 + ["z,y"] * 1
    write_dataset(ws, tmp_path, "edge.csv", "\n".join(rows) + "\n")

    run, res = run_analysis(ws, "fisher-exact", {"row": "a", "column": "b"}, "python", dataset_id="edge")
    ws.report(run.id, mode="learning")

    s = res["statistics"]
    assert s["p"] < 0.05 and s["ci_lower"] <= 1 <= s["ci_upper"]
    notes = (run.dir / "learning_notes.md").read_text(encoding="utf-8")
    assert "包含 1" in notes and "不包含 1" not in notes


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_upper_boundary_gives_infinite_estimate(ws, tmp_path, engine):
    rows = ["a,b"] + ["x,w"] * 5 + ["z,w"] * 1 + ["z,y"] * 4
    write_dataset(ws, tmp_path, "upper.csv", "\n".join(rows) + "\n")

    run, res = run_analysis(ws, "fisher-exact", {"row": "a", "column": "b"}, engine, dataset_id="upper")

    s = res["statistics"]
    assert s["observed"] == [[5, 0], [1, 4]]
    assert s["odds_ratio"] is None and s["ci_upper"] is None
    assert s["odds_ratio_infinite"] is True
    assert s["ci_lower"] > 1
    assert "OR = ∞" in ws.report(run.id).read_text(encoding="utf-8")
