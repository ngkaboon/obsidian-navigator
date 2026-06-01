#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"
LOG_FILE="$SCRIPT_DIR/server.log"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Server is already running (PID $PID). Use stop_server.sh to stop it first."
        exit 1
    else
        echo "Stale PID file found (process $PID not running). Removing."
        rm -f "$PID_FILE"
    fi
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Start server in background with nohup
nohup "$SCRIPT_DIR/venv/bin/uvicorn" server:app --reload --port 8000 \
    >> "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

echo "Server started (PID $SERVER_PID). Logs: $LOG_FILE"
