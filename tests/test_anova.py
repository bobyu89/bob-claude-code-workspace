"""One-way ANOVA. Reference: R's built-in PlantGrowth data (weight ~ group, 3 × 10).

Classic F(2, 27) = 4.8461, p = .01591, SS_between = 3.7663, SS_within = 10.4921.
Welch (oneway.test): F = 5.181, df = (2, 17.128), p = .01739.
TukeyHSD: trt2 − trt1 = 0.865, 95% CI [0.1738, 1.5562], p = .0120.
"""

import pytest

from aistat.errors import PlanError
from conftest import assert_same_numbers, check, make_workspace, requires_r, run_analysis, write_dataset

VARS = {"outcome": "weight", "group": "group"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "plant_growth.csv", "sleep_long.csv")


def pair(rows, g1, g2):
    return next(r for r in rows if (r["group1"], r["group2"]) == (g1, g2))


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_plant_growth_matches_r_documentation(ws, engine):
    _, res = run_analysis(ws, "one-way-anova", VARS, engine, dataset_id="plant_growth")

    s = res["statistics"]
    assert [g["level"] for g in s["groups"]] == ["ctrl", "trt1", "trt2"]
    c = s["classic"]
    assert (c["df1"], c["df2"]) == (2, 27)
    assert c["f"] == pytest.approx(4.8461, abs=1e-4)
    assert c["p"] == pytest.approx(0.01591, abs=1e-5)
    assert c["ss_between"] == pytest.approx(3.76634, abs=1e-5)
    w = s["welch"]
    assert w["f"] == pytest.approx(5.181, abs=1e-3)
    assert w["df2"] == pytest.approx(17.128, abs=1e-3)
    assert w["p"] == pytest.approx(0.01739, abs=1e-5)
    t = pair(s["tukey"], "trt1", "trt2")
    assert t["diff"] == pytest.approx(0.865, abs=1e-9)
    assert (t["ci_lower"], t["ci_upper"]) == pytest.approx((0.1737839, 1.5562161), abs=1e-6)
    assert t["p"] == pytest.approx(0.0120064, abs=1e-6)
    assert s["eta_squared"] == pytest.approx(3.76634 / (3.76634 + 10.49209), abs=1e-5)
    assert len(s["games_howell"]) == 3


def test_games_howell_matches_hand_computation(ws):
    # trt1 vs trt2 from the group summaries (Welch-type SE and df, studentized range p).
    import math

    from scipy import stats as st

    _, res = run_analysis(ws, "one-way-anova", VARS, "python", dataset_id="plant_growth")
    s = res["statistics"]
    g = {x["level"]: x for x in s["groups"]}
    a, b = g["trt1"], g["trt2"]
    va, vb = a["sd"] ** 2 / a["n"], b["sd"] ** 2 / b["n"]
    se = math.sqrt((va + vb) / 2)
    df = (va + vb) ** 2 / (va ** 2 / (a["n"] - 1) + vb ** 2 / (b["n"] - 1))
    gh = pair(s["games_howell"], "trt1", "trt2")
    assert gh["diff"] == pytest.approx(b["mean"] - a["mean"], abs=1e-12)
    assert gh["df"] == pytest.approx(df, rel=1e-12)
    assert gh["p"] == pytest.approx(st.studentized_range.sf(abs(gh["diff"]) / se, 3, df), rel=1e-9)


@requires_r
def test_r_and_python_agree(ws):
    _, r = run_analysis(ws, "one-way-anova", VARS, "r", dataset_id="plant_growth")
    _, py = run_analysis(ws, "one-way-anova", VARS, "python", dataset_id="plant_growth")

    assert_same_numbers(r["statistics"], py["statistics"])
    assert_same_numbers(r["assumptions"], py["assumptions"])


def test_two_groups_are_redirected_to_t_test(ws):
    run = ws.create_plan("one-way-anova", {"outcome": "extra", "group": "drug"}, dataset_id="sleep_long")

    structure = check(ws.method_review(run.id), "group_structure")
    assert structure.verdict == "NO"
    assert "independent-t-test" in structure.reason


def test_groups_need_two_cases_each(ws, tmp_path):
    write_dataset(ws, tmp_path, "thin.csv", "y,g\n1.5,a\n2.5,a\n3.5,b\n4.5,b\n5.5,c\n")

    run = ws.create_plan("one-way-anova", {"outcome": "y", "group": "g"}, dataset_id="thin")

    assert check(ws.method_review(run.id), "group_structure").verdict == "NO"


def test_no_alternative_plan_yet(ws):
    run = ws.create_plan("one-way-anova", VARS, dataset_id="plant_growth")

    with pytest.raises(PlanError, match="替代"):
        ws.create_alternative_plan(run.id)


def test_report_apa_and_passes_gate_b(ws):
    run, _ = run_analysis(ws, "one-way-anova", VARS, "python", dataset_id="plant_growth")

    text = ws.report(run.id, mode="learning").read_text(encoding="utf-8")

    assert "Welch F(2, 17.13) = 5.18, p = .017" in text
    assert "F(2, 27) = 4.85, p = .016" in text
    assert "Games-Howell" in text and "Tukey HSD" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")
    assert "Games-Howell" in (run.dir / "learning_notes.md").read_text(encoding="utf-8")
