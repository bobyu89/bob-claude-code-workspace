<!-- template-readme -->
# bob-claude-code-workspace

BOB 的 Claude Code 專案範本。在 GitHub 上按 **Use this template** 建立新專案。

## 內容

- `CLAUDE.md`：溝通、檔名格式、開發流程
- `.claude/skills/`：開發流程用的 skills，來自 [mattpocock/skills](https://github.com/mattpocock/skills)（MIT，見 `LICENSE-mattpocock`）
- `.claude/settings.json`：允許 `git add`、`git commit`、`git push`、`npm test`
- `docs/`：PRD 與 tickets

## 新專案第一次開工

- 在本機第一次開 Claude Code 時，接受 trust dialog，`settings.json` 的權限才會生效。
- Claude 會依 `CLAUDE.md` 把這份 README 改寫成新專案的內容。
