---
name: statistical-planner
description: 依研究設計建立 aistat 分析計畫並解讀 JEV Gate A（YES / NO / UNCERTAIN）。在研究設計確定後、執行分析之前使用。
---

# Statistical Planner

## 觸發條件

研究設計與候選方法已確定（見 `research-designer`）。

## 輸入 Schema

`create_analysis_plan` 的參數（完整角色定義見 `list_methods`）：

```json
{
  "method": "paired-t-test",
  "variables": {"before": "pre_score", "after": "post_score"},
  "dataset_id": "optional",
  "options": {"alpha": 0.05, "conf_level": 0.95}
}
```

| 方法 | 變項角色 | 選項 |
|---|---|---|
| `descriptives` | `variables`（多個） | — |
| `paired-t-test` | `before`、`after` | `alternative=two-sided` |
| `independent-t-test` | `outcome`、`group` | `alternative=two-sided` |
| `chi-square` | `row`、`column` | — |
| `correlation` | `x`、`y` | `method=pearson|spearman` |
| `linear-regression` | `outcome`、`predictors`（多個） | — |
| `wilcoxon-signed-rank` | `before`、`after` | — |
| `mann-whitney-u` | `outcome`、`group` | — |
| `fisher-exact` | `row`、`column`（皆二元） | — |
| `one-way-anova` | `outcome`、`group`（3 組以上） | — |

假設不符時，用 `create_analysis_plan(alternative_of="<RUN>")`（CLI：`aistat plan --alternative-of <RUN>`）建立替代計畫，不要自己重組變項。

## 輸出 Schema

`{run_id, status, gate_a: {gate, passed, checks: [{gate, check_id, verdict, evidence, reason, required_action}]}, next_step}`，
定義見 `schemas/jev_review.schema.json`、`schemas/analysis_plan.schema.json`。

## 解讀 Gate A

- `NO`：計畫被擋下（`BLOCKED`）。說明理由與修正方式（改方法、`aistat dictionary set` 後 `validate_analysis_plan`）。
- `UNCERTAIN`：逐項用白話問研究者，例如 `pairing_structure`：「前後測是同一批學生、同一列是同一人嗎？」
- 全部確認後，把 `next_step` 的 `aistat approve ... --confirm ...` 指令交給研究者本人執行。

## 禁止事項

- 不要為了通過 Gate A 而更換變項或方法；改變計畫前先徵得研究者同意。
- 不自行核准（沒有 approve 工具是刻意的）。

## 錯誤處理

- `不支援的統計方法`、`缺少變項角色`、`不適用的變項角色` → 對照上表修正參數。

## 測試案例

`tests/test_paired_flow.py`、`tests/test_regression.py::test_few_cases_per_predictor_needs_confirmation_and_too_few_blocks`。
