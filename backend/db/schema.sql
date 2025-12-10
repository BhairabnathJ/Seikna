-- Seikna Database Schema
-- SQLite database structure

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,  -- 'youtube' | 'article'
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    transcript TEXT,
    metadata TEXT,  -- JSON string: author, duration, publish_date, etc.
    vct_tier INTEGER,  -- 1-5, NULL for articles
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS frames (
    frame_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    timestamp_ms INTEGER,  -- milliseconds into video
    frame_path TEXT,  -- local file path
    visual_claim TEXT,  -- extracted by LLaVA
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS claims (
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

-- Consensus claims derived from clustering similar claims
CREATE TABLE IF NOT EXISTS consensus_claims (
    consensus_id TEXT PRIMARY KEY,
    subject TEXT,
    predicate TEXT,
    object TEXT,
    support_claim_ids TEXT,  -- JSON array of claim_ids
    support_sources TEXT,    -- JSON array of source_ids
    support_count INTEGER,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS contradictions (
    contradiction_id TEXT PRIMARY KEY,
    claim_id_1 TEXT NOT NULL,
    claim_id_2 TEXT NOT NULL,
    reasoning TEXT,  -- LLM explanation
    FOREIGN KEY (claim_id_1) REFERENCES claims(claim_id),
    FOREIGN KEY (claim_id_2) REFERENCES claims(claim_id)
);

CREATE TABLE IF NOT EXISTS courses (
    course_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    title TEXT,
    description TEXT,
    structure TEXT,  -- JSON string: full course outline
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS course_sources (
    course_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    PRIMARY KEY (course_id, source_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding BLOB,  -- serialized vector
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    total_xp INTEGER DEFAULT 0,
    streak_days INTEGER DEFAULT 0,
    last_active_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_progress (
    user_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    PRIMARY KEY (user_id, course_id, section_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

CREATE TABLE IF NOT EXISTS badges (
    badge_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    icon_url TEXT
);

CREATE TABLE IF NOT EXISTS user_badges (
    user_id TEXT NOT NULL,
    badge_id TEXT NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (badge_id) REFERENCES badges(badge_id)
);

-- Source Discovery Cache
CREATE TABLE IF NOT EXISTS source_discovery_cache (
    query_hash TEXT PRIMARY KEY,  -- SHA256(query + difficulty + params)
    query TEXT NOT NULL,
    youtube_results TEXT,  -- JSON string
    article_results TEXT,  -- JSON string
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP  -- 24 hours from cached_at
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_claims_source ON claims(source_id);
CREATE INDEX IF NOT EXISTS idx_claims_type ON claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_course_sources_course ON course_sources(course_id);
CREATE INDEX IF NOT EXISTS idx_course_sources_source ON course_sources(source_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_course ON embeddings(course_id);
CREATE INDEX IF NOT EXISTS idx_user_progress_user ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_user_progress_course ON user_progress(course_id);
CREATE INDEX IF NOT EXISTS idx_discovery_cache_expires ON source_discovery_cache(expires_at);

-- Enhanced Course Generation Pipeline Tables

-- Store normalized transcripts
CREATE TABLE IF NOT EXISTS raw_transcripts (
    transcript_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    full_text TEXT NOT NULL,
    segment_count INTEGER,
    word_count INTEGER,
    language TEXT,
    quality_score REAL,
    metadata TEXT,  -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

-- Store transcript segments
CREATE TABLE IF NOT EXISTS transcript_segments (
    segment_id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    segment_index INTEGER,
    text TEXT NOT NULL,
    start_time_ms INTEGER,
    end_time_ms INTEGER,
    metadata TEXT,  -- JSON string
    FOREIGN KEY (transcript_id) REFERENCES raw_transcripts(transcript_id)
);

-- Store semantic chunks
CREATE TABLE IF NOT EXISTS transcript_chunks (
    chunk_id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    chunk_index INTEGER,
    text TEXT NOT NULL,
    word_count INTEGER,
    start_time_ms INTEGER,
    end_time_ms INTEGER,
    topic_keywords TEXT,  -- JSON array
    semantic_density REAL,
    coherence_score REAL,
    completeness_score REAL,
    previous_chunk_id TEXT,
    next_chunk_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transcript_id) REFERENCES raw_transcripts(transcript_id),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

-- Store expanded chunks
CREATE TABLE IF NOT EXISTS expanded_chunks (
    expanded_id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    original_text TEXT NOT NULL,
    expanded_explanation TEXT NOT NULL,
    key_concepts TEXT,  -- JSON array
    definitions TEXT,   -- JSON object
    examples TEXT,      -- JSON array
    prerequisites TEXT, -- JSON array
    difficulty_level TEXT,
    cognitive_load REAL,
    llm_model TEXT,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES transcript_chunks(chunk_id)
);

-- Store course sections
CREATE TABLE IF NOT EXISTS course_sections (
    section_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    parent_section_id TEXT,  -- For nested sections
    section_index INTEGER,
    title TEXT NOT NULL,
    subtitle TEXT,
    content TEXT NOT NULL,  -- Markdown
    key_takeaways TEXT,  -- JSON array
    glossary_terms TEXT,  -- JSON object
    practice_questions TEXT,  -- JSON array
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
CREATE TABLE IF NOT EXISTS section_citations (
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
-- Note: SQLite doesn't support ALTER TABLE ADD COLUMN with foreign key easily
-- We'll add it manually if needed, or use a migration script

-- Source Discovery V2 Cache Tables

-- Cache for V2 discovery results
CREATE TABLE IF NOT EXISTS source_discovery_v2_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_normalized TEXT NOT NULL,           -- Normalized query (lowercase, sorted keywords)
    tier TEXT NOT NULL,                        -- "tier1", "youtube", "edu", "wikipedia"
    result_url TEXT NOT NULL,
    result_title TEXT,
    result_snippet TEXT,
    keyword_match_score REAL,                  -- % of keywords matched (future use)
    negative_keyword_flagged BOOLEAN,          -- Future use
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(query_normalized, result_url)       -- Prevent duplicate caching
);

CREATE INDEX IF NOT EXISTS idx_source_v2_cache_query ON source_discovery_v2_cache(query_normalized);
CREATE INDEX IF NOT EXISTS idx_source_v2_cache_tier ON source_discovery_v2_cache(tier);
CREATE INDEX IF NOT EXISTS idx_source_v2_cache_fetched ON source_discovery_v2_cache(fetched_at);

-- Source quality metrics table
CREATE TABLE IF NOT EXISTS source_quality_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    tier TEXT NOT NULL,
    avg_course_rating REAL,                    -- Average rating of courses using this source (future use)
    usage_count INTEGER DEFAULT 0,             -- How many courses used this source (future use)
    transcript_quality_score REAL,             -- 0.0-1.0 (for YouTube, future use)
    last_validated TIMESTAMP,
    is_blacklisted BOOLEAN DEFAULT FALSE,

    UNIQUE(source_url)
);

CREATE INDEX IF NOT EXISTS idx_source_quality_url ON source_quality_metrics(source_url);
CREATE INDEX IF NOT EXISTS idx_source_quality_tier ON source_quality_metrics(tier);

