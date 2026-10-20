"""Engine adapters: R and Python must agree with known values and with each other."""

import pytest

from aistat.errors import EngineUnavailable
from conftest import assert_same_numbers, make_workspace, requires_r, run_analysis

PAIRED = {"before": "drug1", "after": "drug2"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "sleep_wide.csv")


@requires_r
def test_r_engine_reproduces_known_paired_t_result(ws):
    run, res = run_analysis(ws, "paired-t-test", PAIRED, "r")

    s = res["statistics"]
    assert res["engine"]["name"] == "r"
    assert res["engine"]["version"].startswith("R version")
    assert s["t"] == pytest.approx(4.0621, abs=1e-4)
    assert s["p"] == pytest.approx(0.002833, abs=1e-6)
    assert (s["ci_lower"], s["ci_upper"]) == pytest.approx((0.7001142, 2.4598858), abs=1e-7)
    assert (run.dir / "analysis.R").is_file()


@requires_r
def test_r_and_python_engines_agree_on_paired_t(ws):
    _, r = run_analysis(ws, "paired-t-test", PAIRED, "r")
    _, py = run_analysis(ws, "paired-t-test", PAIRED, "python")

    assert_same_numbers(r["statistics"], py["statistics"])
    assert_same_numbers(r["assumptions"], py["assumptions"])


@requires_r
def test_auto_engine_prefers_r(ws):
    run, res = run_analysis(ws, "paired-t-test", PAIRED, "auto")

    assert res["engine"]["name"] == "r"


def test_missing_r_is_reported_and_run_stays_approved(ws, monkeypatch):
    run = ws.create_plan("paired-t-test", PAIRED)
    ws.approve(run.id, confirm=["pairing_structure"])
    monkeypatch.setenv("PATH", "")

    with pytest.raises(EngineUnavailable, match="Rscript"):
        ws.execute(run.id, engine="r")
    assert ws.get_run(run.id).status == "USER_APPROVAL"


def test_auto_falls_back_to_python_without_r(ws, monkeypatch):
    monkeypatch.setenv("PATH", "")

    _, res = run_analysis(ws, "paired-t-test", PAIRED, "auto")

    assert res["engine"]["name"] == "python"


@requires_r
def test_unicode_column_names_survive_r_engine(ws, tmp_path):
    from conftest import write_dataset

    write_dataset(ws, tmp_path, "zh.csv", "前測,後測\n10.5,12\n11,15.5\n9.5,10\n12,14.5\n8,9.5\n")

    _, res = run_analysis(ws, "paired-t-test", {"before": "前測", "after": "後測"}, "r", dataset_id="zh")

    assert res["statistics"]["n"] == 5
