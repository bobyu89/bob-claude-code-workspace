Status: done

# 04：R 引擎 adapter 與跨引擎 golden case

**要做什麼（What to build）：** `aistat analyze RUN --engine r` 產生 `analysis.R` 並以 `Rscript` 執行，輸出與 Python 引擎相同結構的 `results.json`。`--engine auto` 時 R 優先。

**相依（Blocked by）：** 03。

- [x] 只需 base R，不需安裝額外 R 套件
- [x] 配對 t 的 R 結果與已知值、Python 結果一致（容許誤差 1e-6）
- [x] 找不到 `Rscript` → 清楚錯誤，run 維持 USER_APPROVAL（不進 FAILED 也不假裝執行）
- [x] manifest 記錄引擎名稱與版本
- [x] 指令白名單與逾時
