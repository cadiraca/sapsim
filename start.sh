#!/usr/bin/env bash
# SAP SIM — Start backend + frontend
# Usage: ./start.sh

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔══════════════════════════════════════════════╗"
echo "║          SAP SIM — Starting up               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Backend ──────────────────────────────────────────────────────────────────
echo "▶  Starting backend (FastAPI on :8000)..."
cd "$REPO_DIR/backend"

if [ ! -d "venv" ]; then
  echo "   Creating virtual environment..."
  python3 -m venv venv
fi

# Activate venv and install deps
source venv/bin/activate
pip install -r requirements.txt -q

uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# ── Frontend ──────────────────────────────────────────────────────────────────
echo ""
echo "▶  Starting frontend (Next.js on :3000)..."
cd "$REPO_DIR/frontend"

if [ ! -d "node_modules" ]; then
  echo "   Installing dependencies..."
  pnpm install
fi

pnpm dev &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

# ── Ready ─────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  Backend:   http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo "  Frontend:  http://localhost:3000"
echo "══════════════════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop both services."
echo ""

# Wait and forward Ctrl+C to both processes
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID $FRONTEND_PID
