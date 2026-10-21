"""JEV: structured YES / NO / UNCERTAIN review gates.

JEV is a process review, not a guarantee of statistical correctness.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

import pandas as pd

from .data import Variable
from .methods import MethodSpec, alternative_command, plan_columns

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
        """Gate A needs every check YES; Gate B only needs no NO (UNCERTAIN is reported, not blocking)."""
        if self.gate == GATE_B:
            return not self.by_verdict(NO)
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
    checks += [fn(plan, spec, complete, dictionary) for fn in EXTRA_CHECKS.get(spec.id, ())]
    checks += [DESIGN_CHECKS[d](plan, spec, complete) for d in spec.design_checks]
    checks += [_missing_data(spec, df, complete), _sample_size(spec, complete, plan, df), _assumptions_planned(spec, plan)]
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

def _group_structure(plan, spec, complete, dictionary) -> Check:
    """Every categorical role needs at least two levels; a two-group comparison needs exactly two,
    each with at least two observations."""
    problems, evidence = [], []
    for role in spec.string_roles:
        col = plan["variables"][role]
        counts = complete[col].astype(str).value_counts().sort_index()
        evidence.append({"role": role, "variable": col, "counts": {str(k): int(v) for k, v in counts.items()}})
        k = len(counts)
        if spec.exact_groups is not None and k != spec.exact_groups:
            problems.append(f"{col} 有 {k} 組（{'、'.join(map(str, counts.index))}），"
                            f"{spec.name_zh}需要恰好 {spec.exact_groups} 組")
        elif spec.min_groups is not None and k < spec.min_groups:
            hint = f"；只有兩組時請改用 {spec.fewer_groups_method}" if spec.fewer_groups_method and k == 2 else ""
            problems.append(f"{col} 只有 {k} 組，{spec.name_zh}需要至少 {spec.min_groups} 組{hint}")
        elif k < 2:
            problems.append(f"{col} 只有 {k} 個類別，無法比較")
        elif counts.min() < spec.min_per_group:
            problems.append(f"{col} 有組別少於 {spec.min_per_group} 筆有效資料")
    if problems:
        return Check(GATE_A, "group_structure", NO, "；".join(problems), evidence, "fix_plan")
    return Check(GATE_A, "group_structure", YES, "分組結構符合方法要求", evidence)


def _correlation_type(plan, spec, complete, dictionary) -> Check:
    method = plan["options"]["method"]
    if method == "spearman":
        return Check(GATE_A, "correlation_type", YES, "Spearman 等級相關適用 ordinal 與 scale 變項")
    ordinal = [c for c in plan_columns(plan["variables"]) if dictionary[c].level == "ordinal"]
    if ordinal:
        return Check(GATE_A, "correlation_type", UNCERTAIN,
                     f"{', '.join(ordinal)} 為 ordinal，Pearson 相關假設等距尺度；可改用 --option method=spearman，"
                     "或確認以等距尺度處理", [{"ordinal": ordinal}], "request_user_confirmation")
    return Check(GATE_A, "correlation_type", YES, "兩變項皆為 scale，適用 Pearson 相關")


def _predictor_coding(plan, spec, complete, dictionary) -> Check:
    multi = [c for c in plan["variables"]["predictors"]
             if dictionary[c].level == "nominal" and complete[c].nunique() > 2]
    if multi:
        return Check(GATE_A, "predictor_coding", NO,
                     f"{', '.join(multi)} 為多類別名目變項，需先建立虛擬變項（dummy coding）；此版本尚未支援",
                     [{"variables": multi}], "fix_plan")
    return Check(GATE_A, "predictor_coding", YES, "預測變項皆為數值或二元編碼")


# method id -> extra Gate A checks: fn(plan, spec, complete_rows, dictionary) -> Check
EXTRA_CHECKS: dict[str, tuple] = {
    "independent-t-test": (_group_structure,),
    "mann-whitney-u": (_group_structure,),
    "one-way-anova": (_group_structure,),
    "chi-square": (_group_structure,),
    "fisher-exact": (_group_structure,),
    "correlation": (_correlation_type,),
    "linear-regression": (_predictor_coding,),
}


def _missing_data(spec: MethodSpec, df: pd.DataFrame, complete: pd.DataFrame) -> Check:
    if spec.missing_strategy == "available-case":
        counts = {c: int(df[c].isna().sum()) for c in complete.columns}
        detail = "、".join(f"{c} 缺 {k}" for c, k in counts.items() if k) or "無缺失"
        return Check(GATE_A, "missing_data", YES, f"各變項分別以有效值計算並報告缺失數（{detail}）",
                     [{"strategy": spec.missing_strategy, "missing": counts}])
    total, kept = len(df), len(complete)
    excluded = total - kept
    ratio = excluded / total if total else 0.0
    strategy = {"complete-pairs": "只保留前後測皆有值的配對",
                "listwise": "排除任一分析變項缺失的列"}[spec.missing_strategy]
    evidence = [{"strategy": spec.missing_strategy, "rows": total, "excluded": excluded}]
    if ratio <= MISSING_OK_RATIO:
        return Check(GATE_A, "missing_data", YES, f"{strategy}：排除 {excluded}/{total} 列", evidence)
    return Check(
        GATE_A, "missing_data", UNCERTAIN,
        f"{strategy}：將排除 {excluded}/{total} 列（{ratio:.0%}），請確認缺失是否為隨機、排除是否合理",
        evidence, "request_user_confirmation",
    )


def _sample_size(spec: MethodSpec, complete: pd.DataFrame, plan: dict, df: pd.DataFrame) -> Check:
    if spec.missing_strategy == "available-case":
        n = min(int(df[c].notna().sum()) for c in complete.columns)
    else:
        n = len(complete)
    k = sum(len(plan["variables"][r.name]) for r in spec.roles if r.multiple) if spec.per_predictor_n else 0
    required = spec.min_n + k
    recommended = spec.per_predictor_n * k
    evidence = [{"n": n, "required": required, "recommended": recommended}]
    if n < required:
        return Check(GATE_A, "sample_size", NO, f"有效樣本只有 {n}，{spec.name_zh}至少需要 {required}",
                     evidence, "collect_more_data")
    if n < recommended:
        return Check(GATE_A, "sample_size", UNCERTAIN,
                     f"有效樣本 {n}，低於每個預測變項約 {spec.per_predictor_n} 筆的建議（{recommended}）；"
                     "估計可能不穩定，請確認是否接受", evidence, "request_user_confirmation")
    return Check(GATE_A, "sample_size", YES, f"有效樣本 {n}（最低需求 {required}）", evidence)


def _assumptions_planned(spec: MethodSpec, plan: dict) -> Check:
    planned = [a for a in spec.assumptions if a.id in plan["assumptions"]]
    if not planned:
        return Check(GATE_A, "assumptions_planned", YES, spec.no_assumption_note)
    labels = "、".join(a.label for a in planned)
    return Check(GATE_A, "assumptions_planned", YES, f"執行時由統計引擎檢查：{labels}", [a.id for a in planned])


def _apply_confirmations(checks: list[Check], confirmations: list[dict]) -> Review:
    confirmed = {c["check_id"]: c for c in confirmations}
    for c in checks:
        if c.verdict == UNCERTAIN and c.check_id in confirmed:
            c.verdict = YES
            c.evidence = [*c.evidence, {"user_confirmed_at": confirmed[c.check_id]["ts"]}]
            c.reason = f"使用者已確認：{c.reason}"
            c.required_action = None
    return Review(GATE_A, checks)


# ---- Gate B ------------------------------------------------------------------

NUMBER = re.compile(r"(?<![A-Za-z0-9_.])-?(?:\d+\.\d+|\.\d+|\d+)(?![A-Za-z0-9_])")
P_TOKEN = re.compile(r"(?<![A-Za-z])p\s*([=<>≤≥])\s*(-?\d*\.?\d+)")
CODE_SPAN = re.compile(r"`[^`]*`")
SENTENCE_END = re.compile(r"[。！？\n]|[.!?](?=\s|$)")
CAUSAL = re.compile(
    r"導致|造成|證明|證實|引起|歸因於|\bcaus(?:e|es|ed|ing)\b|\bprov(?:e|es|ed|ing)\b|\bled to\b"
    r"|\bresult(?:s|ed)? in\b|\bdue to\b|\bbecause of\b",
    re.IGNORECASE,
)
NONSIG = re.compile(r"未達(?:統計)?顯著|不顯著|無顯著|沒有顯著|not statistically significant|non-?significant"
                    r"|not significant|did not reach (?:statistical )?significance", re.IGNORECASE)
SIG = re.compile(r"達(?:到)?(?:統計)?顯著|statistically significant|\bsignificant(?:ly)?\b", re.IGNORECASE)


@dataclass
class Provenance:
    results_exists: bool
    results_sha256: str | None
    recorded_sha256: str | None
    plan_data_sha256: str
    executed_data_sha256: str | None
    current_data_sha256: str


def gate_b(plan: dict, spec: MethodSpec, results: dict | None, text: str, provenance: Provenance,
           report) -> Review:
    checks = [_engine_provenance(results, provenance)]
    if results is None or checks[0].verdict == NO:
        return Review(GATE_B, checks)
    audited = _audited_text(text, plan)
    s = results["statistics"]
    checks += [
        _values_traceable(audited, plan, results),
        _p_value_format(audited),
        _effect_size_ci(audited, report.effect(s)),
        _causal_language(audited, spec),
        _significance_consistency(audited, report.primary_p(s), plan["options"]["alpha"]),
        _assumptions_met(results, spec, plan),
    ]
    return Review(GATE_B, checks)


def _engine_provenance(results: dict | None, p: Provenance) -> Check:
    problems = []
    if not p.results_exists or results is None:
        problems.append("找不到 raw_outputs/results.json")
    else:
        if p.results_sha256 != p.recorded_sha256:
            problems.append("results.json 的雜湊與執行時紀錄不符，原始輸出可能被修改")
        engine = results.get("engine") or {}
        if not engine.get("name") or not engine.get("version"):
            problems.append("原始輸出缺少引擎名稱或版本")
    if p.executed_data_sha256 != p.plan_data_sha256:
        problems.append("執行時的資料雜湊與分析計畫不符")
    if p.current_data_sha256 != p.plan_data_sha256:
        problems.append("目前資料檔與分析計畫的雜湊不符")
    evidence = [{"results_sha256": p.results_sha256, "data_sha256": p.current_data_sha256}]
    if problems:
        return Check(GATE_B, "engine_provenance", NO, "；".join(problems), evidence, "rerun_analysis")
    return Check(GATE_B, "engine_provenance", YES,
                 f"結果來自 {results['engine']['version']}，原始輸出與資料雜湊一致", evidence)


def _labels(plan: dict) -> list[str]:
    levels = [str(x) for values in (plan.get("levels") or {}).values() for x in values]
    return plan_columns(plan["variables"]) + levels + [plan["dataset_id"]]


def _audited_text(text: str, plan: dict) -> str:
    """The part of a draft whose numbers must be traceable: code spans and the JEV appendix excluded,
    and variable names / category labels removed so digits inside names are not read as statistics.
    Purely numeric labels (e.g. Likert codes) are left in place and allowed by `allowed_tokens`."""
    from .reporting import JEV_HEADING

    text = text.split(JEV_HEADING, 1)[0]
    text = CODE_SPAN.sub(" ", text)
    for name in sorted({n for n in _labels(plan) if not NUMBER.fullmatch(n)}, key=len, reverse=True):
        # ASCII boundaries only: label "no" must not eat the "no" in "not"
        text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", " ", text)
    return text


def _numbers(obj) -> list[float]:
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in _numbers(v)]
    if isinstance(obj, list):
        return [x for v in obj for x in _numbers(v)]
    return []


def allowed_tokens(plan: dict, results: dict) -> set[str]:
    from . import apa
    from .reporting import CITATION_TOKENS

    tokens = set(CITATION_TOKENS) | {".001", ".999"} | {n for n in _labels(plan) if NUMBER.fullmatch(n)}
    values = _numbers(results["statistics"]) + _numbers(results.get("assumptions", []))
    values += _numbers(plan["options"])
    for v in values:
        for x in (v, abs(v), -v):
            tokens.update(apa.num(x, d) for d in range(0, 5))
            tokens.update(apa.bounded(x, d) for d in (2, 3))
            tokens.add(apa.df(x))
            tokens.add(apa.num(100 * x, 1))
            tokens.add(apa.num(100 * x, 0))
    return tokens


def _values_traceable(text: str, plan: dict, results: dict) -> Check:
    allowed = allowed_tokens(plan, results)
    found = NUMBER.findall(text)
    untraced = sorted({t for t in found if t not in allowed}, key=found.index)
    if untraced:
        return Check(GATE_B, "values_traceable", NO,
                     f"草稿中的數值無法對應到引擎原始輸出：{', '.join(untraced)}",
                     [{"untraced": untraced}], "regenerate_or_fix_draft")
    return Check(GATE_B, "values_traceable", YES, f"草稿中 {len(found)} 個數值皆可追溯到原始輸出或計畫參數",
                 [{"numbers_checked": len(found)}])


def _p_value_format(text: str) -> Check:
    problems = []
    for op, value in P_TOKEN.findall(text):
        if value.startswith("0."):
            problems.append(f"p {op} {value}（APA 7 不寫前導零）")
        try:
            numeric = float(value)
        except ValueError:
            continue
        if numeric == 0:
            problems.append(f"p {op} {value}（p 不會等於 0，應寫 p < .001）")
        elif op == "=" and numeric < 0.001:
            problems.append(f"p {op} {value}（小於 .001 應寫 p < .001）")
        elif numeric > 1:
            problems.append(f"p {op} {value}（p 不可能大於 1）")
    if problems:
        return Check(GATE_B, "p_value_format", NO, "；".join(problems), problems, "fix_draft")
    return Check(GATE_B, "p_value_format", YES, "p 值格式符合 APA 7")


def _effect_size_ci(text: str, effect) -> Check:
    from . import apa

    if effect is None:
        return Check(GATE_B, "effect_size_ci", YES, "此方法不涉及效果量或信賴區間")
    evidence = [{"effect": effect.name, "value": effect.value, "ci": [effect.ci_lower, effect.ci_upper]}]
    if effect.value is None:
        return Check(GATE_B, "effect_size_ci", UNCERTAIN, f"引擎未產生有限的 {effect.name}（可能變異為 0 或估計值為無限大）", evidence,
                     "review_manually")
    if effect.ci_lower is not None and effect.ci_upper is not None:
        if not effect.ci_lower < effect.ci_upper:
            return Check(GATE_B, "effect_size_ci", NO, "信賴區間下限不小於上限", evidence, "rerun_analysis")
        if effect.estimate is not None and not effect.ci_lower <= effect.estimate <= effect.ci_upper:
            return Check(GATE_B, "effect_size_ci", NO, "點估計值不在信賴區間內", evidence, "rerun_analysis")
    missing = [apa.num(v) for v in (effect.value, effect.ci_lower, effect.ci_upper)
               if v is not None and apa.num(v) not in text and apa.bounded(v) not in text]
    if missing:
        return Check(GATE_B, "effect_size_ci", UNCERTAIN, f"草稿未報告效果量或信賴區間（缺 {', '.join(missing)}）",
                     evidence, "fix_draft")
    if effect.implausible_above is not None and abs(effect.value) > effect.implausible_above:
        return Check(GATE_B, "effect_size_ci", UNCERTAIN,
                     f"{effect.name} = {apa.num(effect.value)} 異常大，請確認資料是否有輸入錯誤或極端值", evidence,
                     "review_manually")
    return Check(GATE_B, "effect_size_ci", YES, f"{effect.name} 與信賴區間已報告且合理", evidence)


def _causal_language(text: str, spec: MethodSpec) -> Check:
    hits = sorted({m.group(0) for m in CAUSAL.finditer(text)})
    if hits:
        return Check(GATE_B, "causal_language", NO,
                     f"草稿使用因果用語：{', '.join(hits)}。{spec.name_zh}只能支持差異或關聯的結論；"
                     "若為隨機分派實驗，請在定稿時由研究者自行斟酌措辭",
                     hits, "fix_draft")
    return Check(GATE_B, "causal_language", YES, "未發現因果過度推論用語")


def _significance_consistency(text: str, primary_p: float | None, alpha: float) -> Check:
    """Each sentence claiming (non)significance must agree with the p values it cites,
    or with the method's primary p value when it cites none."""
    problems = []
    for sentence in SENTENCE_END.split(text):
        if NONSIG.search(sentence):
            claim = False
        elif SIG.search(sentence):
            claim = True
        else:
            continue
        cited = {_p_is_significant(op, v, alpha) for op, v in P_TOKEN.findall(sentence)} - {None}
        if len(cited) > 1:
            continue  # the sentence cites several tests with different outcomes
        actual = cited.pop() if cited else (primary_p is not None and primary_p < alpha)
        if claim != actual:
            problems.append(sentence.strip())
    if problems:
        return Check(GATE_B, "significance_consistency", NO,
                     "顯著性敘述與 p 值不一致：" + " / ".join(problems), problems, "fix_draft")
    return Check(GATE_B, "significance_consistency", YES, "顯著性敘述與 p 值、α 一致")


def _p_is_significant(op: str, value: str, alpha: float) -> bool | None:
    try:
        v = float(value)
    except ValueError:
        return None
    if op == "=":
        return v < alpha
    if op in "<≤":
        return True if v <= alpha else None
    return False if v >= alpha else None


def _assumptions_met(results: dict, spec: MethodSpec, plan: dict) -> Check:
    alternatives = {a.id: a.alternative for a in spec.assumptions}
    relevant = [a for a in results.get("assumptions", []) if not a.get("informational")]
    violated = [a for a in relevant if a.get("violated")]
    untested = [a for a in relevant if a.get("violated") is None]
    evidence = results.get("assumptions", [])
    if violated:
        detail = "；".join(f"{a['label']}未符合，{alternatives.get(a['id'], '請考慮其他方法')}" for a in violated)
        command = alternative_command(plan)
        if command:
            detail += f"；可執行 `{command}` 建立替代計畫（仍須通過 Gate A 並由研究者核准）"
        return Check(GATE_B, "assumptions_met", UNCERTAIN, detail, evidence, "review_manually")
    if untested:
        return Check(GATE_B, "assumptions_met", UNCERTAIN,
                     "、".join(a["label"] for a in untested) + " 無法檢定（樣本數或變異不足）", evidence, "review_manually")
    return Check(GATE_B, "assumptions_met", YES, "引擎檢查的統計假設均未發現違反", evidence)
