"""`aistat` command line. Thin layer: parse arguments, call Workspace, print."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Optional

import typer

from .errors import AistatError
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


def main() -> None:
    app()
