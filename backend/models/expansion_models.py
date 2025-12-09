"""
Data models for expanded chunks.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class ExpandedChunk:
    """Chunk expanded with LLM processing"""
    chunk_id: str
    source_chunk_id: str  # References TranscriptChunk
    
    # Core content
    original_text: str
    expanded_explanation: str = ""
    
    # Structured extractions
    key_concepts: List[str] = field(default_factory=list)
    definitions: Dict[str, str] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    
    # Claims (atomic facts)
    claims: List[Dict[str, str]] = field(default_factory=list)  # [{subject, predicate, object, confidence}]
    
    # Educational metadata
    difficulty_level: str = "intermediate"  # 'beginner' | 'intermediate' | 'advanced'
    cognitive_load: float = 0.5  # 0.0-1.0
    
    # Processing metadata
    llm_model: str = "mixtral:latest"
    expansion_timestamp: Optional[datetime] = None
    token_count: int = 0

