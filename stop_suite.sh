#!/bin/bash

# Script to stop Writer-Nexus Suite services (Kronk and BKA)

echo "🛑 Stopping Writer-Nexus Suite..."

# Stop BKA (Port 8000)
if fuser 8000/tcp >/dev/null 2>&1; then
    echo "Stopping BKA (Port 8000)..."
    fuser -k 8000/tcp
else
    echo "BKA is not running."
fi

# Stop Kronk (Port 5000)
if fuser 5000/tcp >/dev/null 2>&1; then
    echo "Stopping Kronk (Port 5000)..."
    fuser -k 5000/tcp
else
    echo "Kronk is not running."
fi

echo "✅ All services stopped."

# Optional: keep window open for 2 seconds to show message if run from terminal
sleep 2
