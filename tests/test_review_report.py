"""JEV Gate B and APA 7 report drafts (paired t-test on R's sleep data)."""

import json

import pytest

from aistat.errors import InvalidState
from conftest import check, make_workspace, run_analysis

PAIRED = {"before": "drug1", "after": "drug2"}


@pytest.fixture
def ws(tmp_path):
    return make_workspace(tmp_path, "sleep_wide.csv")


@pytest.fixture
def run(ws):
    run, _ = run_analysis(ws, "paired-t-test", PAIRED, "python")
    return run


def draft(ws, run):
    return ws.draft_report(run.id)


def test_generated_draft_passes_gate_b(ws, run):
    review = ws.review(run.id)

    assert review.gate == "result_validation"
    for cid in ("engine_provenance", "values_traceable", "p_value_format", "effect_size_ci",
                "causal_language", "significance_consistency"):
        assert check(review, cid).verdict == "YES", (cid, check(review, cid).reason)
    assert ws.get_run(run.id).status == "JEV_GATE_B"
    stored = json.loads((run.dir / "result_review.json").read_text(encoding="utf-8"))
    assert stored["passed"] is True


def test_violated_assumption_is_flagged_with_alternative(ws, run):
    # Shapiro-Wilk on the sleep differences: W = 0.83, p = .033
    assumption = check(ws.review(run.id), "assumptions_met")

    assert assumption.verdict == "UNCERTAIN"
    assert "Wilcoxon" in assumption.reason


def test_fabricated_number_is_caught(ws, run):
    text = draft(ws, run).replace("t(9) = 4.06", "t(9) = 5.12")

    review = ws.review(run.id, draft=text)

    values = check(review, "values_traceable")
    assert values.verdict == "NO"
    assert "5.12" in values.reason
    assert ws.get_run(run.id).status == "EXECUTED"


@pytest.mark.parametrize("bad", ["p = .000", "p = 0.003"])
def test_bad_p_value_format_is_caught(ws, run, bad):
    text = draft(ws, run).replace("p = .003", bad)

    assert check(ws.review(run.id, draft=text), "p_value_format").verdict == "NO"


@pytest.mark.parametrize("phrase", ["這證明 drug2 有效。", "This proves that drug2 caused longer sleep."])
def test_causal_overreach_is_caught(ws, run, phrase):
    text = draft(ws, run) + "\n" + phrase + "\n"

    assert check(ws.review(run.id, draft=text), "causal_language").verdict == "NO"


def test_significance_claim_must_match_p_value(ws, run):
    text = draft(ws, run).replace("差異達統計顯著", "差異未達統計顯著")

    assert check(ws.review(run.id, draft=text), "significance_consistency").verdict == "NO"


def test_tampered_raw_output_fails_provenance(ws, run):
    out = run.dir / "raw_outputs" / "results.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    data["statistics"]["p"] = 0.0001
    out.write_text(json.dumps(data), encoding="utf-8")

    assert check(ws.review(run.id), "engine_provenance").verdict == "NO"


def test_report_writes_apa_draft_and_advances_state(ws, run):
    path = ws.report(run.id)

    text = path.read_text(encoding="utf-8")
    assert path.name == "statistical_report.md"
    assert "t(9) = 4.06, p = .003" in text
    assert "95% CI [0.70, 2.46]" in text
    assert "d_z = 1.28" in text
    assert "JEV" in text
    assert ws.get_run(run.id).status == "REPORT_GENERATED"


def test_final_report_itself_passes_gate_b(ws, run):
    text = ws.report(run.id).read_text(encoding="utf-8")

    review = ws.review(run.id, draft=text)

    assert not review.by_verdict("NO"), review.summary()


def test_english_report(ws, run):
    text = ws.report(run.id, lang="en").read_text(encoding="utf-8")

    assert "paired-samples t test" in text
    assert "statistically significant" in text


def test_report_refuses_draft_that_fails_gate_b(ws, run, tmp_path):
    edited = tmp_path / "edited.md"
    edited.write_text(draft(ws, run).replace("4.06", "4.60"), encoding="utf-8")

    with pytest.raises(InvalidState, match="values_traceable"):
        ws.report(run.id, draft=edited.read_text(encoding="utf-8"))
    assert not (run.dir / "statistical_report.md").exists()


def test_report_accepts_user_edited_draft_that_passes(ws, run, tmp_path):
    edited = tmp_path / "edited.md"
    edited.write_text(draft(ws, run) + "\n本研究樣本為一般受試者。\n", encoding="utf-8")

    text = ws.report(run.id, draft=edited.read_text(encoding="utf-8")).read_text(encoding="utf-8")

    assert "本研究樣本為一般受試者" in text


def test_learning_mode_answers_six_questions_with_users_variables(ws, run):
    ws.report(run.id, mode="learning")

    notes = (run.dir / "learning_notes.md").read_text(encoding="utf-8")
    for q in ("研究問題", "為什麼選擇", "為什麼不選", "統計假設", "效果量與信賴區間", "可以支持什麼結論"):
        assert q in notes, q
    assert "drug1" in notes and "drug2" in notes


def test_review_requires_executed_run(ws):
    run = ws.create_plan("paired-t-test", PAIRED)

    with pytest.raises(InvalidState):
        ws.review(run.id)


def test_short_category_labels_do_not_corrupt_words(tmp_path):
    ws = make_workspace(tmp_path, "wards.csv")
    run, _ = run_analysis(ws, "chi-square", {"row": "ward", "column": "passed"}, "python")

    text = ws.draft_report(run.id, lang="en").replace("was not statistically", "was statistically")

    assert check(ws.review(run.id, draft=text), "significance_consistency").verdict == "NO"
    assert check(ws.review(run.id, lang="en"), "significance_consistency").verdict == "YES"


@pytest.mark.parametrize("sentence,verdict", [
    ("其中一項差異達統計顯著（p = .050）。", "YES"),   # p rounded to α: cannot be checked either way
    ("其中一項差異未達統計顯著（p = .050）。", "YES"),
    ("其中一項差異達統計顯著（p = .060）。", "NO"),
])
def test_p_values_that_round_to_alpha_are_not_judged(ws, run, sentence, verdict):
    text = draft(ws, run) + "\n" + sentence + "\n"

    assert check(ws.review(run.id, draft=text), "significance_consistency").verdict == verdict
