"""
Course structure generator that creates structured learning paths from claims.
"""
import json
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from core.ollama_client import ollama
from core.database import db


class StructureGenerator:
    """Generates course structure from verified claims."""
    
    def __init__(self):
        # Use prompt manager
        from core.prompt_manager import prompt_manager
        self.prompt_template = prompt_manager.get_prompt("course_structure")
    
    def build_course(
        self,
        query: str,
        claims: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build a structured course from claims and sources.
        
        Args:
            query: Original user query
            claims: List of extracted claims
            sources: List of source information
        
        Returns:
            Course structure dictionary
        """
        if not claims:
            # Return minimal course if no claims
            return {
                "title": f"Introduction to {query}",
                "description": f"A course about {query}",
                "sections": [
                    {
                        "id": "section-1",
                        "title": "Overview",
                        "content": f"This course covers {query}. More content will be available once sources are processed.",
                        "sources": [],
                    }
                ],
                "glossary": [],
            }
        
        # Format claims for prompt
        claims_text = self._format_claims_for_prompt(claims, sources)
        
        # Build prompt
        prompt = self.prompt_template.format(
            topic=query,
            verified_claims=claims_text
        )
        
        # Call LLM
        try:
            response = ollama.call_mixtral(prompt, temperature=0.4, max_tokens=4096)
            
            # Parse JSON from response
            course_structure = self._parse_course_json(response)
            
            # Ensure all required fields
            if "title" not in course_structure:
                course_structure["title"] = f"Introduction to {query}"
            if "description" not in course_structure:
                course_structure["description"] = f"A comprehensive course about {query}"
            if "sections" not in course_structure:
                course_structure["sections"] = []
            if "glossary" not in course_structure:
                course_structure["glossary"] = []
            
            return course_structure
            
        except Exception as e:
            print(f"Error generating course structure: {e}")
            # Return fallback structure
            return self._create_fallback_structure(query, claims, sources)
    
    def _format_claims_for_prompt(
        self,
        claims: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> str:
        """Format claims as text for the prompt."""
        source_map = {s["source_id"]: s.get("title", s["url"]) for s in sources}
        
        claims_text = []
        for claim in claims[:100]:  # Limit to 100 claims to avoid token limits
            source_title = source_map.get(claim["source_id"], claim["source_id"])
            claim_str = (
                f"- ({claim['subject']}, {claim['predicate']}, {claim['object']}) "
                f"[Source: {source_title}]"
            )
            claims_text.append(claim_str)
        
        return "\n".join(claims_text)
    
    def _parse_course_json(self, llm_response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        import re
        
        # Try to find JSON block
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # If no valid JSON found, try to parse manually
        # This is a fallback - ideally the LLM should return valid JSON
        return self._parse_fallback_structure(llm_response)
    
    def _parse_fallback_structure(self, text: str) -> Dict[str, Any]:
        """Fallback parser if JSON parsing fails."""
        return {
            "title": "Course",
            "description": "Generated course",
            "sections": [
                {
                    "id": "section-1",
                    "title": "Overview",
                    "content": text[:1000],  # Use first 1000 chars
                    "sources": [],
                }
            ],
            "glossary": [],
        }
    
    def _create_fallback_structure(
        self,
        query: str,
        claims: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create a basic course structure when LLM fails."""
        # Group claims by subject
        subjects = {}
        for claim in claims:
            subject = claim["subject"]
            if subject not in subjects:
                subjects[subject] = []
            subjects[subject].append(claim)
        
        sections = []
        
        # Overview section
        sections.append({
            "id": "section-1",
            "title": "Overview",
            "content": f"This course introduces {query}. The following concepts are covered: {', '.join(list(subjects.keys())[:5])}.",
            "sources": [s["source_id"] for s in sources],
        })
        
        # Create sections for each major subject
        for i, (subject, subject_claims) in enumerate(list(subjects.items())[:5], start=2):
            content_parts = [f"{subject} {claim['predicate']} {claim['object']}." for claim in subject_claims[:3]]
            sections.append({
                "id": f"section-{i}",
                "title": subject,
                "content": " ".join(content_parts),
                "sources": list(set(claim["source_id"] for claim in subject_claims)),
            })
        
        return {
            "title": f"Introduction to {query}",
            "description": f"A course about {query}",
            "sections": sections,
            "glossary": [],
        }


# Global structure generator instance
structure_generator = StructureGenerator()

