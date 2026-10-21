"""Every method's generated report, in both languages, must pass its own JEV Gate B."""

import pytest

from conftest import make_workspace, run_analysis

CASES = [
    ("descriptives", "sleep_long", {"variables": "extra,drug"}, None),
    ("paired-t-test", "sleep_wide", {"before": "drug1", "after": "drug2"}, None),
    ("independent-t-test", "sleep_long", {"outcome": "extra", "group": "drug"}, None),
    ("chi-square", "wards", {"row": "ward", "column": "passed"}, None),
    ("correlation", "nurse_stress", {"x": "age", "y": "stress"}, None),
    ("correlation", "textbook_xy", {"x": "hours", "y": "score"}, {"method": "spearman"}),
    ("linear-regression", "nurse_stress", {"outcome": "stress", "predictors": "age,years"}, None),
    ("wilcoxon-signed-rank", "sleep_wide", {"before": "drug1", "after": "drug2"}, None),
    ("mann-whitney-u", "sleep_long", {"outcome": "extra", "group": "drug"}, None),
    ("fisher-exact", "tea_tasting", {"row": "guess", "column": "truth"}, None),
]


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("method,dataset,variables,options", CASES)
def test_generated_report_passes_gate_b(tmp_path, method, dataset, variables, options, lang):
    ws = make_workspace(tmp_path, "sleep_wide.csv", "sleep_long.csv", "textbook_xy.csv", "nurse_stress.csv",
                        "wards.csv", "tea_tasting.csv")
    run, _ = run_analysis(ws, method, variables, "python", dataset_id=dataset, options=options)

    text = ws.report(run.id, lang=lang, mode="learning").read_text(encoding="utf-8")

    review = ws.review(run.id, draft=text)
    assert not review.by_verdict("NO"), review.summary()
    assert (run.dir / "learning_notes.md").is_file()
