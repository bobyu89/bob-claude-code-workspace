# aistat：AI Statistical Platform

[![tests](https://github.com/bobyu89/bob-claude-code-workspace/actions/workflows/tests.yml/badge.svg)](https://github.com/bobyu89/bob-claude-code-workspace/actions/workflows/tests.yml)

開源、AI 原生的統計分析平台，給研究生、護理與醫療研究者、統計初學者使用。

**Statistical Analysis Should Be Explainable, Reproducible, and Accessible.**

- 所有統計數值由實際統計引擎（R 或 Python：SciPy / statsmodels）計算，LLM 不產生數字。
- 每次分析都經過 **JEV** 兩道結構化審查（YES / NO / UNCERTAIN）：Gate A 在執行前檢查方法是否適用，Gate B 在報告前檢查每個數字是否能追溯到原始輸出。
- 分析計畫一定要由研究者本人核准後才能執行。
- 每次分析保存程式碼、原始輸出、審查紀錄與雜湊，可重新執行核對。
- 產出 APA 7 結果草稿（繁體中文 / 英文），Learning Mode 以你自己的資料講解方法。
- CLI 不連 LLM 也能完整使用；AI Agent（Claude Code 等）透過 MCP Server 操作同一個核心服務。

> 狀態：第一階段 MVP（v0.1）。規格見 [`docs/2026-10-20_PRD_AI統計平台.md`](docs/2026-10-20_PRD_AI統計平台.md)，原始需求書見 [`docs/2026-10-20_產品與工程設計需求書_v1.md`](docs/2026-10-20_產品與工程設計需求書_v1.md)。

## 安裝

需要 Python 3.10 以上。R 為選配（只需 base R，不需額外套件）；沒有 R 時自動使用 Python 引擎。

```bash
pip install -e ".[mcp]"      # 開發中：在 repo 根目錄安裝
aistat --help
```

## 快速開始：配對樣本 t 檢定

```bash
mkdir my-study && cd my-study
aistat init
aistat import pretest_posttest.xlsx          # 也支援 CSV（UTF-8 / Big5）；--sheet 指定工作表
aistat inspect --report quality_report.md    # 預覽、資料字典、品質問題
aistat dictionary set likert_total --level scale   # 修正系統推論的測量尺度

aistat plan --method paired-t-test --var before=pre --var after=post
#   JEV Gate A：[UNCERTAIN] pairing_structure：尚未確認 pre 與 post 是否來自相同受試者…
aistat approve RUN_20261020_001 --confirm pairing_structure   # 研究者本人核准

aistat analyze RUN_20261020_001              # --engine auto | r | python
aistat review RUN_20261020_001               # JEV Gate B
aistat report RUN_20261020_001 --mode learning   # --lang en 產生英文草稿
aistat rerun RUN_20261020_001                # 重新執行並核對輸出
aistat export RUN_20261020_001               # zip 成果包，預設不含資料（--include-data）
```

統計假設不符時，`aistat plan --alternative-of <RUN>` 會沿用同一組變項建立替代方法的新計畫（例如配對 t → Wilcoxon、獨立 t → Mann-Whitney、2 × 2 卡方 → Fisher、Pearson → Spearman），新計畫一樣要通過 Gate A 並經研究者核准。

其他指令：`aistat datasets`、`aistat runs`、`aistat status <RUN>`、`aistat validate <RUN>`、`aistat cancel <RUN>`、`aistat dictionary export`。

## 支援的方法

| `--method` | 變項角色（`--var role=欄位`） | 主要輸出 |
|---|---|---|
| `descriptives` | `variables=a,b,c` | n、缺失、M、SD、Mdn、Q1–Q3、範圍；類別次數與百分比 |
| `paired-t-test` | `before`、`after` | 平均差、CI、t、df、p、Cohen's d_z；差值 Shapiro-Wilk |
| `independent-t-test` | `outcome`、`group` | Welch 與 Student t、CI、Cohen's d；各組常態性、Brown-Forsythe Levene |
| `one-way-anova` | `outcome`、`group`（3 組以上） | Welch ANOVA + Games-Howell；傳統 F + Tukey HSD 對照；η²、ω²；各組常態性、Levene |
| `chi-square` | `row`、`column` | Pearson χ²、Cramér's V、交叉表；期望次數檢查 |
| `correlation` | `x`、`y`（`--option method=spearman`） | r / r_s、t、p、Fisher z CI；常態性 |
| `linear-regression` | `outcome`、`predictors=a,b` | B、SE、β、t、p、CI；R²、F；殘差常態、Breusch-Pagan、VIF |
| `wilcoxon-signed-rank` | `before`、`after`（scale 或 ordinal） | W+、z、p（exact 或常態近似）、r、rank-biserial r；中位數與四分位數 |
| `mann-whitney-u` | `outcome`（scale 或 ordinal）、`group` | U、z、p（exact 或常態近似）、r、rank-biserial r；各組中位數 |
| `fisher-exact` | `row`、`column`（皆二元） | 雙尾 p、條件最大概似勝算比與 CI、交叉表 |

選項：`--option alpha=0.05`、`--option conf_level=0.95`。

## 統計圖表

每次分析完成後自動以 matplotlib 畫 1–2 張 APA 7 版面的圖（PNG 300 dpi + SVG），嵌入報告的「圖表（Figures）」段落：

| 方法 | 圖 |
|---|---|
| 配對 t、Wilcoxon | 每位受試者前後測線圖，加上平均數或中位數 |
| 獨立 t、Mann-Whitney、ANOVA | 各組箱形圖加個別觀察值 |
| 卡方、Fisher | 各列類別內的比例堆疊長條圖 |
| 相關 | 散布圖 |
| 線性迴歸 | 單一預測變項時散布圖加迴歸線；殘差對配適值圖與殘差常態 Q-Q 圖 |
| 描述統計 | 數值變項直方圖、類別變項長條圖 |

- 圖上不寫 p 值或檢定統計量，只畫資料與引擎已輸出的數值（例如迴歸殘差）。
- 中文欄位名稱需要 CJK 字型（例如 Noto Sans CJK、Microsoft JhengHei、PingFang）；找不到時圖照樣產生，報告會註記。
- 畫圖失敗不影響分析狀態，報告照樣產生並寫明原因。
- `aistat analyze <RUN> --no-figures` 或環境變數 `AISTAT_FIGURES=0` 可關閉圖表。

## 分析狀態機與 JEV

```text
PLAN_DRAFTED → JEV_GATE_A → USER_APPROVAL → EXECUTING → EXECUTED → JEV_GATE_B → REPORT_GENERATED → EXPORTED
              ↘ BLOCKED（Gate A 有 NO）              ↘ FAILED（引擎錯誤，可重試）        任何階段 → CANCELLED
```

- **Gate A**：`variables_exist`、`measurement_level`、`group_structure`、`pairing_structure` / `independence`、`correlation_type`、`predictor_coding`、`missing_data`、`sample_size`、`assumptions_planned`。
- **Gate B**：`engine_provenance`、`values_traceable`、`p_value_format`、`effect_size_ci`、`causal_language`、`significance_consistency`、`assumptions_met`。

JEV 屬於流程審查機制，並非統計正確性的絕對保證。

## 分析紀錄

```text
runs/RUN_20261020_001/
├── manifest.json          # 資料與輸出雜湊、引擎版本、狀態歷程、使用者確認紀錄
├── analysis_plan.json     # 方法、變項、選項（schemas/analysis_plan.schema.json）
├── method_review.json     # JEV Gate A
├── data_dictionary.csv / quality_report.md
├── analysis.R 或 analysis.py   # 可獨立重跑的分析程式碼
├── raw_outputs/results.json    # 引擎原始輸出：報告數字的唯一來源
├── figures.py             # 可獨立重跑的畫圖程式碼（python figures.py）
├── figures/figure_N.png / .svg / figures.json
├── result_review.json     # JEV Gate B
├── statistical_report.md / learning_notes.md
└── execution_log.json     # 只記錄中繼資料，不記錄資料值
```

## AI Agent 與 MCP

在研究專案資料夾（已 `aistat init`）向 Claude Code 註冊 MCP Server：

```bash
claude mcp add --scope project aistat -- aistat-mcp --workspace .
```

這會在專案根目錄寫入 `.mcp.json`；也可以手動建立同內容的檔案：

```json
{ "mcpServers": { "aistat": { "command": "aistat-mcp", "args": ["--workspace", "."] } } }
```

MCP 工具：`list_methods`、`list_datasets`、`inspect_dataset`、`get_data_dictionary`、`create_analysis_plan`、`validate_analysis_plan`、`execute_statistical_analysis`、`retrieve_analysis_results`、`review_statistical_results`、`generate_statistical_report`、`export_analysis_bundle`。刻意不提供核准工具。Agent 工作流程見 [`agents/README.md`](agents/README.md)。

## 資料治理

- 匯入的原始檔與 canonical CSV 設為唯讀，並記錄 SHA-256；資料被改動時拒絕執行、重跑與匯出。
- 統計引擎只以白名單指令（`Rscript`、目前的 Python 直譯器）在子行程執行，不經 shell，並有逾時限制。
- `inspect_dataset` 預設不把資料列傳給 Agent；成果包預設不含資料。
- 平台本身不呼叫任何 LLM，也不把資料傳到外部。

## 開發

```bash
pip install -e ".[dev,mcp]"
pytest                      # 沒有 R 時，R 相關測試自動略過
```

GitHub Actions（`.github/workflows/tests.yml`）在每次 push 到 `main` 與每個 PR 時，以 Python 3.10 與 3.13 加上 R 執行全部測試；CI 設定 `AISTAT_REQUIRE_R=1`，缺少 R 時直接失敗，不會默默略過 R 與 Python 的交叉比對。

測試以已知文獻值為 golden case（例如 R 官方 `sleep` 範例：t = 4.0621, df = 9, p = 0.002833），並交叉比對 R 與 Python 引擎（容許誤差 1e-6）。

本 repo 的開發流程（PRD → tickets → TDD → code review）使用 `.claude/skills/`，來自 [mattpocock/skills](https://github.com/mattpocock/skills)（MIT，見 `.claude/skills/LICENSE-mattpocock`）；流程說明見 `CLAUDE.md`。

## 授權

Apache License 2.0（見 `LICENSE`）。R 以獨立行程呼叫，本專案不散布 R 或其套件。
