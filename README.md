# Obsidian Second Brain Navigator

A local web app for navigating and querying your Obsidian vault. Browse notes with rendered markdown and clickable wikilinks, or ask natural language questions answered by your own notes via RAG + Claude.

Works on desktop and mobile (responsive layout).

## Prerequisites

- Python 3.10+
- An Anthropic or OpenRouter API key (only needed for LLM query mode)

## Quick Start

```bash
chmod +x setup.sh
./setup.sh --vault ~/path/to/your/obsidian/vault
```

The script creates a venv, installs dependencies, indexes your vault, builds the vector index, and starts the server. Then open `http://localhost:8000` in your browser.

To skip the slow vector index build (disables LLM queries):

```bash
./setup.sh --vault ~/path/to/your/obsidian/vault --skip-rag
```

## Setting Your API Key

The LLM query feature requires an Anthropic or OpenRouter API key.

**In the app:** click the settings gear ⚙ (top right) and paste your key. Stored in browser localStorage only.

**Environment variable:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

OpenRouter keys (`sk-or-...`) are also supported and offer cheaper model options.

## Refreshing Your Vault

When you add, edit or delete notes in Obsidian, run:

```bash
./refresh.sh
```

This re-indexes the vault and rebuilds the vector index. The server picks up changes automatically — no restart needed.

## Mobile Access via Tailscale

To access the app privately from your phone:

1. Install [Tailscale](https://tailscale.com) on both your Mac and phone
2. Enable HTTPS certificates in the Tailscale admin console
3. Run once to expose the server on your tailnet:
   ```bash
   tailscale serve --bg 8000
   ```
4. Your app is now available at `https://<your-machine>.ts.net` — only accessible to devices on your Tailscale network

Add it as a home screen icon in Safari: Share → Add to Home Screen.

## File Overview

| File | Description |
|------|-------------|
| `server.py` | FastAPI backend, runs on port 8000 |
| `indexer.py` | Crawls vault, parses wikilinks and frontmatter, writes `index.json` |
| `rag.py` | Embeds note chunks into ChromaDB, exposes `query()` for semantic search |
| `frontend/index.html` | Single-file UI — responsive, works on desktop and mobile |
| `setup.sh` | First-time setup and launch script |
| `refresh.sh` | Re-indexes vault and rebuilds vector index |
| `requirements.txt` | Python dependencies |
| `tests/` | Playwright tests for desktop and mobile layout |
| `chroma_db/` | Persisted vector index (auto-created, gitignored) |
| `index.json` | Flat note index (auto-created by indexer, gitignored) |

## How This Was Built

This project started with a conversation on the Claude web — before a single line of code existed. What began as a broader itch to explore LLM coding (self-harnessing multi-agent setups, coding from a phone) narrowed, over the course of one chat, into something concrete: a local web app to navigate my Obsidian second brain through both an LLM query interface and a Wikipedia-style browsing UI.

The idea was sketched out in that chat, then refined through a few rounds of questions — how the vault is accessed (local + git), what the first version should prioritize (query and browse, equally), whether a backend was acceptable (yes). Rather than jump straight to code, the goal became a dev plan I could hand to an autonomous agent. Claude was asked to generate a CLAUDE.md spec file that would serve as the blueprint for the entire build.

An interactive artifact was built to demonstrate the pattern — an Architect → Coder → Reviewer pipeline running across four phases, with Claude calling Claude via the API. I did not exactly execute on it. The real work belonged in Claude Code, where agents actually write files, run them, and fix what breaks. The CLAUDE.md was the bridge between the two.

As I could not create a docker container to call my Claude Pro account, development was driven through Claude Code YOLO style using the multi-agent, phased approach the spec laid out. The spec drove the backend (FastAPI, RAG pipeline, ChromaDB), then the desktop frontend, then deployment.

The deployment path itself was exploratory. Cloudflare Tunnel was the first plan but stalled at the zone/domain requirement. Tailscale Serve turned out to be the right fit — already installed, private by default, no domain needed.

The mobile UI required its own design pass. Three layout options were prototyped as interactive HTML mockups for comparison (also in this repo), then a hybrid was chosen: Option C's search-first card layout with Option A's two-tab bar. The final implementation is a single responsive file — desktop gets the three-panel layout, mobile gets the tab-driven hybrid, all from one index.html.

Playwright tests were added to make verification autonomous — the test suite spins up the server itself and covers both desktop and mobile viewports. That said, the tests are deliberately basic: they verify structure and navigation, not semantic correctness of RAG responses or edge cases in note parsing.

In summary, I practised the multiple-agents at one point running as two parallel tasks for phases 2 and 3, and in YOLO mode. Then, I setup playwright tests to ensure the mobile part of enhancements can run towards goal complete (but in actual fact, it finished in one shot). Finally, having a chat, and produce a CLAUDE.md with a prototype is an interesting way to initiate development outside Claude Code.

## EXPERIMENTS

**HTML prototyping technique:** I experimented with developing using an HTML mockup technique I learnt from the "How I AI" podcast — building interactive static prototypes first to agree on layout and interaction before touching the real codebase. The mobile layout options and the theme toggle placement prototype in this repo came from that workflow.

**Mobile-first development workflow:** I now have a workflow that uses the Claude Code tab on mobile to read GitHub issues, then prototype and develop entirely on a mobile phone. I then use the Claude Dispatch tab on mobile to issue commands by changing a command file (such as git pull, server start and stop). In this way I can develop on mobile end-to-end. Testing via mobile is still an area to work on.

## Troubleshooting

**Port 8000 already in use**
```bash
lsof -ti:8000 | xargs kill -9
```

**Vault not found**
Make sure the path exists and contains `.md` files. iCloud vaults may need to be downloaded locally first.

**ChromaDB errors / stale index**
```bash
rm -rf chroma_db/
./refresh.sh
```

**Slow first run**
The first `--build` downloads the `all-MiniLM-L6-v2` embedding model (~90 MB) and embeds all your notes. Subsequent runs only re-embed changed files.

**Mobile not loading**
Make sure Tailscale is active on your phone and `tailscale serve status` shows the proxy is running on your Mac.
