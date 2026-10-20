"""Workspace: the single core service shared by the CLI and the MCP server.

All rules (state machine, JEV gates, approval) live behind this facade so that
every entry point applies the same statistical rules.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

import time

import pandas as pd

from . import data as datamod
from . import engines, methods, quality, reporting, validation
from .audit import append_jsonl, now_iso
from .errors import EngineFailed, InvalidState, NotFound, PlanError, WorkspaceNotFound
from .runs import Run

META_DIR = ".aistat"
WORKSPACE_FILE = "workspace.json"
SCHEMA_VERSION = 1
DEFAULT_TIMEOUT = 120.0
REVIEWABLE = ("EXECUTED", "JEV_GATE_B", "REPORT_GENERATED", "EXPORTED")
LANGS = ("zh", "en")


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

    # ---- runs: plan and JEV Gate A ---------------------------------------

    def runs_dir(self) -> Path:
        return self.root / "runs"

    def list_runs(self) -> list[Run]:
        return [Run(p) for p in sorted(self.runs_dir().iterdir()) if (p / "manifest.json").is_file()]

    def get_run(self, run_id: str) -> Run:
        path = self.runs_dir() / run_id
        if not (path / "manifest.json").is_file():
            raise NotFound(f"找不到分析紀錄：{run_id}（見 `aistat runs`）")
        return Run(path)

    def create_plan(self, method: str, variables: dict, dataset_id: str | None = None,
                    options: dict | None = None) -> Run:
        spec = methods.get_method(method)
        variables = methods.normalize_variables(spec, variables)
        options = methods.resolve_options(spec, options)
        ds = self.get_dataset(dataset_id)

        run = Run.create(self.runs_dir(), {"id": ds.id, "source_name": ds.source_name,
                                           "sha256": ds.sha256, "data_sha256": ds.data_sha256})
        run.set_status("IMPORTED", dataset_id=ds.id, sha256=ds.sha256)
        self.export_dictionary(ds.id, run.dir / "data_dictionary.csv")
        run.write_text("quality_report.md", self.quality_report(ds.id))
        run.set_status("PROFILED")

        plan = {
            "run_id": run.id,
            "dataset_id": ds.id,
            "dataset_sha256": ds.sha256,
            "data_sha256": ds.data_sha256,
            "method": spec.id,
            "variables": variables,
            "options": options,
            "missing_strategy": spec.missing_strategy,
            "assumptions": [a.id for a in spec.assumptions],
            "string_columns": [],
        }
        run.write_json("analysis_plan.json", plan)
        run.manifest["method"] = spec.id
        run.set_status("PLAN_DRAFTED", method=spec.id)
        self._audit("plan_created", run_id=run.id, dataset_id=ds.id, method=spec.id)
        return self.validate_plan(run.id)

    def _gate_a(self, run: Run, confirmations: list[dict]) -> validation.Review:
        plan = run.plan
        spec = methods.get_method(plan["method"])
        return validation.gate_a(plan, spec, self.load_data(plan["dataset_id"]),
                                 self.get_dictionary(plan["dataset_id"]), confirmations)

    def _record_gate_a(self, run: Run, review: validation.Review) -> None:
        run.write_json("method_review.json", {**review.to_dict(), "run_id": run.id, "evaluated_at": now_iso()})
        run.log("jev_gate_a", passed=review.passed,
                verdicts={c.check_id: c.verdict for c in review.checks})
        run.set_status("BLOCKED" if review.by_verdict(validation.NO) else "JEV_GATE_A")

    def validate_plan(self, run_id: str) -> Run:
        """Run (or re-run) JEV Gate A against the current data dictionary."""
        run = self.get_run(run_id)
        run.require("PLAN_DRAFTED", "JEV_GATE_A", "BLOCKED", action="重新驗證分析計畫")
        self._record_gate_a(run, self._gate_a(run, run.confirmations))
        return run

    def method_review(self, run_id: str) -> validation.Review:
        return validation.Review.from_dict(self.get_run(run_id).read_json("method_review.json"))

    def approve(self, run_id: str, confirm: list[str] | tuple[str, ...] = ()) -> Run:
        """Human approval. Confirms UNCERTAIN checks; refuses while any check is NO.

        Deliberately not exposed through MCP: approval must come from the user.
        """
        run = self.get_run(run_id)
        run.require("JEV_GATE_A", "BLOCKED", action="核准", hint="請先建立並驗證分析計畫。")
        raw = self._gate_a(run, [])
        blocking = raw.by_verdict(validation.NO)
        if blocking:
            self._record_gate_a(run, self._gate_a(run, run.confirmations))
            raise InvalidState("JEV Gate A 未通過，無法核准：\n" + "\n".join(
                f"[NO] {c.check_id}：{c.reason}" for c in blocking))

        confirmable = {c.check_id for c in raw.by_verdict(validation.UNCERTAIN)}
        unknown = sorted(set(confirm) - confirmable)
        if unknown:
            raise PlanError(f"沒有需要確認的項目：{', '.join(unknown)}（需要確認：{', '.join(sorted(confirmable)) or '無'}）")
        already = {c["check_id"] for c in run.confirmations}
        for check_id in confirm:
            if check_id in already:
                continue
            record = {"check_id": check_id, "ts": now_iso(), "by": "user"}
            run.confirmations.append(record)
            run.log("user_confirmation", **record)
        run.save()

        review = self._gate_a(run, run.confirmations)
        self._record_gate_a(run, review)
        pending = review.by_verdict(validation.UNCERTAIN)
        if pending:
            raise PlanError("尚有需要確認的項目，確認後請加上 --confirm <check_id>：\n" + "\n".join(
                f"[UNCERTAIN] {c.check_id}：{c.reason}" for c in pending))
        run.set_status("USER_APPROVAL", by="user")
        self._audit("plan_approved", run_id=run.id, confirmations=[c["check_id"] for c in run.confirmations])
        return run

    # ---- runs: execution -------------------------------------------------

    def execute(self, run_id: str, engine: str = "auto", timeout: float = DEFAULT_TIMEOUT) -> Run:
        run = self.get_run(run_id)
        run.require("USER_APPROVAL", "FAILED", action="執行分析",
                    hint="分析計畫須經使用者核准（`aistat approve`）後才能執行。")
        plan = run.plan
        data_path = self.dataset_dir(plan["dataset_id"]) / "data.csv"
        current = datamod.sha256_file(data_path)
        if current != plan["data_sha256"]:
            raise InvalidState(f"資料雜湊與分析計畫不符（計畫 {plan['data_sha256'][:12]}…，目前 {current[:12]}…）；"
                               "資料可能已被修改，拒絕執行。")
        adapter = engines.get_engine(engine)

        run.set_status("EXECUTING", engine=adapter.name)
        script = run.write_text(adapter.script_name, adapter.render_script(plan, _relpath(data_path, run.dir)))
        out = run.dir / "raw_outputs" / "results.json"
        out.parent.mkdir(exist_ok=True)
        out.unlink(missing_ok=True)
        run.log("engine_started", engine=adapter.name, script=adapter.script_name, timeout_s=timeout)
        started = time.monotonic()
        try:
            adapter.run(script, data_path, out, cwd=run.dir, timeout=timeout)
            results = json.loads(out.read_text(encoding="utf-8"))
            if results.get("method") != plan["method"] or "engine" not in results:
                raise EngineFailed("引擎輸出格式不符（缺少 engine 或 method 不一致）")
        except EngineFailed as e:
            out.unlink(missing_ok=True)
            run.log("engine_failed", engine=adapter.name, error=str(e))
            run.set_status("FAILED", error=str(e))
            raise
        duration = round(time.monotonic() - started, 3)
        run.manifest["engine"] = results["engine"]
        run.manifest["outputs"] = {
            "raw_outputs/results.json": datamod.sha256_file(out),
            adapter.script_name: datamod.sha256_file(script),
        }
        run.manifest["executed_data_sha256"] = current
        run.save()
        run.log("engine_finished", engine=adapter.name, version=results["engine"].get("version"),
                duration_s=duration, warnings=results.get("warnings", []))
        run.set_status("EXECUTED", engine=adapter.name)
        self._audit("analysis_executed", run_id=run.id, engine=adapter.name)
        return run

    def results(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        path = run.dir / "raw_outputs" / "results.json"
        if not path.is_file():
            raise InvalidState(f"{run.id} 尚未有分析結果（狀態 {run.status}）")
        return json.loads(path.read_text(encoding="utf-8"))

    # ---- runs: JEV Gate B and reports ------------------------------------

    def draft_report(self, run_id: str, lang: str = "zh") -> str:
        run = self.get_run(run_id)
        _check_lang(lang)
        plan = run.plan
        return reporting.build_draft(plan, self.results(run.id), run.manifest, methods.get_method(plan["method"]), lang)

    def review(self, run_id: str, draft: str | None = None, lang: str = "zh") -> validation.Review:
        """JEV Gate B on a report draft (the generated one unless `draft` text is given)."""
        run = self.get_run(run_id)
        run.require(*REVIEWABLE, action="審查結果", hint="請先執行分析（`aistat analyze`）。")
        plan = run.plan
        out = run.dir / "raw_outputs" / "results.json"
        results = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
        text = draft if draft is not None else self.draft_report(run.id, lang)
        provenance = validation.Provenance(
            results_exists=out.is_file(),
            results_sha256=datamod.sha256_file(out) if out.is_file() else None,
            recorded_sha256=run.manifest["outputs"].get("raw_outputs/results.json"),
            plan_data_sha256=plan["data_sha256"],
            executed_data_sha256=run.manifest.get("executed_data_sha256"),
            current_data_sha256=datamod.sha256_file(self.dataset_dir(plan["dataset_id"]) / "data.csv"),
        )
        review = validation.gate_b(plan, methods.get_method(plan["method"]), results, text, provenance,
                                   reporting.method_report(plan["method"]))
        run.write_json("result_review.json", {
            **review.to_dict(), "run_id": run.id, "evaluated_at": now_iso(),
            "draft_source": "generated" if draft is None else "supplied",
            "draft_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })
        run.log("jev_gate_b", passed=review.passed, verdicts={c.check_id: c.verdict for c in review.checks})
        if run.status in ("EXECUTED", "JEV_GATE_B"):
            run.set_status("JEV_GATE_B" if review.passed else "EXECUTED")
        return review

    def report(self, run_id: str, lang: str = "zh", mode: str = "research",
               draft_path: Path | str | None = None) -> Path:
        """Write statistical_report.md (and learning_notes.md in learning mode) after Gate B passes."""
        run = self.get_run(run_id)
        _check_lang(lang)
        if mode not in ("research", "learning"):
            raise PlanError(f"不支援的模式：{mode}（可用 research、learning）")
        run.require("EXECUTED", "JEV_GATE_B", "REPORT_GENERATED", action="產生報告",
                    hint="請先執行分析；已匯出的分析請建立新的 run。")
        text = Path(draft_path).read_text(encoding="utf-8") if draft_path else self.draft_report(run.id, lang)
        text = text.split(reporting.JEV_HEADING, 1)[0].rstrip() + "\n"
        review = self.review(run.id, draft=text if draft_path else None, lang=lang)
        run = self.get_run(run.id)  # review() advanced the state on disk
        if not review.passed:
            raise InvalidState("JEV Gate B 未通過，不產生報告：\n" + "\n".join(
                f"[NO] {c.check_id}：{c.reason}" for c in review.by_verdict(validation.NO)))
        path = run.write_text("statistical_report.md", text + "\n" + reporting.jev_appendix(review, lang))
        if mode == "learning":
            plan = run.plan
            run.write_text("learning_notes.md", reporting.method_report(plan["method"]).learning(
                plan, self.results(run.id), methods.get_method(plan["method"])))
        run.log("report_generated", lang=lang, mode=mode, draft_source="supplied" if draft_path else "generated")
        run.set_status("REPORT_GENERATED")
        return path

    def _write_dictionary(self, dataset_id: str, dictionary: dict[str, datamod.Variable]) -> None:
        (self.dataset_dir(dataset_id) / "dictionary.json").write_text(
            json.dumps([v.to_dict() for v in dictionary.values()], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _check_lang(lang: str) -> None:
    if lang not in LANGS:
        raise PlanError(f"不支援的報告語言：{lang}（可用 {', '.join(LANGS)}）")


def _relpath(target: Path, start: Path) -> str:
    return Path(os.path.relpath(target, start)).as_posix()


def _make_read_only(path: Path) -> None:
    mode = os.stat(path).st_mode
    os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
