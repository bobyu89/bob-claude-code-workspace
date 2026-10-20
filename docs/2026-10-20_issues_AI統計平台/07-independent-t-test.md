Status: done

# 07：獨立樣本 t 檢定

**要做什麼（What to build）：** 使用者可以用 `--method independent-t-test --var outcome=Y --var group=G` 完整走完計畫到報告。

**相依（Blocked by）：** 06。

- [x] Gate A：分組恰兩組（否則 NO）、`independence` 需確認
- [x] 兩引擎輸出 Welch 與 Student 結果、Brown-Forsythe Levene、各組描述統計、Cohen's d，與 R `sleep` Welch 範例已知值一致
- [x] 報告以 Welch 為主，Levene 結果寫入假設檢查
