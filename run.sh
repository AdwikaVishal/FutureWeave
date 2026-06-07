#!/bin/bash
# FutureWeave - The Operating System for Human Decisions
# Start both backend and frontend

echo "◆ FutureWeave - Starting Decision Intelligence Platform"
echo ""

# Start backend
echo "Starting backend (port 8000)..."
cd "$(dirname "$0")/sim-engine"
uvicorn api:app --host 0.0.0.0 --port 8000 --reload --reload-exclude 'logs/*' --reload-exclude 'outputs/*' --reload-exclude 'cache/*' --reload-exclude '*.json' &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend (port 5173)..."
cd "$(dirname "$0")/sim-ui"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "◆ FutureWeave is running:"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
