# weekly-brain-sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One explicit command that runs the full vault maintenance pipeline
end to end: trim LLM chat tails, reindex `raw/`, update `wiki/`, then
reindex + restart the obsidian-navigator server.

**Architecture:** A single new skill file, `weekly-brain-sync/SKILL.md`,
placed alongside its three siblings in the vault's `.claude/skills/`
directory. It contains a numbered sequence of steps that invoke the three
existing skills by name (via the Skill tool) and then shell out to
`refresh.sh`. No code, no tests in the pytest sense — this is a
process-documentation deliverable, so "testing" means actually running the
sequence once and confirming each step behaves as documented.

**Tech Stack:** Markdown + YAML frontmatter (skill format), bash (for the
`cd`/`refresh.sh` step).

## Global Constraints

- Skill frontmatter: `disable-model-invocation: true` (explicit-invocation
  only, matching `trim-llm`, `reindex`, `wiki-update`).
- Vault path must be quoted in every shell reference:
  `"$HOME/Documents/Kevin Notes"` (path contains a space).
- Stop at the first step that fails; do not proceed to later steps.
- Invoke the three existing skills by name rather than inlining their
  instructions (single source of truth).

---

### Task 1: Write the `weekly-brain-sync` skill file

**Files:**
- Create: `/Users/kevinng/Documents/Kevin Notes/.claude/skills/weekly-brain-sync/SKILL.md`

**Interfaces:**
- Consumes: existing skills `trim-llm`, `reindex`, `wiki-update` (invoked by
  name via the Skill tool — no code interface, just the skill names as
  documented in their own SKILL.md files) and
  `/Users/kevinng/codep/obsidian-navigator/refresh.sh` (bash script, no
  args needed — defaults to `$HOME/Documents/Kevin Notes`).
- Produces: nothing consumed by other tasks — this is the only task.

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p "/Users/kevinng/Documents/Kevin Notes/.claude/skills/weekly-brain-sync"
```

- [ ] **Step 2: Write SKILL.md**

Create `/Users/kevinng/Documents/Kevin Notes/.claude/skills/weekly-brain-sync/SKILL.md`
with exactly this content:

```markdown
---
name: weekly-brain-sync
description: Use when you want to run the full vault maintenance pipeline in one shot — trims LLM chat tails, reindexes raw/, updates wiki/, then reindexes and restarts the obsidian-navigator server. Use instead of running trim-llm, reindex, wiki-update, and refresh.sh separately.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, Skill
---

# Weekly Brain Sync

Runs the full vault-to-navigator maintenance pipeline end to end, in order.

## Steps

1. `cd "$HOME/Documents/Kevin Notes"`
2. Invoke skill `trim-llm`. If it reports an error, stop and report it —
   do not continue to step 3.
3. Invoke skill `reindex`. If it reports an error, stop and report it —
   do not continue to step 4.
4. Invoke skill `wiki-update`. If it reports an error, stop and report it —
   do not continue to step 5.
5. Run the navigator refresh:

   ```bash
   cd /Users/kevinng/codep/obsidian-navigator && ./refresh.sh
   ```

   If this fails (non-zero exit, or "Restarting server" never printed),
   stop and report the failure output.

## Report

After all steps succeed, report a combined summary covering:
- Files trimmed by `trim-llm` (and how many lines removed each)
- New entries added by `reindex` (file names)
- Wiki pages created/updated by `wiki-update` (titles + one-line reason
  each)
- The `refresh.sh` output (confirm "Done. Server restarted (PID ...)")

If any step stopped early, report which step failed and the exact error
instead of a summary.
```

- [ ] **Step 3: Verify frontmatter and file placement**

```bash
head -6 "/Users/kevinng/Documents/Kevin Notes/.claude/skills/weekly-brain-sync/SKILL.md"
ls "/Users/kevinng/Documents/Kevin Notes/.claude/skills/"
```

Expected: frontmatter matches Step 2 exactly, and `weekly-brain-sync`
appears alongside `trim-llm`, `reindex`, `wiki-update` in the listing.

- [ ] **Step 4: End-to-end run (the real test)**

Invoke the skill for real: `Skill(skill: "weekly-brain-sync")`.

This is a live run against the real vault and real navigator server — there
is no mock mode, since the three sub-skills and `refresh.sh` all operate on
real files. Expected: each of the 4 steps executes in order, ending with
`refresh.sh`'s "Done. Server restarted (PID ...)" line, and the final report
lists whatever was actually trimmed/indexed/updated (an empty result, e.g.
"Wiki is up to date", is a valid pass — it means the step ran correctly
against a vault with nothing new to process).

If any step fails, fix the SKILL.md (Step 2) and re-run Step 4 from the top.

- [ ] **Step 5: Commit**

```bash
cd "/Users/kevinng/Documents/Kevin Notes"
git add .claude/skills/weekly-brain-sync/SKILL.md 2>/dev/null || true
```

Note: check first whether the vault is a git repo (`git rev-parse
--is-inside-work-tree`). If it isn't, skip commit for the vault file — it's
outside version control and this step is a no-op. The plan's spec doc and
this plan file live in `obsidian-navigator` and are committed separately
(already done during brainstorming).
```

## Self-Review

- **Spec coverage:** Design calls for (1) vault location, (2) invoke-by-name
  composition, (3) explicit-only invocation, (4) stop-on-first-failure,
  (5) quoted vault path. All five are in Step 2's SKILL.md content above.
- **No placeholders:** SKILL.md content is complete and final, not a
  sketch.
- **Consistency:** skill name `weekly-brain-sync` matches the spec exactly;
  sibling skill names (`trim-llm`, `reindex`, `wiki-update`) match what's on
  disk (verified during brainstorming).
