"""Tests on contingency tables."""

from __future__ import annotations

from .. import apa
from ..methods import MethodSpec
from .common import Effect, significance_sentence


def cramers_v_label(v: float, k: int, lang: str) -> str:
    """Cohen's w benchmarks (.1 / .3 / .5) scaled by √(min(r, c) − 1)."""
    w = v * k ** 0.5
    zh, en = (("微弱", "negligible") if w < 0.1 else ("小", "small") if w < 0.3
              else ("中等", "medium") if w < 0.5 else ("大", "large"))
    return f"依 Cohen（1988）的慣例屬於{zh}關聯強度" if lang == "zh" else f"a {en} association by Cohen's (1988) convention"


def crosstab(plan, s, lang) -> str:
    r, c = plan["variables"]["row"], plan["variables"]["column"]
    head = f"| {r} \\ {c} | " + " | ".join(s["column_levels"]) + " |"
    sep = "|" + "---|" * (len(s["column_levels"]) + 1)
    lp, rp = ("（", "）") if lang == "zh" else (" (", ")")
    body = [f"| {lvl} | " + " | ".join(f"{o}{lp}{apa.pct(pr)}{rp}" for o, pr in zip(obs, props)) + " |"
            for lvl, obs, props in zip(s["row_levels"], s["observed"], s["row_proportions"])]
    note = "括號內為列百分比。" if lang == "zh" else "Row percentages in parentheses."
    return "\n".join([head, sep, *body, "", note])


class ChiSquareReport:
    def headline(self, plan, s) -> str:
        return (f"χ²({apa.df(s['df'])}, N = {s['n']}) = {apa.num(s['chi2'])}, p {apa.p_value(s['p'])}, "
                f"Cramér's V = {apa.bounded(s['cramers_v'])}")

    def primary_p(self, s) -> float | None:
        return s["p"]

    def effect(self, s) -> Effect:
        return Effect("Cramér's V", s["cramers_v"])

    def table(self, plan, s, lang) -> str:
        return crosstab(plan, s, lang)

    def paragraph(self, plan, s, lang) -> str:
        r, c = plan["variables"]["row"], plan["variables"]["column"]
        o = plan["options"]
        k = min(len(s["row_levels"]), len(s["column_levels"])) - 1
        stats = self.headline(plan, s)
        dropped = s["n_excluded"]
        if lang == "zh":
            text = (f"以卡方獨立性檢定（Pearson χ²，未做連續性校正）分析 {r} 與 {c} 的關聯"
                    + (f"（排除 {dropped} 筆缺失）" if dropped else "") + f"，{stats}。"
                    + significance_sentence(s["p"], o["alpha"], "zh", "兩變項的關聯")
                    + f"{cramers_v_label(s['cramers_v'], k, 'zh')}。")
        else:
            text = (f"A chi-square test of independence (Pearson, no continuity correction) examined the association "
                    f"between {r} and {c}" + (f" ({dropped} cases with missing values excluded)" if dropped else "")
                    + f", {stats}. "
                    + significance_sentence(s["p"], o["alpha"], "en", subject_en="The association")
                    + f" This is {cramers_v_label(s['cramers_v'], k, 'en')}.")
        return text + "\n\n" + self.table(plan, s, lang)

    def limitations(self, lang) -> str:
        if lang == "zh":
            return "卡方檢定只說明兩個類別變項是否有關聯，不代表其中一個變項影響另一個；也無法排除其他變項的干擾。"
        return ("A chi-square test shows whether two categorical variables are associated; it says nothing about "
                "direction of influence and cannot rule out confounding variables.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s, a = results["statistics"], results["assumptions"][0]
        r, c = plan["variables"]["row"], plan["variables"]["column"]
        sig = apa.significant(s["p"], plan["options"]["alpha"])
        k = min(len(s["row_levels"]), len(s["column_levels"])) - 1
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

`{r}` 與 `{c}` 兩個類別變項是否有關聯？也就是 `{c}` 的分布是否因 `{r}` 的類別而不同。
虛無假設 H0：兩變項互相獨立；對立假設 H1：兩變項有關聯。

## 2. 為什麼選擇卡方獨立性檢定？

- 兩個變項都是類別（nominal / ordinal）尺度，資料可整理成交叉表。
- 每一位受試者只出現在一個格子裡（你已在 Gate A 確認 independence）。
- 卡方檢定比較「實際觀察次數」與「若兩變項獨立時的期望次數」差多少。

{self.table(plan, s, 'zh')}

## 3. 為什麼不選其他方法？

- **Fisher's exact test**：期望次數太小（常見規則：超過兩成格子期望次數小於 5）時使用。
- **McNemar test**：同一批人前後兩次的類別結果（配對資料），不能用一般卡方。
- **t 檢定 / 相關**：用於連續變項；你的兩個變項都是類別。

## 4. 如何理解統計假設？

卡方檢定的近似需要足夠的期望次數。本次最小期望次數為 {apa.num(a['min_expected'])}，
期望次數小於 {a['threshold']} 的格子占 {apa.pct(a['proportion_below_threshold'])}，
{'超過建議上限，結果可能不可靠，建議改用 Fisher exact test 或合併類別。' if a['violated'] else '符合一般建議。'}

## 5. 如何解讀效果量？

Cramér's V = {apa.bounded(s['cramers_v'])}（介於 0 到 1，0 代表完全無關聯），{cramers_v_label(s['cramers_v'], k, 'zh')}。
卡方值會隨樣本數變大，因此要看 V 才知道關聯有多強。

## 6. 這個結果可以支持什麼結論？

- 可以說：`{r}` 與 `{c}` 的關聯{'達' if sig else '未達'}統計顯著（χ²({apa.df(s['df'])}) = {apa.num(s['chi2'])}, p {apa.p_value(s['p'])}）。
- 不能說：其中一個變項「導致」另一個；卡方只描述關聯。
- 看交叉表的列百分比，才知道關聯的方向（哪一組比例較高）。
"""


def odds_ratio_text(value: float | None) -> str:
    return "∞" if value is None else apa.num(value)


class FisherReport:
    def headline(self, plan, s) -> str:
        cl = apa.num(100 * s["conf_level"], 0)
        return (f"p {apa.p_value(s['p'])}, OR = {odds_ratio_text(s['odds_ratio'])}, "
                f"{cl}% CI [{apa.num(s['ci_lower'])}, {odds_ratio_text(s['ci_upper'])}]")

    def primary_p(self, s) -> float | None:
        return s["p"]

    def effect(self, s) -> Effect:
        return Effect("OR", s["odds_ratio"], s["odds_ratio"], s["ci_lower"], s["ci_upper"], implausible_above=None)

    def paragraph(self, plan, s, lang) -> str:
        r, c = plan["variables"]["row"], plan["variables"]["column"]
        (r1, r2), (c1, _) = s["row_levels"], s["column_levels"]
        o = plan["options"]
        dropped = s["n_excluded"]
        if lang == "zh":
            text = (f"以 Fisher's exact test 分析 {r} 與 {c} 的關聯（n = {s['n']}"
                    + (f"，排除 {dropped} 筆缺失" if dropped else "") + f"），{self.headline(plan, s)}。"
                    f"勝算比（條件最大概似估計）代表 {r1} 組中 {c1} 的勝算相對於 {r2} 組的倍數。"
                    + significance_sentence(s["p"], o["alpha"], "zh", "兩變項的關聯"))
        else:
            text = (f"Fisher's exact test examined the association between {r} and {c} (n = {s['n']}"
                    + (f"; {dropped} cases with missing values excluded" if dropped else "") + f"), {self.headline(plan, s)}. "
                    f"The conditional maximum likelihood odds ratio compares the odds of {c1} in {r1} with those in {r2}. "
                    + significance_sentence(s["p"], o["alpha"], "en", subject_en="The association"))
        return text + "\n\n" + crosstab(plan, s, lang)

    def limitations(self, lang) -> str:
        if lang == "zh":
            return ("Fisher's exact test 適用小樣本的四格表（兩個二元變項），只說明兩變項是否有關聯，不代表其中一個影響另一個；"
                    "樣本很小時信賴區間很寬，解讀勝算比時要特別保守。")
        return ("Fisher's exact test suits small two-by-two tables; it shows whether two variables are associated, not that "
                "one influences the other. With very small samples the confidence interval is wide, so interpret the "
                "odds ratio cautiously.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s = results["statistics"]
        r, c = plan["variables"]["row"], plan["variables"]["column"]
        (r1, r2), (c1, _) = s["row_levels"], s["column_levels"]
        sig = apa.significant(s["p"], plan["options"]["alpha"])
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

`{r}` 與 `{c}` 兩個二元變項是否有關聯？
虛無假設 H0：兩變項互相獨立（勝算比 = 1）。

## 2. 為什麼選擇 Fisher's exact test？

- 兩個變項都只有兩類，資料可整理成 2 × 2 交叉表，每位受試者只在一個格子裡（你已在 Gate A 確認 independence）。
- 它直接計算「在邊際總和固定下，出現這張表或更極端的表」的機率，不依賴大樣本近似，期望次數很小時仍然正確。

{crosstab(plan, s, 'zh')}

## 3. 為什麼不選其他方法？

- **卡方檢定**：樣本夠大、期望次數都足夠時可用；期望次數太小時近似不可靠。
- **McNemar test**：同一批人前後兩次的二元結果（配對資料）。
- **大於 2 × 2 的表**：本平台目前只支援 2 × 2 的 Fisher's exact test。

## 4. 如何理解統計假設？

精確檢定不需要期望次數或常態假設，只需要觀察值互相獨立。代價是樣本小時檢定力低，未達顯著不代表沒有關聯。

## 5. 如何解讀效果量與信賴區間？

- 勝算比 OR = {odds_ratio_text(s['odds_ratio'])}：`{r1}` 組中 `{c1}` 的勝算是 `{r2}` 組的幾倍；OR = 1 代表沒有關聯。
- 信賴區間 [{apa.num(s['ci_lower'])}, {odds_ratio_text(s['ci_upper'])}]：{'不包含' if sig else '包含'} 1。區間很寬時，代表樣本太小，無法精確估計關聯強度。

## 6. 這個結果可以支持什麼結論？

- 可以說：`{r}` 與 `{c}` 的關聯{'達' if sig else '未達'}統計顯著（p {apa.p_value(s['p'])}）。
- 不能說：其中一個變項「導致」另一個；這只是關聯。
"""
