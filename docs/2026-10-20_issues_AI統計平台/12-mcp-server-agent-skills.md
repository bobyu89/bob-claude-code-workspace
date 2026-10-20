Status: ready-for-agent

# 12：MCP Server 與 Agent Skills

**要做什麼（What to build）：** `aistat-mcp` 啟動 stdio MCP Server，提供需求書第 4 節 10 個工具；`agents/skills/` 提供 Agent 工作流程說明。

**相依（Blocked by）：** 07、08、09、10、11。

- [ ] 10 個工具皆呼叫 Workspace 門面，不另寫統計規則
- [ ] 沒有 approve 工具；執行未核准的 run 回傳明確錯誤，指示使用者執行 `aistat approve`
- [ ] Skills 說明觸發條件、輸入輸出、可用工具、禁止事項（不得自行產生統計數值、不得自行核准）、錯誤處理
- [ ] README 說明如何在 Claude Code 註冊 MCP Server
