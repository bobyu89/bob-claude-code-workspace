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
    options: dict = field(default_factory=dict)  # option -> allowed values (tuple) or None for numeric

    def role(self, name: str) -> Role:
        return next(r for r in self.roles if r.name == name)


COMMON_OPTIONS = {"alpha": 0.05, "conf_level": 0.95}

METHODS: dict[str, MethodSpec] = {}


def _register(spec: MethodSpec) -> None:
    METHODS[spec.id] = spec


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
                "Wilcoxon signed-rank test（樣本數大時 t 檢定對常態性較穩健）",
            ),
        ),
        design_checks=("pairing_structure",),
        options={"alternative": ("two-sided",)},
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
