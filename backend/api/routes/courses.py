"""
Course-related API routes.
"""
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict
import json

from api.models.requests import CourseCreateRequest
from api.models.responses import CourseCreateResponse, JobStatusResponse, CourseResponse, SourceMetadata, Section, GlossaryTerm
from core.pipeline import pipeline
from core.database import db

router = APIRouter()

# Simple job storage (in-memory, replace with Redis in production)
jobs: Dict[str, Dict] = {}


@router.post("/create", response_model=CourseCreateResponse)
async def create_course(
    request: CourseCreateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Initiate course creation from a query.
    For MVP, processes synchronously if URLs are provided.
    """
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    
    try:
        # If URLs are provided, process synchronously for MVP
        if (request.youtube_urls or request.article_urls):
            jobs[job_id] = {"status": "processing", "progress": 0}
            
            # Run pipeline
            course_id = pipeline.run_pipeline_with_sources(
                query=request.query,
                youtube_urls=request.youtube_urls or [],
                article_urls=request.article_urls or [],
            )
            
            jobs[job_id] = {
                "status": "completed",
                "progress": 100,
                "course_id": course_id,
            }
            
            return CourseCreateResponse(
                job_id=job_id,
                status="completed",
                course_id=course_id,
                estimated_time=60,
            )
        else:
            # No URLs provided - use automatic source discovery
            jobs[job_id] = {"status": "processing", "progress": 0}
            
            try:
                # Run pipeline with automatic discovery
                course_id = pipeline.run_course_creation_pipeline(
                    query=request.query,
                    num_sources=request.num_sources or 8,
                    source_types=request.source_types or ["youtube", "article"],
                    difficulty=request.difficulty,
                )
                
                jobs[job_id] = {
                    "status": "completed",
                    "progress": 100,
                    "course_id": course_id,
                }
                
                return CourseCreateResponse(
                    job_id=job_id,
                    status="completed",
                    course_id=course_id,
                    estimated_time=60,
                )
            except Exception as e:
                jobs[job_id] = {"status": "failed", "progress": 0}
                raise HTTPException(status_code=500, detail=str(e))
    
    except Exception as e:
        jobs[job_id] = {"status": "failed", "progress": 0}
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: str):
    """Fetch complete course structure."""
    result = db.execute_one(
        "SELECT * FROM courses WHERE course_id = ?",
        (course_id,)
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Try to get enhanced course sections first
    section_results = db.execute(
        "SELECT * FROM course_sections WHERE course_id = ? ORDER BY section_index",
        (course_id,)
    )
    
    if section_results:
        # Enhanced course with sections in database
        sections = []
        for sec_row in section_results:
            # sqlite3.Row uses bracket access (required columns can be accessed directly)
            section_id = sec_row["section_id"]
                
            # Get primary sources for this section from citations
            citation_results = db.execute(
                "SELECT source_id FROM section_citations WHERE section_id = ?",
                (section_id,)
            )
            source_ids = [row["source_id"] for row in citation_results] if citation_results else []
            
            # Handle optional columns safely
            subtitle_val = sec_row["subtitle"] if "subtitle" in sec_row.keys() else None
            
            sections.append(Section(
                id=section_id,
                title=sec_row["title"],
                content=sec_row["content"],
                sources=source_ids,
            ))
        
        # Get glossary from sections
        glossary_terms = {}
        for sec_row in section_results:
            # sqlite3.Row uses bracket access - handle None safely for optional JSON columns
            glossary_json = sec_row["glossary_terms"] if "glossary_terms" in sec_row.keys() else None
            terms = json.loads(glossary_json or "{}")
            glossary_terms.update(terms)
        
        glossary = [
            GlossaryTerm(term=term, definition=defn)
            for term, defn in glossary_terms.items()
        ]
    else:
        # Legacy course format (structure in JSON)
        # sqlite3.Row uses bracket access - handle None safely
        structure_json = result["structure"] if "structure" in result.keys() else "{}"
        structure = json.loads(structure_json)
        
        sections = [
            Section(
                id=sec.get("id", f"section-{i}"),
                title=sec.get("title", ""),
                content=sec.get("content", ""),
                sources=sec.get("sources", []),
            )
            for i, sec in enumerate(structure.get("sections", []), 1)
        ]
        
        glossary = [
            GlossaryTerm(term=term.get("term", ""), definition=term.get("definition", ""))
            for term in structure.get("glossary", [])
        ]
    
    # Get source count
    source_count_result = db.execute_one(
        "SELECT COUNT(*) as count FROM course_sources WHERE course_id = ?",
        (course_id,)
    )
    # sqlite3.Row uses bracket access - count column always exists in COUNT(*) queries
    source_count = source_count_result["count"] if source_count_result else 0
    
    # Get estimated time from metadata or calculate
    # sqlite3.Row uses bracket access - structure column should always exist
    structure_json = result["structure"]
    structure_data = json.loads(structure_json or "{}")
    metadata_info = structure_data.get("metadata", {})
    estimated_time = f"{metadata_info.get('estimated_duration_minutes', 240) // 60} hours"
    
    # Handle optional title/description columns
    result_title = result["title"] if "title" in result.keys() else None
    result_description = result["description"] if "description" in result.keys() else None
    
    return CourseResponse(
        course_id=course_id,
        title=structure_data.get("title") or result_title or "",
        description=structure_data.get("description") or result_description or "",
        metadata=SourceMetadata(
            source_count=source_count,
            estimated_time=estimated_time,
        ),
        sections=sections,
        glossary=glossary,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Check course creation job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        course_id=job.get("course_id"),
        progress=job.get("progress", 0),
    )

