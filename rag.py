"""
rag.py — ChromaDB vector store + RAG query engine for Obsidian Navigator.

Usage (build/rebuild vector index):
    python rag.py --vault /path/to/obsidian/vault --build

Falls back to OBSIDIAN_VAULT env var, then ~/obsidian.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent
INDEX_PATH = PROJECT_ROOT / "index.json"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "obsidian_notes"

# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

# Rough heuristic: 1 token ≈ 0.75 words for English prose.
# Targeting ~500 tokens → ~375 words per chunk.
CHUNK_TARGET_WORDS = 375
# Overlap = ~50 tokens → ~37 words, implemented as 1-paragraph overlap.


def _word_count(text: str) -> int:
    """Count whitespace-delimited words in text."""
    return len(text.split())


def chunk_note(body: str) -> list[str]:
    """
    Split a note body into overlapping chunks.

    Strategy:
    1. Split on double newlines to get paragraphs.
    2. Group paragraphs until the word budget (~375 words) is exhausted.
    3. Carry the last paragraph of the previous chunk into the next one
       as the overlap (~50-token / 1-paragraph overlap).
    4. Very long single paragraphs are split by sentence as a fallback.

    Returns a list of chunk strings (may be empty if body is blank).
    """
    if not body or not body.strip():
        return []

    # Split into paragraphs, filtering empties.
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    overlap_para: str | None = None  # last paragraph of the previous chunk

    for para in paragraphs:
        para_words = _word_count(para)

        # If a single paragraph already exceeds the budget, split it by sentence.
        if para_words > CHUNK_TARGET_WORDS:
            # Flush current chunk first.
            if current:
                chunk_text = "\n\n".join(current)
                chunks.append(chunk_text)
                overlap_para = current[-1]
                current = []
                current_words = 0

            # Start new chunk with overlap from previous chunk.
            sentences = _split_sentences(para)
            sentence_group: list[str] = []
            sg_words = 0
            if overlap_para:
                sentence_group.append(overlap_para)
                sg_words = _word_count(overlap_para)
                overlap_para = None

            for sent in sentences:
                s_words = _word_count(sent)
                if sg_words + s_words > CHUNK_TARGET_WORDS and sentence_group:
                    chunks.append(" ".join(sentence_group))
                    # Overlap: carry last sentence.
                    sentence_group = [sentence_group[-1], sent]
                    sg_words = _word_count(sentence_group[-2]) + s_words
                else:
                    sentence_group.append(sent)
                    sg_words += s_words

            if sentence_group:
                overlap_para = sentence_group[-1]
                current = [" ".join(sentence_group)]
                current_words = sg_words
            continue

        # Normal paragraph: fits within budget.
        if current_words + para_words > CHUNK_TARGET_WORDS and current:
            # Flush.
            chunks.append("\n\n".join(current))
            # Carry last paragraph as overlap into next chunk.
            overlap_para = current[-1]
            current = []
            current_words = 0

        # Start new chunk: inject overlap paragraph first.
        if not current and overlap_para:
            current = [overlap_para]
            current_words = _word_count(overlap_para)
            overlap_para = None

        current.append(para)
        current_words += para_words

    # Flush remaining.
    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _split_sentences(text: str) -> list[str]:
    """
    Naive sentence splitter: split on '. ', '! ', '? '.
    Preserves the delimiter character.
    """
    import re
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Embedding model (lazy singleton)
# ---------------------------------------------------------------------------

_embedding_model = None


def _get_embedding_model():
    """Load sentence-transformers model once and cache it."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        print("Loading embedding model (all-MiniLM-L6-v2)…", flush=True)
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("Embedding model loaded.", flush=True)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts and return a list of float vectors."""
    model = _get_embedding_model()
    vectors = model.encode(texts, show_progress_bar=False, batch_size=64)
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# ChromaDB client (lazy singleton)
# ---------------------------------------------------------------------------

_chroma_client = None
_chroma_collection = None


def _get_collection():
    """Return the ChromaDB collection, initialising client on first call."""
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _chroma_collection


# ---------------------------------------------------------------------------
# Change detection helpers
# ---------------------------------------------------------------------------

def _get_indexed_mtimes(collection) -> dict[str, float]:
    """
    Return a mapping of slug → mtime for all chunks already in ChromaDB.

    We only need one entry per slug, so we take the first chunk (chunk_idx=0).
    """
    try:
        results = collection.get(include=["metadatas"])
    except Exception:
        return {}

    slug_mtimes: dict[str, float] = {}
    for meta in results.get("metadatas") or []:
        if meta is None:
            continue
        slug = meta.get("slug")
        chunk_idx = meta.get("chunk_idx", 0)
        mtime = meta.get("mtime")
        if slug and chunk_idx == 0 and mtime is not None:
            slug_mtimes[slug] = float(mtime)
    return slug_mtimes


def _delete_slug_chunks(collection, slug: str) -> None:
    """Remove all ChromaDB documents belonging to a given slug."""
    collection.delete(where={"slug": slug})


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

def build_index(index: dict[str, dict[str, Any]], force: bool = False) -> None:
    """
    Chunk, embed, and upsert notes into ChromaDB.

    - If force=True, re-index every note regardless of mtime.
    - Otherwise, skip notes whose mtime matches what's already stored.
    """
    collection = _get_collection()

    # Load currently indexed mtimes (skip on force rebuild).
    indexed_mtimes: dict[str, float] = {} if force else _get_indexed_mtimes(collection)

    slugs_to_index: list[str] = []
    for slug, note in index.items():
        current_mtime = float(note.get("mtime") or 0.0)
        stored_mtime = indexed_mtimes.get(slug)
        if stored_mtime is None or abs(current_mtime - stored_mtime) > 0.001:
            slugs_to_index.append(slug)

    if not slugs_to_index:
        print("ChromaDB index is up to date — nothing to re-index.", flush=True)
        return

    print(
        f"Indexing {len(slugs_to_index)} note(s) "
        f"({len(index) - len(slugs_to_index)} unchanged)…",
        flush=True,
    )

    # Process in batches to keep memory manageable.
    BATCH = 50
    total_chunks = 0

    for batch_start in range(0, len(slugs_to_index), BATCH):
        batch_slugs = slugs_to_index[batch_start : batch_start + BATCH]

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for slug in batch_slugs:
            note = index[slug]
            body = note.get("body", "")
            title = note.get("title", slug)
            mtime = float(note.get("mtime") or 0.0)

            # Remove stale chunks for this slug before re-inserting.
            _delete_slug_chunks(collection, slug)

            chunks = chunk_note(body)
            if not chunks:
                # Insert a placeholder so the note is still findable.
                chunks = [f"{title} (no content)"]

            for idx, chunk in enumerate(chunks):
                doc_id = f"{slug}_{idx}"
                ids.append(doc_id)
                documents.append(chunk)
                metadatas.append({
                    "slug": slug,
                    "title": title,
                    "mtime": mtime,
                    "chunk_idx": idx,
                })

        if not ids:
            continue

        # Embed the batch.
        embeddings = embed_texts(documents)

        # Upsert into ChromaDB.
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        total_chunks += len(ids)
        print(
            f"  Upserted {len(ids)} chunk(s) for "
            f"slugs {batch_start + 1}–{batch_start + len(batch_slugs)} "
            f"/ {len(slugs_to_index)}",
            flush=True,
        )

    print(f"Done. Total chunks in this run: {total_chunks}", flush=True)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query(question: str, top_k: int = 5) -> list[dict]:
    """
    Embed *question* and retrieve the top_k most relevant chunks from ChromaDB.

    Returns a list of dicts:
        {
            "chunk_text": str,
            "note_slug":  str,
            "note_title": str,
            "score":      float,   # cosine similarity in [0, 1]
        }

    Raises RuntimeError if the ChromaDB directory doesn't exist yet.
    """
    if not CHROMA_DIR.exists():
        raise RuntimeError(
            "ChromaDB index not found. "
            "Run `python rag.py --vault <path> --build` first."
        )

    collection = _get_collection()

    if collection.count() == 0:
        raise RuntimeError(
            "ChromaDB collection is empty. "
            "Run `python rag.py --vault <path> --build` first."
        )

    # Embed the question.
    [q_vector] = embed_texts([question])

    results = collection.query(
        query_embeddings=[q_vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    output: list[dict] = []
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        # ChromaDB cosine distance ∈ [0, 2]; similarity = 1 - dist/2.
        score = round(1.0 - dist / 2.0, 4)
        output.append({
            "chunk_text": doc,
            "note_slug": meta.get("slug", ""),
            "note_title": meta.get("title", ""),
            "score": score,
        })

    return output


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build or query the Obsidian Navigator RAG vector index."
    )
    parser.add_argument(
        "--vault",
        default=os.environ.get("OBSIDIAN_VAULT", str(Path.home() / "obsidian")),
        help="Path to Obsidian vault (default: $OBSIDIAN_VAULT or ~/obsidian)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build (or update) the ChromaDB vector index from index.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full re-index even for unchanged files (use with --build).",
    )
    parser.add_argument(
        "--query",
        metavar="QUESTION",
        help="Run a test query against the index and print results.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve (default: 5).",
    )
    args = parser.parse_args()

    if not args.build and not args.query:
        parser.print_help()
        sys.exit(0)

    if args.build:
        if not INDEX_PATH.exists():
            print(
                f"Error: {INDEX_PATH} not found. Run indexer.py first.",
                file=sys.stderr,
            )
            sys.exit(1)

        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)

        print(f"Loaded {len(index)} notes from {INDEX_PATH}")
        build_index(index, force=args.force)

    if args.query:
        try:
            hits = query(args.query, top_k=args.top_k)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"\nTop {len(hits)} result(s) for: {args.query!r}\n")
        for i, hit in enumerate(hits, 1):
            print(
                f"[{i}] {hit['note_title']} (slug={hit['note_slug']}, "
                f"score={hit['score']:.4f})"
            )
            excerpt = hit["chunk_text"][:200].replace("\n", " ")
            print(f"    {excerpt}…\n")


if __name__ == "__main__":
    main()
