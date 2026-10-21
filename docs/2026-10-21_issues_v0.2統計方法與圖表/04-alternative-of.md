Status: done

# 04：`aistat plan --alternative-of RUN`

**要做什麼（What to build）：** 從假設不符的分析，一個指令建立替代方法的新計畫。

**相依（Blocked by）：** 01、02、03。

- [x] paired → Wilcoxon、independent → Mann-Whitney、chi-square 2 × 2 → Fisher、Pearson → Spearman
- [x] 新計畫沿用資料集、變項、alpha、conf_level，並記錄 `alternative_of`；原 run 不變
- [x] 沒有對應的替代方法時回報明確錯誤
- [x] Gate B 理由與報告假設檢查段落列出替代指令
- [x] CLI 與 MCP 都可使用
