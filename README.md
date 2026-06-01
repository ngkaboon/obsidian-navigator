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
