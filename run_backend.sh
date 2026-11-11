#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/scripts/fyp_env.sh"

# FYP Backend Startup Script

set -e

cd "$FYP_ROOT"

echo "======================================="
echo "FYP Backend Server"
echo "======================================="
echo

# Python interpreter with torch + FastAPI comes from scripts/fyp_env.sh
# (FYP_PY: explicit override, project venv, legacy conda env, system python3).
if ! "$FYP_PY" -c "import uvicorn, fastapi, torch" 2>/dev/null; then
    echo "ERROR: $FYP_PY is missing uvicorn/fastapi/torch"
    echo "Create the project venv at $FYP_ROOT/venv or export FYP_PY"
    exit 1
fi

# Verify Python version
PYTHON_VERSION=$("$FYP_PY" --version 2>&1)
echo "Using: $PYTHON_VERSION ($FYP_PY)"
echo

# Check if MiDaS directory exists
if [ ! -d "MiDaS" ]; then
    echo "ERROR: MiDaS directory not found"
    exit 1
fi

# Check if weights exist
if [ ! -f "MiDaS/weights/dpt_hybrid_384.pt" ]; then
    echo "ERROR: MiDaS weights not found at MiDaS/weights/dpt_hybrid_384.pt"
    exit 1
fi

echo "Starting FastAPI backend on http://0.0.0.0:8000"
echo "MiDaS will load on startup..."
echo

# Start the backend with FYP environment
PYTHONPATH=$FYP_ROOT:$PYTHONPATH \
"$FYP_PY" -m uvicorn backend.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
