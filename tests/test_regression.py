"""Linear regression.

Simple model on textbook data x = 1..5, y = (2, 4, 5, 4, 5): b = SSxy / SSx = 6 / 10 = 0.6,
a = 4 − 0.6 × 3 = 2.2, SSE = 2.4, MSE = 0.8, SE(b) = √(0.8 / 10), R² = 3.6 / 6 = .6, F(1, 3) = 4.5,
SE(a) = √(0.8 × (1/5 + 9/10)) = √0.88, β = r = √.6.
"""

import math

import pytest

from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis, write_dataset

SIMPLE = {"outcome": "score", "predictors": "hours"}
MULTI = {"outcome": "stress", "predictors": "age,years"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "textbook_xy.csv", "nurse_stress.csv")


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_simple_regression_matches_hand_computation(ws, engine):
    _, res = run_analysis(ws, "linear-regression", SIMPLE, engine, dataset_id="textbook_xy")

    s = res["statistics"]
    intercept, slope = s["coefficients"]
    assert intercept["term"] == "(Intercept)" and slope["term"] == "hours"
    assert slope["b"] == pytest.approx(0.6, abs=1e-12)
    assert intercept["b"] == pytest.approx(2.2, abs=1e-12)
    assert slope["se"] == pytest.approx(math.sqrt(0.08), abs=1e-12)
    assert intercept["se"] == pytest.approx(math.sqrt(0.88), abs=1e-12)
    assert slope["beta"] == pytest.approx(math.sqrt(0.6), abs=1e-12)
    assert intercept["beta"] is None
    assert s["r_squared"] == pytest.approx(0.6, abs=1e-12)
    assert s["adj_r_squared"] == pytest.approx(1 - 0.4 * 4 / 3, abs=1e-12)
    assert (s["f"], s["df1"], s["df2"]) == (pytest.approx(4.5, abs=1e-9), 1, 3)
    assert s["f_p"] == pytest.approx(slope["p"], abs=1e-12)
    ids = [a["id"] for a in res["assumptions"]]
    assert ids == ["normality_of_residuals", "homoscedasticity"]


@requires_r
def test_r_and_python_agree_on_multiple_regression(ws):
    _, r = run_analysis(ws, "linear-regression", MULTI, "r", dataset_id="nurse_stress")
    _, py = run_analysis(ws, "linear-regression", MULTI, "python", dataset_id="nurse_stress")

    assert_same_numbers(r["statistics"], py["statistics"])
    assert_same_numbers(r["assumptions"], py["assumptions"])


def test_multiple_regression_flags_collinearity(ws):
    # R: VIF(age) = 19.31; Koenker Breusch-Pagan LM = 4.685
    run, res = run_analysis(ws, "linear-regression", MULTI, "python", dataset_id="nurse_stress")

    vif = next(a for a in res["assumptions"] if a["id"] == "multicollinearity")
    assert vif["statistic"] == pytest.approx(19.31115, abs=1e-4)
    assert vif["violated"] is True
    bp = next(a for a in res["assumptions"] if a["id"] == "homoscedasticity")
    assert bp["statistic"] == pytest.approx(4.685131, abs=1e-5)
    assert check(ws.review(run.id), "assumptions_met").verdict == "UNCERTAIN"


def test_multicategory_nominal_predictor_is_blocked(ws, tmp_path):
    write_dataset(ws, tmp_path, "wards.csv",
                  "y,ward\n1.5,A\n2.5,B\n3.5,C\n4.5,A\n5.5,B\n6.5,C\n7.5,A\n8.5,B\n")

    run = ws.create_plan("linear-regression", {"outcome": "y", "predictors": "ward"}, dataset_id="wards")

    assert run.status == "BLOCKED"


def test_few_cases_per_predictor_needs_confirmation_and_too_few_blocks(ws, tmp_path):
    run = ws.create_plan("linear-regression", SIMPLE, dataset_id="textbook_xy")
    write_dataset(ws, tmp_path, "tiny.csv", "y,a,b\n1.5,1.25,3.5\n2.5,2.75,1.5\n3.75,3.5,2.25\n")
    tiny = ws.create_plan("linear-regression", {"outcome": "y", "predictors": "a,b"}, dataset_id="tiny")

    assert check(ws.method_review(run.id), "sample_size").verdict == "UNCERTAIN"
    assert check(ws.method_review(tiny.id), "sample_size").verdict == "NO"


def test_perfectly_collinear_predictors_fail_clearly(ws, tmp_path):
    from aistat.errors import EngineFailed

    write_dataset(ws, tmp_path, "dup.csv",
                  "y,a,b\n" + "".join(f"{i * 1.5},{i * 0.5},{i * 1.0}\n" for i in range(1, 13)))
    run = ws.create_plan("linear-regression", {"outcome": "y", "predictors": "a,b"}, dataset_id="dup")
    ws.approve(run.id, confirm=[c.check_id for c in ws.method_review(run.id).by_verdict("UNCERTAIN")])

    with pytest.raises(EngineFailed, match="共線"):
        ws.execute(run.id, engine="python")


def test_report_apa_regression(ws):
    run, _ = run_analysis(ws, "linear-regression", SIMPLE, "python", dataset_id="textbook_xy")

    text = ws.report(run.id).read_text(encoding="utf-8")

    assert "F(1, 3) = 4.50, p = .124, R² = .60" in text
    assert "| hours | 0.60 | 0.28 | .77 | 2.12 | .124 | [-0.30, 1.50] |" in text
