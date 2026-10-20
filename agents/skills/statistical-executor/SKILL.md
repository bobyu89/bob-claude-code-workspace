---
name: statistical-executor
description: 在研究者核准後，以 R 或 Python 統計引擎執行 aistat 分析計畫，並處理引擎不可用、逾時與執行錯誤。研究者已執行 aistat approve 之後使用。
---

# Statistical Executor

## 觸發條件

run 狀態為 `USER_APPROVAL`（或修正環境後重試的 `FAILED`）。

## 輸入

`{run_id, engine: "auto" | "r" | "python", timeout: 120}`。`auto` 優先 R，找不到時用 Python。

## 輸出

`{run_id, status: "EXECUTED", engine: {name, version}, summary}`；完整數值用 `retrieve_analysis_results` 取得。
run 資料夾會保存 `analysis.R` 或 `analysis.py` 與 `raw_outputs/results.json`。

## 錯誤處理

| 訊息 | 意義 | 處理 |
|---|---|---|
| `無法執行分析（需要 USER_APPROVAL ...）` | 尚未核准 | 請研究者執行 `aistat approve` |
| `找不到 r 引擎` | 沒有安裝 R | 改用 `engine="python"`，或請研究者安裝 R |
| `引擎執行逾時` | 超過 timeout | 狀態為 `FAILED`；確認資料大小後以較長 timeout 重試 |
| `預測變項完全共線` | 迴歸無法估計 | 向研究者說明，建立新計畫 |
| `資料雜湊與分析計畫不符` | 資料被改動 | 停止，告知研究者；不要嘗試修復 |

## 禁止事項

- 不要在引擎失敗時自行估計結果或「先給個大概」。
- 不要直接修改 run 資料夾內的檔案。

## 測試案例

`tests/test_engines.py`、`tests/test_paired_flow.py::test_engine_timeout_marks_run_failed_and_can_be_retried`。
