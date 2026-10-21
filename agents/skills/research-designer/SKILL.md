---
name: research-designer
description: 從研究問題與資料結構辨識研究設計（單組前後測、兩組比較、類別關聯、相關、預測），並列出需要研究者確認的設計前提（配對、獨立性、分派方式）。在選擇統計方法之前使用。
---

# Research Designer

## 觸發條件

研究者描述研究問題，但尚未決定統計方法。

## 輸入

- 研究者的研究問題（自然語言）。
- `get_data_dictionary` 的變項清單與尺度。

## 輸出

一段結構化摘要：

```text
研究問題：…
研究設計：單組前後測 / 兩組比較 / 橫斷性相關 / …
依變項：…（尺度）
自變項 / 分組：…（尺度、組數）
需要確認：
- 前後測是否為相同受試者（同一列為同一人）？
- 分組是否為隨機分派？
- 是否有同一人重複出現在資料中？
```

## 對應表

| 設計 | 資料形狀 | 候選方法 |
|---|---|---|
| 單組前後測 | 同一列有前測、後測兩欄（scale） | `paired-t-test` |
| 單組前後測（ordinal 或差值偏態） | 同上，分數為 ordinal 或差值不符常態 | `wilcoxon-signed-rank` |
| 兩組比較 | 一個 scale 結果欄 + 一個兩組分組欄 | `independent-t-test` |
| 兩組比較（ordinal 或偏態） | 一個 scale / ordinal 結果欄 + 兩組分組欄 | `mann-whitney-u` |
| 兩類別變項關聯 | 兩個 nominal / ordinal 欄 | `chi-square` |
| 兩個二元變項、樣本小 | 2 × 2 表、期望次數不足 | `fisher-exact` |
| 兩連續變項關係 | 兩個 scale（或 ordinal）欄 | `correlation` |
| 預測 | 一個 scale 依變項 + 一或多個預測變項 | `linear-regression` |
| 樣本描述 | 任意變項 | `descriptives` |

三組以上比較（ANOVA）、重複量數、混合模型、存活分析目前不支援：如實告知，不要硬套。

## 禁止事項

- 不替研究者回答設計前提（配對、分派方式）；這些是 Gate A 的 UNCERTAIN 項目，必須由研究者確認。
- 非隨機分派的設計不得在任何說明中使用因果語言。

## 測試案例

設計前提對應的 Gate A 檢查：`tests/test_paired_flow.py`（pairing_structure）、`tests/test_independent_t.py`（independence）。
