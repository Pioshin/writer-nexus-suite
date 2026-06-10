#!/bin/bash

# writer-nexus-suite Unified Start Script
# Launches: BKA, Kronk, NOOS Hub, BKA worker, KRONK worker, StoryForge worker (optional)

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"

mkdir -p "$LOG_DIR"

echo "--- Starting Writer-Nexus Suite ---"
echo "Root Dir: $ROOT_DIR"

# GLOBAL VENV CONFIGURATION
# User provided: source ~/.venv/workspace/bin/activate
GLOBAL_PYTHON="$HOME/.venv/workspace/bin/python"

if [ ! -f "$GLOBAL_PYTHON" ]; then
    echo "WARNING: Global Python not found at $GLOBAL_PYTHON"
    echo "Falling back to system 'python3' (might miss dependencies!)"
    GLOBAL_PYTHON="python3"
else
    echo "Using Global Python Environment: $GLOBAL_PYTHON"
fi

# 1. Start BKA (Port 8008)
echo "[1/2] Starting BKA on port 8008..."
cd "$ROOT_DIR/bka"

# Clear port 8008
fuser -k 8008/tcp 2>/dev/null
nohup "$GLOBAL_PYTHON" -m uvicorn backend.main:app --host 0.0.0.0 --port 8008 > "$LOG_DIR/bka.log" 2>&1 &
BKA_PID=$!
echo "BKA started (PID: $BKA_PID). Logs: $LOG_DIR/bka.log"

# 2. Start Kronk (Port 5000)
echo "[2/2] Starting Kronk on port 5000..."
cd "$ROOT_DIR/kronk"

# Clear port 5000
fuser -k 5000/tcp 2>/dev/null
nohup "$GLOBAL_PYTHON" app.py > "$LOG_DIR/kronk.log" 2>&1 &
KRONK_PID=$!
echo "Kronk started (PID: $KRONK_PID). Logs: $LOG_DIR/kronk.log"

# NOOS Hub configuration
NOOS_DIR="$(cd "$ROOT_DIR/../Writers_Nexus/NOOS" && pwd)"
WORKERS_DIR="$(cd "$ROOT_DIR/../Writers_Nexus" && pwd)"

if [ ! -f "$NOOS_DIR/.env" ]; then
    echo "WARNING: $NOOS_DIR/.env not found — NOOS Hub and workers will NOT start."
    echo "Create it with NOOS_JWT_SECRET and token vars, then re-run."
else
    # Load NOOS env vars (NOOS_JWT_SECRET, NOOS_APP_TOKEN, NOOS_WORKER_*_TOKEN)
    set -a && source "$NOOS_DIR/.env" && set +a

    # 3. Start NOOS Hub (Port 9090)
    echo "[3/5] Starting NOOS Hub on port 9090..."
    fuser -k 9090/tcp 2>/dev/null
    cd "$NOOS_DIR"
    nohup .venv/bin/uvicorn noos.main:app --host 0.0.0.0 --port 9090 > "$LOG_DIR/noos.log" 2>&1 &
    NOOS_PID=$!
    echo "NOOS Hub started (PID: $NOOS_PID). Logs: $LOG_DIR/noos.log"

    # Give NOOS time to initialize its DB before workers connect
    sleep 3

    # 4. Start BKA Worker
    echo "[4/6] Starting BKA Worker..."
    cd "$WORKERS_DIR"
    NOOS_HUB_URL=http://127.0.0.1:9090 \
    NOOS_WORKER_TOKEN="$NOOS_WORKER_BKA_TOKEN" \
    BKA_URL=http://127.0.0.1:8008 \
    KRONK_URL=http://127.0.0.1:5000 \
    nohup "$GLOBAL_PYTHON" -m workers.bka.main > "$LOG_DIR/worker_bka.log" 2>&1 &
    WORKER_BKA_PID=$!
    echo "BKA Worker started (PID: $WORKER_BKA_PID). Logs: $LOG_DIR/worker_bka.log"

    # 5. Start KRONK Worker
    echo "[5/6] Starting KRONK Worker..."
    NOOS_HUB_URL=http://127.0.0.1:9090 \
    NOOS_WORKER_TOKEN="$NOOS_WORKER_KRONK_TOKEN" \
    KRONK_URL=http://127.0.0.1:5000 \
    nohup "$GLOBAL_PYTHON" -m workers.kronk.main > "$LOG_DIR/worker_kronk.log" 2>&1 &
    WORKER_KRONK_PID=$!
    echo "KRONK Worker started (PID: $WORKER_KRONK_PID). Logs: $LOG_DIR/worker_kronk.log"

    # 6. Start StoryForge Worker (only if SF_PASSWORD is set)
    if [ -n "$SF_PASSWORD" ] && [ -n "$NOOS_WORKER_SF_TOKEN" ]; then
        echo "[6/6] Starting StoryForge Worker..."
        NOOS_HUB_URL=http://127.0.0.1:9090 \
        NOOS_WORKER_TOKEN="$NOOS_WORKER_SF_TOKEN" \
        SF_URL=http://127.0.0.1:8000 \
        SF_PASSWORD="$SF_PASSWORD" \
        nohup "$GLOBAL_PYTHON" -m workers.storyforge.main > "$LOG_DIR/worker_storyforge.log" 2>&1 &
        WORKER_SF_PID=$!
        echo "StoryForge Worker started (PID: $WORKER_SF_PID). Logs: $LOG_DIR/worker_storyforge.log"
    else
        echo "[6/6] StoryForge Worker skipped (SF_PASSWORD or NOOS_WORKER_SF_TOKEN not set)"
    fi
fi

cd "$ROOT_DIR"

echo "-----------------------------------"
echo "Suite is running!"
echo "- Kronk UI:   http://localhost:5000"
echo "- BKA API:    http://localhost:8008"
echo "- NOOS Hub:   http://localhost:9090"
echo "-----------------------------------"
echo "To stop everything, run: $ROOT_DIR/stop_suite.sh"
