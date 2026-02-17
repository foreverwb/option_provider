#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Options Provider — Quick Start Script
# ──────────────────────────────────────────────────────────────────────────────
#
#   ./start.sh                  Interactive menu (first time auto-setup)
#   ./start.sh serve            Start API server
#   ./start.sh dev              Dev mode (auto-reload)
#   ./start.sh test             Run all tests
#   ./start.sh greeks gex AAPL  Direct Greeks query
#   ./start.sh vol skew SPY     Direct Vol query
#   ./start.sh full TSLA        Full analysis
#   ./start.sh health           Check server health
#   ./start.sh setup            Install dependencies + init .env
#   ./start.sh stop             Stop running server
#   ./start.sh logs             Tail server logs
#   ./start.sh clean            Clean caches
#   ./start.sh help             Show help
#
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Project paths ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
PID_FILE=".server.pid"
LOG_FILE=".server.log"
ENV_FILE=".env"

# ── Defaults (overridable via env or .env) ───────────────────────────────
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-9988}"
WORKERS="${WORKERS:-1}"
LOG_LEVEL="${LOG_LEVEL:-info}"
PYTHON="${PYTHON:-}"

# ── Colors ───────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()    { echo -e "${CYAN}▸${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
error()   { echo -e "${RED}✗${NC} $*" >&2; }

# ── Load .env ────────────────────────────────────────────────────────────
load_env() {
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    fi
}

# ── Detect Python ────────────────────────────────────────────────────────
find_python() {
    if [[ -n "$PYTHON" ]]; then
        echo "$PYTHON"
        return
    fi

    # Prefer venv python
    if [[ -f "$VENV_DIR/bin/python" ]]; then
        echo "$VENV_DIR/bin/python"
        return
    fi

    # Fallback to system python
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return
        fi
    done

    error "Python not found. Please install Python 3.10+."
    exit 1
}

# ── Check prerequisites ─────────────────────────────────────────────────
check_python_version() {
    local py="$1"
    local version
    version=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    local major minor
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)
    if [[ "$major" -lt 3 ]] || { [[ "$major" -eq 3 ]] && [[ "$minor" -lt 10 ]]; }; then
        error "Python 3.10+ required, found $version"
        exit 1
    fi
    echo "$version"
}

# ══════════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════════

# ── setup ────────────────────────────────────────────────────────────────
cmd_setup() {
    info "Setting up Options Provider ..."
    echo ""

    local py
    py=$(find_python)
    local ver
    ver=$(check_python_version "$py")
    success "Python $ver found ($py)"

    # Create venv if not exists
    if [[ ! -d "$VENV_DIR" ]]; then
        info "Creating virtual environment ..."
        "$py" -m venv "$VENV_DIR"
        success "Virtual environment created: $VENV_DIR/"
    else
        success "Virtual environment exists: $VENV_DIR/"
    fi

    # Use venv python from here
    py="$VENV_DIR/bin/python"

    # Install dependencies
    info "Installing dependencies ..."
    "$py" -m pip install --upgrade pip -q 2>/dev/null
    "$py" -m pip install -r requirements.txt -q
    success "Dependencies installed"

    # Init .env
    if [[ ! -f "$ENV_FILE" ]]; then
        cp .env.example "$ENV_FILE"
        warn "Created ${BOLD}.env${NC} from template — please edit it with your API tokens:"
        echo ""
        echo -e "    ${DIM}vim .env${NC}"
        echo ""
    else
        success ".env file exists"
    fi

    echo ""
    success "Setup complete! Start with: ${BOLD}./start.sh serve${NC}"
    echo ""
}

# ── serve ────────────────────────────────────────────────────────────────
cmd_serve() {
    load_env
    local py
    py=$(find_python)

    local orats_display
    if [[ -n "${ORATS_TOKEN:-}" ]] && [[ "${ORATS_TOKEN}" != "your_orats_token_here" ]]; then
        orats_display="***${ORATS_TOKEN: -4}"
    else
        orats_display="${YELLOW}(not set)${NC}"
    fi

    echo ""
    echo -e "  ${BOLD}${CYAN}Options Provider API${NC}"
    echo -e "  ─────────────────────────────────────"
    echo -e "  Server     ${BOLD}http://${HOST}:${PORT}${NC}"
    echo -e "  Docs       ${DIM}http://${HOST}:${PORT}/docs${NC}"
    echo -e "  BRIDGE_URL ${DIM}${BRIDGE_URL:-http://localhost:8668}${NC}"
    echo -e "  ORATS_TOKEN${DIM} ${orats_display}${NC}"
    echo -e "  Workers    ${WORKERS}"
    echo ""

    export PYTHONPATH="$SCRIPT_DIR"
    exec "$py" -m uvicorn api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --no-access-log
}

# ── dev ──────────────────────────────────────────────────────────────────
cmd_dev() {
    load_env
    local py
    py=$(find_python)

    echo ""
    echo -e "  ${BOLD}${YELLOW}Options Provider API (DEV MODE)${NC}"
    echo -e "  ─────────────────────────────────────"
    echo -e "  Server     ${BOLD}http://${HOST}:${PORT}${NC}"
    echo -e "  Docs       ${DIM}http://${HOST}:${PORT}/docs${NC}"
    echo -e "  Auto-reload ${GREEN}enabled${NC}"
    echo ""

    export PYTHONPATH="$SCRIPT_DIR"
    exec "$py" -m uvicorn api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        --log-level debug \
        --no-access-log
}

# ── start (background) ──────────────────────────────────────────────────
cmd_start_bg() {
    load_env
    local py
    py=$(find_python)

    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        warn "Server already running (PID $(cat "$PID_FILE")). Use ${BOLD}./start.sh stop${NC} first."
        return 1
    fi

    info "Starting server in background on port $PORT ..."
    export PYTHONPATH="$SCRIPT_DIR"
    nohup "$py" -m uvicorn api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --no-access-log \
        > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    # Wait briefly and verify
    sleep 1
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        success "Server started (PID $(cat "$PID_FILE"))"
        info "Logs: ${BOLD}./start.sh logs${NC}"
        info "Stop: ${BOLD}./start.sh stop${NC}"
    else
        error "Server failed to start. Check logs: cat $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# ── stop ─────────────────────────────────────────────────────────────────
cmd_stop() {
    if [[ ! -f "$PID_FILE" ]]; then
        warn "No PID file found. Server may not be running."
        # Try to kill by port anyway
        local pid
        pid=$(lsof -ti :"$PORT" 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            info "Found process on port $PORT (PID $pid), stopping ..."
            kill "$pid" 2>/dev/null && success "Stopped" || error "Failed to stop PID $pid"
        fi
        return 0
    fi

    local pid
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        info "Stopping server (PID $pid) ..."
        kill "$pid"
        sleep 1
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        success "Server stopped"
    else
        warn "Process $pid not running"
    fi
    rm -f "$PID_FILE"
}

# ── logs ─────────────────────────────────────────────────────────────────
cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        warn "No log file found. Start the server with: ${BOLD}./start.sh start-bg${NC}"
        return 1
    fi
    info "Tailing $LOG_FILE (Ctrl+C to exit) ..."
    tail -f "$LOG_FILE"
}

# ── status ───────────────────────────────────────────────────────────────
cmd_status() {
    load_env

    echo ""
    echo -e "  ${BOLD}Server Status${NC}"
    echo -e "  ─────────────────────────────────────"

    # Check PID file
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "  Process  ${GREEN}running${NC} (PID $(cat "$PID_FILE"))"
    else
        echo -e "  Process  ${RED}not running${NC}"
        rm -f "$PID_FILE" 2>/dev/null
    fi

    # Check HTTP health
    if command -v curl &>/dev/null; then
        local resp
        resp=$(curl -s -m 3 -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null) || resp="000"
        if [[ "$resp" == "200" ]]; then
            echo -e "  Health   ${GREEN}OK${NC} (HTTP 200)"
        else
            echo -e "  Health   ${RED}unreachable${NC}"
        fi
    fi

    # Env check
    if [[ -n "${ORATS_TOKEN:-}" ]] && [[ "${ORATS_TOKEN}" != "your_orats_token_here" ]]; then
        echo -e "  ORATS    ${GREEN}configured${NC}"
    else
        echo -e "  ORATS    ${YELLOW}not configured${NC}"
    fi

    echo ""
}

# ── test ─────────────────────────────────────────────────────────────────
cmd_test() {
    local py
    py=$(find_python)
    shift 2>/dev/null || true

    info "Running tests ..."
    export PYTHONPATH="$SCRIPT_DIR"
    "$py" -m pytest tests/ -v --tb=short "$@"
}

# ── health ───────────────────────────────────────────────────────────────
cmd_health() {
    load_env
    local url="http://localhost:${PORT}/health"
    info "Checking $url ..."

    if command -v curl &>/dev/null; then
        local resp
        resp=$(curl -s "$url" 2>/dev/null)
        if [[ $? -eq 0 ]]; then
            success "Server healthy: $resp"
        else
            error "Server unreachable at $url"
            exit 1
        fi
    else
        local py
        py=$(find_python)
        "$py" cli.py health --port "$PORT"
    fi
}

# ── greeks / vol / full (delegate to cli.py) ─────────────────────────────
cmd_cli_delegate() {
    load_env
    local py
    py=$(find_python)
    export PYTHONPATH="$SCRIPT_DIR"
    "$py" cli.py "$@"
}

# ── clean ────────────────────────────────────────────────────────────────
cmd_clean() {
    info "Cleaning caches and temp files ..."
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -name '*.pyc' -delete 2>/dev/null || true
    rm -rf .coverage htmlcov/ .mypy_cache/
    rm -f "$LOG_FILE"
    success "Cleaned"
}

# ── help ─────────────────────────────────────────────────────────────────
cmd_help() {
    echo ""
    echo -e "  ${BOLD}${CYAN}Options Provider${NC} — Quick Start Script"
    echo ""
    echo -e "  ${BOLD}Usage:${NC} ./start.sh <command> [args]"
    echo ""
    echo -e "  ${BOLD}Server:${NC}"
    echo -e "    ${GREEN}serve${NC}                      Start API server (foreground)"
    echo -e "    ${GREEN}dev${NC}                        Dev mode with auto-reload"
    echo -e "    ${GREEN}start-bg${NC}                   Start server in background"
    echo -e "    ${GREEN}stop${NC}                       Stop background server"
    echo -e "    ${GREEN}status${NC}                     Show server status"
    echo -e "    ${GREEN}logs${NC}                       Tail server logs"
    echo -e "    ${GREEN}health${NC}                     Check server health"
    echo ""
    echo -e "  ${BOLD}Testing:${NC}"
    echo -e "    ${GREEN}test${NC}                       Run all tests"
    echo -e "    ${GREEN}test${NC} -k greeks             Run filtered tests"
    echo ""
    echo -e "  ${BOLD}Offline Queries:${NC}"
    echo -e "    ${GREEN}greeks${NC} gex AAPL            Greeks exposure command"
    echo -e "    ${GREEN}vol${NC}    skew SPY             Volatility analysis command"
    echo -e "    ${GREEN}full${NC}   TSLA                 Full analysis"
    echo ""
    echo -e "  ${BOLD}Setup:${NC}"
    echo -e "    ${GREEN}setup${NC}                      Install deps + init .env"
    echo -e "    ${GREEN}clean${NC}                      Clean caches and temp files"
    echo ""
    echo -e "  ${BOLD}Environment:${NC}"
    echo -e "    PORT=${DIM}9988${NC}   HOST=${DIM}0.0.0.0${NC}   WORKERS=${DIM}1${NC}   LOG_LEVEL=${DIM}info${NC}"
    echo ""
    echo -e "  ${BOLD}Examples:${NC}"
    echo -e "    ${DIM}./start.sh setup${NC}                 First-time setup"
    echo -e "    ${DIM}./start.sh serve${NC}                 Start server"
    echo -e "    ${DIM}PORT=9000 ./start.sh dev${NC}         Dev on port 9000"
    echo -e "    ${DIM}./start.sh greeks gex AAPL${NC}       Query GEX"
    echo -e "    ${DIM}./start.sh start-bg && ./start.sh logs${NC}"
    echo ""
}

# ── Interactive menu ─────────────────────────────────────────────────────
cmd_menu() {
    echo ""
    echo -e "  ${BOLD}${CYAN}Options Provider${NC}"
    echo ""
    echo -e "  Select an action:"
    echo ""
    echo -e "    ${BOLD}1${NC})  Start server         ${DIM}(foreground)${NC}"
    echo -e "    ${BOLD}2${NC})  Start dev mode        ${DIM}(auto-reload)${NC}"
    echo -e "    ${BOLD}3${NC})  Start background      ${DIM}(daemon)${NC}"
    echo -e "    ${BOLD}4${NC})  Run tests"
    echo -e "    ${BOLD}5${NC})  Setup / Install"
    echo -e "    ${BOLD}6${NC})  Server status"
    echo -e "    ${BOLD}7${NC})  Show help"
    echo -e "    ${BOLD}0${NC})  Exit"
    echo ""
    read -rp "  > " choice

    case "$choice" in
        1) cmd_serve ;;
        2) cmd_dev ;;
        3) cmd_start_bg ;;
        4) cmd_test ;;
        5) cmd_setup ;;
        6) cmd_status ;;
        7) cmd_help ;;
        0) exit 0 ;;
        *) warn "Invalid choice"; cmd_menu ;;
    esac
}

# ══════════════════════════════════════════════════════════════════════════
# Main dispatch
# ══════════════════════════════════════════════════════════════════════════

# Auto-setup check: if no venv and no system packages, prompt setup
auto_setup_check() {
    local py
    py=$(find_python)
    if ! "$py" -c "import fastapi" 2>/dev/null; then
        warn "Dependencies not installed."
        echo ""
        read -rp "  Run setup now? [Y/n] " answer
        case "${answer:-Y}" in
            [Yy]*|"") cmd_setup ;;
            *) info "Skipped. Run ${BOLD}./start.sh setup${NC} manually." ;;
        esac
    fi
}

main() {
    local cmd="${1:-}"

    case "$cmd" in
        serve|s|run)       cmd_serve ;;
        dev|d)             cmd_dev ;;
        start-bg|bg)       cmd_start_bg ;;
        stop)              cmd_stop ;;
        status|st)         cmd_status ;;
        logs|log)          cmd_logs ;;
        test|t)            shift; cmd_test "$@" ;;
        health|h)          cmd_health ;;
        setup|install)     cmd_setup ;;
        clean)             cmd_clean ;;
        greeks|g|vol|v|full|f|routes)
                           cmd_cli_delegate "$@" ;;
        help|--help|-h)    cmd_help ;;
        "")
            auto_setup_check
            cmd_menu
            ;;
        *)
            error "Unknown command: $cmd"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
