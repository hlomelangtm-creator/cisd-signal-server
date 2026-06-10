#!/bin/bash
# start.sh — runs Node.js server AND Python CISD engine simultaneously

echo "Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages --quiet

echo "Starting Node.js webhook server..."
node server.js &
NODE_PID=$!

echo "Waiting for server to be ready..."
sleep 3

echo "Starting Python CISD engine..."
python3 cisd_engine.py &
PYTHON_PID=$!

echo "Both services running."
echo "Node PID: $NODE_PID | Python PID: $PYTHON_PID"

# Keep running — if either exits, kill both
wait $NODE_PID $PYTHON_PID
