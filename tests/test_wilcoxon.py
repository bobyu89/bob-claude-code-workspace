"""Wilcoxon signed-rank test.

Exact case: R ?wilcox.test (Hollander & Wolfe) data, d = x − y has no ties or zeros, n = 9:
V = W+ = 40, two-sided p = .0390625; W− = 5, rank-biserial = 35/45, Z = 17.5/√71.25.
Approximation: R sleep data, d = drug2 − drug1 has one zero (dropped, n = 9) and one tie at 1.3:
W+ = 45, p = 0.009090698 (normal approximation, tie-corrected, continuity-corrected);
σ² = 9·10·19/24 − (2³ − 2)/48 = 71.125, Z = 22.5/√71.125.
"""

import math

import pytest

from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis

HW = {"before": "y", "after": "x"}  # diff = x − y, matching R's wilcox.test(x, y, paired = TRUE)
SLEEP = {"before": "drug1", "after": "drug2"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "hollander_wolfe.csv", "sleep_wide.csv")


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_exact_p_for_small_sample_without_ties(ws, engine):
    _, res = run_analysis(ws, "wilcoxon-signed-rank", HW, engine, dataset_id="hollander_wolfe")

    s = res["statistics"]
    assert (s["n"], s["n_zero"], s["exact"]) == (9, 0, True)
    assert (s["w_plus"], s["w_minus"]) == (40, 5)
    assert s["p"] == pytest.approx(0.0390625, abs=1e-12)
    assert s["rank_biserial"] == pytest.approx(35 / 45, abs=1e-12)
    assert s["z"] == pytest.approx(17.5 / math.sqrt(71.25), abs=1e-12)
    assert s["r"] == pytest.approx(17.5 / math.sqrt(71.25) / 3, abs=1e-12)


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_normal_approximation_with_zero_and_ties(ws, engine):
    _, res = run_analysis(ws, "wilcoxon-signed-rank", SLEEP, engine, dataset_id="sleep_wide")

    s = res["statistics"]
    assert (s["n"], s["n_zero"], s["exact"]) == (9, 1, False)
    assert s["w_plus"] == 45
    assert s["p"] == pytest.approx(0.009090698, abs=1e-9)
    assert s["z"] == pytest.approx(22.5 / math.sqrt(71.125), abs=1e-12)
    assert s["rank_biserial"] == 1
    assert s["median_diff"] == pytest.approx(1.3, abs=1e-12)


@requires_r
@pytest.mark.parametrize("dataset,variables", [("hollander_wolfe", HW), ("sleep_wide", SLEEP)])
def test_r_and_python_agree(ws, dataset, variables):
    _, r = run_analysis(ws, "wilcoxon-signed-rank", variables, "r", dataset_id=dataset)
    _, py = run_analysis(ws, "wilcoxon-signed-rank", variables, "python", dataset_id=dataset)

    assert_same_numbers(r["statistics"], py["statistics"])


def test_accepts_ordinal_scores_and_asks_to_confirm_pairing(ws, tmp_path):
    from conftest import write_dataset

    write_dataset(ws, tmp_path, "likert.csv", "pre,post\n1,3\n2,4\n2,2\n3,5\n1,2\n4,5\n2,3\n")
    ws.set_variable_level("likert", "pre", "ordinal")
    ws.set_variable_level("likert", "post", "ordinal")

    run = ws.create_plan("wilcoxon-signed-rank", {"before": "pre", "after": "post"}, dataset_id="likert")

    review = ws.method_review(run.id)
    assert check(review, "measurement_level").verdict == "YES"
    assert check(review, "pairing_structure").verdict == "UNCERTAIN"


def test_report_apa_and_passes_gate_b(ws):
    run, _ = run_analysis(ws, "wilcoxon-signed-rank", HW, "python", dataset_id="hollander_wolfe")

    text = ws.report(run.id, mode="learning").read_text(encoding="utf-8")

    assert "Wilcoxon signed-rank" in text
    assert "W+ = 40.0, z = 2.07, p = .039, r = .69" in text
    assert "精確" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")
    assert "Wilcoxon" in (run.dir / "learning_notes.md").read_text(encoding="utf-8")
