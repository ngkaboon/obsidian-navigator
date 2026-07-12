# prune skill — design

## Goal

When a raw file is deleted from `raw/`, nothing today cleans up after it:
`reindex` only scans forward (new files → new index entries), so the
deleted file's block stays in `raw/index.md` with a now-broken
`[[wikilink]]`, and any wiki page that cited it under **Sources** keeps
that dangling citation indefinitely.

## Background

Vault maintenance skills today (all `~/Documents/Kevin Notes/.claude/skills/`,
all `disable-model-invocation: true`):

- `trim-llm` — strips trailing LLM sign-off paragraphs from `raw/` files
- `reindex` — diffs `raw/` against `raw/index.md`, appends entries for new
  files. Never removes entries.
- `wiki-update` — compiles indexed-but-uncompiled raw files into `wiki/`
  pages, tracked via `wiki/log.md` (append-only ingest log)
- `brain-sync` — chains the above (trim opt-in, then reindex, then
  wiki-update, then `obsidian-navigator/refresh.sh`) via read-and-follow
  (Skill tool can't invoke `disable-model-invocation` skills, confirmed
  during `brain-sync`'s build)

None of these detect or handle raw files being deleted.

## Design

New skill: **`prune`**, at
`~/Documents/Kevin Notes/.claude/skills/prune/SKILL.md`.

### Frontmatter

```yaml
name: prune
description: Use when you've deleted files from raw/ and need to clean up the resulting stale raw/index.md entries and dangling Sources citations in wiki/ pages.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Bash
```

### Task

1. **Find stale entries** — same list-diff mechanism as `reindex` (grep
   `[[...]]` titles out of `raw/index.md`, `ls raw/*.md` for what actually
   exists), but reversed: titles present in the index with no matching
   file in `raw/` are stale.
2. If the stale list is empty: report "No stale entries found" and stop.
3. For each stale title:
   a. **Remove its `raw/index.md` block.** Read the file, locate the exact
      `### [[Title]]` block (from the heading down to just before the next
      `### ` heading or end of file), and remove it along with one
      adjacent `---` separator line, so spacing around the remaining
      blocks stays consistent with the file's existing convention. Use
      Edit — this is a precise, read-first-then-edit removal (same style
      as `trim-llm`'s block removal), not a scripted regex substitution,
      because block content varies and titles may contain characters that
      are awkward to pattern-match safely in bash.
   b. **Strip dangling wiki citations.** Grep `wiki/*.md` for a Sources
      bullet citing the title (format: `- [[Title]] (raw/)`). For each
      page that matches, remove just that bullet line — no other edits to
      the page (its synthesized prose stays; only the source citation for
      the now-deleted file goes).
   c. **Log it.** Append one line to `wiki/log.md`:
      `## [YYYY-MM-DD] prune | Title — removed from index; removed from
      Sources on: Page A, Page B` (or `no wiki citations found` if step 3b
      matched nothing). This follows `wiki/log.md`'s existing append-only
      convention (it already has `ingest` and `bulk-compile` entry types;
      `prune` is a new entry type in the same log).
4. **Report** — for each stale title pruned: confirmation it was removed
   from the index, and the list of wiki pages whose Sources bullet was
   removed (or "none cited it").

### Integration into `brain-sync`

New opt-in argument `prune`, same pattern as the existing `trim` argument
— skipped by default, included only when explicitly passed. Order in the
pipeline: `trim` (if passed) → `prune` (if passed) → `reindex` →
`wiki-update` → `refresh.sh`. Prune runs before reindex so cleanup happens
before any new-file scan (the two operate on disjoint file sets — files
present vs. entries with no file — so strict ordering between them isn't
required for correctness, but cleanup-before-add reads more naturally).

`brain-sync`'s frontmatter description and Report section get updated to
mention the new opt-in step, matching how `trim` is documented today.

## Out of scope

- No changes to `trim-llm`, `reindex`, or `wiki-update` themselves.
- No automatic editing of wiki page prose/content beyond the Sources
  bullet — if a deleted raw file's claims live on in a page's body text,
  that's left for manual review.
- No handling of raw files being *renamed* (distinct from deleted) — a
  rename looks like a delete + a new file today, and it isn't addressed by
  this skill either. Out of scope for this design.
