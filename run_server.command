#!/bin/bash
cd "$(dirname "$0")/server"
echo "Dang khoi chay FastAPI Server tai http://localhost:8000..."
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
