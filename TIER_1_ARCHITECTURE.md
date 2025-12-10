# TIER 1 FOUNDATION HARDENING - ARCHITECTURAL SPECIFICATIONS

**Architect:** Claude (Sonnet 4.5)
**Date:** 2025-12-09
**Status:** Architectural Design Complete, Ready for Cursor Implementation
**Priority:** CRITICAL - Must be completed before Tier 2/3/4 features

---

## OVERVIEW

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
