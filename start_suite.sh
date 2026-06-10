#!/bin/bash

# writer-nexus-suite Unified Start Script
# This script launches both Kronk (UI) and BKA (BookAnalizer)

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

echo "-----------------------------------"
echo "Suite is running!"
echo "- Kronk UI: http://localhost:5000"
echo "- BKA API:  http://localhost:8008"
echo "-----------------------------------"
echo "To stop everything, run: $ROOT_DIR/stop_suite.sh"
