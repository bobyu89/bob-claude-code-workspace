Status: done

# 06：成果包匯出與重新執行核對

**要做什麼（What to build）：** `aistat export RUN [--include-data]` 匯出 zip 成果包；`aistat rerun RUN` 重新執行並比對原始輸出。

**相依（Blocked by）：** 04、05。

- [x] 成果包含 run 資料夾全部檔案；預設不含資料，只含雜湊
- [x] `--include-data` 時才包含 canonical 資料
- [x] export 後狀態為 EXPORTED
- [x] rerun 結果一致時回報 match；資料被改動（雜湊不符）時拒絕 rerun
- [x] `aistat cancel RUN` 取消非終止狀態的 run
