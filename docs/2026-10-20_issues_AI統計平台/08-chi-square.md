Status: done

# 08：卡方獨立性檢定

**要做什麼（What to build）：** `--method chi-square --var row=A --var column=B` 完整走完計畫到報告。

**相依（Blocked by）：** 06。

- [x] Gate A：兩變項為類別尺度、各 ≥ 2 類、`independence` 需確認
- [x] 兩引擎輸出 Pearson χ²、df、p、Cramér's V、交叉表、期望次數 < 5 的格數比例，與手算例題一致
- [x] 期望次數 < 5 的格數 > 20% → Gate B `assumptions_met` 為 UNCERTAIN 並建議 Fisher's exact test
