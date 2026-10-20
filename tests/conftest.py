import shutil
from pathlib import Path

import pytest

from aistat.workspace import Workspace

GOLDEN = Path(__file__).parent / "golden_cases"

requires_r = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")


def make_workspace(tmp_path, *golden_files):
    ws = Workspace.init(tmp_path / "proj")
    for name in golden_files:
        ws.import_dataset(GOLDEN / name)
    return ws


def write_dataset(ws, tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return ws.import_dataset(path)


def check(review, check_id):
    return next(c for c in review.checks if c.check_id == check_id)


def run_analysis(ws, method, variables, engine, dataset_id=None, options=None):
    """Plan → confirm every UNCERTAIN check → execute. Returns (run, results)."""
    run = ws.create_plan(method, variables, dataset_id=dataset_id, options=options)
    pending = [c.check_id for c in ws.method_review(run.id).by_verdict("UNCERTAIN")]
    ws.approve(run.id, confirm=pending)
    run = ws.execute(run.id, engine=engine)
    return run, ws.results(run.id)


def assert_same_numbers(a, b, rel=1e-6, path="statistics"):
    """Recursively compare two engines' outputs."""
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys differ {set(a) ^ set(b)}"
        for k in a:
            assert_same_numbers(a[k], b[k], rel, f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), f"{path}: length differs"
        for i, (x, y) in enumerate(zip(a, b)):
            assert_same_numbers(x, y, rel, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool) and b is not None:
        assert b == pytest.approx(a, rel=rel, abs=1e-9), f"{path}: {a} != {b}"
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"
