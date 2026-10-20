import json
import os
import stat
import zipfile

import pytest

from aistat.errors import AistatError, InvalidState
from conftest import make_workspace, run_analysis

PAIRED = {"before": "drug1", "after": "drug2"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "sleep_wide.csv")


@pytest.fixture
def reported(ws):
    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python")
    ws.report(run.id)
    return ws.get_run(run.id)


def test_export_bundle_contains_run_files_but_not_data_by_default(ws, reported, tmp_path):
    bundle = ws.export(reported.id, tmp_path / "out.zip")

    names = zipfile.ZipFile(bundle).namelist()
    prefix = reported.id + "/"
    for f in ("manifest.json", "analysis_plan.json", "method_review.json", "analysis.py",
              "raw_outputs/results.json", "result_review.json", "statistical_report.md", "execution_log.json"):
        assert prefix + f in names, f
    assert not any(n.endswith("data.csv") for n in names)
    assert ws.get_run(reported.id).status == "EXPORTED"


def test_export_manifest_lists_file_hashes(ws, reported, tmp_path):
    bundle = ws.export(reported.id, tmp_path / "out.zip")

    manifest = json.loads(zipfile.ZipFile(bundle).read(f"{reported.id}/manifest.json"))
    assert "statistical_report.md" in manifest["outputs"]
    assert len(manifest["outputs"]["analysis.py"]) == 64
    assert manifest["data_included"] is False


def test_export_with_data_includes_canonical_csv(ws, reported, tmp_path):
    bundle = ws.export(reported.id, tmp_path / "out.zip", include_data=True)

    assert f"{reported.id}/data/data.csv" in zipfile.ZipFile(bundle).namelist()


def test_export_requires_a_report(ws, tmp_path):
    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python")

    with pytest.raises(InvalidState):
        ws.export(run.id, tmp_path / "out.zip")


def test_rerun_reproduces_outputs(ws, reported):
    result = ws.rerun(reported.id)

    assert result.match, result.differences
    assert ws.get_run(reported.id).status == "REPORT_GENERATED"


def test_rerun_detects_changed_script(ws, reported):
    script = reported.dir / "analysis.py"
    script.write_text(script.read_text(encoding="utf-8").replace("confidence_level=O[\"conf_level\"]",
                                                                 "confidence_level=0.9"), encoding="utf-8")

    with pytest.raises(AistatError, match="analysis.py"):
        ws.rerun(reported.id)


def test_rerun_refuses_modified_data(ws, reported):
    data = ws.dataset_dir("sleep_wide") / "data.csv"
    os.chmod(data, stat.S_IRUSR | stat.S_IWUSR)
    data.write_text(data.read_text(encoding="utf-8").replace("3.4", "3.5"), encoding="utf-8")

    with pytest.raises(InvalidState, match="雜湊"):
        ws.rerun(reported.id)


def test_cancel_run(ws):
    run = ws.create_plan("paired-t-test", PAIRED)

    assert ws.cancel(run.id).status == "CANCELLED"
    with pytest.raises(InvalidState):
        ws.approve(run.id, confirm=["pairing_structure"])


def test_export_refuses_tampered_raw_output(ws, reported, tmp_path):
    out = reported.dir / "raw_outputs" / "results.json"
    out.write_text(out.read_text(encoding="utf-8").replace('"n": 10', '"n": 11'), encoding="utf-8")

    with pytest.raises(InvalidState, match="results.json"):
        ws.export(reported.id, tmp_path / "out.zip")


def test_report_edited_after_gate_b_cannot_be_exported(ws, reported, tmp_path):
    report = reported.dir / "statistical_report.md"
    report.write_text(report.read_text(encoding="utf-8") + "\n這證明 drug2 有效（p = .000）。\n", encoding="utf-8")

    with pytest.raises(InvalidState, match="statistical_report.md"):
        ws.export(reported.id, tmp_path / "out.zip")


def test_export_can_be_repeated(ws, reported, tmp_path):
    ws.export(reported.id, tmp_path / "a.zip")

    with pytest.raises(InvalidState):
        ws.review(reported.id)  # exported runs are frozen
    assert ws.export(reported.id, tmp_path / "b.zip").is_file()


def test_failed_export_does_not_mark_run_exported(ws, reported, tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")

    with pytest.raises(OSError):
        ws.export(reported.id, blocker / "out.zip")
    assert ws.get_run(reported.id).status == "REPORT_GENERATED"
