"""
server.py — FastAPI backend for Obsidian Navigator.

Run with:
    uvicorn server:app --reload --port 8000
"""

import json
import os
from pathlib import Path
from typing import Any

import anthropic
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fuzzywuzzy import fuzz
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Obsidian Navigator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Index loading
# ---------------------------------------------------------------------------

INDEX_PATH = Path(__file__).parent / "index.json"

# In-memory store: { slug → note_dict }
_index: dict[str, dict[str, Any]] = {}


def load_index() -> None:
    """Load index.json from disk into memory."""
    global _index
    if not INDEX_PATH.exists():
        print(
            f"Warning: {INDEX_PATH} not found. Run indexer.py first.",
            flush=True,
        )
        _index = {}
        return

    with open(INDEX_PATH, encoding="utf-8") as f:
        _index = json.load(f)

    print(f"Loaded {len(_index)} notes from {INDEX_PATH}", flush=True)


@app.on_event("startup")
async def startup_event() -> None:
    load_index()


# ---------------------------------------------------------------------------
# Frontend static serving
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).parent / "frontend"

@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


# ---------------------------------------------------------------------------
# Helper: build backlink map
# ---------------------------------------------------------------------------

def _build_backlink_map() -> dict[str, list[str]]:
    """
    Return a mapping of slug → list of slugs that link TO that slug.

    Uses the resolved `slug` field in each note's `links` list.
    """
    backlinks: dict[str, list[str]] = {slug: [] for slug in _index}
    for source_slug, note in _index.items():
        for link in note.get("links", []):
            target = link.get("slug")
            if target and target in _index:
                backlinks.setdefault(target, []).append(source_slug)
    return backlinks


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Basic health check."""
    return {"status": "ok", "note_count": len(_index)}


@app.get("/notes")
def list_notes() -> list[dict]:
    """Return a lightweight list of all notes (slug, title, tags)."""
    return [
        {"slug": slug, "title": note["title"], "tags": note["tags"]}
        for slug, note in _index.items()
    ]


@app.get("/note/{slug}")
def get_note(slug: str) -> dict:
    """Return the full note for a given slug."""
    note = _index.get(slug)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note '{slug}' not found")
    return {
        "slug": slug,
        "title": note["title"],
        "tags": note["tags"],
        "aliases": note.get("aliases", []),
        "date": note.get("date", ""),
        "body": note["body"],
        "links": note["links"],
        "path": note["path"],
        "mtime": note.get("mtime"),
    }


@app.get("/backlinks/{slug}")
def get_backlinks(slug: str) -> list[dict]:
    """
    Return notes that link TO the given slug.

    Each item: { slug, title, tags }
    """
    if slug not in _index:
        raise HTTPException(status_code=404, detail=f"Note '{slug}' not found")

    backlink_map = _build_backlink_map()
    sources = backlink_map.get(slug, [])

    return [
        {
            "slug": src,
            "title": _index[src]["title"],
            "tags": _index[src]["tags"],
        }
        for src in sources
        if src in _index
    ]


@app.get("/tags")
def list_tags() -> list[dict]:
    """Return all unique tags with their occurrence counts."""
    counts: dict[str, int] = {}
    for note in _index.values():
        for tag in note.get("tags", []):
            counts[tag] = counts.get(tag, 0) + 1

    return sorted(
        [{"tag": tag, "count": count} for tag, count in counts.items()],
        key=lambda x: (-x["count"], x["tag"]),
    )


@app.get("/search")
def search(q: str = Query(..., min_length=1)) -> list[dict]:
    """
    Fuzzy search across note titles and bodies.

    Returns up to 10 results sorted by descending score.
    Each result: { slug, title, score }
    """
    q_lower = q.lower()
    results: list[dict] = []

    for slug, note in _index.items():
        title = note.get("title", "")
        body = note.get("body", "")

        # Score: best of title partial ratio and body partial ratio.
        # Title match is weighted higher (×1.2 cap at 100).
        title_score = fuzz.partial_ratio(q_lower, title.lower())
        body_score = fuzz.partial_ratio(q_lower, body.lower())

        # Prefer title matches
        combined = max(min(int(title_score * 1.2), 100), body_score)

        if combined >= 40:  # threshold to filter out noise
            results.append({"slug": slug, "title": title, "score": combined})

    results.sort(key=lambda x: -x["score"])
    return results[:10]


# ---------------------------------------------------------------------------
# RAG / LLM query endpoint
# ---------------------------------------------------------------------------

_RAG_SYSTEM_PROMPT = """\
You are a knowledgeable assistant helping the user explore their personal Obsidian knowledge base (second brain).

Answer the user's question using ONLY the provided note excerpts below.
- Be conversational and direct
- Cite which notes you drew from (use the note title, formatted as [[Note Title]])
- If the notes don't contain enough information to answer, say so honestly
- Never make up information not present in the notes\
"""


class QueryRequest(BaseModel):
    question: str
    api_key: str = ""


@app.post("/query")
def rag_query(request: QueryRequest) -> dict:
    """
    Answer a natural-language question using RAG over the vault.

    Accepts:
        { "question": "...", "api_key": "..." }

    Returns:
        { "answer": "...", "sources": [{ "slug", "title", "score" }] }
    """
    from pathlib import Path as _Path
    chroma_dir = _Path(__file__).parent / "chroma_db"
    if not chroma_dir.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "RAG index not built yet. "
                "Run `python rag.py --vault <path> --build` first."
            ),
        )

    # Resolve API key: request body → env vars (Anthropic or OpenRouter).
    api_key = (
        request.api_key.strip()
        or os.environ.get("ANTHROPIC_API_KEY", "")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "No API key provided. Supply an Anthropic or OpenRouter key "
                "in the request body or via ANTHROPIC_API_KEY / OPENROUTER_API_KEY env var."
            ),
        )

    # Lazy import so the server starts even if rag deps are missing.
    try:
        from rag import query as rag_query_fn
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG module could not be imported: {exc}",
        )

    # Retrieve relevant chunks.
    try:
        hits = rag_query_fn(request.question, top_k=5)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"RAG retrieval error: {exc}"
        )

    if not hits:
        return {
            "answer": "No relevant notes found for your question.",
            "sources": [],
        }

    # Build context block for the LLM prompt.
    context_parts: list[str] = []
    for i, hit in enumerate(hits, 1):
        context_parts.append(
            f"--- Excerpt {i} from [[{hit['note_title']}]] ---\n{hit['chunk_text']}"
        )
    context_block = "\n\n".join(context_parts)

    user_message = (
        f"Here are relevant excerpts from my notes:\n\n{context_block}"
        f"\n\n---\n\nMy question: {request.question}"
    )

    # OpenRouter keys start with "sk-or-"; route accordingly.
    is_openrouter = api_key.startswith("sk-or-")

    try:
        if is_openrouter:
            from openai import OpenAI
            client_or = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            response = client_or.chat.completions.create(
                model="deepseek/deepseek-chat",
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": _RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            answer = response.choices[0].message.content
        else:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                system=_RAG_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            answer = message.content[0].text
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key.")
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")
    except Exception as exc:
        from openai import AuthenticationError as OpenAIAuthError
        if isinstance(exc, OpenAIAuthError):
            raise HTTPException(status_code=401, detail="Invalid OpenRouter API key.")
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc}")

    # Deduplicate sources (multiple chunks from the same note).
    seen: set[str] = set()
    sources: list[dict] = []
    for hit in hits:
        slug = hit["note_slug"]
        if slug not in seen:
            seen.add(slug)
            sources.append({
                "slug": slug,
                "title": hit["note_title"],
                "score": hit["score"],
            })

    return {"answer": answer, "sources": sources}
