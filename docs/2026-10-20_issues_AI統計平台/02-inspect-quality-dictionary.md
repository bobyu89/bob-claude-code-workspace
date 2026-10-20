Status: ready-for-agent

# 02：資料檢查、品質報告與資料字典

**要做什麼（What to build）：** `aistat inspect [DATASET]` 顯示資料預覽、資料字典與品質問題；`aistat dictionary set VAR --level LEVEL` 修正測量尺度；`aistat dictionary export` 輸出 `data_dictionary.csv`。

**相依（Blocked by）：** 01。

- [ ] 預覽前 N 列
- [ ] 品質問題：高缺失比例、常數欄、重複列、疑似 ID 欄、少數值數值欄（尺度可疑）
- [ ] 品質報告可寫成 `quality_report.md`
- [ ] 修正尺度後尺度來源變為 `user`，並寫入 audit log
- [ ] 不存在的變項或不合法尺度 → 清楚錯誤
