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
_process_sources_into_course() [WRAPPED IN TRANSACTION]
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

## Transaction Management

The entire `_process_sources_into_course()` method is wrapped in a database transaction:
- **Transaction Manager:** `core.transaction.TransactionManager`
- **Isolation Level:** IMMEDIATE (prevents concurrent writes)
- **Rollback:** If ANY stage fails, ALL writes are rolled back
- **Compensation:** Cache writes are undone via compensation handlers on rollback

---

## Deprecated Methods

**REMOVED:**
- `_store_course()` - Legacy non-transactional storage (replaced by `_store_enhanced_course_transactional()`)

