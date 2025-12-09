"""
Data models for transcripts and chunks.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class TranscriptSegment:
    """Individual timed segment (for videos) or paragraph (for articles)"""
    text: str
    start_time_ms: Optional[int] = None  # None for articles
    end_time_ms: Optional[int] = None
    segment_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawTranscript:
    """Complete source content"""
    source_id: str
    source_type: str  # 'youtube' | 'article'
    title: str
    url: str
    language: str = "en"  # ISO 639-1 code
    total_duration_ms: Optional[int] = None  # None for articles
    segments: List[TranscriptSegment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    fetched_at: Optional[datetime] = None
    
    @property
    def full_text(self) -> str:
        """Concatenated text from all segments"""
        return " ".join(seg.text for seg in self.segments)
    
    @property
    def word_count(self) -> int:
        """Total word count"""
        return len(self.full_text.split())


@dataclass
class TranscriptChunk:
    """Semantic chunk of transcript"""
    chunk_id: str
    source_id: str
    chunk_index: int  # Position in sequence
    text: str
    start_time_ms: Optional[int] = None
    end_time_ms: Optional[int] = None
    word_count: int = 0
    
    # Semantic metadata
    topic_keywords: List[str] = field(default_factory=list)
    semantic_density: float = 0.0  # 0.0-1.0
    
    # Context
    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
    
    # Quality metrics
    coherence_score: float = 0.0  # 0.0-1.0
    completeness_score: float = 0.0  # 0.0-1.0

