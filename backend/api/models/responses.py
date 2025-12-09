"""
Pydantic response models for API endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class CourseCreateResponse(BaseModel):
    """Response model for course creation."""
    job_id: str = Field(..., description="Job ID for tracking")
    status: str = Field(..., description="Job status")
    estimated_time: Optional[int] = Field(default=60, description="Estimated processing time in seconds")
    course_id: Optional[str] = Field(default=None, description="Course ID if completed immediately")


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str
    course_id: Optional[str] = None
    progress: int = Field(ge=0, le=100, description="Progress percentage")


class SourceMetadata(BaseModel):
    """Metadata about a source."""
    source_count: int
    difficulty: Optional[str] = None
    estimated_time: Optional[str] = None
    vct_tier: Optional[int] = None


class Section(BaseModel):
    """Course section."""
    id: str
    title: str
    content: str
    sources: List[str] = []


class GlossaryTerm(BaseModel):
    """Glossary term."""
    term: str
    definition: str


class CourseResponse(BaseModel):
    """Response model for course retrieval."""
    course_id: str
    title: str
    description: str
    metadata: SourceMetadata
    sections: List[Section]
    glossary: List[GlossaryTerm] = []


class Citation(BaseModel):
    """Citation for a chatbot response."""
    section_id: str
    section_title: str
    source: str


class ChatResponse(BaseModel):
    """Response model for chatbot."""
    response: str
    citations: List[Citation] = []
    confidence: str = "medium"


class ProgressResponse(BaseModel):
    """Response model for progress update."""
    xp_earned: int
    new_total_xp: int
    badges_unlocked: List[str] = []
    level_up: bool = False

