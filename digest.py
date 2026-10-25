"""
digest.py — "What's new in my wiki" digest.

Picks the most recently updated pages in the vault's wiki/ folder, asks an LLM
for a short catch-up summary of each, and caches the result in
digest_cache.json so reopening the digest is instant and free. The cache is
keyed on the selected pages' mtimes, so it goes stale when brain-sync changes
the wiki.
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

CACHE_PATH = Path(__file__).parent / "digest_cache.json"

DIGEST_SIZE = 10
# brain-sync housekeeping pages, not content
EXCLUDED_SLUGS = {"log", "index"}
# Pages longer than this are truncated in the prompt to bound token usage
MAX_PAGE_CHARS = 8000
# A page modified within this long of being created counts as "new"
NEW_PAGE_WINDOW_SECS = 24 * 60 * 60

DIGEST_SYSTEM_PROMPT = """\
You write a catch-up digest of the user's personal wiki (an Obsidian second brain).
The wiki pages are compiled from articles the user clipped but may not have read in detail.

For each page, write 3-5 plain sentences: what it is about, the key takeaways, and any
memorable fact or example. For pages marked UPDATED, focus on what the newest source added.
Write for someone catching up quickly: direct, concrete, no filler, no markdown.

Also write a 2-3 sentence overview of the themes across the whole batch.

Use ONLY the page content provided. Respond with JSON only, in exactly this shape:
{"overview": "...", "items": [{"slug": "...", "summary": "..."}]}\
"""


def _is_under(note: dict, folder: str) -> bool:
    return f"/{folder}/" in note.get("path", "")


def select_pages(index: dict[str, dict], n: int = DIGEST_SIZE) -> list[dict]:
    """Return the n most recently modified wiki pages with digest metadata."""
    wiki = [
        (slug, note) for slug, note in index.items()
        if _is_under(note, "wiki") and slug not in EXCLUDED_SLUGS
    ]
    wiki.sort(key=lambda item: item[1].get("mtime") or 0, reverse=True)

    pages = []
    for slug, note in wiki[:n]:
        mtime = note.get("mtime") or 0
        created = note.get("created", mtime)
        is_new = mtime - created < NEW_PAGE_WINDOW_SECS

        # Clippings this page was compiled from, newest first
        source_slugs = {
            link["slug"] for link in note.get("links", [])
            if link.get("slug") in index and _is_under(index[link["slug"]], "raw")
        }
        sources = sorted(
            ({"slug": s, "title": index[s]["title"]} for s in source_slugs),
            key=lambda src: index[src["slug"]].get("created", 0),
            reverse=True,
        )

        pages.append({
            "slug": slug,
            "title": note["title"],
            "status": "new" if is_new else "updated",
            "mtime": mtime,
            "sources": sources,
        })
    return pages


def cache_key(pages: list[dict]) -> str:
    """Fingerprint of the selected pages; changes whenever the wiki does."""
    raw = "|".join(f"{p['slug']}:{p['mtime']}" for p in pages)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_prompt(pages: list[dict], index: dict[str, dict]) -> str:
    """Build the user message containing every page's content."""
    parts = []
    for page in pages:
        body = index[page["slug"]]["body"]
        if len(body) > MAX_PAGE_CHARS:
            body = body[:MAX_PAGE_CHARS] + "\n[...truncated]"
        header = f"=== slug: {page['slug']} | {page['status'].upper()} ==="
        if page["status"] == "updated" and page["sources"]:
            header += f"\nNewest source: {page['sources'][0]['title']}"
        parts.append(f"{header}\n{body}")
    return "Here are my most recently updated wiki pages:\n\n" + "\n\n".join(parts)


def parse_response(text: str) -> dict[str, Any]:
    """Extract the JSON object from the LLM reply (tolerates code fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("LLM reply did not contain JSON")
    return json.loads(match.group(0))


def assemble(pages: list[dict], reply: dict[str, Any]) -> dict[str, Any]:
    """Merge LLM summaries with page metadata into the digest returned to clients."""
    summaries = {
        item.get("slug"): item.get("summary", "")
        for item in reply.get("items", [])
    }
    return {
        "generated_at": time.time(),
        "key": cache_key(pages),
        "overview": reply.get("overview", ""),
        "items": [
            {
                "slug": p["slug"],
                "title": p["title"],
                "status": p["status"],
                "summary": summaries.get(p["slug"], ""),
                "sources": p["sources"],
            }
            for p in pages
        ],
    }


def load_cache() -> dict[str, Any] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(digest: dict[str, Any]) -> None:
    CACHE_PATH.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
