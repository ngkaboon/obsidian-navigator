#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VAULT="${1:-$HOME/Documents/Kevin Notes}"

source venv/bin/activate
echo "Indexing vault: $VAULT"
python indexer.py --vault "$VAULT"
echo "Rebuilding vector index..."
python rag.py --vault "$VAULT" --build
echo "Done. Reload the app to see updated notes."
