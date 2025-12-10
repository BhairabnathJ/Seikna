"""
LLM-powered chunk expansion service.
"""
import json
import re
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

from models.transcript_models import TranscriptChunk
from models.expansion_models import ExpandedChunk
from core.ollama_client import ollama
from core.config import (
    EXPANSION_MODEL,
    EXPANSION_TEMPERATURE,
    EXPANSION_MAX_TOKENS,
    MIN_CLAIMS_PER_CHUNK,
    MAX_COGNITIVE_LOAD,
    LLM_BATCH_SIZE,
)
from services.processing.utils import calculate_flesch_kincaid_grade, extract_technical_terms


class ChunkExpander:
    """LLM-powered chunk expansion"""
    
    def __init__(
        self,
        model_name: str = EXPANSION_MODEL,
        temperature: float = EXPANSION_TEMPERATURE,
        max_tokens: int = EXPANSION_MAX_TOKENS,
    ):
        """Initialize with LLM configuration"""
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Use prompt manager
        from core.prompt_manager import prompt_manager
        self.prompt_template = prompt_manager.get_prompt("chunk_expansion")
    
    def expand_chunk(
        self,
        chunk: TranscriptChunk,
        context: Optional[Dict[str, Any]] = None
    ) -> ExpandedChunk:
        """Expand single chunk with LLM."""
        # Build prompt
        previous_context = ""
        topic = "educational content"
        
        if context:
            topic = context.get("topic", topic)
            prev_chunk = context.get("previous_chunk")
            if prev_chunk:
                previous_context = prev_chunk.text[:500]  # Limit context
        
        prompt = self.prompt_template.format(
            chunk_text=chunk.text,
            topic=topic,
            previous_context=previous_context or "None"
        )
        
        # Call LLM
        try:
            response = ollama.call_mixtral(
                prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            # Parse JSON response
            expansion_data = self._parse_expansion_response(response)
            
            # Extract claims
            claims = expansion_data.get("claims", [])
            
            # Calculate metadata
            difficulty_level = self.calculate_difficulty_level(
                expansion_data.get("expanded_explanation", chunk.text),
                list(expansion_data.get("definitions", {}).keys())
            )
            
            # Build a temporary ExpandedChunk-like structure for cognitive load calculation
            # Since we haven't created the ExpandedChunk yet, we'll calculate from expansion_data
            cognitive_load = self.calculate_cognitive_load_from_data(
                expansion_data,
                expansion_data.get("expanded_explanation", chunk.text)
            )
            
            # Create ExpandedChunk
            expanded = ExpandedChunk(
                chunk_id=f"exp_{uuid.uuid4().hex[:12]}",
                source_chunk_id=chunk.chunk_id,
                original_text=chunk.text,
                expanded_explanation=expansion_data.get("expanded_explanation", chunk.text),
                key_concepts=expansion_data.get("key_concepts", []),
                definitions=expansion_data.get("definitions", {}),
                examples=expansion_data.get("examples", []),
                prerequisites=expansion_data.get("prerequisites", []),
                claims=claims,
                difficulty_level=difficulty_level,
                cognitive_load=cognitive_load,
                llm_model=self.model_name,
                expansion_timestamp=datetime.now(),
                token_count=len(response.split()),  # Approximate
            )
            
            return expanded
            
        except Exception as e:
            print(f"Error expanding chunk {chunk.chunk_id}: {e}")
            # Return minimal expansion as fallback
            return ExpandedChunk(
                chunk_id=f"exp_{uuid.uuid4().hex[:12]}",
                source_chunk_id=chunk.chunk_id,
                original_text=chunk.text,
                expanded_explanation=chunk.text,  # Use original as fallback
                key_concepts=chunk.topic_keywords[:5],
                claims=[],
                difficulty_level="intermediate",
                cognitive_load=0.5,
                llm_model=self.model_name,
                expansion_timestamp=datetime.now(),
            )
    
    def expand_batch(
        self,
        chunks: List[TranscriptChunk],
        batch_size: int = LLM_BATCH_SIZE,
        preserve_context: bool = True
    ) -> List[ExpandedChunk]:
        """Expand multiple chunks efficiently."""
        expanded_chunks = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            for j, chunk in enumerate(batch):
                # Build context
                context = {}
                if preserve_context and i + j > 0:
                    prev_chunk = chunks[i + j - 1]
                    context["previous_chunk"] = prev_chunk
                
                # Expand chunk
                expanded = self.expand_chunk(chunk, context)
                expanded_chunks.append(expanded)
        
        return expanded_chunks
    
    def extract_claims_from_expansion(
        self,
        expanded_chunk: ExpandedChunk
    ) -> List[Dict[str, str]]:
        """Extract atomic knowledge claims from expansion."""
        return expanded_chunk.claims
    
    def calculate_difficulty_level(
        self,
        text: str,
        terminology: List[str]
    ) -> str:
        """Determine difficulty level."""
        # Calculate Flesch-Kincaid grade
        fk_grade = calculate_flesch_kincaid_grade(text)
        
        # Count technical terms
        term_density = len(terminology) / max(1, len(text.split()) / 100)
        
        # Determine difficulty
        if fk_grade < 10 and term_density < 0.1:
            return "beginner"
        elif fk_grade > 15 or term_density > 0.3:
            return "advanced"
        else:
            return "intermediate"
    
    def calculate_cognitive_load_from_data(
        self,
        expansion_data: Dict[str, Any],
        expanded_text: str
    ) -> float:
        """
        Estimate cognitive load from expansion data.
        
        This method is used during chunk expansion before ExpandedChunk is created.
        """
        load = 0.0
        
        # Concept count (more concepts = higher load)
        concept_count = len(expansion_data.get("key_concepts", []))
        load += min(0.4, concept_count * 0.05)
        
        # Definition density
        definitions = expansion_data.get("definitions", {})
        word_count = len(expanded_text.split())
        def_density = len(definitions) / max(1, word_count / 100)
        load += min(0.3, def_density * 0.5)
        
        # Prerequisite count
        prereq_count = len(expansion_data.get("prerequisites", []))
        load += min(0.2, prereq_count * 0.05)
        
        # Sentence complexity (approximate)
        sentences = expanded_text.split('.')
        if sentences:
            avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
            complexity = min(0.1, (avg_words - 15) / 100)
            load += complexity
        
        return min(1.0, load)
    
    def calculate_cognitive_load(
        self,
        expanded_chunk: ExpandedChunk
    ) -> float:
        """
        Estimate cognitive load from ExpandedChunk object.
        
        This method is used when you already have an ExpandedChunk object.
        """
        load = 0.0
        
        # Concept count (more concepts = higher load)
        concept_count = len(expanded_chunk.key_concepts)
        load += min(0.4, concept_count * 0.05)
        
        # Definition density
        def_density = len(expanded_chunk.definitions) / max(1, len(expanded_chunk.expanded_explanation.split()) / 100)
        load += min(0.3, def_density * 0.5)
        
        # Prerequisite count
        prereq_count = len(expanded_chunk.prerequisites)
        load += min(0.2, prereq_count * 0.05)
        
        # Sentence complexity (approximate)
        sentences = expanded_chunk.expanded_explanation.split('.')
        if sentences:
            avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
            complexity = min(0.1, (avg_words - 15) / 100)
            load += complexity
        
        return min(1.0, load)
    
    def _parse_expansion_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response."""
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to parse manually
        return self._parse_fallback(response)
    
    def _parse_fallback(self, text: str) -> Dict[str, Any]:
        """Fallback parser if JSON parsing fails."""
        return {
            "expanded_explanation": text[:1000],
            "key_concepts": [],
            "definitions": {},
            "examples": [],
            "prerequisites": [],
            "claims": [],
        }


def build_expansion_prompt(
    chunk_text: str,
    topic: str,
    previous_context: Optional[str] = None
) -> str:
    """Construct LLM prompt for chunk expansion."""
    # This is handled by the ChunkExpander class, but kept for API compatibility
    expander = ChunkExpander()
    return expander.prompt_template.format(
        chunk_text=chunk_text,
        topic=topic,
        previous_context=previous_context or "None"
    )

