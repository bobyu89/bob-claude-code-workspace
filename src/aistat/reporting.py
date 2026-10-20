"""Turning engine raw outputs into APA 7 text.

Every number in a report is formatted from results.json by `apa`; JEV Gate B
re-checks that claim on whatever draft text is finally used.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import apa
from .methods import MethodSpec

JEV_HEADING = "## JEV 審查紀錄（JEV Review）"
CITATION_TOKENS = {"1988"}  # Cohen (1988), the only literal numbers the templates write
DISCLAIMER = {
    "zh": "JEV 屬於流程審查機制，並非統計正確性的絕對保證。所有數值由統計引擎計算，請研究者自行確認研究設計與結論。",
    "en": "JEV is a process review, not a guarantee of statistical correctness. All values were computed by "
          "the statistical engine; the researcher remains responsible for the design and conclusions.",
}


ALTERNATIVES_EN = {
    "normality_of_differences": "consider the Wilcoxon signed-rank test",
    "normality_by_group": "consider the Mann-Whitney U test",
    "homogeneity_of_variance": "the Welch test reported above does not assume equal variances",
    "expected_counts": "consider Fisher's exact test or merging sparse categories",
    "normality_of_residuals": "check for outliers or consider transforming the outcome",
    "homoscedasticity": "consider robust (HC3) standard errors",
    "multicollinearity": "consider removing or combining highly correlated predictors",
}


@dataclass
class Effect:
    name: str
    value: float | None
    estimate: float | None = None  # the quantity the CI is for
    ci_lower: float | None = None
    ci_upper: float | None = None


def cohen_d_label(d: float | None, lang: str) -> str:
    if d is None:
        return ""
    size = abs(d)
    zh, en = (("微小", "negligible") if size < 0.2 else ("小", "small") if size < 0.5
              else ("中等", "medium") if size < 0.8 else ("大", "large"))
    return f"依 Cohen（1988）的慣例屬於{zh}效果量" if lang == "zh" else f"a {en} effect by Cohen's (1988) convention"


def significance_sentence(p: float | None, alpha: float, lang: str, subject_zh: str = "差異",
                          subject_en: str = "The difference") -> str:
    sig = apa.significant(p, alpha)
    a = apa.bounded(alpha, 2)
    if lang == "zh":
        return f"{subject_zh}{'達' if sig else '未達'}統計顯著（α = {a}）。"
    return f"{subject_en} was {'' if sig else 'not '}statistically significant (α = {a})."


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


def cramers_v_label(v: float, k: int, lang: str) -> str:
    """Cohen's w benchmarks (.1 / .3 / .5) scaled by √(min(r, c) − 1)."""
    w = v * k ** 0.5
    zh, en = (("微弱", "negligible") if w < 0.1 else ("小", "small") if w < 0.3
              else ("中等", "medium") if w < 0.5 else ("大", "large"))
    return f"依 Cohen（1988）的慣例屬於{zh}關聯強度" if lang == "zh" else f"a {en} association by Cohen's (1988) convention"


class ChiSquareReport:
    def headline(self, plan, s) -> str:
        return (f"χ²({apa.df(s['df'])}, N = {s['n']}) = {apa.num(s['chi2'])}, p {apa.p_value(s['p'])}, "
                f"Cramér's V = {apa.bounded(s['cramers_v'])}")

    def primary_p(self, s) -> float | None:
        return s["p"]

    def effect(self, s) -> Effect:
        return Effect("Cramér's V", s["cramers_v"])

    def table(self, plan, s, lang) -> str:
        r, c = plan["variables"]["row"], plan["variables"]["column"]
        head = f"| {r} \\ {c} | " + " | ".join(s["column_levels"]) + " |"
        sep = "|" + "---|" * (len(s["column_levels"]) + 1)
        lp, rp = ("（", "）") if lang == "zh" else (" (", ")")
        body = [f"| {lvl} | " + " | ".join(f"{o}{lp}{apa.pct(pr)}{rp}" for o, pr in zip(obs, props)) + " |"
                for lvl, obs, props in zip(s["row_levels"], s["observed"], s["row_proportions"])]
        note = "括號內為列百分比。" if lang == "zh" else "Row percentages in parentheses."
        return "\n".join([head, sep, *body, "", note])

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


REPORTS = {"paired-t-test": PairedReport(), "independent-t-test": IndependentReport(),
           "chi-square": ChiSquareReport(), "correlation": CorrelationReport(),
           "linear-regression": RegressionReport()}


def method_report(method: str):
    return REPORTS[method]


def headline(plan: dict, results: dict) -> str:
    """One-line statistical summary for terminal output."""
    return method_report(plan["method"]).headline(plan, results["statistics"])


def assumption_lines(results: dict, spec: MethodSpec, lang: str) -> list[str]:
    alternatives = {a.id: a.alternative for a in spec.assumptions}
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
        else:
            verdict = "符合" if lang == "zh" else "met"
        sep = "：" if lang == "zh" else ": "
        lines.append(f"- {label}{sep}" + (f"{stat}，{verdict}" if lang == "zh" and stat else
                                         f"{stat}, {verdict}" if stat else verdict))
    return lines


def build_draft(plan: dict, results: dict, manifest: dict, spec: MethodSpec, lang: str = "zh") -> str:
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
    assumptions = assumption_lines(results, spec, lang)
    if assumptions:
        lines += ["## 統計假設檢查（Assumption Checks）" if zh else "## Assumption Checks", "", *assumptions, ""]
    lines += ["## 研究限制（Limitations）" if zh else "## Limitations", "", r.limitations(lang), ""]
    return "\n".join(lines)


def jev_appendix(review, lang: str) -> str:
    zh = lang == "zh"
    lines = [JEV_HEADING, ""]
    lines += [f"- `{c.verdict}` `{c.check_id}`：{c.reason}" for c in review.checks]
    uncertain = review.by_verdict("UNCERTAIN")
    if uncertain:
        lines += ["", "審查提醒：以上 UNCERTAIN 項目需要研究者判斷後再定稿。" if zh
                  else "Reminder: UNCERTAIN items above need the researcher's judgement before finalising."]
    lines += ["", DISCLAIMER[lang], ""]
    return "\n".join(lines)
