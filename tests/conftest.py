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
