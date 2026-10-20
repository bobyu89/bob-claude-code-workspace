---
name: data-inspector
description: 檢查已匯入資料集的結構與品質（變項型態、測量尺度、缺失、重複列、疑似 ID 欄），並協助研究者確認測量尺度。在建立分析計畫之前，或使用者問「我的資料有沒有問題」時使用。
---

# Data Inspector

## 觸發條件

- 新匯入資料、尚未建立分析計畫。
- 使用者詢問資料品質、缺失、變項型態。

## 輸入

- `dataset_id`（只有一個資料集時可省略）。

## 輸出（給研究者）

- 列數 × 欄數、各變項型態與測量尺度（標示「系統推論」或「使用者確認」）。
- 品質問題清單：`high_missing`、`constant`、`duplicate_rows`、`possible_id`、`ambiguous_level`。
- 需要研究者確認的事項（例如 Likert 題項是 ordinal 還是總分的一部分）。

## 工具

- MCP：`list_datasets`、`inspect_dataset`（**不要**設 `include_preview=True`，除非研究者明確授權且資料已去識別化）、`get_data_dictionary`。
- CLI（由研究者執行或經同意後執行）：`aistat inspect --report quality_report.md`、`aistat dictionary set <變項> --level <nominal|ordinal|scale>`。

## 禁止事項

- 不修改、刪除或補值資料；只提出建議。
- 不把個別資料值貼到對話中。
- 不臆測變項意義；尺度有疑問時問研究者。

## 錯誤處理

- 「workspace 內還沒有資料集」→ 請研究者執行 `aistat import <檔案>`。
- 「找不到變項」→ 列出 `get_data_dictionary` 的變項名稱，請研究者確認拼字。

## 紀錄

尺度修正會寫入 `.aistat/audit.jsonl`（`variable_level_set`）。

## 測試案例

`tests/test_inspect.py`、`tests/test_mcp_server.py::test_inspect_does_not_send_rows_unless_asked`。
