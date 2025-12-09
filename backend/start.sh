#!/bin/bash
# Startup script for Seikna backend

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the FastAPI server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

