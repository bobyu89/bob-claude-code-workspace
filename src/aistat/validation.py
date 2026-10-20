"""JEV: structured YES / NO / UNCERTAIN review gates.

JEV is a process review, not a guarantee of statistical correctness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from .data import Variable
from .methods import MethodSpec, plan_columns

YES, NO, UNCERTAIN = "YES", "NO", "UNCERTAIN"
GATE_A = "method_validation"
GATE_B = "result_validation"
MISSING_OK_RATIO = 0.05


@dataclass
class Check:
    gate: str
    check_id: str
    verdict: str
    reason: str
    evidence: list = field(default_factory=list)
    required_action: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Review:
    gate: str
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return all(c.verdict == YES for c in self.checks)

    def by_verdict(self, verdict: str) -> list[Check]:
        return [c for c in self.checks if c.verdict == verdict]

    def to_dict(self) -> dict:
        return {"gate": self.gate, "passed": self.passed, "checks": [c.to_dict() for c in self.checks]}

    @classmethod
    def from_dict(cls, raw: dict) -> "Review":
        return cls(raw["gate"], [Check(**c) for c in raw["checks"]])

    def summary(self) -> str:
        return "\n".join(f"[{c.verdict}] {c.check_id}：{c.reason}" for c in self.checks)


# ---- Gate A ------------------------------------------------------------------


def gate_a(plan: dict, spec: MethodSpec, df: pd.DataFrame, dictionary: dict[str, Variable],
           confirmations: list[dict]) -> Review:
    variables = plan["variables"]
    columns = plan_columns(variables)
    missing_cols = [c for c in columns if c not in df.columns]
    if missing_cols:
        return Review(GATE_A, [Check(
            GATE_A, "variables_exist", NO,
            f"資料集中找不到欄位：{', '.join(missing_cols)}",
            evidence=[{"available_columns": list(df.columns)}],
            required_action="fix_plan",
        )])

    checks = [
        Check(GATE_A, "variables_exist", YES, f"欄位皆存在：{', '.join(columns)}", evidence=columns),
        _measurement_level(spec, variables, dictionary),
    ]
    complete = df[columns].dropna()
    checks += [fn(plan, spec, df, complete) for fn in EXTRA_CHECKS.get(spec.id, ())]
    checks += [DESIGN_CHECKS[d](plan, spec, complete) for d in spec.design_checks]
    checks += [_missing_data(spec, df, complete), _sample_size(spec, complete), _assumptions_planned(spec)]
    return _apply_confirmations(checks, confirmations)


def _measurement_level(spec: MethodSpec, variables: dict, dictionary: dict[str, Variable]) -> Check:
    wrong, unsure, evidence = [], [], []
    for role in spec.roles:
        cols = variables[role.name] if role.multiple else [variables[role.name]]
        for col in cols:
            var = dictionary[col]
            evidence.append({"role": role.name, "variable": col, "level": var.level,
                             "level_source": var.level_source, "required": list(role.levels)})
            type_ok = var.type == "numeric" or not role.numeric
            if type_ok and var.level in role.levels:
                continue
            desc = f"{col}（{role.label}）為 {var.level}，此方法需要 {' / '.join(role.levels)}"
            if type_ok and var.ambiguous:
                unsure.append(desc)
            else:
                wrong.append(desc)
    if wrong:
        return Check(GATE_A, "measurement_level", NO, "；".join(wrong), evidence, "fix_plan")
    if unsure:
        return Check(
            GATE_A, "measurement_level", UNCERTAIN,
            "；".join(unsure) + "。尺度為系統推論，請以 `aistat dictionary set` 設定正確尺度後重新驗證，"
            "或確認以此方法所需尺度處理",
            evidence, "confirm_measurement_level",
        )
    return Check(GATE_A, "measurement_level", YES, "所有變項尺度符合方法要求", evidence)


def _pairing_structure(plan, spec, complete) -> Check:
    v = plan["variables"]
    return Check(
        GATE_A, "pairing_structure", UNCERTAIN,
        f"尚未確認 {v['before']} 與 {v['after']} 是否來自相同受試者（同一列為同一人）",
        evidence=[{"complete_pairs": len(complete)}],
        required_action="request_user_confirmation",
    )


def _independence(plan, spec, complete) -> Check:
    return Check(
        GATE_A, "independence", UNCERTAIN,
        "尚未確認每一列為不同受試者且觀察值互相獨立（沒有同一人重複測量或配對）",
        evidence=[{"n": len(complete)}],
        required_action="request_user_confirmation",
    )


DESIGN_CHECKS = {"pairing_structure": _pairing_structure, "independence": _independence}

# method id -> extra Gate A checks: fn(plan, spec, df, complete) -> Check
EXTRA_CHECKS: dict[str, tuple] = {}


def _missing_data(spec: MethodSpec, df: pd.DataFrame, complete: pd.DataFrame) -> Check:
    total, kept = len(df), len(complete)
    excluded = total - kept
    ratio = excluded / total if total else 0.0
    strategy = {"complete-pairs": "只保留前後測皆有值的配對", "listwise": "排除任一分析變項缺失的列"}[spec.missing_strategy]
    evidence = [{"strategy": spec.missing_strategy, "rows": total, "excluded": excluded}]
    if ratio <= MISSING_OK_RATIO:
        return Check(GATE_A, "missing_data", YES, f"{strategy}：排除 {excluded}/{total} 列", evidence)
    return Check(
        GATE_A, "missing_data", UNCERTAIN,
        f"{strategy}：將排除 {excluded}/{total} 列（{ratio:.0%}），請確認缺失是否為隨機、排除是否合理",
        evidence, "request_user_confirmation",
    )


def _sample_size(spec: MethodSpec, complete: pd.DataFrame) -> Check:
    n = len(complete)
    if n >= spec.min_n:
        return Check(GATE_A, "sample_size", YES, f"有效樣本 {n}（最低需求 {spec.min_n}）", [{"n": n}])
    return Check(GATE_A, "sample_size", NO, f"有效樣本只有 {n}，{spec.name_zh}至少需要 {spec.min_n}",
                 [{"n": n}], "collect_more_data")


def _assumptions_planned(spec: MethodSpec) -> Check:
    if not spec.assumptions:
        return Check(GATE_A, "assumptions_planned", YES, "此方法沒有需要另外檢查的統計假設")
    labels = "、".join(a.label for a in spec.assumptions)
    return Check(GATE_A, "assumptions_planned", YES, f"執行時由統計引擎檢查：{labels}",
                 [a.id for a in spec.assumptions])


def _apply_confirmations(checks: list[Check], confirmations: list[dict]) -> Review:
    confirmed = {c["check_id"]: c for c in confirmations}
    for c in checks:
        if c.verdict == UNCERTAIN and c.check_id in confirmed:
            c.verdict = YES
            c.evidence = [*c.evidence, {"user_confirmed_at": confirmed[c.check_id]["ts"]}]
            c.reason = f"使用者已確認：{c.reason}"
            c.required_action = None
    return Review(GATE_A, checks)
