# Obsidian Second Brain Navigator — Project Spec

## Goal

Build a local web app that lets me navigate and query my Obsidian vault through a browser. Two core modes:
1. **LLM Query mode** — ask natural language questions, get answers grounded in my notes with source citations
2. **Wikipedia-style Browse mode** — read notes with rendered markdown, clickable `[[wikilinks]]`, backlinks, tags

---

## Architecture

```
obsidian-navigator/
├── CLAUDE.md              ← this file
├── server.py              ← FastAPI backend (main entrypoint)
├── indexer.py             ← vault crawler + wikilink parser + index builder
├── rag.py                 ← ChromaDB vector store + RAG query engine
├── requirements.txt       ← all Python dependencies
├── setup.sh               ← one-shot setup + launch script
├── README.md              ← usage instructions
└── frontend/
    └── index.html         ← single-file frontend (no build step)
```

---

## Phase 1 — Backend Foundation

### `indexer.py`
- Accepts `--vault <path>` CLI argument
- Recursively scans vault for all `.md` files
- For each file, parse:
  - YAML frontmatter (title, tags, aliases, date)
  - Raw markdown body
  - All `[[wikilinks]]` and `[[wikilink|aliases]]` — extract as outgoing links
- Build an in-memory index: `{ slug → { title, tags, body, links, path } }`
- Persist index as `index.json` in the project root
- Print summary: total notes, total links, total tags

### `server.py`
- FastAPI app, runs on `http://localhost:8000`
- CORS enabled for all origins (needed for browser fetch)
- Loads `index.json` on startup
- Endpoints:
  - `GET /notes` → list all notes (slug, title, tags)
  - `GET /note/{slug}` → full note (title, body, tags, outgoing links)
  - `GET /backlinks/{slug}` → list of notes that link TO this slug
  - `GET /tags` → all unique tags with counts
  - `GET /search?q=<query>` → fuzzy title + body search, return top 10 matches
  - `GET /health` → `{ status: "ok", note_count: N }`

### `requirements.txt`
```
fastapi
uvicorn
python-frontmatter
chromadb
sentence-transformers
anthropic
fuzzywuzzy
python-levenshtein
```

---

## Phase 2 — RAG Query Engine

### `rag.py`
- On first run, chunk all notes into ~500 token chunks with 50 token overlap
- Embed chunks using `sentence-transformers` (`all-MiniLM-L6-v2` model)
- Store in ChromaDB persisted at `./chroma_db/`
- On subsequent runs, only re-index changed files (compare mtime)
- Expose a `query(question: str, top_k: int = 5)` function that:
  - Embeds the question
  - Retrieves top_k most relevant chunks
  - Returns list of `{ chunk_text, note_slug, note_title, score }`

### Add to `server.py`
- `POST /query` endpoint accepting `{ "question": "...", "api_key": "..." }`
- Calls `rag.query()` to get relevant chunks
- Sends to Claude API (`claude-sonnet-4-20250514`) with this system prompt:

```
You are a knowledgeable assistant helping the user explore their personal Obsidian knowledge base (second brain).

Answer the user's question using ONLY the provided note excerpts below. 
- Be conversational and direct
- Cite which notes you drew from (use the note title, formatted as [[Note Title]])
- If the notes don't contain enough information to answer, say so honestly
- Never make up information not present in the notes
```

- Returns `{ "answer": "...", "sources": [{ "slug": "...", "title": "...", "score": 0.9 }] }`

---

## Phase 3 — Frontend

### `frontend/index.html`
Single HTML file, pure vanilla JS, no build step required. All API calls go to `http://localhost:8000`.

**Layout — three-panel design:**
```
┌─────────────────────────────────────────────────────┐
│  🧠 Second Brain          [search bar]    [settings] │
├──────────────┬──────────────────────┬────────────────┤
│              │                      │                │
│  Sidebar     │   Note / Browse      │  LLM Chat      │
│              │   Panel              │  Panel         │
│  - File tree │                      │                │
│  - Tags      │  Rendered markdown   │  Ask anything  │
│  - Recent    │  [[wikilinks]]       │  about your    │
│              │  clickable           │  notes         │
│              │                      │                │
│              │  --- Backlinks ---   │  Sources cited │
│              │  Notes that link     │  as clickable  │
│              │  here                │  note links    │
└──────────────┴──────────────────────┴────────────────┘
```

**Features:**
- Dark theme, refined editorial aesthetic
- Sidebar: collapsible file tree grouped by folder, tag cloud, 5 most recently modified notes
- Browse panel: render markdown (headings, bold, italic, code blocks, lists, blockquotes), `[[wikilinks]]` rendered as styled clickable links that navigate to that note, backlinks section at bottom
- Search: real-time fuzzy search calling `GET /search?q=`, results appear as dropdown
- Chat panel: text input + send button, calls `POST /query`, displays answer + source notes as clickable links that open in browse panel
- Settings gear: field to enter Anthropic API key (stored in localStorage), vault path display
- Breadcrumb trail showing navigation history
- Loading states for all async operations

---

## Phase 4 — Setup & Docs

### `setup.sh`
```bash
#!/bin/bash
# Usage: ./setup.sh --vault /path/to/your/vault
# - Creates Python venv
# - Installs requirements
# - Runs indexer
# - Builds ChromaDB vector index  
# - Starts server on port 8000
# - Prints "Open frontend/index.html in your browser"
```

### `README.md`
- Prerequisites: Python 3.10+, Anthropic API key
- Quick start (3 commands max)
- How to point at vault
- How to get/set API key
- What each file does
- Troubleshooting: port in use, vault not found, ChromaDB errors

---

## Implementation Notes

- **Slug generation**: lowercase filename without `.md` extension, spaces → hyphens
- **Wikilink resolution**: try exact slug match first, then fuzzy match on title/aliases
- **Vault path**: accept via `--vault` CLI arg OR `OBSIDIAN_VAULT` env var
- **API key**: accept via `ANTHROPIC_API_KEY` env var OR per-request in POST body
- **No auth needed**: this is local-only, localhost only
- **Error handling**: if a `[[wikilink]]` points to a non-existent note, render it as greyed-out
- **Performance**: index.json should load in <1s for vaults up to 10,000 notes; ChromaDB query should return in <2s

---

## Running Order

```bash
# 1. Install deps
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Index vault
python indexer.py --vault ~/path/to/obsidian/vault

# 3. Build vector index (first time is slow, ~1 min per 1000 notes)
python rag.py --vault ~/path/to/obsidian/vault --build

# 4. Start server
uvicorn server:app --reload --port 8000

# 5. Open frontend in browser
open frontend/index.html
```

---

## Yolo Instructions for Claude Code

Work through phases 1–4 in order. Complete each phase fully before moving to the next. After each phase, verify the code runs without errors before proceeding. Write clean, well-commented code. When in doubt about vault path, default to `~/obsidian` or prompt the user. Do not ask for permission — just build it.
