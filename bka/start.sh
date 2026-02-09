#!/bin/bash
# BookAnalizer Start Script

# Ensure we are in the script's directory
cd "$(dirname "$0")"

echo "Starting BookAnalizer..."

# Activate Virtual Environment if exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: 'venv' not found. Trying to run with system python..."
fi

# Check if model exists (optional, nice helper)
# curl -s http://localhost:11434/api/tags | grep "gpt-oss:latest" > /dev/null
# if [ $? -ne 0 ]; then
#     echo "Warning: User might not have pulled gpt-oss:latest yet."
# fi

# Kill existing instance if running (cleanup)
fuser -k 8000/tcp 2>/dev/null

# Start Uvicorn
echo "Server running at http://localhost:8000"
echo "Press CTRL+C to stop."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
