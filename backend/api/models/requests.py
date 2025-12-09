"""
Pydantic request models for API endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class CourseCreateRequest(BaseModel):
    """Request model for course creation."""
    query: str = Field(..., description="Search query for course topic")
    num_sources: int = Field(default=5, ge=1, le=20, description="Number of sources to gather")
    source_types: List[str] = Field(default=["youtube", "article"], description="Types of sources")
    difficulty: Optional[str] = Field(default=None, description="Difficulty level")
    youtube_urls: Optional[List[str]] = Field(default=None, description="Optional YouTube URLs")
    article_urls: Optional[List[str]] = Field(default=None, description="Optional article URLs")


class ChatRequest(BaseModel):
    """Request model for chatbot."""
    course_id: str = Field(..., description="Course ID")
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for context")


class ProgressCheckpointRequest(BaseModel):
    """Request model for progress checkpoint."""
    user_id: str = Field(..., description="User ID")
    course_id: str = Field(..., description="Course ID")
    section_id: str = Field(..., description="Section ID")

