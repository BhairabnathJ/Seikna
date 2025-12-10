"""
Enhanced course builder for assembling expanded chunks into structured courses.
"""
import json
import re
import uuid
from typing import List, Dict, Optional, Any
from pathlib import Path

from models.expansion_models import ExpandedChunk
from models.course_models import CourseSection, Citation
from core.ollama_client import ollama
from core.config import (
    EXPANSION_MODEL,
    TARGET_TAKEAWAYS_PER_SECTION,
    TARGET_QUESTIONS_PER_SECTION,
    MIN_SECTION_WORD_COUNT,
    MIN_CITATIONS_PER_SECTION,
)
from services.processing.utils import (
    calculate_reading_time,
    format_timestamp,
)
from services.course_builder.structure_generator import structure_generator
from models.transcript_models import TranscriptChunk


class CourseBuilder:
    """Orchestrates course assembly from processed chunks"""
    
    def __init__(
        self,
        model_name: str = EXPANSION_MODEL,
        temperature: float = 0.4
    ):
        """Initialize with LLM configuration"""
        self.model_name = model_name
        self.temperature = temperature
    
    def generate_course_structure(
        self,
        query: str,
        expanded_chunks: List[ExpandedChunk],
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate high-level course outline."""
        # Extract key concepts from all chunks
        all_concepts = []
        for chunk in expanded_chunks:
            all_concepts.extend(chunk.key_concepts)
        
        # Use existing structure generator with chunks
        # Build claims-like structure for compatibility
        claims_text = []
        for chunk in expanded_chunks[:50]:  # Limit for prompt
            for claim in chunk.claims:
                claim_str = f"- ({claim.get('subject', '')}, {claim.get('predicate', '')}, {claim.get('object', '')})"
                claims_text.append(claim_str)
        
        # Use structure generator (will be enhanced later)
        structure = structure_generator.build_course(
            query=query,
            claims=[c for chunk in expanded_chunks for c in chunk.claims],
            sources=sources
        )
        
        # Estimate duration
        total_words = sum(len(c.expanded_explanation.split()) for c in expanded_chunks)
        estimated_duration = max(10, total_words // 200)  # ~200 words per minute
        
        return {
            "title": structure.get("title", f"Introduction to {query}"),
            "description": structure.get("description", f"A comprehensive course about {query}"),
            "sections": structure.get("sections", []),
            "prerequisites": [],
            "estimated_duration_minutes": estimated_duration
        }
    
    def synthesize_section(
        self,
        section_title: str,
        relevant_chunks: List[ExpandedChunk],
        section_index: int,
        course_id: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        consensus_claims: Optional[List[Dict[str, Any]]] = None,
    ) -> CourseSection:
        """Create single CourseSection from chunks."""
        section_id = f"sec_{course_id}_{uuid.uuid4().hex[:8]}"
        
        # Merge chunk content
        content_parts = []
        glossary_terms = {}
        all_sources = set()
        
        # Map chunk_ids to source_ids (extract from chunk_id format: chunk_sourceid_xxx)
        for chunk in relevant_chunks:
            # Add expanded explanation
            if chunk.expanded_explanation:
                content_parts.append(chunk.expanded_explanation)
            else:
                content_parts.append(chunk.original_text)
            
            # Collect glossary terms
            glossary_terms.update(chunk.definitions)
            
            # Extract source_id from chunk_id
            if chunk.source_chunk_id.startswith("chunk_"):
                parts = chunk.source_chunk_id.split('_')
                if len(parts) >= 2:
                    # Format: chunk_sourceid_xxx, so source_id is parts[1]
                    source_id = parts[1] if len(parts) > 1 else "unknown"
                    all_sources.add(source_id)
        
        # Merge content with transitions
        content = self._merge_content_with_transitions(content_parts)
        
        # Generate key takeaways
        key_takeaways = self.generate_key_takeaways(content, relevant_chunks)
        
        # Create citations
        citations = []
        if sources:
            source_map = {s["source_id"]: s for s in sources}
            for source_id in all_sources:
                if source_id in source_map:
                    source = source_map[source_id]
                    citation = Citation(
                        source_id=source_id,
                        source_type=source.get("source_type", "unknown"),
                        title=source.get("title", ""),
                        url=source.get("url", ""),
                        relevance_score=0.8
                    )
                    citations.append(citation)
        
        # Extract primary sources
        primary_sources = list(all_sources)
        
        # Calculate reading time
        reading_time = calculate_reading_time(content)
        
        # Create section
        section = CourseSection(
            section_id=section_id,
            course_id=course_id,
            section_index=section_index,
            title=section_title,
            content=content,
            key_takeaways=key_takeaways,
            glossary_terms=glossary_terms,
            citations=citations,
            primary_sources=primary_sources,
            estimated_reading_time_minutes=reading_time,
            difficulty_level="intermediate",  # Will be calculated
        )
        
        # Calculate scores
        scores = self.calculate_section_scores(section, consensus_claims or [])
        section.coherence_score = scores.get("coherence_score", 0.8)
        section.coverage_score = scores.get("coverage_score", 0.8)
        section.confidence_score = scores.get("confidence_score", 0.8)
        
        return section
    
    def _merge_content_with_transitions(self, content_parts: List[str]) -> str:
        """Merge content parts with transitions."""
        if not content_parts:
            return ""
        
        merged = content_parts[0]
        
        transitions = [
            "\n\nBuilding on this concept, ",
            "\n\nAdditionally, ",
            "\n\nFurthermore, ",
            "\n\nMoreover, ",
        ]
        
        for i, part in enumerate(content_parts[1:], 1):
            transition = transitions[i % len(transitions)]
            merged += transition + part.lower() if part else ""
        
        return merged
    
    def create_citations(
        self,
        chunks: List[ExpandedChunk],
        sources: List[Dict[str, Any]]
    ) -> List[Citation]:
        """Generate source citations for section."""
        citations = []
        source_map = {s["source_id"]: s for s in sources}
        
        # Group chunks by source (would need source_id tracking in chunks)
        # Simplified version for now
        for source in sources:
            citation = Citation(
                source_id=source["source_id"],
                source_type=source.get("source_type", "unknown"),
                title=source.get("title", ""),
                url=source.get("url", ""),
                timestamp_ms=None,
                relevance_score=0.8
            )
            citations.append(citation)
        
        return citations
    
    def generate_key_takeaways(
        self,
        section_content: str,
        chunks: List[ExpandedChunk]
    ) -> List[str]:
        """Extract main points from section."""
        takeaways = []
        
        # Extract from chunk key concepts
        all_concepts = []
        for chunk in chunks:
            all_concepts.extend(chunk.key_concepts[:2])  # Top 2 per chunk
        
        # Get unique concepts
        unique_concepts = list(dict.fromkeys(all_concepts))[:TARGET_TAKEAWAYS_PER_SECTION]
        
        # Convert to takeaways format
        for concept in unique_concepts:
            takeaways.append(f"{concept}")
        
        return takeaways
    
    def generate_practice_questions(
        self,
        section: CourseSection,
        difficulty: str = "mixed",
        count: int = TARGET_QUESTIONS_PER_SECTION
    ) -> List[Dict[str, Any]]:
        """Create quiz questions for section."""
        # Simplified: Generate questions from key concepts
        questions = []
        
        for i, takeaway in enumerate(section.key_takeaways[:count]):
            question = {
                "question": f"What is a key concept about {takeaway}?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct": "A",
                "explanation": f"This concept relates to {takeaway} as explained in the section."
            }
            questions.append(question)
        
        return questions
    
    def merge_sections(
        self,
        sections: List[CourseSection],
        structure: Dict[str, Any]
    ) -> List[CourseSection]:
        """Organize sections into final hierarchy."""
        # Simple implementation: just return sections in order
        # Enhanced version would handle nested subsections
        return sections
    
    def calculate_section_scores(
        self,
        section: CourseSection,
        consensus_claims: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate quality metrics for section."""
        # Coherence: check for proper transitions and flow
        coherence = 0.8  # Simplified
        if len(section.content.split()) >= MIN_SECTION_WORD_COUNT:
            coherence += 0.1
        if len(section.key_takeaways) >= 3:
            coherence += 0.1
        
        # Coverage: how many sources are cited
        coverage = min(1.0, len(section.primary_sources) / max(1, 3))
        
        # Confidence: based on claim agreement (simplified)
        confidence = 0.9  # Default high confidence
        if consensus_claims:
            supporting_sources = set(section.primary_sources)
            aligned_claims = [
                claim
                for claim in consensus_claims
                if supporting_sources.intersection(set(claim.get("support_sources", [])))
            ]
            if aligned_claims:
                avg_conf = sum(claim.get("confidence", 0.8) for claim in aligned_claims) / len(aligned_claims)
                confidence = min(1.0, 0.7 + 0.3 * avg_conf)
        
        return {
            "coherence_score": min(1.0, coherence),
            "coverage_score": coverage,
            "confidence_score": confidence
        }


def build_complete_course(
    query: str,
    expanded_chunks: List[ExpandedChunk],
    sources: List[Dict[str, Any]],
    course_id: str,
    consensus_claims: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Main orchestration function for building complete course.
    
    Returns:
        {
            "course_id": str,
            "title": str,
            "description": str,
            "sections": List[CourseSection],
            "metadata": {...}
        }
    """
    builder = CourseBuilder()
    
    # Generate structure
    structure = builder.generate_course_structure(query, expanded_chunks, sources)
    
    # Create sections
    sections = []
    structure_sections = structure.get("sections", [])
    
    for i, sec_def in enumerate(structure_sections):
        section_title = sec_def.get("title", f"Section {i+1}")
        
        # Find relevant chunks (simplified: use all chunks for now)
        relevant_chunks = expanded_chunks
        
        # Synthesize section
            section = builder.synthesize_section(
                section_title=section_title,
                relevant_chunks=relevant_chunks,
                section_index=i,
                course_id=course_id,
                sources=sources,
                consensus_claims=consensus_claims or [],
            )
        sections.append(section)
    
    return {
        "course_id": course_id,
        "title": structure["title"],
        "description": structure["description"],
        "sections": sections,
        "metadata": {
            "estimated_duration_minutes": structure.get("estimated_duration_minutes", 60),
            "section_count": len(sections),
        }
    }

