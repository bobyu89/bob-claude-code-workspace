# aistat Agent Skills

給 Claude Code（或其他支援 Skills / MCP 的 AI Coding Agent）使用的工作流程說明。
Agent 透過 aistat MCP Server 操作同一個 Core 服務；所有統計數值都由統計引擎計算。

## 安裝

1. 安裝 aistat 與 MCP 支援：`pip install "aistat[mcp]"`（開發中請在 repo 根目錄 `pip install -e ".[mcp]"`）。
2. 在研究專案資料夾執行 `aistat init`、`aistat import <資料檔>`。
3. 在同一個資料夾建立 `.mcp.json`：

   ```json
   {
     "mcpServers": {
       "aistat": {"command": "aistat-mcp", "args": ["--workspace", "."]}
     }
   }
   ```

4. 把 `agents/skills/` 下的資料夾複製到研究專案的 `.claude/skills/`。

## Skills

| Skill | 職責 |
|---|---|
| `aistat-workflow` | 流程協調（入口） |
| `data-inspector` | 資料結構與品質檢查 |
| `research-designer` | 研究設計辨識 |
| `statistical-planner` | 統計方法規劃與 Gate A 解讀 |
| `assumption-checker` | 統計假設檢查解讀 |
| `statistical-executor` | 呼叫分析引擎 |
| `result-reviewer` | JEV Gate B 結果審查 |
| `report-generator` | APA 7 報告 |
| `statistical-tutor` | Learning Mode 教學 |
| `reproducibility-manager` | 分析紀錄、重現與匯出 |

Visualization（統計圖表）尚未實作，列於後續版本。

## 設計原則

- MCP 沒有核准工具：分析計畫一律由研究者本人以 `aistat approve` 核准。
- `inspect_dataset` 預設不回傳資料列；成果包預設不含資料。
- Agent 改寫的結果文字必須再通過 JEV Gate B。
