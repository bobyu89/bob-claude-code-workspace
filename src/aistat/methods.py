"""Statistical method specifications.

A spec declares what a method needs (variable roles, accepted measurement
levels, options, assumptions, minimum sample). Plan validation, JEV Gate A,
engine scripts and report templates all read from these specs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import PlanError


@dataclass(frozen=True)
class Role:
    name: str
    label: str
    levels: tuple[str, ...]
    numeric: bool = False  # the column must hold numbers
    multiple: bool = False


@dataclass(frozen=True)
class Assumption:
    id: str
    label: str
    alternative: str  # what to consider when violated
    when: tuple[tuple[str, str], ...] = ()  # option values under which it applies, e.g. (("method", "pearson"),)
    min_multiple: int = 0  # needs at least this many variables in the method's multiple role

    def applies(self, options: dict, n_multiple: int = 0) -> bool:
        return n_multiple >= self.min_multiple and all(options.get(k) == v for k, v in self.when)


@dataclass(frozen=True)
class MethodSpec:
    id: str
    name_zh: str
    name_en: str
    roles: tuple[Role, ...]
    missing_strategy: str
    min_n: int
    assumptions: tuple[Assumption, ...] = ()
    design_checks: tuple[str, ...] = ()
    options: dict = field(default_factory=dict)  # option -> allowed values (tuple)
    string_roles: tuple[str, ...] = ()  # roles read as text; their levels are fixed in the plan
    per_predictor_n: int = 0  # recommended cases per variable in a multiple role (rule of thumb)
    exact_groups: int | None = None  # categorical roles must have exactly this many levels
    min_per_group: int = 1  # minimum valid cases per level of a categorical role
    text_unless_scale: bool = False  # read every non-scale variable of the multiple role as text (descriptives)

    def role(self, name: str) -> Role:
        return next(r for r in self.roles if r.name == name)


COMMON_OPTIONS = {"alpha": 0.05, "conf_level": 0.95}

METHODS: dict[str, MethodSpec] = {}


def _register(spec: MethodSpec) -> None:
    METHODS[spec.id] = spec


_register(
    MethodSpec(
        id="descriptives",
        name_zh="描述性統計",
        name_en="descriptive statistics",
        roles=(Role("variables", "變項", ("nominal", "ordinal", "scale"), multiple=True),),
        missing_strategy="available-case",
        min_n=1,
        text_unless_scale=True,
    )
)

_register(
    MethodSpec(
        id="paired-t-test",
        name_zh="配對樣本 t 檢定",
        name_en="paired-samples t test",
        roles=(
            Role("before", "前測（或條件一）", ("scale",), numeric=True),
            Role("after", "後測（或條件二）", ("scale",), numeric=True),
        ),
        missing_strategy="complete-pairs",
        min_n=3,
        assumptions=(
            Assumption(
                "normality_of_differences",
                "前後測差值近似常態分布",
                "可考慮 Wilcoxon signed-rank test（樣本數大時 t 檢定對常態性較穩健）",
            ),
        ),
        design_checks=("pairing_structure",),
        options={"alternative": ("two-sided",)},
    )
)


_register(
    MethodSpec(
        id="independent-t-test",
        name_zh="獨立樣本 t 檢定",
        name_en="independent-samples t test",
        roles=(
            Role("outcome", "結果變項", ("scale",), numeric=True),
            Role("group", "分組變項", ("nominal", "ordinal")),
        ),
        missing_strategy="listwise",
        min_n=4,
        assumptions=(
            Assumption("normality_by_group", "各組結果變項近似常態分布",
                       "可考慮 Mann-Whitney U test（各組樣本數大時 t 檢定較穩健）"),
            Assumption("homogeneity_of_variance", "兩組變異數相等",
                       "報告以 Welch t 檢定為主，不需假設變異數相等"),
        ),
        design_checks=("independence",),
        options={"alternative": ("two-sided",)},
        string_roles=("group",),
        exact_groups=2,
        min_per_group=2,
    )
)


_register(
    MethodSpec(
        id="chi-square",
        name_zh="卡方獨立性檢定",
        name_en="chi-square test of independence",
        roles=(
            Role("row", "列變項", ("nominal", "ordinal")),
            Role("column", "欄變項", ("nominal", "ordinal")),
        ),
        missing_strategy="listwise",
        min_n=4,
        assumptions=(
            Assumption("expected_counts", "期望次數足夠",
                       "可考慮 Fisher's exact test，或合併人數過少的類別"),
        ),
        design_checks=("independence",),
        string_roles=("row", "column"),
    )
)


_register(
    MethodSpec(
        id="correlation",
        name_zh="相關分析",
        name_en="correlation analysis",
        roles=(
            Role("x", "變項一", ("scale", "ordinal"), numeric=True),
            Role("y", "變項二", ("scale", "ordinal"), numeric=True),
        ),
        missing_strategy="listwise",
        min_n=4,
        assumptions=(
            Assumption("normality", "變項近似常態分布", "可考慮 Spearman 等級相關（--option method=spearman）",
                       when=(("method", "pearson"),)),
        ),
        options={"method": ("pearson", "spearman")},
    )
)


_register(
    MethodSpec(
        id="linear-regression",
        name_zh="線性迴歸",
        name_en="linear regression",
        roles=(
            Role("outcome", "依變項", ("scale",), numeric=True),
            # nominal only as a 0/1 (two-level) numeric code; see predictor_coding in Gate A
            Role("predictors", "預測變項", ("scale", "nominal"), numeric=True, multiple=True),
        ),
        missing_strategy="listwise",
        min_n=3,
        per_predictor_n=10,
        assumptions=(
            Assumption("normality_of_residuals", "殘差近似常態分布",
                       "樣本數大時影響較小；可檢查極端值或考慮轉換依變項"),
            Assumption("homoscedasticity", "殘差變異數同質",
                       "可考慮使用 robust（HC3）標準誤，或轉換依變項"),
            Assumption("multicollinearity", "預測變項之間沒有嚴重共線性",
                       "可考慮移除或合併高度相關的預測變項", min_multiple=2),
        ),
    )
)


def get_method(method: str) -> MethodSpec:
    if method not in METHODS:
        raise PlanError(f"不支援的統計方法：{method}（可用：{', '.join(METHODS)}）")
    return METHODS[method]


def normalize_variables(spec: MethodSpec, variables: dict) -> dict:
    """Validate role names and shapes; multiple-roles become lists."""
    known = {r.name for r in spec.roles}
    unknown = sorted(set(variables) - known)
    if unknown:
        raise PlanError(f"{spec.id} 不適用的變項角色：{', '.join(unknown)}（需要：{', '.join(known)}）")
    missing = [r.name for r in spec.roles if not variables.get(r.name)]
    if missing:
        raise PlanError(f"{spec.id} 缺少變項角色：{', '.join(missing)}（例：--var {missing[0]}=<欄位>）")
    out: dict = {}
    for r in spec.roles:
        value = variables[r.name]
        if r.multiple:
            items = value.split(",") if isinstance(value, str) else list(value)
            out[r.name] = [str(v).strip() for v in items if str(v).strip()]
        else:
            if not isinstance(value, str) or "," in value:
                raise PlanError(f"變項角色 {r.name} 只能指定一個欄位")
            out[r.name] = value.strip()
    columns = plan_columns(out)
    dups = sorted({c for c in columns if columns.count(c) > 1})
    if dups:
        raise PlanError(f"同一個欄位不能同時擔任多個角色：{', '.join(dups)}")
    return out


def planned_assumptions(spec: MethodSpec, variables: dict, options: dict) -> list[str]:
    n_multiple = sum(len(variables[r.name]) for r in spec.roles if r.multiple)
    return [a.id for a in spec.assumptions if a.applies(options, n_multiple)]


def categorical_columns(spec: MethodSpec, variables: dict, dictionary: dict) -> list[str]:
    """Columns the engines read as text: the spec's categorical roles, plus (for descriptives)
    every requested variable that is not on a scale level."""
    cols = [variables[r] for r in spec.string_roles]
    if spec.text_unless_scale:
        multiple = [c for r in spec.roles if r.multiple for c in variables[r.name]]
        cols += [c for c in multiple if c in dictionary and dictionary[c].level != "scale"]
    return cols


def plan_columns(variables: dict) -> list[str]:
    cols: list[str] = []
    for v in variables.values():
        cols.extend(v if isinstance(v, list) else [v])
    return cols


def resolve_options(spec: MethodSpec, options: dict | None) -> dict:
    options = dict(options or {})
    resolved = dict(COMMON_OPTIONS)
    for name, allowed in spec.options.items():
        resolved[name] = allowed[0]
    unknown = sorted(set(options) - set(resolved))
    if unknown:
        raise PlanError(f"{spec.id} 不支援的選項：{', '.join(unknown)}（可用：{', '.join(resolved)}）")
    for name, value in options.items():
        if name in COMMON_OPTIONS:
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise PlanError(f"選項 {name} 必須是數字") from None
            if not 0 < value < 1:
                raise PlanError(f"選項 {name} 必須介於 0 與 1 之間")
        elif value not in spec.options[name]:
            raise PlanError(f"選項 {name}={value} 不支援（可用：{', '.join(spec.options[name])}）")
        resolved[name] = value
    return resolved
