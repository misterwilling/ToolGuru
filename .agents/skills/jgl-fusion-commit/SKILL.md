---
name: jgl-fusion-commit
description: Stages a Fusion add-in's relevant changes and makes a local commit with a specific message and no AI attribution, checking that integration results travel with the source they were generated against; never pushes. On a long session it also refreshes docs/PROGRESS.md. Use when the user says "commit", "/jgl-fusion-commit", "save my work", or "checkpoint".
disable-model-invocation: true
---

# Commit (Fusion add-in)

Make one local commit of the work in progress. This skill never pushes —
pushing runs CI and can update an add-in other people install, so it's a
separate, deliberate step (`/jgl-fusion-push`, GIT-2). If the user said
"commit and push", commit, then tell them pushing is `/jgl-fusion-push` and
do it only if they confirm.

## Stage

Look at `git status` and `git diff` first. If nothing changed, say so and
stop — no empty commits. Stage specific paths, not `git add -A`.

- **Belongs in a commit when modified:** `code/<prefix>_*/`, `webapp/src/`
  and the webapp's package, lock, Vite and TS config files,
  `<AddInName>.py`, `<AddInName>.manifest`, `config.json`,
  `requirements*.txt`, `.github/workflows/`.
- **Leave out:** `code/lib/coverage_pkg/` (developer-local),
  `webapp/dist/` when the build is reproducible, `__pycache__/`,
  `.pytest_cache/`, `.coverage`, `htmlcov/`.
- **Secret-shaped files** (`.env*`, `credentials*.json`, `*.key`, `*.pem`)
  stay out even if the user said "commit everything"; tell them which you
  skipped (SEC-1).
- **`code/<prefix>_tests/fusion_test_results.json`** belongs with the source
  it was generated against. If source under `code/` changed since the last
  integration run, the hash is stale and CI will reject the push — say so
  before committing, and suggest re-running the integration tests
  (`/jgl-fusion-mcp` or the "Run Tests" button) (TEST-4).

## Write the message

A subject under ~72 characters saying what changed — "fix joint-origin
pairing when the assembly has no proxies", not "update files". Add a short
body only when the subject can't carry something the reader needs.

No AI attribution (GIT-1): no `Co-Authored-By` naming an AI tool or model, no
"Generated with" line, no 🤖. Your tool may add one by default; leave it off.
The scaffolded `commit-msg` hook rejects them anyway.

```bash
git commit -m "$(cat <<'EOF'
<subject>

<optional body>
EOF
)"
```

If a hook rejects the commit, fix what it found and commit again rather than
using `--no-verify`.

## Hand off on a long session (GIT-5)

Before committing, measure what's been generated since the last commit:
files changed plus untracked files, and added lines from
`git diff --numstat HEAD` plus the line counts of untracked text files. Past
roughly 10 files or 400 lines, update `docs/PROGRESS.md` (create it if
needed, under ~30 lines) and include it in the commit:

```markdown
# Progress
_Updated <date>._

## Done
## In flight
## Next step
## Open questions
```

Rewrite the sections rather than appending, so it stays a snapshot. Then
suggest continuing in a fresh session that starts from `docs/PROGRESS.md` and
`git log`.

## Report

```
Committed locally: "fix joint-origin pairing when the assembly has no proxies"
2 files changed. Integration results: current.

Push when you're ready: /jgl-fusion-push
```
