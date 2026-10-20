Status: ready-for-agent

# 05：Gate B 與 APA 7 報告、Learning notes（配對 t）

**要做什麼（What to build）：** `aistat review RUN [--draft FILE]` 執行 Gate B；`aistat report RUN [--lang zh|en] [--mode research|learning]` 通過 Gate B 後產出 `statistical_report.md`（與 learning 模式的 `learning_notes.md`）。

**相依（Blocked by）：** 03。

- [ ] Gate B 檢查 `engine_provenance`、`values_traceable`、`p_value_format`、`effect_size_ci`、`causal_language`、`significance_consistency`、`assumptions_met`，寫入 `result_review.json`
- [ ] 竄改過的數字、`p = .000`、因果用語的草稿被判 NO
- [ ] Gate B 有 NO 時拒絕輸出報告
- [ ] 報告數字符合 APA 7 格式（p 無前導零、p < .001）
- [ ] Learning notes 回答需求書第 6 節六個問題，使用使用者的變項名稱
