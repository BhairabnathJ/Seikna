# Seikna - Learning Platform

Seikna automatically constructs structured, multi-source learning courses from YouTube videos and web articles.

## Architecture

Seikna consists of:
- **Backend**: FastAPI application with SQLite database
- **Frontend**: Next.js with TypeScript and Tailwind CSS
- **LLM**: Ollama (Mixtral for reasoning, LLaVA for vision - Phase 2)

## Setup Instructions

### Prerequisites

1. **Python 3.9+**
2. **Node.js 18+**
3. **Ollama** - Install from https://ollama.ai
4. **Required Ollama models:**
   ```bash
   ollama pull mixtral:latest
   ollama pull llava:latest  # Phase 2
   ollama pull nomic-embed-text:latest  # Phase 4
   ```

### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize database:
   The database will be automatically created when you first run the backend.

5. Run backend server:
   ```bash
   uvicorn api.main:app --reload
   ```
   
   The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies (if not already installed):
   ```bash
   npm install
   ```

3. Set environment variable (optional):
   Create `.env.local` file:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```

4. Run development server:
   ```bash
   npm run dev
   ```
   
   The frontend will be available at `http://localhost:3000`

## Usage

1. Start Ollama (if not running):
   ```bash
   ollama serve
   ```

2. Start backend server (port 8000)

3. Start frontend server (port 3000)

4. Open browser to `http://localhost:3000`

5. Enter a learning topic in the search bar
   - Optionally provide YouTube URLs and/or article URLs in advanced options
   - Click "Create Course"

6. Wait for course generation (may take 30-60 seconds for MVP)

7. View the generated course

## Project Structure

```
seikna/
├── backend/
│   ├── api/                 # FastAPI application
│   ├── services/            # Business logic services
│   ├── core/                # Core utilities
│   ├── db/                  # Database schema
│   └── prompts/             # LLM prompt templates
├── frontend/
│   ├── app/                 # Next.js app directory
│   ├── components/          # React components
│   └── lib/                 # Utility functions
├── data/                    # Data storage
│   ├── cache/               # Cached sources
│   ├── frames/              # Extracted frames (Phase 2)
│   └── seikna.db            # SQLite database
└── docs/                    # Documentation
```

## Phase Status

- **Phase 1 (MVP)**: ✅ Complete
  - Basic ingestion (YouTube + articles)
  - Claim extraction (transcript only)
  - Simple course builder
  - Basic frontend

- **Phase 2**: Vision Intelligence (not yet implemented)
- **Phase 3**: Gamification (not yet implemented)
- **Phase 4**: Full RAG Chatbot (not yet implemented)

## API Documentation

Once the backend is running, visit:
- API Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Notes

- For MVP, YouTube transcript extraction may have limitations. Some videos may not have transcripts available.
- Course generation can take 30-60 seconds depending on source content length.
- The chatbot feature is a placeholder in MVP and will be fully implemented in Phase 4.

