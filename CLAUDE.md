@AGENTS.md

## Claude Code notes

- Register the Fusion MCP server once:
  `claude mcp add --transport http fusion http://127.0.0.1:27182/mcp`
  (MCP-1). Its tools appear as `fusion_mcp_*`.
- Skills live in `.claude/skills/`. `/jgl-fusion-check`,
  `/jgl-fusion-review-code` and `/jgl-fusion-review-testing` run in a forked
  context and hand back a report.
- `/jgl-fusion-scope`, `/jgl-fusion-scaffold`, `/jgl-fusion-setup-testing`,
  `/jgl-fusion-commit` and `/jgl-fusion-push` run only when the user types them.
