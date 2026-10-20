"""Workspace: the single core service shared by the CLI and the MCP server.

All rules (state machine, JEV gates, approval) live behind this facade so that
every entry point applies the same statistical rules.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from . import data as datamod
from . import quality
from .audit import append_jsonl, now_iso
from .errors import NotFound, PlanError, WorkspaceNotFound

META_DIR = ".aistat"
WORKSPACE_FILE = "workspace.json"
SCHEMA_VERSION = 1


@dataclass
class Dataset:
    id: str
    source_name: str
    original_file: str
    sha256: str
    data_sha256: str
    n_rows: int
    columns: list[str]
    imported_at: str
    sheet: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Inspection:
    dataset: Dataset
    dictionary: dict[str, datamod.Variable]
    issues: list[quality.Issue]
    preview: pd.DataFrame


@dataclass
class Workspace:
    root: Path
    _datasets: list[Dataset] = field(default_factory=list, repr=False)

    # ---- lifecycle -------------------------------------------------------

    @classmethod
    def init(cls, root: Path | str) -> "Workspace":
        root = Path(root).resolve()
        meta = root / META_DIR
        for d in (meta, root / "data", root / "runs"):
            d.mkdir(parents=True, exist_ok=True)
        if not (meta / WORKSPACE_FILE).exists():
            ws = cls(root)
            ws._save()
            ws._audit("workspace_initialized")
        return cls.open(root)

    @classmethod
    def open(cls, start: Path | str = ".") -> "Workspace":
        start = Path(start).resolve()
        for d in (start, *start.parents):
            f = d / META_DIR / WORKSPACE_FILE
            if f.is_file():
                raw = json.loads(f.read_text(encoding="utf-8"))
                return cls(d, [Dataset(**x) for x in raw.get("datasets", [])])
        raise WorkspaceNotFound(f"{start} 不在 aistat workspace 內。請先執行 `aistat init`。")

    def _save(self) -> None:
        payload = {"schema_version": SCHEMA_VERSION, "datasets": [d.to_dict() for d in self._datasets]}
        (self.root / META_DIR / WORKSPACE_FILE).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _audit(self, event: str, **fields) -> None:
        append_jsonl(self.root / META_DIR / "audit.jsonl", event, **fields)

    # ---- datasets --------------------------------------------------------

    def dataset_dir(self, dataset_id: str) -> Path:
        return self.root / "data" / dataset_id

    def list_datasets(self) -> list[Dataset]:
        return list(self._datasets)

    def get_dataset(self, dataset_id: str | None = None) -> Dataset:
        if dataset_id is None:
            if len(self._datasets) == 1:
                return self._datasets[0]
            if not self._datasets:
                raise NotFound("workspace 內還沒有資料集，請先執行 `aistat import <檔案>`。")
            raise NotFound("workspace 內有多個資料集，請指定資料集 ID（見 `aistat datasets`）。")
        for d in self._datasets:
            if d.id == dataset_id:
                return d
        raise NotFound(f"找不到資料集：{dataset_id}")

    def import_dataset(self, path: Path | str, sheet: str | None = None) -> Dataset:
        path = Path(path)
        df = datamod.read_table(path, sheet=sheet)
        digest = datamod.sha256_file(path)
        for d in self._datasets:
            if d.sha256 == digest and d.sheet == sheet:
                return d

        ds_id = self._new_dataset_id(path.stem)
        target = self.dataset_dir(ds_id)
        target.mkdir(parents=True)
        original = target / f"original{path.suffix.lower()}"
        shutil.copyfile(path, original)
        canonical = target / "data.csv"
        datamod.write_canonical_csv(df, canonical)
        dictionary = datamod.infer_dictionary(df)
        self._write_dictionary(ds_id, dictionary)
        for f in (original, canonical):
            _make_read_only(f)

        ds = Dataset(
            id=ds_id,
            source_name=path.name,
            original_file=original.name,
            sha256=digest,
            data_sha256=datamod.sha256_file(canonical),
            n_rows=len(df),
            columns=list(df.columns),
            imported_at=now_iso(),
            sheet=sheet,
        )
        self._datasets.append(ds)
        self._save()
        self._audit("dataset_imported", dataset_id=ds_id, sha256=digest, n_rows=ds.n_rows, n_columns=len(ds.columns))
        return ds

    def _new_dataset_id(self, stem: str) -> str:
        base = re.sub(r"[^\w]+", "_", stem, flags=re.UNICODE).strip("_") or "dataset"
        taken = {d.id for d in self._datasets}
        if base not in taken:
            return base
        n = 2
        while f"{base}_{n}" in taken:
            n += 1
        return f"{base}_{n}"

    # ---- data dictionary -------------------------------------------------

    def get_dictionary(self, dataset_id: str | None = None) -> dict[str, datamod.Variable]:
        ds = self.get_dataset(dataset_id)
        raw = json.loads((self.dataset_dir(ds.id) / "dictionary.json").read_text(encoding="utf-8"))
        return {v["name"]: datamod.Variable(**v) for v in raw}

    def set_variable_level(self, dataset_id: str | None, variable: str, level: str) -> datamod.Variable:
        ds = self.get_dataset(dataset_id)
        if level not in datamod.LEVELS:
            raise PlanError(f"不合法的測量尺度：{level}（可用 {', '.join(datamod.LEVELS)}）")
        dictionary = self.get_dictionary(ds.id)
        if variable not in dictionary:
            raise NotFound(f"找不到變項：{variable}（資料集 {ds.id}）")
        var = dictionary[variable]
        old = var.level
        var.level, var.level_source, var.ambiguous = level, "user", False
        self._write_dictionary(ds.id, dictionary)
        self._audit("variable_level_set", dataset_id=ds.id, variable=variable, old=old, new=level)
        return var

    def export_dictionary(self, dataset_id: str | None, path: Path | str) -> Path:
        dictionary = self.get_dictionary(dataset_id)
        path = Path(path)
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(datamod.Variable.__dataclass_fields__))
            w.writeheader()
            for v in dictionary.values():
                w.writerow(v.to_dict())
        return path

    # ---- inspection ------------------------------------------------------

    def load_data(self, dataset_id: str | None = None):
        ds = self.get_dataset(dataset_id)
        return datamod.read_canonical_csv(self.dataset_dir(ds.id) / "data.csv")

    def inspect(self, dataset_id: str | None = None, preview_rows: int = 5) -> Inspection:
        ds = self.get_dataset(dataset_id)
        df = self.load_data(ds.id)
        dictionary = self.get_dictionary(ds.id)
        return Inspection(ds, dictionary, quality.find_issues(df, dictionary), df.head(preview_rows))

    def quality_report(self, dataset_id: str | None = None) -> str:
        result = self.inspect(dataset_id)
        return quality.quality_report_markdown(result.dataset, result.dictionary, result.issues)

    def _write_dictionary(self, dataset_id: str, dictionary: dict[str, datamod.Variable]) -> None:
        (self.dataset_dir(dataset_id) / "dictionary.json").write_text(
            json.dumps([v.to_dict() for v in dictionary.values()], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _make_read_only(path: Path) -> None:
    mode = os.stat(path).st_mode
    os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
