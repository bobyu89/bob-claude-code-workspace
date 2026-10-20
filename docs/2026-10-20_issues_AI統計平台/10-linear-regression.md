Status: ready-for-agent

# 10：基本線性迴歸

**要做什麼（What to build）：** `--method linear-regression --var outcome=Y --var predictors=X1,X2` 完整走完計畫到報告。

**相依（Blocked by）：** 06。

- [ ] 每個係數 B、SE、t、p、95% CI、標準化 β；模型 R²、調整後 R²、F、df1、df2、p
- [ ] 殘差 Shapiro-Wilk；兩個以上預測變項時輸出 VIF
- [ ] 多類別 nominal 預測變項 → Gate A NO
- [ ] 兩引擎一致，並與教科書手算例題一致
