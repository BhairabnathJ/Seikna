"""
Shared utilities for processing pipeline.
"""
import re
import hashlib
from typing import List, Tuple, Optional
import numpy as np
from core.ollama_client import ollama
from core.config import EMBEDDING_BATCH_SIZE


def calculate_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec1) == 0 or len(vec2) == 0:
        return 0.0
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


def embed_text(text: str, model: str = "nomic-embed-text") -> np.ndarray:
    """Get embedding vector for text via Ollama."""
    try:
        embedding = ollama.generate_embedding(text)
        return np.array(embedding, dtype=np.float32)
    except Exception as e:
        print(f"Error generating embedding: {e}")
        # Return zero vector as fallback
        return np.zeros(768, dtype=np.float32)


def embed_batch(
    texts: List[str],
    model: str = "nomic-embed-text",
    batch_size: int = EMBEDDING_BATCH_SIZE
) -> List[np.ndarray]:
    """Batch embedding for efficiency."""
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = [embed_text(text, model) for text in batch]
        embeddings.extend(batch_embeddings)
    return embeddings


def clean_text(text: str) -> str:
    """
    Normalize text.
    
    Operations:
        - Remove extra whitespace
        - Fix encoding issues
        - Normalize punctuation
        - Remove speaker labels
    """
    # Remove speaker labels (e.g., "Speaker 1:", "[MUSIC]", etc.)
    text = re.sub(r'^[\w\s]+:\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[.*?\]', '', text)  # Remove [MUSIC], [LAUGHTER], etc.
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Fix common encoding issues
    text = text.replace('\u2019', "'")  # Right single quotation mark
    text = text.replace('\u201c', '"')  # Left double quotation mark
    text = text.replace('\u201d', '"')  # Right double quotation mark
    text = text.replace('\u2013', '-')  # En dash
    text = text.replace('\u2014', '--')  # Em dash
    
    return text


def format_timestamp(milliseconds: int) -> str:
    """Convert milliseconds to MM:SS format."""
    total_seconds = milliseconds // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def calculate_reading_time(text: str, wpm: int = 200) -> int:
    """Estimate reading time in minutes."""
    word_count = len(text.split())
    minutes = max(1, word_count // wpm)
    return minutes


def extract_markdown_headings(markdown: str) -> List[Dict[str, str]]:
    """Parse markdown headings for navigation."""
    headings = []
    lines = markdown.split('\n')
    for line in lines:
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            title = line.lstrip('#').strip()
            headings.append({'level': level, 'title': title})
    return headings


def merge_overlapping_chunks(
    chunks: List[str],
    overlap_size: int
) -> str:
    """Merge chunks while removing overlap (simple word-based)."""
    if not chunks:
        return ""
    
    merged = chunks[0]
    overlap_words = overlap_size // 10  # Rough estimate: 10 chars per word
    
    for chunk in chunks[1:]:
        # Simple overlap removal - find common ending/beginning
        merged_words = merged.split()
        chunk_words = chunk.split()
        
        # Check for overlap
        overlap_found = False
        for i in range(min(overlap_words, len(merged_words)), 0, -1):
            if merged_words[-i:] == chunk_words[:i]:
                # Found overlap, skip it
                merged += " " + " ".join(chunk_words[i:])
                overlap_found = True
                break
        
        if not overlap_found:
            merged += " " + chunk
    
    return merged


def detect_language(text: str) -> Tuple[str, float]:
    """
    Simple language detection (basic implementation).
    
    Returns:
        (language_code, confidence)
    """
    # Simple heuristic: check for common English words
    english_words = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'it'}
    words = set(text.lower().split())
    english_matches = len(words & english_words)
    
    if len(words) == 0:
        return ('en', 0.5)
    
    confidence = min(1.0, english_matches / max(1, len(words) * 0.1))
    return ('en', confidence)


def calculate_flesch_kincaid_grade(text: str) -> float:
    """
    Calculate readability grade level (simplified).
    
    Flesch-Kincaid formula (simplified):
    FK = 206.835 - (1.015 * ASL) - (84.6 * ASW)
    Where ASL = average sentence length, ASW = average syllables per word
    """
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return 10.0
    
    words = text.split()
    total_syllables = sum(_count_syllables(word) for word in words)
    
    if len(words) == 0:
        return 10.0
    
    avg_sentence_length = len(words) / len(sentences)
    avg_syllables_per_word = total_syllables / len(words)
    
    # Simplified FK formula
    fk_grade = (0.39 * avg_sentence_length) + (11.8 * avg_syllables_per_word) - 15.59
    
    return max(0, min(20, fk_grade))


def _count_syllables(word: str) -> int:
    """Count syllables in a word (simplified heuristic)."""
    word = word.lower().strip(".,!?;:")
    if not word:
        return 1
    
    vowels = 'aeiouy'
    count = 0
    prev_was_vowel = False
    
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    
    # Handle silent e
    if word.endswith('e'):
        count -= 1
    
    return max(1, count)


def extract_technical_terms(
    text: str,
    threshold: float = 0.7
) -> List[str]:
    """
    Identify technical/domain-specific terms (simplified).
    
    Method:
        - Extract noun phrases
        - Check against common English words
        - Return capitalized/multi-word terms
    """
    # Common English words to filter out
    common_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
        'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'this', 'that', 'these', 'those'
    }
    
    words = text.split()
    technical_terms = []
    
    # Extract capitalized terms and multi-word phrases
    current_phrase = []
    for word in words:
        clean_word = word.strip('.,!?;:()[]{}"\'')
        if not clean_word:
            continue
        
        # Check if capitalized (likely proper noun or technical term)
        if clean_word[0].isupper() or clean_word.isupper():
            current_phrase.append(clean_word)
        else:
            if len(current_phrase) > 0:
                phrase = ' '.join(current_phrase)
                if phrase.lower() not in common_words:
                    technical_terms.append(phrase)
                current_phrase = []
            
            # Single word technical term (not common word, longer than 4 chars)
            if len(clean_word) > 4 and clean_word.lower() not in common_words:
                technical_terms.append(clean_word)
    
    # Add final phrase
    if len(current_phrase) > 0:
        phrase = ' '.join(current_phrase)
        if phrase.lower() not in common_words:
            technical_terms.append(phrase)
    
    # Remove duplicates and return
    return list(set(technical_terms))[:20]  # Limit to top 20

