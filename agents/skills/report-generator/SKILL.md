---
name: report-generator
description: 在 JEV Gate B 通過後產生 APA 7 統計結果草稿（繁體中文或英文），可採用研究者或你改寫後仍通過 Gate B 的版本。研究者要「結果段落」「APA 格式」「寫進論文」時使用。
---

# Report Generator

## 觸發條件

run 狀態為 `EXECUTED`、`JEV_GATE_B` 或 `REPORT_GENERATED`。

## 輸入

`generate_statistical_report(run_id, lang="zh" | "en", mode="research" | "learning", draft=None)`。

## 輸出

- `runs/<RUN>/statistical_report.md`：結果、假設檢查、研究限制、JEV 審查紀錄與聲明。
- `mode="learning"` 時另有 `learning_notes.md`（見 `statistical-tutor`）。

## 寫作規則

- 結果段落沿用 APA 7：統計符號斜體由排版處理；p 值不加前導零；小於 .001 寫 `p < .001`；同時報告效果量與 CI。
- 研究限制段落保留；單組前後測、觀察性分組不可寫成因果。
- 若研究者要改寫（例如加上研究脈絡），把整份草稿以 `draft` 傳入；Gate B 會再審一次。

## 錯誤處理

- `JEV Gate B 未通過，不產生報告` → 依列出的 NO 項目修正草稿（見 `result-reviewer`）。
- `已匯出的分析請建立新的 run` → 狀態已是 `EXPORTED`。

## 禁止事項

- 不在對話中自行重寫一份「更好看」但未經 Gate B 的結果段落交給研究者。

## 測試案例

`tests/test_review_report.py::test_report_writes_apa_draft_and_advances_state`、`tests/test_all_methods.py`。
