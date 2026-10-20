"""Files written to a run folder follow the published JSON Schemas (the data contract shared by
CLI, MCP and future GUIs)."""

import json
from pathlib import Path

import pytest

from conftest import make_workspace, run_analysis

jsonschema = pytest.importorskip("jsonschema")
SCHEMAS = Path(__file__).parent.parent / "schemas"


def validate(path, schema_name):
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), schema)


@pytest.mark.parametrize("method,dataset,variables", [
    ("paired-t-test", "sleep_wide", {"before": "drug1", "after": "drug2"}),
    ("chi-square", "wards", {"row": "ward", "column": "passed"}),
    ("linear-regression", "nurse_stress", {"outcome": "stress", "predictors": "age,years"}),
    ("descriptives", "sleep_long", {"variables": "extra,drug"}),
])
def test_run_files_match_schemas(tmp_path, method, dataset, variables):
    ws = make_workspace(tmp_path, f"{dataset}.csv")
    run, _ = run_analysis(ws, method, variables, "python")
    ws.report(run.id)

    validate(run.dir / "analysis_plan.json", "analysis_plan.schema.json")
    validate(run.dir / "method_review.json", "jev_review.schema.json")
    validate(run.dir / "result_review.json", "jev_review.schema.json")
    validate(run.dir / "raw_outputs" / "results.json", "results.schema.json")
    validate(run.dir / "manifest.json", "manifest.schema.json")
