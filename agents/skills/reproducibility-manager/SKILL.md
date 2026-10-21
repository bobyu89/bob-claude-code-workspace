---
name: reproducibility-manager
description: 管理 aistat 分析紀錄的重現與成果包：查詢 run 狀態歷程、重新執行核對輸出、匯出 zip 成果包（預設不含資料）。研究者要「交給指導教授」「確認可以重現」「整理分析紀錄」時使用。
---

# Reproducibility Manager

## 觸發條件

- 報告已產生，研究者要分享或歸檔。
- 研究者要確認分析可以重現。

## 工具

- `aistat runs`、`aistat status <RUN>`：狀態與歷程。
- `aistat rerun <RUN>`：以已保存的 `analysis.R` / `analysis.py` 與相同引擎重跑，逐項比對 `results.json`。
- `export_analysis_bundle(run_id, include_data=False)` 或 `aistat export <RUN> [--include-data]`。

## run 資料夾內容

`manifest.json`（資料與輸出雜湊、引擎版本、確認紀錄）、`analysis_plan.json`、`method_review.json`（Gate A）、
`analysis.R|py`、`raw_outputs/results.json`、`figures.py` 與 `figures/`、`result_review.json`（Gate B）、`statistical_report.md`、
`learning_notes.md`、`execution_log.json`、`data_dictionary.csv`、`quality_report.md`。

## 規則

- `include_data=True` 只在研究者明確確認「資料已去識別化且分享已獲授權」時使用。
- rerun 不一致時，列出差異與引擎版本變化，請研究者判斷；不要覆蓋原始輸出。
- 檔案雜湊不符時（匯出或 rerun 被拒），代表檔案被修改：停止並告知研究者。

## 測試案例

`tests/test_export_rerun.py`。
