"""Data quality checks: structural profiling, not inferential statistics."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import pandas as pd

from .data import Variable

HIGH_MISSING_RATIO = 0.20
ID_NAME = re.compile(r"(^id$|id$|_id|^id_|_no$|^no$|number|編號|代號|序號|學號|病歷號)", re.IGNORECASE)


@dataclass
class Issue:
    code: str
    variable: str | None
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def find_issues(df: pd.DataFrame, dictionary: dict[str, Variable]) -> list[Issue]:
    issues: list[Issue] = []
    n = len(df)
    for name, var in dictionary.items():
        if n and var.n_missing / n > HIGH_MISSING_RATIO:
            issues.append(Issue("high_missing", name, f"{name} 缺失 {var.n_missing}/{n}（{var.n_missing / n:.0%}）"))
        if var.n_unique <= 1:
            issues.append(Issue("constant", name, f"{name} 只有 {var.n_unique} 個相異值，無法用於分析"))
        if _looks_like_id(name, df[name], var):
            issues.append(Issue("possible_id", name, f"{name} 每列都不同，疑似 ID 欄；請勿當作分析變項，並確認已去識別化"))
        if var.ambiguous:
            issues.append(
                Issue(
                    "ambiguous_level",
                    name,
                    f"{name} 推論為 {var.level}，但可能是其他尺度；"
                    f"請以 `aistat dictionary set {name} --level <nominal|ordinal|scale>` 確認",
                )
            )
    dup = int(df.duplicated().sum())
    if dup:
        issues.append(Issue("duplicate_rows", None, f"有 {dup} 列與前面某列完全重複"))
    return issues


def _looks_like_id(name: str, s: pd.Series, var: Variable) -> bool:
    n = len(s)
    if n < 5 or var.n_missing or var.n_unique != n:
        return False
    if var.type == "string":
        return True
    is_integer = bool((s == s.round()).all())
    return is_integer and bool(ID_NAME.search(name))


def quality_report_markdown(dataset, dictionary: dict[str, Variable], issues: list[Issue]) -> str:
    lines = [
        f"# 資料品質報告：{dataset.id}",
        "",
        f"- 來源檔案：{dataset.source_name}" + (f"（工作表 {dataset.sheet}）" if dataset.sheet else ""),
        f"- 列數 × 欄數：{dataset.n_rows} × {len(dataset.columns)}",
        f"- 原始檔 SHA-256：`{dataset.sha256}`",
        f"- 匯入時間：{dataset.imported_at}",
        "",
        "## 變項（Variables）",
        "",
        "| 變項 | 型態 | 測量尺度 | 尺度來源 | 缺失 | 相異值 |",
        "|---|---|---|---|---|---|",
    ]
    for v in dictionary.values():
        level = v.level + ("（待確認）" if v.ambiguous else "")
        source = "使用者確認" if v.level_source == "user" else "系統推論"
        lines.append(f"| {v.name} | {v.type} | {level} | {source} | {v.n_missing} | {v.n_unique} |")
    lines += ["", "## 問題（Issues）", ""]
    if issues:
        lines += [f"- [{i.code}] {i.message}" for i in issues]
    else:
        lines.append("未發現結構性問題。")
    lines.append("")
    return "\n".join(lines)
