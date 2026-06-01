#!/bin/bash
set -e

# ── Obsidian Second Brain Navigator — local setup & launch ──────────────────

VAULT=""
SKIP_RAG=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault)
      VAULT="$2"
      shift 2
      ;;
    --skip-rag)
      SKIP_RAG=true
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: ./setup.sh --vault /path/to/obsidian/vault [--skip-rag]"
      exit 1
      ;;
  esac
done

if [[ -z "$VAULT" ]]; then
  echo "ERROR: --vault is required."
  echo ""
  echo "Usage: ./setup.sh --vault /path/to/obsidian/vault [--skip-rag]"
  echo ""
  echo "  --vault <path>   Path to your Obsidian vault directory"
  echo "  --skip-rag       Skip building the vector index (faster startup, no LLM queries)"
  exit 1
fi

# Expand ~ in path
VAULT="${VAULT/#\~/$HOME}"

if [[ ! -d "$VAULT" ]]; then
  echo "ERROR: Vault directory not found: $VAULT"
  exit 1
fi

MD_COUNT=$(find "$VAULT" -name "*.md" | wc -l | tr -d ' ')
if [[ "$MD_COUNT" -eq 0 ]]; then
  echo "ERROR: No .md files found in vault: $VAULT"
  exit 1
fi

echo "=== Obsidian Second Brain Navigator ==="
echo "Vault: $VAULT ($MD_COUNT markdown files)"
echo ""

# ── Python venv ──────────────────────────────────────────────────────────────
cd "$SCRIPT_DIR"

if [[ ! -d "venv" ]]; then
  echo "[1/4] Creating Python virtual environment..."
  python3 -m venv venv
else
  echo "[1/4] Virtual environment already exists, skipping."
fi

echo "[2/4] Installing dependencies..."
source venv/bin/activate
pip install --quiet -r requirements.txt

# ── Index vault ───────────────────────────────────────────────────────────────
echo "[3/4] Indexing vault..."
python indexer.py --vault "$VAULT"

# ── Build vector index ────────────────────────────────────────────────────────
if [[ "$SKIP_RAG" == true ]]; then
  echo "[4/4] Skipping vector index build (--skip-rag). LLM queries will not work."
else
  echo "[4/4] Building vector index (this may take a minute on first run)..."
  python rag.py --vault "$VAULT" --build
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
echo "Open frontend/index.html in your browser"
echo ""
echo "Starting server on http://localhost:8000 ..."
echo ""
echo "For mobile access via Tailscale, run once in a separate terminal:"
echo "  tailscale serve --bg 8000"
echo "Then open https://<your-machine>.ts.net on your phone."
echo ""
uvicorn server:app --reload --port 8000
