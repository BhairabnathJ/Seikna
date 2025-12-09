"""
Source Discovery V2.0 - Complete redesign with tier-based system and strict filtering.

Implements the architecture from SYSTEM_NOTES.md Section 18.
"""
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import requests
from duckduckgo_search import DDGS

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = False

try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    WIKIPEDIA_AVAILABLE = False

from core.config import SourceDiscoveryConfigV2
from core.database import db
from services.ingestion.youtube_fetcher import YouTubeFetcher

logger = logging.getLogger(__name__)


class SourceTier(Enum):
    """Source quality tiers."""
    TIER1 = "tier1"  # Whitelisted educational domains
    YOUTUBE = "youtube"  # YouTube videos
    EDU = "edu"  # University domains
    WIKIPEDIA = "wikipedia"  # Wikipedia (fallback only)
    BLACKLISTED = "blacklisted"  # Rejected sources


@dataclass
class SearchResult:
    """Represents a search result from source discovery."""
    url: str
    title: str
    snippet: Optional[str] = None
    tier: Optional[SourceTier] = None


def normalize_query(query: str) -> str:
    """Normalize query for caching (lowercase, sorted keywords)."""
    keywords = sorted(query.lower().split())
    return ' '.join(keywords)


def add_context_keywords(query: str) -> str:
    """Add programming context to ambiguous queries."""
    query_lower = query.lower()
    
    # Check for ambiguous terms
    AMBIGUOUS_TERMS = {
        "decorators": "python programming decorators tutorial",
        "classes": "python classes OOP programming",
        "async": "python async await programming"
    }
    
    for term, replacement in AMBIGUOUS_TERMS.items():
        if term in query_lower:
            return replacement
    
    # Default: add programming context if not present
    if "python" not in query_lower and "programming" not in query_lower:
        return f"python programming {query}"
    
    return query


def validate_keyword_match(result: SearchResult, query_keywords: List[str]) -> bool:
    """ALL query keywords must appear in title OR URL."""
    title_lower = result.title.lower()
    url_lower = result.url.lower()
    
    for keyword in query_keywords:
        keyword_lower = keyword.lower()
        if keyword_lower not in title_lower and keyword_lower not in url_lower:
            return False  # REJECT if ANY keyword missing
    
    return True  # Accept only if ALL keywords present


def check_negative_keywords(result: SearchResult, query: str) -> bool:
    """Reject if negative keywords present (indicates wrong topic)."""
    query_lower = query.lower()
    config = SourceDiscoveryConfigV2()
    
    # Find matching negative keyword set
    for key, negative_terms in config.NEGATIVE_KEYWORDS.items():
        if key in query_lower:
            title_lower = result.title.lower()
            for negative_term in negative_terms:
                if negative_term in title_lower:
                    return False  # REJECT
    
    return True  # Accept


def pre_validate_source(result: SearchResult) -> bool:
    """Fast validation before downloading content."""
    config = SourceDiscoveryConfigV2()
    url_lower = result.url.lower()
    
    # Reject file types
    if any(url_lower.endswith(ext) for ext in config.REJECTED_EXTENSIONS):
        return False
    
    # Reject blacklisted domains
    parsed = urlparse(result.url)
    domain = parsed.netloc.replace('www.', '')
    if any(bl_domain in domain for bl_domain in config.BLACKLISTED_DOMAINS):
        return False
    
    # Check for paywall indicators in URL
    if any(indicator in url_lower for indicator in config.PAYWALL_INDICATORS):
        return False
    
    return True


def get_youtube_transcript_v2(video_id: str) -> Optional[str]:
    """Accept auto-generated captions, validate quality."""
    if not YOUTUBE_TRANSCRIPT_API_AVAILABLE:
        # Fallback to existing YouTubeFetcher
        return YouTubeFetcher.get_transcript(video_id)
    
    config = SourceDiscoveryConfigV2()
    
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Priority: Manual > Auto-generated English > Translated
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except (TranscriptsDisabled, NoTranscriptFound):
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except (TranscriptsDisabled, NoTranscriptFound):
                # Fallback: Try to translate any available transcript to English
                try:
                    available = list(transcript_list)
                    if available:
                        transcript = available[0].translate('en')
                    else:
                        return None
                except Exception:
                    return None
        
        # Fetch transcript segments
        segments = transcript.fetch()
        full_text = " ".join([seg['text'] for seg in segments])
        
        # Quality validation: Check for minimum word count
        word_count = len(full_text.split())
        
        if word_count < config.MIN_TRANSCRIPT_WORDS:
            return None  # Too short
        
        return full_text
    
    except Exception as e:
        logger.warning(f"Transcript fetch failed for {video_id}: {e}")
        return None


def search_tier1_domains(query: str) -> List[SearchResult]:
    """Search Tier 1 whitelisted domains."""
    config = SourceDiscoveryConfigV2()
    results = []
    
    if DDGS is None:
        logger.warning("DuckDuckGo search not available")
        return results
    
    try:
        with DDGS() as ddgs:
            for domain in config.TIER_1_DOMAINS:
                search_query = f"site:{domain} {query}"
                try:
                    for result in ddgs.text(search_query, max_results=3):
                        results.append(SearchResult(
                            url=result.get('href', ''),
                            title=result.get('title', ''),
                            snippet=result.get('body', ''),
                            tier=SourceTier.TIER1
                        ))
                except Exception as e:
                    logger.warning(f"Search failed for {domain}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Tier 1 search error: {e}")
    
    return results


def search_youtube(query: str) -> List[SearchResult]:
    """Search YouTube with transcript validation."""
    config = SourceDiscoveryConfigV2()
    results = []
    
    if DDGS is None:
        logger.warning("DuckDuckGo search not available")
        return results
    
    try:
        # Search YouTube with tutorial context
        youtube_query = f"site:youtube.com {query} tutorial"
        
        with DDGS() as ddgs:
            for result in ddgs.text(youtube_query, max_results=10):
                url = result.get('href', '')
                if not url or 'youtube.com' not in url and 'youtu.be' not in url:
                    continue
                
                # Extract video ID
                video_id = YouTubeFetcher._extract_video_id(url)
                if not video_id:
                    continue
                
                # Validate transcript exists and meets quality threshold
                transcript = get_youtube_transcript_v2(video_id)
                if not transcript:
                    logger.debug(f"Skipping {video_id}: no valid transcript")
                    continue
                
                # TODO: Validate duration (requires YouTube API or yt-dlp)
                # For now, accept if transcript exists
                
                results.append(SearchResult(
                    url=url,
                    title=result.get('title', ''),
                    snippet=result.get('body', ''),
                    tier=SourceTier.YOUTUBE
                ))
                
                # Limit results
                if len(results) >= 5:
                    break
    
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
    
    return results


def search_edu_domains(query: str) -> List[SearchResult]:
    """Search .edu domains, filter administrative pages."""
    config = SourceDiscoveryConfigV2()
    results = []
    
    if DDGS is None:
        logger.warning("DuckDuckGo search not available")
        return results
    
    try:
        search_query = f"site:.edu {query} tutorial lecture"
        
        with DDGS() as ddgs:
            for result in ddgs.text(search_query, max_results=10):
                url = result.get('href', '')
                title = result.get('title', '').lower()
                snippet = result.get('body', '').lower()
                
                # Filter out administrative pages
                if any(keyword in title or keyword in snippet for keyword in config.ADMIN_PAGE_KEYWORDS):
                    continue
                
                # Check for educational content keywords
                edu_keywords = ['tutorial', 'lecture', 'course', 'guide', 'lesson', 'notes']
                if not any(keyword in title or keyword in snippet for keyword in edu_keywords):
                    continue
                
                results.append(SearchResult(
                    url=url,
                    title=result.get('title', ''),
                    snippet=result.get('body', ''),
                    tier=SourceTier.EDU
                ))
                
                if len(results) >= 5:
                    break
    
    except Exception as e:
        logger.error(f".edu search error: {e}")
    
    return results


def search_wikipedia_strict(query: str) -> List[SearchResult]:
    """Wikipedia fallback with strict topic matching."""
    if not WIKIPEDIA_AVAILABLE:
        logger.warning("Wikipedia library not available")
        return []
    
    results = []
    query_keywords = set(query.lower().split())
    
    try:
        # Search Wikipedia
        search_results = wikipedia.search(query, results=5)
        
        for title in search_results:
            title_keywords = set(title.lower().split())
            
            # STRICT MATCH: ALL query keywords must appear in Wikipedia page title
            if not query_keywords.issubset(title_keywords):
                continue  # Reject if not exact match
            
            # Fetch page summary to validate relevance
            try:
                page = wikipedia.page(title, auto_suggest=False)
                
                # Check summary for query keywords
                summary_lower = page.summary.lower()
                keyword_count = sum(1 for kw in query_keywords if kw in summary_lower)
                
                # Require >= 80% of keywords in summary
                if keyword_count / len(query_keywords) < 0.8:
                    continue  # Reject if summary doesn't match
                
                results.append(SearchResult(
                    url=page.url,
                    title=page.title,
                    snippet=page.summary[:200],
                    tier=SourceTier.WIKIPEDIA
                ))
            
            except wikipedia.exceptions.DisambiguationError:
                continue  # Skip disambiguation pages
            except wikipedia.exceptions.PageError:
                continue  # Skip missing pages
    
    except Exception as e:
        logger.error(f"Wikipedia search failed: {e}")
    
    return results


def fetch_content_smart(url: str) -> Optional[str]:
    """Validate before downloading to avoid wasting time."""
    try:
        # Step 1: HEAD request to check file type (no download)
        response = requests.head(url, timeout=3, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '')
        
        # Reject non-HTML content
        if 'application/pdf' in content_type or 'application/zip' in content_type:
            return None
        
        # Step 2: Check file size (reject > 5MB)
        content_length = response.headers.get('Content-Length')
        if content_length:
            try:
                size = int(content_length)
                if size > 5_000_000:  # 5MB
                    return None
            except ValueError:
                pass
        
        # Step 3: Now download content
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        
        return None
    
    except Exception as e:
        logger.warning(f"Failed to fetch content from {url}: {e}")
        return None


def search_all_tiers_parallel(query: str) -> List[SearchResult]:
    """Search all tiers in parallel, merge results by priority."""
    config = SourceDiscoveryConfigV2()
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tier searches simultaneously
        future_tier1 = executor.submit(search_tier1_domains, query)
        future_youtube = executor.submit(search_youtube, query)
        future_edu = executor.submit(search_edu_domains, query)
        
        # Collect results with timeout
        tier1_results = []
        youtube_results = []
        edu_results = []
        
        try:
            tier1_results = future_tier1.result(timeout=config.SEARCH_TIMEOUT_PER_TIER)
        except FutureTimeoutError:
            logger.warning("Tier 1 search timed out")
        
        try:
            youtube_results = future_youtube.result(timeout=config.SEARCH_TIMEOUT_PER_TIER)
        except FutureTimeoutError:
            logger.warning("YouTube search timed out")
        
        try:
            edu_results = future_edu.result(timeout=config.SEARCH_TIMEOUT_PER_TIER)
        except FutureTimeoutError:
            logger.warning(".edu search timed out")
    
    # Merge by priority
    all_results = tier1_results + youtube_results + edu_results
    
    return all_results


def search_with_early_termination(query: str, target_count: int) -> List[SearchResult]:
    """Stop searching once target count reached."""
    results = []
    config = SourceDiscoveryConfigV2()
    
    # Tier 1: Whitelisted domains (highest quality)
    tier1_results = search_tier1_domains(query)
    results.extend(tier1_results)
    if len(results) >= target_count:
        return results[:target_count]  # STOP
    
    # Tier 2: YouTube
    youtube_results = search_youtube(query)
    results.extend(youtube_results)
    if len(results) >= target_count:
        return results[:target_count]  # STOP
    
    # Tier 3: .edu domains
    edu_results = search_edu_domains(query)
    results.extend(edu_results)
    if len(results) >= target_count:
        return results[:target_count]  # STOP
    
    # Tier 4: Wikipedia (fallback only)
    if len(results) < config.MIN_SOURCES_BEFORE_WIKIPEDIA:
        wikipedia_results = search_wikipedia_strict(query)
        results.extend(wikipedia_results)
    
    return results[:target_count]


def _get_cached_results(query_normalized: str) -> Optional[List[SearchResult]]:
    """Get cached discovery results if still valid (7 days)."""
    try:
        # Get all cached results for this query
        all_results = db.execute(
            """
            SELECT result_url, result_title, result_snippet, tier
            FROM source_discovery_v2_cache
            WHERE query_normalized = ? 
            AND datetime(fetched_at, '+7 days') > datetime('now')
            ORDER BY fetched_at DESC
            LIMIT 20
            """,
            (query_normalized,)
        )
        
        if all_results:
            search_results = []
            for row in all_results:
                tier = SourceTier(row["tier"]) if row["tier"] else None
                search_results.append(SearchResult(
                    url=row["result_url"],
                    title=row["result_title"] or "",
                    snippet=row["result_snippet"],
                    tier=tier
                ))
            return search_results
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    
    return None


def _cache_results(query_normalized: str, results: List[SearchResult]) -> None:
    """Cache discovery results."""
    try:
        for result in results:
            tier_str = result.tier.value if result.tier else None
            db.execute_write(
                """
                INSERT OR REPLACE INTO source_discovery_v2_cache
                (query_normalized, tier, result_url, result_title, result_snippet, fetched_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    query_normalized,
                    tier_str,
                    result.url,
                    result.title,
                    result.snippet,
                )
            )
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


def discover_sources_v2(query: str, target_count: Optional[int] = None) -> List[SearchResult]:
    """
    Main entry point for Source Discovery V2.0.
    
    Args:
        query: Search query
        target_count: Target number of sources (defaults to config)
    
    Returns:
        List of SearchResult objects
    """
    config = SourceDiscoveryConfigV2()
    
    if target_count is None:
        target_count = config.TARGET_SOURCE_COUNT
    
    # Step 1: Normalize query and check cache
    query_normalized = normalize_query(query)
    cached_results = _get_cached_results(query_normalized)
    if cached_results:
        logger.info(f"Returning {len(cached_results)} cached results for query: {query}")
        return cached_results[:target_count]
    
    # Step 2: Add context keywords if needed
    augmented_query = add_context_keywords(query)
    query_keywords = augmented_query.split()
    
    # Step 3: Execute tier searches (parallel + early termination)
    all_candidates = search_with_early_termination(augmented_query, target_count * 2)
    
    # Step 4: Apply filtering pipeline
    filtered_results = []
    for candidate in all_candidates:
        # Stage 3: Keyword match validation
        if not validate_keyword_match(candidate, query_keywords):
            continue
        
        # Stage 4: Negative keyword filtering
        if not check_negative_keywords(candidate, query):
            continue
        
        # Stage 5: Pre-validation
        if not pre_validate_source(candidate):
            continue
        
        filtered_results.append(candidate)
        
        # Early termination if we have enough
        if len(filtered_results) >= target_count:
            break
    
    # Step 5: Wikipedia fallback if needed
    if len(filtered_results) < config.MIN_SOURCES_BEFORE_WIKIPEDIA:
        wikipedia_results = search_wikipedia_strict(augmented_query)
        for wiki_result in wikipedia_results:
            if validate_keyword_match(wiki_result, query_keywords):
                if check_negative_keywords(wiki_result, query):
                    filtered_results.append(wiki_result)
                    if len(filtered_results) >= target_count:
                        break
    
    # Step 6: Cache results
    if filtered_results:
        _cache_results(query_normalized, filtered_results)
    
    logger.info(f"Discovered {len(filtered_results)} sources for query: {query}")
    return filtered_results[:target_count]
