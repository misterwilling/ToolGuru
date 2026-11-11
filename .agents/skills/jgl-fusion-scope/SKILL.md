---
name: jgl-fusion-scope
description: Runs a 15–20 minute guided interview for a new Fusion 360 add-in — what it does, which workspaces it touches, whether it reads or mutates the model, how it persists state, and the MCP dev loop — then writes docs/SCOPE.md, adds a Project context section to AGENTS.md, and hands the four scaffold inputs to /jgl-fusion-scaffold. Use when the user says "/jgl-fusion-scope", "help me get started", "scope this out", or "what am I building".
disable-model-invocation: true
---

# Fusion scope — the guided start

A scope document for a Fusion 360 add-in, built as a conversation instead of
a blank page. Interview the user, write it down, then hand off to the
scaffolder — so every future session starts oriented instead of guessing.

**This is the greenfield phase 0.** Run it *before* `/jgl-fusion-scaffold`.
Its answers (add-in name, company, target workspace, description) are exactly
the four inputs the scaffolder needs — you'll pass them straight over. On an
existing add-in it switches to update mode (see "Re-running").

## Ground rules

- **One question per message.** People answer the first question and hit
  enter; anything stacked after it gets lost, and each answer should shape the
  next question. If your tool has a structured question UI, use it, with
  options where the answers are predictable and free text for the open ones.
  The phases below are sequences to walk one turn at a time, skipping
  whatever is already answered.
- **Adapt.** Skip what earlier answers settled; go deeper where they're
  vague — vagueness in scoping is where projects die.
- **"I don't know" is a valid answer.** Park it in Open Questions with your
  recommended default in force, and move on.
- **Don't ask for secrets.** No keys, no tokens. If a real one gets pasted,
  stop and walk them through rotating it (SEC-3 in `AGENTS.md`).
- **Target 15–20 minutes.** In a hurry: phases 1, 3, and 5 only.
- **Show before you write.** Present the summary and the file list; write only
  after they confirm.

## The interview

### Phase 1 — the tool

What are you building, in one paragraph as you'd say it to a machinist
friend? What Fusion pain triggered it — the concrete moment you decided the
built-in behavior wasn't enough? Who's it for (just you, your shop, the
public)?

### Phase 2 — the Fusion shape

- **Add-in** (loaded, persistent UI) or a one-shot **script**? This kit is
  built for add-ins; if they describe a run-once script, say so and confirm
  they still want the add-in structure.
- **One focused tool, or a suite of commands?** A suite (several independent
  commands under one add-in — like a QoL bundle) needs an enable/disable
  settings system and per-user persistence from day one; a single tool
  doesn't. Decide now — it changes the scaffold.
- **UI: React palette or pure-Python CommandInputs dialogs?** This kit is
  scoped to **React-palette add-ins** (Python backend + HTML palette). If
  they want a pure-Python CommandInputs-only add-in, flag that it's outside
  this kit's templates — the principles still apply but the scaffolder and
  webapp guidance won't fit. Confirm before continuing.

### Phase 3 — workspaces & API surface (the core Fusion question)

- **Which Fusion workspace(s)?** Don't default this. Ask them to describe the
  workflow, then map it with the **same table `/jgl-fusion-scaffold` uses**
  (design / manufacturing / render / simulation / drawings). Many real
  add-ins are **multi-workspace** — e.g. a Design tool that also mirrors a
  result into a CAM setup, or a CAM tool whose palette is also surfaced in
  Design. If it's more than one, note it: `start()` registers the toolbar in
  each. See "Workspace IDs" in `ARCHITECTURE.md`.
- **Does it read the model, or mutate it?** This fork drives the whole
  architecture. A **read-only** tool (browse/tag/report, never writes Fusion's
  data — make that a stated invariant if so) is a different beast from one
  that **creates geometry/joints/occurrences or CAM setups**. Which is it,
  and if it mutates, what does it create?
- **Which API areas?** Joints/occurrences, BRep geometry, CAM tool libraries,
  CAM setups/operations, attributes, construction geometry. A rough list is
  enough — it points at which `ARCHITECTURE.md` gotchas will bite.

### Phase 4 — data & persistence

- **What state persists, and where?** The three real options: Fusion
  **attributes + entityTokens** stored on the document, an **external JSON**
  file in the user's home dir (never the add-in folder — it's gitignored
  territory), or a **cloud Data project** (`app.data.dataProjects`) the user
  maintains. Which fits?
- **Cloud / APS / Forge posture?** Does it depend on Autodesk Platform
  Services, a cloud data library, or any network call — or is it strictly
  **local, no cloud, ever**? If it touches cloud services, the secrets rules
  in `AGENTS.md` (SEC-1..5) apply to the tokens; note them in Open Questions.

### Phase 5 — the dev loop (MCP + testing)

- **Set up and validate the Fusion MCP server** by running
  **`/jgl-fusion-mcp`** now (or, if slash-skills don't fire in this
  environment, read its `SKILL.md` and run the preflight directly). Getting
  the live-Fusion loop working *at scoping time* means the first real feature
  can be tested headlessly instead of clicking through the GUI. Record the
  outcome in SCOPE.md (connected / deferred, and why).
- **Confirm the 3-layer testing model** is understood: Python unit (pytest,
  mock `adsk`), TypeScript unit (Vitest), and in-Fusion integration
  (unittest, hash-gated, runnable headlessly via MCP). See TEST-1..4 in
  `AGENTS.md`.

### Phase 6 — workflow

Solo or a team? (Solo greenfield → `main` is fine; shared/published → feature
branches + PRs, which `/jgl-fusion-push` warns about.) Where will it install
and run — just your machine, or distributed to others (cross-OS manifest)? A
one-line answer each is enough here.

## Outputs (after they confirm the summary)

1. **`docs/SCOPE.md`** (or `SCOPE.md` at root if no `docs/`):

   ```markdown
   # Scope — <add-in>
   _From the /jgl-fusion-scope interview, <date>. Update as decisions change._

   ## What this is          <the one-paragraph pitch, their words>
   ## Who it's for          <users + the Fusion pain it kills>
   ## Fusion shape          <add-in; single tool vs suite; React palette vs CommandInputs>
   ## Workspaces            <design/manufacturing/…, and multi-workspace notes>
   ## Reads vs mutates      <read-only invariant, or what it creates>
   ## API surface           <joints, CAM libraries, CAM setups, BRep, attributes…>
   ## Data & persistence    <attributes+tokens | external JSON | cloud Data project>
   ## Cloud posture         <local-only, or which APS/cloud services + their secrets>
   ## Dev loop              <MCP connected? + the 3-layer testing plan>
   ## First milestone       <thinnest end-to-end path that touches the pain + why>
   ## Workflow              <solo/main or team/PRs; where it installs>
   ## Open questions        <every "I don't know", default in force>
   ```

2. **`AGENTS.md` — add a Project context section, don't overwrite.**
   `AGENTS.md` holds the kit's guidelines (how to build); this section says
   *what* is being built. Append it at the end and keep it lean —
   `docs/SCOPE.md` holds the detail:

   ```markdown
   ## Project context
   _From /jgl-fusion-scope on <date>. Detail in docs/SCOPE.md._

   - **What this is:** <one line>
   - **Workspaces:** <design / manufacturing / …>
   - **Reads vs mutates:** <read-only, or what it creates>
   - **Persistence:** <attributes+tokens | external JSON | cloud Data project>
   - **First milestone:** <the thinnest end-to-end path>
   ```

   On a re-run, update the existing section in place rather than adding a
   second one.

## Then hand off to the scaffolder

You now have the four inputs `/jgl-fusion-scaffold` needs:

- **Add-in name** (PascalCase, identifier-safe)
- **Company name** (identifier-safe, for globally-unique UI IDs)
- **Target workspace** (from Phase 3)
- **One-line description** (from Phase 1)

Propose it: "Milestone one is X. Want me to scaffold the add-in now with
`/jgl-fusion-scaffold`?" — and pass these answers straight in so the user
isn't re-interviewed.

## Re-running

On a project that already has a `docs/SCOPE.md`, switch to update mode: read
it, ask only what changed, and revise rather than starting over. Suggest a re-run when the work has clearly drifted from the doc.
