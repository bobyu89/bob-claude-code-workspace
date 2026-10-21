"""Statistical figures: APA-style PNG + SVG next to each run, embedded in the report."""

import json
import subprocess
import sys

import pytest

from conftest import check, make_workspace, run_analysis
from test_all_methods import CASES

pytestmark = pytest.mark.figures

PAIRED = {"before": "drug1", "after": "drug2"}
DATASETS = ("sleep_wide.csv", "sleep_long.csv", "textbook_xy.csv", "nurse_stress.csv", "wards.csv",
            "tea_tasting.csv", "plant_growth.csv")


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, *DATASETS)


def is_png(path):
    return path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_figures_are_written_hashed_and_embedded(ws):
    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")

    info = json.loads((run.dir / "figures" / "figures.json").read_text(encoding="utf-8"))
    first = info["figures"][0]["file"]
    assert is_png(run.dir / f"{first}.png")
    assert "<svg" in (run.dir / f"{first}.svg").read_text(encoding="utf-8")[:500]
    outputs = ws.get_run(run.id).manifest["outputs"]
    assert "figures.py" in outputs and f"{first}.png" in outputs and f"{first}.svg" in outputs

    text = ws.report(run.id).read_text(encoding="utf-8")
    assert "**Figure 1**" in text
    assert f"![Figure 1]({first}.png)" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")


@pytest.mark.parametrize("method,dataset,variables,options", CASES)
def test_every_method_draws_at_least_one_figure(ws, method, dataset, variables, options):
    run, _ = run_analysis(ws, method, variables, "python", dataset_id=dataset, options=options)

    info = json.loads((run.dir / "figures" / "figures.json").read_text(encoding="utf-8"))
    assert 1 <= len(info["figures"]) <= 2
    for f in info["figures"]:
        assert is_png(run.dir / f"{f['file']}.png")
        assert f["caption"]["zh"] and f["caption"]["en"]


def test_figures_script_can_be_rerun_by_hand(ws):
    run, _ = run_analysis(ws, "one-way-anova", {"outcome": "weight", "group": "group"}, "python",
                          dataset_id="plant_growth")
    for f in (run.dir / "figures").iterdir():
        f.unlink()

    subprocess.run([sys.executable, "figures.py"], cwd=run.dir, check=True, capture_output=True, timeout=120)

    assert is_png(run.dir / "figures" / "figure_1.png")


def test_figure_failure_does_not_block_analysis_or_report(ws, monkeypatch):
    from aistat import figures

    monkeypatch.setattr(figures, "render_script", lambda plan, data: "raise SystemExit('boom: no figures')\n")

    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")

    assert run.status == "EXECUTED"
    assert ws.get_run(run.id).manifest["figures"]["status"] == "failed"
    text = ws.report(run.id).read_text(encoding="utf-8")
    assert "圖表未能產生" in text
    assert not ws.review(run.id, draft=text).by_verdict("NO")


def test_export_refuses_a_modified_figure(ws, tmp_path):
    from aistat.errors import InvalidState

    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")
    ws.report(run.id)
    png = run.dir / "figures" / "figure_1.png"
    png.write_bytes(png.read_bytes() + b"tampered")

    with pytest.raises(InvalidState, match="figure_1.png"):
        ws.export(run.id, tmp_path / "out.zip")


def test_chinese_labels_are_reported_when_no_cjk_font(ws, tmp_path):
    from conftest import write_dataset

    write_dataset(ws, tmp_path, "zh.csv", "前測,後測\n10.5,12\n11,15.5\n9.5,10\n12,14.5\n8,9.5\n")
    run, _ = run_analysis(ws, "paired-t-test", {"before": "前測", "after": "後測"}, "python", dataset_id="zh")

    info = json.loads((run.dir / "figures" / "figures.json").read_text(encoding="utf-8"))
    text = ws.report(run.id).read_text(encoding="utf-8")
    assert info["needs_cjk"] is True
    if info["cjk_font"] is None:
        assert "CJK 字型" in text
    else:
        assert "CJK 字型" not in text


def test_figures_can_be_turned_off(ws, monkeypatch):
    monkeypatch.setenv("AISTAT_FIGURES", "0")

    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")

    assert not (run.dir / "figures").exists()
    assert "**Figure" not in ws.report(run.id).read_text(encoding="utf-8")
    assert check(ws.review(run.id), "values_traceable").verdict == "YES"


def test_cli_reports_figures_and_can_skip_them(tmp_path):
    from typer.testing import CliRunner

    from aistat.cli import app
    from conftest import GOLDEN

    ws_dir = tmp_path / "proj"

    def invoke(*args):
        return CliRunner().invoke(app, ["--workspace", str(ws_dir), *args])

    invoke("init")
    invoke("import", str(GOLDEN / "sleep_wide.csv"))
    run_ids = []
    for _ in range(2):
        planned = invoke("plan", "--method", "paired-t-test", "--var", "before=drug1", "--var", "after=drug2")
        run_ids.append(next(w for w in planned.output.split() if w.startswith("RUN_")))
        invoke("approve", run_ids[-1], "--confirm", "pairing_structure")

    drawn = invoke("analyze", run_ids[0], "--engine", "python")
    skipped = invoke("analyze", run_ids[1], "--engine", "python", "--no-figures")

    assert drawn.exit_code == 0 and "圖表：1 張" in drawn.output
    assert skipped.exit_code == 0 and "圖表" not in skipped.output
    assert (ws_dir / "runs" / run_ids[0] / "figures").is_dir()
    assert not (ws_dir / "runs" / run_ids[1] / "figures").exists()


def test_multiline_failure_stays_one_code_span(ws, monkeypatch):
    from aistat import figures

    monkeypatch.setattr(figures, "render_script",
                        lambda plan, data: "import sys\nsys.exit('line one `x`\\nline two')\n")

    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")

    text = ws.report(run.id).read_text(encoding="utf-8")
    failure = next(line for line in text.splitlines() if line.startswith("圖表未能產生"))
    assert failure.count("`") == 2 and "line two" in failure
    assert not ws.review(run.id, draft=text).by_verdict("NO")


def test_every_registered_method_has_a_figure_case():
    from aistat.methods import METHODS

    assert {case[0] for case in CASES} == set(METHODS)


def test_chinese_group_levels_count_as_cjk_labels(ws, tmp_path):
    from conftest import write_dataset

    write_dataset(ws, tmp_path, "zh_levels.csv",
                  "score,arm\n" + "".join(f"{10 + i % 5},{'對照組' if i % 2 else '實驗組'}\n" for i in range(12)))
    run, _ = run_analysis(ws, "independent-t-test", {"outcome": "score", "group": "arm"}, "python",
                          dataset_id="zh_levels")

    info = json.loads((run.dir / "figures" / "figures.json").read_text(encoding="utf-8"))
    assert info["needs_cjk"] is True


def test_failed_figures_leave_no_unhashed_files(ws, monkeypatch):
    from aistat import figures

    monkeypatch.setattr(figures, "render_script", lambda plan, data: (
        "import os\nos.makedirs('figures', exist_ok=True)\nopen('figures/figure_1.png', 'wb').write(b'x')\n"
        "raise SystemExit('boom')\n"))

    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")

    assert not (run.dir / "figures").exists()
    assert "figures.py" in ws.get_run(run.id).manifest["outputs"]


def test_report_survives_a_deleted_figures_folder(ws):
    import shutil

    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python", dataset_id="sleep_wide")
    shutil.rmtree(run.dir / "figures")

    text = ws.report(run.id).read_text(encoding="utf-8")

    assert "圖表未能產生" in text


def test_missing_cjk_font_note_passes_gate_b(ws, tmp_path, monkeypatch):
    from aistat import figures
    from conftest import write_dataset

    original = figures.render_script
    monkeypatch.setattr(figures, "render_script", lambda plan, data: original(plan, data).replace(
        "CJK = next((name for name in CJK_FONTS if name in available), None)", "CJK = None"))
    write_dataset(ws, tmp_path, "zh.csv", "前測,後測\n10.5,12\n11,15.5\n9.5,10\n12,14.5\n8,9.5\n")
    run, _ = run_analysis(ws, "paired-t-test", {"before": "前測", "after": "後測"}, "python", dataset_id="zh")

    for lang in ("zh", "en"):
        text = ws.draft_report(run.id, lang=lang)
        assert "CJK" in text and "get_cachedir" in text
        assert not ws.review(run.id, draft=text, lang=lang).by_verdict("NO")
