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
echo "Restarting server..."
if [ -f "$SCRIPT_DIR/server.pid" ]; then
  kill "$(cat "$SCRIPT_DIR/server.pid")" 2>/dev/null || true
  sleep 1
fi
nohup uvicorn server:app --port 8000 > "$SCRIPT_DIR/server.log" 2>&1 &
echo $! > "$SCRIPT_DIR/server.pid"
echo "Done. Server restarted (PID $(cat "$SCRIPT_DIR/server.pid")). Reload the app to see updated notes."
