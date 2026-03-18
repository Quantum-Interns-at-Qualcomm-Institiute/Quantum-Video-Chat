#!/usr/bin/env bash
# start.sh — Start Quantum Video Chat processes
# Usage: bash start.sh <client|server>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
MAX_WAIT=60

# --- Colour helpers ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}[qvc]${NC} $*"; }
ok()   { echo -e "${GREEN}[qvc]${NC} $*"; }
warn() { echo -e "${YELLOW}[qvc]${NC} $*"; }
err()  { echo -e "${RED}[qvc]${NC} $*" >&2; }

usage() {
    echo -e "Usage: ${YELLOW}bash start.sh <client|server>${NC}"
    echo "  client  — Start browser frontend + Python middleware"
    echo "  server  — Start Python backend server + admin dashboard"
    exit 1
}

[[ $# -eq 1 ]] || usage
MODE="$1"

# --- Find the lowest free TCP port at or above $1 ---
find_free_port() {
    python3 - "$1" <<'EOF'
import socket, sys
port = int(sys.argv[1])
while True:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind(('', port))
        s.close()
        print(port)
        break
    except OSError:
        port += 1
EOF
}

# --- Kill all background children on exit ---
PIDS=()
_CLEANUP_DONE=false
cleanup() {
    # Guard against double-invocation (EXIT fires after INT on bash 3.2/macOS).
    if $_CLEANUP_DONE; then return; fi
    _CLEANUP_DONE=true
    trap '' EXIT INT TERM
    log "Shutting down..."
    # ${#PIDS[@]} is safe on empty arrays in all bash versions; ${PIDS[@]}
    # raises nounset on bash 3.2 (macOS) when the array is empty.
    if [[ ${#PIDS[@]} -gt 0 ]]; then
        for pid in "${PIDS[@]}"; do
            kill "$pid" 2>/dev/null || true
        done
    fi
    wait 2>/dev/null || true
    ok "Done."
}
trap cleanup EXIT INT TERM

# --- Launch a subprocess with prefixed output ---
# The while-loop reader runs in a bash subshell created by the pipe; we clear
# its inherited traps so the parent's cleanup() is not called again when the
# subshell exits.
run_prefixed() {
    local label="$1"; shift
    "$@" 2>&1 | ( trap '' EXIT INT TERM; while IFS= read -r line; do
        echo -e "${CYAN}[$label]${NC} $line"
    done ) &
    PIDS+=($!)
}

# =============================================================================
start_client() {
    log "Checking prerequisites..."
    command -v npm    >/dev/null 2>&1 || { err "npm not found on PATH"; exit 1; }
    command -v curl   >/dev/null 2>&1 || { err "curl not found on PATH"; exit 1; }
    [[ -f "$ROOT/frontend/node_modules/.bin/webpack" ]] || {
        err "Frontend dependencies missing. Run: cd frontend && npm install"
        exit 1
    }

    RENDERER_PORT=$(find_free_port "${PORT:-1212}")
    if [[ "$RENDERER_PORT" != "${PORT:-1212}" ]]; then
        warn "Port ${PORT:-1212} in use — using $RENDERER_PORT for renderer"
    fi
    export PORT="$RENDERER_PORT"

    MIDDLEWARE_PORT=$(find_free_port "${MIDDLEWARE_PORT:-5001}")
    if [[ "$MIDDLEWARE_PORT" != "${MIDDLEWARE_PORT:-5001}" ]]; then
        warn "Middleware port 5001 in use — using $MIDDLEWARE_PORT"
    fi

    log "Starting Python middleware on port $MIDDLEWARE_PORT..."
    run_prefixed "middleware" python3 "$ROOT/middleware/client.py" --port "$MIDDLEWARE_PORT"

    log "Waiting for middleware at http://localhost:$MIDDLEWARE_PORT ..."
    ELAPSED=0
    until curl -sf "http://localhost:$MIDDLEWARE_PORT/socket.io/?EIO=4&transport=polling" >/dev/null 2>&1; do
        sleep 1
        (( ELAPSED++ ))
        if (( ELAPSED >= MAX_WAIT )); then
            err "Middleware did not start within ${MAX_WAIT}s — check [middleware] output above."
            exit 1
        fi
    done
    ok "Middleware ready (${ELAPSED}s)."

    log "Starting webpack renderer on port $RENDERER_PORT..."
    run_prefixed "renderer" bash -c "cd '$ROOT/frontend' && BROWSER_ONLY=true PORT=$RENDERER_PORT MIDDLEWARE_PORT=$MIDDLEWARE_PORT npm run start:renderer"

    log "Waiting for renderer at http://localhost:$RENDERER_PORT ..."
    ELAPSED=0
    until curl -sf "http://localhost:$RENDERER_PORT" >/dev/null 2>&1; do
        sleep 1
        (( ELAPSED++ ))
        if (( ELAPSED >= MAX_WAIT )); then
            err "Renderer did not start within ${MAX_WAIT}s — check [renderer] output above."
            exit 1
        fi
    done
    ok "Client ready (${ELAPSED}s)."
    ok "Client app: http://localhost:$RENDERER_PORT"

    # Open the client app in the default browser (macOS/Linux).
    if command -v open >/dev/null 2>&1; then
        open "http://localhost:$RENDERER_PORT"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:$RENDERER_PORT" &
    fi

    wait "${PIDS[@]}"   # blocks until renderer exits; Ctrl+C triggers cleanup
}

# =============================================================================
start_server() {
    log "Checking prerequisites..."
    command -v python3 >/dev/null 2>&1 || { err "python3 not found on PATH"; exit 1; }
    command -v curl   >/dev/null 2>&1 || { err "curl not found on PATH"; exit 1; }
    [[ -f "$ROOT/server/main.py" ]] || { err "server/main.py not found"; exit 1; }

    # Resolve the IP the server will bind to — mirrors shared/config.py get_local_ip().
    # If QVC_LOCAL_IP is already set by the caller, honour it; otherwise auto-detect.
    if [[ -z "${QVC_LOCAL_IP:-}" ]]; then
        QVC_LOCAL_IP=$(python3 - <<'EOF'
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0])
    s.close()
except Exception:
    print('127.0.0.1')
EOF
)
    fi
    export QVC_LOCAL_IP

    # QVC_SERVER_REST_PORT and QVC_SERVER_WS_PORT are read by shared/config.py
    REST_PORT=$(find_free_port "${QVC_SERVER_REST_PORT:-5050}")
    if [[ "$REST_PORT" != "${QVC_SERVER_REST_PORT:-5050}" ]]; then
        warn "Port ${QVC_SERVER_REST_PORT:-5050} in use — using $REST_PORT for REST API"
    fi
    export QVC_SERVER_REST_PORT="$REST_PORT"

    WS_PORT=$(find_free_port "${QVC_SERVER_WS_PORT:-3000}")
    if [[ "$WS_PORT" != "${QVC_SERVER_WS_PORT:-3000}" ]]; then
        warn "Port ${QVC_SERVER_WS_PORT:-3000} in use — using $WS_PORT for WebSocket API"
    fi
    export QVC_SERVER_WS_PORT="$WS_PORT"

    log "Starting Python backend server (REST :$REST_PORT, WebSocket :$WS_PORT) on $QVC_LOCAL_IP..."
    run_prefixed "server" bash -c "cd '$ROOT/server' && python3 main.py"

    log "Waiting for server at http://$QVC_LOCAL_IP:$REST_PORT ..."
    ELAPSED=0
    until curl -sf "http://$QVC_LOCAL_IP:$REST_PORT/admin/status" >/dev/null 2>&1; do
        sleep 1
        (( ELAPSED++ ))
        if (( ELAPSED >= MAX_WAIT )); then
            err "Server did not start within ${MAX_WAIT}s — check [server] output above."
            exit 1
        fi
    done
    ok "Server ready (${ELAPSED}s)."
    ok "Admin dashboard: http://$QVC_LOCAL_IP:$REST_PORT/dashboard"

    # Open the dashboard in the default browser (macOS/Linux).
    if command -v open >/dev/null 2>&1; then
        open "http://$QVC_LOCAL_IP:$REST_PORT/dashboard"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://$QVC_LOCAL_IP:$REST_PORT/dashboard" &
    fi

    wait "${PIDS[@]}"
}

# =============================================================================
case "$MODE" in
    client) start_client ;;
    server) start_server ;;
    *)      err "Unknown mode: '$MODE'"; usage ;;
esac
