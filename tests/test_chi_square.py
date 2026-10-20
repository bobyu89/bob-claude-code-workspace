"""Chi-square test of independence.

Hand-computed 2 × 2 example: A = (20 yes, 30 no), B = (15 yes, 35 no); expected counts
17.5 / 32.5; χ² = 2 × 2.5²/17.5 + 2 × 2.5²/32.5 = 1.0989, df = 1, p = .2945, V = √(χ²/N) = .1048.
"""

import pytest

from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis, write_dataset

VARS = {"row": "ward", "column": "passed"}


def table_csv(cells):
    rows = ["ward,passed"]
    for (ward, passed), count in cells.items():
        rows += [f"{ward},{passed}"] * count
    return "\n".join(rows) + "\n"


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "wards.csv")


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_engine_reproduces_hand_computed_chi_square(ws, engine):
    _, res = run_analysis(ws, "chi-square", VARS, engine)

    s = res["statistics"]
    assert s["row_levels"] == ["A", "B"] and s["column_levels"] == ["no", "yes"]
    assert s["observed"] == [[30, 20], [35, 15]]
    assert s["expected"] == [[32.5, 17.5], [32.5, 17.5]]
    assert s["chi2"] == pytest.approx(1.0989011, abs=1e-6)
    assert s["df"] == 1
    assert s["p"] == pytest.approx(0.2945, abs=1e-4)
    assert s["cramers_v"] == pytest.approx(0.1048285, abs=1e-6)
    assert res["assumptions"][0]["id"] == "expected_counts"
    assert res["assumptions"][0]["violated"] is False


@requires_r
def test_r_and_python_agree(ws):
    _, r = run_analysis(ws, "chi-square", VARS, "r")
    _, py = run_analysis(ws, "chi-square", VARS, "python")

    assert_same_numbers(r["statistics"], py["statistics"])
    assert_same_numbers(r["assumptions"], py["assumptions"])


def test_gate_a_requires_categorical_variables_and_independence(ws, tmp_path):
    write_dataset(ws, tmp_path, "mixed.csv", "ward,score\nA,1.5\nB,2.25\nA,3.5\nB,4.75\n")

    run = ws.create_plan("chi-square", {"row": "ward", "column": "score"}, dataset_id="mixed")
    good = ws.create_plan("chi-square", VARS, dataset_id="wards")

    assert check(ws.method_review(run.id), "measurement_level").verdict == "NO"
    assert check(ws.method_review(good.id), "independence").verdict == "UNCERTAIN"


def test_sparse_table_flags_expected_counts(ws, tmp_path):
    write_dataset(ws, tmp_path, "sparse.csv",
                  table_csv({("A", "yes"): 1, ("A", "no"): 6, ("B", "yes"): 5, ("B", "no"): 2}))

    run, res = run_analysis(ws, "chi-square", VARS, "python", dataset_id="sparse")

    assert res["assumptions"][0]["violated"] is True
    assumption = check(ws.review(run.id), "assumptions_met")
    assert assumption.verdict == "UNCERTAIN" and "Fisher" in assumption.reason


def test_report_contains_apa_chi_square_and_table(ws):
    run, _ = run_analysis(ws, "chi-square", VARS, "python")

    text = ws.report(run.id).read_text(encoding="utf-8")

    assert "χ²(1, N = 100) = 1.10, p = .295, Cramér's V = .10" in text
    assert "| A | 30（60.0%） | 20（40.0%） |" in text
    assert "未達統計顯著" in text
