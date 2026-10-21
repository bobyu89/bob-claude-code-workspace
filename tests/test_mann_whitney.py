"""Mann-Whitney U test.

Exact case: R ?wilcox.test two-sample example (10 vs 5, no ties): W = U(A) = 35, p = .2544;
rank-biserial = 2·35/50 − 1 = .4, Z = (35 − 25)/√(50·16/12).
Approximation: R sleep data (ties at −0.1, 0.8 and 3.4): U(drug1) = 25.5, p = 0.06932758;
σ² = 100/12 · (21 − 18/(20·19)), Z = −24.5/σ, rank-biserial = 51/100 − 1 = −.49.
"""

import math

import pytest

from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis

PERM = {"outcome": "value", "group": "membrane"}
SLEEP = {"outcome": "extra", "group": "drug"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "permeability.csv", "sleep_long.csv")


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_exact_p_without_ties(ws, engine):
    _, res = run_analysis(ws, "mann-whitney-u", PERM, engine, dataset_id="permeability")

    s = res["statistics"]
    assert [g["level"] for g in s["groups"]] == ["A", "B"]
    assert [g["n"] for g in s["groups"]] == [10, 5]
    assert (s["u"], s["exact"]) == (35, True)
    assert s["p"] == pytest.approx(0.2544122544, abs=1e-9)
    assert s["rank_biserial"] == pytest.approx(0.4, abs=1e-12)
    assert s["z"] == pytest.approx(10 / math.sqrt(50 * 16 / 12), abs=1e-12)
    assert s["r"] == pytest.approx(10 / math.sqrt(50 * 16 / 12) / math.sqrt(15), abs=1e-12)


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_normal_approximation_with_ties(ws, engine):
    _, res = run_analysis(ws, "mann-whitney-u", SLEEP, engine, dataset_id="sleep_long")

    s = res["statistics"]
    sigma = math.sqrt(100 / 12 * (21 - 18 / (20 * 19)))
    assert (s["u"], s["exact"]) == (25.5, False)
    assert s["p"] == pytest.approx(0.06932758, abs=1e-8)
    assert s["z"] == pytest.approx(-24.5 / sigma, abs=1e-12)
    assert s["rank_biserial"] == pytest.approx(-0.49, abs=1e-12)
    assert s["groups"][0]["median"] == pytest.approx(0.35, abs=1e-12)


@requires_r
@pytest.mark.parametrize("dataset,variables", [("permeability", PERM), ("sleep_long", SLEEP)])
def test_r_and_python_agree(ws, dataset, variables):
    _, r = run_analysis(ws, "mann-whitney-u", variables, "r", dataset_id=dataset)
    _, py = run_analysis(ws, "mann-whitney-u", variables, "python", dataset_id=dataset)

    assert_same_numbers(r["statistics"], py["statistics"])


def test_gate_a_requires_two_groups_and_independence(ws):
    run = ws.create_plan("mann-whitney-u", SLEEP, dataset_id="sleep_long")

    review = ws.method_review(run.id)
    assert check(review, "group_structure").verdict == "YES"
    assert check(review, "independence").verdict == "UNCERTAIN"


def test_report_apa_and_passes_gate_b(ws):
    run, _ = run_analysis(ws, "mann-whitney-u", SLEEP, "python", dataset_id="sleep_long")

    text = ws.report(run.id, mode="learning").read_text(encoding="utf-8")

    assert "U = 25.5, z = -1.85, p = .069, r = -.41" in text
    assert "常態近似" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")
