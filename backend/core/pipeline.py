"""
Main pipeline orchestration for course creation.
Enhanced with full processing pipeline (Priority 2).
"""
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.ingestion.youtube_fetcher import youtube_fetcher
from services.ingestion.article_scraper import article_scraper
from services.ingestion.source_discoverer import source_discoverer
from services.ingestion.cache_manager import cache_manager
from services.processing.transcriber import (
    normalize_youtube_transcript,
    normalize_article_content,
    validate_transcript,
)
from services.processing.chunker import SemanticChunker, rechunk_if_needed
from services.processing.llm_expander import ChunkExpander
from services.processing.course_builder import build_complete_course
from services.extraction.consensus_builder import consensus_builder
from core.database import db


class CourseCreationPipeline:
    """Orchestrates the end-to-end course creation process."""
    
    def run_course_creation_pipeline(
        self,
        query: str,
        num_sources: int = 5,
        source_types: List[str] = None,
        difficulty: Optional[str] = None,
    ) -> str:
        """
        Run the complete enhanced pipeline to create a course.

        Enhanced Pipeline Stages:
        1. Source Discovery (automatic)
        2. Ingestion (fetch transcripts/articles)
        3. Transcription & Normalization
        4. Semantic Chunking
        5. LLM Expansion
        6. Claim Extraction
        7. Course Structure Generation
        8. Section Synthesis
        9. Final Storage

        Args:
            query: User's search query
            num_sources: Number of sources to gather
            source_types: Types of sources to use (default: ["youtube", "article"])
            difficulty: Optional difficulty level

        Returns:
            course_id: ID of the created course
        """
        if source_types is None:
            source_types = ["youtube", "article"]

        course_id = f"course_{uuid.uuid4().hex[:12]}"

        # STAGE 1: Source Discovery
        num_youtube = num_sources // 2 if "youtube" in source_types else 0
        num_articles = num_sources - num_youtube if "article" in source_types else 0

        discovery_result = source_discoverer.discover_sources(
            query=query,
            num_youtube=num_youtube,
            num_articles=num_articles,
            difficulty=difficulty,
        )

        # STAGE 2: Ingestion
        raw_sources = []
        for url in discovery_result.youtube_urls:
            try:
                source_data = youtube_fetcher.fetch_youtube_transcript(url)
                # Only include sources with valid transcripts
                if source_data.get("transcript"):
                    raw_sources.append(source_data)
                else:
                    print(f"Warning: No transcript available for {url}, skipping")
            except Exception as e:
                print(f"Failed to fetch YouTube video {url}: {e}")

        for url in discovery_result.article_urls:
            try:
                source_data = article_scraper.fetch_article(url)
                raw_sources.append(source_data)
            except Exception as e:
                print(f"Failed to fetch article {url}: {e}")

        if not raw_sources:
            raise ValueError(
                f"No sources with valid transcripts were fetched for query '{query}'. "
                f"Discovery found {len(discovery_result.youtube_urls)} YouTube videos "
                f"and {len(discovery_result.article_urls)} articles. "
                f"Try a different query or ensure videos have captions."
            )

        # Persist sources before downstream foreign-key usage
        raw_sources = [self._store_source(source) for source in raw_sources]

        # STAGE 3-9: Normalize, chunk, expand, extract claims, build course, store
        self._process_sources_into_course(query, course_id, raw_sources)

        return course_id
    
    def run_pipeline_with_sources(
        self,
        query: str,
        youtube_urls: List[str] = None,
        article_urls: List[str] = None,
    ) -> str:
        """
        Run pipeline with explicitly provided URLs.
        
        Args:
            query: User's search query
            youtube_urls: List of YouTube video URLs
            article_urls: List of article URLs
        
        Returns:
            course_id: ID of the created course
        """
        if youtube_urls is None:
            youtube_urls = []
        if article_urls is None:
            article_urls = []
        
        course_id = f"course_{uuid.uuid4().hex[:12]}"
        
        # Step 1: Ingestion
        sources = []
        
        # Fetch YouTube videos
        for url in youtube_urls:
            try:
                source_data = youtube_fetcher.fetch_youtube_transcript(url)
                # Only include sources with valid transcripts
                if source_data.get("transcript"):
                    sources.append(source_data)
                else:
                    print(f"Warning: No transcript available for {url}, skipping")
            except Exception as e:
                print(f"Failed to fetch YouTube video {url}: {e}")
        
        # Fetch articles
        for url in article_urls:
            try:
                source_data = article_scraper.fetch_article(url)
                sources.append(source_data)
            except Exception as e:
                print(f"Failed to fetch article {url}: {e}")
        
        if not sources:
            raise ValueError(
                "No sources with valid transcripts were successfully fetched. "
                "Ensure YouTube videos have captions enabled."
            )

        # Persist sources before claims/chunks reference them
        sources = [self._store_source(source) for source in sources]

        # Step 2-9: Normalize, chunk, expand, extract claims, build course, store
        self._process_sources_into_course(query, course_id, sources)

        return course_id

    def _process_sources_into_course(
        self, query: str, course_id: str, sources: List[Dict[str, Any]]
    ) -> None:
        """Shared processing path that converts stored sources into a course."""
        # STAGE 3: Transcription & Normalization
        transcripts = []

        for source in sources:
            try:
                source_type = source.get(
                    "source_type", "youtube" if "youtube.com" in source.get("url", "") else "article"
                )
                transcript_text = source.get("transcript", "")

                # Skip sources without transcripts
                if not transcript_text or not transcript_text.strip():
                    print(f"Warning: Empty transcript for {source.get('url')}, skipping")
                    continue

                if source_type == "youtube":
                    transcript = normalize_youtube_transcript(
                        source_id=source["source_id"],
                        url=source["url"],
                        title=source.get("title", ""),
                        raw_transcript=transcript_text,
                        metadata=source.get("metadata", {}),
                    )
                else:  # article
                    # For articles, content is already extracted as plain text
                    transcript = normalize_article_content(
                        source_id=source["source_id"],
                        url=source["url"],
                        title=source.get("title", ""),
                        raw_html=f"<p>{transcript_text}</p>",
                        metadata=source.get("metadata", {}),
                    )

                # Validate transcript
                validation = validate_transcript(transcript)
                if validation["is_valid"]:
                    transcripts.append(transcript)
                    # Store in database
                    self._store_transcript(transcript)
                else:
                    print(
                        f"Warning: Transcript validation failed for {source.get('url')}: {validation.get('issues', [])}"
                    )
            except Exception as e:
                print(f"Error normalizing transcript for {source.get('url')}: {e}")

        if not transcripts:
            raise ValueError(
                "No valid transcripts could be created from sources. "
                "Ensure sources have readable transcripts with at least 200 words."
            )

        # STAGE 4: Semantic Chunking
        chunker = SemanticChunker()
        all_chunks = []

        for transcript in transcripts:
            chunks = chunker.chunk_transcript(transcript)
            # Improve chunk quality
            chunks = rechunk_if_needed(chunks)
            all_chunks.extend(chunks)
            # Store chunks
            self._store_chunks(chunks, transcript.source_id)

        if not all_chunks:
            raise ValueError("No chunks could be created from transcripts")

        # STAGE 5: LLM Expansion
        expander = ChunkExpander()
        expanded_chunks = expander.expand_batch(all_chunks)

        # Store expanded chunks
        self._store_expanded_chunks(expanded_chunks)

        # STAGE 6: Claim Extraction (from expanded chunks)
        # Build source_id map from chunks (chunk_id -> source_id)
        all_claims = []
        source_id_map = {chunk.chunk_id: chunk.source_id for chunk in all_chunks}

        for expanded in expanded_chunks:
            # Get source_id from the chunk this expansion is based on
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
                        "timestamp_ms": None,  # Will be enhanced
                    }
                    all_claims.append(claim_data)
                    # Store claim
                    self._store_claim(claim_data)

        # STAGE 6.5: Consensus & Contradiction Detection
        consensus_results = consensus_builder.build_consensus(all_claims)
        for consensus in consensus_results.get("consensus_claims", []):
            self._store_consensus_claim(consensus)

        for contradiction in consensus_results.get("contradictions", []):
            self._store_contradiction(contradiction)

        # STAGE 7 & 8: Course Building & Section Synthesis
        course_data = build_complete_course(
            query=query,
            expanded_chunks=expanded_chunks,
            sources=sources,
            course_id=course_id,
            consensus_claims=consensus_results.get("consensus_claims", []),
        )

        # STAGE 9: Store course and sections
        self._store_enhanced_course(course_data, query, sources)

    def _store_source(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a source and return the stored record (ensures source_id is valid)."""
        source_type = source.get("source_type") or (
            "youtube" if "youtube.com" in source.get("url", "") else "article"
        )
        source_url = source.get("url")
        if not source_url:
            raise ValueError("Source URL is required for persistence")

        existing = db.execute_one(
            "SELECT source_id FROM sources WHERE url = ?", (source_url,)
        )

        # Ensure a stable source_id is present for inserts/updates
        source_id = source.get("source_id")
        if existing:
            source_id = existing["source_id"]
        else:
            source_id = source_id or f"src_{uuid.uuid4().hex[:12]}"
        source["source_id"] = source_id

        # Normalize transcript/content field
        transcript_text = source.get("transcript") or source.get("content") or ""
        metadata = source.get("metadata") or {}

        if existing:
            source["source_id"] = existing["source_id"]
            db.execute_write(
                """
                UPDATE sources
                SET source_type = ?, title = ?, transcript = ?, metadata = ?, vct_tier = ?
                WHERE url = ?
                """,
                (
                    source_type,
                    source.get("title"),
                    transcript_text,
                    json.dumps(metadata),
                    source.get("vct_tier"),
                    source_url,
                ),
            )
        else:
            db.execute_write(
                """
                INSERT INTO sources (source_id, source_type, url, title, transcript, metadata, vct_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source_type,
                    source_url,
                    source.get("title"),
                    transcript_text,
                    json.dumps(metadata),
                    source.get("vct_tier"),
                ),
            )

        # Keep cache in sync for future fetches
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
    
    def _store_transcript(self, transcript) -> None:
        """Store RawTranscript in database."""
        transcript_id = f"trans_{transcript.source_id}_{uuid.uuid4().hex[:8]}"
        
        db.execute_write(
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
                0.8,  # Default quality score
                json.dumps(transcript.metadata),
            )
        )
        
        # Store segments
        for i, segment in enumerate(transcript.segments):
            db.execute_write(
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
    
    def _store_chunks(self, chunks, source_id: str) -> None:
        """Store TranscriptChunks in database."""
        for chunk in chunks:
            transcript_id = chunk.chunk_id.split('_')[1] if '_' in chunk.chunk_id else None
            
            db.execute_write(
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
    
    def _store_expanded_chunks(self, expanded_chunks) -> None:
        """Store ExpandedChunks in database."""
        for expanded in expanded_chunks:
            db.execute_write(
                """
                INSERT INTO expanded_chunks
                (expanded_id, chunk_id, original_text, expanded_explanation, 
                 key_concepts, definitions, examples, prerequisites, 
                 difficulty_level, cognitive_load, llm_model, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expanded.chunk_id,
                    expanded.source_chunk_id,
                    expanded.original_text,
                    expanded.expanded_explanation,
                    json.dumps(expanded.key_concepts),
                    json.dumps(expanded.definitions),
                    json.dumps(expanded.examples),
                    json.dumps(expanded.prerequisites),
                    expanded.difficulty_level,
                    expanded.cognitive_load,
                    expanded.llm_model,
                    expanded.token_count,
                )
            )
    
    def _store_claim(self, claim: Dict[str, Any]) -> None:
        """Store a claim in database."""
        db.execute_write(
            """
            INSERT OR IGNORE INTO claims
            (claim_id, source_id, claim_type, subject, predicate, object, timestamp_ms, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim["claim_id"],
                claim["source_id"],
                claim["claim_type"],
                claim["subject"],
                claim["predicate"],
                claim["object"],
                claim["timestamp_ms"],
                claim["confidence"],
            )
        )

    def _store_consensus_claim(self, consensus: Dict[str, Any]) -> None:
        """Store a consensus claim derived from multiple claims."""
        db.execute_write(
            """
            INSERT OR IGNORE INTO consensus_claims
            (consensus_id, subject, predicate, object, support_claim_ids, support_sources, support_count, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                consensus["consensus_id"],
                consensus.get("subject"),
                consensus.get("predicate"),
                consensus.get("object"),
                json.dumps(consensus.get("support_claim_ids", [])),
                json.dumps(consensus.get("support_sources", [])),
                consensus.get("support_count"),
                consensus.get("confidence"),
            ),
        )

    def _store_contradiction(self, contradiction: Dict[str, Any]) -> None:
        """Persist detected contradictions between claims."""
        db.execute_write(
            """
            INSERT OR IGNORE INTO contradictions
            (contradiction_id, claim_id_1, claim_id_2, reasoning)
            VALUES (?, ?, ?, ?)
            """,
            (
                contradiction["contradiction_id"],
                contradiction["claim_id_1"],
                contradiction["claim_id_2"],
                contradiction.get("reasoning", ""),
            ),
        )
    
    def _store_enhanced_course(
        self,
        course_data: Dict[str, Any],
        query: str,
        sources: List[Dict[str, Any]],
    ) -> None:
        """Store enhanced course with sections."""
        # Store course
        db.execute_write(
            """
            INSERT INTO courses (course_id, query, title, description, structure)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                course_data["course_id"],
                query,
                course_data["title"],
                course_data["description"],
                json.dumps({
                    "sections": [self._section_to_dict(s) for s in course_data["sections"]],
                    "metadata": course_data["metadata"],
                }),
            )
        )
        
        # Store sections
        for section in course_data["sections"]:
            db.execute_write(
                """
                INSERT INTO course_sections
                (section_id, course_id, section_index, title, subtitle, content,
                 key_takeaways, glossary_terms, practice_questions,
                 estimated_reading_minutes, difficulty_level,
                 coherence_score, coverage_score, confidence_score,
                 has_contradictions, controversy_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    section.section_id,
                    section.course_id,
                    section.section_index,
                    section.title,
                    section.subtitle,
                    section.content,
                    json.dumps(section.key_takeaways),
                    json.dumps(section.glossary_terms),
                    json.dumps(section.practice_questions),
                    section.estimated_reading_time_minutes,
                    section.difficulty_level,
                    section.coherence_score,
                    section.coverage_score,
                    section.confidence_score,
                    section.has_contradictions,
                    section.controversy_notes,
                )
            )
            
            # Store citations
            for citation in section.citations:
                db.execute_write(
                    """
                    INSERT INTO section_citations
                    (citation_id, section_id, source_id, timestamp_ms, timestamp_formatted, relevance_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"cite_{uuid.uuid4().hex[:8]}",
                        section.section_id,
                        citation.source_id,
                        citation.timestamp_ms,
                        citation.timestamp_formatted,
                        citation.relevance_score,
                    )
                )
        
        # Link sources
        for source in sources:
            db.execute_write(
                """
                INSERT OR IGNORE INTO course_sources (course_id, source_id)
                VALUES (?, ?)
                """,
                (course_data["course_id"], source["source_id"])
            )
    
    def _section_to_dict(self, section) -> Dict[str, Any]:
        """Convert CourseSection to dictionary for JSON storage."""
        return {
            "id": section.section_id,
            "title": section.title,
            "content": section.content,
            "sources": section.primary_sources,
        }
    
    def _store_course(
        self,
        course_id: str,
        query: str,
        structure: Dict[str, Any],
        source_ids: List[str],
    ) -> None:
        """Store course in database (legacy method for compatibility)."""
        # Insert course
        db.execute_write(
            """
            INSERT INTO courses (course_id, query, title, description, structure)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                course_id,
                query,
                structure.get("title", ""),
                structure.get("description", ""),
                json.dumps(structure),
            )
        )
        
        # Link sources
        for source_id in source_ids:
            db.execute_write(
                """
                INSERT OR IGNORE INTO course_sources (course_id, source_id)
                VALUES (?, ?)
                """,
                (course_id, source_id)
            )


# Global pipeline instance
pipeline = CourseCreationPipeline()

