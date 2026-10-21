Status: done

# 02：Mann-Whitney U test

**要做什麼（What to build）：** `--method mann-whitney-u --var outcome=Y --var group=G` 完整走完計畫到報告。

**相依（Blocked by）：** 01。

- [x] Gate A：結果變項為 scale / ordinal、分組恰好兩組、`independence` 需確認
- [x] 兩引擎輸出 U、p（exact 或常態近似）、Z、r、rank-biserial r、各組中位數與四分位數
- [x] 與 R 文件範例（exact）及 `sleep` 資料（近似）一致；R 與 Python 互相一致
