#!/usr/bin/env bash
# Garuda — project startup script (local development & Vercel dev)
# Usage: bash start.sh
# 
# Modes:
#   - Local development: starts uvicorn + Vite dev server (original behavior)
#   - Vercel dev: prepares environment for Vercel serverless deployment
#
# License: MIT

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
LOG_DIR="$REPO_DIR/.logs"

mkdir -p "$LOG_DIR"

echo "==> Garuda startup"
echo "   Repo:   $REPO_DIR"
echo "   Backend: $BACKEND_DIR"
echo "   Frontend: $FRONTEND_DIR"

# Detect mode: check for VERCEL environment variable
if [ "${VERCEL:-}" = "1" ] || [ "${1:-local}" = "vercel" ]; then
  echo ""
  echo "==> Vercel serverless mode"
  echo "   Starting vercel dev server..."
  echo "   Run: vercel dev --localhost-only"
  echo ""
  echo "==> Local environment setup"
  
  # Install Python dependencies
  echo "==> Installing Python dependencies (with --break-system-packages for Python 3.12+)"
  pip install --upgrade pip --break-system-packages -q 2>&1 | tail -1
  pip install -e "$BACKEND_DIR" --break-system-packages -q 2>&1 | tail -1
  
  # Install Node dependencies
  echo "==> Installing Node dependencies"
  cd "$FRONTEND_DIR"
  npm install --no-audit --no-fund -q 2>&1 | tail -3
  
  # Check for PostgreSQL configuration
  if [ -z "${DATABASE_URL:-}" ]; then
    echo "==> ⚠️  DATABASE_URL not set"
    echo "   For Vercel serverless, you need a PostgreSQL database (Neon, Supabase, Railway, etc.)"
    echo "   Set DATABASE_URL environment variable to your PG connection string"
  else
    echo "==> PostgreSQL database configured: ${DATABASE_URL:0:20}..."
  fi
  
  echo ""
  echo "==> To deploy to Vercel:"
  echo "   vercel login"
  echo "   vercel --prod"
  echo ""
  echo "==> Development mode:"
  echo "   vercel dev"
  exit 0
fi

# ---- Original local development mode ----

# ---- Python environment ----
echo "==> Installing Python dependencies (with --break-system-packages for Python 3.12+)"
pip install --upgrade pip --break-system-packages -q 2>&1 | tail -1
pip install -e "$BACKEND_DIR" --break-system-packages -q 2>&1 | tail -1

# ---- Node environment ----
echo "==> Installing Node dependencies"
cd "$FRONTEND_DIR"
npm install --no-audit --no-fund -q 2>&1 | tail -3

# ---- Database ----
cd "$BACKEND_DIR"
echo "==> Initializing database schema"
PYTHONPATH=backend python3 -m app.db.init_db 2>&1 | tail -3

echo "==> Seeding pilot data (idempotent)"
python3 seed_pilot.py 2>&1 | tail -3 || echo "   (seed skipped or already current)"

# ---- Free ports ----
echo "==> Freeing ports 8000 and 5173"
for port in 8000 5173; do
  pids=$(ss -ltnpH "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u | tr '\n' ' ')
  if [ -n "$pids" ]; then
    echo "   stopping processes on port $port: $pids"
    kill $pids 2>/dev/null || true
    sleep 1
    kill -9 $pids 2>/dev/null || true
  fi
done

# ---- Start services ----
cd "$REPO_DIR"
echo "==> Starting backend on :8000 (log: $LOG_DIR/backend.log)"
PYTHONPATH=backend nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

echo "==> Starting frontend on :5173 (log: $LOG_DIR/frontend.log)"
cd "$FRONTEND_DIR"
nohup npm run dev -- --port 5173 --strictPort --host 127.0.0.1 > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

cd "$REPO_DIR"

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo; echo "==> Stopped."' INT TERM

echo "==> Backend PID $BACKEND_PID  Frontend PID $FRONTEND_PID"
echo "   API:      http://127.0.0.1:8000"
echo "   App:      http://127.0.0.1:5173"
echo "   Globe:    http://127.0.0.1:5173/?globe=1"
echo "   Logs:     $LOG_DIR/"
echo "   Ctrl-C to stop both."
wait
