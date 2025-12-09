"""
Semantic chunking service for segmenting transcripts into coherent chunks.
"""
import re
import uuid
from typing import List, Optional
from models.transcript_models import RawTranscript, TranscriptChunk
from services.processing.utils import (
    clean_text,
    embed_text,
    embed_batch,
    calculate_cosine_similarity,
    extract_technical_terms,
)
import numpy as np

from core.config import (
    CHUNK_TARGET_SIZE,
    CHUNK_MIN_SIZE,
    CHUNK_MAX_SIZE,
    CHUNK_OVERLAP_SIZE,
    USE_EMBEDDING_CHUNKING,
    MIN_COHERENCE_SCORE,
    MIN_COMPLETENESS_SCORE,
    MIN_SEMANTIC_DENSITY,
)


class SemanticChunker:
    """Stateful chunker with configurable strategy."""
    
    def __init__(
        self,
        target_chunk_size: int = CHUNK_TARGET_SIZE,
        min_chunk_size: int = CHUNK_MIN_SIZE,
        max_chunk_size: int = CHUNK_MAX_SIZE,
        overlap_size: int = CHUNK_OVERLAP_SIZE,
        use_embeddings: bool = USE_EMBEDDING_CHUNKING,
    ):
        """Initialize chunker with parameters."""
        self.target_chunk_size = target_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.use_embeddings = use_embeddings
    
    def chunk_transcript(
        self,
        transcript: RawTranscript
    ) -> List[TranscriptChunk]:
        """
        Create semantic chunks from transcript.
        
        Algorithm:
            1. Sentence segmentation
            2. If use_embeddings: find semantic boundaries
            3. Else: use heuristics (paragraph breaks, punctuation)
            4. Group sentences into chunks
            5. Enforce size constraints
            6. Add overlap for context
            7. Extract topic keywords
            8. Calculate coherence scores
        """
        # Get full text
        full_text = transcript.full_text
        
        if not full_text or len(full_text.strip()) < 50:
            return []
        
        # Segment into sentences
        sentences = self._segment_sentences(full_text)
        
        if not sentences:
            return []
        
        # Find chunk boundaries
        if self.use_embeddings:
            boundaries = self._find_embedding_boundaries(sentences)
        else:
            boundaries = self._find_heuristic_boundaries(sentences, transcript)
        
        # Create chunks
        chunks = []
        for i, boundary in enumerate(boundaries):
            start_idx = boundary
            end_idx = boundaries[i + 1] if i + 1 < len(boundaries) else len(sentences)
            
            chunk_sentences = sentences[start_idx:end_idx]
            chunk_text = " ".join(chunk_sentences)
            word_count = len(chunk_text.split())
            
            # Skip if too small (unless it's the last chunk)
            if word_count < self.min_chunk_size and i < len(boundaries) - 1:
                continue
            
            # Split if too large
            if word_count > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(chunk_text)
                for sub_chunk_text in sub_chunks:
                    chunk = self._create_chunk(
                        transcript,
                        sub_chunk_text,
                        i * len(chunks),  # Approximate index
                        start_idx,
                        end_idx
                    )
                    chunks.append(chunk)
            else:
                chunk = self._create_chunk(
                    transcript,
                    chunk_text,
                    i,
                    start_idx,
                    end_idx
                )
                chunks.append(chunk)
        
        # Link chunks
        for i in range(len(chunks)):
            if i > 0:
                chunks[i].previous_chunk_id = chunks[i-1].chunk_id
            if i < len(chunks) - 1:
                chunks[i].next_chunk_id = chunks[i+1].chunk_id
        
        return chunks
    
    def _segment_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence segmentation
        sentences = re.split(r'[.!?]+\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def _find_embedding_boundaries(self, sentences: List[str]) -> List[int]:
        """Find chunk boundaries using semantic similarity."""
        if len(sentences) <= 1:
            return [0]
        
        boundaries = [0]
        embeddings = embed_batch(sentences)
        
        # Calculate similarity between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = calculate_cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)
        
        # Find significant drops in similarity (topic shifts)
        current_word_count = 0
        for i, sim in enumerate(similarities):
            sentence_word_count = len(sentences[i].split())
            current_word_count += sentence_word_count
            
            # Check if we've reached minimum chunk size and similarity drops
            if current_word_count >= self.min_chunk_size:
                # Significant drop indicates topic shift
                if i > 0 and sim < 0.7:  # Threshold for topic shift
                    boundaries.append(i + 1)
                    current_word_count = 0
                # Force boundary if chunk too large
                elif current_word_count >= self.max_chunk_size:
                    boundaries.append(i + 1)
                    current_word_count = 0
        
        return boundaries
    
    def _find_heuristic_boundaries(
        self,
        sentences: List[str],
        transcript: RawTranscript
    ) -> List[int]:
        """Find boundaries using heuristics."""
        boundaries = [0]
        current_word_count = 0
        
        for i, sentence in enumerate(sentences):
            word_count = len(sentence.split())
            current_word_count += word_count
            
            # Force boundary if chunk too large
            if current_word_count >= self.max_chunk_size:
                boundaries.append(i + 1)
                current_word_count = 0
            # Check for paragraph breaks (if available in segments)
            elif transcript.source_type == "article" and i > 0:
                # Articles have paragraph breaks in segments
                # This is a simplified heuristic
                if current_word_count >= self.target_chunk_size:
                    boundaries.append(i + 1)
                    current_word_count = 0
        
        return boundaries
    
    def _split_large_chunk(self, chunk_text: str) -> List[str]:
        """Split a chunk that exceeds max size."""
        sentences = self._segment_sentences(chunk_text)
        sub_chunks = []
        current_chunk = []
        current_word_count = 0
        
        for sentence in sentences:
            word_count = len(sentence.split())
            if current_word_count + word_count > self.max_chunk_size and current_chunk:
                sub_chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_word_count = word_count
            else:
                current_chunk.append(sentence)
                current_word_count += word_count
        
        if current_chunk:
            sub_chunks.append(" ".join(current_chunk))
        
        return sub_chunks
    
    def _create_chunk(
        self,
        transcript: RawTranscript,
        chunk_text: str,
        chunk_index: int,
        start_sentence_idx: int,
        end_sentence_idx: int
    ) -> TranscriptChunk:
        """Create a TranscriptChunk with metadata."""
        chunk_id = f"chunk_{transcript.source_id}_{uuid.uuid4().hex[:8]}"
        
        # Calculate timestamps (for videos)
        start_time_ms = None
        end_time_ms = None
        if transcript.segments:
            # Find segments that correspond to this chunk
            # Simplified: use first and last segment timestamps
            first_seg = transcript.segments[0]
            if first_seg.start_time_ms is not None:
                start_time_ms = first_seg.start_time_ms
        
        # Extract topic keywords
        topic_keywords = extract_technical_terms(chunk_text, threshold=0.7)
        
        # Calculate semantic density
        semantic_density = self.calculate_semantic_density(chunk_text)
        
        # Calculate coherence score  
        coherence_score = self.calculate_coherence_score(clean_text(chunk_text))
        
        # Calculate completeness score
        completeness_score = self.calculate_completeness_score(chunk_text)
        
        return TranscriptChunk(
            chunk_id=chunk_id,
            source_id=transcript.source_id,
            chunk_index=chunk_index,
            text=clean_text(chunk_text),
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            word_count=len(chunk_text.split()),
            topic_keywords=topic_keywords[:10],  # Limit to top 10
            semantic_density=semantic_density,
            coherence_score=coherence_score,
            completeness_score=completeness_score,
        )
    
    def extract_topic_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """Extract key terms from chunk text."""
        return extract_technical_terms(text, threshold=0.7)[:top_k]
    
    def calculate_coherence_score(self, chunk_text: str) -> float:
        """Measure chunk coherence."""
        # Simple heuristic: check sentence connectivity
        sentences = self._segment_sentences(chunk_text)
        if len(sentences) < 2:
            return 0.8
        
        # Check for transition words and topic consistency
        transition_words = {'however', 'therefore', 'furthermore', 'moreover', 'additionally', 'also', 'next', 'then'}
        word_count = 0
        transition_count = 0
        
        words = chunk_text.lower().split()
        for word in words:
            word_count += 1
            if word in transition_words:
                transition_count += 1
        
        # Coherence increases with proper transitions and topic consistency
        transition_score = min(1.0, transition_count / max(1, len(sentences)))
        
        # Topic consistency (simplified: check for repeated key terms)
        unique_terms = set(extract_technical_terms(chunk_text))
        repetition_score = min(1.0, len(unique_terms) / max(5, len(words) // 20))
        
        coherence = (transition_score * 0.3) + (repetition_score * 0.7)
        return min(1.0, coherence)
    
    def calculate_completeness_score(self, text: str) -> float:
        """Check if chunk has complete thoughts."""
        sentences = self._segment_sentences(text)
        if not sentences:
            return 0.0
        
        # Check if sentences end properly
        proper_endings = sum(1 for s in sentences if s and s[-1] in '.!?')
        completeness = proper_endings / len(sentences) if sentences else 0.0
        
        # Penalize if chunk is too short
        word_count = len(text.split())
        if word_count < self.min_chunk_size:
            completeness *= 0.7
        
        return completeness
    
    def calculate_semantic_density(self, text: str) -> float:
        """Estimate information density."""
        words = text.split()
        if not words:
            return 0.0
        
        # Count unique concepts (technical terms)
        technical_terms = extract_technical_terms(text)
        unique_concepts = len(technical_terms)
        
        # Count unique words
        unique_words = len(set(words))
        
        # Density = ratio of unique concepts to total words
        density = unique_concepts / max(1, len(words)) * 10  # Scale
        
        return min(1.0, density)


def rechunk_if_needed(
    chunks: List[TranscriptChunk],
    quality_threshold: float = MIN_COHERENCE_SCORE
) -> List[TranscriptChunk]:
    """
    Re-chunk low-quality chunks.
    
    Checks:
        - Coherence score < threshold → merge with neighbors
        - Completeness score < threshold → expand boundaries
        - Size violations → split or merge
    """
    if not chunks:
        return chunks
    
    improved_chunks = []
    i = 0
    
    while i < len(chunks):
        chunk = chunks[i]
        
        # Check if chunk needs improvement
        needs_merge = (
            chunk.coherence_score < quality_threshold or
            chunk.completeness_score < MIN_COMPLETENESS_SCORE or
            chunk.word_count < CHUNK_MIN_SIZE
        )
        
        if needs_merge and i < len(chunks) - 1:
            # Try merging with next chunk
            next_chunk = chunks[i + 1]
            merged_text = chunk.text + " " + next_chunk.text
            merged_word_count = len(merged_text.split())
            
            if merged_word_count <= CHUNK_MAX_SIZE:
                # Merge chunks
                chunk.text = merged_text
                chunk.word_count = merged_word_count
                chunk.end_time_ms = next_chunk.end_time_ms
                chunk.next_chunk_id = next_chunk.next_chunk_id
                
                # Recalculate scores
                chunker = SemanticChunker()
                chunk.coherence_score = chunker.calculate_coherence_score(merged_text)
                chunk.completeness_score = chunker.calculate_completeness_score(merged_text)
                chunk.semantic_density = chunker.calculate_semantic_density(merged_text)
                
                improved_chunks.append(chunk)
                i += 2  # Skip next chunk as it's merged
                continue
        
        # Check if chunk is too large
        if chunk.word_count > CHUNK_MAX_SIZE:
            # Split chunk
            chunker = SemanticChunker()
            sentences = chunker._segment_sentences(chunk.text)
            sub_chunks = chunker._split_large_chunk(chunk.text)
            
            for j, sub_text in enumerate(sub_chunks):
                sub_chunk = TranscriptChunk(
                    chunk_id=f"{chunk.chunk_id}_sub{j}",
                    source_id=chunk.source_id,
                    chunk_index=chunk.chunk_index + j,
                    text=sub_text,
                    start_time_ms=chunk.start_time_ms,
                    end_time_ms=chunk.end_time_ms,
                    word_count=len(sub_text.split()),
                    topic_keywords=chunker.extract_topic_keywords(sub_text),
                    semantic_density=chunker.calculate_semantic_density(sub_text),
                    coherence_score=chunker.calculate_coherence_score(sub_text),
                    completeness_score=chunker.calculate_completeness_score(sub_text),
                )
                improved_chunks.append(sub_chunk)
            i += 1
        else:
            improved_chunks.append(chunk)
            i += 1
    
    # Re-link chunks
    for i in range(len(improved_chunks)):
        if i > 0:
            improved_chunks[i].previous_chunk_id = improved_chunks[i-1].chunk_id
        if i < len(improved_chunks) - 1:
            improved_chunks[i].next_chunk_id = improved_chunks[i+1].chunk_id
    
    return improved_chunks

