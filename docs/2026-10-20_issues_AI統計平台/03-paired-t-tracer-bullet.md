Status: ready-for-agent

# 03：配對 t 檢定 tracer bullet（plan → Gate A → approve → analyze，Python 引擎）

**要做什麼（What to build）：** 使用者可以為配對 t 檢定建立分析計畫、看到 Gate A 結果、確認 UNCERTAIN 並核准、以 Python 引擎執行，得到 run 資料夾內的 `analysis_plan.json`、`method_review.json`、`analysis.py`、`raw_outputs/results.json`、`manifest.json`、`execution_log.json`。

**相依（Blocked by）：** 02。

- [ ] `aistat plan --method paired-t-test --var before=X --var after=Y` 建立 `runs/RUN_YYYYMMDD_NNN/`
- [ ] Gate A 檢查 `variables_exist`、`measurement_level`、`pairing_structure`、`missing_data`、`sample_size`、`assumptions_planned`
- [ ] 有 NO 時 run 進 BLOCKED，無法 approve
- [ ] UNCERTAIN 需 `aistat approve RUN --confirm CHECK_ID` 才能核准；確認紀錄寫入 log
- [ ] 未核准的 run 無法 analyze
- [ ] Python 引擎輸出平均差、95% CI、t、df、p、d_z、差值 Shapiro-Wilk，與 R `sleep` 範例的已知值一致
- [ ] 引擎錯誤或逾時 → FAILED 並保存錯誤
- [ ] `aistat runs`、`aistat status RUN` 顯示狀態與歷程
