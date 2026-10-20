"""`aistat` command line. Thin layer: parse arguments, call Workspace, print."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Optional

import typer

from . import reporting
from .errors import AistatError, PlanError
from .workspace import Workspace

app = typer.Typer(
    help="AI-native 開源統計分析平台。所有統計數值由實際統計引擎計算。",
    no_args_is_help=True,
    add_completion=False,
)

_state: dict = {"workspace": Path(".")}


@app.callback()
def _root(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w", help="workspace 路徑（預設為目前目錄）"),
) -> None:
    _state["workspace"] = workspace


def _ws() -> Workspace:
    return Workspace.open(_state["workspace"])


def handles_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AistatError as e:
            typer.secho(f"錯誤：{e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    return wrapper


@app.command()
@handles_errors
def init() -> None:
    """建立 workspace（.aistat/、data/、runs/）。"""
    ws = Workspace.init(_state["workspace"])
    typer.echo(f"已建立 workspace：{ws.root}")


@app.command("import")
@handles_errors
def import_(
    path: Path = typer.Argument(..., help="CSV 或 Excel（.xlsx）檔案"),
    sheet: Optional[str] = typer.Option(None, help="Excel 工作表名稱（預設第一個）"),
) -> None:
    """匯入研究資料；原始檔保存為唯讀副本並記錄 SHA-256。"""
    ds = _ws().import_dataset(path, sheet=sheet)
    typer.echo(f"資料集 {ds.id}：{ds.n_rows} 列 × {len(ds.columns)} 欄（SHA-256 {ds.sha256[:12]}…）")


@app.command()
@handles_errors
def datasets() -> None:
    """列出已匯入的資料集。"""
    items = _ws().list_datasets()
    if not items:
        typer.echo("尚未匯入資料集。")
        return
    for d in items:
        typer.echo(f"{d.id}\t{d.n_rows} 列\t{len(d.columns)} 欄\t{d.source_name}\t{d.imported_at}")


@app.command()
@handles_errors
def inspect(
    dataset: Optional[str] = typer.Argument(None, help="資料集 ID（只有一個時可省略）"),
    rows: int = typer.Option(5, help="預覽列數"),
    report: Optional[Path] = typer.Option(None, help="把品質報告寫成 Markdown 檔"),
) -> None:
    """資料預覽、資料字典與品質檢查。"""
    ws = _ws()
    result = ws.inspect(dataset, preview_rows=rows)
    ds = result.dataset
    typer.echo(f"資料集 {ds.id}：{ds.n_rows} 列 × {len(ds.columns)} 欄\n")
    typer.echo(result.preview.to_string(index=False))
    typer.echo("\n變項\t型態\t尺度\t缺失\t相異值")
    for v in result.dictionary.values():
        level = v.level + ("?" if v.ambiguous else "") + ("（使用者確認）" if v.level_source == "user" else "")
        typer.echo(f"{v.name}\t{v.type}\t{level}\t{v.n_missing}\t{v.n_unique}")
    typer.echo("\n品質問題：" if result.issues else "\n未發現結構性問題。")
    for i in result.issues:
        typer.echo(f"  [{i.code}] {i.message}")
    if report:
        report.write_text(ws.quality_report(ds.id), encoding="utf-8")
        typer.echo(f"\n品質報告已寫入 {report}")


dictionary_app = typer.Typer(help="資料字典：修正測量尺度、匯出。", no_args_is_help=True)
app.add_typer(dictionary_app, name="dictionary")


@dictionary_app.command("set")
@handles_errors
def dictionary_set(
    variable: str = typer.Argument(...),
    level: str = typer.Option(..., help="nominal | ordinal | scale"),
    dataset: Optional[str] = typer.Option(None, help="資料集 ID"),
) -> None:
    """以使用者確認的測量尺度取代系統推論。"""
    var = _ws().set_variable_level(dataset, variable, level)
    typer.echo(f"{var.name} 的測量尺度已設為 {var.level}（使用者確認）")


@dictionary_app.command("export")
@handles_errors
def dictionary_export(
    path: Path = typer.Argument(Path("data_dictionary.csv")),
    dataset: Optional[str] = typer.Option(None, help="資料集 ID"),
) -> None:
    """匯出 data_dictionary.csv。"""
    typer.echo(f"資料字典已寫入 {_ws().export_dictionary(dataset, path)}")


def _pairs(items: list[str], what: str) -> dict:
    out = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise PlanError(f"{what} 格式應為 role=欄位（例：--var before=pre_score），收到：{item}")
        out[key.strip()] = value.strip()
    return out


def _print_review(review) -> None:
    for c in review.checks:
        color = {"YES": typer.colors.GREEN, "NO": typer.colors.RED}.get(c.verdict, typer.colors.YELLOW)
        typer.secho(f"  [{c.verdict}] {c.check_id}：{c.reason}", fg=color)


def _print_gate_a_next_step(ws: Workspace, run) -> None:
    review = ws.method_review(run.id)
    typer.echo(f"{run.id}  狀態 {run.status}\nJEV Gate A（分析執行前審查）：")
    _print_review(review)
    if run.status == "BLOCKED":
        typer.echo("\n計畫被擋下：請依 NO 項目修正（例如 `aistat dictionary set`）後執行 "
                   f"`aistat validate {run.id}`，或建立新計畫。")
    elif run.status == "JEV_GATE_A":
        pending = [c.check_id for c in review.by_verdict("UNCERTAIN")]
        confirm = "".join(f" --confirm {c}" for c in pending)
        typer.echo(f"\n確認上述內容無誤後，請由研究者本人核准：aistat approve {run.id}{confirm}")


@app.command()
@handles_errors
def plan(
    method: str = typer.Option(..., help="統計方法，例如 paired-t-test"),
    var: list[str] = typer.Option([], "--var", help="變項角色，role=欄位，可重複"),
    option: list[str] = typer.Option([], "--option", help="方法選項，key=value，可重複"),
    dataset: Optional[str] = typer.Option(None, help="資料集 ID"),
) -> None:
    """建立分析計畫並執行 JEV Gate A。"""
    ws = _ws()
    run = ws.create_plan(method, _pairs(var, "--var"), dataset_id=dataset, options=_pairs(option, "--option"))
    _print_gate_a_next_step(ws, run)


@app.command()
@handles_errors
def validate(run_id: str) -> None:
    """依目前資料字典重新執行 JEV Gate A。"""
    ws = _ws()
    _print_gate_a_next_step(ws, ws.validate_plan(run_id))


@app.command()
@handles_errors
def approve(
    run_id: str,
    confirm: list[str] = typer.Option([], "--confirm", help="確認 UNCERTAIN 項目的 check_id，可重複"),
) -> None:
    """研究者核准分析計畫（確認 UNCERTAIN 項目）。"""
    run = _ws().approve(run_id, confirm=confirm)
    typer.echo(f"{run.id} 已核准。下一步：aistat analyze {run.id}")


@app.command()
@handles_errors
def analyze(
    run_id: str,
    engine: str = typer.Option("auto", help="auto | r | python"),
    timeout: float = typer.Option(120.0, help="引擎逾時秒數"),
) -> None:
    """以實際統計引擎執行已核准的分析計畫。"""
    ws = _ws()
    run = ws.execute(run_id, engine=engine, timeout=timeout)
    results = ws.results(run.id)
    typer.echo(f"{run.id} 已由 {results['engine']['version']} 執行完成。")
    typer.echo(reporting.headline(run.plan, results))
    for a in results.get("assumptions", []):
        flag = "違反" if a.get("violated") else ("未檢定" if a.get("violated") is None else "符合")
        typer.echo(f"  假設檢查 {a['label']}（{a['test']}）：{flag}")
    typer.echo(f"下一步：aistat review {run.id}")


@app.command()
@handles_errors
def runs() -> None:
    """列出所有分析紀錄。"""
    items = _ws().list_runs()
    if not items:
        typer.echo("尚無分析紀錄。")
    for r in items:
        typer.echo(f"{r.id}\t{r.status}\t{r.manifest['method']}\t{r.manifest['dataset']['id']}")


@app.command()
@handles_errors
def status(run_id: str) -> None:
    """顯示分析紀錄的狀態歷程。"""
    run = _ws().get_run(run_id)
    typer.echo(f"{run.id}  {run.manifest['method']}  資料集 {run.manifest['dataset']['id']}  狀態 {run.status}")
    for h in run.history:
        typer.echo(f"  {h['ts']}  {h['state']}")


@app.command()
@handles_errors
def review(
    run_id: str,
    draft: Optional[Path] = typer.Option(None, help="審查自行（或 AI）改寫的草稿，而非系統產生的草稿"),
    lang: str = typer.Option("zh", help="zh | en"),
) -> None:
    """JEV Gate B：報告輸出前審查。"""
    ws = _ws()
    text = draft.read_text(encoding="utf-8") if draft else None
    result = ws.review(run_id, draft=text, lang=lang)
    typer.echo("JEV Gate B（報告輸出前審查）：")
    _print_review(result)
    if result.passed:
        typer.echo(f"\n通過。下一步：aistat report {run_id}")
    else:
        typer.echo("\n未通過：請修正 NO 項目。")
        raise typer.Exit(1)


@app.command()
@handles_errors
def report(
    run_id: str,
    lang: str = typer.Option("zh", help="zh | en"),
    mode: str = typer.Option("research", help="research | learning（另產生 learning_notes.md）"),
    draft: Optional[Path] = typer.Option(None, help="以改寫過的草稿作為報告（仍須通過 Gate B）"),
) -> None:
    """通過 Gate B 後產生 APA 7 統計結果草稿。"""
    ws = _ws()
    text = draft.read_text(encoding="utf-8") if draft else None
    path = ws.report(run_id, lang=lang, mode=mode, draft=text)
    typer.echo(f"報告已寫入 {path}")
    if mode == "learning":
        typer.echo(f"學習筆記已寫入 {path.parent / 'learning_notes.md'}")


@app.command()
@handles_errors
def export(
    run_id: str,
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="zip 路徑（預設 exports/<RUN>.zip）"),
    include_data: bool = typer.Option(False, "--include-data", help="把資料一併放入成果包（需確認已獲授權）"),
) -> None:
    """匯出成果包；預設不含研究資料，只含雜湊。"""
    path = _ws().export(run_id, output, include_data=include_data)
    typer.echo(f"成果包已寫入 {path}" + ("（含資料）" if include_data else "（不含資料）"))


@app.command()
@handles_errors
def rerun(run_id: str, timeout: float = typer.Option(120.0, help="引擎逾時秒數")) -> None:
    """以相同程式碼與資料重新執行，核對輸出是否一致。"""
    result = _ws().rerun(run_id, timeout=timeout)
    if result.match:
        typer.echo(f"{run_id} 重新執行結果與原始輸出一致（{result.engine_version}）。")
        return
    typer.secho(f"{run_id} 重新執行結果不一致：", fg=typer.colors.RED)
    for d in result.differences:
        typer.echo(f"  {d}")
    if result.engine_version != result.original_engine_version:
        typer.echo(f"  引擎版本不同：{result.original_engine_version} → {result.engine_version}")
    raise typer.Exit(1)


@app.command()
@handles_errors
def cancel(run_id: str) -> None:
    """取消分析紀錄。"""
    _ws().cancel(run_id)
    typer.echo(f"{run_id} 已取消。")


def main() -> None:
    app()
