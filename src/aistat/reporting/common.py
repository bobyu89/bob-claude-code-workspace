"""Shared report wording: effect-size labels, significance sentences."""

from __future__ import annotations

from dataclasses import dataclass

from .. import apa


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
    implausible_above: float | None = 3.0  # |value| above this is flagged for a data check; None = no bound


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
