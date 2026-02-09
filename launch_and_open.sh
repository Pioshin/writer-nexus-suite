#!/bin/bash

# Helper script to launch the suite and open the browser
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Launch the suite
cd "$ROOT_DIR"
./start_suite.sh

# Wait a few seconds for servers to be ready
echo "Waiting for servers to start..."
sleep 3

# Open the browser
if command -v xdg-open > /dev/null; then
    xdg-open "http://localhost:5000"
elif command -v google-chrome > /dev/null; then
    google-chrome "http://localhost:5000"
elif command -v firefox > /dev/null; then
    firefox "http://localhost:5000"
fi
