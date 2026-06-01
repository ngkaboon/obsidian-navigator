#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found. Server may not be running."
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping server (PID $PID)..."
    kill "$PID"

    # Wait up to 5 seconds for graceful shutdown
    for i in $(seq 1 5); do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "Server stopped."
            rm -f "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    echo "Server did not stop gracefully. Force killing..."
    kill -9 "$PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "Server force-stopped."
else
    echo "Process $PID is not running. Removing stale PID file."
    rm -f "$PID_FILE"
fi
