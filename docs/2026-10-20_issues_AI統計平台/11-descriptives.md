Status: done

# 11：描述性統計

**要做什麼（What to build）：** `--method descriptives --var variables=A,B,C` 由引擎計算描述性統計並產出報告表格。

**相依（Blocked by）：** 06。

- [x] scale 變項：n、缺失、平均、標準差、中位數、Q1、Q3、最小、最大
- [x] 類別變項：各類次數與百分比
- [x] 兩引擎一致（四分位數使用 type 7）
