Status: ready-for-agent

# 01：建立 workspace 並匯入 CSV / Excel

**要做什麼（What to build）：** 使用者可以 `aistat init` 建立 workspace，`aistat import` 匯入 CSV 或 Excel，`aistat datasets` 列出資料集。匯入後保存唯讀原始檔與 canonical CSV、SHA-256 雜湊與推論出的資料字典。

**相依（Blocked by）：** 無（可立即開始）。

- [ ] 可用 `pip install -e .` 安裝並執行 `aistat --help`
- [ ] `aistat init` 建立 `.aistat/workspace.json`、`data/`、`runs/`；重複 init 不覆蓋
- [ ] 匯入 CSV 與 .xlsx（可指定 `--sheet`），保存 `original.<ext>`、`data.csv` 皆為唯讀
- [ ] 同雜湊檔案重複匯入時回報既有資料集，不重建
- [ ] 不存在、不支援格式、空檔、重複欄名 → 清楚錯誤訊息與非零 exit code
- [ ] 資料字典含型態、測量尺度、尺度來源、缺失數、相異值數
- [ ] 寫入 workspace `audit.jsonl`
