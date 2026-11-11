---
name: jgl-fusion-status
description: Gives a read-only session checkpoint for a Fusion add-in — what's committed, staged and in progress, integration-test hash freshness, webapp build freshness, anything risky left uncommitted, and whether enough has been generated since the last commit to checkpoint. Use when the user says "status", "/jgl-fusion-status", "where are we", or before committing on a long session.
---

# Status (Fusion add-in)

A checkpoint the user can read in under a minute: what's done, what's left,
what's at risk. This skill only reads — report anything that needs fixing as
a finding and leave the files alone.

## What changed

From `git status`, `git diff --stat`, and `git log @{u}..HEAD --oneline`,
count three buckets: committed but not pushed, staged, and unstaged or
untracked. When many files are touched, group them by area: Python
production (`code/<prefix>_lib/`, `code/<prefix>_commands/`), Python tests,
`webapp/src/`, and `webapp/dist/` (usually shouldn't be committed).

## Session volume (GIT-5)

Count what's been generated since the last commit: files changed (tracked
diff against `HEAD` plus untracked files from
`git ls-files --others --exclude-standard`) and added lines
(`git diff --numstat HEAD` plus the line counts of untracked text files).
Past roughly 10 files or 400 lines, recommend `/jgl-fusion-commit` in one
line — it also refreshes `docs/PROGRESS.md` for the next session. Volume, not
time, is what drives drift; uncommitted work older than about two hours is a
weaker hint worth one line.

## What's still open

- **Integration hash (TEST-4)** — compare the current codebase hash with
  `code/<prefix>_tests/fusion_test_results.json`. If source changed since the
  last integration run, the results are stale and CI will reject the push.
  This is the Fusion-specific finding to put first.
- **Webapp build (BUILD-1)** — `webapp/src/` modified after
  `webapp/dist/index.html`: the palette will show stale UI until
  `cd webapp && npm run build`.
- Failing tests, if results from a recent run are available (re-run only on
  request).
- New `TODO` / `FIXME` / `XXX` markers and new `.skip` / `xit` /
  `@pytest.mark.skip` in this session's diff.

If nothing turns up, say "Nothing flagged."

## Anything risky uncommitted

- Secret-shaped files modified or untracked (`.env*`, `*.key`,
  `credentials*`).
- `webapp/package.json` or lockfile changes — rebuild and re-run the tests.
- A modified `<AddInName>.manifest` — check the `id` UUID wasn't regenerated;
  changing it confuses Fusion's add-in registry.

## Report

```
Status — feature/joint-pairs-fix (no PR yet)

Committed, not pushed:  2 commits
Staged:                 0 files
Unstaged:               code/mt_lib/joint_utils.py, code/mt_tests/test_joint_utils.py

Session:  ! 12 files / ~430 added lines since the last commit — checkpoint
            with /jgl-fusion-commit

Open:
  • Integration tests STALE — source changed since the last run; re-run
    before pushing or CI rejects it (/jgl-fusion-mcp or "Run Tests")
  • webapp/dist out of date — run `cd webapp && npm run build`

Next steps you might consider:
  • Re-run the integration tests
  • Build the webapp
  • /jgl-fusion-commit
```

End with two or three suggested next steps — suggestions; the user picks.
