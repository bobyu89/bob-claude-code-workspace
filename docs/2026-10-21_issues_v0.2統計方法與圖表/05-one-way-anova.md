Status: ready-for-agent

# 05：單因子 ANOVA

**要做什麼（What to build）：** `--method one-way-anova --var outcome=Y --var group=G` 完整走完計畫到報告。

**相依（Blocked by）：** 04。

- [ ] Gate A：3 組以上、每組至少 2 筆；兩組時判 NO 並建議 t 檢定
- [ ] Welch ANOVA + Games-Howell 為主，傳統 F + Tukey HSD 為對照，η² 與 ω²
- [ ] 各組 Shapiro-Wilk、Levene（informational）；常態不符時建議 Kruskal-Wallis
- [ ] 與 R `PlantGrowth` 一致；R 與 Python 互相一致
