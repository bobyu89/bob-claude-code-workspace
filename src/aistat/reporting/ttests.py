"""Paired and independent-samples t tests."""

from __future__ import annotations

from .. import apa
from ..methods import MethodSpec
from .common import Effect, cohen_d_label, significance_sentence


class PairedReport:
    def headline(self, plan, s) -> str:
        return (f"t({apa.df(s['df'])}) = {apa.num(s['t'])}, p {apa.p_value(s['p'])}, "
                f"M_diff = {apa.num(s['mean_diff'])}, d_z = {apa.num(s['cohens_dz'])}")

    def primary_p(self, s) -> float | None:
        return s["p"]

    def effect(self, s) -> Effect:
        return Effect("Cohen's d_z", s["cohens_dz"], s["mean_diff"], s["ci_lower"], s["ci_upper"])

    def paragraph(self, plan, s, lang) -> str:
        b, a = plan["variables"]["before"], plan["variables"]["after"]
        o = plan["options"]
        cl = apa.num(100 * o["conf_level"], 0)
        stats = (f"{cl}% CI [{apa.num(s['ci_lower'])}, {apa.num(s['ci_upper'])}]，"
                 f"t({apa.df(s['df'])}) = {apa.num(s['t'])}, p {apa.p_value(s['p'])}, "
                 f"Cohen's d_z = {apa.num(s['cohens_dz'])}")
        excluded = s["n_excluded"]
        if lang == "zh":
            direction = "高於" if s["mean_diff"] > 0 else "低於" if s["mean_diff"] < 0 else "等於"
            dropped = f"，排除 {excluded} 筆缺失配對" if excluded else ""
            return (
                f"以配對樣本 t 檢定比較 {b} 與 {a}（n = {s['n']}{dropped}）。"
                f"{a}（M = {apa.num(s['mean_after'])}, SD = {apa.num(s['sd_after'])}）{direction} "
                f"{b}（M = {apa.num(s['mean_before'])}, SD = {apa.num(s['sd_before'])}），"
                f"平均差為 {apa.num(s['mean_diff'])}，{stats}。"
                + significance_sentence(s["p"], o["alpha"], "zh")
                + (f"{cohen_d_label(s['cohens_dz'], 'zh')}。" if s["cohens_dz"] is not None else "")
            )
        direction = "higher" if s["mean_diff"] > 0 else "lower" if s["mean_diff"] < 0 else "equal"
        dropped = f"; {excluded} incomplete pairs excluded" if excluded else ""
        stats_en = stats.replace("，", ", ")
        return (
            f"A paired-samples t test compared {b} and {a} (n = {s['n']}{dropped}). "
            f"Scores for {a} (M = {apa.num(s['mean_after'])}, SD = {apa.num(s['sd_after'])}) were {direction} "
            f"than for {b} (M = {apa.num(s['mean_before'])}, SD = {apa.num(s['sd_before'])}), "
            f"mean difference = {apa.num(s['mean_diff'])}, {stats_en}. "
            + significance_sentence(s["p"], o["alpha"], "en")
            + (f" This is {cohen_d_label(s['cohens_dz'], 'en')}." if s["cohens_dz"] is not None else "")
        )

    def limitations(self, lang) -> str:
        if lang == "zh":
            return ("配對樣本 t 檢定只描述同一批受試者兩次測量的差異。若為單組前後測設計，沒有對照組，"
                    "無法排除時間、成熟、測驗練習或其他同時發生的事件等解釋，結果不應解讀為介入本身的因果效果。")
        return ("A paired-samples t test describes the change within the same participants. In a one-group "
                "pretest-posttest design there is no control group, so maturation, testing, history and other "
                "explanations cannot be ruled out; the result should not be read as the causal effect of an intervention.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s = results["statistics"]
        b, a = plan["variables"]["before"], plan["variables"]["after"]
        alpha = apa.bounded(plan["options"]["alpha"], 2)
        cl = apa.num(100 * plan["options"]["conf_level"], 0)
        sig = apa.significant(s["p"], plan["options"]["alpha"])
        normal = results["assumptions"][0]
        if normal.get("violated") is None:
            normal_text = "樣本數或變異不足，引擎無法檢定差值的常態性。"
        else:
            normal_text = (f"本次 Shapiro-Wilk 檢定 W = {apa.bounded(normal['statistic'])}, p {apa.p_value(normal['p'])}，"
                           + ("顯示差值偏離常態，建議同時以 Wilcoxon signed-rank test 確認結論。" if normal["violated"]
                              else "沒有證據顯示差值偏離常態。"))
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

同一批受試者在 `{b}` 與 `{a}` 兩次測量之間，平均分數是否有改變？
虛無假設 H0：兩次測量的平均差為 0；對立假設 H1：平均差不為 0（雙尾）。

## 2. 為什麼選擇配對樣本 t 檢定？

- 每一列是同一位受試者，`{b}` 與 `{a}` 兩個分數彼此配對（你已在 Gate A 確認 pairing_structure）。
- 兩個變項都是連續（scale）尺度，可以計算平均差。
- 配對設計把「每個人原本的程度」相減掉，只看個人自己的改變，所以比把兩次測量當成兩組更敏感。

## 3. 為什麼不選其他方法？

- **獨立樣本 t 檢定**：假設兩組是不同的人。你的資料是同一批人測兩次，若用獨立樣本會忽略配對，標準誤估計錯誤。
- **Wilcoxon signed-rank test**：不假設常態，適合差值明顯偏態或樣本很小時；本平台會在常態性不符時提醒你考慮它。
- **重複量數 ANOVA**：適用三次以上的測量；只有兩次時結果等同配對 t 檢定。

## 4. 如何理解統計假設？

配對 t 檢定的關鍵假設是「差值（`{a}` − `{b}`）近似常態分布」，而不是兩次分數各自常態。
{normal_text}
另一個前提是受試者之間互相獨立：一個人的改變不影響另一個人。

## 5. 如何解讀效果量與信賴區間？

- 平均差 {apa.num(s['mean_diff'])} 的 {cl}% 信賴區間為 [{apa.num(s['ci_lower'])}, {apa.num(s['ci_upper'])}]：
  若以同樣方式重複抽樣很多次，約 {cl}% 的區間會包含真正的平均差。區間{'不包含' if sig else '包含'} 0，與檢定結果{'達' if sig else '未達'}顯著一致。
- Cohen's d_z = {apa.num(s['cohens_dz'])}：平均差相當於差值標準差的幾倍，{cohen_d_label(s['cohens_dz'], 'zh')}。
  p 值只回答「是否可能為 0」，效果量回答「改變有多大」，兩者都要報告。

## 6. 這個結果可以支持什麼結論？

- 可以說：在這 {s['n']} 位受試者中，`{a}` 平均{'高於' if s['mean_diff'] > 0 else '低於'} `{b}` {apa.num(abs(s['mean_diff']))}，
  差異{'達' if sig else '未達'}統計顯著（p {apa.p_value(s['p'])}，α = {alpha}）。
- 不能說：介入「導致」了改變。若沒有對照組，時間、成熟或練習效應都可能造成差異。
- 統計顯著不等於臨床上有意義：請對照你的領域中「最小臨床重要差異（MCID）」判斷 {apa.num(abs(s['mean_diff']))} 是否重要。
"""


class IndependentReport:
    def headline(self, plan, s) -> str:
        w = s["welch"]
        return (f"Welch t({apa.df(w['df'])}) = {apa.num(w['t'])}, p {apa.p_value(w['p'])}, "
                f"M_diff = {apa.num(s['mean_diff'])}, d = {apa.num(s['cohens_d'])}")

    def primary_p(self, s) -> float | None:
        return s["welch"]["p"]

    def effect(self, s) -> Effect:
        w = s["welch"]
        return Effect("Cohen's d", s["cohens_d"], s["mean_diff"], w["ci_lower"], w["ci_upper"])

    def paragraph(self, plan, s, lang) -> str:
        y, g = plan["variables"]["outcome"], plan["variables"]["group"]
        o, w = plan["options"], s["welch"]
        g1, g2 = s["groups"]
        cl = apa.num(100 * o["conf_level"], 0)
        desc = [f"{x['level']}（n = {x['n']}, M = {apa.num(x['mean'])}, SD = {apa.num(x['sd'])}）" for x in (g1, g2)]
        stats = (f"{cl}% CI [{apa.num(w['ci_lower'])}, {apa.num(w['ci_upper'])}]，"
                 f"t({apa.df(w['df'])}) = {apa.num(w['t'])}, p {apa.p_value(w['p'])}, "
                 f"Cohen's d = {apa.num(s['cohens_d'])}")
        excluded = s["n_excluded"]
        d_label = s["cohens_d"]
        if lang == "zh":
            dropped = f"，排除 {excluded} 筆缺失" if excluded else ""
            return (f"以獨立樣本 t 檢定（Welch 校正，不假設兩組變異數相等）比較 {g} 兩組的 {y}（n = {s['n']}{dropped}）。"
                    f"{desc[0]}與{desc[1]}的平均差（{g1['level']} − {g2['level']}）為 {apa.num(s['mean_diff'])}，{stats}。"
                    + significance_sentence(w["p"], o["alpha"], "zh")
                    + (f"{cohen_d_label(d_label, 'zh')}。" if d_label is not None else ""))
        desc_en = [f"{x['level']} (n = {x['n']}, M = {apa.num(x['mean'])}, SD = {apa.num(x['sd'])})" for x in (g1, g2)]
        dropped = f"; {excluded} cases with missing values excluded" if excluded else ""
        return (f"An independent-samples t test with Welch's correction compared {y} between the {g} groups "
                f"(n = {s['n']}{dropped}). The mean difference between {desc_en[0]} and {desc_en[1]} "
                f"({g1['level']} minus {g2['level']}) was {apa.num(s['mean_diff'])}, {stats.replace('，', ', ')}. "
                + significance_sentence(w["p"], o["alpha"], "en")
                + (f" This is {cohen_d_label(d_label, 'en')}." if d_label is not None else ""))

    def limitations(self, lang) -> str:
        if lang == "zh":
            return ("若組別不是隨機分派，兩組在結果變項上的差異可能來自其他干擾變項，"
                    "只能描述為組間差異，不應解讀為分組本身的因果效果。")
        return ("Unless participants were randomly assigned, group differences may reflect confounding variables; "
                "the result describes a difference between groups, not the causal effect of group membership.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s, a = results["statistics"], results["assumptions"]
        y, g = plan["variables"]["outcome"], plan["variables"]["group"]
        g1, g2 = s["groups"]
        w, st = s["welch"], s["student"]
        alpha = apa.bounded(plan["options"]["alpha"], 2)
        cl = apa.num(100 * plan["options"]["conf_level"], 0)
        sig = apa.significant(w["p"], plan["options"]["alpha"])
        normal = [x for x in a if x["id"] == "normality_by_group"]
        lev = next(x for x in a if x["id"] == "homogeneity_of_variance")
        normal_lines = "\n".join(
            f"- `{x['group']}` 組：" + ("無法檢定（樣本數或變異不足）" if x.get("violated") is None else
                                       f"W = {apa.bounded(x['statistic'])}, p {apa.p_value(x['p'])}，"
                                       + ("偏離常態" if x["violated"] else "沒有證據顯示偏離常態"))
            for x in normal)
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

`{g}` 的兩組（`{g1['level']}`、`{g2['level']}`）在 `{y}` 的平均數是否不同？
虛無假設 H0：兩組母體平均數相等；對立假設 H1：兩組平均數不相等（雙尾）。

## 2. 為什麼選擇獨立樣本 t 檢定？

- 結果變項 `{y}` 是連續（scale）尺度，分組變項 `{g}` 恰好兩組。
- 兩組是不同的人（你已在 Gate A 確認 independence），彼此沒有配對。
- 本平台預設報告 **Welch t 檢定**：不需要假設兩組變異數相等，兩組人數不同時也穩健。

## 3. 為什麼不選其他方法？

- **配對樣本 t 檢定**：用於同一批人測兩次；你的兩組是不同的人。
- **Student t 檢定（假設變異數相等）**：結果也一併算出（t({apa.df(st['df'])}) = {apa.num(st['t'])}, p {apa.p_value(st['p'])}），
  但當變異數或人數不等時可能偏誤，因此以 Welch 為主。
- **Mann-Whitney U test**：結果明顯偏態或樣本很小時的無母數替代。
- **單因子 ANOVA**：三組以上時使用；兩組時與 t 檢定等價。

## 4. 如何理解統計假設？

各組常態性（Shapiro-Wilk）：
{normal_lines}

變異數同質性（Brown-Forsythe Levene）：F = {apa.num(lev['statistic'])}, p {apa.p_value(lev['p'])}。
Welch 檢定不依賴這個假設，所以它只作參考；觀察值互相獨立則是無法用檢定確認、必須由研究設計保證的前提。

## 5. 如何解讀效果量與信賴區間？

- 平均差（`{g1['level']}` − `{g2['level']}`）= {apa.num(s['mean_diff'])}，{cl}% CI [{apa.num(w['ci_lower'])}, {apa.num(w['ci_upper'])}]。
  區間{'不包含' if sig else '包含'} 0，與檢定{'達' if sig else '未達'}顯著一致。
- Cohen's d = {apa.num(s['cohens_d'])}：兩組平均差相當於合併標準差的幾倍，{cohen_d_label(s['cohens_d'], 'zh')}。
- 未達顯著不代表「兩組一樣」：信賴區間若很寬，代表樣本可能不足以偵測差異。

## 6. 這個結果可以支持什麼結論？

- 可以說：`{g1['level']}` 與 `{g2['level']}` 在 `{y}` 的平均差為 {apa.num(s['mean_diff'])}，差異{'達' if sig else '未達'}統計顯著（p {apa.p_value(w['p'])}，α = {alpha}）。
- 只有在隨機分派的實驗中，才能進一步討論組別的因果作用；觀察性分組只能描述差異。
- 請同時判斷差異大小在臨床或教育情境中是否有實質意義。
"""
