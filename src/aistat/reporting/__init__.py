"""Turning engine raw outputs into APA 7 text.

Every number in a report is formatted from results.json by `apa`; JEV Gate B
re-checks that claim on whatever draft text is finally used. One module per
method family holds the wording; this module holds the shared report layout.
"""

from __future__ import annotations

from .. import apa
from ..methods import MethodSpec, alternative_command
from ..validation import UNCERTAIN
from .anova import AnovaReport
from .association import CorrelationReport, RegressionReport
from .categorical import ChiSquareReport, FisherReport
from .common import ALTERNATIVES_EN, Effect
from .descriptives import DescriptivesReport
from .nonparametric import MannWhitneyReport, WilcoxonReport
from .ttests import IndependentReport, PairedReport

JEV_HEADING = "## JEV 審查紀錄（JEV Review）"
CITATION_TOKENS = {"1988"}  # Cohen (1988), the only literal numbers the templates write
DISCLAIMER = {
    "zh": "JEV 屬於流程審查機制，並非統計正確性的絕對保證。所有數值由統計引擎計算，請研究者自行確認研究設計與結論。",
    "en": "JEV is a process review, not a guarantee of statistical correctness. All values were computed by "
          "the statistical engine; the researcher remains responsible for the design and conclusions.",
}

REPORTS = {
    "descriptives": DescriptivesReport(),
    "paired-t-test": PairedReport(),
    "wilcoxon-signed-rank": WilcoxonReport(),
    "independent-t-test": IndependentReport(),
    "mann-whitney-u": MannWhitneyReport(),
    "one-way-anova": AnovaReport(),
    "chi-square": ChiSquareReport(),
    "fisher-exact": FisherReport(),
    "correlation": CorrelationReport(),
    "linear-regression": RegressionReport(),
}

__all__ = ["JEV_HEADING", "CITATION_TOKENS", "DISCLAIMER", "REPORTS", "Effect", "method_report", "headline",
           "assumption_lines", "build_draft", "jev_appendix"]


def method_report(method: str):
    return REPORTS[method]


def headline(plan: dict, results: dict) -> str:
    """One-line statistical summary for terminal output."""
    return method_report(plan["method"]).headline(plan, results["statistics"])


def assumption_lines(results: dict, spec: MethodSpec, lang: str, plan: dict) -> list[str]:
    alternatives = {a.id: a.alternative for a in spec.assumptions}
    command = alternative_command(plan)
    lines = []
    for a in results.get("assumptions", []):
        group = f" [{a.get('group') or a.get('variable')}]" if a.get("group") or a.get("variable") else ""
        label = f"{a['label']}（{a['test']}）" if lang == "zh" else f"{a['id']}{group} ({a['test']})"
        stat = ""
        if a["id"] == "expected_counts":
            stat = (f"最小期望次數 = {apa.num(a['min_expected'])}，期望次數 < {a['threshold']} 的格數占 "
                    f"{apa.pct(a['proportion_below_threshold'])}" if lang == "zh" else
                    f"minimum expected count = {apa.num(a['min_expected'])}; cells with expected count "
                    f"< {a['threshold']}: {apa.pct(a['proportion_below_threshold'])}")
        elif a.get("statistic") is not None:
            symbol = {"Shapiro-Wilk": "W", "Brown-Forsythe Levene": "F", "Breusch-Pagan (Koenker)": "LM",
                      "VIF": "max VIF"}.get(a["test"], "statistic")
            value = apa.bounded(a["statistic"]) if symbol == "W" else apa.num(a["statistic"])
            stat = f"{symbol} = {value}" + (f", p {apa.p_value(a['p'])}" if a.get("p") is not None else "")
        if a.get("violated") is None:
            verdict = "無法檢定" if lang == "zh" else "not testable"
        elif a["violated"]:
            verdict = (f"未符合；{alternatives.get(a['id'], '請考慮其他方法')}" if lang == "zh"
                       else f"not met; {ALTERNATIVES_EN.get(a['id'], 'consider an alternative method')}")
            if command and not a.get("informational"):
                verdict += (f"（替代計畫：`{command}`）" if lang == "zh" else f" (alternative plan: `{command}`)")
        else:
            verdict = "符合" if lang == "zh" else "met"
        sep = "：" if lang == "zh" else ": "
        lines.append(f"- {label}{sep}" + (f"{stat}，{verdict}" if lang == "zh" and stat else
                                         f"{stat}, {verdict}" if stat else verdict))
    return lines


def figure_lines(figures: dict | None, lang: str) -> list[str]:
    zh = lang == "zh"
    if not figures:
        return []
    heading = "## 圖表（Figures）" if zh else "## Figures"
    if "failed" in figures:
        note = ("圖表未能產生（不影響統計結果）：" if zh else "Figures could not be produced (the statistics are unaffected): ")
        error = " ".join(figures["failed"].replace("`", "'").split())[:200]  # keep it one code span
        return [heading, "", note + f"`{error}`", ""]
    lines = [heading, ""]
    for n, f in enumerate(figures["figures"], start=1):
        lines += [f"**Figure {n}**", "", f"*{f['caption'][lang]}*", "", f"![Figure {n}]({f['file']}.png)", ""]
    if figures.get("needs_cjk") and not figures.get("cjk_font"):
        lines += [("圖中的中文標籤需要 CJK 字型才能正確顯示。請安裝 Noto Sans CJK TC（Windows 內建 Microsoft JhengHei、"
                   "macOS 內建 PingFang TC），刪除 matplotlib 字型快取（`python -c \"import matplotlib; "
                   "print(matplotlib.get_cachedir())\"` 顯示的資料夾），再以新的 run 重新分析。"
                   if zh else "Chinese labels need a CJK font. Install Noto Sans CJK TC (Windows ships Microsoft "
                              "JhengHei, macOS ships PingFang TC), delete the matplotlib font cache (the folder shown "
                              "by `python -c \"import matplotlib; print(matplotlib.get_cachedir())\"`), then analyse "
                              "again in a new run."), ""]
    return lines


def build_draft(plan: dict, results: dict, spec: MethodSpec, lang: str = "zh", figures: dict | None = None) -> str:
    r = method_report(plan["method"])
    zh = lang == "zh"
    method_name = spec.name_zh if zh else spec.name_en
    lines = [
        "# 統計結果報告（Statistical Report）" if zh else "# Statistical Report",
        "",
        f"- {'分析紀錄' if zh else 'Run'}：`{plan['run_id']}`",
        f"- {'資料集' if zh else 'Dataset'}：`{plan['dataset_id']}`（`sha256:{plan['dataset_sha256']}`）",
        f"- {'統計方法' if zh else 'Method'}：{method_name}",
        f"- {'統計引擎' if zh else 'Engine'}：`{results['engine']['version']}`",
        "",
        "## 結果（Results）" if zh else "## Results",
        "",
        r.paragraph(plan, results["statistics"], lang),
        "",
    ]
    assumptions = assumption_lines(results, spec, lang, plan)
    if assumptions:
        lines += ["## 統計假設檢查（Assumption Checks）" if zh else "## Assumption Checks", "", *assumptions, ""]
    lines += figure_lines(figures, lang)
    lines += ["## 研究限制（Limitations）" if zh else "## Limitations", "", r.limitations(lang), ""]
    return "\n".join(lines)


def jev_appendix(review, lang: str) -> str:
    zh = lang == "zh"
    lines = [JEV_HEADING, ""]
    lines += [f"- `{c.verdict}` `{c.check_id}`：{c.reason}" for c in review.checks]
    uncertain = review.by_verdict(UNCERTAIN)
    if uncertain:
        lines += ["", "審查提醒：以上 UNCERTAIN 項目需要研究者判斷後再定稿。" if zh
                  else "Reminder: UNCERTAIN items above need the researcher's judgement before finalising."]
    lines += ["", DISCLAIMER[lang], ""]
    return "\n".join(lines)
