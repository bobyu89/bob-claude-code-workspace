Status: done

# 01：Wilcoxon signed-rank test

**要做什麼（What to build）：** `--method wilcoxon-signed-rank --var before=X --var after=Y` 完整走完計畫到報告與 Learning notes。

**相依（Blocked by）：** 無（可立即開始）。

- [x] Gate A：接受 scale / ordinal 數值變項、`pairing_structure` 需確認
- [x] 兩引擎輸出 W+、p（exact 或常態近似，並標示是哪一種）、Z、r、rank-biserial r、差值與前後測的中位數與四分位數
- [x] 與 R 文件的 Hollander & Wolfe 範例（exact）及 `sleep` 資料（近似）一致；R 與 Python 互相一致
- [x] 報告通過自身的 Gate B
