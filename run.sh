#!/bin/bash
# LogSync Startup Script (Cross-platform compatible)
# Usage: ./run.sh [port]

PORT=${1:-8000}

echo "Starting LogSync server on port $PORT..."
cd "$(dirname "$0")"

python3 -m uvicorn src.main:app --host 0.0.0.0 --port "$PORT"
