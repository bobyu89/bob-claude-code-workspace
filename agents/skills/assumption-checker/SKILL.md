---
name: assumption-checker
description: 解讀統計引擎回傳的假設檢查（常態性、變異數同質、期望次數、殘差、共線性），並在假設不符時提出替代方法建議。分析執行後、撰寫結論前使用。
---

# Assumption Checker

## 觸發條件

`execute_statistical_analysis` 完成，`retrieve_analysis_results` 的 `assumptions` 有內容。

## 輸入

`results.json` 的 `assumptions` 陣列，每項：`{id, label, test, statistic, p, violated, ...}`。
`violated: null` 表示樣本數或變異不足、無法檢定；`informational: true` 表示僅供參考（例如 Welch t 已不需變異數同質）。

## 對應建議

| id | 違反時 |
|---|---|
| `normality_of_differences` | Wilcoxon signed-rank test；樣本數大時 t 檢定較穩健 |
| `normality_by_group` | Mann-Whitney U test |
| `homogeneity_of_variance` | 已以 Welch 報告，不需處理 |
| `expected_counts` | Fisher's exact test 或合併類別 |
| `normality` | Spearman 等級相關 |
| `normality_of_residuals` | 檢查極端值、轉換依變項 |
| `homoscedasticity` | robust（HC3）標準誤 |
| `multicollinearity` | 移除或合併高度相關的預測變項 |

## 禁止事項

- 不自行計算檢定統計量；只引用 `results.json`。
- 假設不符時不要自動換方法重跑；向研究者說明，由研究者決定是否建立新計畫。
- 有對應替代方法時（Wilcoxon、Mann-Whitney、Fisher、Spearman），Gate B 理由會附上 `aistat plan --alternative-of <RUN>`；請研究者決定是否建立替代計畫，不要自己重組變項。
- 替代方法若 aistat 尚未支援（例如 Kruskal-Wallis），如實告知。

## 測試案例

`tests/test_review_report.py::test_violated_assumption_is_flagged_with_alternative`、`tests/test_chi_square.py::test_sparse_table_flags_expected_counts`。
