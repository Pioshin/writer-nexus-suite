#!/bin/bash

# writer-nexus-suite Unified Start Script
# This script launches both Kronk (UI) and BKA (BookAnalizer)

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"

mkdir -p "$LOG_DIR"

echo "--- Starting Writer-Nexus Suite ---"

# 1. Start BKA (Port 8000)
echo "[1/2] Starting BKA on port 8000..."
cd "$ROOT_DIR/bka"
BKA_PYTHON="$ROOT_DIR/bka/venv/bin/python"
if [ ! -f "$BKA_PYTHON" ]; then BKA_PYTHON="python3"; fi

# Clear port 8000
fuser -k 8000/tcp 2>/dev/null
nohup "$BKA_PYTHON" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/bka.log" 2>&1 &
BKA_PID=$!
echo "BKA started (PID: $BKA_PID). Logs: logs/bka.log"

# 2. Start Kronk (Port 5000)
echo "[2/2] Starting Kronk on port 5000..."
cd "$ROOT_DIR/kronk"
KRONK_PYTHON="$ROOT_DIR/kronk/venv/bin/python"
if [ ! -f "$KRONK_PYTHON" ]; then KRONK_PYTHON="python3"; fi

# Clear port 5000
fuser -k 5000/tcp 2>/dev/null
nohup "$KRONK_PYTHON" app.py > "$LOG_DIR/kronk.log" 2>&1 &
KRONK_PID=$!
echo "Kronk started (PID: $KRONK_PID). Logs: logs/kronk.log"

echo "-----------------------------------"
echo "Suite is running!"
echo "- Kronk UI: http://localhost:5000"
echo "- BKA API:  http://localhost:8000"
echo "-----------------------------------"
echo "To stop everything, run: kill $BKA_PID $KRONK_PID or use 'fuser -k 5000/tcp 8000/tcp'"
