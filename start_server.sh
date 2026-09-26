#!/bin/bash
# TRIG PROFESSIONAL - STARTUP SCRIPT FOR GM GEAR ARAU
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "Memulakan Pelayan TRIG PROFESSIONAL - GM GEAR ARAU..."
echo "=========================================================="

# Kill any existing process on port 8080 if running
lsof -ti:8080 | xargs kill -9 2>/dev/null || true

# Start server
/usr/bin/python3 "$DIR/app.py" 8080
