---
name: result-reviewer
description: 以 JEV Gate B 審查統計結果草稿（數值可追溯、p 值格式、效果量與 CI、因果用語、顯著性敘述一致、假設檢查）。產出或改寫任何結果文字之前使用。
---

# Result Reviewer

## 觸發條件

- 分析已執行（`EXECUTED`），準備產生報告。
- 你或研究者改寫了結果段落，需要再次檢查。

## 輸入

`review_statistical_results(run_id, draft=None | "<改寫後的 Markdown>", lang="zh" | "en")`。

## 檢查項目

| check_id | NO 的情況 |
|---|---|
| `engine_provenance` | 原始輸出遺失、被修改，或資料雜湊不符 |
| `values_traceable` | 草稿出現引擎原始輸出沒有的數字（捏造或打錯） |
| `p_value_format` | `p = .000`、`p = 0.03`（前導零）、p > 1 |
| `effect_size_ci` | CI 上下限顛倒、點估計不在 CI 內 |
| `causal_language` | 「證明」「導致」「造成」「caused」「proves」等 |
| `significance_consistency` | 「達顯著」與 p 值、α 不符 |
| `assumptions_met` | 只會是 UNCERTAIN：假設不符或無法檢定 |

## 改寫規則

- 數字只能從系統草稿或 `results.json` 照抄（含 APA 格式，例如 `p = .003`、`p < .001`）。
- 變項名稱、run ID、雜湊可以出現；識別碼請放在反引號內。
- 改寫後一定要再跑一次 Gate B；NO 全部消除才能產生報告。

## 禁止事項

- 不要為了通過 Gate B 修改 `results.json` 或繞過檢查。
- JEV 是流程審查，不是統計正確性的保證；向研究者說明 UNCERTAIN 項目。

## 測試案例

`tests/test_review_report.py`、`tests/test_all_methods.py`。
