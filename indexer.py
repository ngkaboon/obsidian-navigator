"""
indexer.py — Vault crawler, wikilink parser, and index builder for Obsidian Navigator.

Usage:
    python indexer.py --vault /path/to/obsidian/vault

Falls back to OBSIDIAN_VAULT env var, then ~/obsidian.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import frontmatter


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def make_slug(filepath: str) -> str:
    """Convert a file path to a URL-safe slug."""
    name = os.path.splitext(os.path.basename(filepath))[0]
    return name.lower().replace(" ", "-")


def resolve_wikilink(raw: str, slug_map: dict, title_map: dict) -> str | None:
    """
    Try to resolve a raw wikilink target to a slug.

    1. Exact slug match (lowercased + hyphenated)
    2. Case-insensitive title match
    3. Alias match
    Returns None when no match found.
    """
    candidate = raw.lower().replace(" ", "-")

    # 1. Exact slug match
    if candidate in slug_map:
        return candidate

    # 2. Case-insensitive title / alias match
    raw_lower = raw.lower()
    if raw_lower in title_map:
        return title_map[raw_lower]

    return None


# ---------------------------------------------------------------------------
# Wikilink extraction
# ---------------------------------------------------------------------------

# Matches [[Target]] and [[Target|Alias]] and [[Target#Heading]]
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def extract_wikilinks(body: str) -> list[str]:
    """Return a list of raw wikilink targets (before alias/heading stripping)."""
    return WIKILINK_RE.findall(body)


# ---------------------------------------------------------------------------
# Frontmatter parsing helpers
# ---------------------------------------------------------------------------

def normalize_tags(raw_tags) -> list[str]:
    """Ensure tags is always a list of strings."""
    if not raw_tags:
        return []
    if isinstance(raw_tags, str):
        # Some vaults use comma-separated or space-separated strings
        return [t.strip() for t in re.split(r"[,\s]+", raw_tags) if t.strip()]
    if isinstance(raw_tags, list):
        return [str(t).strip() for t in raw_tags if str(t).strip()]
    return []


def normalize_aliases(raw_aliases) -> list[str]:
    """Ensure aliases is always a list of strings."""
    if not raw_aliases:
        return []
    if isinstance(raw_aliases, str):
        return [raw_aliases.strip()]
    if isinstance(raw_aliases, list):
        return [str(a).strip() for a in raw_aliases if str(a).strip()]
    return []


# ---------------------------------------------------------------------------
# Main indexing logic
# ---------------------------------------------------------------------------

def scan_vault(vault_path: Path) -> dict:
    """
    Scan all .md files in vault_path and build a two-pass index.

    Pass 1: Parse every file, collect slugs, titles, aliases, raw wikilinks.
    Pass 2: Resolve raw wikilinks to slugs using the collected maps.

    Returns: { slug → { title, tags, aliases, body, links, path, mtime } }
    """
    md_files = list(vault_path.rglob("*.md"))

    if not md_files:
        print(f"Warning: no .md files found under {vault_path}", file=sys.stderr)

    # --- Pass 1: parse files -------------------------------------------------
    raw_index: dict[str, dict] = {}
    # slug → slug (identity, for fast lookup)
    slug_map: dict[str, str] = {}
    # lowercased title/alias → slug (for fuzzy resolution)
    title_map: dict[str, str] = {}

    for filepath in md_files:
        slug = make_slug(str(filepath))

        try:
            post = frontmatter.load(str(filepath))
        except Exception as exc:
            print(f"Warning: could not parse {filepath}: {exc}", file=sys.stderr)
            continue

        meta = post.metadata
        body = post.content

        title = meta.get("title") or os.path.splitext(os.path.basename(filepath))[0]
        tags = normalize_tags(meta.get("tags"))
        aliases = normalize_aliases(meta.get("aliases"))
        date = str(meta.get("date", "")) or ""
        mtime = os.path.getmtime(filepath)

        raw_links = extract_wikilinks(body)

        raw_index[slug] = {
            "title": title,
            "tags": tags,
            "aliases": aliases,
            "date": date,
            "body": body,
            "raw_links": raw_links,
            "path": str(filepath),
            "mtime": mtime,
        }

        slug_map[slug] = slug
        title_map[title.lower()] = slug
        for alias in aliases:
            title_map[alias.lower()] = slug

    # --- Pass 2: resolve wikilinks to slugs ----------------------------------
    index: dict[str, dict] = {}

    for slug, data in raw_index.items():
        resolved_links: list[dict] = []
        for raw in data["raw_links"]:
            resolved = resolve_wikilink(raw, slug_map, title_map)
            resolved_links.append({
                "raw": raw.strip(),
                "slug": resolved,  # None if unresolved
            })

        index[slug] = {
            "title": data["title"],
            "tags": data["tags"],
            "aliases": data["aliases"],
            "date": data["date"],
            "body": data["body"],
            "links": resolved_links,
            "path": data["path"],
            "mtime": data["mtime"],
        }

    return index


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Index an Obsidian vault into index.json"
    )
    parser.add_argument(
        "--vault",
        default=os.environ.get("OBSIDIAN_VAULT", str(Path.home() / "obsidian")),
        help="Path to Obsidian vault (default: $OBSIDIAN_VAULT or ~/obsidian)",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "index.json"),
        help="Output path for index.json (default: project root)",
    )
    args = parser.parse_args()

    vault_path = Path(args.vault).expanduser().resolve()
    if not vault_path.exists():
        print(f"Error: vault path does not exist: {vault_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Indexing vault: {vault_path}")
    index = scan_vault(vault_path)

    # --- Write index ---------------------------------------------------------
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # --- Summary -------------------------------------------------------------
    total_notes = len(index)
    total_links = sum(len(note["links"]) for note in index.values())
    all_tags: set[str] = set()
    for note in index.values():
        all_tags.update(note["tags"])

    print(f"Index written to: {output_path}")
    print(f"  Total notes : {total_notes}")
    print(f"  Total links : {total_links}")
    print(f"  Total tags  : {len(all_tags)}")


if __name__ == "__main__":
    main()
