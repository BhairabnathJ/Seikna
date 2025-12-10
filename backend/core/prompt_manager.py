"""
Centralized prompt file management with fallback templates.
"""
from pathlib import Path
from typing import Dict, Optional

class PromptManager:
    """Manages prompt file loading with consistent fallback behavior."""

    def __init__(self):
        from core.config import BACKEND_DIR
        self.prompts_dir = BACKEND_DIR / "prompts"
        self.loaded_prompts: Dict[str, str] = {}

        # Fallback templates
        self.fallback_templates = {
            "claim_extraction": self._get_claim_extraction_fallback(),
            "chunk_expansion": self._get_chunk_expansion_fallback(),
            "course_structure": self._get_course_structure_fallback(),
        }

    def get_prompt(self, prompt_name: str) -> str:
        """
        Load prompt by name with fallback.

        Args:
            prompt_name: Name of prompt file (without .txt extension)

        Returns:
            Prompt template string
        """
        # Return cached if already loaded
        if prompt_name in self.loaded_prompts:
            return self.loaded_prompts[prompt_name]

        # Try to load from file
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"

        if prompt_file.exists():
            try:
                with open(prompt_file, "r") as f:
                    template = f.read()

                # Validate not empty
                if not template.strip():
                    raise ValueError(f"Prompt file is empty: {prompt_file}")

                # Cache and return
                self.loaded_prompts[prompt_name] = template
                return template

            except Exception as e:
                print(f"Warning: Failed to load prompt file {prompt_file}: {e}")
                # Fall through to fallback

        # Use fallback template
        if prompt_name in self.fallback_templates:
            print(f"Using fallback template for: {prompt_name}")
            template = self.fallback_templates[prompt_name]
            self.loaded_prompts[prompt_name] = template
            return template

        # No fallback available
        raise FileNotFoundError(
            f"Prompt file not found and no fallback available: {prompt_name}.txt. "
            f"Expected at: {prompt_file}"
        )

    def _get_claim_extraction_fallback(self) -> str:
        """Fallback template for claim extraction."""
        return """You are a knowledge extraction assistant.

Given the following transcript chunk, extract ALL factual claims as structured triples.

TRANSCRIPT:
\"\"\"
{transcript_chunk}
\"\"\"

For each claim, output in this format:
("subject", "predicate", "object")

RULES:
1. Extract ONLY factual claims, not opinions or speculation
2. Keep claims atomic (one fact per triple)
3. Preserve technical terminology exactly

EXAMPLE:
Input: "Neural networks are inspired by biological neurons."
Output:
("Neural networks", "are inspired by", "biological neurons")

Now extract claims from the transcript above."""

    def _get_chunk_expansion_fallback(self) -> str:
        """Fallback template for chunk expansion."""
        return """Expand this educational content chunk with detailed explanations.

CHUNK:
{chunk_text}

TOPIC: {topic}

PREVIOUS CONTEXT: {previous_context}

Provide a JSON response with:
{{
  "expanded_explanation": "Detailed explanation (500-800 words)",
  "key_concepts": ["concept1", "concept2", ...],
  "definitions": {{"term1": "definition1", ...}},
  "examples": ["example1", "example2", ...],
  "prerequisites": ["prerequisite1", ...],
  "claims": [
    {{"subject": "X", "predicate": "is", "object": "Y", "confidence": 0.95}},
    ...
  ]
}}"""

    def _get_course_structure_fallback(self) -> str:
        """Fallback template for course structure generation."""
        return """You are an expert curriculum designer.

Create a structured learning course for: {topic}

VERIFIED CLAIMS:
{verified_claims}

Create a course outline with these sections:
1. Overview
2. Prerequisites
3. Fundamentals
4. Examples
5. Summary

Output as JSON with title, description, and sections array."""

# Global prompt manager instance
prompt_manager = PromptManager()

