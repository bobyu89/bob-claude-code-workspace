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


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_games_howell_matches_an_independent_implementation(ws, engine):
    # pingouin.pairwise_gameshowell on PlantGrowth (computed once, independent code base):
    # ctrl–trt1 p = .4745549222, df = 16.5235851; ctrl–trt2 p = .1128891769; trt1–trt2 p = .0237034547, df = 14.1035691.
    # rstatix reports trt2 − trt1 95% CI [0.114, 1.62].
    _, res = run_analysis(ws, "one-way-anova", VARS, engine, dataset_id="plant_growth")

    gh = res["statistics"]["games_howell"]
    assert pair(gh, "ctrl", "trt1")["p"] == pytest.approx(0.4745549222, abs=1e-6)
    assert pair(gh, "ctrl", "trt1")["df"] == pytest.approx(16.5235850569, abs=1e-8)
    assert pair(gh, "ctrl", "trt2")["p"] == pytest.approx(0.1128891769, abs=1e-6)
    t12 = pair(gh, "trt1", "trt2")
    assert t12["p"] == pytest.approx(0.0237034547, abs=1e-6)
    assert t12["df"] == pytest.approx(14.1035691228, abs=1e-8)
    assert (t12["ci_lower"], t12["ci_upper"]) == pytest.approx((0.114, 1.62), abs=5e-3)


def test_effect_sizes_match_hand_computation(ws):
    # R anova(): SS_between = 3.76634, SS_within = 10.49209, df_within = 27 → MS_within = 0.388596.
    _, res = run_analysis(ws, "one-way-anova", VARS, "python", dataset_id="plant_growth")

    s = res["statistics"]
    assert s["eta_squared"] == pytest.approx(0.2641482968, abs=1e-6)  # also pingouin's np2
    assert s["omega_squared"] == pytest.approx(0.204079, abs=1e-5)


@pytest.mark.parametrize("engine", ["python", pytest.param("r", marks=requires_r)])
def test_zero_variance_group_falls_back_to_classic_f(ws, tmp_path, engine):
    write_dataset(ws, tmp_path, "flat.csv", "y,g\n5,a\n5,a\n5,a\n1,b\n2,b\n3,b\n4,c\n6,c\n8,c\n")

    run, res = run_analysis(ws, "one-way-anova", {"outcome": "y", "group": "g"}, engine, dataset_id="flat")
    text = ws.report(run.id).read_text(encoding="utf-8")

    assert res["statistics"]["welch"]["p"] is None
    assert "無法計算" in text and "F(2, 6)" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")


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

    with pytest.raises(PlanError, match="Kruskal-Wallis.*尚未支援"):
        ws.create_alternative_plan(run.id)


def test_report_apa_and_passes_gate_b(ws):
    run, _ = run_analysis(ws, "one-way-anova", VARS, "python", dataset_id="plant_growth")

    text = ws.report(run.id, mode="learning").read_text(encoding="utf-8")

    assert "Welch F(2, 17.13) = 5.18, p = .017" in text
    assert "F(2, 27) = 4.85, p = .016" in text
    assert "Games-Howell" in text and "Tukey HSD" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")
    assert "Games-Howell" in (run.dir / "learning_notes.md").read_text(encoding="utf-8")
