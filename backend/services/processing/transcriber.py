"""
Transcript normalization and segmentation service.
"""
import re
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from models.transcript_models import RawTranscript, TranscriptSegment
from services.processing.utils import clean_text, detect_language


def normalize_youtube_transcript(
    source_id: str,
    url: str,
    title: str,
    raw_transcript: str,
    metadata: Dict[str, Any]
) -> RawTranscript:
    """
    Convert YouTube transcript to RawTranscript.
    
    Processing:
        1. Parse VTT/SRT format (or plain text)
        2. Extract timestamps and text
        3. Clean text
        4. Create TranscriptSegment objects
        5. Validate completeness
    """
    segments = []
    
    # Try to parse as WebVTT format
    if '-->' in raw_transcript or 'WEBVTT' in raw_transcript:
        segments = _parse_vtt_format(raw_transcript)
    # Try to parse as SRT format
    elif re.match(r'^\d+\s*$', raw_transcript.split('\n')[0]):
        segments = _parse_srt_format(raw_transcript)
    else:
        # Plain text - create single segment
        clean_content = clean_text(raw_transcript)
        if clean_content:
            segment = TranscriptSegment(
                text=clean_content,
                start_time_ms=None,
                end_time_ms=None,
                segment_id=f"seg_{uuid.uuid4().hex[:8]}",
                metadata={}
            )
            segments.append(segment)
    
    # Calculate total duration from segments
    total_duration_ms = None
    if segments and segments[-1].end_time_ms:
        total_duration_ms = segments[-1].end_time_ms
    
    # Detect language
    full_text = " ".join(seg.text for seg in segments)
    language, _ = detect_language(full_text)
    
    return RawTranscript(
        source_id=source_id,
        source_type="youtube",
        title=title,
        url=url,
        language=language,
        total_duration_ms=total_duration_ms,
        segments=segments,
        metadata=metadata,
        fetched_at=datetime.now()
    )


def normalize_article_content(
    source_id: str,
    url: str,
    title: str,
    raw_html: str,
    metadata: Dict[str, Any]
) -> RawTranscript:
    """
    Convert article HTML to RawTranscript.
    
    Processing:
        1. Extract main content (BeautifulSoup)
        2. Remove ads, navigation, footers
        3. Split into paragraphs
        4. Create TranscriptSegment per paragraph
        5. Validate readability
    """
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # Remove unwanted elements
    for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
        element.decompose()
    
    # Try to find article content
    article_selectors = [
        'article',
        '[role="article"]',
        '.article-content',
        '.post-content',
        '.entry-content',
        'main',
        '.content',
    ]
    
    content_elem = None
    for selector in article_selectors:
        content_elem = soup.select_one(selector)
        if content_elem:
            break
    
    if not content_elem:
        content_elem = soup.find('body') or soup
    
    # Extract paragraphs
    paragraphs = content_elem.find_all(['p', 'div', 'section'])
    segments = []
    
    for para in paragraphs:
        text = para.get_text(strip=True)
        clean_text_content = clean_text(text)
        
        if clean_text_content and len(clean_text_content.split()) > 5:  # Min 5 words
            segment = TranscriptSegment(
                text=clean_text_content,
                start_time_ms=None,
                end_time_ms=None,
                segment_id=f"seg_{uuid.uuid4().hex[:8]}",
                metadata={'paragraph_index': len(segments)}
            )
            segments.append(segment)
    
    # If no paragraphs found, use full text
    if not segments:
        full_text = content_elem.get_text()
        clean_text_content = clean_text(full_text)
        if clean_text_content:
            segment = TranscriptSegment(
                text=clean_text_content,
                start_time_ms=None,
                end_time_ms=None,
                segment_id=f"seg_{uuid.uuid4().hex[:8]}",
                metadata={}
            )
            segments.append(segment)
    
    # Detect language
    full_text = " ".join(seg.text for seg in segments)
    language, _ = detect_language(full_text)
    
    return RawTranscript(
        source_id=source_id,
        source_type="article",
        title=title,
        url=url,
        language=language,
        total_duration_ms=None,
        segments=segments,
        metadata=metadata,
        fetched_at=datetime.now()
    )


def validate_transcript(transcript: RawTranscript) -> Dict[str, Any]:
    """
    Validate transcript quality.
    
    Returns:
        {
            "is_valid": bool,
            "word_count": int,
            "language_confidence": float,
            "issues": List[str],
            "quality_score": float  # 0.0-1.0
        }
    """
    issues = []
    quality_score = 1.0
    
    # Check word count
    word_count = transcript.word_count
    if word_count < 200:
        issues.append(f"Low word count: {word_count} (minimum: 200)")
        quality_score *= 0.5
    
    # Check language
    language, confidence = detect_language(transcript.full_text)
    if language != 'en':
        issues.append(f"Non-English content detected: {language}")
        quality_score *= 0.7
    
    if confidence < 0.5:
        issues.append(f"Low language detection confidence: {confidence:.2f}")
        quality_score *= 0.8
    
    # Check for excessive repetition
    words = transcript.full_text.lower().split()
    if len(words) > 0:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.3:
            issues.append("High repetition detected (low unique word ratio)")
            quality_score *= 0.6
    
    # Check segment count
    if len(transcript.segments) == 0:
        issues.append("No segments found")
        quality_score = 0.0
    
    return {
        "is_valid": quality_score >= 0.5 and len(transcript.segments) > 0,
        "word_count": word_count,
        "language_confidence": confidence,
        "issues": issues,
        "quality_score": max(0.0, quality_score)
    }


def _parse_vtt_format(vtt_content: str) -> List[TranscriptSegment]:
    """Parse WebVTT format transcript."""
    segments = []
    lines = vtt_content.split('\n')
    
    current_text = ""
    start_ms = None
    end_ms = None
    
    for line in lines:
        line = line.strip()
        
        # Skip headers and empty lines
        if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
            continue
        
        # Check for timestamp line (HH:MM:SS.mmm --> HH:MM:SS.mmm)
        timestamp_match = re.match(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})', line)
        if timestamp_match:
            # Save previous segment if exists
            if current_text and start_ms is not None:
                clean_seg_text = clean_text(current_text)
                if clean_seg_text:
                    segments.append(TranscriptSegment(
                        text=clean_seg_text,
                        start_time_ms=start_ms,
                        end_time_ms=end_ms,
                        segment_id=f"seg_{uuid.uuid4().hex[:8]}",
                        metadata={}
                    ))
            
            # Parse new timestamps
            h1, m1, s1, ms1, h2, m2, s2, ms2 = timestamp_match.groups()
            start_ms = int(h1) * 3600000 + int(m1) * 60000 + int(s1) * 1000 + int(ms1)
            end_ms = int(h2) * 3600000 + int(m2) * 60000 + int(s2) * 1000 + int(ms2)
            current_text = ""
            continue
        
        # Skip cue identifiers (numbers)
        if line.isdigit():
            continue
        
        # Text content
        if start_ms is not None:
            current_text += " " + line
    
    # Add final segment
    if current_text and start_ms is not None:
        clean_seg_text = clean_text(current_text)
        if clean_seg_text:
            segments.append(TranscriptSegment(
                text=clean_seg_text,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                segment_id=f"seg_{uuid.uuid4().hex[:8]}",
                metadata={}
            ))
    
    return segments


def _parse_srt_format(srt_content: str) -> List[TranscriptSegment]:
    """Parse SRT format transcript."""
    segments = []
    blocks = re.split(r'\n\s*\n', srt_content)
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        # First line is number, second is timestamp
        timestamp_line = lines[1] if len(lines) > 1 else ""
        text_lines = lines[2:]
        
        # Parse timestamp (HH:MM:SS,mmm --> HH:MM:SS,mmm)
        timestamp_match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', timestamp_line)
        if timestamp_match:
            h1, m1, s1, ms1, h2, m2, s2, ms2 = timestamp_match.groups()
            start_ms = int(h1) * 3600000 + int(m1) * 60000 + int(s1) * 1000 + int(ms1)
            end_ms = int(h2) * 3600000 + int(m2) * 60000 + int(s2) * 1000 + int(ms2)
            
            text = " ".join(text_lines)
            clean_seg_text = clean_text(text)
            
            if clean_seg_text:
                segments.append(TranscriptSegment(
                    text=clean_seg_text,
                    start_time_ms=start_ms,
                    end_time_ms=end_ms,
                    segment_id=f"seg_{uuid.uuid4().hex[:8]}",
                    metadata={}
                ))
    
    return segments


def merge_transcripts(transcripts: List[RawTranscript]) -> RawTranscript:
    """
    Merge multiple transcripts into one (for multi-part videos).
    """
    if not transcripts:
        raise ValueError("Cannot merge empty transcript list")
    
    if len(transcripts) == 1:
        return transcripts[0]
    
    # Use first transcript as base
    base = transcripts[0]
    all_segments = list(base.segments)
    current_time = base.total_duration_ms or 0
    
    # Merge remaining transcripts
    for transcript in transcripts[1:]:
        time_offset = current_time
        
        for segment in transcript.segments:
            new_segment = TranscriptSegment(
                text=segment.text,
                start_time_ms=(segment.start_time_ms + time_offset) if segment.start_time_ms else None,
                end_time_ms=(segment.end_time_ms + time_offset) if segment.end_time_ms else None,
                segment_id=f"seg_{uuid.uuid4().hex[:8]}",
                metadata=segment.metadata
            )
            all_segments.append(new_segment)
        
        if transcript.total_duration_ms:
            current_time += transcript.total_duration_ms
    
    # Update metadata
    merged_metadata = base.metadata.copy()
    merged_metadata['merged_from'] = [t.source_id for t in transcripts]
    
    return RawTranscript(
        source_id=base.source_id,
        source_type=base.source_type,
        title=base.title,
        url=base.url,
        language=base.language,
        total_duration_ms=current_time,
        segments=all_segments,
        metadata=merged_metadata,
        fetched_at=base.fetched_at
    )

