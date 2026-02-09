#!/bin/bash

# writer-nexus-suite Setup Script
# Creates virtual environments and installs requirements for both Kronk and BKA

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "--- Setting up Writer-Nexus Suite ---"

# 1. Setup BKA
echo "[1/2] Setting up BKA (BookAnalizer)..."
cd "$ROOT_DIR/bka"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Error: bka/requirements.txt not found!"
fi
deactivate

# 2. Setup Kronk
echo "[2/2] Setting up Kronk (UI)..."
cd "$ROOT_DIR/kronk"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Error: kronk/requirements.txt not found!"
fi
deactivate

echo "-----------------------------------"
echo "Setup complete!"
echo "You can now run the suite using: ./start_suite.sh"
echo "-----------------------------------"
