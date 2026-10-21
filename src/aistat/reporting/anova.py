"""One-way ANOVA: Welch ANOVA with Games-Howell, classic F with Tukey HSD for comparison."""

from __future__ import annotations

from .. import apa
from ..methods import MethodSpec
from .common import Effect, significance_sentence


def omega_label(omega: float, lang: str) -> str:
    """Cohen's benchmarks for η² / ω² (.01 / .06 / .14)."""
    zh, en = (("微小", "negligible") if omega < 0.01 else ("小", "small") if omega < 0.06
              else ("中等", "medium") if omega < 0.14 else ("大", "large"))
    return f"依 Cohen（1988）的慣例屬於{zh}效果量" if lang == "zh" else f"a {en} effect by Cohen's (1988) convention"


def pair_label(row: dict) -> str:
    return f"{row['group2']} − {row['group1']}"


def posthoc_table(rows: list[dict], conf_level: float, lang: str) -> str:
    cl = apa.num(100 * conf_level, 0)
    head = f"| 比較 | 平均差 | {cl}% CI | p |" if lang == "zh" else f"| Comparison | Mean difference | {cl}% CI | p |"
    lines = [head, "|---|---|---|---|"]
    for r in rows:
        p = apa.p_value(r["p"]).replace("= ", "")
        lines.append(f"| {pair_label(r)} | {apa.num(r['diff'])} | [{apa.num(r['ci_lower'])}, {apa.num(r['ci_upper'])}] | {p} |")
    return "\n".join(lines)


def welch_available(s: dict) -> bool:
    """Welch's ANOVA is undefined when a group has zero variance; the classic F test then leads."""
    return s["welch"]["f"] is not None and s["welch"]["p"] is not None


def posthoc_sentence(rows: list[dict], alpha: float, lang: str) -> str:
    """Every claim cites its own p values, so Gate B checks each sentence against them."""
    rows = [r for r in rows if r["p"] is not None]
    if not rows:
        return ("事後比較無法計算（組內變異數為零）。" if lang == "zh"
                else "Post hoc comparisons could not be computed (zero within-group variance).")
    sig = [r for r in rows if apa.significant(r["p"], alpha)]
    if lang == "zh":
        if sig:
            return "達統計顯著的配對：" + "、".join(f"{pair_label(r)}（p {apa.p_value(r['p'])}）" for r in sig) + "。"
        smallest = min(rows, key=lambda r: r["p"])
        return f"所有配對比較皆未達統計顯著（最小 p {apa.p_value(smallest['p'])}）。"
    if sig:
        return "Statistically significant pairs: " + "; ".join(
            f"{pair_label(r)} (p {apa.p_value(r['p'])})" for r in sig) + "."
    smallest = min(rows, key=lambda r: r["p"])
    return f"No pairwise comparison was statistically significant (smallest p {apa.p_value(smallest['p'])})."


class AnovaReport:
    def headline(self, plan, s) -> str:
        if not welch_available(s):
            return self.classic_line(s)
        w = s["welch"]
        return (f"Welch F({apa.df(w['df1'])}, {apa.df(w['df2'])}) = {apa.num(w['f'])}, p {apa.p_value(w['p'])}, "
                f"ω² = {apa.bounded(s['omega_squared'])}")

    def primary_p(self, s) -> float | None:
        return s["welch"]["p"] if welch_available(s) else s["classic"]["p"]

    def effect(self, s) -> Effect:
        return Effect("ω²", s["omega_squared"], implausible_above=None)

    def classic_line(self, s) -> str:
        c = s["classic"]
        return (f"F({apa.df(c['df1'])}, {apa.df(c['df2'])}) = {apa.num(c['f'])}, p {apa.p_value(c['p'])}, "
                f"η² = {apa.bounded(s['eta_squared'])}, ω² = {apa.bounded(s['omega_squared'])}")

    def paragraph(self, plan, s, lang) -> str:
        y, g = plan["variables"]["outcome"], plan["variables"]["group"]
        o = plan["options"]
        w = s["welch"]
        welch = f"Welch F({apa.df(w['df1'])}, {apa.df(w['df2'])}) = {apa.num(w['f'])}, p {apa.p_value(w['p'])}"
        primary = self.primary_p(s)
        posthoc = s["games_howell"] if welch_available(s) else s["tukey"]
        zh = lang == "zh"
        if zh:
            groups = "、".join(f"{x['level']}（n = {x['n']}, M = {apa.num(x['mean'])}, SD = {apa.num(x['sd'])}）"
                              for x in s["groups"])
            dropped = f"，排除 {s['n_excluded']} 筆缺失" if s["n_excluded"] else ""
            if welch_available(s):
                main = (f"Welch ANOVA（不假設各組變異數相等）結果為 {welch}。"
                        + significance_sentence(primary, o["alpha"], "zh", "組間差異")
                        + f"傳統 F 檢定供對照：{self.classic_line(s)}，{omega_label(s['omega_squared'], 'zh')}。")
            else:
                main = ("Welch ANOVA 無法計算（至少一組的變異數為零），以下以傳統 F 檢定為主："
                        f"{self.classic_line(s)}。"
                        + significance_sentence(primary, o["alpha"], "zh", "組間差異")
                        + f"{omega_label(s['omega_squared'], 'zh')}。")
            return (f"以單因子變異數分析比較 {g} 各組的 {y}（n = {s['n']}{dropped}）。各組為 {groups}。" + main
                    + "\n\nGames-Howell 事後比較：\n\n" + posthoc_table(s["games_howell"], s["conf_level"], "zh")
                    + "\n\nTukey HSD 事後比較（假設變異數相等，供對照）：\n\n"
                    + posthoc_table(s["tukey"], s["conf_level"], "zh")
                    + "\n\n" + posthoc_sentence(posthoc, o["alpha"], "zh"))
        groups = "; ".join(f"{x['level']} (n = {x['n']}, M = {apa.num(x['mean'])}, SD = {apa.num(x['sd'])})"
                           for x in s["groups"])
        dropped = f"; {s['n_excluded']} cases with missing values excluded" if s["n_excluded"] else ""
        if welch_available(s):
            main = (f"Welch's ANOVA, which does not assume equal variances, gave {welch}. "
                    + significance_sentence(primary, o["alpha"], "en", subject_en="The group difference")
                    + f" For comparison, the classic F test gave {self.classic_line(s)}; this is "
                    + f"{omega_label(s['omega_squared'], 'en')}.")
        else:
            main = ("Welch's ANOVA could not be computed (at least one group has zero variance), so the classic F "
                    f"test is reported: {self.classic_line(s)}. "
                    + significance_sentence(primary, o["alpha"], "en", subject_en="The group difference")
                    + f" This is {omega_label(s['omega_squared'], 'en')}.")
        return (f"A one-way analysis of variance compared {y} across levels of {g} (n = {s['n']}{dropped}): {groups}. "
                + main
                + "\n\nGames-Howell post hoc comparisons:\n\n" + posthoc_table(s["games_howell"], s["conf_level"], "en")
                + "\n\nTukey HSD post hoc comparisons (equal variances assumed, for comparison):\n\n"
                + posthoc_table(s["tukey"], s["conf_level"], "en")
                + "\n\n" + posthoc_sentence(posthoc, o["alpha"], "en"))

    def limitations(self, lang) -> str:
        if lang == "zh":
            return ("Welch ANOVA 不需假設各組變異數相等，但仍假設各組近似常態、觀察值互相獨立；"
                    "事後比較以 studentized range 分布校正多重比較。若組別不是隨機分派，結果只描述組間差異，不應解讀為分組本身的因果效果。")
        return ("Welch's ANOVA does not assume equal variances but still assumes approximately normal groups and "
                "independent observations; post hoc comparisons are adjusted with the studentized range distribution. "
                "Without random assignment the result describes group differences, not the causal effect of group membership.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s, a = results["statistics"], results["assumptions"]
        y, g = plan["variables"]["outcome"], plan["variables"]["group"]
        sig = apa.significant(self.primary_p(s), plan["options"]["alpha"])
        posthoc = s["games_howell"] if welch_available(s) else s["tukey"]
        levels = "、".join(f"`{x['level']}`" for x in s["groups"])
        normal = "\n".join(
            f"- `{x['group']}` 組：" + ("無法檢定（樣本數或變異不足）" if x.get("violated") is None else
                                       f"W = {apa.bounded(x['statistic'])}, p {apa.p_value(x['p'])}，"
                                       + ("偏離常態" if x["violated"] else "沒有證據顯示偏離常態"))
            for x in a if x["id"] == "normality_by_group")
        lev = next(x for x in a if x["id"] == "homogeneity_of_variance")
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

`{g}` 的 {s['k']} 組（{levels}）在 `{y}` 的平均數是否全部相等？
虛無假設 H0：所有組的母體平均數相等；對立假設 H1：至少有一組不同。

## 2. 為什麼選擇單因子變異數分析？

- 結果變項 `{y}` 是連續（scale）尺度，分組變項有三組以上，各組是不同的人（你已在 Gate A 確認 independence）。
- 一次檢定所有組別，避免兩兩做 t 檢定造成第一型錯誤膨脹。
- 本平台以 **Welch ANOVA** 為主：不需假設各組變異數相等，各組人數不同時也穩健；事後比較用對應的 **Games-Howell**。

## 3. 為什麼不選其他方法？

- **多次獨立樣本 t 檢定**：比較次數越多，至少一次誤判的機率越高。
- **傳統 F 檢定 + Tukey HSD**：假設各組變異數相等；本報告一併列出供對照（{self.classic_line(s)}）。
- **Kruskal-Wallis test**：各組明顯偏態或為 ordinal 資料時的無母數替代（本平台尚未支援）。

## 4. 如何理解統計假設？

各組常態性（Shapiro-Wilk）：
{normal}

變異數同質性（Brown-Forsythe Levene）：F = {apa.num(lev['statistic'])}, p {apa.p_value(lev['p'])}。Welch ANOVA 不依賴這個假設，因此只作參考。

## 5. 如何解讀效果量？

- η² = {apa.bounded(s['eta_squared'])}：分組解釋了 `{y}` 變異的比例，但在樣本中會高估。
- ω² = {apa.bounded(s['omega_squared'])}：校正過的母體估計，{omega_label(s['omega_squared'], 'zh')}（.01 / .06 / .14 為小、中、大）。
- 整體 F 檢定只告訴你「至少有一組不同」，要看事後比較才知道是哪幾組。

## 6. 這個結果可以支持什麼結論？

- 可以說：各組 `{y}` 的差異{'達' if sig else '未達'}統計顯著（{self.headline(plan, s)}）；{posthoc_sentence(posthoc, plan['options']['alpha'], 'zh')}
- 不能說：分組「造成」差異，除非組別是隨機分派。
"""
