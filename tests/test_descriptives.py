"""Descriptive statistics. Hand values for score = (1, 2, 3, 4, 10, missing):
n = 5, mean = 4, SD = √(50 / 4) = 3.5355, type-7 quartiles 2 / 3 / 4, range 1–10."""

import math

import pytest

from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis, write_dataset

CSV = "score,sex,likert\n1,F,1\n2,M,2\n3,F,2\n4,F,3\n10,M,5\n,F,4\n"
VARS = {"variables": "score,sex,likert"}


@pytest.fixture
def ws(tmp_path):
    ws = make_workspace(tmp_path)
    write_dataset(ws, tmp_path, "sample.csv", CSV)
    ws.set_variable_level("sample", "score", "scale")
    return ws


def by_name(res, name):
    return next(v for v in res["statistics"]["variables"] if v["name"] == name)


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_numeric_and_categorical_summaries(ws, engine):
    _, res = run_analysis(ws, "descriptives", VARS, engine)

    score = by_name(res, "score")
    assert score["kind"] == "numeric"
    assert (score["n"], score["missing"]) == (5, 1)
    assert score["mean"] == pytest.approx(4.0, abs=1e-12)
    assert score["sd"] == pytest.approx(math.sqrt(12.5), abs=1e-12)
    assert (score["q1"], score["median"], score["q3"]) == (2, 3, 4)
    assert (score["min"], score["max"]) == (1, 10)
    sex = by_name(res, "sex")
    assert sex["kind"] == "categorical"
    assert [(f["level"], f["count"]) for f in sex["frequencies"]] == [("F", 4), ("M", 2)]
    assert sex["frequencies"][0]["proportion"] == pytest.approx(4 / 6)
    assert by_name(res, "likert")["kind"] == "categorical"


@requires_r
def test_r_and_python_agree(ws):
    _, r = run_analysis(ws, "descriptives", VARS, "r")
    _, py = run_analysis(ws, "descriptives", VARS, "python")

    assert_same_numbers(r["statistics"], py["statistics"])


def test_gate_a_uses_available_cases(ws):
    run = ws.create_plan("descriptives", VARS)

    review = ws.method_review(run.id)
    assert review.passed
    assert run.status == "JEV_GATE_A"
    assert "score" in check(review, "missing_data").reason


def test_report_tables_pass_gate_b(ws):
    run, _ = run_analysis(ws, "descriptives", VARS, "python")

    text = ws.report(run.id).read_text(encoding="utf-8")

    assert "| score | 5 | 1 | 4.00 | 3.54 | 3.00 | 2.00–4.00 | 1.00–10.00 |" in text
    assert "| sex | F | 4 | 66.7% |" in text
