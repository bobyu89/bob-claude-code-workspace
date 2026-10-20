"""Tracer bullet: plan → JEV Gate A → user approval → execution (paired t-test).

Expected values are R's documented `sleep` example:
t = 4.0621, df = 9, p = 0.002833, 95% CI [0.7001142, 2.4598858], mean difference 1.58.
"""

import json
import os
import stat

import pytest

from aistat.errors import AistatError, InvalidState, PlanError
from conftest import check, make_workspace, write_dataset

PAIRED = {"before": "drug1", "after": "drug2"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "sleep_wide.csv")


def approved_run(ws):
    run = ws.create_plan("paired-t-test", PAIRED)
    return ws.approve(run.id, confirm=["pairing_structure"])


def test_plan_creates_run_folder_and_gate_a_asks_to_confirm_pairing(ws):
    run = ws.create_plan("paired-t-test", PAIRED)

    assert run.id.startswith("RUN_") and run.status == "JEV_GATE_A"
    review = ws.method_review(run.id)
    assert not review.passed
    pairing = check(review, "pairing_structure")
    assert pairing.verdict == "UNCERTAIN"
    assert pairing.required_action == "request_user_confirmation"
    for cid in ("variables_exist", "measurement_level", "missing_data", "sample_size", "assumptions_planned"):
        assert check(review, cid).verdict == "YES", cid
    for name in ("analysis_plan.json", "method_review.json", "manifest.json", "execution_log.json",
                 "data_dictionary.csv", "quality_report.md"):
        assert (run.dir / name).is_file(), name
    plan = json.loads((run.dir / "analysis_plan.json").read_text(encoding="utf-8"))
    assert plan["dataset_sha256"] == ws.get_dataset("sleep_wide").sha256
    assert [h["state"] for h in run.history][:4] == ["CREATED", "IMPORTED", "PROFILED", "PLAN_DRAFTED"]


def test_jev_check_records_follow_contract(ws):
    run = ws.create_plan("paired-t-test", PAIRED)

    stored = json.loads((run.dir / "method_review.json").read_text(encoding="utf-8"))

    assert stored["gate"] == "method_validation"
    first = stored["checks"][0]
    assert set(first) >= {"gate", "check_id", "verdict", "evidence", "reason", "required_action"}


def test_approve_without_confirming_uncertain_check_is_refused(ws):
    run = ws.create_plan("paired-t-test", PAIRED)

    with pytest.raises(AistatError, match="pairing_structure"):
        ws.approve(run.id)
    assert ws.get_run(run.id).status == "JEV_GATE_A"


def test_cannot_execute_unapproved_plan(ws):
    run = ws.create_plan("paired-t-test", PAIRED)

    with pytest.raises(InvalidState, match="核准"):
        ws.execute(run.id, engine="python")


def test_approval_records_user_confirmation(ws):
    run = approved_run(ws)

    assert run.status == "USER_APPROVAL"
    assert [c["check_id"] for c in run.confirmations] == ["pairing_structure"]
    assert check(ws.method_review(run.id), "pairing_structure").verdict == "YES"


def test_python_engine_reproduces_known_paired_t_result(ws):
    run = approved_run(ws)

    run = ws.execute(run.id, engine="python")

    assert run.status == "EXECUTED"
    res = ws.results(run.id)
    s = res["statistics"]
    assert res["engine"]["name"] == "python"
    assert s["n"] == 10
    assert s["mean_diff"] == pytest.approx(1.58, abs=1e-9)
    assert s["t"] == pytest.approx(4.0621, abs=1e-4)
    assert s["df"] == 9
    assert s["p"] == pytest.approx(0.002833, abs=1e-6)
    assert s["ci_lower"] == pytest.approx(0.7001142, abs=1e-7)
    assert s["ci_upper"] == pytest.approx(2.4598858, abs=1e-7)
    assert s["sd_diff"] == pytest.approx(1.229995, abs=1e-6)
    assert s["cohens_dz"] == pytest.approx(4.0621 / 10**0.5, abs=1e-4)
    assert res["assumptions"][0]["id"] == "normality_of_differences"
    assert (run.dir / "analysis.py").is_file()
    assert run.manifest["engine"]["name"] == "python"


def test_wrong_measurement_level_blocks_plan(ws):
    ws.set_variable_level("sleep_wide", "drug1", "nominal")

    run = ws.create_plan("paired-t-test", PAIRED)

    assert run.status == "BLOCKED"
    assert check(ws.method_review(run.id), "measurement_level").verdict == "NO"
    with pytest.raises(InvalidState):
        ws.approve(run.id, confirm=["pairing_structure"])


def test_missing_variable_blocks_plan(ws):
    run = ws.create_plan("paired-t-test", {"before": "drug1", "after": "drug3"})

    assert run.status == "BLOCKED"
    assert "drug3" in check(ws.method_review(run.id), "variables_exist").reason


def test_dictionary_change_after_plan_is_caught_at_approval(ws):
    run = ws.create_plan("paired-t-test", PAIRED)
    ws.set_variable_level("sleep_wide", "drug2", "nominal")

    with pytest.raises(AistatError, match="measurement_level"):
        ws.approve(run.id, confirm=["pairing_structure"])
    assert ws.get_run(run.id).status == "BLOCKED"


def test_revalidate_after_fixing_dictionary_unblocks_plan(ws):
    ws.set_variable_level("sleep_wide", "drug1", "nominal")
    run = ws.create_plan("paired-t-test", PAIRED)
    ws.set_variable_level("sleep_wide", "drug1", "scale")

    assert ws.validate_plan(run.id).status == "JEV_GATE_A"


@pytest.mark.parametrize(
    "method,variables,message",
    [
        ("anova", PAIRED, "不支援的統計方法"),
        ("paired-t-test", {"before": "drug1"}, "after"),
        ("paired-t-test", {**PAIRED, "group": "x"}, "group"),
    ],
)
def test_malformed_plan_is_rejected(ws, method, variables, message):
    with pytest.raises(PlanError, match=message):
        ws.create_plan(method, variables)


def test_heavy_missing_data_needs_confirmation(ws, tmp_path):
    write_dataset(ws, tmp_path, "gappy.csv", "pre,post\n1.5,2\n2.5,3\n3,3.5\n,4\n4,\n5.5,6\n6,7\n7,8.5\n")

    run = ws.create_plan("paired-t-test", {"before": "pre", "after": "post"}, dataset_id="gappy")
    missing = check(ws.method_review(run.id), "missing_data")

    assert missing.verdict == "UNCERTAIN"
    assert "2" in missing.reason
    assert ws.approve(run.id, confirm=["pairing_structure", "missing_data"]).status == "USER_APPROVAL"


def test_too_few_pairs_blocks_plan(ws, tmp_path):
    write_dataset(ws, tmp_path, "tiny.csv", "pre,post\n1.5,2\n2.5,3.5\n")

    run = ws.create_plan("paired-t-test", {"before": "pre", "after": "post"}, dataset_id="tiny")

    assert check(ws.method_review(run.id), "sample_size").verdict == "NO"


def test_engine_timeout_marks_run_failed_and_can_be_retried(ws):
    run = approved_run(ws)

    with pytest.raises(AistatError, match="逾時"):
        ws.execute(run.id, engine="python", timeout=0.001)
    assert ws.get_run(run.id).status == "FAILED"
    assert not (run.dir / "raw_outputs" / "results.json").exists()

    assert ws.execute(run.id, engine="python").status == "EXECUTED"


def test_modified_data_is_refused_before_execution(ws):
    run = approved_run(ws)
    data = ws.dataset_dir("sleep_wide") / "data.csv"
    os.chmod(data, stat.S_IRUSR | stat.S_IWUSR)
    data.write_text(data.read_text(encoding="utf-8").replace("0.7", "9.9"), encoding="utf-8")

    with pytest.raises(AistatError, match="雜湊"):
        ws.execute(run.id, engine="python")
    assert ws.get_run(run.id).status == "USER_APPROVAL"


def test_unknown_engine_is_reported(ws):
    run = approved_run(ws)

    with pytest.raises(AistatError, match="spss"):
        ws.execute(run.id, engine="spss")


def test_runs_listing_and_execution_log(ws):
    run = approved_run(ws)
    ws.execute(run.id, engine="python")

    assert [r.id for r in ws.list_runs()] == [run.id]
    events = [e["event"] for e in json.loads((run.dir / "execution_log.json").read_text(encoding="utf-8"))]
    assert "user_confirmation" in events and "engine_finished" in events
    states = [h["state"] for h in ws.get_run(run.id).history]
    assert states[-3:] == ["USER_APPROVAL", "EXECUTING", "EXECUTED"]


def test_malformed_engine_output_marks_run_failed(ws, monkeypatch):
    from aistat.engines.python_engine import PythonEngine

    run = approved_run(ws)

    def broken_run(self, script, data, out, cwd, timeout):
        out.write_text("{not json", encoding="utf-8")

    monkeypatch.setattr(PythonEngine, "run", broken_run)
    with pytest.raises(AistatError, match="格式"):
        ws.execute(run.id, engine="python")
    assert ws.get_run(run.id).status == "FAILED"


def test_manifest_records_plan_parameters(ws):
    run = ws.create_plan("paired-t-test", PAIRED, options={"alpha": 0.01})

    assert run.manifest["parameters"]["variables"] == PAIRED
    assert run.manifest["parameters"]["options"]["alpha"] == 0.01
