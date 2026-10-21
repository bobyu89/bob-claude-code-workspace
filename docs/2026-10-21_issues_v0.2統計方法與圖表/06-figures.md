Status: done

# 06：統計圖表

**要做什麼（What to build）：** 每次分析產生 APA 7 版面的 PNG + SVG 圖，嵌入報告，`figures.py` 可重跑。

**相依（Blocked by）：** 05。

- [x] 每個方法都有對應的圖（線圖、箱形圖、散布圖、殘差圖、堆疊長條圖、直方圖 / 長條圖）
- [x] 報告有 Figure N 段落與相對路徑嵌入
- [x] 中文欄名使用 CJK 字型；找不到字型時報告註記
- [x] 畫圖失敗不影響分析狀態，報告照樣產生
- [x] figures.py 與圖檔雜湊寫入 manifest，匯出時核對
