---
name: jgl-fusion-push
description: Pushes a Fusion add-in's committed work to the remote after checking for a stale integration-test hash and an out-of-date webapp build, asking first before any push to main or master, and never forcing or skipping hooks. Use when the user says "push", "/jgl-fusion-push", or "send it up".
disable-model-invocation: true
---

# Push (Fusion add-in)

Push committed work to the remote. Pushing runs CI (unit tests plus the
integration hash gate) and can update an add-in other people install, which
is why it's a separate step from `/jgl-fusion-commit` (GIT-2).

## Before pushing

Show what's going out: the branch and the commits ahead of the remote
(`git log @{u}..HEAD --oneline`). If nothing is ahead, say so and stop.

Then check the two Fusion-specific ways a push fails in CI:

1. **Stale integration hash (TEST-4).** If commits going up changed files
   under `code/` but `code/<prefix>_tests/fusion_test_results.json` wasn't
   updated with them, CI will reject the push. Tell the user to re-run the
   integration tests first (`/jgl-fusion-mcp` headlessly, or the "Run Tests"
   button) and commit the new results.
2. **Webapp build out of date (BUILD-1).** Only matters when `webapp/dist/`
   is committed: if `webapp/src/` changed without a rebuild, flag it.

## Branch rules

- **Feature branch:** push. `git push -u origin <branch>` the first time.
- **`main`, `master`, or a production branch:** ask first and wait for a
  clear yes, even if the user already asked you to push. Offer the safer path
  in the same message:

  ```
  You're about to push 2 commits to origin/main.
  Add-ins other people install benefit from PR review:
      git checkout -b <feature-branch> && git push -u origin <feature-branch>
  Push directly to main? (yes/no)
  ```

  A yes covers the rest of this session only.

## Pushing

Let the pre-push hook run — it re-runs the Python and webapp unit suites and
stops a red push. Don't use `--no-verify` to get past it.

If the push is rejected as non-fast-forward, don't force it: tell the user the
remote has commits they don't have, suggest `git pull --rebase`, and let them
decide. Use `--force` / `--force-with-lease` only when the user explicitly
asks and has confirmed what it overwrites. Push only the checked-out branch or
the one the user named.

## Report

```
Pushed 2 commits to origin/feature/joint-pairs-fix.
https://github.com/<owner>/<repo>/tree/feature/joint-pairs-fix
```
