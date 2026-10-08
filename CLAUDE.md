# 專案規範

## 溝通

- 一律使用繁體中文；醫學術語保留英文（例：Sepsis、Delirium、qSOFA）。
- 程式碼、指令、檔案路徑維持原文。

## 檔名格式

- 文件與產出檔一律 `YYYY-MM-DD_主題_版本`，例：`2026-10-08_問卷分析_v1.docx`。版本從 `v1` 起，改版遞增。
- PRD 固定存為 `docs/YYYY-MM-DD_PRD_主題.md`；改版時尾端加 `_v2`、`_v3`。
- 例外：程式碼與設定檔（`src/`、`tests/`、`package.json`、`CLAUDE.md` 等）依語言與工具慣例命名。

## 程式開發流程

以下流程直接依序執行，不用每步問我。

1. **需求不清** → `grill-me` 釐清需求。這步本身是訪談，要等我回答。
2. **需求明確** → `to-spec`（上游原名 `to-prd`）寫成 PRD，存到 `docs/YYYY-MM-DD_PRD_主題.md`。
3. **功能多**（超過一個 vertical slice）→ `to-tickets`（上游原名 `to-issues`）拆成 tickets。
4. **實作** → `tdd`：red → green，一次一個 slice。
5. **遇到 bug** → `diagnosing-bugs`（上游原名 `diagnose`）。
6. **測試全數通過** → `code-review`。依 review 結果修正後重跑測試。
7. **commit**（Conventional Commits）→ **push**。

### 執行方式

- 流程中的 skill 一律讀取 `.claude/skills/<name>/SKILL.md` 並照做，不經 Skill tool：`grill-me`、`to-spec`、`to-tickets` 在上游設為僅限手動呼叫，`code-review` 則與 Claude Code 內建的 `/code-review` 撞名。`grill-me` 的內容就是執行 `grilling`。
- skill 內要求向我確認的步驟（`to-spec` 與 `tdd` 的 seams、`to-tickets` 的拆分、`code-review` 的基準點），直接採用你的推薦答案並在輸出中註明，不停下等待。
- 仍要先問我：刪除檔案或分支、`git push --force`、改寫已 push 的歷史。

### Issue tracker

使用本機 Markdown，不需執行 `/setup-matt-pocock-skills`。

- Spec（PRD）：`docs/YYYY-MM-DD_PRD_主題.md`
- Tickets：`docs/YYYY-MM-DD_issues_主題/NN-<slug>.md`，從 `01` 依相依順序編號，一個 ticket 一個檔案。
- Triage label：在檔案頂端以 `Status: ready-for-agent` 這類 `Status:` 行記錄。
- Domain docs：若有 `GLOSSARY.md` 或 `docs/adr/` 就先讀；沒有就略過，不主動建立。

### code-review

- 基準點預設為與 `origin/main`（或 repo 預設分支）的 merge-base；尚未 commit 的變更與新檔案一併納入審查。
- Spec 軸對照 `docs/` 內對應的 PRD。

### Commit 與 push

- 格式：`<type>(<scope>): <描述>`，type 用 `feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`；描述用繁體中文。
- push 到目前所在分支。
- 這個 repo 已在 GitHub 上：不要 `gh repo create`、不要 `git init`、不要更改 `git remote`。
