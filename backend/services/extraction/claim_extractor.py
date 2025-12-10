"""
Claim extractor for extracting knowledge claims from transcripts.
"""
import uuid
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from core.ollama_client import ollama
from core.database import db


class ClaimExtractor:
    """Extracts atomic knowledge claims from transcripts."""
    
    def __init__(self):
        # Use prompt manager instead of direct file loading
        from core.prompt_manager import prompt_manager
        self.prompt_template = prompt_manager.get_prompt("claim_extraction")
    
    def extract_claims(
        self,
        transcript: str,
        source_id: str,
        chunk_size: int = 2000,
    ) -> List[Dict[str, Any]]:
        """
        Extract claims from a transcript.
        
        Args:
            transcript: Full transcript text
            source_id: Source identifier
            chunk_size: Size of chunks to process
        
        Returns:
            List of claim dictionaries
        """
        if not transcript or not transcript.strip():
            return []
        
        # Split transcript into chunks
        chunks = self._chunk_transcript(transcript, chunk_size)
        
        all_claims = []
        
        for i, chunk in enumerate(chunks):
            try:
                # Build prompt
                prompt = self.prompt_template.format(transcript_chunk=chunk)
                
                # Call LLM
                response = ollama.call_mixtral(prompt, temperature=0.3)
                
                # Parse claims from response
                claims = self._parse_claims(response, source_id)
                all_claims.extend(claims)
                
            except Exception as e:
                print(f"Error extracting claims from chunk {i}: {e}")
                continue
        
        # Store claims in database
        for claim in all_claims:
            self._store_claim(claim)
        
        return all_claims
    
    def _chunk_transcript(self, transcript: str, chunk_size: int) -> List[str]:
        """Split transcript into semantic chunks."""
        # Simple chunking by sentences first
        sentences = re.split(r'[.!?]+\s+', transcript)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _parse_claims(
        self,
        llm_response: str,
        source_id: str,
    ) -> List[Dict[str, Any]]:
        """Parse claims from LLM response."""
        claims = []
        
        # Pattern to match (subject, predicate, object) format
        pattern = r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)'
        
        matches = re.findall(pattern, llm_response)
        
        for subject, predicate, object_text in matches:
            claim_id = f"claim_{uuid.uuid4().hex[:12]}"
            
            claim = {
                "claim_id": claim_id,
                "source_id": source_id,
                "claim_type": "transcript",
                "subject": subject.strip(),
                "predicate": predicate.strip(),
                "object": object_text.strip(),
                "timestamp_ms": None,  # TODO: Extract timestamp if available
                "confidence": 1.0,
            }
            
            claims.append(claim)
        
        return claims
    
    def _store_claim(self, claim: Dict[str, Any]) -> None:
        """Store a claim in the database."""
        db.execute_write(
            """
            INSERT OR IGNORE INTO claims
            (claim_id, source_id, claim_type, subject, predicate, object, timestamp_ms, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim["claim_id"],
                claim["source_id"],
                claim["claim_type"],
                claim["subject"],
                claim["predicate"],
                claim["object"],
                claim["timestamp_ms"],
                claim["confidence"],
            )
        )


# Global claim extractor instance
claim_extractor = ClaimExtractor()

