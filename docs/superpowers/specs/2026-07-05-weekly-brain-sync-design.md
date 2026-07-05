# weekly-brain-sync skill — design

## Goal

A single explicit command that runs the full vault-to-navigator maintenance
pipeline end to end, instead of running four separate commands by hand.

## Background

The vault (`~/Documents/Kevin Notes`) already has three maintenance skills
under `.claude/skills/`, each explicit-invocation-only
(`disable-model-invocation: true`):

- `trim-llm` — strips trailing "want me to do more?" paragraphs from LLM
  chat exports in `raw/`
- `reindex` — appends index entries in `raw/index.md` for new files in `raw/`
- `wiki-update` — compiles newly-indexed raw files into `wiki/` pages

Separately, `obsidian-navigator/refresh.sh` re-indexes the vault for the
navigator app and restarts its server.

Today these four steps are run manually, in order, as separate commands.

## Design

New skill: **`weekly-brain-sync`**, placed at
`~/Documents/Kevin Notes/.claude/skills/weekly-brain-sync/SKILL.md`, alongside
its three siblings.

### Frontmatter

```yaml
name: weekly-brain-sync
description: Run the full vault maintenance pipeline end to end — trim LLM chat tails, reindex raw/, update wiki/, then reindex and restart the obsidian-navigator server. Use for periodic full maintenance in one shot.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
```

`disable-model-invocation: true` matches the siblings — this only ever runs
when explicitly invoked, never auto-triggered.

### Sequence

1. `cd "$HOME/Documents/Kevin Notes"` (quoted — path has a space)
2. Read `trim-llm`'s SKILL.md and carry out its Task
3. Read `reindex`'s SKILL.md and carry out its Task
4. Read `wiki-update`'s SKILL.md and carry out its Task
5. `cd /Users/kevinng/codep/obsidian-navigator && ./refresh.sh`
6. Report a combined summary: files trimmed, raw entries added, wiki pages
   created/updated, and the refresh.sh output (server restart PID).

### Composition approach

**Correction (discovered during testing):** the original design called for
invoking the three existing skills by name via the Skill tool. In practice
the Skill tool refuses to run any skill with `disable-model-invocation:
true` at all — that flag blocks explicit-by-name invocation too, not just
auto-triggering by description match. It's a hard block enforced by the
tool, not merely a suggestion.

The corrected approach: `weekly-brain-sync`'s instructions tell the agent to
`Read` each sibling's SKILL.md file and carry out its documented Task
directly, rather than calling the Skill tool. This still keeps one source
of truth (the task logic lives only in `trim-llm`/`reindex`/`wiki-update`'s
own files — `weekly-brain-sync` doesn't duplicate it), it just changes the
mechanism from "invoke" to "read and follow."

### Failure handling

Stop at the first step that fails and report the error. Do not proceed to
later steps (e.g. don't run `wiki-update` against a `raw/index.md` that
`reindex` failed to update correctly; don't restart the navigator server
against a stale re-index if an earlier step errored).

## Out of scope

- No changes to the three existing sibling skills.
- No changes to `refresh.sh` itself.
- No scheduling/cron — this is a manually-invoked, on-demand command.
