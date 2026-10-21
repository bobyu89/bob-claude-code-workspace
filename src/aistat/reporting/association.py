"""Correlation and linear regression."""

from __future__ import annotations

from .. import apa
from ..methods import MethodSpec
from .common import Effect, significance_sentence


def r_label(r: float, lang: str) -> str:
    size = abs(r)
    zh, en = (("微弱", "negligible") if size < 0.1 else ("小", "small") if size < 0.3
              else ("中等", "medium") if size < 0.5 else ("大", "large"))
    return f"依 Cohen（1988）的慣例屬於{zh}相關" if lang == "zh" else f"a {en} correlation by Cohen's (1988) convention"


class CorrelationReport:
    def _symbol(self, s) -> str:
        return "r" if s["method"] == "pearson" else "r_s"

    def headline(self, plan, s) -> str:
        return f"{self._symbol(s)}({apa.df(s['df'])}) = {apa.bounded(s['r'])}, p {apa.p_value(s['p'])}"

    def primary_p(self, s) -> float | None:
        return s["p"]

    def effect(self, s) -> Effect:
        return Effect(self._symbol(s), s["r"], s["r"], s["ci_lower"], s["ci_upper"])

    def paragraph(self, plan, s, lang) -> str:
        x, y = plan["variables"]["x"], plan["variables"]["y"]
        o = plan["options"]
        stats = self.headline(plan, s)
        if s["ci_lower"] is not None:
            cl = apa.num(100 * o["conf_level"], 0)
            stats += f", {cl}% CI [{apa.bounded(s['ci_lower'])}, {apa.bounded(s['ci_upper'])}]"
        dropped = s["n_excluded"]
        name_zh = "Pearson 積差相關" if s["method"] == "pearson" else "Spearman 等級相關"
        name_en = "A Pearson correlation" if s["method"] == "pearson" else "A Spearman rank correlation"
        if lang == "zh":
            direction = "正相關" if s["r"] > 0 else "負相關" if s["r"] < 0 else "零相關"
            return (f"以{name_zh}分析 {x} 與 {y} 的關係（n = {s['n']}"
                    + (f"，排除 {dropped} 筆缺失" if dropped else "") + f"），兩者呈{direction}，{stats}。"
                    + significance_sentence(s["p"], o["alpha"], "zh", "相關") + f"{r_label(s['r'], 'zh')}。")
        direction = "positive" if s["r"] > 0 else "negative" if s["r"] < 0 else "zero"
        return (f"{name_en} examined the relationship between {x} and {y} (n = {s['n']}"
                + (f"; {dropped} cases with missing values excluded" if dropped else "")
                + f"). The correlation was {direction}, {stats}. "
                + significance_sentence(s["p"], o["alpha"], "en", subject_en="The correlation")
                + f" This is {r_label(s['r'], 'en')}.")

    def limitations(self, lang) -> str:
        if lang == "zh":
            return "相關只描述兩變項共同變化的程度，不代表其中一個影響另一個，也可能由第三個變項同時影響兩者。"
        return ("Correlation describes how two variables vary together; it does not show that one influences the "
                "other, and both may depend on a third variable.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s = results["statistics"]
        x, y = plan["variables"]["x"], plan["variables"]["y"]
        sig = apa.significant(s["p"], plan["options"]["alpha"])
        pearson = s["method"] == "pearson"
        normal = "\n".join(
            f"- `{a['variable']}`：" + ("無法檢定" if a.get("violated") is None else
                                       f"W = {apa.bounded(a['statistic'])}, p {apa.p_value(a['p'])}，"
                                       + ("偏離常態，可考慮 Spearman" if a["violated"] else "沒有證據顯示偏離常態"))
            for a in results["assumptions"]) or "- Spearman 以等級計算，不需要常態假設。"
        ci = (f"{apa.num(100 * s['conf_level'], 0)}% CI [{apa.bounded(s['ci_lower'])}, {apa.bounded(s['ci_upper'])}]："
              f"母體相關係數的合理範圍；區間{'不包含' if sig else '包含'} 0。") if pearson else "Spearman 相關本平台不計算信賴區間。"
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

`{x}` 與 `{y}` 之間是否有線性（或單調）關係？關係的方向與強度為何？
虛無假設 H0：母體相關係數為 0。

## 2. 為什麼選擇{'Pearson 積差相關' if pearson else 'Spearman 等級相關'}？

- 兩個變項都是數值，且每一列是同一位受試者的兩個測量。
- {'Pearson 適用兩個連續（scale）變項的線性關係。' if pearson else 'Spearman 以等級計算，適用 ordinal 變項、偏態分布或有極端值時的單調關係。'}

## 3. 為什麼不選其他方法？

- **{'Spearman' if pearson else 'Pearson'}**：{'變項為 ordinal、明顯偏態或有極端值時使用。' if pearson else '兩變項皆為連續且近似常態、關係為線性時較有檢定力。'}
- **線性迴歸**：想用一個變項「預測」另一個、或同時控制其他變項時使用。
- **卡方檢定**：兩個都是類別變項時使用。

## 4. 如何理解統計假設？

{normal}
相關分析也假設關係大致為線性（Pearson）或單調（Spearman）；請畫散布圖確認，並注意極端值。

## 5. 如何解讀效果量與信賴區間？

- 相關係數本身就是效果量：{self._symbol(s)} = {apa.bounded(s['r'])}，{r_label(s['r'], 'zh')}。
- {ci}

## 6. 這個結果可以支持什麼結論？

- 可以說：`{x}` 與 `{y}` 的相關{'達' if sig else '未達'}統計顯著（{self.headline(plan, s)}）。
- 不能說：`{x}` 造成 `{y}` 的變化；相關不等於因果。
"""


class RegressionReport:
    def headline(self, plan, s) -> str:
        return (f"F({apa.df(s['df1'])}, {apa.df(s['df2'])}) = {apa.num(s['f'])}, p {apa.p_value(s['f_p'])}, "
                f"R² = {apa.bounded(s['r_squared'])}, adjusted R² = {apa.bounded(s['adj_r_squared'])}")

    def primary_p(self, s) -> float | None:
        return s["f_p"]

    def effect(self, s) -> Effect:
        return Effect("R²", s["r_squared"])

    def table(self, plan, s, lang) -> str:
        cl = apa.num(100 * plan["options"]["conf_level"], 0)
        head = (f"| 預測變項 | B | SE | β | t | p | {cl}% CI |" if lang == "zh"
                else f"| Predictor | B | SE | β | t | p | {cl}% CI |")
        rows = [head, "|---|---|---|---|---|---|---|"]
        for c in s["coefficients"]:
            term = ("（截距）" if lang == "zh" else "(Intercept)") if c["term"] == "(Intercept)" else c["term"]
            beta = "—" if c["beta"] is None else apa.bounded(c["beta"])
            p = apa.p_value(c["p"]).replace("= ", "")
            rows.append(f"| {term} | {apa.num(c['b'])} | {apa.num(c['se'])} | {beta} | {apa.num(c['t'])} | {p} | "
                        f"[{apa.num(c['ci_lower'])}, {apa.num(c['ci_upper'])}] |")
        return "\n".join(rows)

    def paragraph(self, plan, s, lang) -> str:
        y, xs = plan["variables"]["outcome"], plan["variables"]["predictors"]
        o = plan["options"]
        df2 = apa.df(s["df2"])
        dropped = s["n_excluded"]
        preds = [c for c in s["coefficients"] if c["term"] != "(Intercept)"]
        if lang == "zh":
            kind = "簡單線性迴歸" if len(xs) == 1 else "多元線性迴歸"
            lines = [f"以{kind}分析 {'、'.join(xs)} 對 {y} 的預測（n = {s['n']}"
                     + (f"，排除 {dropped} 筆缺失" if dropped else "")
                     + f"）。整體模型 {self.headline(plan, s)}，"
                     + significance_sentence(s["f_p"], o["alpha"], "zh", "模型")]
            for c in preds:
                sig = apa.significant(c["p"], o["alpha"])
                lines.append(f"{c['term']} 的迴歸係數 B = {apa.num(c['b'])}（β = {apa.bounded(c['beta'])}），"
                             f"t({df2}) = {apa.num(c['t'])}, p {apa.p_value(c['p'])}，{'達' if sig else '未達'}統計顯著。")
            return "".join(lines) + "\n\n" + self.table(plan, s, lang)
        kind = "A simple linear regression" if len(xs) == 1 else "A multiple linear regression"
        lines = [f"{kind} examined {', '.join(xs)} as predictors of {y} (n = {s['n']}"
                 + (f"; {dropped} cases with missing values excluded" if dropped else "")
                 + f"). The overall model, {self.headline(plan, s)}. "
                 + significance_sentence(s["f_p"], o["alpha"], "en", subject_en="The model")]
        for c in preds:
            sig = apa.significant(c["p"], o["alpha"])
            lines.append(f" For {c['term']}, B = {apa.num(c['b'])} (β = {apa.bounded(c['beta'])}), "
                         f"t({df2}) = {apa.num(c['t'])}, p {apa.p_value(c['p'])}; this coefficient was "
                         f"{'' if sig else 'not '}statistically significant.")
        return "".join(lines) + "\n\n" + self.table(plan, s, lang)

    def limitations(self, lang) -> str:
        if lang == "zh":
            return ("迴歸係數描述在控制模型中其他預測變項後的關聯；觀察性資料不能解讀為因果，"
                    "且結果只適用於資料涵蓋的數值範圍，未納入模型的變項仍可能干擾結果。")
        return ("Regression coefficients describe associations holding the other predictors constant; with "
                "observational data they are not causal effects, apply only within the observed range, and may be "
                "confounded by variables left out of the model.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s, a = results["statistics"], results["assumptions"]
        y, xs = plan["variables"]["outcome"], plan["variables"]["predictors"]
        sig = apa.significant(s["f_p"], plan["options"]["alpha"])
        lines = []
        for x in a:
            if x["id"] == "multicollinearity":
                detail = "、".join(f"`{v['term']}` VIF = {apa.num(v['vif'])}" for v in x["vif"])
                lines.append(f"- 共線性：{detail}" + ("（VIF 大於等於 10 表示嚴重共線，係數不穩定）" if x["violated"] else "（未達嚴重共線）"))
            elif x.get("violated") is None:
                lines.append(f"- {x['label']}：無法檢定")
            else:
                stat = apa.bounded(x["statistic"]) if x["test"] == "Shapiro-Wilk" else apa.num(x["statistic"])
                lines.append(f"- {x['label']}（{x['test']}）：{stat}, p {apa.p_value(x['p'])}，"
                             + ("未符合" if x["violated"] else "沒有證據顯示違反"))
        first = next(c for c in s["coefficients"] if c["term"] != "(Intercept)")
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

能否用 {'、'.join(f'`{x}`' for x in xs)} 預測 `{y}`？每個預測變項在控制其他變項後，與 `{y}` 的關聯有多大？

## 2. 為什麼選擇線性迴歸？

- 依變項 `{y}` 是連續（scale）尺度。
- 想同時估計多個預測變項各自的關聯，並得到整體模型的解釋力（R²）。

## 3. 為什麼不選其他方法？

- **相關分析**：只看兩個變項，無法同時控制其他變項。
- **邏輯斯迴歸**：依變項為二元（例如是否發生）時使用。
- **ANOVA**：預測變項全為類別、想比較組平均時使用；本質上是迴歸的特例。

## 4. 如何理解統計假設？

{chr(10).join(lines)}
另外也假設關係為線性、觀察值互相獨立；建議畫殘差對預測值圖確認。

## 5. 如何解讀效果量與信賴區間？

- R² = {apa.bounded(s['r_squared'])}：模型解釋了 `{y}` 約 {apa.pct(s['r_squared'])} 的變異；adjusted R² = {apa.bounded(s['adj_r_squared'])} 已考慮預測變項數量。
- 以 `{first['term']}` 為例：B = {apa.num(first['b'])} 表示在其他變項不變時，`{first['term']}` 每增加 1 單位，`{y}` 平均改變 {apa.num(first['b'])}；
  {apa.num(100 * s['conf_level'], 0)}% CI [{apa.num(first['ci_lower'])}, {apa.num(first['ci_upper'])}] 是這個改變量的合理範圍。
- β（標準化係數）讓不同單位的預測變項可以比較相對大小。

## 6. 這個結果可以支持什麼結論？

- 可以說：整體模型{'達' if sig else '未達'}統計顯著（{self.headline(plan, s)}）。
- 不能說：預測變項「造成」`{y}` 改變；迴歸描述的是關聯。
- 不要用模型預測資料範圍以外的數值。
"""
