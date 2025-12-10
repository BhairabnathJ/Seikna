# SYSTEM NOTES - Seikna

This file contains the canonical architecture, decisions, conventions, and instructions shared between Claude (architect) and Cursor (engineer). All changes must be reflected here.

**Last Updated:** 2025-12-08
**Phase:** MVP (Phase 1)

---

# 1. ARCHITECTURE (Claude)

## 1.1 High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         SEIKNA PLATFORM                         │
└─────────────────────────────────────────────────────────────────┘

   USER INPUT (Query: "Machine Learning")
          ↓
   ┌─────────────────────┐
   │   API LAYER         │  FastAPI
   │   /api/v1/*         │
   └─────────────────────┘
          ↓
   ┌─────────────────────────────────────────────────────────────┐
   │              CORE PROCESSING PIPELINE                        │
   ├─────────────────────────────────────────────────────────────┤
   │                                                               │
   │  [1] INGESTION SERVICE                                       │
   │      ├─ YouTube Fetcher (yt-dlp)                            │
   │      ├─ Article Scraper                                      │
   │      ├─ Frame Extractor (ffmpeg)                            │
   │      └─ Cache Manager (SQLite)                              │
   │                                                               │
   │  [2] KNOWLEDGE EXTRACTION ENGINE                             │
   │      ├─ Transcript Claim Extractor (Mixtral)                │
   │      ├─ Visual Claim Extractor (LLaVA)                      │
   │      ├─ VCT Classifier (Visual Complexity Tier)             │
   │      ├─ Contradiction Detector                               │
   │      └─ Consensus Builder                                    │
   │                                                               │
   │  [3] COURSE BUILDER                                          │
   │      ├─ Structure Generator                                  │
   │      ├─ Content Synthesizer                                  │
   │      └─ Quiz Generator                                       │
   │                                                               │
   │  [4] RAG CHATBOT                                             │
   │      ├─ Embedding Store (course content)                    │
   │      ├─ Retriever                                            │
   │      └─ Domain-Limited Responder                            │
   │                                                               │
   │  [5] GAMIFICATION ENGINE                                     │
   │      ├─ XP Tracker                                           │
   │      ├─ Badge Unlocker                                       │
   │      └─ Skill Tree Manager                                   │
   │                                                               │
   └─────────────────────────────────────────────────────────────┘
          ↓
   ┌─────────────────────┐
   │   DATA LAYER        │  SQLite
   │   ├─ Sources        │
   │   ├─ Claims         │
   │   ├─ Courses        │
   │   ├─ User Progress  │
   │   └─ Embeddings     │
   └─────────────────────┘
          ↓
   ┌─────────────────────┐
   │   FRONTEND          │  Next.js
   │   ├─ Search         │
   │   ├─ Course Viewer  │
   │   ├─ Chat Panel     │
   │   └─ Profile        │
   └─────────────────────┘
```

## 1.2 Component Responsibilities

### **[1] Ingestion Service**
**Purpose:** Fetch and cache raw learning materials

**Sub-components:**
- **YouTube Fetcher**: Uses yt-dlp to download transcripts and metadata
- **Article Scraper**: Fetches web articles, extracts clean text
- **Frame Extractor**: Uses ffmpeg to extract keyframes based on VCT
- **Cache Manager**: SQLite-based caching to avoid re-fetching

**Inputs:** List of YouTube URLs + Article URLs
**Outputs:** Raw transcripts, article text, video frames

---

### **[2] Knowledge Extraction Engine**
**Purpose:** Transform raw content into verified knowledge claims

**Sub-components:**

**a) Transcript Claim Extractor**
- Uses Mixtral to parse transcripts into atomic claims
- Output format: `(subject, predicate, object, timestamp, source_id)`
- Example: `("Neural networks", "are inspired by", "biological neurons", "00:02:15", "video_1")`

**b) Visual Claim Extractor**
- Uses LLaVA to analyze frames
- Extracts visual information (diagrams, slides, equations)
- OCR for text-heavy frames
- Output: `(visual_claim, frame_timestamp, source_id)`

**c) VCT Classifier (Visual Complexity Tier)**
- Analyzes video to determine visual importance
- Tiers:
  - **VCT-1:** Audio-only, no visual value
  - **VCT-2:** Talking head, minimal visuals
  - **VCT-3:** Occasional slides/diagrams
  - **VCT-4:** Heavy visual content (50%+ valuable frames)
  - **VCT-5:** Visual-dependent (whiteboard, animations, demos)
- Determines frame extraction strategy

**d) Contradiction Detector**
- Compares claims across sources
- Flags contradictions using semantic similarity + LLM reasoning
- Example: Source A says "X is Y", Source B says "X is not Y"

**e) Consensus Builder**
- Merges claims from multiple sources
- Confidence scoring based on agreement
- Outputs: Verified facts with source attributions

**Inputs:** Raw transcripts, frames
**Outputs:** Structured claims, contradictions, consensus model

---

### **[3] Course Builder**
**Purpose:** Generate structured learning paths

**Sub-components:**

**Structure Generator**
- Creates course outline:
  1. Overview
  2. Prerequisites
  3. Fundamentals
  4. Visual Explanations
  5. Examples
  6. Troubleshooting / Common Mistakes
  7. Glossary
  8. Quizzes

**Content Synthesizer**
- Assembles verified claims into coherent lessons
- Adds source citations
- Highlights contradictions or "controversial points"

**Quiz Generator**
- Creates multiple-choice questions from claims
- Difficulty scaling

**Inputs:** Consensus claims, source metadata
**Outputs:** Structured course JSON

---

### **[4] RAG Chatbot**
**Purpose:** Answer questions ONLY using course content

**Sub-components:**

**Embedding Store**
- Embeds all course sections (chunks)
- Uses Ollama embedding model
- Stored in SQLite with vector extension or in-memory index

**Retriever**
- Semantic search over course content
- Top-k retrieval

**Domain-Limited Responder**
- LLM (Mixtral) with strict prompt:
  - "Answer ONLY using the provided context"
  - "If answer not in context, say 'I don't have that information in this course'"
  - Always cite section references

**Inputs:** User question, course_id
**Outputs:** Answer + citations

---

### **[5] Gamification Engine**
**Purpose:** Track learning progress and motivate users

**Sub-components:**

**XP Tracker**
- Awards XP for:
  - Completing modules
  - Passing quizzes
  - Checkpoint completion

**Badge Unlocker**
- "First Explorer" - first course completed
- "Deep Diver" - complete 3+ advanced topics
- "Polymath" - courses in 5+ domains

**Skill Tree Manager**
- Builds knowledge graph of user's completed topics
- Visualizes connections

**Inputs:** User actions (module_completed, quiz_passed)
**Outputs:** XP deltas, badge unlocks, skill tree updates

---

## 1.3 Technology Stack Mapping

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Layer | FastAPI | REST endpoints |
| Ingestion | yt-dlp, requests, ffmpeg | Fetch content |
| LLM Reasoning | Ollama (Mixtral) | Claim extraction, synthesis |
| Vision | Ollama (LLaVA) | Frame analysis |
| Embeddings | Ollama (nomic-embed-text) | RAG retrieval |
| Database | SQLite | Cache + persistence |
| Frontend | Next.js | UI |
| Task Queue | (Optional: Celery/RQ) | Async processing |

---

## 1.4 System Modes

### **MVP (Phase 1)**
- Basic ingestion (YouTube + articles)
- Claim extraction (transcript only, no vision yet)
- Simple course structure
- Basic chatbot

### **Phase 2 - Vision Intelligence**
- VCT classification
- Frame extraction
- Visual claim extraction (LLaVA)

### **Phase 3 - Gamification**
- XP, badges, streaks
- Skill trees

### **Phase 4 - Full Ecosystem**
- Quizzes
- Learning paths
- Multi-course connections

---

# 2. DATA PIPELINES (Claude)

## 2.1 End-to-End Pipeline Flow

```
USER QUERY: "Machine Learning"
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: SOURCE DISCOVERY                                    │
│ - Search YouTube API for "Machine Learning tutorial"       │
│ - Search web for "Machine Learning introduction article"   │
│ - Select top N sources (e.g., 5 videos + 3 articles)       │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: INGESTION                                           │
│ For each source:                                            │
│   - Check cache (SQLite: sources table)                    │
│   - If cached: skip                                         │
│   - If new:                                                 │
│       * Download transcript (yt-dlp)                       │
│       * Fetch article (requests + beautifulsoup)           │
│       * Store in cache                                      │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: VISUAL PROCESSING (Phase 2)                         │
│ For each video:                                             │
│   - Run VCT classifier on metadata + sample frames         │
│   - If VCT >= 3:                                            │
│       * Extract keyframes (ffmpeg)                         │
│       * Run LLaVA on each frame                            │
│       * Extract visual claims                               │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: CLAIM EXTRACTION                                    │
│ For each transcript:                                        │
│   - Split into chunks (semantic chunking)                  │
│   - For each chunk:                                         │
│       * LLM prompt: "Extract atomic claims as triples"    │
│       * Store: (subject, predicate, object, timestamp)     │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: CONTRADICTION DETECTION                             │
│ - Embed all claims                                          │
│ - Find semantically similar claim pairs                    │
│ - For similar pairs:                                        │
│     * LLM prompt: "Do these contradict? Explain"           │
│     * Store contradiction + reasoning                       │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: CONSENSUS BUILDING                                  │
│ - Group claims by semantic similarity                      │
│ - For each group:                                           │
│     * Count source agreement                                │
│     * Confidence = sources_agreeing / total_sources        │
│     * If contradiction: mark as "controversial"            │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: COURSE CONSTRUCTION                                 │
│ - LLM prompt: "Given these verified claims, create a       │
│   structured course outline"                                │
│ - Generate sections:                                        │
│     * Overview (what is X?)                                │
│     * Prerequisites                                         │
│     * Fundamentals (core concepts from claims)             │
│     * Visual Explanations (embed frames + visual claims)   │
│     * Examples                                              │
│     * Troubleshooting                                       │
│     * Glossary (extract terms from claims)                 │
│     * Quizzes (generate from claims)                       │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 8: RAG PREPARATION                                     │
│ - Chunk course content                                      │
│ - Embed all chunks                                          │
│ - Store in vector index (course_embeddings table)          │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: COURSE READY                                        │
│ - Return course_id to frontend                             │
│ - User can now read + chat                                  │
└─────────────────────────────────────────────────────────────┘
```

## 2.2 Pipeline Execution Strategy

**Synchronous (MVP):**
- Small pipelines block until complete
- User waits ~30-60 seconds

**Asynchronous (Production):**
- User submits query → gets job_id
- Backend processes in background
- Frontend polls /api/v1/jobs/{job_id}
- Notifies when complete

---

# 3. API CONTRACTS (Claude)

## 3.1 Endpoint Specifications

### **POST /api/v1/courses/create**
**Purpose:** Initiate course creation from query

**Request:**
```json
{
  "query": "Machine Learning",
  "num_sources": 8,
  "source_types": ["youtube", "article"],
  "difficulty": "beginner"  // optional
}
```

**Response:**
```json
{
  "job_id": "uuid-1234",
  "status": "processing",
  "estimated_time": 60  // seconds
}
```

---

### **GET /api/v1/jobs/{job_id}**
**Purpose:** Check course creation status

**Response:**
```json
{
  "job_id": "uuid-1234",
  "status": "completed",  // or "processing", "failed"
  "course_id": "course-5678",
  "progress": 100
}
```

---

### **GET /api/v1/courses/{course_id}**
**Purpose:** Fetch complete course structure

**Response:**
```json
{
  "course_id": "course-5678",
  "title": "Machine Learning Fundamentals",
  "description": "A comprehensive introduction...",
  "metadata": {
    "source_count": 8,
    "difficulty": "beginner",
    "estimated_time": "4 hours",
    "vct_tier": 4
  },
  "sections": [
    {
      "id": "section-1",
      "title": "Overview",
      "content": "Machine Learning is...",
      "sources": ["video-1", "article-2"]
    },
    {
      "id": "section-2",
      "title": "Prerequisites",
      "content": "You should know...",
      "sources": ["video-1"]
    }
    // ... more sections
  ],
  "glossary": [...],
  "quizzes": [...]
}
```

---

### **POST /api/v1/chat**
**Purpose:** Domain-limited chatbot

**Request:**
```json
{
  "course_id": "course-5678",
  "message": "What is supervised learning?",
  "conversation_id": "conv-123"  // optional, for context
}
```

**Response:**
```json
{
  "response": "Supervised learning is a type of machine learning where...",
  "citations": [
    {
      "section_id": "section-3",
      "section_title": "Fundamentals",
      "source": "video-1"
    }
  ],
  "confidence": "high"
}
```

---

### **GET /api/v1/users/{user_id}/progress**
**Purpose:** Fetch user gamification data

**Response:**
```json
{
  "user_id": "user-42",
  "total_xp": 1250,
  "level": 5,
  "streak_days": 12,
  "badges": [
    {
      "id": "first_explorer",
      "name": "First Explorer",
      "unlocked_at": "2025-12-01"
    }
  ],
  "completed_courses": ["course-5678", "course-1234"],
  "skill_tree": {
    "Machine Learning": {
      "completed": true,
      "children": ["Neural Networks", "Decision Trees"]
    }
  }
}
```

---

### **POST /api/v1/progress/checkpoint**
**Purpose:** Mark section complete, award XP

**Request:**
```json
{
  "user_id": "user-42",
  "course_id": "course-5678",
  "section_id": "section-3"
}
```

**Response:**
```json
{
  "xp_earned": 50,
  "new_total_xp": 1300,
  "badges_unlocked": [],
  "level_up": false
}
```

---

# 4. DATABASE SCHEMAS (Claude)

## 4.1 SQLite Schema

### **sources**
```sql
CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,  -- 'youtube' | 'article'
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    transcript TEXT,
    metadata JSON,  -- author, duration, publish_date, etc.
    vct_tier INTEGER,  -- 1-5, NULL for articles
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **frames**
```sql
CREATE TABLE frames (
    frame_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    timestamp_ms INTEGER,  -- milliseconds into video
    frame_path TEXT,  -- local file path
    visual_claim TEXT,  -- extracted by LLaVA
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
```

### **claims**
```sql
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    claim_type TEXT,  -- 'transcript' | 'visual'
    subject TEXT,
    predicate TEXT,
    object TEXT,
    timestamp_ms INTEGER,  -- for video timestamps
    confidence REAL DEFAULT 1.0,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
```

### **contradictions**
```sql
CREATE TABLE contradictions (
    contradiction_id TEXT PRIMARY KEY,
    claim_id_1 TEXT NOT NULL,
    claim_id_2 TEXT NOT NULL,
    reasoning TEXT,  -- LLM explanation
    FOREIGN KEY (claim_id_1) REFERENCES claims(claim_id),
    FOREIGN KEY (claim_id_2) REFERENCES claims(claim_id)
);
```

### **courses**
```sql
CREATE TABLE courses (
    course_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    title TEXT,
    description TEXT,
    structure JSON,  -- full course outline
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **course_sources**
```sql
CREATE TABLE course_sources (
    course_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    PRIMARY KEY (course_id, source_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
```

### **embeddings**
```sql
CREATE TABLE embeddings (
    embedding_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding BLOB,  -- serialized vector
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);
```

### **users**
```sql
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    total_xp INTEGER DEFAULT 0,
    streak_days INTEGER DEFAULT 0,
    last_active_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **user_progress**
```sql
CREATE TABLE user_progress (
    user_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    PRIMARY KEY (user_id, course_id, section_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);
```

### **badges**
```sql
CREATE TABLE badges (
    badge_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    icon_url TEXT
);
```

### **user_badges**
```sql
CREATE TABLE user_badges (
    user_id TEXT NOT NULL,
    badge_id TEXT NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (badge_id) REFERENCES badges(badge_id)
);
```

---

## 4.2 Caching Strategy

**Level 1: Source Cache**
- Cache all fetched transcripts/articles
- Key: URL hash
- TTL: Infinite (or 30 days for news)

**Level 2: Claim Cache**
- Cache extracted claims per source
- Avoid re-running LLM on same content

**Level 3: Course Cache**
- Cache full courses
- Invalidate if sources updated

---

# 5. LLM PROMPT BLUEPRINTS (Claude)

## 5.1 Claim Extraction Prompt (Transcript)

**Model:** Mixtral
**Purpose:** Extract atomic knowledge claims from transcript chunks

**Prompt Template:**
```
You are a knowledge extraction assistant.

Given the following transcript chunk, extract ALL factual claims as structured triples.

TRANSCRIPT:
"""
{transcript_chunk}
"""

For each claim, output in this format:
(subject, predicate, object)

RULES:
1. Extract ONLY factual claims, not opinions or speculation
2. Keep claims atomic (one fact per triple)
3. Preserve technical terminology exactly
4. If timestamp available, include it

EXAMPLE:
Input: "Neural networks are inspired by biological neurons. They consist of layers of interconnected nodes."
Output:
("Neural networks", "are inspired by", "biological neurons")
("Neural networks", "consist of", "layers of interconnected nodes")

Now extract claims from the transcript above.
```

---

## 5.2 Visual Claim Extraction Prompt (LLaVA)

**Model:** LLaVA
**Purpose:** Extract visual information from frame

**Prompt Template:**
```
Analyze this image from an educational video about {topic}.

Describe:
1. What type of visual is this? (diagram, slide, whiteboard, code, equation, etc.)
2. What key information does it convey?
3. Extract any text visible in the image (OCR)
4. What claim or concept is being illustrated?

Be specific and technical. Output as a structured claim.
```

---

## 5.3 VCT Classification Prompt

**Model:** Mixtral (with optional LLaVA for sample frames)
**Purpose:** Determine visual complexity tier

**Prompt Template:**
```
You are analyzing a video to determine its Visual Complexity Tier (VCT).

VIDEO METADATA:
- Title: {title}
- Description: {description}
- Duration: {duration}
- Sample frames analyzed: {num_frames}

SAMPLE FRAME DESCRIPTIONS:
{frame_descriptions}

Classify into one of these tiers:

VCT-1: Audio-only lecture, no visual value (talking head only)
VCT-2: Talking head with minimal slides (< 20% valuable frames)
VCT-3: Regular slides/diagrams appear (20-50% valuable frames)
VCT-4: Heavy visual content (50-80% valuable frames)
VCT-5: Visually-dependent (whiteboard, live coding, animations) (80%+ valuable frames)

Output: VCT-X (with brief reasoning)
```

---

## 5.4 Contradiction Detection Prompt

**Model:** Mixtral
**Purpose:** Detect if two claims contradict

**Prompt Template:**
```
You are a fact-checking assistant.

CLAIM 1 (from {source_1}):
"{claim_1}"

CLAIM 2 (from {source_2}):
"{claim_2}"

QUESTION: Do these claims contradict each other?

INSTRUCTIONS:
- If YES: Explain the contradiction clearly
- If NO: Explain why they are compatible (or about different things)
- If UNCERTAIN: Note what additional context is needed

Output format:
CONTRADICTION: [YES/NO/UNCERTAIN]
REASONING: [Your explanation]
```

---

## 5.5 Course Structure Generation Prompt

**Model:** Mixtral
**Purpose:** Create course outline from verified claims

**Prompt Template:**
```
You are an expert curriculum designer.

You have been given a collection of verified knowledge claims about: {topic}

CLAIMS:
{verified_claims}

Create a structured learning course with these sections:

1. Overview - What is {topic}? Why is it important?
2. Prerequisites - What should learners know first?
3. Fundamentals - Core concepts (build from claims)
4. Visual Explanations - Key diagrams/examples
5. Examples - Real-world applications
6. Troubleshooting - Common mistakes or confusions
7. Glossary - Define key terms
8. Summary - Recap

For each section, synthesize the relevant claims into clear, educational prose.
Always cite which source(s) each fact came from.

Output as structured JSON.
```

---

## 5.6 Domain-Limited Chatbot Prompt

**Model:** Mixtral
**Purpose:** Answer questions ONLY from course content

**Prompt Template:**
```
You are a helpful teaching assistant for a course about {course_topic}.

STRICT RULES:
1. Answer ONLY using information from the CONTEXT below
2. If the answer is not in the context, respond: "I don't have that information in this course. You might want to check the {suggested_section} section."
3. Always cite which course section your answer comes from
4. Do not make up information
5. Do not use external knowledge

CONTEXT (from course):
"""
{retrieved_chunks}
"""

STUDENT QUESTION:
"{user_question}"

Provide a helpful answer with citations.
```

---

# 6. VISUAL COMPLEXITY TIER (VCT) SYSTEM (Claude)

## 6.1 VCT Architecture

**Purpose:** Optimize frame extraction based on visual importance

### **VCT Tiers:**

| Tier | Description | Frame Extraction Strategy |
|------|-------------|---------------------------|
| VCT-1 | Audio-only lecture | No frames extracted |
| VCT-2 | Talking head, minimal visuals | 1 frame per 2 minutes |
| VCT-3 | Occasional slides/diagrams | 1 frame per 30 seconds |
| VCT-4 | Heavy visual content | 1 frame per 10 seconds |
| VCT-5 | Visual-dependent (whiteboard) | 1 frame per 3 seconds |

### **Classification Process:**

1. **Metadata Analysis:**
   - Check title/description for visual keywords ("whiteboard", "animation", "slides")
   - Channel history (educational channels often have consistent VCT)

2. **Sample Frame Analysis:**
   - Extract 5 frames at [10%, 30%, 50%, 70%, 90%] of video
   - Run LLaVA to describe each frame
   - Count frames with "educational visual content"

3. **LLM Classification:**
   - Feed metadata + frame descriptions to Mixtral
   - Output: VCT tier + reasoning

### **Storage:**
- Store VCT tier in `sources.vct_tier`
- Cache frame extraction results

---

# 7. GAMIFICATION SYSTEM (Claude)

## 7.1 XP System

**XP Awards:**
- Complete section: 50 XP
- Pass quiz (per question): 10 XP
- First course completed: 200 XP bonus
- Daily streak maintained: 25 XP

**Levels:**
- XP thresholds: [0, 100, 300, 600, 1000, 1500, 2200, 3000...]
- Formula: `level_threshold = 100 * level * (level + 1) / 2`

## 7.2 Badge System

**Badge Definitions:**

| Badge ID | Name | Unlock Condition |
|----------|------|------------------|
| first_explorer | First Explorer | Complete first course |
| deep_diver | Deep Diver | Complete 3+ advanced courses |
| polymath | Polymath | Complete courses in 5+ domains |
| speed_reader | Speed Reader | Complete course in < 2 hours |
| streak_warrior | Streak Warrior | 30-day streak |

**Implementation:**
- Check badge conditions after each progress update
- Store in `user_badges` table
- Frontend displays with icons

## 7.3 Skill Tree

**Structure:**
- Directed graph of topics
- Nodes = courses completed
- Edges = prerequisite relationships

**Example:**
```
Programming
 ├─ Python
 │   ├─ Data Science
 │   └─ Web Development
 └─ JavaScript
     └─ React
```

**Visualization:**
- Frontend renders as interactive graph
- Unlocked nodes colored differently

---

# 8. FOLDER STRUCTURE (Claude → Cursor to implement)

```
seikna/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app
│   │   ├── routes/
│   │   │   ├── courses.py          # /api/v1/courses/*
│   │   │   ├── chat.py             # /api/v1/chat
│   │   │   ├── users.py            # /api/v1/users/*
│   │   │   └── jobs.py             # /api/v1/jobs/*
│   │   └── models/
│   │       ├── requests.py         # Pydantic request models
│   │       └── responses.py        # Pydantic response models
│   ├── services/
│   │   ├── ingestion/
│   │   │   ├── youtube_fetcher.py
│   │   │   ├── article_scraper.py
│   │   │   ├── frame_extractor.py
│   │   │   └── cache_manager.py
│   │   ├── extraction/
│   │   │   ├── claim_extractor.py
│   │   │   ├── visual_extractor.py
│   │   │   ├── vct_classifier.py
│   │   │   ├── contradiction_detector.py
│   │   │   └── consensus_builder.py
│   │   ├── course_builder/
│   │   │   ├── structure_generator.py
│   │   │   ├── content_synthesizer.py
│   │   │   └── quiz_generator.py
│   │   ├── rag/
│   │   │   ├── embedder.py
│   │   │   ├── retriever.py
│   │   │   └── responder.py
│   │   └── gamification/
│   │       ├── xp_tracker.py
│   │       ├── badge_manager.py
│   │       └── skill_tree.py
│   ├── core/
│   │   ├── config.py               # Configuration
│   │   ├── database.py             # SQLite connection
│   │   ├── ollama_client.py        # Ollama API wrapper
│   │   └── pipeline.py             # Main orchestration
│   ├── prompts/
│   │   ├── claim_extraction.txt
│   │   ├── visual_analysis.txt
│   │   ├── vct_classification.txt
│   │   ├── contradiction_detection.txt
│   │   ├── course_structure.txt
│   │   └── chatbot.txt
│   ├── db/
│   │   ├── schema.sql              # Database schema
│   │   └── migrations/
│   ├── tests/
│   │   ├── test_ingestion.py
│   │   ├── test_extraction.py
│   │   └── test_rag.py
│   └── requirements.txt
├── frontend/
│   ├── pages/
│   │   ├── index.tsx               # Home/search
│   │   ├── courses/[id].tsx        # Course viewer
│   │   └── profile.tsx             # User dashboard
│   ├── components/
│   │   ├── SearchBar.tsx
│   │   ├── CourseCard.tsx
│   │   ├── ChatPanel.tsx
│   │   ├── SkillTree.tsx
│   │   └── BadgeDisplay.tsx
│   ├── lib/
│   │   └── api.ts                  # API client
│   └── package.json
├── data/
│   ├── cache/                      # Downloaded videos/articles
│   ├── frames/                     # Extracted frames
│   └── seikna.db                   # SQLite database
├── docs/
│   ├── PRD.md
│   ├── Claude_prompt.md
│   └── SYSTEM_NOTES.md
└── README.md
```

---

# 9. IMPLEMENTATION PHASES (Claude)

## Phase 1: MVP (Current Target)

**Cursor Tasks:**
1. Set up FastAPI backend structure
2. Implement YouTube fetcher (yt-dlp)
3. Implement article scraper
4. Create SQLite database + tables
5. Implement basic claim extractor (transcript only)
6. Implement simple course builder
7. Create API endpoints: /courses/create, /courses/{id}
8. Build basic Next.js frontend (search + course viewer)

**No Vision, No Gamification Yet**

## Phase 2: Vision Intelligence

**Cursor Tasks:**
1. Implement frame extractor (ffmpeg)
2. Implement VCT classifier
3. Implement visual claim extractor (LLaVA)
4. Update course builder to include visual content
5. Update frontend to display frames

## Phase 3: Gamification

**Cursor Tasks:**
1. Implement XP tracker
2. Implement badge system
3. Implement skill tree
4. Create profile dashboard UI

## Phase 4: RAG Chatbot

**Cursor Tasks:**
1. Implement embedder
2. Implement retriever
3. Implement domain-limited responder
4. Create chat panel UI

---

# 10. NEXT STEPS FOR CURSOR

## Immediate Tasks (MVP - Phase 1)

1. **Backend Setup**
   - Initialize FastAPI project
   - Install dependencies: `fastapi uvicorn yt-dlp requests beautifulsoup4 sqlite3 pydantic ollama`
   - Create folder structure as specified above

2. **Database Initialization**
   - Create `db/schema.sql` with tables defined in Section 4.1
   - Create `core/database.py` with connection logic

3. **Ingestion Service**
   - Implement `services/ingestion/youtube_fetcher.py`:
     - Function: `fetch_youtube_transcript(url) -> dict`
     - Use yt-dlp to download transcript
     - Return: `{source_id, url, title, transcript, metadata}`
   - Implement `services/ingestion/article_scraper.py`:
     - Function: `fetch_article(url) -> dict`
     - Use requests + beautifulsoup4
     - Return: `{source_id, url, title, content, metadata}`
   - Implement `services/ingestion/cache_manager.py`:
     - Function: `get_cached_source(url) -> dict | None`
     - Function: `save_source(source_data) -> None`

4. **Claim Extraction**
   - Implement `core/ollama_client.py`:
     - Function: `call_mixtral(prompt, max_tokens) -> str`
   - Implement `services/extraction/claim_extractor.py`:
     - Function: `extract_claims(transcript, source_id) -> List[dict]`
     - Use prompt from Section 5.1
     - Parse LLM output into claim triples
     - Store in `claims` table

5. **Course Builder (Basic)**
   - Implement `services/course_builder/structure_generator.py`:
     - Function: `build_course(query, claims, sources) -> dict`
     - Use prompt from Section 5.5
     - Generate JSON structure matching Section 3.1 response

6. **API Endpoints**
   - Implement `api/routes/courses.py`:
     - `POST /api/v1/courses/create` (Section 3.1)
     - `GET /api/v1/courses/{course_id}` (Section 3.1)
   - Implement `core/pipeline.py`:
     - Function: `run_course_creation_pipeline(query) -> course_id`
     - Orchestrate: ingestion → extraction → course building

7. **Frontend (Basic)**
   - Create Next.js app
   - Implement search page
   - Implement course viewer
   - API client to call backend

---

# 11. CURSOR IMPLEMENTATION NOTES

## Implementation Date: 2025-01-08

### Phase 1 MVP Implementation Status: ✅ COMPLETE

**Implemented Components:**

1. **Backend Structure** ✅
   - FastAPI application with proper routing
   - Database schema (SQLite) with all required tables
   - Core utilities (database, Ollama client, config)

2. **Ingestion Services** ✅
   - YouTube fetcher using yt-dlp
   - Article scraper using BeautifulSoup
   - Cache manager for source persistence

3. **Claim Extraction** ✅
   - Transcript-based claim extractor
   - LLM integration with Mixtral via Ollama
   - Claim storage in database

4. **Course Builder** ✅
   - Structure generator using LLM
   - JSON-based course structure
   - Source attribution

5. **API Endpoints** ✅
   - POST `/api/v1/courses/create` - Course creation
   - GET `/api/v1/courses/{course_id}` - Course retrieval
   - GET `/api/v1/courses/jobs/{job_id}` - Job status
   - POST `/api/v1/chat` - Placeholder for Phase 4

6. **Frontend** ✅
   - Next.js application with TypeScript
   - Search page with URL input
   - Course viewer with collapsible sections
   - Basic styling with Tailwind CSS

### Implementation Decisions:

1. **Synchronous Processing for MVP**
   - Course creation processes synchronously when URLs are provided
   - Job polling system in place for future async enhancement

2. **YouTube Transcript Extraction**
   - Uses yt-dlp to fetch subtitle URLs
   - Parses WebVTT format subtitles
   - Falls back gracefully if transcripts unavailable

3. **Course Structure**
   - LLM generates JSON structure with sections
   - Fallback structure generator if LLM fails
   - Sections are collapsible in frontend

4. **Database**
   - SQLite for MVP (can be migrated to PostgreSQL later)
   - Automatic schema initialization on first run
   - JSON storage for complex structures

### Known Limitations (MVP):

1. **Source Discovery**: Not implemented - requires explicit URLs
2. **Vision Processing**: Deferred to Phase 2
3. **Contradiction Detection**: Not implemented in MVP
4. **Consensus Building**: Simplified - just aggregates claims
5. **Chatbot**: Placeholder only - Phase 4
6. **Gamification**: Not implemented - Phase 3

### File Structure Created:

```
backend/
├── api/
│   ├── main.py
│   ├── routes/
│   │   ├── courses.py
│   │   └── chat.py
│   └── models/
│       ├── requests.py
│       └── responses.py
├── services/
│   ├── ingestion/
│   │   ├── youtube_fetcher.py
│   │   ├── article_scraper.py
│   │   ├── cache_manager.py
│   │   └── frame_extractor.py (Phase 2 placeholder)
│   ├── extraction/
│   │   ├── claim_extractor.py
│   │   ├── visual_extractor.py (Phase 2 placeholder)
│   │   ├── vct_classifier.py (Phase 2 placeholder)
│   │   ├── contradiction_detector.py (placeholder)
│   │   └── consensus_builder.py (placeholder)
│   ├── course_builder/
│   │   ├── structure_generator.py
│   │   └── content_synthesizer.py (placeholder)
│   ├── rag/ (Phase 4 placeholders)
│   └── gamification/ (Phase 3 placeholders)
├── core/
│   ├── config.py
│   ├── database.py
│   ├── ollama_client.py
│   └── pipeline.py
├── prompts/
│   ├── claim_extraction.txt
│   └── course_structure.txt
└── db/
    └── schema.sql

frontend/
├── app/
│   ├── page.tsx (home/search)
│   └── courses/[id]/page.tsx (course viewer)
├── components/
│   ├── SearchBar.tsx
│   └── CourseCard.tsx
└── lib/
    └── api.ts
```

### Testing Notes:

- Backend can be tested with: `uvicorn api.main:app --reload`
- Frontend runs with: `npm run dev` in frontend directory
- Requires Ollama running with Mixtral model: `ollama pull mixtral:latest`
- Database is automatically created on first run

### Configuration Management:

**Updated: 2025-01-08**
- Added `python-dotenv` for environment variable management
- Configuration now loads from `.env` file in project root or backend directory
- All config values can be overridden via environment variables
- Added support for API keys (YouTube API, Web Search API) for future features
- Created `.env.example` template (manually create `.env` file based on it)
- Configuration priorities:
  1. Environment variables (highest priority)
  2. `.env` file in project root
  3. `.env` file in backend directory
  4. Default values (lowest priority)

### Full Course Generation Pipeline:

**Implemented: 2025-01-08 (Priority 2)**
- ✅ **Transcription & Normalization** (`transcriber.py`)
  - Normalizes YouTube VTT/SRT transcripts
  - Normalizes article HTML content
  - Validates transcript quality
  - Creates RawTranscript objects with segments
  
- ✅ **Semantic Chunking** (`chunker.py`)
  - Embedding-based boundary detection
  - Heuristic fallback chunking
  - Coherence and completeness scoring
  - Quality-based rechunking
  
- ✅ **LLM Expansion** (`llm_expander.py`)
  - Expands chunks with educational context
  - Extracts key concepts, definitions, examples
  - Generates atomic claims
  - Calculates difficulty and cognitive load
  
- ✅ **Enhanced Course Builder** (`course_builder.py`)
  - Synthesizes sections from expanded chunks
  - Generates key takeaways and practice questions
  - Creates citations with source attribution
  - Calculates quality metrics
  
- ✅ **Database Schema Updates**
  - `raw_transcripts` table
  - `transcript_segments` table
  - `transcript_chunks` table
  - `expanded_chunks` table
  - `course_sections` table
  - `section_citations` table
  
- ✅ **Pipeline Integration**
  - Full 8-stage pipeline implemented
  - Backward compatible with legacy format
  - Stores all intermediate data

### Source Discovery System:

**Implemented: 2025-01-08 (Priority 1)**
- ✅ **YouTube Search Integration**
  - Uses YouTube Data API v3 for video discovery
  - Filters: Must have closed captions, 4-20 minute duration
  - Ranking algorithm: View count (40%), Like ratio (30%), Relevance (20%), Recency (10%)
  - Diversity sampling: Max 2 videos per channel
  
- ✅ **Web Article Search Integration**
  - Uses DuckDuckGo Search (free, no API key required)
  - Domain authority scoring: .edu/.org domains prioritized
  - Ranking algorithm: Domain authority (50%), Relevance (30%), Recency (20%)
  - Diversity sampling: Max 2 articles per domain
  
- ✅ **Caching System**
  - SQLite table `source_discovery_cache` stores search results
  - TTL: 24 hours (configurable)
  - Cache key: SHA256(query + difficulty + params)
  
- ✅ **Pipeline Integration**
  - `run_course_creation_pipeline()` now uses automatic source discovery
  - Falls back gracefully if YouTube API unavailable
  - Supports both automatic (query-only) and manual (URLs) modes
  
- ✅ **API Endpoint Updates**
  - POST `/api/v1/courses/create` supports automatic discovery mode
  - If no URLs provided, automatically discovers sources
  - Clear error messages if discovery fails
  
**Configuration Required:**
- `YOUTUBE_API_KEY`: Required for YouTube search (get free key from Google Cloud Console)
- Optional: All discovery parameters configurable via `.env` file

**Dependencies Added:**
- `google-api-python-client==2.108.0` - YouTube Data API
- `duckduckgo-search==4.1.1` - Free web search

### Next Steps (Future Phases):

1. **Phase 2**: Implement vision processing with LLaVA
2. **Phase 3**: Add gamification (XP, badges, skill trees)
3. **Phase 4**: Full RAG chatbot implementation

---

# 12. SOURCE DISCOVERY SYSTEM (Claude - New Architecture)

## 12.1 Overview

**Purpose:** Automatically find relevant YouTube videos and web articles for a given query.

**Current Gap:** MVP requires manual URL input. This system enables true automation.

---

## 12.2 Architecture

### **Component: Source Discoverer**

**Location:** `backend/services/ingestion/source_discoverer.py`

**Function Signature:**
```python
def discover_sources(
    query: str,
    num_youtube: int = 5,
    num_articles: int = 3,
    difficulty: Optional[str] = None
) -> SourceDiscoveryResult:
    """
    Returns:
        SourceDiscoveryResult(
            youtube_urls: List[str],
            article_urls: List[str],
            metadata: Dict
        )
    """
```

---

## 12.3 YouTube Search Strategy

### **API: YouTube Data API v3**

**Endpoint:** `GET https://www.googleapis.com/youtube/v3/search`

**Search Parameters:**
```python
params = {
    "part": "snippet",
    "q": f"{query} tutorial explained",  # Query augmentation
    "type": "video",
    "videoCaption": "closedCaption",  # CRITICAL: Only videos with captions
    "videoDuration": "medium",  # 4-20 minutes (optimal for learning)
    "relevanceLanguage": "en",
    "maxResults": 25,  # Fetch more, then rank
    "order": "relevance"
}
```

**Query Augmentation Rules:**
- Beginner difficulty: `"{query} tutorial for beginners explained"`
- Intermediate: `"{query} tutorial explained"`
- Advanced: `"{query} deep dive advanced"`

**Ranking Algorithm:**
```
score = (
    0.4 * view_count_normalized +
    0.3 * like_ratio +
    0.2 * relevance_score (from API) +
    0.1 * recency_score
)
```

**Filters:**
- MUST have closed captions (transcripts required)
- Duration: 4-20 minutes (configurable)
- Language: English (Phase 1)
- Exclude: Shorts, music videos, ads

**Deduplication:**
- Check against cached sources in database
- Skip if URL already in `sources` table

---

## 12.4 Web Article Search Strategy

### **API Choice: SerpAPI (Google Custom Search alternative)**

**Why SerpAPI:**
- No Google API quota limits
- Easier to use than Google Custom Search
- Supports pagination
- Cost-effective for MVP

**Alternative (Free):** DuckDuckGo API via `duckduckgo-search` library

**Search Parameters:**
```python
params = {
    "q": f"{query} tutorial guide",
    "num": 20,
    "hl": "en",
    "gl": "us"
}
```

**Ranking Algorithm:**
```
score = (
    0.5 * domain_authority +  # Prefer .edu, .org, known tech blogs
    0.3 * relevance_score +
    0.2 * recency_score
)
```

**Domain Whitelist (High Authority):**
- Educational: `.edu`, `.ac.uk`
- Documentation: `docs.python.org`, `developer.mozilla.org`
- Trusted Tech: `medium.com`, `dev.to`, `stackoverflow.com`
- Official: Official project docs

**Content Validation:**
- Minimum word count: 500 words
- Must have readable text (not just images)
- Exclude: Paywalls, login-required content

---

## 12.5 Source Selection Logic

**Goal:** Diversity + Quality

**Algorithm:**
```python
def select_top_sources(
    youtube_candidates: List[Video],
    article_candidates: List[Article],
    num_youtube: int,
    num_articles: int
) -> SourceSelection:

    # Step 1: Remove duplicates (by URL)
    youtube_unique = deduplicate(youtube_candidates)
    article_unique = deduplicate(article_candidates)

    # Step 2: Score and rank
    youtube_ranked = sort_by_score(youtube_unique)
    article_ranked = sort_by_score(article_unique)

    # Step 3: Diversity sampling (avoid same channel/domain dominance)
    youtube_selected = diverse_sample(youtube_ranked, num_youtube, key="channel_id")
    article_selected = diverse_sample(article_ranked, num_articles, key="domain")

    return SourceSelection(
        youtube_urls=youtube_selected,
        article_urls=article_selected
    )
```

**Diversity Sampling:**
- No more than 2 videos from same channel
- No more than 2 articles from same domain
- Balances quality with source variety

---

## 12.6 Error Handling

**API Failures:**
- YouTube API down → Fallback to manual URLs + log error
- SerpAPI down → Fallback to DuckDuckGo search
- No results found → Return user-friendly error: "No sources found for '{query}'. Try a different search term."

**Partial Failures:**
- If YouTube succeeds but web search fails → Return YouTube results only
- If fewer than requested sources → Return what's available + warning

**Rate Limits:**
- YouTube API: 10,000 units/day (1 search = 100 units)
  - Implement: Request caching, query deduplication
- SerpAPI: 100 searches/month (free tier)
  - Implement: Cache search results for 24 hours

---

## 12.7 Caching Strategy

**Cache Layer:** SQLite table `source_discovery_cache`

```sql
CREATE TABLE source_discovery_cache (
    query_hash TEXT PRIMARY KEY,  -- SHA256(query + difficulty + params)
    query TEXT NOT NULL,
    youtube_results JSON,
    article_results JSON,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP  -- 24 hours from cached_at
);
```

**Cache Hit Logic:**
- If `query_hash` exists AND `expires_at > NOW()` → Return cached results
- Else → Perform fresh search + cache results

---

## 12.8 Configuration

**File:** `backend/core/config.py`

```python
class SourceDiscoveryConfig:
    YOUTUBE_API_KEY: str  # From environment variable
    SERPAPI_KEY: str  # From environment variable

    # Defaults
    DEFAULT_NUM_YOUTUBE: int = 5
    DEFAULT_NUM_ARTICLES: int = 3
    YOUTUBE_MIN_DURATION_SEC: int = 240  # 4 minutes
    YOUTUBE_MAX_DURATION_SEC: int = 1200  # 20 minutes
    ARTICLE_MIN_WORDS: int = 500
    CACHE_TTL_HOURS: int = 24

    # Ranking weights
    YOUTUBE_VIEW_WEIGHT: float = 0.4
    YOUTUBE_LIKE_WEIGHT: float = 0.3
    # ... etc
```

---

## 12.9 Integration with Existing Pipeline

**Updated Step 1 (Section 2.1):**

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: SOURCE DISCOVERY (NEW)                              │
│ Input: query="Machine Learning", num_sources=8              │
│                                                              │
│ 1. Call source_discoverer.discover_sources(query)          │
│ 2. YouTube Search:                                          │
│    - Query: "Machine Learning tutorial explained"          │
│    - Filter: videos with captions, 4-20 min                │
│    - Rank by: views, likes, relevance                      │
│    - Select top 5 (diverse channels)                       │
│ 3. Web Search:                                              │
│    - Query: "Machine Learning tutorial guide"              │
│    - Filter: .edu, docs, trusted domains                   │
│    - Rank by: domain authority, relevance                  │
│    - Select top 3 (diverse domains)                        │
│ 4. Return: List of 8 URLs (5 YouTube + 3 articles)         │
└─────────────────────────────────────────────────────────────┘
```

**API Endpoint Update:**

**POST /api/v1/courses/create** now supports TWO modes:

**Mode 1: Automatic (NEW)**
```json
{
  "query": "Machine Learning",
  "num_sources": 8,
  "difficulty": "beginner"
}
```
→ System automatically discovers sources

**Mode 2: Manual (Current MVP)**
```json
{
  "query": "Machine Learning",
  "youtube_urls": ["https://youtube.com/..."],
  "article_urls": ["https://example.com/..."]
}
```
→ System uses provided URLs

---

# 13. CONTRADICTION DETECTION & CONSENSUS ARCHITECTURE (Claude)

## 13.1 Overview

**Purpose:** Validate claims across sources and build consensus model.

**Current Gap:** Listed as placeholder. Needs full specification.

---

## 13.2 Architecture

### **Step 1: Claim Embedding**

**Component:** `backend/services/extraction/claim_embedder.py`

**Model:** Ollama `nomic-embed-text` (768 dimensions)

**Function:**
```python
def embed_claims(claims: List[Claim]) -> List[ClaimEmbedding]:
    """
    For each claim:
    1. Construct claim text: f"{subject} {predicate} {object}"
    2. Call Ollama embedding model
    3. Store embedding in database
    """
```

**Database Storage:**
```sql
-- Add to claims table
ALTER TABLE claims ADD COLUMN embedding BLOB;
```

---

### **Step 2: Similarity Detection**

**Component:** `backend/services/extraction/contradiction_detector.py`

**Algorithm:**
```python
def find_similar_claim_pairs(
    claims: List[Claim],
    similarity_threshold: float = 0.85
) -> List[ClaimPair]:
    """
    1. For each claim pair (i, j) where i.source_id != j.source_id:
       - Calculate cosine similarity between embeddings
       - If similarity >= threshold: Add to candidate pairs
    2. Return pairs sorted by similarity (descending)
    """
```

**Optimization:** Use FAISS or similar for fast similarity search if claim count > 1000.

---

### **Step 3: Contradiction Detection (LLM)**

**For each similar pair, call LLM with prompt from Section 5.4**

**Function:**
```python
def detect_contradiction(
    claim1: Claim,
    claim2: Claim
) -> ContradictionResult:
    """
    Returns:
        ContradictionResult(
            is_contradiction: bool,
            reasoning: str,
            confidence: float
        )
    """
```

**Prompt Enhancement (Add to Section 5.4):**
```
CONTEXT:
These claims are semantically similar (85%+ similarity).
Your job is to determine if they CONTRADICT each other.

CLAIM 1 (from {source_1}):
"{claim_1_text}"

CLAIM 2 (from {source_2}):
"{claim_2_text}"

ANALYSIS:
1. Do they make opposite statements about the same thing? (YES/NO)
2. Could both be true simultaneously? (YES/NO)
3. Are they about different aspects of the same topic? (YES/NO)

OUTPUT (JSON):
{
  "is_contradiction": true/false,
  "reasoning": "...",
  "confidence": 0.0-1.0
}
```

**Storage:**
- If contradiction: Insert into `contradictions` table
- Update both claims with `has_contradiction` flag

---

### **Step 4: Consensus Building**

**Component:** `backend/services/extraction/consensus_builder.py`

**Algorithm:**
```python
def build_consensus(claims: List[Claim]) -> List[ConsensusClaim]:
    """
    1. Group claims by semantic similarity (0.85+ threshold)
    2. For each group:
       a. Count agreeing sources
       b. Check for contradictions within group
       c. Calculate confidence score
       d. Merge into consensus claim
    """
```

**Confidence Scoring:**
```
confidence = (
    agreeing_sources / total_sources
) * (
    1 - controversy_penalty
)

Where:
- controversy_penalty = 0.3 if contradictions exist, else 0.0
```

**Output Schema:**
```python
@dataclass
class ConsensusClaim:
    claim_text: str
    subject: str
    predicate: str
    object: str
    source_ids: List[str]  # All sources that agree
    confidence: float  # 0.0 to 1.0
    is_controversial: bool
    contradiction_reasoning: Optional[str]
```

**Database Storage:**
```sql
CREATE TABLE consensus_claims (
    consensus_id TEXT PRIMARY KEY,
    claim_text TEXT NOT NULL,
    subject TEXT,
    predicate TEXT,
    object TEXT,
    source_ids JSON,  -- Array of source_id
    confidence REAL,
    is_controversial BOOLEAN DEFAULT FALSE,
    contradiction_reasoning TEXT
);
```

---

## 13.3 Integration with Pipeline

**Updated Step 5 & 6 (Section 2.1):**

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: CONTRADICTION DETECTION (UPDATED)                   │
│ 1. Embed all claims using nomic-embed-text                 │
│ 2. Find similar pairs (cosine similarity >= 0.85)          │
│ 3. For each similar pair:                                   │
│    - Call LLM to detect contradiction                      │
│    - Store result in contradictions table                  │
│ Output: Contradiction map                                   │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: CONSENSUS BUILDING (UPDATED)                        │
│ 1. Group claims by similarity                               │
│ 2. For each group:                                          │
│    - Count agreeing sources                                 │
│    - Calculate confidence: agreeing/total * controversy_adj│
│    - Create ConsensusClaim with source attributions       │
│ 3. Store consensus claims                                   │
│ Output: List of verified ConsensusClaims for course        │
└─────────────────────────────────────────────────────────────┘
```

---

# 14. ERROR HANDLING & RESILIENCE STRATEGY (Claude)

## 14.1 Principles

1. **Graceful Degradation:** Partial success > total failure
2. **Explicit Failures:** Clear error messages, no silent failures
3. **Retry Logic:** Transient failures auto-retry with exponential backoff
4. **Observability:** Log all errors with context

---

## 14.2 Error Categories

### **Category 1: External API Failures**

**Examples:** YouTube API down, Ollama unreachable, SerpAPI rate limit

**Strategy:**
- Retry with exponential backoff (1s, 2s, 4s)
- Max retries: 3
- If all retries fail: Log error + return user-friendly message

**Implementation Pattern:**
```python
@retry(max_attempts=3, backoff=exponential, exceptions=[APIError])
def call_external_api(...):
    pass
```

---

### **Category 2: LLM Output Parsing Failures**

**Examples:** Mixtral returns malformed JSON, missing fields

**Strategy:**
- Validate with Pydantic schema
- If parsing fails: Use fallback structure
- Log raw LLM output for debugging

**Example:**
```python
try:
    course_structure = parse_llm_json(llm_output)
except JSONDecodeError:
    logger.error(f"LLM returned invalid JSON: {llm_output}")
    course_structure = get_fallback_structure(query, claims)
```

---

### **Category 3: Resource Unavailability**

**Examples:** No YouTube results, no transcripts available

**Strategy:**
- Check preconditions before processing
- Return partial results if possible
- Clear error message to user

**Example:**
```python
if len(youtube_urls) == 0:
    raise NoSourcesFoundError(
        f"No YouTube videos with transcripts found for '{query}'. "
        f"Try a different search term or provide URLs manually."
    )
```

---

### **Category 4: Database Errors**

**Examples:** Connection timeout, constraint violation

**Strategy:**
- Use database transactions for multi-step operations
- Rollback on failure
- Retry connection errors once

---

## 14.3 Retry Decorator

**File:** `backend/core/retry.py`

```python
def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: Tuple = (Exception,)
):
    """
    Decorator for automatic retry with exponential backoff.

    Usage:
        @retry_with_backoff(max_retries=3, exceptions=(APIError,))
        def call_api():
            ...
    """
    # Implementation: exponential backoff = base_delay * (2 ** attempt)
```

---

## 14.4 Fallback Behaviors

**Fallback 1: Course Structure Generation**

If LLM fails → Use template structure:
```python
def get_fallback_course_structure(query: str, claims: List[Claim]):
    return {
        "sections": [
            {"title": "Overview", "content": f"Introduction to {query}..."},
            {"title": "Fundamentals", "content": format_claims(claims)},
            # ... basic structure
        ]
    }
```

**Fallback 2: Source Discovery**

If automatic search fails → Prompt user for manual URLs

**Fallback 3: Claim Extraction**

If LLM extraction fails → Store raw transcript as single "claim"

---

## 14.5 Logging Strategy

**Levels:**
- `DEBUG`: API requests/responses, LLM prompts/outputs
- `INFO`: Pipeline steps completed, sources found
- `WARNING`: Retries, partial failures
- `ERROR`: API failures, parsing errors
- `CRITICAL`: Database corruption, system unavailable

**File:** `backend/core/logger.py`

```python
import logging

logger = logging.getLogger("seikna")
logger.setLevel(logging.INFO)

# Format: [timestamp] [level] [module] message
```

---

# 15. ASYNC JOB PROCESSING SYSTEM (Claude)

## 15.1 Overview

**Purpose:** Handle long-running course creation asynchronously.

**Current Gap:** MVP is synchronous (blocks until complete). Need async for production.

---

## 15.2 Technology Choice: Redis + RQ (Redis Queue)

**Why RQ:**
- Lightweight (simpler than Celery)
- Python-native
- Good for MVP → Production transition
- Easy to monitor

**Alternative:** Celery (if more complex workflows needed later)

---

## 15.3 Architecture

### **Job Lifecycle:**

```
User submits query
    ↓
API creates job → stores in Redis → returns job_id
    ↓
Worker picks up job → runs pipeline → updates status
    ↓
Frontend polls /jobs/{job_id} → gets status/progress
    ↓
Job completes → frontend redirects to course
```

---

## 15.4 Job States

```python
class JobStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

**State Machine:**
```
QUEUED → PROCESSING → COMPLETED
                   ↘ FAILED
```

---

## 15.5 Database Schema

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,  -- 'queued', 'processing', 'completed', 'failed'
    query TEXT,
    progress INTEGER DEFAULT 0,  -- 0-100
    current_step TEXT,  -- "Fetching sources", "Extracting claims", etc.
    result_course_id TEXT,  -- NULL until completed
    error_message TEXT,  -- NULL unless failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 15.6 Worker Implementation

**File:** `backend/worker.py`

```python
from rq import Worker, Queue
from redis import Redis

redis_conn = Redis()
queue = Queue('course_creation', connection=redis_conn)

# Start worker
worker = Worker([queue], connection=redis_conn)
worker.work()
```

**Job Function:**
```python
def create_course_job(job_id: str, query: str, params: dict):
    """
    Runs in background worker.
    Updates job status in database as it progresses.
    """
    try:
        update_job_status(job_id, "processing", progress=0)

        # Step 1: Source discovery
        update_job_status(job_id, "processing", progress=10, step="Discovering sources")
        sources = discover_sources(query, **params)

        # Step 2: Ingestion
        update_job_status(job_id, "processing", progress=30, step="Fetching content")
        ingested = ingest_sources(sources)

        # Step 3: Claim extraction
        update_job_status(job_id, "processing", progress=50, step="Extracting knowledge")
        claims = extract_claims(ingested)

        # Step 4: Consensus
        update_job_status(job_id, "processing", progress=70, step="Building consensus")
        consensus = build_consensus(claims)

        # Step 5: Course building
        update_job_status(job_id, "processing", progress=90, step="Generating course")
        course_id = build_course(query, consensus)

        # Done
        update_job_status(job_id, "completed", progress=100, result=course_id)

    except Exception as e:
        update_job_status(job_id, "failed", error=str(e))
        logger.exception(f"Job {job_id} failed")
```

---

## 15.7 API Endpoint Updates

**POST /api/v1/courses/create** (Updated)

```python
@router.post("/create")
def create_course(request: CourseCreateRequest):
    # Create job
    job_id = str(uuid.uuid4())

    # Store in database
    db.insert_job(job_id, status="queued", query=request.query)

    # Enqueue job
    queue.enqueue(create_course_job, job_id, request.query, request.params)

    return {
        "job_id": job_id,
        "status": "queued",
        "estimated_time": 60
    }
```

**GET /api/v1/jobs/{job_id}** (Already exists, no changes needed)

---

## 15.8 Frontend Polling Strategy

**Component:** `frontend/lib/useJobPolling.ts`

```typescript
function useJobPolling(jobId: string) {
  const [status, setStatus] = useState('queued')
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const interval = setInterval(async () => {
      const job = await fetch(`/api/v1/jobs/${jobId}`)
      setStatus(job.status)
      setProgress(job.progress)

      if (job.status === 'completed') {
        clearInterval(interval)
        router.push(`/courses/${job.course_id}`)
      }
    }, 2000)  // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [jobId])

  return { status, progress }
}
```

---

# 16. PRIORITY TASKS FOR CURSOR (Claude - Updated 2025-12-08)

## 16.1 Implementation Priority Ranking

Based on architectural review, here are the next engineering tasks prioritized by impact and dependency:

---

### **🔴 PRIORITY 1 (CRITICAL): Source Discovery System**

**Why Critical:**
- MVP currently requires manual URL input
- Blocks true "automatic course construction" vision from PRD
- Highest user impact

**Implementation Scope:**

**Task 1.1: YouTube Search Integration**
- **File:** `backend/services/ingestion/source_discoverer.py`
- **Requirements:**
  - Set up YouTube Data API v3 credentials
  - Implement `search_youtube(query, num_results, difficulty)` function
  - Use search parameters from Section 12.3
  - Implement ranking algorithm (view count, like ratio, relevance)
  - Filter: Must have closed captions, 4-20 min duration
  - Implement diversity sampling (max 2 videos per channel)
  - Add deduplication against database cache

**Task 1.2: Web Article Search Integration**
- **File:** Same as above
- **Requirements:**
  - Choose: SerpAPI (paid) OR DuckDuckGo (free) - recommend DuckDuckGo for MVP
  - Implement `search_web_articles(query, num_results)` function
  - Implement domain whitelist scoring (.edu, docs, tech blogs)
  - Content validation: min 500 words
  - Diversity sampling (max 2 articles per domain)

**Task 1.3: Source Discovery Cache**
- **File:** `backend/db/schema.sql` (add table), `backend/services/ingestion/cache_manager.py`
- **Requirements:**
  - Create `source_discovery_cache` table (Section 12.7)
  - Implement cache hit/miss logic
  - TTL: 24 hours
  - Hash function: SHA256(query + difficulty + params)

**Task 1.4: API Endpoint Update**
- **File:** `backend/api/routes/courses.py`
- **Requirements:**
  - Modify `POST /api/v1/courses/create` to support two modes:
    - Mode 1 (automatic): `{query, num_sources, difficulty}` → auto-discover
    - Mode 2 (manual): `{query, youtube_urls, article_urls}` → use provided
  - Add validation: If mode 1 and discovery fails, return clear error

**Task 1.5: Configuration & Environment**
- **File:** `backend/core/config.py`, `.env`
- **Requirements:**
  - Add `YOUTUBE_API_KEY` to config
  - Add `SERPAPI_KEY` (or leave empty if using DuckDuckGo)
  - Add source discovery parameters (see Section 12.8)

**Estimated Effort:** 1-2 days
**Testing:** Verify automatic search for "Python tutorial" returns 5 valid YouTube URLs + 3 article URLs

---

### **🟡 PRIORITY 2 (HIGH): Error Handling & Resilience**

**Why High:**
- Production readiness requirement
- Current MVP has no error handling
- Prevents user frustration and debugging issues

**Task 2.1: Retry Decorator**
- **File:** `backend/core/retry.py`
- **Requirements:**
  - Implement `@retry_with_backoff` decorator (Section 14.3)
  - Exponential backoff: 1s, 2s, 4s
  - Max retries: 3
  - Support custom exception types

**Task 2.2: Apply Retry Logic**
- **Files:** All API calls to YouTube, SerpAPI, Ollama
- **Requirements:**
  - Wrap external API calls with `@retry_with_backoff`
  - Examples:
    - `youtube_fetcher.py`: `fetch_youtube_transcript()`
    - `ollama_client.py`: `call_mixtral()`
    - `source_discoverer.py`: API calls

**Task 2.3: Fallback Behaviors**
- **Files:** `backend/services/course_builder/structure_generator.py`
- **Requirements:**
  - Implement `get_fallback_course_structure()` (Section 14.4)
  - If LLM returns malformed JSON → use fallback template
  - Log raw LLM output for debugging

**Task 2.4: Logging Setup**
- **File:** `backend/core/logger.py`
- **Requirements:**
  - Configure Python logging module (Section 14.5)
  - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Format: `[timestamp] [level] [module] message`
  - Add logging throughout pipeline

**Task 2.5: User-Friendly Error Messages**
- **File:** `backend/api/routes/courses.py`
- **Requirements:**
  - Catch exceptions and return structured errors:
    ```json
    {
      "error": "NoSourcesFound",
      "message": "No YouTube videos with transcripts found for 'X'. Try different keywords."
    }
    ```

**Estimated Effort:** 1 day
**Testing:** Trigger errors (disconnect Ollama, invalid query) and verify graceful handling

---

### **🟢 PRIORITY 3 (MEDIUM): Contradiction Detection & Consensus**

**Why Medium:**
- Core feature for multi-source validation (PRD goal)
- Requires embeddings (need to install `nomic-embed-text`)
- Can function without it initially (just aggregate claims)

**Task 3.1: Claim Embedding**
- **File:** `backend/services/extraction/claim_embedder.py`
- **Requirements:**
  - Install Ollama model: `ollama pull nomic-embed-text`
  - Implement `embed_claims(claims)` function (Section 13.2)
  - For each claim: construct text, call Ollama, store embedding
  - Update database schema: Add `embedding BLOB` column to `claims` table

**Task 3.2: Similarity Detection**
- **File:** `backend/services/extraction/contradiction_detector.py`
- **Requirements:**
  - Implement `find_similar_claim_pairs(claims, threshold=0.85)`
  - Calculate cosine similarity between embeddings
  - Return pairs sorted by similarity
  - Optimization: Use numpy for vector operations

**Task 3.3: Contradiction Detection (LLM)**
- **File:** Same as above
- **Requirements:**
  - Implement `detect_contradiction(claim1, claim2)`
  - Use enhanced prompt from Section 13.2
  - Parse JSON output: `{is_contradiction, reasoning, confidence}`
  - Store in `contradictions` table

**Task 3.4: Consensus Building**
- **File:** `backend/services/extraction/consensus_builder.py`
- **Requirements:**
  - Implement `build_consensus(claims)` (Section 13.2)
  - Group claims by similarity
  - Count agreeing sources
  - Calculate confidence score with controversy penalty
  - Create `consensus_claims` table (Section 13.2)
  - Store consensus claims

**Task 3.5: Integrate into Pipeline**
- **File:** `backend/core/pipeline.py`
- **Requirements:**
  - After claim extraction, call:
    1. `embed_claims()`
    2. `find_similar_claim_pairs()`
    3. `detect_contradiction()` for similar pairs
    4. `build_consensus()`
  - Pass consensus claims (not raw claims) to course builder

**Estimated Effort:** 2 days
**Testing:** Create course from 3 sources, verify contradictions detected and consensus built

---

### **🔵 PRIORITY 4 (MEDIUM-LOW): Async Job Processing**

**Why Medium-Low:**
- MVP works synchronously
- Needed for production scale
- Can defer if timeline is tight

**Task 4.1: Redis + RQ Setup**
- **Files:** `requirements.txt`, `backend/worker.py`
- **Requirements:**
  - Install: `pip install redis rq`
  - Install Redis: `brew install redis` (Mac) or Docker
  - Create worker file (Section 15.6)

**Task 4.2: Job Database Schema**
- **File:** `backend/db/schema.sql`
- **Requirements:**
  - Create `jobs` table (Section 15.5)
  - Add job status enum

**Task 4.3: Background Job Function**
- **File:** `backend/core/pipeline.py`
- **Requirements:**
  - Extract pipeline logic into `create_course_job(job_id, query, params)`
  - Add progress tracking (Section 15.6)
  - Update job status at each step: 0% → 10% → 30% → 50% → 70% → 90% → 100%

**Task 4.4: Update API Endpoint**
- **File:** `backend/api/routes/courses.py`
- **Requirements:**
  - Modify `POST /api/v1/courses/create` to enqueue job instead of running inline
  - Return `job_id` immediately
  - Keep synchronous option for development/testing

**Task 4.5: Frontend Polling**
- **File:** `frontend/lib/useJobPolling.ts`
- **Requirements:**
  - Implement polling hook (Section 15.8)
  - Poll every 2 seconds
  - Show progress bar
  - Redirect to course when complete

**Estimated Effort:** 1-2 days
**Testing:** Submit long-running course creation, verify status updates and completion

---

### **🔵 PRIORITY 5 (LOW): Database Schema Updates**

**Why Low:**
- Small improvements to existing schema
- No blocking impact

**Task 5.1: Add Missing Columns**
- **File:** `backend/db/schema.sql`
- **Requirements:**
  - Add `embedding BLOB` to `claims` table
  - Create `consensus_claims` table
  - Create `source_discovery_cache` table
  - Create `jobs` table (if doing Priority 4)

**Task 5.2: Database Migration**
- **File:** `backend/db/migrations/002_add_consensus.sql`
- **Requirements:**
  - Write ALTER TABLE statements for existing database
  - Create migration runner script

**Estimated Effort:** 0.5 days

---

## 16.2 Recommended Implementation Order

### **Phase 1A: Core Automation (Week 1)**
1. Source Discovery System (Priority 1)
2. Error Handling & Resilience (Priority 2)

**Goal:** Users can submit query → system auto-discovers sources → builds course reliably

---

### **Phase 1B: Multi-Source Validation (Week 2)**
3. Contradiction Detection & Consensus (Priority 3)
4. Database Schema Updates (Priority 5)

**Goal:** Courses validate facts across sources and show confidence/contradictions

---

### **Phase 1C: Production Readiness (Week 3)**
5. Async Job Processing (Priority 4)

**Goal:** System handles concurrent requests and long-running jobs

---

## 16.3 Quick Wins (If Time-Constrained)

If Cursor has limited time, implement in this order:

1. **Source Discovery (YouTube only)** - Use DuckDuckGo for free, skip SerpAPI
2. **Basic Error Handling** - Just retry decorator + logging
3. **Skip Consensus for now** - Defer to Phase 2

This gives 80% of user value in 20% of effort.

---

## 16.4 Dependencies & Prerequisites

**Before Starting:**
- [ ] YouTube Data API key obtained (free tier)
- [ ] Ollama `nomic-embed-text` model installed: `ollama pull nomic-embed-text`
- [ ] Redis installed (if doing Priority 4)
- [ ] Python packages: `pip install google-api-python-client duckduckgo-search rq redis numpy`

---

## 16.5 Success Criteria

**Priority 1 Complete When:**
- User can input "Python tutorial" → system returns course without manual URLs
- At least 3 YouTube + 2 article sources found automatically

**Priority 2 Complete When:**
- All external API calls have retry logic
- Errors return user-friendly messages
- Logs capture all important events

**Priority 3 Complete When:**
- Claims are embedded and compared
- Contradictions are detected and stored
- Consensus claims are used in course building

**Priority 4 Complete When:**
- Course creation is async
- Frontend shows real-time progress
- Multiple concurrent requests work

---

**END OF PRIORITY TASKS SECTION**

---

# 12. PROMPTS / MODEL SETTINGS

## Ollama Models Required

```bash
ollama pull mixtral:latest
ollama pull llava:latest  # Phase 2
ollama pull nomic-embed-text:latest  # Phase 4 (RAG)
```

## Model Configuration

**Mixtral (Reasoning):**
- Temperature: 0.3 (factual tasks)
- Max tokens: 2048
- Use for: claim extraction, contradiction detection, course building

**LLaVA (Vision):**
- Temperature: 0.2
- Use for: frame analysis, visual claim extraction

**Nomic-Embed (Embeddings):**
- Dimensions: 768
- Use for: RAG retrieval

---

# 13. TODO / BACKLOG

## High Priority
- [ ] Implement MVP backend (Cursor)
- [ ] Create database schema (Cursor)
- [ ] Test ingestion pipeline (Cursor)
- [ ] Build basic frontend (Cursor)

## Medium Priority
- [ ] Implement VCT system (Phase 2)
- [ ] Add frame extraction (Phase 2)
- [ ] Implement gamification (Phase 3)

## Low Priority
- [ ] Optimize LLM prompts
- [ ] Add error handling
- [ ] Create admin dashboard
- [ ] Multi-language support

---

# 17. FULL COURSE GENERATION PIPELINE - ENHANCED ARCHITECTURE (Claude - 2025-12-08)

**Status:** Architecture Specification Complete
**Implementation Target:** Priority 2 Enhancement
**Estimated Implementation Effort:** 5-7 days

---

## 17.1 Overview & Purpose

**Current Gap:** MVP has basic claim extraction → course building, but lacks:
- Semantic chunking of transcripts
- Progressive expansion of content with LLM
- Multi-pass synthesis for quality
- Structured educational formatting
- Comprehensive quality validation
- Granular source citation tracking

**Enhanced Architecture Goals:**
1. Transform raw transcripts into semantically coherent chunks
2. Expand chunks with educational context using LLM
3. Extract structured knowledge (claims, definitions, examples)
4. Synthesize chunks into polished course sections
5. Validate quality at each stage
6. Maintain precise source attribution with timestamps

---

## 17.2 Pipeline Architecture

### Multi-Stage Processing Flow

```
RAW SOURCES (transcripts + articles)
    ↓
[STAGE 1] TRANSCRIPTION & NORMALIZATION
    ↓
[STAGE 2] SEMANTIC CHUNKING
    ↓
[STAGE 3] CHUNK EXPANSION (LLM)
    ↓
[STAGE 4] CLAIM EXTRACTION (from expanded chunks)
    ↓
[STAGE 5] CONSENSUS BUILDING (cross-source)
    ↓
[STAGE 6] COURSE STRUCTURE GENERATION
    ↓
[STAGE 7] SECTION SYNTHESIS
    ↓
[STAGE 8] QUALITY VALIDATION
    ↓
FINISHED COURSE
```

---

## 17.3 Data Models & JSON Schemas

### 17.3.1 RawTranscript

**Purpose:** Normalized representation of source content

**Python Dataclass:**
```python
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime

@dataclass
class TranscriptSegment:
    """Individual timed segment (for videos) or paragraph (for articles)"""
    text: str
    start_time_ms: Optional[int]  # None for articles
    end_time_ms: Optional[int]
    segment_id: str  # Unique identifier
    metadata: Dict[str, any]  # Speaker, confidence, etc.

@dataclass
class RawTranscript:
    """Complete source content"""
    source_id: str
    source_type: str  # 'youtube' | 'article'
    title: str
    url: str
    language: str  # ISO 639-1 code
    total_duration_ms: Optional[int]  # None for articles
    segments: List[TranscriptSegment]
    metadata: Dict[str, any]
    fetched_at: datetime

    # Computed properties
    @property
    def full_text(self) -> str:
        """Concatenated text from all segments"""
        return " ".join(seg.text for seg in self.segments)

    @property
    def word_count(self) -> int:
        """Total word count"""
        return len(self.full_text.split())
```

**JSON Schema Example:**
```json
{
  "source_id": "src_abc123",
  "source_type": "youtube",
  "title": "Introduction to Machine Learning",
  "url": "https://youtube.com/watch?v=...",
  "language": "en",
  "total_duration_ms": 720000,
  "segments": [
    {
      "text": "Welcome to this introduction to machine learning.",
      "start_time_ms": 0,
      "end_time_ms": 3500,
      "segment_id": "seg_001",
      "metadata": {"speaker": "instructor", "confidence": 0.98}
    }
  ],
  "metadata": {
    "author": "Tech Educator",
    "publish_date": "2025-01-15",
    "view_count": 150000,
    "like_ratio": 0.95
  },
  "fetched_at": "2025-12-08T10:30:00Z"
}
```

---

### 17.3.2 TranscriptChunk

**Purpose:** Semantically coherent segment for processing

**Python Dataclass:**
```python
@dataclass
class TranscriptChunk:
    """Semantic chunk of transcript"""
    chunk_id: str
    source_id: str
    chunk_index: int  # Position in sequence
    text: str
    start_time_ms: Optional[int]
    end_time_ms: Optional[int]
    word_count: int

    # Semantic metadata
    topic_keywords: List[str]  # Extracted key terms
    semantic_density: float  # 0.0-1.0, information density score

    # Context
    previous_chunk_id: Optional[str]
    next_chunk_id: Optional[str]

    # Quality metrics
    coherence_score: float  # 0.0-1.0
    completeness_score: float  # 0.0-1.0 (does chunk have complete thoughts?)
```

**JSON Schema Example:**
```json
{
  "chunk_id": "chunk_abc123_001",
  "source_id": "src_abc123",
  "chunk_index": 0,
  "text": "Machine learning is a subset of artificial intelligence...",
  "start_time_ms": 0,
  "end_time_ms": 45000,
  "word_count": 250,
  "topic_keywords": ["machine learning", "AI", "algorithms", "data"],
  "semantic_density": 0.82,
  "previous_chunk_id": null,
  "next_chunk_id": "chunk_abc123_002",
  "coherence_score": 0.91,
  "completeness_score": 0.95
}
```

---

### 17.3.3 ExpandedChunk

**Purpose:** LLM-enhanced chunk with educational structure

**Python Dataclass:**
```python
@dataclass
class ExpandedChunk:
    """Chunk expanded with LLM processing"""
    chunk_id: str
    source_chunk_id: str  # References TranscriptChunk

    # Core content
    original_text: str
    expanded_explanation: str  # LLM-generated elaboration

    # Structured extractions
    key_concepts: List[str]  # Main ideas
    definitions: Dict[str, str]  # Term -> definition
    examples: List[str]  # Concrete examples
    prerequisites: List[str]  # Required prior knowledge

    # Claims (atomic facts)
    claims: List[Dict[str, str]]  # [{subject, predicate, object, confidence}]

    # Educational metadata
    difficulty_level: str  # 'beginner' | 'intermediate' | 'advanced'
    cognitive_load: float  # 0.0-1.0

    # Processing metadata
    llm_model: str  # e.g., "mixtral:latest"
    expansion_timestamp: datetime
    token_count: int
```

**JSON Schema Example:**
```json
{
  "chunk_id": "exp_abc123_001",
  "source_chunk_id": "chunk_abc123_001",
  "original_text": "Machine learning is a subset of AI...",
  "expanded_explanation": "Machine learning represents a fundamental approach within artificial intelligence where systems learn patterns from data rather than following explicitly programmed rules...",
  "key_concepts": [
    "Machine learning definition",
    "Relationship to AI",
    "Learning from data",
    "Pattern recognition"
  ],
  "definitions": {
    "machine learning": "A method of data analysis that automates analytical model building using algorithms that iteratively learn from data",
    "supervised learning": "A type of ML where the model is trained on labeled data"
  },
  "examples": [
    "Email spam filtering learns from examples of spam vs. legitimate emails",
    "Image recognition systems trained on millions of labeled photos"
  ],
  "prerequisites": [
    "Basic programming concepts",
    "Understanding of algorithms"
  ],
  "claims": [
    {
      "subject": "Machine learning",
      "predicate": "is a subset of",
      "object": "artificial intelligence",
      "confidence": 0.98
    }
  ],
  "difficulty_level": "beginner",
  "cognitive_load": 0.45,
  "llm_model": "mixtral:latest",
  "expansion_timestamp": "2025-12-08T10:35:00Z",
  "token_count": 450
}
```

---

### 17.3.4 CourseSection

**Purpose:** Final structured course section with citations

**Python Dataclass:**
```python
@dataclass
class Citation:
    """Source attribution for content"""
    source_id: str
    source_type: str
    title: str
    url: str
    timestamp_ms: Optional[int]  # For video sources
    timestamp_formatted: Optional[str]  # "02:15" format
    relevance_score: float  # 0.0-1.0

@dataclass
class CourseSection:
    """Complete course section"""
    section_id: str
    course_id: str
    section_index: int  # Order in course

    # Content
    title: str
    subtitle: Optional[str]
    content: str  # Markdown formatted

    # Structure
    subsections: List['CourseSection']  # Recursive for nested sections

    # Educational elements
    key_takeaways: List[str]
    glossary_terms: Dict[str, str]
    practice_questions: List[Dict[str, any]]  # For quizzes

    # Source attribution
    citations: List[Citation]
    primary_sources: List[str]  # source_ids

    # Metadata
    estimated_reading_time_minutes: int
    difficulty_level: str
    prerequisites_section_ids: List[str]

    # Visual content (Phase 2)
    visual_elements: List[Dict[str, any]]  # Images, diagrams, frames

    # Quality metrics
    coherence_score: float
    coverage_score: float  # How well sources are represented
    confidence_score: float  # Based on source agreement

    # Flags
    has_contradictions: bool
    controversy_notes: Optional[str]
```

**JSON Schema Example:**
```json
{
  "section_id": "sec_course123_001",
  "course_id": "course_123",
  "section_index": 0,
  "title": "What is Machine Learning?",
  "subtitle": "Understanding the fundamentals",
  "content": "# What is Machine Learning?\n\nMachine learning is a subset of artificial intelligence...",
  "subsections": [],
  "key_takeaways": [
    "Machine learning enables computers to learn from data without explicit programming",
    "It is a subset of artificial intelligence",
    "Three main types: supervised, unsupervised, reinforcement learning"
  ],
  "glossary_terms": {
    "machine learning": "A method of data analysis that automates analytical model building",
    "supervised learning": "ML approach using labeled training data"
  },
  "practice_questions": [
    {
      "question": "What is the primary difference between traditional programming and machine learning?",
      "options": ["A", "B", "C", "D"],
      "correct": "B",
      "explanation": "..."
    }
  ],
  "citations": [
    {
      "source_id": "src_abc123",
      "source_type": "youtube",
      "title": "Introduction to Machine Learning",
      "url": "https://youtube.com/watch?v=...",
      "timestamp_ms": 15000,
      "timestamp_formatted": "00:15",
      "relevance_score": 0.95
    }
  ],
  "primary_sources": ["src_abc123", "src_def456"],
  "estimated_reading_time_minutes": 5,
  "difficulty_level": "beginner",
  "prerequisites_section_ids": [],
  "visual_elements": [],
  "coherence_score": 0.92,
  "coverage_score": 0.88,
  "confidence_score": 0.94,
  "has_contradictions": false,
  "controversy_notes": null
}
```

---

## 17.4 Module Architecture & File Layout

### Enhanced Directory Structure

```
backend/
├── services/
│   ├── processing/              # NEW DIRECTORY
│   │   ├── __init__.py
│   │   ├── transcriber.py       # NEW: Transcript normalization
│   │   ├── chunker.py           # NEW: Semantic chunking
│   │   ├── llm_expander.py      # NEW: Chunk expansion
│   │   ├── course_builder.py   # ENHANCED: Course assembly
│   │   ├── quality_validator.py # NEW: Validation gates
│   │   └── utils.py             # NEW: Shared utilities
│   ├── extraction/
│   │   ├── claim_extractor.py   # ENHANCED: Extract from ExpandedChunk
│   │   └── ...
│   └── ...
├── models/                       # NEW DIRECTORY
│   ├── __init__.py
│   ├── transcript_models.py     # NEW: RawTranscript, TranscriptChunk
│   ├── expansion_models.py      # NEW: ExpandedChunk
│   ├── course_models.py         # NEW: CourseSection, Citation
│   └── ...
└── ...
```

---

## 17.5 Module Specifications

### 17.5.1 transcriber.py

**Purpose:** Normalize raw source content into standardized RawTranscript format

**Function Signatures:**

```python
from typing import Dict, List
from models.transcript_models import RawTranscript, TranscriptSegment

def normalize_youtube_transcript(
    source_id: str,
    url: str,
    title: str,
    raw_vtt_content: str,
    metadata: Dict[str, any]
) -> RawTranscript:
    """
    Convert YouTube VTT/SRT transcript to RawTranscript.

    Processing:
        1. Parse VTT/SRT format
        2. Extract timestamps and text
        3. Clean text (remove speaker labels, formatting)
        4. Create TranscriptSegment objects
        5. Validate completeness
    """
    pass

def normalize_article_content(
    source_id: str,
    url: str,
    title: str,
    raw_html: str,
    metadata: Dict[str, any]
) -> RawTranscript:
    """
    Convert article HTML to RawTranscript.

    Processing:
        1. Extract main content (BeautifulSoup)
        2. Remove ads, navigation, footers
        3. Split into paragraphs
        4. Create TranscriptSegment per paragraph (no timestamps)
        5. Validate readability
    """
    pass

def validate_transcript(transcript: RawTranscript) -> Dict[str, any]:
    """
    Validate transcript quality.

    Returns:
        {
            "is_valid": bool,
            "word_count": int,
            "language_confidence": float,
            "issues": List[str],
            "quality_score": float  # 0.0-1.0
        }

    Validation checks:
        - Minimum word count (> 200)
        - Language detection confidence
        - Text coherence
        - No excessive repetition
    """
    pass

def merge_transcripts(transcripts: List[RawTranscript]) -> RawTranscript:
    """
    Merge multiple transcripts into one (for multi-part videos).

    Processing:
        1. Concatenate segments
        2. Adjust timestamps for sequential playback
        3. Merge metadata
    """
    pass
```

---

### 17.5.2 chunker.py

**Purpose:** Segment transcripts into semantically coherent chunks

**Class & Function Signatures:**

```python
from typing import List, Optional
from models.transcript_models import RawTranscript, TranscriptChunk

class SemanticChunker:
    """Stateful chunker with configurable strategy"""

    def __init__(
        self,
        target_chunk_size: int = 300,  # words
        min_chunk_size: int = 150,
        max_chunk_size: int = 500,
        overlap_size: int = 50,  # words for context preservation
        use_embeddings: bool = True
    ):
        """Initialize chunker with parameters"""
        pass

    def chunk_transcript(
        self,
        transcript: RawTranscript
    ) -> List[TranscriptChunk]:
        """
        Create semantic chunks from transcript.

        Algorithm:
            1. Sentence segmentation (spaCy or NLTK)
            2. If use_embeddings:
                a. Embed each sentence (nomic-embed-text)
                b. Find semantic boundaries (cosine distance jumps)
            3. Else:
                a. Use heuristics (paragraph breaks, punctuation)
            4. Group sentences into chunks
            5. Enforce size constraints
            6. Add overlap for context
            7. Extract topic keywords
            8. Calculate coherence scores
        """
        pass

    def extract_topic_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """
        Extract key terms from chunk text.

        Methods:
            - TF-IDF scoring
            - Noun phrase extraction
            - Named entity recognition
        """
        pass

    def calculate_coherence_score(self, chunk: TranscriptChunk) -> float:
        """
        Measure chunk coherence.

        Metrics:
            - Lexical cohesion (word overlap with context)
            - Sentence connectivity
            - Topic consistency

        Returns:
            Score 0.0-1.0
        """
        pass

    def calculate_semantic_density(self, text: str) -> float:
        """
        Estimate information density.

        Factors:
            - Unique concept count
            - Technical term frequency
            - Sentence complexity

        Returns:
            Score 0.0-1.0
        """
        pass

def rechunk_if_needed(
    chunks: List[TranscriptChunk],
    quality_threshold: float = 0.7
) -> List[TranscriptChunk]:
    """
    Re-chunk low-quality chunks.

    Checks:
        - Coherence score < threshold → merge with neighbors
        - Completeness score < threshold → expand boundaries
        - Size violations → split or merge
    """
    pass
```

---

### 17.5.3 llm_expander.py

**Purpose:** Expand chunks using LLM for educational enrichment

**Class & Function Signatures:**

```python
from typing import List, Dict, Optional
from models.transcript_models import TranscriptChunk
from models.expansion_models import ExpandedChunk

class ChunkExpander:
    """LLM-powered chunk expansion"""

    def __init__(
        self,
        model_name: str = "mixtral:latest",
        temperature: float = 0.3,
        max_tokens: int = 2048
    ):
        """Initialize with LLM configuration"""
        pass

    def expand_chunk(
        self,
        chunk: TranscriptChunk,
        context: Optional[Dict[str, any]] = None
    ) -> ExpandedChunk:
        """
        Expand single chunk with LLM.

        Processing:
            1. Build prompt (educational expansion)
            2. Add context if provided
            3. Call Mixtral
            4. Parse JSON response
            5. Validate output
            6. Extract claims, definitions, examples
            7. Calculate metadata
        """
        pass

    def expand_batch(
        self,
        chunks: List[TranscriptChunk],
        batch_size: int = 5,
        preserve_context: bool = True
    ) -> List[ExpandedChunk]:
        """
        Expand multiple chunks efficiently.

        Optimization:
            - Batch LLM calls when possible
            - Cache embeddings
            - Parallel processing
        """
        pass

    def extract_claims_from_expansion(
        self,
        expanded_chunk: ExpandedChunk
    ) -> List[Dict[str, str]]:
        """
        Extract atomic knowledge claims from expansion.

        Returns:
            List of {subject, predicate, object, confidence} dicts
        """
        pass

    def calculate_difficulty_level(
        self,
        text: str,
        terminology: List[str]
    ) -> str:
        """
        Determine difficulty level.

        Factors:
            - Flesch-Kincaid grade level
            - Technical term density
            - Sentence complexity
            - Prerequisite depth

        Returns:
            'beginner' | 'intermediate' | 'advanced'
        """
        pass

    def calculate_cognitive_load(
        self,
        expanded_chunk: ExpandedChunk
    ) -> float:
        """
        Estimate cognitive load.

        Factors:
            - Concept count
            - Definition density
            - Prerequisite count
            - Sentence complexity

        Returns:
            Score 0.0-1.0 (0=easy, 1=very demanding)
        """
        pass

def build_expansion_prompt(
    chunk_text: str,
    topic: str,
    previous_context: Optional[str] = None
) -> str:
    """
    Construct LLM prompt for chunk expansion.

    Template includes:
        - Role definition
        - Task description
        - Output format (JSON)
        - Rules (no hallucination, preserve facts)
        - Examples
    """
    pass
```

---

### 17.5.4 course_builder.py (Enhanced)

**Purpose:** Assemble expanded chunks into structured course sections

**Class & Function Signatures:**

```python
from typing import List, Dict, Optional
from models.expansion_models import ExpandedChunk
from models.course_models import CourseSection, Citation

class CourseBuilder:
    """Orchestrates course assembly from processed chunks"""

    def __init__(
        self,
        model_name: str = "mixtral:latest",
        temperature: float = 0.4
    ):
        """Initialize with LLM configuration"""
        pass

    def generate_course_structure(
        self,
        query: str,
        expanded_chunks: List[ExpandedChunk],
        sources: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        Generate high-level course outline.

        Returns:
            {
              "title": str,
              "description": str,
              "sections": [{"title": str, "subsections": [...]}],
              "prerequisites": List[str],
              "estimated_duration_minutes": int
            }

        Processing:
            1. Analyze all expanded chunks
            2. Identify main topics
            3. Group related concepts
            4. Order by pedagogical flow (prerequisites → advanced)
            5. Generate section hierarchy
        """
        pass

    def synthesize_section(
        self,
        section_title: str,
        relevant_chunks: List[ExpandedChunk],
        section_index: int,
        course_id: str
    ) -> CourseSection:
        """
        Create single CourseSection from chunks.

        Processing:
            1. Merge chunk content coherently
            2. Remove redundancy
            3. Add transitions between chunks
            4. Extract glossary terms
            5. Generate key takeaways
            6. Create practice questions
            7. Add citations
            8. Calculate metadata
        """
        pass

    def create_citations(
        self,
        chunks: List[ExpandedChunk],
        sources: List[Dict[str, any]]
    ) -> List[Citation]:
        """
        Generate source citations for section.

        Processing:
            1. Map chunks → sources
            2. Extract timestamps (for videos)
            3. Calculate relevance scores
            4. Deduplicate citations
            5. Sort by relevance
        """
        pass

    def generate_key_takeaways(
        self,
        section_content: str,
        chunks: List[ExpandedChunk]
    ) -> List[str]:
        """
        Extract main points from section.

        Method:
            - Identify most important claims
            - LLM summarization
            - Limit: 3-5 takeaways per section
        """
        pass

    def generate_practice_questions(
        self,
        section: CourseSection,
        difficulty: str = "mixed",
        count: int = 3
    ) -> List[Dict[str, any]]:
        """
        Create quiz questions for section.

        Returns:
            [
              {
                "question": str,
                "options": [str, str, str, str],
                "correct": str,  # Letter: A, B, C, D
                "explanation": str
              }
            ]
        """
        pass

    def merge_sections(
        self,
        sections: List[CourseSection],
        structure: Dict[str, any]
    ) -> List[CourseSection]:
        """
        Organize sections into final hierarchy.

        Processing:
            1. Apply structure (nested subsections)
            2. Resolve cross-references
            3. Add navigation links
            4. Validate prerequisite ordering
        """
        pass

    def calculate_section_scores(
        self,
        section: CourseSection,
        consensus_claims: List[Dict[str, any]]
    ) -> Dict[str, float]:
        """
        Calculate quality metrics for section.

        Returns:
            {
              "coherence_score": float,  # Text flow quality
              "coverage_score": float,   # How well sources represented
              "confidence_score": float  # Claim agreement
            }
        """
        pass

def build_complete_course(
    query: str,
    sources: List[RawTranscript],
    consensus_claims: List[Dict[str, any]],
    config: Optional[Dict[str, any]] = None
) -> Dict[str, any]:
    """
    Main orchestration function.

    Full pipeline:
        1. Chunk all transcripts
        2. Expand chunks with LLM
        3. Generate course structure
        4. Synthesize sections
        5. Validate quality
        6. Return complete course

    Returns:
        {
          "course_id": str,
          "title": str,
          "description": str,
          "sections": List[CourseSection],
          "metadata": {...},
          "quality_report": {...}
        }
    """
    pass
```

---

### 17.5.5 quality_validator.py

**Purpose:** Validate course quality at each stage

**Class & Function Signatures:**

```python
from typing import Dict, List, Tuple
from models.course_models import CourseSection

class QualityValidator:
    """Multi-stage validation"""

    def validate_chunk_quality(
        self,
        chunk: TranscriptChunk,
        min_coherence: float = 0.7,
        min_completeness: float = 0.6
    ) -> Tuple[bool, List[str]]:
        """
        Validate chunk meets quality standards.

        Returns:
            (is_valid, issues_list)

        Checks:
            - Coherence score >= threshold
            - Completeness score >= threshold
            - Size within bounds
            - No excessive repetition
        """
        pass

    def validate_expansion_quality(
        self,
        expanded: ExpandedChunk,
        min_claims: int = 2,
        max_cognitive_load: float = 0.9
    ) -> Tuple[bool, List[str]]:
        """
        Validate expansion quality.

        Checks:
            - Has minimum claims count
            - Cognitive load not excessive
            - Definitions present for technical terms
            - Examples provided
        """
        pass

    def validate_section_quality(
        self,
        section: CourseSection,
        min_word_count: int = 200,
        min_citations: int = 1
    ) -> Tuple[bool, List[str]]:
        """
        Validate section quality.

        Checks:
            - Minimum word count
            - Has citations
            - Has key takeaways
            - Coherence score acceptable
            - No broken references
        """
        pass

    def generate_quality_report(
        self,
        course: Dict[str, any]
    ) -> Dict[str, any]:
        """
        Generate comprehensive quality report.

        Returns:
            {
              "overall_score": float,
              "section_scores": {...},
              "issues": [...],
              "recommendations": [...]
            }
        """
        pass
```

---

### 17.5.6 utils.py

**Purpose:** Shared utilities for processing pipeline

**Function Signatures:**

```python
from typing import List, Dict, Optional, Tuple
import numpy as np

def calculate_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Cosine similarity between vectors"""
    pass

def embed_text(
    text: str,
    model: str = "nomic-embed-text"
) -> np.ndarray:
    """Get embedding vector for text via Ollama"""
    pass

def embed_batch(
    texts: List[str],
    model: str = "nomic-embed-text",
    batch_size: int = 32
) -> List[np.ndarray]:
    """Batch embedding for efficiency"""
    pass

def clean_text(text: str) -> str:
    """
    Normalize text.

    Operations:
        - Remove extra whitespace
        - Fix encoding issues
        - Normalize punctuation
        - Remove speaker labels
    """
    pass

def format_timestamp(milliseconds: int) -> str:
    """Convert milliseconds to MM:SS format"""
    pass

def calculate_reading_time(text: str, wpm: int = 200) -> int:
    """Estimate reading time in minutes"""
    pass

def extract_markdown_headings(markdown: str) -> List[Dict[str, str]]:
    """Parse markdown headings for navigation"""
    pass

def merge_overlapping_chunks(
    chunks: List[TranscriptChunk],
    overlap_size: int
) -> str:
    """Merge chunks while removing overlap"""
    pass

def detect_language(text: str) -> Tuple[str, float]:
    """
    Detect text language.

    Returns:
        (language_code, confidence)
    """
    pass

def calculate_flesch_kincaid_grade(text: str) -> float:
    """Calculate readability grade level"""
    pass

def extract_technical_terms(
    text: str,
    threshold: float = 0.7
) -> List[str]:
    """
    Identify technical/domain-specific terms.

    Method:
        - Compare to general English vocabulary
        - Check term frequency
        - Use POS tagging
    """
    pass
```

---

## 17.6 Complete Pipeline Flow Diagram

```
INPUT: query="Machine Learning", sources=[url1, url2, ...]

┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: TRANSCRIPTION & NORMALIZATION                         │
├─────────────────────────────────────────────────────────────────┤
│ For each source:                                                │
│   1. Fetch content (already done by ingestion service)         │
│   2. Call normalize_youtube_transcript() OR                    │
│      normalize_article_content()                               │
│   3. Get RawTranscript object                                  │
│   4. Validate with validate_transcript()                       │
│   5. Store in database                                          │
│                                                                  │
│ Output: List[RawTranscript]                                     │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: SEMANTIC CHUNKING                                      │
├─────────────────────────────────────────────────────────────────┤
│ For each RawTranscript:                                         │
│   1. Initialize SemanticChunker(                               │
│        target_chunk_size=300,                                  │
│        overlap_size=50,                                         │
│        use_embeddings=True                                     │
│      )                                                          │
│   2. Call chunker.chunk_transcript(transcript)                 │
│   3. Get List[TranscriptChunk]                                 │
│   4. For each chunk:                                            │
│      a. Calculate coherence_score                              │
│      b. Calculate semantic_density                             │
│      c. Extract topic_keywords                                 │
│   5. Call rechunk_if_needed() for quality control              │
│   6. Store chunks in database                                   │
│                                                                  │
│ Output: List[TranscriptChunk] (all sources combined)           │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: CHUNK EXPANSION (LLM)                                 │
├─────────────────────────────────────────────────────────────────┤
│ Initialize ChunkExpander(model="mixtral:latest")               │
│                                                                  │
│ For each TranscriptChunk:                                       │
│   1. Build context from previous chunks                        │
│   2. Call expander.expand_chunk(chunk, context)                │
│   3. LLM generates:                                             │
│      - expanded_explanation                                    │
│      - key_concepts                                             │
│      - definitions                                              │
│      - examples                                                 │
│      - prerequisites                                            │
│      - atomic claims                                            │
│   4. Calculate difficulty_level                                │
│   5. Calculate cognitive_load                                  │
│   6. Validate with validator.validate_expansion_quality()      │
│   7. Store ExpandedChunk in database                           │
│                                                                  │
│ Optimization: Use expander.expand_batch() for efficiency       │
│                                                                  │
│ Output: List[ExpandedChunk]                                     │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 4: CLAIM EXTRACTION                                      │
├─────────────────────────────────────────────────────────────────┤
│ For each ExpandedChunk:                                         │
│   1. Extract claims from expansion                             │
│   2. Store in claims table with:                               │
│      - (subject, predicate, object)                            │
│      - source_id                                                │
│      - confidence score                                         │
│      - timestamp (if video)                                    │
│                                                                  │
│ Output: List[Claim] stored in database                         │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 5: CONSENSUS BUILDING                                    │
├─────────────────────────────────────────────────────────────────┤
│ (Use existing consensus_builder.py - Section 13 architecture)  │
│                                                                  │
│ 1. Embed all claims                                             │
│ 2. Find similar claim pairs (cosine similarity >= 0.85)        │
│ 3. Detect contradictions with LLM                              │
│ 4. Group claims by similarity                                  │
│ 5. Calculate confidence scores                                 │
│ 6. Create consensus claims                                      │
│                                                                  │
│ Output: List[ConsensusClaim]                                    │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 6: COURSE STRUCTURE GENERATION                           │
├─────────────────────────────────────────────────────────────────┤
│ Initialize CourseBuilder()                                      │
│                                                                  │
│ 1. Call builder.generate_course_structure(                     │
│      query=query,                                               │
│      expanded_chunks=all_expanded_chunks,                      │
│      sources=all_sources                                        │
│    )                                                            │
│ 2. LLM analyzes all content and generates:                     │
│    {                                                            │
│      "title": "...",                                            │
│      "description": "...",                                      │
│      "sections": [                                              │
│        {"title": "Overview", "subsections": []},               │
│        {"title": "Fundamentals", "subsections": [...]},        │
│        ...                                                      │
│      ],                                                         │
│      "prerequisites": [...],                                    │
│      "estimated_duration_minutes": 240                         │
│    }                                                            │
│ 3. Store structure in database                                 │
│                                                                  │
│ Output: Course structure Dict                                   │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 7: SECTION SYNTHESIS                                     │
├─────────────────────────────────────────────────────────────────┤
│ For each section in structure:                                 │
│   1. Identify relevant ExpandedChunks (by topic keywords)      │
│   2. Call builder.synthesize_section(                          │
│        section_title=section["title"],                         │
│        relevant_chunks=matched_chunks,                         │
│        section_index=i,                                         │
│        course_id=course_id                                      │
│      )                                                          │
│   3. Synthesize:                                                │
│      a. Merge chunk content with transitions                   │
│      b. Remove redundancy                                       │
│      c. Format as markdown                                      │
│      d. Extract glossary terms                                  │
│      e. Generate key_takeaways                                  │
│      f. Create practice_questions                              │
│      g. Add citations with timestamps                          │
│      h. Calculate quality scores                               │
│   4. Validate with validator.validate_section_quality()        │
│   5. Store CourseSection in database                           │
│                                                                  │
│ Output: List[CourseSection]                                     │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 8: QUALITY VALIDATION & FINALIZATION                     │
├─────────────────────────────────────────────────────────────────┤
│ 1. Call validator.generate_quality_report(course)              │
│ 2. Check overall quality metrics:                              │
│    - All sections have min word count                          │
│    - All sections have citations                               │
│    - Coherence scores acceptable                               │
│    - No broken references                                      │
│ 3. If issues found:                                             │
│    - Log warnings                                               │
│    - Flag for review                                            │
│    - Auto-fix if possible                                      │
│ 4. Merge sections with builder.merge_sections()                │
│ 5. Store final course in database                              │
│ 6. Return course_id to API                                      │
│                                                                  │
│ Output: Complete Course ready for frontend                     │
└─────────────────────────────────────────────────────────────────┘
    ↓
FINAL OUTPUT: {course_id, title, sections, metadata, quality_report}
```

---

## 17.7 Chunking & Expansion Rules

### 17.7.1 Chunking Rules

**Size Constraints:**
- **Target size:** 300 words (optimal for LLM processing)
- **Minimum size:** 150 words (avoid fragments)
- **Maximum size:** 500 words (prevent overwhelming LLM)
- **Overlap:** 50 words between chunks (preserve context)

**Boundary Detection:**

**Method 1: Embedding-based (Preferred)**
1. Split transcript into sentences
2. Embed each sentence (nomic-embed-text)
3. Calculate cosine similarity between consecutive sentences
4. Identify boundary where similarity drops significantly (> 0.3 change)
5. This indicates topic shift

**Method 2: Heuristic-based (Fallback)**
1. Paragraph breaks (strong signal)
2. Section headings in articles
3. Long pauses in video transcripts (> 2 seconds)
4. Punctuation patterns (. ? ! followed by capital letter)

**Quality Thresholds:**
- **Coherence score** >= 0.7 (otherwise merge with neighbors)
- **Completeness score** >= 0.6 (no incomplete thoughts)
- **Semantic density** >= 0.3 (not too sparse)

**Special Cases:**
- **Code blocks:** Keep together even if > 500 words
- **Lists/enumerations:** Don't split mid-list
- **Mathematical proofs:** Keep complete
- **Quotes:** Preserve attribution

---

### 17.7.2 Expansion Rules

**Expansion Goals:**
1. **Clarify:** Explain complex concepts in simpler terms
2. **Contextualize:** Add background and prerequisites
3. **Exemplify:** Provide concrete examples
4. **Define:** Create glossary entries for technical terms
5. **Structure:** Extract atomic claims

**LLM Parameters:**
- **Model:** Mixtral (8x7B)
- **Temperature:** 0.3 (factual, low creativity)
- **Max tokens:** 2048
- **Top-p:** 0.9

**Output Structure Requirements:**
```json
{
  "expanded_explanation": "500-800 words",
  "key_concepts": "3-7 concepts",
  "definitions": "All technical terms",
  "examples": "2-4 concrete examples",
  "prerequisites": "0-5 prior knowledge items",
  "claims": "5-15 atomic facts"
}
```

**Validation Rules:**
- **Minimum claims:** 2 per chunk (otherwise re-expand)
- **Definition coverage:** >= 80% of technical terms
- **Example requirement:** >= 1 example per key concept
- **Cognitive load:** <= 0.9 (otherwise simplify)

**Prohibited Actions:**
- **No hallucination:** Only expand what's in original
- **No opinions:** Remain factual
- **No speculation:** Stick to stated facts
- **No style changes:** Maintain academic tone

---

## 17.8 Model Usage Specification

### 17.8.1 Mixtral Usage

**Where Used:**
1. **Chunk Expansion** (Stage 3)
2. **Course Structure Generation** (Stage 6)
3. **Section Synthesis** (Stage 7)
4. **Contradiction Detection** (Stage 5 - existing)

**Configuration:**
```python
{
  "model": "mixtral:latest",
  "temperature": 0.3,  # Factual tasks
  "max_tokens": 2048,
  "top_p": 0.9,
  "frequency_penalty": 0.0,
  "presence_penalty": 0.0
}
```

**Prompt Engineering Principles:**
- **Role definition:** "You are an expert educator..."
- **Task clarity:** "TASK: Extract claims..."
- **Format specification:** "OUTPUT (JSON): {...}"
- **Rules/constraints:** "RULES: 1. No hallucination..."
- **Examples:** Show desired output format

**Rate Limiting:**
- Max 10 concurrent requests to Ollama
- Batch processing when possible
- Cache responses for identical prompts

---

### 17.8.2 Nomic-Embed-Text Usage

**Where Used:**
1. **Semantic Chunking** (Stage 2)
2. **Claim Similarity** (Stage 5 - existing)
3. **Topic Clustering** (Stage 6)

**Configuration:**
```python
{
  "model": "nomic-embed-text",
  "dimensions": 768,
  "normalize": True  # Unit vectors
}
```

**Embedding Strategy:**
- **Batch size:** 32 texts per call
- **Cache:** Store embeddings in database
- **Similarity metric:** Cosine similarity

**Use Cases:**
- **Chunk boundary detection:** Embed sentences, find similarity drops
- **Claim deduplication:** Find similar claims (threshold = 0.85)
- **Content clustering:** Group related chunks by topic

---

### 17.8.3 LLaVA Usage (Phase 2)

**Where Used:**
- **Visual claim extraction** (not in Priority 2, but specified for future)

**Configuration:**
```python
{
  "model": "llava:latest",
  "temperature": 0.2,
  "max_tokens": 1024
}
```

**Deferred to Phase 2:** Vision processing pipeline

---

## 17.9 Database Schema Updates

### New Tables Required

```sql
-- Store normalized transcripts
CREATE TABLE raw_transcripts (
    transcript_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    full_text TEXT NOT NULL,
    segment_count INTEGER,
    word_count INTEGER,
    language TEXT,
    quality_score REAL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

-- Store transcript segments
CREATE TABLE transcript_segments (
    segment_id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    segment_index INTEGER,
    text TEXT NOT NULL,
    start_time_ms INTEGER,
    end_time_ms INTEGER,
    metadata JSON,
    FOREIGN KEY (transcript_id) REFERENCES raw_transcripts(transcript_id)
);

-- Store semantic chunks
CREATE TABLE transcript_chunks (
    chunk_id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    chunk_index INTEGER,
    text TEXT NOT NULL,
    word_count INTEGER,
    start_time_ms INTEGER,
    end_time_ms INTEGER,
    topic_keywords JSON,  -- Array of keywords
    semantic_density REAL,
    coherence_score REAL,
    completeness_score REAL,
    previous_chunk_id TEXT,
    next_chunk_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transcript_id) REFERENCES raw_transcripts(transcript_id)
);

-- Store expanded chunks
CREATE TABLE expanded_chunks (
    expanded_id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    original_text TEXT NOT NULL,
    expanded_explanation TEXT NOT NULL,
    key_concepts JSON,  -- Array
    definitions JSON,   -- Object {term: definition}
    examples JSON,      -- Array
    prerequisites JSON, -- Array
    difficulty_level TEXT,
    cognitive_load REAL,
    llm_model TEXT,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES transcript_chunks(chunk_id)
);

-- Store course sections
CREATE TABLE course_sections (
    section_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    parent_section_id TEXT,  -- For nested sections
    section_index INTEGER,
    title TEXT NOT NULL,
    subtitle TEXT,
    content TEXT NOT NULL,  -- Markdown
    key_takeaways JSON,
    glossary_terms JSON,
    practice_questions JSON,
    estimated_reading_minutes INTEGER,
    difficulty_level TEXT,
    coherence_score REAL,
    coverage_score REAL,
    confidence_score REAL,
    has_contradictions BOOLEAN DEFAULT FALSE,
    controversy_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (parent_section_id) REFERENCES course_sections(section_id)
);

-- Store section citations
CREATE TABLE section_citations (
    citation_id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    timestamp_ms INTEGER,
    timestamp_formatted TEXT,
    relevance_score REAL,
    FOREIGN KEY (section_id) REFERENCES course_sections(section_id),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

-- Update claims table (add link to expanded chunk)
ALTER TABLE claims ADD COLUMN expanded_chunk_id TEXT;
ALTER TABLE claims ADD FOREIGN KEY (expanded_chunk_id) REFERENCES expanded_chunks(expanded_id);
```

---

## 17.10 Configuration Parameters

**File:** `backend/core/config.py`

```python
class CourseGenerationConfig:
    """Configuration for course generation pipeline"""

    # Chunking parameters
    CHUNK_TARGET_SIZE: int = 300  # words
    CHUNK_MIN_SIZE: int = 150
    CHUNK_MAX_SIZE: int = 500
    CHUNK_OVERLAP_SIZE: int = 50
    USE_EMBEDDING_CHUNKING: bool = True

    # Quality thresholds
    MIN_COHERENCE_SCORE: float = 0.7
    MIN_COMPLETENESS_SCORE: float = 0.6
    MIN_SEMANTIC_DENSITY: float = 0.3

    # Expansion parameters
    EXPANSION_MODEL: str = "mixtral:latest"
    EXPANSION_TEMPERATURE: float = 0.3
    EXPANSION_MAX_TOKENS: int = 2048
    MIN_CLAIMS_PER_CHUNK: int = 2
    MAX_COGNITIVE_LOAD: float = 0.9

    # Section parameters
    MIN_SECTION_WORD_COUNT: int = 200
    MIN_CITATIONS_PER_SECTION: int = 1
    TARGET_TAKEAWAYS_PER_SECTION: int = 3
    TARGET_QUESTIONS_PER_SECTION: int = 3

    # Processing optimization
    LLM_BATCH_SIZE: int = 5
    EMBEDDING_BATCH_SIZE: int = 32
    MAX_CONCURRENT_LLM_CALLS: int = 10

    # Validation
    ENABLE_QUALITY_VALIDATION: bool = True
    FAIL_ON_LOW_QUALITY: bool = False  # Log warnings instead
```

---

## 17.11 Error Handling Strategy

### Stage-Specific Error Handling

**Stage 1: Transcription**
- **Error:** Invalid transcript format
- **Action:** Try alternative parser, log error, skip source
- **Fallback:** Use raw text if available

**Stage 2: Chunking**
- **Error:** Cannot create valid chunks
- **Action:** Fall back to heuristic chunking (no embeddings)
- **Fallback:** Use fixed-size chunks (300 words)

**Stage 3: Expansion**
- **Error:** LLM returns malformed JSON
- **Action:** Retry once, then use minimal expansion
- **Fallback:** Store original chunk as expansion

**Stage 4-5: Claims & Consensus**
- **Error:** Embedding model unavailable
- **Action:** Skip consensus, use simple claim aggregation
- **Fallback:** All claims treated as equal confidence

**Stage 6-7: Course Building**
- **Error:** LLM fails to generate structure
- **Action:** Use template structure (Section 1, 2, 3...)
- **Fallback:** Sections = topics from chunk keywords

**Stage 8: Validation**
- **Error:** Quality below threshold
- **Action:** Log warnings, flag for review, continue
- **Fallback:** Mark course as "draft" status

---

## 17.12 Performance Optimization

### Optimization Strategies

**Parallel Processing:**
- Chunk expansion: Process multiple chunks concurrently (batch_size=5)
- Embedding: Batch embed 32 texts per call
- Section synthesis: Parallelize independent sections

**Caching:**
- Cache LLM responses (prompt hash → response)
- Cache embeddings (text hash → vector)
- Cache chunk analysis results

**Database Optimization:**
- Index: chunk_id, source_id, course_id
- Store embeddings as BLOB (not JSON)
- Use transactions for batch inserts

**Memory Management:**
- Stream large transcripts
- Process one course at a time (no multi-course parallel)
- Clear embedding cache after course completion

---

## 17.13 Testing Strategy

### Unit Tests Required

**transcriber.py:**
- Test VTT parsing with sample files
- Test HTML article extraction
- Test language detection
- Test quality validation

**chunker.py:**
- Test chunk size constraints
- Test overlap preservation
- Test coherence scoring
- Test boundary detection

**llm_expander.py:**
- Test prompt construction
- Test JSON parsing
- Test claim extraction
- Test difficulty calculation

**course_builder.py:**
- Test structure generation
- Test section synthesis
- Test citation creation
- Test quality scoring

### Integration Tests

**Full Pipeline:**
1. Input: 2 YouTube URLs + 1 article URL
2. Expected: Complete course with 5-8 sections
3. Validate: All sections have citations, takeaways, questions
4. Check: Quality scores >= thresholds

**Edge Cases:**
- Empty transcript
- Very short transcript (< 200 words)
- Very long transcript (> 10,000 words)
- Non-English content
- Contradictory sources

---

## 17.14 Migration from Current MVP

### Transition Plan

**Current State:**
- Basic claim extraction directly from transcripts
- Simple course structure generation

**Migration Steps:**

**Step 1:** Add new database tables (Section 17.9)

**Step 2:** Implement processing modules (transcriber → chunker → expander)

**Step 3:** Update pipeline.py to use new flow

**Step 4:** Keep old flow as fallback (config flag: USE_NEW_PIPELINE)

**Step 5:** A/B test both pipelines

**Step 6:** Deprecate old flow after validation

**Backwards Compatibility:**
- Old courses remain unchanged
- New courses use enhanced pipeline
- API responses identical format

---

## 17.15 Success Criteria

### Quality Metrics

**Course must achieve:**
- Overall coherence score >= 0.85
- All sections have >= 1 citation
- >= 80% of technical terms defined
- >= 70% source coverage (claims used in final course)
- Reading time estimate within 20% of actual

**Performance Targets:**
- Pipeline completion: < 3 minutes for 5 sources
- LLM calls: < 100 per course
- Memory usage: < 2GB peak

**User Satisfaction:**
- Course structure logical (prerequisite → advanced)
- No major factual errors
- Citations accurate (timestamp within 30 seconds)

---

## 17.16 Implementation Summary

**New Components:** 5 modules (transcriber, chunker, expander, enhanced course builder, validator)
**New Data Models:** 4 models (RawTranscript, TranscriptChunk, ExpandedChunk, CourseSection)
**New Database Tables:** 6 tables
**Pipeline Stages:** 8 stages (transcription → validation)
**LLM Usage:** Mixtral for expansion, structure, synthesis
**Embedding Usage:** Nomic-embed-text for chunking, similarity

**Total Estimated Implementation Effort:** 5-7 days for experienced engineer

---

**END OF FULL COURSE GENERATION PIPELINE ARCHITECTURE**

---

# 18. SOURCE DISCOVERY V2.0 - COMPLETE REDESIGN

## PART 1: ROOT CAUSE ANALYSIS - WHY THE CURRENT SYSTEM FAILS

### 18.1 Failure Mode Analysis

**The current Source Discovery system (Section 12) has catastrophic failures across 6 dimensions:**

#### Failure 1: Unrelated Wikipedia Pages

**Symptom:** Query "Python decorators" returns "Python (programming language)" general page.

**Root Cause:**
- DuckDuckGo Wikipedia search returns **topically broad matches**
- No keyword validation after retrieval
- Wikipedia's internal search prioritizes **high-traffic general pages** over specific subtopics
- Current filter only checks domain (`wikipedia.org`), not content relevance

**Why It Matters:** Wikipedia general pages contain too much irrelevant information, polluting the course content with off-topic material.

---

#### Failure 2: DuckDuckGo Results Not Properly Filtered

**Symptom:** Query "Python decorators" returns Medium posts about home decorating, StackOverflow questions about interior design.

**Root Cause:**
- **Keyword ambiguity:** "decorators" matches both programming AND home decor
- DuckDuckGo does NOT understand programming context
- No negative keyword filtering (e.g., exclude "home", "interior", "wall")
- Post-search validation missing

**Why It Matters:** 40-60% of DuckDuckGo results are completely off-topic, wasting processing time and degrading course quality.

---

#### Failure 3: Wikipedia Prioritized Over Educational Content

**Symptom:** Wikipedia appears as top result before RealPython, Python.org, or educational YouTube.

**Root Cause:**
- **Source tier system missing:** All sources treated equally
- Wikipedia has high domain authority in search rankings
- No explicit prioritization of educational/tutorial content

**Why It Matters:** Wikipedia is reference material, NOT tutorial material. Courses should teach concepts step-by-step, not dump encyclopedia entries.

---

#### Failure 4: Transcript Validation Too Strict

**Symptom:** "No valid transcript available" for 30% of YouTube videos that DO have captions.

**Root Cause:**
- Current logic rejects auto-generated captions (`kind != 'asr'`)
- Validation checks for exact transcript match instead of **approximate match**
- No fallback to accept lower-quality transcripts

**Why It Matters:** Auto-generated captions are 85-90% accurate for educational content. Rejecting them cuts available source pool by 60%.

---

#### Failure 5: System Extremely Slow

**Symptom:** Takes 45-90 seconds to discover 5 sources.

**Root Cause:**
- **Sequential processing:** Fetches ALL candidates before filtering
- Downloads PDF content (multi-MB files) before checking file type
- No early termination when target count reached
- No parallel search execution

**Why It Matters:** Users abandon course creation when discovery takes > 30 seconds.

---

#### Failure 6: PDFs and Low-Quality Sites Being Fetched

**Symptom:** Results include paywalled PDFs, content-farm scraper sites, broken links.

**Root Cause:**
- No file-type pre-filtering before download
- No domain blacklist
- No paywall detection
- No broken link validation

**Why It Matters:** PDFs are unstructured, paywalls block content access, scrapers have low-quality content.

---

## PART 2: SOURCE DISCOVERY V2.0 - FINAL ARCHITECTURE

### 18.2 Design Principles (Non-Negotiable)

1. **Precision Over Recall:** Better to have 3 perfect sources than 10 mediocre ones
2. **Educational Content First:** Tutorials > Documentation > Reference
3. **Speed Through Filtering:** Validate before downloading, not after
4. **Explicit Topic Matching:** ALL query keywords must appear in title/URL
5. **Tiered Source Quality:** Whitelist > YouTube > Wikipedia (fallback only)

---

### 18.3 Source Tier System

**Tier 1: Whitelisted Educational Domains (Highest Priority)**

```
python.org            # Official Python docs
realpython.com        # Premium tutorials
docs.python.org       # Python documentation
pythontutorial.net    # Educational tutorials
learnpython.org       # Interactive learning
w3schools.com         # Beginner tutorials
geeksforgeeks.org     # Algorithm tutorials
freecodecamp.org      # Project-based learning
```

**Tier 2: YouTube (Primary Video Source)**

- **Search Strategy:** `site:youtube.com [query]` via DuckDuckGo
- **Transcript Requirement:** Accept auto-generated captions (≥ 80% accuracy)
- **Minimum Duration:** 5 minutes (filters out short ads/promos)
- **Maximum Duration:** 60 minutes (filters out multi-hour streams)

**Tier 3: University & Academic (.edu domains)**

- **Whitelist:** `*.edu` domains with educational content
- **Validation:** Page must contain tutorial/lecture keywords

**Tier 4: Wikipedia (FALLBACK ONLY)**

- **Usage:** Only if Tiers 1-3 return < 2 sources
- **Strict Matching:** Page title must contain ALL query keywords
- **Specificity Filter:** Reject general disambiguation pages

**Blacklisted Domains:**

```
*.pdf                 # File type, not web page
stackoverflow.com     # Q&A, not structured tutorial
reddit.com            # Forum discussion, not educational
quora.com             # Forum discussion
medium.com/*          # Paywall risk (unless verified author)
researchgate.net      # Paywalled PDFs
arxiv.org             # Academic papers (too advanced)
```

---

### 18.4 Five-Stage Filtering Pipeline

**Stage 1: Pre-Search Keyword Disambiguation**

```python
def add_context_keywords(query: str) -> str:
    """Add programming context to ambiguous queries."""

    AMBIGUOUS_TERMS = {
        "decorators": "python programming decorators tutorial",
        "classes": "python classes OOP programming",
        "async": "python async await programming"
    }

    for term, replacement in AMBIGUOUS_TERMS.items():
        if term in query.lower():
            return replacement

    return f"python programming {query}"
```

**Stage 2: Domain-Tier Pre-Filtering**

```python
def search_by_tier(query: str) -> List[SearchResult]:
    """Search tiers sequentially, stop when target count reached."""

    results = []

    # Tier 1: Whitelisted domains
    for domain in TIER_1_DOMAINS:
        results.extend(search_domain(query, domain))
        if len(results) >= 5:
            return results[:5]  # Early termination

    # Tier 2: YouTube
    results.extend(search_youtube(query))
    if len(results) >= 5:
        return results[:5]

    # Tier 3: .edu domains
    results.extend(search_edu(query))
    if len(results) >= 5:
        return results[:5]

    # Tier 4: Wikipedia (fallback only)
    if len(results) < 2:
        results.extend(search_wikipedia_strict(query))

    return results[:5]
```

**Stage 3: Keyword Match Validation**

```python
def validate_keyword_match(result: SearchResult, query_keywords: List[str]) -> bool:
    """ALL query keywords must appear in title OR URL."""

    title_lower = result.title.lower()
    url_lower = result.url.lower()

    for keyword in query_keywords:
        keyword_lower = keyword.lower()

        # Check if keyword appears in title OR URL
        if keyword_lower not in title_lower and keyword_lower not in url_lower:
            return False  # REJECT if ANY keyword missing

    return True  # Accept only if ALL keywords present
```

**Stage 4: Negative Keyword Filtering**

```python
NEGATIVE_KEYWORDS = {
    "decorators": ["home", "interior", "wall", "room", "design", "furniture"],
    "classes": ["school", "university", "classroom", "student"],
    "async": ["asynchronous motor", "electrical"]
}

def check_negative_keywords(result: SearchResult, query: str) -> bool:
    """Reject if negative keywords present (indicates wrong topic)."""

    if query not in NEGATIVE_KEYWORDS:
        return True  # No negative keywords defined

    title_lower = result.title.lower()

    for negative_term in NEGATIVE_KEYWORDS[query]:
        if negative_term in title_lower:
            return False  # REJECT

    return True  # Accept
```

**Stage 5: File Type & Content Validation (Before Download)**

```python
def pre_validate_source(result: SearchResult) -> bool:
    """Fast validation before downloading content."""

    url_lower = result.url.lower()

    # Reject file types
    REJECTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.zip', '.exe']
    if any(url_lower.endswith(ext) for ext in REJECTED_EXTENSIONS):
        return False

    # Reject blacklisted domains
    BLACKLISTED_DOMAINS = ['stackoverflow.com', 'reddit.com', 'quora.com']
    if any(domain in url_lower for domain in BLACKLISTED_DOMAINS):
        return False

    # Check for paywall indicators in URL
    PAYWALL_INDICATORS = ['/premium/', '/subscribe/', '/membership/']
    if any(indicator in url_lower for indicator in PAYWALL_INDICATORS):
        return False

    return True
```

---

### 18.5 Revised DuckDuckGo Search Strategy

**Current Problem:** Generic queries return off-topic results.

**Solution:** Use site-specific searches with strong filters.

```python
def search_duckduckgo_v2(query: str) -> List[SearchResult]:
    """Constrained DuckDuckGo search with heavy filtering."""

    from duckduckgo_search import DDGS

    results = []

    # Search Tier 1 domains explicitly
    for domain in TIER_1_DOMAINS:
        search_query = f"site:{domain} {query}"

        with DDGS() as ddgs:
            for result in ddgs.text(search_query, max_results=3):
                results.append(SearchResult(
                    url=result['href'],
                    title=result['title'],
                    snippet=result['body']
                ))

    # Search YouTube explicitly
    youtube_query = f"site:youtube.com {query} tutorial"

    with DDGS() as ddgs:
        for result in ddgs.text(youtube_query, max_results=5):
            results.append(SearchResult(
                url=result['href'],
                title=result['title'],
                snippet=result['body']
            ))

    # Apply all 5 filtering stages
    filtered_results = []
    query_keywords = query.split()

    for result in results:
        if not validate_keyword_match(result, query_keywords):
            continue
        if not check_negative_keywords(result, query):
            continue
        if not pre_validate_source(result):
            continue

        filtered_results.append(result)

    return filtered_results[:5]
```

---

### 18.6 YouTube Transcript Validation (Simplified)

**Current Problem:** Auto-generated captions rejected, cutting source pool by 60%.

**Solution:** Accept auto-generated captions with quality check.

```python
def get_youtube_transcript_v2(video_id: str) -> Optional[str]:
    """Accept auto-generated captions, validate quality."""

    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        # Get ANY available transcript (manual or auto-generated)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Priority: Manual > Auto-generated English > Translated
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                # Fallback: Translate any available transcript to English
                transcript = transcript_list.find_transcript(['en']).translate('en')

        # Fetch transcript segments
        segments = transcript.fetch()
        full_text = " ".join([seg['text'] for seg in segments])

        # Quality validation: Check for minimum word count
        word_count = len(full_text.split())

        if word_count < 100:
            return None  # Too short, likely intro/outro only

        return full_text

    except Exception as e:
        logger.warning(f"Transcript fetch failed for {video_id}: {e}")
        return None
```

---

### 18.7 Wikipedia Strict Matching (Fallback Only)

**Current Problem:** Generic Wikipedia pages (e.g., "Python (programming language)") returned for specific queries.

**Solution:** Wikipedia ONLY as fallback, with exact topic matching.

```python
def search_wikipedia_strict(query: str) -> List[SearchResult]:
    """Wikipedia fallback with strict topic matching."""

    import wikipedia

    results = []
    query_keywords = set(query.lower().split())

    try:
        # Search Wikipedia
        search_results = wikipedia.search(query, results=5)

        for title in search_results:
            title_keywords = set(title.lower().split())

            # STRICT MATCH: ALL query keywords must appear in Wikipedia page title
            if not query_keywords.issubset(title_keywords):
                continue  # Reject if not exact match

            # Fetch page summary to validate relevance
            try:
                page = wikipedia.page(title)

                # Check summary for query keywords
                summary_lower = page.summary.lower()
                keyword_count = sum(1 for kw in query_keywords if kw in summary_lower)

                # Require >= 80% of keywords in summary
                if keyword_count / len(query_keywords) < 0.8:
                    continue  # Reject if summary doesn't match

                results.append(SearchResult(
                    url=page.url,
                    title=page.title,
                    snippet=page.summary[:200]
                ))

            except wikipedia.exceptions.DisambiguationError:
                continue  # Skip disambiguation pages
            except wikipedia.exceptions.PageError:
                continue  # Skip missing pages

    except Exception as e:
        logger.error(f"Wikipedia search failed: {e}")

    return results
```

---

### 18.8 Speed Optimizations

**Target:** < 15 seconds for 5 sources (down from 45-90 seconds)

**Optimization 1: Parallel Tier Search**

```python
import concurrent.futures

def search_all_tiers_parallel(query: str) -> List[SearchResult]:
    """Search all tiers in parallel, merge results by priority."""

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tier searches simultaneously
        future_tier1 = executor.submit(search_tier1_domains, query)
        future_youtube = executor.submit(search_youtube, query)
        future_edu = executor.submit(search_edu_domains, query)
        future_wikipedia = executor.submit(search_wikipedia_strict, query)

        # Collect results as they complete
        tier1_results = future_tier1.result(timeout=5)
        youtube_results = future_youtube.result(timeout=5)
        edu_results = future_edu.result(timeout=5)
        wikipedia_results = future_wikipedia.result(timeout=5)

    # Merge by priority
    all_results = tier1_results + youtube_results + edu_results

    # Only add Wikipedia if insufficient results
    if len(all_results) < 2:
        all_results.extend(wikipedia_results)

    return all_results[:5]
```

**Optimization 2: Early Termination**

```python
def search_with_early_termination(query: str, target_count: int = 5) -> List[SearchResult]:
    """Stop searching once target count reached."""

    results = []

    # Tier 1: Whitelisted domains (highest quality)
    results.extend(search_tier1_domains(query))
    if len(results) >= target_count:
        return results[:target_count]  # STOP

    # Tier 2: YouTube
    results.extend(search_youtube(query))
    if len(results) >= target_count:
        return results[:target_count]  # STOP

    # Continue only if needed...
    return results[:target_count]
```

**Optimization 3: Pre-Validation Before Download**

```python
def fetch_content_smart(url: str) -> Optional[str]:
    """Validate before downloading to avoid wasting time."""

    # Step 1: HEAD request to check file type (no download)
    response = requests.head(url, timeout=3)
    content_type = response.headers.get('Content-Type', '')

    # Reject non-HTML content
    if 'application/pdf' in content_type:
        return None
    if 'application/zip' in content_type:
        return None

    # Step 2: Check file size (reject > 5MB)
    content_length = int(response.headers.get('Content-Length', 0))
    if content_length > 5_000_000:  # 5MB
        return None

    # Step 3: Now download content
    response = requests.get(url, timeout=10)
    return response.text
```

---

### 18.9 Complete Discovery Flow (Example)

**Query:** "Python decorators"

**Step 1: Keyword Disambiguation**

```
Original query: "Python decorators"
Disambiguated: "Python programming decorators tutorial"
Query keywords: ["python", "programming", "decorators", "tutorial"]
```

**Step 2: Tier 1 Search (Whitelisted Domains)**

```
Search: site:realpython.com Python programming decorators tutorial
Result: "Python Decorators 101" - https://realpython.com/primer-on-python-decorators/
Keyword match: ✓ (all keywords in URL + title)
Negative keywords: ✓ (none present)
Pre-validation: ✓ (HTML, no paywall)
→ ACCEPTED (1/5)
```

**Step 3: YouTube Search**

```
Search: site:youtube.com Python programming decorators tutorial
Result: "Python Decorators in 15 Minutes" - https://youtube.com/watch?v=abc123
Transcript: ✓ (auto-generated, 3,200 words)
Duration: 15 minutes ✓
Keyword match: ✓
→ ACCEPTED (2/5)
```

**Step 4: Tier 1 Continued**

```
Search: site:python.org Python programming decorators tutorial
Result: "PEP 318 - Decorators for Functions" - https://python.org/dev/peps/pep-0318/
Keyword match: ✓
→ ACCEPTED (3/5)
```

**Step 5: YouTube Continued**

```
Result: "Advanced Python Decorators" - https://youtube.com/watch?v=xyz789
Transcript: ✓
→ ACCEPTED (4/5)
```

**Step 6: .edu Domain Search**

```
Search: site:.edu Python programming decorators tutorial
Result: "CS106A Lecture: Decorators" - https://stanford.edu/~cs106a/decorators
Keyword match: ✓
→ ACCEPTED (5/5)
```

**Step 7: Early Termination**

```
Target count reached (5/5). Stop searching.
Wikipedia search NOT executed (fallback not needed).
```

**Final Results:**

1. RealPython (Tier 1)
2. YouTube Video 1 (Tier 2)
3. Python.org PEP (Tier 1)
4. YouTube Video 2 (Tier 2)
5. Stanford Lecture (Tier 3)

**Total Time:** 8 seconds (vs. 45-90 seconds previously)

---

### 18.10 Configuration & Tuning

**File:** `backend/core/config.py`

```python
class SourceDiscoveryConfigV2:
    # Tier 1 Domains (Whitelisted)
    TIER_1_DOMAINS = [
        "realpython.com",
        "python.org",
        "docs.python.org",
        "pythontutorial.net",
        "learnpython.org",
        "w3schools.com",
        "geeksforgeeks.org",
        "freecodecamp.org"
    ]

    # Blacklisted Domains
    BLACKLISTED_DOMAINS = [
        "stackoverflow.com",
        "reddit.com",
        "quora.com",
        "researchgate.net",
        "arxiv.org"
    ]

    # YouTube Constraints
    YOUTUBE_MIN_DURATION = 300  # 5 minutes
    YOUTUBE_MAX_DURATION = 3600  # 60 minutes

    # Transcript Settings
    ACCEPT_AUTO_CAPTIONS = True
    MIN_TRANSCRIPT_WORDS = 100

    # Search Timeouts
    SEARCH_TIMEOUT_PER_TIER = 5  # seconds
    TOTAL_SEARCH_TIMEOUT = 15  # seconds

    # Target Counts
    TARGET_SOURCE_COUNT = 5
    MIN_SOURCES_BEFORE_WIKIPEDIA = 2  # Use Wikipedia only if < 2 sources

    # Negative Keywords (Topic Disambiguation)
    NEGATIVE_KEYWORDS = {
        "decorators": ["home", "interior", "wall", "room", "design", "furniture"],
        "classes": ["school", "university", "classroom", "student"],
        "async": ["asynchronous motor", "electrical"]
    }

    # Keyword Match Threshold
    KEYWORD_MATCH_THRESHOLD = 1.0  # ALL keywords must match (100%)
```

---

### 18.11 Error Handling & Fallbacks

**Scenario 1: All Tiers Return 0 Results**

```python
def handle_no_results(query: str) -> List[SearchResult]:
    """Fallback when all tiers fail."""

    logger.warning(f"No sources found for query: {query}")

    # Fallback 1: Try broader query (remove last keyword)
    if len(query.split()) > 2:
        broader_query = " ".join(query.split()[:-1])
        logger.info(f"Retrying with broader query: {broader_query}")
        return search_all_tiers_parallel(broader_query)

    # Fallback 2: Return empty list + user-friendly error
    return []
```

**Scenario 2: Transcript Unavailable for YouTube**

```python
def handle_missing_transcript(video_id: str) -> Optional[str]:
    """Try alternative transcript methods."""

    # Method 1: Try all available languages, translate to English
    # Method 2: Use video title + description as fallback content
    # Method 3: Skip video, log warning

    logger.warning(f"No transcript for {video_id}, skipping source")
    return None
```

**Scenario 3: Network Timeout**

```python
def search_with_timeout(tier_func, timeout: int = 5) -> List[SearchResult]:
    """Execute search with timeout protection."""

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(tier_func)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning(f"Search timeout for {tier_func.__name__}")
        return []
```

---

### 18.12 Database Schema Updates

**New Table: `source_discovery_v2_cache`**

```sql
CREATE TABLE source_discovery_v2_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_normalized TEXT NOT NULL,           -- Normalized query (lowercase, sorted keywords)
    tier TEXT NOT NULL,                        -- "tier1", "youtube", "edu", "wikipedia"
    result_url TEXT NOT NULL,
    result_title TEXT,
    result_snippet TEXT,
    keyword_match_score REAL,                  -- % of keywords matched
    negative_keyword_flagged BOOLEAN,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(query_normalized, result_url)       -- Prevent duplicate caching
);

CREATE INDEX idx_source_v2_cache_query ON source_discovery_v2_cache(query_normalized);
CREATE INDEX idx_source_v2_cache_tier ON source_discovery_v2_cache(tier);
```

**New Table: `source_quality_metrics`**

```sql
CREATE TABLE source_quality_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    tier TEXT NOT NULL,
    avg_course_rating REAL,                    -- Average rating of courses using this source
    usage_count INTEGER DEFAULT 0,             -- How many courses used this source
    transcript_quality_score REAL,             -- 0.0-1.0 (for YouTube)
    last_validated TIMESTAMP,
    is_blacklisted BOOLEAN DEFAULT FALSE,

    UNIQUE(source_url)
);
```

---

## PART 3: IMPLEMENTATION TASKS FOR CURSOR

### 18.13 Implementation Checklist

**Task Group 1: Core Architecture**

- [ ] Create `source_discoverer_v2.py` module
- [ ] Implement `SourceTier` enum (TIER_1, YOUTUBE, EDU, WIKIPEDIA, BLACKLISTED)
- [ ] Implement `SearchResult` dataclass with validation
- [ ] Create `SourceDiscoveryConfigV2` configuration class

**Task Group 2: Keyword Processing**

- [ ] Implement `add_context_keywords()` for query disambiguation
- [ ] Implement `validate_keyword_match()` with 100% threshold
- [ ] Implement `check_negative_keywords()` filtering
- [ ] Create `NEGATIVE_KEYWORDS` configuration dictionary

**Task Group 3: Tier 1 Search (Whitelisted Domains)**

- [ ] Implement `search_tier1_domains()` function
- [ ] Configure `TIER_1_DOMAINS` whitelist
- [ ] Add site-specific search logic for each domain
- [ ] Implement parallel search across Tier 1 domains

**Task Group 4: YouTube Search**

- [ ] Implement `search_youtube()` with site-specific DuckDuckGo query
- [ ] Implement `get_youtube_transcript_v2()` accepting auto-captions
- [ ] Add duration constraints (5-60 minutes)
- [ ] Add quality validation (min 100 words)

**Task Group 5: .edu Domain Search**

- [ ] Implement `search_edu_domains()` function
- [ ] Add educational content keyword validation
- [ ] Filter out administrative pages (admissions, about, contact)

**Task Group 6: Wikipedia Fallback**

- [ ] Implement `search_wikipedia_strict()` with exact matching
- [ ] Add keyword subset validation (ALL keywords in title)
- [ ] Add summary relevance check (80% keyword threshold)
- [ ] Reject disambiguation pages

**Task Group 7: Five-Stage Filtering Pipeline**

- [ ] Implement Stage 1: Pre-search keyword disambiguation
- [ ] Implement Stage 2: Domain-tier pre-filtering
- [ ] Implement Stage 3: Keyword match validation
- [ ] Implement Stage 4: Negative keyword filtering
- [ ] Implement Stage 5: File type & content pre-validation

**Task Group 8: Speed Optimizations**

- [ ] Implement parallel tier search with ThreadPoolExecutor
- [ ] Add early termination when target count reached
- [ ] Implement HEAD request pre-validation before download
- [ ] Add timeout protection (5s per tier, 15s total)

**Task Group 9: Database & Caching**

- [ ] Create `source_discovery_v2_cache` table
- [ ] Create `source_quality_metrics` table
- [ ] Implement cache read/write logic
- [ ] Add cache expiration (7 days)

---

### 18.14 Testing Strategy

**Unit Tests:**

```python
def test_keyword_match_validation():
    """Test that ALL keywords must be present."""

    result = SearchResult(
        url="https://realpython.com/python-decorators/",
        title="Python Decorators Tutorial"
    )

    # Should PASS: All keywords present
    assert validate_keyword_match(result, ["python", "decorators"])

    # Should FAIL: "tutorial" keyword missing from URL
    assert not validate_keyword_match(result, ["python", "decorators", "tutorial"])

def test_negative_keyword_filtering():
    """Test that negative keywords are rejected."""

    result = SearchResult(
        url="https://example.com/home-decorators",
        title="Best Home Decorators for Your Living Room"
    )

    # Should FAIL: Contains negative keywords "home", "living room"
    assert not check_negative_keywords(result, "decorators")

def test_wikipedia_strict_matching():
    """Test Wikipedia fallback only returns exact matches."""

    results = search_wikipedia_strict("Python decorators")

    # Should NOT return "Python (programming language)" general page
    assert all("Python decorators" in r.title for r in results)
```

**Integration Tests:**

```python
def test_full_discovery_pipeline():
    """Test end-to-end source discovery."""

    query = "Python decorators"
    results = discover_sources_v2(query)

    # Assertions
    assert len(results) == 5
    assert any("realpython.com" in r.url for r in results)  # Tier 1 present
    assert any("youtube.com" in r.url for r in results)     # YouTube present
    assert not any("wikipedia.org" in r.url for r in results)  # Wikipedia not needed

    # All results should match keywords
    for result in results:
        assert validate_keyword_match(result, ["python", "decorators"])

def test_performance_target():
    """Test that discovery completes within 15 seconds."""

    import time

    start = time.time()
    results = discover_sources_v2("Python async await")
    elapsed = time.time() - start

    assert elapsed < 15.0  # Must complete in < 15 seconds
    assert len(results) >= 3  # Must return at least 3 sources
```

**Edge Case Tests:**

```python
def test_no_results_fallback():
    """Test behavior when no sources found."""

    results = discover_sources_v2("zxqwertyjkl12345")  # Nonsense query

    # Should return empty list, not crash
    assert results == []

def test_transcript_fallback():
    """Test YouTube without manual transcript."""

    # Video with only auto-generated captions
    video_id = "dQw4w9WgXcQ"

    transcript = get_youtube_transcript_v2(video_id)

    # Should accept auto-generated transcript
    assert transcript is not None
    assert len(transcript.split()) >= 100
```

---

### 18.15 Migration from V1 to V2

**Transition Plan:**

**Step 1:** Deploy V2 alongside V1 (feature flag)

```python
# config.py
USE_SOURCE_DISCOVERY_V2 = True  # Toggle between V1/V2
```

**Step 2:** A/B test for 1 week

- 50% of courses use V1
- 50% of courses use V2
- Compare metrics: source quality, speed, course ratings

**Step 3:** Analyze metrics

```python
# Expected V2 improvements:
# - 60% faster discovery (45s → 15s)
# - 80% fewer off-topic sources
# - 40% more YouTube sources accepted (auto-captions)
# - 70% fewer Wikipedia general pages
```

**Step 4:** Full rollout if V2 metrics ≥ 20% better

**Step 5:** Deprecate V1 code after 2 weeks

---

### 18.16 Success Criteria

**Performance Targets:**

- Discovery time: < 15 seconds (down from 45-90s)
- Source relevance: ≥ 90% (up from 40-60%)
- YouTube success rate: ≥ 70% (up from 40%)
- Wikipedia usage: < 20% of courses (down from 80%)

**Quality Metrics:**

- All sources contain ALL query keywords in title/URL
- Zero off-topic sources (e.g., no "home decorators" for "Python decorators")
- Tier 1 domains represent ≥ 40% of sources
- YouTube videos have valid transcripts ≥ 100 words

**User Experience:**

- Course generation completes in < 2 minutes total
- Users report ≥ 4/5 satisfaction with source quality
- ≤ 5% of courses require manual source correction

---

### 18.17 Monitoring & Observability

**Metrics to Track:**

```python
# Log every discovery operation
logger.info({
    "query": query,
    "tier_breakdown": {
        "tier1_count": 2,
        "youtube_count": 2,
        "edu_count": 1,
        "wikipedia_count": 0
    },
    "total_time_seconds": 12.3,
    "keyword_match_failures": 8,
    "negative_keyword_rejections": 5,
    "blacklist_rejections": 3
})
```

**Alerts:**

- Alert if discovery time > 20 seconds
- Alert if source relevance < 80%
- Alert if Wikipedia usage > 30%

---

**END OF SOURCE DISCOVERY V2.0 ARCHITECTURE**

---

CODEX IMPLEMENTATION

- Added source persistence inside the pipeline so transcripts, chunks, and claims always reference existing `sources` rows; updates cache synchronization and preserves existing source_ids when URLs are already stored.
- Fixed the explicit URL pipeline path by importing the course structure generator, ensuring explicit URL runs can build courses without NameError.
- Implemented a consensus builder that clusters extracted claims, stores consensus and contradiction records, and feeds consensus confidence into section scoring for the enhanced pipeline.
- Unified both pipeline entry points to share the same normalization → chunking → expansion → consensus-aware course builder path, added a shared processing helper, and enforced stable `source_id` creation when inserting new sources.
- Next steps: wrap multi-table pipeline writes in DB transactions, expose consensus/contradiction data through the API, surface consensus/conflict indicators in the frontend course views, and proceed with the queued Phase 2 (vision), Phase 3 (gamification), and Phase 4 (RAG chat) milestones after transaction hardening.

Actionable tasks from recommendations (implementation queue)
- Pipeline robustness: add transactional wrappers around the ingestion → extraction → course-build writes in `backend/core/pipeline.py` (e.g., helpers around `_store_transcript`, `_store_chunks`, `_store_claims`, and course persistence) so partial failures roll back consistently.
- Course builder alignment: keep both entry points on `_process_sources_into_course`; remove any legacy divergent paths and ensure the shared path calls the same section synthesis utilities in `backend/services/processing/course_builder.py`.
- Consensus integration: thread consensus outputs into section scoring everywhere (verify `calculate_section_scores` uses stored consensus records) and add unit coverage for contradiction/conflict flags.
- Prompt/LLM resilience: add configuration validation and explicit error handling around prompt/model loading in `backend/services/extraction/claim_extractor.py`, `chunk_expander.py`, and related modules to surface missing prompt files or model names early.
- API exposure: extend FastAPI routes to return consensus claims, contradiction details, and section-level citation metadata; ensure response schemas in `backend/api` reflect the new fields.
- Frontend visibility: update course viewer components to render consensus confidence, contradictions, and citation lists; add empty/error states for source discovery failures and missing transcripts.
- Vision features (Phase 2): implement frame extraction via `frame_extractor` (ffmpeg), VCT classification, and visual claim extraction using LLaVA; persist frames/visual claims and surface frame-based citations in course sections.
- Gamification (Phase 3): wire XP, badges, and skill tree progression to existing tables; add backend endpoints and frontend dashboard components for progress tracking.
- RAG chat (Phase 4): generate embeddings for course sections, build retriever/query APIs, and connect the chat panel using the chatbot prompt with strict context-only responses.

# TIER 1 FOUNDATION HARDENING - ARCHITECTURAL SPECIFICATIONS

**Architect:** Claude (Sonnet 4.5)
**Date:** 2025-12-09
**Status:** Architectural Design Complete, Ready for Cursor Implementation
**Priority:** CRITICAL - Must be completed before Tier 2/3/4 features

---

##OVERVIEW

This document specifies the architecture for **Tier 1 Foundation Hardening**, comprising three critical architectural domains that ensure system reliability, maintainability, and correctness:

1. **Pipeline Robustness** - Transactional integrity for multi-table writes
2. **Prompt/LLM Resilience** - Configuration validation and error handling
3. **Course Builder Alignment** - Remove legacy code paths

**Implementation Dependency:** These three domains must be implemented BEFORE exposing consensus data, building frontend features, or expanding to Phases 2-4.

**Total Implementation Effort:** 3-4 days for experienced engineer

---

# 19. PIPELINE ROBUSTNESS - TRANSACTIONAL INTEGRITY

## 19.1 Problem Analysis

### Current Implementation Issues

**File:** `backend/core/pipeline.py`

**Issue 1: No Atomic Transactions**

The current pipeline makes 8+ separate database writes across the `_process_sources_into_course()` method (lines 172-293):

```
Line 214: _store_transcript() → Writes raw_transcripts + transcript_segments
Line 238: _store_chunks() → Writes transcript_chunks (one per chunk)
Line 248: _store_expanded_chunks() → Writes expanded_chunks (one per expansion)
Line 273: _store_claim() → Writes claims (one per claim)
Line 278: _store_consensus_claim() → Writes consensus_claims (one per consensus)
Line 281: _store_contradiction() → Writes contradictions (one per contradiction)
Line 293: _store_enhanced_course() → Writes courses + course_sections + section_citations + course_sources
```

Each of these methods calls `db.execute_write()` which **commits immediately** (database.py line 66).

**Problem:** If the pipeline fails at any point (e.g., LLM timeout during course building), partial data remains in the database:
- Orphaned transcripts without associated courses
- Chunks without claims
- Claims without consensus records
- Incomplete course records

**Impact:**
- Database integrity violations
- Manual cleanup required
- Re-running pipeline creates duplicates
- Foreign key relationships broken

---

**Issue 2: No Rollback on Failure**

**File:** `backend/core/database.py` (lines 61-69)

```python
def execute_write(self, query: str, params: Optional[tuple] = None) -> int:
    """Execute an INSERT/UPDATE/DELETE query and return last row ID."""
    conn = self.get_connection_raw()
    try:
        cursor = conn.execute(query, params or ())
        conn.commit()  # ← COMMITS IMMEDIATELY
        return cursor.lastrowid
    finally:
        conn.close()
```

Each write commits individually. There is NO mechanism to group writes into a transaction and rollback on failure.

---

**Issue 3: Cache Inconsistency**

**File:** `backend/core/pipeline.py` (lines 354-363)

After storing sources in the database, the pipeline updates the cache:

```python
cache_manager.save_source(...)
```

If database write succeeds but cache write fails (or vice versa), the two systems diverge.

**Impact:**
- Cache returns stale data
- Re-fetching sources may miss database updates
- Inconsistent source_id references

---

## 19.2 Architecture Solution

### Three-Layer Transaction Design

**Layer 1: Pipeline-Level Transaction Wrapper**

Wrap the entire `_process_sources_into_course()` method in a single database transaction. If ANY step fails, rollback ALL writes.

**Layer 2: Stage-Level Checkpoints**

Allow partial commits at major stage boundaries (e.g., after source discovery completes) so that long pipelines can recover from mid-stage failures.

**Layer 3: Compensation Logic**

For external operations that cannot be rolled back (e.g., LLM calls, cache writes), implement compensation logic to undo their effects on rollback.

---

### Database Transaction Manager

**New Module:** `backend/core/transaction.py`

**Purpose:** Provide transaction context managers for pipeline operations.

**Key Features:**
1. **Context manager** for automatic commit/rollback
2. **Nested transaction support** (savepoints)
3. **Compensation handlers** for non-database operations
4. **Error categorization** (transient vs. permanent failures)

---

## 19.3 Implementation Specification

### 19.3.1 Transaction Context Manager

**File:** `backend/core/transaction.py` (NEW FILE)

```python
"""
Database transaction management with rollback support.
"""
import sqlite3
from typing import Optional, Callable, List, Any
from contextlib import contextmanager
from core.database import db

class TransactionManager:
    """Manages database transactions with rollback and compensation."""

    def __init__(self):
        self.compensation_handlers: List[Callable] = []

    @contextmanager
    def transaction(self, isolation_level: Optional[str] = None):
        """
        Context manager for database transactions.

        Usage:
            with transaction_manager.transaction():
                db.execute_write(...)
                db.execute_write(...)
                # If exception raised, all writes rolled back

        Args:
            isolation_level: Optional SQLite isolation level
                - None: Default (DEFERRED)
                - "IMMEDIATE": Lock database immediately
                - "EXCLUSIVE": Exclusive lock

        Yields:
            Connection object for manual operations
        """
        conn = db.get_connection_raw()

        # Set isolation level if specified
        if isolation_level:
            conn.isolation_level = isolation_level

        try:
            # Start transaction
            conn.execute("BEGIN")

            yield conn

            # Commit transaction
            conn.commit()

            # Clear compensation handlers on success
            self.compensation_handlers.clear()

        except Exception as e:
            # Rollback transaction
            conn.rollback()

            # Execute compensation handlers (for external operations)
            self._execute_compensation()

            # Re-raise exception
            raise

        finally:
            conn.close()

    @contextmanager
    def savepoint(self, conn: sqlite3.Connection, name: str):
        """
        Create a savepoint for nested transactions.

        Usage:
            with transaction_manager.savepoint(conn, "stage_3"):
                # Partial rollback possible

        Args:
            conn: Active connection
            name: Savepoint identifier
        """
        try:
            conn.execute(f"SAVEPOINT {name}")
            yield
            conn.execute(f"RELEASE SAVEPOINT {name}")
        except Exception:
            conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
            raise

    def register_compensation(self, handler: Callable[[], None]):
        """
        Register a compensation handler for external operations.

        Compensation handlers execute on rollback to undo
        non-database operations (e.g., delete cached files).

        Args:
            handler: Function to call on rollback
        """
        self.compensation_handlers.append(handler)

    def _execute_compensation(self):
        """Execute all registered compensation handlers in reverse order."""
        for handler in reversed(self.compensation_handlers):
            try:
                handler()
            except Exception as e:
                # Log but don't re-raise (rollback already happened)
                print(f"Compensation handler failed: {e}")

# Global transaction manager instance
transaction_manager = TransactionManager()
```

---

### 19.3.2 Enhanced Database Module

**File:** `backend/core/database.py` (MODIFICATIONS)

**Add Method:**

```python
def execute_write_in_transaction(
    self,
    conn: sqlite3.Connection,
    query: str,
    params: Optional[tuple] = None
) -> int:
    """
    Execute write within an existing transaction.

    DOES NOT commit - caller must commit via transaction manager.

    Args:
        conn: Active connection (from transaction context)
        query: SQL query
        params: Query parameters

    Returns:
        Last row ID
    """
    cursor = conn.execute(query, params or ())
    return cursor.lastrowid
```

---

### 19.3.3 Transactional Pipeline Wrapper

**File:** `backend/core/pipeline.py` (MODIFICATIONS)

**Modify `_process_sources_into_course()`:**

```python
def _process_sources_into_course(
    self, query: str, course_id: str, sources: List[Dict[str, Any]]
) -> None:
    """
    Shared processing path that converts stored sources into a course.

    NOW WRAPPED IN TRANSACTION for atomicity.
    """
    from core.transaction import transaction_manager

    # Wrap entire pipeline in transaction
    with transaction_manager.transaction(isolation_level="IMMEDIATE"):

        # STAGE 3: Transcription & Normalization
        transcripts = []

        for source in sources:
            # ... (existing normalization logic)

            # Validate transcript
            validation = validate_transcript(transcript)
            if validation["is_valid"]:
                transcripts.append(transcript)
                # Store in database (within transaction)
                self._store_transcript_transactional(transcript, conn)
            else:
                print(f"Warning: Transcript validation failed...")

        if not transcripts:
            raise ValueError("No valid transcripts...")

        # STAGE 4: Semantic Chunking
        chunker = SemanticChunker()
        all_chunks = []

        for transcript in transcripts:
            chunks = chunker.chunk_transcript(transcript)
            chunks = rechunk_if_needed(chunks)
            all_chunks.extend(chunks)
            # Store chunks (within transaction)
            self._store_chunks_transactional(chunks, transcript.source_id, conn)

        if not all_chunks:
            raise ValueError("No chunks could be created")

        # STAGE 5: LLM Expansion
        expander = ChunkExpander()
        expanded_chunks = expander.expand_batch(all_chunks)

        # Store expanded chunks (within transaction)
        self._store_expanded_chunks_transactional(expanded_chunks, conn)

        # STAGE 6: Claim Extraction
        all_claims = []
        source_id_map = {chunk.chunk_id: chunk.source_id for chunk in all_chunks}

        for expanded in expanded_chunks:
            source_id = source_id_map.get(expanded.source_chunk_id, "unknown")

            for claim in expanded.claims:
                if isinstance(claim, dict) and claim.get("subject"):
                    claim_data = {
                        "claim_id": f"claim_{uuid.uuid4().hex[:12]}",
                        "source_id": source_id,
                        "claim_type": "transcript",
                        "subject": claim.get("subject", ""),
                        "predicate": claim.get("predicate", ""),
                        "object": claim.get("object", ""),
                        "confidence": float(claim.get("confidence", 1.0)),
                        "timestamp_ms": None,
                    }
                    all_claims.append(claim_data)
                    # Store claim (within transaction)
                    self._store_claim_transactional(claim_data, conn)

        # STAGE 6.5: Consensus & Contradiction Detection
        consensus_results = consensus_builder.build_consensus(all_claims)

        for consensus in consensus_results.get("consensus_claims", []):
            self._store_consensus_claim_transactional(consensus, conn)

        for contradiction in consensus_results.get("contradictions", []):
            self._store_contradiction_transactional(contradiction, conn)

        # STAGE 7 & 8: Course Building & Section Synthesis
        course_data = build_complete_course(
            query=query,
            expanded_chunks=expanded_chunks,
            sources=sources,
            course_id=course_id,
            consensus_claims=consensus_results.get("consensus_claims", []),
        )

        # STAGE 9: Store course and sections (within transaction)
        self._store_enhanced_course_transactional(course_data, query, sources, conn)

        # If we reach here, transaction commits automatically
        # If any exception raised above, transaction rolls back
```

---

### 19.3.4 Transactional Storage Methods

**File:** `backend/core/pipeline.py` (NEW METHODS)

**Add transactional variants of all storage methods:**

```python
def _store_transcript_transactional(self, transcript, conn: sqlite3.Connection) -> None:
    """Store RawTranscript within existing transaction."""
    transcript_id = f"trans_{transcript.source_id}_{uuid.uuid4().hex[:8]}"

    db.execute_write_in_transaction(
        conn,
        """
        INSERT INTO raw_transcripts
        (transcript_id, source_id, full_text, segment_count, word_count, language, quality_score, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transcript_id,
            transcript.source_id,
            transcript.full_text,
            len(transcript.segments),
            transcript.word_count,
            transcript.language,
            0.8,
            json.dumps(transcript.metadata),
        )
    )

    # Store segments
    for i, segment in enumerate(transcript.segments):
        db.execute_write_in_transaction(
            conn,
            """
            INSERT INTO transcript_segments
            (segment_id, transcript_id, segment_index, text, start_time_ms, end_time_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                segment.segment_id or f"seg_{uuid.uuid4().hex[:8]}",
                transcript_id,
                i,
                segment.text,
                segment.start_time_ms,
                segment.end_time_ms,
                json.dumps(segment.metadata),
            )
        )

def _store_chunks_transactional(self, chunks, source_id: str, conn: sqlite3.Connection) -> None:
    """Store TranscriptChunks within existing transaction."""
    for chunk in chunks:
        transcript_id = chunk.chunk_id.split('_')[1] if '_' in chunk.chunk_id else None

        db.execute_write_in_transaction(
            conn,
            """
            INSERT INTO transcript_chunks
            (chunk_id, transcript_id, source_id, chunk_index, text, word_count,
             start_time_ms, end_time_ms, topic_keywords, semantic_density,
             coherence_score, completeness_score, previous_chunk_id, next_chunk_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                transcript_id or source_id,
                source_id,
                chunk.chunk_index,
                chunk.text,
                chunk.word_count,
                chunk.start_time_ms,
                chunk.end_time_ms,
                json.dumps(chunk.topic_keywords),
                chunk.semantic_density,
                chunk.coherence_score,
                chunk.completeness_score,
                chunk.previous_chunk_id,
                chunk.next_chunk_id,
            )
        )

# Similar transactional methods for:
# - _store_expanded_chunks_transactional()
# - _store_claim_transactional()
# - _store_consensus_claim_transactional()
# - _store_contradiction_transactional()
# - _store_enhanced_course_transactional()
```

---

### 19.3.5 Cache Compensation Logic

**File:** `backend/core/pipeline.py` (MODIFICATIONS)

**Add cache compensation for `_store_source()`:**

```python
def _store_source(self, source: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a source and return the stored record."""
    from core.transaction import transaction_manager

    # ... (existing database persistence logic)

    # Register cache write compensation
    # If transaction rolls back, we need to invalidate cache entry
    source_url = source.get("url")
    transaction_manager.register_compensation(
        lambda: cache_manager.delete_source(source_url)  # Undo cache write
    )

    # Keep cache in sync
    cache_manager.save_source(
        source_id=source["source_id"],
        source_type=source_type,
        url=source_url,
        title=source.get("title"),
        transcript=transcript_text,
        metadata=metadata,
        vct_tier=source.get("vct_tier"),
    )

    return source
```

**Required Addition to cache_manager:**

```python
# File: backend/services/ingestion/cache_manager.py (ADD METHOD)

def delete_source(self, url: str) -> None:
    """Delete source from cache (compensation handler)."""
    db.execute_write(
        "DELETE FROM sources WHERE url = ?",
        (url,)
    )
```

---

## 19.4 Error Handling Strategy

### Error Categories

**Category 1: Transient Errors (Retryable)**
- Network timeouts (LLM API)
- Temporary database locks
- Ollama service unavailable

**Action:** Retry with exponential backoff (max 3 attempts)

**Category 2: Permanent Errors (Non-Retryable)**
- Invalid transcript format
- Missing required fields
- Foreign key violations

**Action:** Rollback transaction, log error, return user-friendly message

**Category 3: External Operation Failures**
- Cache write failures
- File system errors

**Action:** Execute compensation handlers, rollback transaction

---

### Retry Decorator

**File:** `backend/core/transaction.py` (ADD FUNCTION)

```python
import time
from functools import wraps

def retry_on_transient_error(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator to retry operations on transient errors.

    Detects SQLite busy errors, network timeouts, etc.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        # Database locked, retry
                        delay = base_delay * (2 ** attempt)
                        print(f"Database locked, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    raise
                except Exception as e:
                    # Check if error is transient
                    if _is_transient_error(e) and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Transient error, retrying in {delay}s: {e}")
                        time.sleep(delay)
                        continue
                    raise

            return func(*args, **kwargs)

        return wrapper
    return decorator

def _is_transient_error(error: Exception) -> bool:
    """Determine if error is transient (retryable)."""
    error_str = str(error).lower()
    transient_indicators = [
        "timeout",
        "connection reset",
        "temporary failure",
        "service unavailable",
        "429",  # Rate limit
        "503",  # Service unavailable
    ]
    return any(indicator in error_str for indicator in transient_indicators)
```

---

## 19.5 Testing Requirements

### Unit Tests

**File:** `backend/tests/test_transaction.py` (NEW FILE)

```python
def test_transaction_commit():
    """Test that transaction commits on success."""
    with transaction_manager.transaction() as conn:
        db.execute_write_in_transaction(
            conn,
            "INSERT INTO sources (source_id, url, source_type) VALUES (?, ?, ?)",
            ("test_1", "http://test.com", "article")
        )

    # Verify record exists
    result = db.execute_one("SELECT * FROM sources WHERE source_id = ?", ("test_1",))
    assert result is not None

def test_transaction_rollback():
    """Test that transaction rolls back on error."""
    try:
        with transaction_manager.transaction() as conn:
            db.execute_write_in_transaction(
                conn,
                "INSERT INTO sources (source_id, url, source_type) VALUES (?, ?, ?)",
                ("test_2", "http://test2.com", "article")
            )

            # Raise error to trigger rollback
            raise ValueError("Intentional error")

    except ValueError:
        pass

    # Verify record does NOT exist
    result = db.execute_one("SELECT * FROM sources WHERE source_id = ?", ("test_2",))
    assert result is None

def test_compensation_handler():
    """Test compensation handlers execute on rollback."""
    compensation_executed = [False]

    def compensation():
        compensation_executed[0] = True

    try:
        with transaction_manager.transaction():
            transaction_manager.register_compensation(compensation)
            raise ValueError("Trigger rollback")
    except ValueError:
        pass

    assert compensation_executed[0] is True
```

### Integration Tests

**File:** `backend/tests/test_pipeline_robustness.py` (NEW FILE)

```python
def test_pipeline_rollback_on_llm_failure():
    """Test that pipeline rolls back if LLM expansion fails."""

    # Mock LLM to fail
    with patch('core.ollama_client.ollama.call_mixtral') as mock_llm:
        mock_llm.side_effect = Exception("LLM timeout")

        try:
            pipeline.run_pipeline_with_sources(
                query="Test query",
                youtube_urls=["https://youtube.com/watch?v=test"]
            )
        except Exception:
            pass

    # Verify NO orphaned data in database
    transcripts = db.execute("SELECT * FROM raw_transcripts")
    chunks = db.execute("SELECT * FROM transcript_chunks")

    assert len(transcripts) == 0
    assert len(chunks) == 0
```

---

## 19.6 Success Criteria

**Criterion 1:** All pipeline writes complete atomically
- If ANY stage fails, ALL writes roll back
- Zero orphaned records in database

**Criterion 2:** Error recovery
- Transient errors retry automatically (max 3 attempts)
- Permanent errors rollback cleanly

**Criterion 3:** Cache consistency
- Cache and database always synchronized
- Compensation handlers undo cache writes on rollback

**Criterion 4:** Performance
- Transaction overhead < 5% of total pipeline time
- No deadlocks or lock timeouts under concurrent load

---

# 20. PROMPT/LLM RESILIENCE - CONFIGURATION VALIDATION

## 20.1 Problem Analysis

### Current Implementation Issues

**Issue 1: Missing Prompt File Crashes System**

**File:** `backend/services/extraction/claim_extractor.py` (lines 16-18)

```python
def __init__(self):
    prompt_file = Path(__file__).parent.parent.parent / "prompts" / "claim_extraction.txt"
    with open(prompt_file, "r") as f:  # ← NO ERROR HANDLING
        self.prompt_template = f.read()
```

**Problem:** If `claim_extraction.txt` is deleted or path is wrong, `FileNotFoundError` crashes the entire pipeline.

**Impact:**
- Pipeline fails silently during initialization
- No helpful error message
- User cannot diagnose issue

---

**Issue 2: Inconsistent Fallback Behavior**

**File:** `backend/services/processing/llm_expander.py` (lines 40-52)

```python
# Load prompt template
prompt_file = Path(__file__).parent.parent.parent / "prompts" / "chunk_expansion.txt"
if prompt_file.exists():  # ← HAS FALLBACK
    with open(prompt_file, "r") as f:
        self.prompt_template = f.read()
else:
    # Fallback template
    self.prompt_template = """..."""
```

**Problem:** Inconsistent pattern across modules. Some have fallbacks, some don't.

**Impact:**
- Unpredictable behavior
- Difficult to maintain

---

**Issue 3: No Model Name Validation**

**File:** `backend/core/config.py`

Models are defined as strings from environment variables:

```python
OLLAMA_MIXTRAL_MODEL = os.getenv("OLLAMA_MIXTRAL_MODEL", "mixtral:latest")
OLLAMA_LLAVA_MODEL = os.getenv("OLLAMA_LLAVA_MODEL", "llava:latest")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
```

**Problem:** No validation that these models:
1. Actually exist in Ollama
2. Are pulled and available
3. Are the correct model type (e.g., not using LLaVA for text generation)

**Impact:**
- Pipeline starts, then fails mid-way when model not found
- Wasted processing time
- Confusing error messages

---

**Issue 4: No Pre-Execution Configuration Check**

Before starting an expensive pipeline (multiple LLM calls, database writes), there is NO validation that:
- All prompt files exist
- All models are available
- Configuration values are valid
- Database is accessible

**Impact:**
- Pipeline fails 30 seconds in after expensive operations
- User frustration
- Resource waste

---

## 20.2 Architecture Solution

### Four-Layer Validation System

**Layer 1: Startup Validation**
- Check all prompt files exist on application startup
- Verify Ollama connection and model availability
- Validate database schema
- Fail fast with clear error messages

**Layer 2: Configuration Validator**
- Centralized configuration validation module
- Type checking, range validation
- Required vs. optional settings

**Layer 3: Prompt Manager**
- Centralized prompt file loading
- Automatic fallback templates
- Consistent error handling

**Layer 4: LLM Client Resilience**
- Pre-call model validation
- Structured error responses
- Retry logic with backoff

---

## 20.3 Implementation Specification

### 20.3.1 Configuration Validator

**File:** `backend/core/config_validator.py` (NEW FILE)

```python
"""
Configuration validation for Seikna backend.
Validates prompt files, models, database, and settings on startup.
"""
import os
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass

class ConfigValidator:
    """Validates system configuration before pipeline execution."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Dict[str, Any]:
        """
        Run all validation checks.

        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str]
            }
        """
        self.errors = []
        self.warnings = []

        # Run all checks
        self._validate_prompt_files()
        self._validate_ollama_connection()
        self._validate_ollama_models()
        self._validate_database()
        self._validate_directories()
        self._validate_config_values()

        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings
        }

    def _validate_prompt_files(self):
        """Check that all required prompt files exist."""
        from core.config import BACKEND_DIR

        prompts_dir = BACKEND_DIR / "prompts"
        required_prompts = [
            "claim_extraction.txt",
            "chunk_expansion.txt",
            "course_structure.txt",
        ]

        if not prompts_dir.exists():
            self.errors.append(
                f"Prompts directory not found: {prompts_dir}. "
                "Create directory and add prompt files."
            )
            return

        for prompt_file in required_prompts:
            path = prompts_dir / prompt_file
            if not path.exists():
                self.errors.append(
                    f"Required prompt file missing: {prompt_file}. "
                    f"Expected at: {path}"
                )
            elif path.stat().st_size == 0:
                self.warnings.append(f"Prompt file is empty: {prompt_file}")

    def _validate_ollama_connection(self):
        """Check that Ollama service is reachable."""
        from core.config import OLLAMA_BASE_URL

        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            self.errors.append(
                f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
                "Ensure Ollama is running: `ollama serve`"
            )
        except requests.exceptions.Timeout:
            self.errors.append(
                f"Ollama connection timeout at {OLLAMA_BASE_URL}. "
                "Check network or Ollama performance."
            )
        except Exception as e:
            self.errors.append(f"Ollama connection error: {e}")

    def _validate_ollama_models(self):
        """Check that required models are pulled and available."""
        from core.config import (
            OLLAMA_BASE_URL,
            OLLAMA_MIXTRAL_MODEL,
            OLLAMA_EMBED_MODEL,
        )

        required_models = {
            "Mixtral (text generation)": OLLAMA_MIXTRAL_MODEL,
            "Nomic-Embed (embeddings)": OLLAMA_EMBED_MODEL,
        }

        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
            available_models = [model["name"] for model in response.json().get("models", [])]

            for model_name, model_id in required_models.items():
                if model_id not in available_models:
                    self.errors.append(
                        f"Required model not found: {model_name} ({model_id}). "
                        f"Pull it with: `ollama pull {model_id}`"
                    )

        except Exception as e:
            # Ollama connection already checked, skip if failed
            pass

    def _validate_database(self):
        """Check that database is accessible and schema is initialized."""
        from core.config import DB_PATH

        if not DB_PATH.exists():
            self.warnings.append(
                f"Database file not found at {DB_PATH}. "
                "Will be created on first run."
            )
            return

        # Try to connect
        try:
            from core.database import db

            # Check that required tables exist
            required_tables = [
                "sources",
                "claims",
                "courses",
                "raw_transcripts",
                "transcript_chunks",
                "expanded_chunks",
            ]

            for table in required_tables:
                result = db.execute_one(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                if not result:
                    self.errors.append(
                        f"Required database table missing: {table}. "
                        "Run schema initialization."
                    )

        except Exception as e:
            self.errors.append(f"Database connection error: {e}")

    def _validate_directories(self):
        """Check that required directories exist."""
        from core.config import DATA_DIR, CACHE_DIR, FRAMES_DIR

        directories = {
            "Data directory": DATA_DIR,
            "Cache directory": CACHE_DIR,
            "Frames directory": FRAMES_DIR,
        }

        for name, path in directories.items():
            if not path.exists():
                self.warnings.append(
                    f"{name} not found at {path}. Will be created automatically."
                )

    def _validate_config_values(self):
        """Validate configuration value ranges and types."""
        from core.config import (
            CHUNK_TARGET_SIZE,
            CHUNK_MIN_SIZE,
            CHUNK_MAX_SIZE,
            MIN_COHERENCE_SCORE,
            LLM_TEMPERATURE,
        )

        # Chunk size validation
        if CHUNK_MIN_SIZE >= CHUNK_TARGET_SIZE:
            self.errors.append(
                f"CHUNK_MIN_SIZE ({CHUNK_MIN_SIZE}) must be < CHUNK_TARGET_SIZE ({CHUNK_TARGET_SIZE})"
            )

        if CHUNK_TARGET_SIZE >= CHUNK_MAX_SIZE:
            self.errors.append(
                f"CHUNK_TARGET_SIZE ({CHUNK_TARGET_SIZE}) must be < CHUNK_MAX_SIZE ({CHUNK_MAX_SIZE})"
            )

        # Quality threshold validation
        if not (0.0 <= MIN_COHERENCE_SCORE <= 1.0):
            self.errors.append(
                f"MIN_COHERENCE_SCORE ({MIN_COHERENCE_SCORE}) must be between 0.0 and 1.0"
            )

        # Temperature validation
        if not (0.0 <= LLM_TEMPERATURE <= 1.0):
            self.warnings.append(
                f"LLM_TEMPERATURE ({LLM_TEMPERATURE}) outside normal range [0.0, 1.0]"
            )

# Global validator instance
config_validator = ConfigValidator()
```

---

### 20.3.2 Prompt Manager

**File:** `backend/core/prompt_manager.py` (NEW FILE)

```python
"""
Centralized prompt file management with fallback templates.
"""
from pathlib import Path
from typing import Dict, Optional

class PromptManager:
    """Manages prompt file loading with consistent fallback behavior."""

    def __init__(self):
        from core.config import BACKEND_DIR
        self.prompts_dir = BACKEND_DIR / "prompts"
        self.loaded_prompts: Dict[str, str] = {}

        # Fallback templates
        self.fallback_templates = {
            "claim_extraction": self._get_claim_extraction_fallback(),
            "chunk_expansion": self._get_chunk_expansion_fallback(),
            "course_structure": self._get_course_structure_fallback(),
        }

    def get_prompt(self, prompt_name: str) -> str:
        """
        Load prompt by name with fallback.

        Args:
            prompt_name: Name of prompt file (without .txt extension)

        Returns:
            Prompt template string
        """
        # Return cached if already loaded
        if prompt_name in self.loaded_prompts:
            return self.loaded_prompts[prompt_name]

        # Try to load from file
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"

        if prompt_file.exists():
            try:
                with open(prompt_file, "r") as f:
                    template = f.read()

                # Validate not empty
                if not template.strip():
                    raise ValueError(f"Prompt file is empty: {prompt_file}")

                # Cache and return
                self.loaded_prompts[prompt_name] = template
                return template

            except Exception as e:
                print(f"Warning: Failed to load prompt file {prompt_file}: {e}")
                # Fall through to fallback

        # Use fallback template
        if prompt_name in self.fallback_templates:
            print(f"Using fallback template for: {prompt_name}")
            template = self.fallback_templates[prompt_name]
            self.loaded_prompts[prompt_name] = template
            return template

        # No fallback available
        raise FileNotFoundError(
            f"Prompt file not found and no fallback available: {prompt_name}.txt. "
            f"Expected at: {prompt_file}"
        )

    def _get_claim_extraction_fallback(self) -> str:
        """Fallback template for claim extraction."""
        return """You are a knowledge extraction assistant.

Given the following transcript chunk, extract ALL factual claims as structured triples.

TRANSCRIPT:
\"\"\"
{transcript_chunk}
\"\"\"

For each claim, output in this format:
("subject", "predicate", "object")

RULES:
1. Extract ONLY factual claims, not opinions or speculation
2. Keep claims atomic (one fact per triple)
3. Preserve technical terminology exactly

EXAMPLE:
Input: "Neural networks are inspired by biological neurons."
Output:
("Neural networks", "are inspired by", "biological neurons")

Now extract claims from the transcript above."""

    def _get_chunk_expansion_fallback(self) -> str:
        """Fallback template for chunk expansion."""
        return """Expand this educational content chunk with detailed explanations.

CHUNK:
{chunk_text}

TOPIC: {topic}

PREVIOUS CONTEXT: {previous_context}

Provide a JSON response with:
{{
  "expanded_explanation": "Detailed explanation (500-800 words)",
  "key_concepts": ["concept1", "concept2", ...],
  "definitions": {{"term1": "definition1", ...}},
  "examples": ["example1", "example2", ...],
  "prerequisites": ["prerequisite1", ...],
  "claims": [
    {{"subject": "X", "predicate": "is", "object": "Y", "confidence": 0.95}},
    ...
  ]
}}"""

    def _get_course_structure_fallback(self) -> str:
        """Fallback template for course structure generation."""
        return """You are an expert curriculum designer.

Create a structured learning course for: {topic}

VERIFIED CLAIMS:
{verified_claims}

Create a course outline with these sections:
1. Overview
2. Prerequisites
3. Fundamentals
4. Examples
5. Summary

Output as JSON with title, description, and sections array."""

# Global prompt manager instance
prompt_manager = PromptManager()
```

---

### 20.3.3 Updated LLM Modules

**File:** `backend/services/extraction/claim_extractor.py` (MODIFICATIONS)

```python
class ClaimExtractor:
    """Extracts atomic knowledge claims from transcripts."""

    def __init__(self):
        # Use prompt manager instead of direct file loading
        from core.prompt_manager import prompt_manager
        self.prompt_template = prompt_manager.get_prompt("claim_extraction")
```

**File:** `backend/services/processing/llm_expander.py` (MODIFICATIONS)

```python
class ChunkExpander:
    """LLM-powered chunk expansion"""

    def __init__(
        self,
        model_name: str = EXPANSION_MODEL,
        temperature: float = EXPANSION_TEMPERATURE,
        max_tokens: int = EXPANSION_MAX_TOKENS,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Use prompt manager
        from core.prompt_manager import prompt_manager
        self.prompt_template = prompt_manager.get_prompt("chunk_expansion")
```

---

### 20.3.4 Startup Validation Hook

**File:** `backend/api/main.py` (MODIFICATIONS)

```python
from fastapi import FastAPI
from core.config_validator import config_validator

app = FastAPI(title="Seikna API")

@app.on_event("startup")
async def validate_configuration():
    """Validate configuration on application startup."""

    print("🔍 Validating configuration...")

    validation_result = config_validator.validate_all()

    # Print warnings
    for warning in validation_result["warnings"]:
        print(f"⚠️  WARNING: {warning}")

    # Print errors and fail if invalid
    if not validation_result["valid"]:
        print("\n❌ CONFIGURATION ERRORS DETECTED:\n")
        for error in validation_result["errors"]:
            print(f"   ❌ {error}")
        print("\n🛑 Application startup aborted due to configuration errors.\n")
        raise SystemExit(1)

    print("✅ Configuration validated successfully\n")
```

---

### 20.3.5 Pre-Pipeline Validation

**File:** `backend/core/pipeline.py` (MODIFICATIONS)

```python
def run_course_creation_pipeline(
    self,
    query: str,
    num_sources: int = 5,
    source_types: List[str] = None,
    difficulty: Optional[str] = None,
) -> str:
    """Run the complete enhanced pipeline to create a course."""

    # PRE-EXECUTION VALIDATION
    from core.config_validator import config_validator

    validation = config_validator.validate_all()
    if not validation["valid"]:
        error_msg = "Configuration errors detected:\n" + "\n".join(validation["errors"])
        raise ConfigurationError(error_msg)

    # Proceed with pipeline...
    # (rest of existing implementation)
```

---

## 20.4 Testing Requirements

### Unit Tests

**File:** `backend/tests/test_config_validator.py` (NEW FILE)

```python
def test_validate_prompt_files_success():
    """Test prompt file validation when all files exist."""
    validator = ConfigValidator()
    validator._validate_prompt_files()
    assert len(validator.errors) == 0

def test_validate_prompt_files_missing():
    """Test prompt file validation when file is missing."""
    # Rename file temporarily
    import shutil
    from core.config import BACKEND_DIR

    prompt_file = BACKEND_DIR / "prompts" / "claim_extraction.txt"
    backup_file = prompt_file.with_suffix(".txt.bak")

    shutil.move(prompt_file, backup_file)

    try:
        validator = ConfigValidator()
        validator._validate_prompt_files()
        assert any("claim_extraction.txt" in error for error in validator.errors)
    finally:
        shutil.move(backup_file, prompt_file)

def test_validate_ollama_models_missing():
    """Test model validation when model not pulled."""
    # Mock Ollama response without required model
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "models": [{"name": "some_other_model"}]
        }

        validator = ConfigValidator()
        validator._validate_ollama_models()

        assert any("mixtral" in error.lower() for error in validator.errors)
```

---

## 20.5 Success Criteria

**Criterion 1:** No runtime failures from missing prompt files
- All prompt files validated on startup
- Fallback templates used when files missing
- Clear error messages guide user to fix

**Criterion 2:** Model availability verified before pipeline
- Ollama connection checked
- Required models validated
- Pipeline fails fast if models missing

**Criterion 3:** Consistent error handling
- All modules use prompt_manager
- All LLM calls have fallback behavior
- Structured error messages

---

# 21. COURSE BUILDER ALIGNMENT - REMOVE LEGACY PATHS

## 21.1 Problem Analysis

### Current Implementation Issues

**Issue 1: Legacy Storage Method Exists**

**File:** `backend/core/pipeline.py` (lines 616-647)

```python
def _store_course(
    self,
    course_id: str,
    query: str,
    structure: Dict[str, Any],
    source_ids: List[str],
) -> None:
    """Store course in database (legacy method for compatibility)."""
    # ... (old implementation)
```

**Problem:** This method is marked "legacy" but still exists. It's unclear:
- Is it still being called?
- Can it be safely removed?
- Does it conflict with `_store_enhanced_course()`?

**Impact:**
- Code duplication
- Maintenance burden
- Potential bugs if both paths used inconsistently

---

**Issue 2: Two Entry Points Share Common Path (GOOD)**

Both `run_course_creation_pipeline()` and `run_pipeline_with_sources()` call the shared `_process_sources_into_course()` method.

**This is CORRECT architecture** - no issue here.

However, need to verify:
- Are there any other entry points?
- Any routes bypassing the unified path?

---

**Issue 3: No Documentation of Call Graph**

It's unclear from code alone:
- Which methods call which
- What the execution flow is
- Which methods are public API vs. internal

**Impact:**
- Difficult to maintain
- Risk of breaking changes
- Hard to onboard new developers

---

## 21.2 Architecture Solution

### Three-Step Cleanup

**Step 1: Remove Legacy Code**
- Delete `_store_course()` method
- Verify no callers exist
- Remove any other unused methods

**Step 2: Formalize Entry Points**
- Document public vs. private methods
- Add deprecation warnings if needed
- Ensure all routes use unified path

**Step 3: Add Architecture Documentation**
- Create call graph diagram
- Document execution flow
- Add method docstrings clarifying usage

---

## 21.3 Implementation Specification

### 21.3.1 Code Removal

**File:** `backend/core/pipeline.py` (DELETIONS)

**Action:** DELETE `_store_course()` method (lines 616-647)

**Verification Steps:**
1. Search codebase for calls to `_store_course()`:
   ```bash
   grep -r "_store_course" backend/
   ```

2. If NO callers found, safe to delete

3. If callers found, update them to use `_store_enhanced_course_transactional()`

---

### 21.3.2 Method Visibility Documentation

**File:** `backend/core/pipeline.py` (MODIFICATIONS)

**Add docstring annotations:**

```python
class CourseCreationPipeline:
    """
    Orchestrates the end-to-end course creation process.

    PUBLIC API (Entry Points):
    - run_course_creation_pipeline() - Automatic source discovery
    - run_pipeline_with_sources() - Explicit URL input

    INTERNAL METHODS (Do not call directly):
    - _process_sources_into_course() - Shared processing path
    - _store_source() - Source persistence
    - _store_transcript_transactional() - Transcript storage
    - _store_chunks_transactional() - Chunk storage
    - _store_expanded_chunks_transactional() - Expansion storage
    - _store_claim_transactional() - Claim storage
    - _store_consensus_claim_transactional() - Consensus storage
    - _store_contradiction_transactional() - Contradiction storage
    - _store_enhanced_course_transactional() - Course storage
    - _section_to_dict() - Helper for JSON conversion
    """
```

---

### 21.3.3 Call Graph Documentation

**File:** `backend/docs/PIPELINE_ARCHITECTURE.md` (NEW FILE)

```markdown
# Pipeline Architecture - Call Graph

## Entry Points

### Public API

**1. run_course_creation_pipeline(query, num_sources, source_types, difficulty)**
- **Purpose:** Automatic source discovery + course creation
- **Used by:** API route `/api/v1/courses/create` (automatic mode)
- **Flow:**
  ```
  run_course_creation_pipeline()
    → source_discoverer.discover_sources()
    → youtube_fetcher.fetch_youtube_transcript() [for each YouTube URL]
    → article_scraper.fetch_article() [for each article URL]
    → _store_source() [for each source]
    → _process_sources_into_course()
  ```

**2. run_pipeline_with_sources(query, youtube_urls, article_urls)**
- **Purpose:** Explicit URL input + course creation
- **Used by:** API route `/api/v1/courses/create` (manual mode)
- **Flow:**
  ```
  run_pipeline_with_sources()
    → youtube_fetcher.fetch_youtube_transcript() [for each URL]
    → article_scraper.fetch_article() [for each URL]
    → _store_source() [for each source]
    → _process_sources_into_course()
  ```

---

## Shared Processing Path

**_process_sources_into_course(query, course_id, sources)**

This is the UNIFIED path used by both entry points.

**Flow:**
```
_process_sources_into_course()
  │
  ├─ STAGE 3: Transcription & Normalization
  │    → normalize_youtube_transcript() OR normalize_article_content()
  │    → validate_transcript()
  │    → _store_transcript_transactional()
  │
  ├─ STAGE 4: Semantic Chunking
  │    → SemanticChunker.chunk_transcript()
  │    → rechunk_if_needed()
  │    → _store_chunks_transactional()
  │
  ├─ STAGE 5: LLM Expansion
  │    → ChunkExpander.expand_batch()
  │    → _store_expanded_chunks_transactional()
  │
  ├─ STAGE 6: Claim Extraction
  │    → _store_claim_transactional() [for each claim]
  │
  ├─ STAGE 6.5: Consensus & Contradiction Detection
  │    → consensus_builder.build_consensus()
  │    → _store_consensus_claim_transactional()
  │    → _store_contradiction_transactional()
  │
  └─ STAGE 7-9: Course Building & Storage
       → build_complete_course()
       → _store_enhanced_course_transactional()
```

---

## Internal Storage Methods

All storage methods follow the pattern:
- `_store_X_transactional(data, conn)` - Writes within transaction
- Called ONLY from `_process_sources_into_course()`
- Never called directly by API routes

**Storage Methods:**
1. `_store_transcript_transactional()` - Writes raw_transcripts + transcript_segments
2. `_store_chunks_transactional()` - Writes transcript_chunks
3. `_store_expanded_chunks_transactional()` - Writes expanded_chunks
4. `_store_claim_transactional()` - Writes claims
5. `_store_consensus_claim_transactional()` - Writes consensus_claims
6. `_store_contradiction_transactional()` - Writes contradictions
7. `_store_enhanced_course_transactional()` - Writes courses + course_sections + section_citations + course_sources

---

## Deprecated Methods

**REMOVED:**
- `_store_course()` - Legacy non-transactional storage (replaced by `_store_enhanced_course_transactional()`)
```

---

### 21.3.4 API Route Verification

**File:** `backend/api/routes/courses.py` (VERIFICATION)

**Check that all routes use public API:**

```python
@router.post("/create")
def create_course(request: CourseCreateRequest):
    """Create course endpoint."""

    # Should call ONE of these:
    # - pipeline.run_course_creation_pipeline() (automatic mode)
    # - pipeline.run_pipeline_with_sources() (manual mode)

    # Should NOT call:
    # - pipeline._process_sources_into_course() directly (internal method)
    # - pipeline._store_course() (deleted legacy method)
```

---

## 21.4 Testing Requirements

### Code Search Verification

**Script:** `backend/scripts/verify_no_legacy_calls.sh` (NEW FILE)

```bash
#!/bin/bash

echo "Searching for legacy method calls..."

# Check for _store_course calls
if grep -r "_store_course" backend/ --exclude-dir=tests | grep -v "# REMOVED"; then
    echo "❌ ERROR: Found calls to legacy _store_course() method"
    exit 1
fi

# Check for direct calls to internal methods from routes
if grep -r "_process_sources_into_course" backend/api/ --exclude-dir=tests; then
    echo "❌ ERROR: API routes calling internal _process_sources_into_course() directly"
    exit 1
fi

echo "✅ No legacy method calls found"
```

---

## 21.5 Success Criteria

**Criterion 1:** Zero legacy code
- `_store_course()` method removed
- No unused helper methods
- Code size reduced

**Criterion 2:** All routes use public API
- No routes call internal methods directly
- Clear separation of concerns

**Criterion 3:** Documented architecture
- Call graph diagram exists
- All methods have docstrings
- Entry points clearly marked

---

# 22. TIER 1 IMPLEMENTATION ROADMAP FOR CURSOR

## 22.1 Implementation Order

**CRITICAL:** Implement in this exact order due to dependencies.

### Week 1: Pipeline Robustness (2-3 days)

**Day 1: Transaction Infrastructure**
- [ ] Create `backend/core/transaction.py`
- [ ] Implement `TransactionManager` class
- [ ] Implement `transaction()` context manager
- [ ] Implement `savepoint()` for nested transactions
- [ ] Implement `register_compensation()` for external operations
- [ ] Implement `retry_on_transient_error` decorator
- [ ] Add unit tests for transaction manager

**Day 2: Database Enhancements**
- [ ] Modify `backend/core/database.py`
- [ ] Add `execute_write_in_transaction()` method
- [ ] Update `get_connection()` to support transaction context
- [ ] Add unit tests for transactional writes

**Day 3: Pipeline Transactionalization**
- [ ] Modify `backend/core/pipeline.py`
- [ ] Wrap `_process_sources_into_course()` in transaction
- [ ] Create transactional variants of all `_store_*` methods:
  - [ ] `_store_transcript_transactional()`
  - [ ] `_store_chunks_transactional()`
  - [ ] `_store_expanded_chunks_transactional()`
  - [ ] `_store_claim_transactional()`
  - [ ] `_store_consensus_claim_transactional()`
  - [ ] `_store_contradiction_transactional()`
  - [ ] `_store_enhanced_course_transactional()`
- [ ] Add cache compensation logic to `_store_source()`
- [ ] Add `delete_source()` method to `cache_manager.py`
- [ ] Integration test: pipeline rollback on failure

---

### Week 1: Prompt/LLM Resilience (1-2 days)

**Day 1: Configuration Validation**
- [ ] Create `backend/core/config_validator.py`
- [ ] Implement `ConfigValidator` class
- [ ] Implement validation methods:
  - [ ] `_validate_prompt_files()`
  - [ ] `_validate_ollama_connection()`
  - [ ] `_validate_ollama_models()`
  - [ ] `_validate_database()`
  - [ ] `_validate_directories()`
  - [ ] `_validate_config_values()`
- [ ] Add unit tests for all validation methods

**Day 2: Prompt Manager + Integration**
- [ ] Create `backend/core/prompt_manager.py`
- [ ] Implement `PromptManager` class
- [ ] Implement `get_prompt()` with fallback logic
- [ ] Add fallback template methods
- [ ] Update `backend/services/extraction/claim_extractor.py` to use `prompt_manager`
- [ ] Update `backend/services/processing/llm_expander.py` to use `prompt_manager`
- [ ] Update `backend/services/processing/course_builder.py` to use `prompt_manager`
- [ ] Add startup validation hook to `backend/api/main.py`
- [ ] Add pre-pipeline validation to `pipeline.py`
- [ ] Integration test: system starts with missing prompt file (uses fallback)

---

### Week 1: Course Builder Alignment (0.5 days)

**Tasks:**
- [ ] Delete `_store_course()` method from `backend/core/pipeline.py` (lines 616-647)
- [ ] Search codebase for any callers: `grep -r "_store_course" backend/`
- [ ] If callers found, update them to use `_store_enhanced_course_transactional()`
- [ ] Add method visibility docstrings to `CourseCreationPipeline` class
- [ ] Create `backend/docs/PIPELINE_ARCHITECTURE.md` with call graph documentation
- [ ] Verify all API routes use public entry points (no direct internal calls)
- [ ] Create `backend/scripts/verify_no_legacy_calls.sh` verification script
- [ ] Run verification script in CI/CD pipeline

---

## 22.2 Testing Checklist

**Transaction Tests:**
- [ ] Transaction commits on success
- [ ] Transaction rolls back on error
- [ ] Compensation handlers execute on rollback
- [ ] Nested savepoints work correctly
- [ ] Retry decorator handles transient errors
- [ ] Pipeline rollback leaves zero orphaned data

**Configuration Tests:**
- [ ] Missing prompt file detected
- [ ] Missing Ollama model detected
- [ ] Ollama connection failure detected
- [ ] Invalid config values detected
- [ ] Fallback templates used correctly
- [ ] Startup validation prevents bad configuration

**Alignment Tests:**
- [ ] Legacy methods removed
- [ ] No legacy method calls exist
- [ ] All routes use public API
- [ ] Documentation accurate

---

## 22.3 Acceptance Criteria

**Pipeline Robustness:**
- ✅ 100% of pipeline writes are transactional
- ✅ Zero orphaned records on failure
- ✅ Cache stays synchronized with database
- ✅ Transient errors retry automatically
- ✅ Performance overhead < 5%

**Prompt/LLM Resilience:**
- ✅ Application starts with missing prompt files (uses fallbacks)
- ✅ Application detects missing Ollama models at startup
- ✅ All configuration errors surface before pipeline execution
- ✅ Consistent error handling across all LLM modules
- ✅ Clear error messages guide users to fixes

**Course Builder Alignment:**
- ✅ Zero legacy methods exist
- ✅ All API routes use documented entry points
- ✅ Call graph documentation complete
- ✅ Verification script passes

---

## 22.4 Migration Notes

**Backwards Compatibility:**
- Tier 1 changes are **backwards compatible** with existing data
- No database schema changes required (only behavior changes)
- Existing courses remain valid

**Deployment:**
1. Deploy code changes
2. Run startup validation
3. Test course creation with both entry points
4. Monitor for transaction rollbacks (should be rare)

**Rollback Plan:**
- If issues found, revert to previous commit
- Transaction logic can be disabled via feature flag: `USE_TRANSACTIONS = False`

---

**END OF TIER 1 ARCHITECTURE SPECIFICATIONS**

---

**END OF SYSTEM NOTES**
