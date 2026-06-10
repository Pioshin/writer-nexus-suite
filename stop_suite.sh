#!/bin/bash

# Script to stop Writer-Nexus Suite services (LiteLLM, BKA, Kronk, NOOS Hub, workers)

echo "Stopping Writer-Nexus Suite..."

# Stop LiteLLM proxy (Port 4000)
if fuser 4000/tcp >/dev/null 2>&1; then
    echo "Stopping LiteLLM proxy (Port 4000)..."
    fuser -k 4000/tcp
else
    echo "LiteLLM proxy is not running."
fi

# Stop BKA (Port 8008)
if fuser 8008/tcp >/dev/null 2>&1; then
    echo "Stopping BKA (Port 8008)..."
    fuser -k 8008/tcp
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

# Stop NOOS Hub (Port 9090)
if fuser 9090/tcp >/dev/null 2>&1; then
    echo "Stopping NOOS Hub (Port 9090)..."
    fuser -k 9090/tcp
else
    echo "NOOS Hub is not running."
fi

# Stop NOOS workers (by process name)
if pkill -f "workers.bka.main" 2>/dev/null; then
    echo "BKA Worker stopped."
else
    echo "BKA Worker is not running."
fi

if pkill -f "workers.kronk.main" 2>/dev/null; then
    echo "KRONK Worker stopped."
else
    echo "KRONK Worker is not running."
fi

echo "All services stopped."
sleep 2
