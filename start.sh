#!/usr/bin/env bash
# Garuda — project startup script (local development)
# Usage: bash start.sh
# Starts backend (uvicorn :8000) + frontend (Vite :5173) in one terminal.
# Ctrl-C stops both.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$REPO_DIR/.logs"

mkdir -p "$LOG_DIR"

echo "==> Garuda startup"
echo "   Repo:   $REPO_DIR"
echo "   Backend: $BACKEND_DIR (uvicorn :8000)"
echo "   Frontend: $FRONTEND_DIR (Vite :5173)"

# ---- Python environment ----
if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating Python venv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Installing Python dependencies"
pip install --upgrade pip -q
pip install -e "$BACKEND_DIR" -q

echo "==> Installing Node dependencies"
cd "$FRONTEND_DIR"
npm install --no-audit --no-fund -q 2>&1 | tail -3

# ---- Database ----
cd "$BACKEND_DIR"
echo "==> Initializing database schema"
PYTHONPATH=backend python3 -m app.db.init_db

echo "==> Seeding pilot data (idempotent)"
python3 backend/seed_pilot.py 2>&1 | tail -3 || echo "   (seed skipped or already current)"

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