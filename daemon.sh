#!/usr/bin/env bash
# daemon.sh — Control daemon for the uvicorn server.
# Usage: ./daemon.sh &
# Control by writing "start" or "stop" to .cmd

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CMD_FILE="$DIR/.cmd"
STATUS_FILE="$DIR/.status"
PID_FILE="$DIR/server.pid"
LOG_FILE="$DIR/daemon.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

is_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

start_server() {
    if is_running; then
        log "START requested but server is already running (PID $(cat "$PID_FILE"))"
        echo "running" > "$STATUS_FILE"
        return
    fi
    log "Starting uvicorn server..."
    nohup "$DIR/venv/bin/uvicorn" server:app --port 8000 --host 0.0.0.0 \
        >> "$DIR/server.log" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    echo "running" > "$STATUS_FILE"
    log "Server started with PID $pid"
}

stop_server() {
    if ! is_running; then
        log "STOP requested but server is not running"
        echo "stopped" > "$STATUS_FILE"
        rm -f "$PID_FILE"
        return
    fi
    local pid
    pid=$(cat "$PID_FILE")
    log "Stopping server (PID $pid)..."
    kill "$pid" 2>/dev/null
    # Wait up to 5 seconds for graceful shutdown
    local waited=0
    while kill -0 "$pid" 2>/dev/null && (( waited < 5 )); do
        sleep 1
        (( waited++ ))
    done
    if kill -0 "$pid" 2>/dev/null; then
        log "Server did not stop gracefully, force-killing PID $pid"
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PID_FILE"
    echo "stopped" > "$STATUS_FILE"
    log "Server stopped"
}

# Initialise files on startup
touch "$CMD_FILE"
if is_running; then
    echo "running" > "$STATUS_FILE"
    log "Daemon started — server already running (PID $(cat "$PID_FILE"))"
else
    echo "stopped" > "$STATUS_FILE"
    log "Daemon started — server is not running"
fi

# Main poll loop
while true; do
    cmd=$(cat "$CMD_FILE" 2>/dev/null | tr -d '[:space:]')

    case "$cmd" in
        start)
            start_server
            echo "" > "$CMD_FILE"
            ;;
        stop)
            stop_server
            echo "" > "$CMD_FILE"
            ;;
    esac

    # Keep .status accurate regardless of command
    if is_running; then
        echo "running" > "$STATUS_FILE"
    else
        echo "stopped" > "$STATUS_FILE"
        rm -f "$PID_FILE"
    fi

    sleep 2
done
