Status: done

# 03：Fisher's exact test（2 × 2）

**要做什麼（What to build）：** `--method fisher-exact --var row=A --var column=B` 完整走完計畫到報告。

**相依（Blocked by）：** 01。

- [x] Gate A：兩變項皆恰好兩類，否則判 NO
- [x] 兩引擎輸出雙尾 p、條件 MLE 勝算比與 CI；CI 端點落在支撐邊界時正確輸出 0 / null
- [x] 與 lady tasting tea 一致；R 與 Python 互相一致（1e-6）
