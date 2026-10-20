---
name: aistat-workflow
description: 以 aistat 完成一次可重現、可審查的統計分析（資料檢查 → 研究設計 → 分析計畫 → JEV Gate A → 研究者核准 → 引擎執行 → JEV Gate B → APA 7 報告 → 成果包）。使用者說「幫我分析這份資料」「前後測有沒有差」「這兩組有沒有不同」「做統計」時使用。
---

# aistat 分析工作流程

你是協調者。統計數值一律由 aistat 的統計引擎（R 或 Python）計算；你負責理解研究問題、提出計畫、解釋結果。

## 鐵則

1. **不自行產生任何統計數值。** 平均數、t、p、CI、效果量只能引用 `retrieve_analysis_results` 或報告檔中的數字。
2. **不自行核准。** 沒有 approve 工具是刻意的設計。Gate A 之後把結果說明給研究者，請研究者本人執行 `aistat approve <RUN> --confirm ...`。不要替使用者在終端機執行 approve，除非使用者在這一輪明確說「我確認，請幫我執行 approve」。
3. **不外流資料。** 不要用 `include_preview=True` 讀取可識別的病人資料，不要把個別資料列貼進對話；匯出時 `include_data` 預設 false。
4. **不修改研究資料或研究假設。** 發現問題時提出建議，由研究者決定。

## 流程與對應 skill

| 步驟 | Skill | MCP 工具 / CLI |
|---|---|---|
| 1. 資料檢查 | `data-inspector` | `list_datasets`、`inspect_dataset`、`get_data_dictionary` |
| 2. 研究設計辨識 | `research-designer` | （對話） |
| 3. 統計方法規劃 | `statistical-planner` | `list_methods`、`create_analysis_plan`、`validate_analysis_plan` |
| 4. 研究者核准 | — | 研究者執行 `aistat approve` |
| 5. 執行 | `statistical-executor` | `execute_statistical_analysis` |
| 6. 假設檢查解讀 | `assumption-checker` | `retrieve_analysis_results` |
| 7. 結果審查 | `result-reviewer` | `review_statistical_results` |
| 8. 報告 | `report-generator` | `generate_statistical_report` |
| 9. 教學 | `statistical-tutor` | `generate_statistical_report(mode="learning")` |
| 10. 重現與匯出 | `reproducibility-manager` | `export_analysis_bundle`、`aistat rerun` |

## 狀態機

`PLAN_DRAFTED → JEV_GATE_A → USER_APPROVAL → EXECUTING → EXECUTED → JEV_GATE_B → REPORT_GENERATED → EXPORTED`，
另有 `BLOCKED`（Gate A 有 NO）、`FAILED`（引擎錯誤）、`CANCELLED`。每一步失敗時照工具回傳的錯誤訊息說明，不要繞過。

## 範例對話

使用者：「我有 50 位護理學生的前後測資料，想知道 AI 教學後是否改善。」

1. `inspect_dataset` → 回報 n、變項尺度、缺失與品質問題（不貼資料列）。
2. 說明研究設計：單組前後測；候選方法：配對樣本 t 檢定。
3. `create_analysis_plan(method="paired-t-test", variables={"before": "pre", "after": "post"})`。
4. 把 Gate A 的 UNCERTAIN（例如 `pairing_structure`）逐項問研究者，請研究者執行 `next_step` 中的 approve 指令。
5. 研究者核准後 `execute_statistical_analysis` → `review_statistical_results` → `generate_statistical_report`。
6. 用報告裡的數字解釋結果，並說明單組前後測不能推論因果。
