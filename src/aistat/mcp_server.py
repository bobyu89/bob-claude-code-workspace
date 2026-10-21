"""MCP server: a thin tool interface over the same Workspace core the CLI uses.

There is deliberately no approval tool. An agent can draft and validate a plan,
but the researcher approves it with `aistat approve` before anything runs.
"""

from __future__ import annotations

import argparse
import functools
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__, methods, reporting
from .errors import AistatError
from .validation import UNCERTAIN
from .workspace import DEFAULT_TIMEOUT, Workspace

INSTRUCTIONS = """\
aistat：可重現、可審查的統計分析。所有統計數值都必須來自 execute_statistical_analysis 的引擎輸出，
不可自行計算或編造。流程：list_datasets → inspect_dataset → create_analysis_plan（JEV Gate A）→
請研究者本人在終端機執行 `aistat approve <RUN> --confirm ...` → execute_statistical_analysis →
review_statistical_results（JEV Gate B）→ generate_statistical_report → export_analysis_bundle。
不要把個別受試者資料貼到對話中；inspect_dataset 預設不回傳資料列。"""


def _next_step(run, review) -> str:
    if run.status == "BLOCKED":
        return "Gate A 有 NO 項目：請依理由修正（例如 `aistat dictionary set`）後呼叫 validate_analysis_plan，或建立新計畫。"
    pending = "".join(f" --confirm {c.check_id}" for c in review.by_verdict(UNCERTAIN))
    return (f"請把 Gate A 結果說明給研究者，由研究者本人確認後在終端機執行：aistat approve {run.id}{pending}。"
            "核准後才能呼叫 execute_statistical_analysis。")


def create_server(workspace: Path | str) -> MCPServer:
    root = Path(workspace)
    server = MCPServer("aistat", instructions=INSTRUCTIONS, version=__version__)

    def ws() -> Workspace:
        return Workspace.open(root)

    def tool(fn):
        """Register a tool whose aistat errors reach the agent as readable tool errors."""
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except AistatError as e:
                raise ToolError(str(e)) from e

        return server.tool()(wrapper)

    @tool
    def list_methods() -> dict:
        """List supported statistical methods with their variable roles and options."""
        return {"methods": [
            {"id": m.id, "name_zh": m.name_zh, "name_en": m.name_en,
             "roles": [{"name": r.name, "label": r.label, "levels": list(r.levels), "multiple": r.multiple}
                       for r in m.roles],
             "options": {k: list(v) for k, v in m.options.items()} | methods.COMMON_OPTIONS}
            for m in methods.METHODS.values()
        ]}

    @tool
    def list_datasets() -> dict:
        """List imported datasets (id, rows, columns, SHA-256)."""
        return {"datasets": [d.to_dict() for d in ws().list_datasets()]}

    @tool
    def inspect_dataset(dataset_id: str | None = None, include_preview: bool = False) -> dict:
        """Data dictionary and quality issues. Rows are returned only with include_preview=True;
        do not request them for identifiable patient data without authorisation."""
        result = ws().inspect(dataset_id)
        out = {
            "dataset": result.dataset.to_dict(),
            "dictionary": [v.to_dict() for v in result.dictionary.values()],
            "issues": [i.to_dict() for i in result.issues],
        }
        if include_preview:
            out["preview"] = result.preview.astype(object).where(result.preview.notna(), None).to_dict("records")
        return out

    @tool
    def get_data_dictionary(dataset_id: str | None = None) -> dict:
        """Variables with type, measurement level (and whether the user confirmed it) and missing counts."""
        return {"variables": [v.to_dict() for v in ws().get_dictionary(dataset_id).values()]}

    @tool
    def create_analysis_plan(method: str | None = None, variables: dict | None = None, dataset_id: str | None = None,
                             options: dict | None = None, alternative_of: str | None = None) -> dict:
        """Draft an analysis plan and run JEV Gate A. `variables` maps roles to columns,
        e.g. {"before": "pre", "after": "post"}. With `alternative_of` (a run ID), draft the
        alternative method for that run instead (e.g. Wilcoxon for a paired t test whose
        assumptions failed), reusing its dataset and variables. Approval must come from the researcher."""
        w = ws()
        if alternative_of:
            if method or variables or dataset_id or options:
                raise ToolError("alternative_of 會沿用原計畫的資料集與變項，不能同時提供 method、variables、dataset_id 或 options。")
            run = w.create_alternative_plan(alternative_of)
        elif method and variables:
            run = w.create_plan(method, variables, dataset_id=dataset_id, options=options)
        else:
            raise ToolError("請提供 method 與 variables，或提供 alternative_of。")
        review = w.method_review(run.id)
        return {"run_id": run.id, "method": run.plan["method"], "status": run.status, "gate_a": review.to_dict(),
                "next_step": _next_step(run, review)}

    @tool
    def validate_analysis_plan(run_id: str) -> dict:
        """Re-run JEV Gate A against the current data dictionary."""
        w = ws()
        run = w.validate_plan(run_id)
        review = w.method_review(run.id)
        return {"run_id": run.id, "status": run.status, "gate_a": review.to_dict(), "next_step": _next_step(run, review)}

    @tool
    def execute_statistical_analysis(run_id: str, engine: str = "auto", timeout: float = DEFAULT_TIMEOUT) -> dict:
        """Run an approved plan on a real statistical engine (r | python | auto)."""
        w = ws()
        run = w.execute(run_id, engine=engine, timeout=timeout)
        results = w.results(run.id)
        return {"run_id": run.id, "status": run.status, "engine": results["engine"],
                "summary": reporting.headline(run.plan, results)}

    @tool
    def retrieve_analysis_results(run_id: str) -> dict:
        """The engine's raw output (raw_outputs/results.json) — the only valid source of numbers."""
        return ws().results(run_id)

    @tool
    def review_statistical_results(run_id: str, draft: str | None = None, lang: str = "zh") -> dict:
        """JEV Gate B on the generated draft, or on `draft` text you (re)wrote."""
        review = ws().review(run_id, draft=draft, lang=lang)
        return review.to_dict()

    @tool
    def generate_statistical_report(run_id: str, lang: str = "zh", mode: str = "research",
                                    draft: str | None = None) -> dict:
        """Write statistical_report.md after Gate B passes; mode="learning" also writes learning_notes.md.
        A supplied `draft` must itself pass Gate B."""
        path = ws().report(run_id, lang=lang, mode=mode, draft=draft)
        out = {"path": str(path), "report": path.read_text(encoding="utf-8")}
        notes = path.parent / "learning_notes.md"
        if mode == "learning":
            out["learning_notes"] = notes.read_text(encoding="utf-8")
        return out

    @tool
    def export_analysis_bundle(run_id: str, include_data: bool = False) -> dict:
        """Zip the run folder. Set include_data only when the researcher confirms data sharing is authorised."""
        path = ws().export(run_id, include_data=include_data)
        return {"path": str(path), "data_included": include_data}

    return server


def main() -> None:
    parser = argparse.ArgumentParser(prog="aistat-mcp", description="aistat MCP server (stdio)")
    parser.add_argument("--workspace", default=os.environ.get("AISTAT_WORKSPACE", "."))
    args = parser.parse_args()
    create_server(Workspace.open(args.workspace).root).run("stdio")


if __name__ == "__main__":
    main()
