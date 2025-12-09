"""
Data models for course sections.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class Citation:
    """Source attribution for content"""
    source_id: str
    source_type: str
    title: str
    url: str
    timestamp_ms: Optional[int] = None
    timestamp_formatted: Optional[str] = None  # "02:15" format
    relevance_score: float = 0.0  # 0.0-1.0


@dataclass
class CourseSection:
    """Complete course section"""
    section_id: str
    course_id: str
    section_index: int  # Order in course
    
    # Content
    title: str
    subtitle: Optional[str] = None
    content: str = ""  # Markdown formatted
    
    # Structure
    subsections: List['CourseSection'] = field(default_factory=list)
    
    # Educational elements
    key_takeaways: List[str] = field(default_factory=list)
    glossary_terms: Dict[str, str] = field(default_factory=dict)
    practice_questions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Source attribution
    citations: List[Citation] = field(default_factory=list)
    primary_sources: List[str] = field(default_factory=list)  # source_ids
    
    # Metadata
    estimated_reading_time_minutes: int = 0
    difficulty_level: str = "intermediate"
    prerequisites_section_ids: List[str] = field(default_factory=list)
    
    # Visual content (Phase 2)
    visual_elements: List[Dict[str, Any]] = field(default_factory=list)
    
    # Quality metrics
    coherence_score: float = 0.0
    coverage_score: float = 0.0
    confidence_score: float = 0.0
    
    # Flags
    has_contradictions: bool = False
    controversy_notes: Optional[str] = None

