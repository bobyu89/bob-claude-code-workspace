"""Rank-based tests: Wilcoxon signed-rank, Mann-Whitney U."""

from __future__ import annotations

from .. import apa
from ..methods import MethodSpec
from .common import Effect, significance_sentence


def r_size(r: float, lang: str) -> str:
    """Cohen's benchmarks for r-type effect sizes (.1 / .3 / .5)."""
    size = abs(r)
    zh, en = (("微小", "negligible") if size < 0.1 else ("小", "small") if size < 0.3
              else ("中等", "medium") if size < 0.5 else ("大", "large"))
    return zh if lang == "zh" else en


def r_effect_label(r: float | None, lang: str) -> str:
    if r is None:
        return ""
    return (f"依 Cohen（1988）的慣例屬於{r_size(r, 'zh')}效果量" if lang == "zh"
            else f"a {r_size(r, 'en')} effect by Cohen's (1988) convention")


def effect_sentence(s: dict, lang: str) -> str:
    """Size labels for both r = Z / √N and the rank-biserial correlation."""
    rb = s["rank_biserial"]
    if lang == "zh":
        parts = []
        if s["r"] is not None:
            parts.append(f"r 屬於{r_size(s['r'], 'zh')}效果量")
        parts.append(f"rank-biserial r 屬於{r_size(rb, 'zh')}效果量")
        return "依 Cohen（1988）的慣例，" + "、".join(parts) + "。"
    parts = [f"r is a {r_size(s['r'], 'en')} effect"] if s["r"] is not None else []
    parts.append(f"the rank-biserial r is a {r_size(rb, 'en')} effect")
    return " By Cohen's (1988) convention, " + " and ".join(parts) + "."


def p_method(exact: bool, lang: str) -> str:
    if lang == "zh":
        return "p 值為精確計算（exact）" if exact else "p 值採常態近似（含同分校正與連續性校正）"
    return "the p value is exact" if exact else "the p value uses the normal approximation with tie and continuity corrections"


def iqr(s: dict, suffix: str) -> str:
    return f"Mdn = {apa.num(s[f'median_{suffix}'])}, IQR = {apa.num(s[f'q1_{suffix}'])}–{apa.num(s[f'q3_{suffix}'])}"


class WilcoxonReport:
    def headline(self, plan, s) -> str:
        return (f"W+ = {apa.num(s['w_plus'], 1)}, z = {apa.num(s['z'])}, p {apa.p_value(s['p'])}, "
                f"r = {apa.bounded(s['r'])}")

    def primary_p(self, s) -> float | None:
        return s["p"]

    def effect(self, s) -> Effect:
        return Effect("r", s["r"])

    def paragraph(self, plan, s, lang) -> str:
        b, a = plan["variables"]["before"], plan["variables"]["after"]
        o = plan["options"]
        higher = s["w_plus"] > s["w_minus"]
        lower = s["w_plus"] < s["w_minus"]
        stats = f"{self.headline(plan, s)}（rank-biserial r = {apa.bounded(s['rank_biserial'])}）"
        if lang == "zh":
            notes = []
            if s["n_zero"]:
                notes.append(f"排除 {s['n_zero']} 筆前後相同（差值為零）的配對")
            if s["n_excluded"]:
                notes.append(f"排除 {s['n_excluded']} 筆缺失")
            direction = "傾向高於" if higher else "傾向低於" if lower else "與"
            return (f"以 Wilcoxon signed-rank test 比較 {b} 與 {a}（n = {s['n']}"
                    + ("，" + "，".join(notes) if notes else "") + "）。"
                    f"{a}（{iqr(s, 'after')}）{direction} {b}（{iqr(s, 'before')}）"
                    + ("相近" if not (higher or lower) else "")
                    + f"，差值中位數為 {apa.num(s['median_diff'])}；{stats}，{p_method(s['exact'], 'zh')}。"
                    + significance_sentence(s["p"], o["alpha"], "zh") + effect_sentence(s, "zh"))
        notes = []
        if s["n_zero"]:
            notes.append(f"{s['n_zero']} pairs with zero difference excluded")
        if s["n_excluded"]:
            notes.append(f"{s['n_excluded']} incomplete pairs excluded")
        direction = "tended to be higher than" if higher else "tended to be lower than" if lower else "were similar to"
        return (f"A Wilcoxon signed-rank test compared {b} and {a} (n = {s['n']}"
                + ("; " + "; ".join(notes) if notes else "") + "). "
                f"Scores for {a} ({iqr(s, 'after')}) {direction} {b} ({iqr(s, 'before')}); the median difference was "
                f"{apa.num(s['median_diff'])}, {stats.replace('（', ' (').replace('）', ')')}; {p_method(s['exact'], 'en')}. "
                + significance_sentence(s["p"], o["alpha"], "en") + effect_sentence(s, "en"))

    def limitations(self, lang) -> str:
        if lang == "zh":
            return ("Wilcoxon signed-rank test 比較配對差值的分布位置，不需要常態假設，但假設差值分布大致對稱。"
                    "與配對 t 檢定一樣，單組前後測設計沒有對照組，結果不應解讀為介入本身的因果效果。")
        return ("The Wilcoxon signed-rank test compares the location of paired differences without assuming normality, "
                "but assumes the differences are roughly symmetric. As with a paired t test, a one-group pretest-posttest "
                "design cannot attribute the change to an intervention.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s = results["statistics"]
        b, a = plan["variables"]["before"], plan["variables"]["after"]
        sig = apa.significant(s["p"], plan["options"]["alpha"])
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

同一批受試者在 `{b}` 與 `{a}` 之間是否有系統性的改變？
虛無假設 H0：差值的分布以 0 為中心；對立假設 H1：差值傾向大於或小於 0（雙尾）。

## 2. 為什麼選擇 Wilcoxon signed-rank test？

- 資料是配對的（同一列為同一人，你已在 Gate A 確認 pairing_structure）。
- 它只用差值的「等級」而不是原始數值，不需要差值呈常態分布，也適用 ordinal 分數（例如 Likert 題項）。
- 極端值對等級的影響有限，因此比配對 t 檢定穩健。

## 3. 為什麼不選其他方法？

- **配對 t 檢定**：差值近似常態、變項為 scale 時檢定力較高；若原本的配對 t 檢定常態性不符，才改用本方法。
- **符號檢定（sign test）**：只看正負號、不看大小，資訊損失更多。
- **Mann-Whitney U test**：用於兩組不同的人，不適用配對資料。

## 4. 如何理解統計假設？

- 不需要常態，但假設差值分布大致對稱；若明顯偏斜，結果較適合解讀為「多數人上升或下降」，而非中位數的改變量。
- 差值為零的配對不提供方向資訊，依 Wilcoxon 原法排除（本次排除 {s['n_zero']} 筆）。
- 本次{'沒有同分且樣本不大，p 值是精確計算' if s['exact'] else '有同分或樣本較大，p 值採常態近似'}。

## 5. 如何解讀效果量？

- r = {apa.bounded(s['r'])}（z 除以有效樣本數的平方根），{r_effect_label(s['r'], 'zh')}。
- rank-biserial r = {apa.bounded(s['rank_biserial'])}：正差值等級和與負差值等級和的差距比例，介於 −1 到 1，正值代表 `{a}` 傾向較高。
- 無母數檢定以中位數與四分位距描述資料：差值中位數為 {apa.num(s['median_diff'])}。

## 6. 這個結果可以支持什麼結論？

- 可以說：`{a}` 與 `{b}` 的差異{'達' if sig else '未達'}統計顯著（p {apa.p_value(s['p'])}）。
- 不能說：介入「導致」了改變；沒有對照組時，時間、成熟或練習效應都可能是原因。
"""


class MannWhitneyReport:
    def headline(self, plan, s) -> str:
        return (f"U = {apa.num(s['u'], 1)}, z = {apa.num(s['z'])}, p {apa.p_value(s['p'])}, "
                f"r = {apa.bounded(s['r'])}")

    def primary_p(self, s) -> float | None:
        return s["p"]

    def effect(self, s) -> Effect:
        return Effect("r", s["r"])

    def paragraph(self, plan, s, lang) -> str:
        y, g = plan["variables"]["outcome"], plan["variables"]["group"]
        o = plan["options"]
        g1, g2 = s["groups"]
        desc = [f"{x['level']}（n = {x['n']}, Mdn = {apa.num(x['median'])}, IQR = {apa.num(x['q1'])}–{apa.num(x['q3'])}）"
                for x in (g1, g2)]
        stats = f"{self.headline(plan, s)}（rank-biserial r = {apa.bounded(s['rank_biserial'])}）"
        rb = s["rank_biserial"]
        if lang == "zh":
            direction = "傾向高於" if rb > 0 else "傾向低於" if rb < 0 else "相近於"
            dropped = f"，排除 {s['n_excluded']} 筆缺失" if s["n_excluded"] else ""
            return (f"以 Mann-Whitney U test 比較 {g} 兩組的 {y}（n = {s['n']}{dropped}）。"
                    f"{desc[0]}的 {y} {direction} {desc[1]}；{stats}，{p_method(s['exact'], 'zh')}。"
                    + significance_sentence(s["p"], o["alpha"], "zh") + effect_sentence(s, "zh"))
        desc_en = [f"{x['level']} (n = {x['n']}, Mdn = {apa.num(x['median'])}, IQR = {apa.num(x['q1'])}–{apa.num(x['q3'])})"
                   for x in (g1, g2)]
        direction = "tended to be higher than" if rb > 0 else "tended to be lower than" if rb < 0 else "were similar to"
        dropped = f"; {s['n_excluded']} cases with missing values excluded" if s["n_excluded"] else ""
        return (f"A Mann-Whitney U test compared {y} between the {g} groups (n = {s['n']}{dropped}). "
                f"Values in {desc_en[0]} {direction} those in {desc_en[1]}, "
                f"{stats.replace('（', ' (').replace('）', ')')}; {p_method(s['exact'], 'en')}. "
                + significance_sentence(s["p"], o["alpha"], "en") + effect_sentence(s, "en"))

    def limitations(self, lang) -> str:
        if lang == "zh":
            return ("Mann-Whitney U test 比較兩組數值的分布位置（一組的值是否傾向大於另一組），不需要常態假設；"
                    "只有兩組分布形狀相近時，才可解讀為中位數的差異。若組別不是隨機分派，不應解讀為分組本身的因果效果。")
        return ("The Mann-Whitney U test compares whether values in one group tend to exceed those in the other, without "
                "assuming normality; it reflects a difference in medians only when the two distributions have similar "
                "shapes. Without random assignment the result is not the causal effect of group membership.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s = results["statistics"]
        y, g = plan["variables"]["outcome"], plan["variables"]["group"]
        g1, g2 = s["groups"]
        sig = apa.significant(s["p"], plan["options"]["alpha"])
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

`{g}` 的兩組（`{g1['level']}`、`{g2['level']}`）在 `{y}` 上，是否有一組的值傾向比較大？
虛無假設 H0：兩組分布相同；對立假設 H1：一組的值傾向大於另一組（雙尾）。

## 2. 為什麼選擇 Mann-Whitney U test？

- 兩組是不同的人（你已在 Gate A 確認 independence）。
- 它把兩組資料合在一起排等級再比較，不需要常態假設，也適用 ordinal 結果變項。
- 樣本小或有極端值時，比獨立樣本 t 檢定穩健。

## 3. 為什麼不選其他方法？

- **獨立樣本 t 檢定**：各組近似常態、變項為 scale 時檢定力較高。
- **Wilcoxon signed-rank test**：用於同一批人的配對資料。
- **Kruskal-Wallis test**：三組以上時使用。

## 4. 如何理解統計假設？

- 不需要常態，但觀察值要互相獨立。
- 若兩組分布形狀差很多（例如一組很分散），顯著結果代表「分布不同」，不一定是中位數不同。
- 本次{'沒有同分且樣本不大，p 值是精確計算' if s['exact'] else '有同分或樣本較大，p 值採常態近似'}。

## 5. 如何解讀效果量？

- r = {apa.bounded(s['r'])}，{r_effect_label(s['r'], 'zh')}。
- rank-biserial r = {apa.bounded(s['rank_biserial'])}：隨機各抽一人時，`{g1['level']}` 比 `{g2['level']}` 大的機率減去比較小的機率。
- 報告時以中位數與四分位距描述各組：`{g1['level']}` Mdn = {apa.num(g1['median'])}，`{g2['level']}` Mdn = {apa.num(g2['median'])}。

## 6. 這個結果可以支持什麼結論？

- 可以說：兩組在 `{y}` 的分布差異{'達' if sig else '未達'}統計顯著（p {apa.p_value(s['p'])}）。
- 只有隨機分派的實驗才能討論組別的因果作用；觀察性分組只能描述差異。
"""
