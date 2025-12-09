"""
Source discovery service for automatically finding YouTube videos and web articles.
"""
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass

import requests
from googleapiclient.discovery import build
try:
    from duckduckgo_search import DDGS
except ImportError:
    # Fallback if library name is different
    try:
        from duckduckgo_search import DDGS as DDGS_alt
        DDGS = DDGS_alt
    except ImportError:
        DDGS = None

from core.config import (
    YOUTUBE_API_KEY,
    SERPAPI_KEY,
    DEFAULT_NUM_YOUTUBE,
    DEFAULT_NUM_ARTICLES,
    YOUTUBE_MIN_DURATION_SEC,
    YOUTUBE_MAX_DURATION_SEC,
    ARTICLE_MIN_WORDS,
    CACHE_TTL_HOURS,
    YOUTUBE_VIEW_WEIGHT,
    YOUTUBE_LIKE_WEIGHT,
    YOUTUBE_RELEVANCE_WEIGHT,
    YOUTUBE_RECENCY_WEIGHT,
    ARTICLE_DOMAIN_WEIGHT,
    ARTICLE_RELEVANCE_WEIGHT,
    ARTICLE_RECENCY_WEIGHT,
    USE_SOURCE_DISCOVERY_V2,
)
from core.database import db
from services.ingestion.cache_manager import cache_manager

# Import V2 if flag is enabled
if USE_SOURCE_DISCOVERY_V2:
    from services.ingestion.source_discoverer_v2 import discover_sources_v2, SearchResult as V2SearchResult


@dataclass
class SourceDiscoveryResult:
    """Result of source discovery operation."""
    youtube_urls: List[str]
    article_urls: List[str]
    metadata: Dict[str, Any]


class SourceDiscoverer:
    """Discovers relevant YouTube videos and web articles for a given query."""
    
    # High-authority domains for articles
    HIGH_AUTHORITY_DOMAINS = {
        'edu': 1.0,
        'ac.uk': 1.0,
        'docs.python.org': 0.9,
        'developer.mozilla.org': 0.9,
        'medium.com': 0.7,
        'dev.to': 0.7,
        'stackoverflow.com': 0.6,
    }
    
    def __init__(self):
        self.youtube_service = None
        if YOUTUBE_API_KEY:
            try:
                self.youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            except Exception as e:
                print(f"Warning: Failed to initialize YouTube API: {e}")
    
    def discover_sources(
        self,
        query: str,
        num_youtube: int = DEFAULT_NUM_YOUTUBE,
        num_articles: int = DEFAULT_NUM_ARTICLES,
        difficulty: Optional[str] = None,
    ) -> SourceDiscoveryResult:
        """
        Discover sources for a given query.
        
        Public entrypoint used by the rest of the codebase.
        Delegates to V1 or V2 based on config flag.
        
        Args:
            query: Search query
            num_youtube: Number of YouTube videos to find
            num_articles: Number of articles to find
            difficulty: Optional difficulty level (beginner, intermediate, advanced)
        
        Returns:
            SourceDiscoveryResult with URLs and metadata
        """
        # Delegate to V2 if enabled
        if USE_SOURCE_DISCOVERY_V2:
            return self._discover_sources_v2_wrapper(query, num_youtube, num_articles, difficulty)
        else:
            return self._discover_sources_v1(query, num_youtube, num_articles, difficulty)
    
    def _discover_sources_v2_wrapper(
        self,
        query: str,
        num_youtube: int,
        num_articles: int,
        difficulty: Optional[str] = None,
    ) -> SourceDiscoveryResult:
        """Wrapper to convert V2 SearchResult to V1 SourceDiscoveryResult format."""
        # Calculate target count
        target_count = num_youtube + num_articles
        
        # Call V2 (synchronous)
        v2_results = discover_sources_v2(query, target_count)
        
        # Convert V2 SearchResult to V1 format
        youtube_urls = []
        article_urls = []
        
        for result in v2_results:
            if result.tier and result.tier.value == "youtube":
                youtube_urls.append(result.url)
            else:
                article_urls.append(result.url)
        
        # Limit to requested counts
        youtube_urls = youtube_urls[:num_youtube]
        article_urls = article_urls[:num_articles]
        
        metadata = {
            'youtube_discovered': len(youtube_urls),
            'articles_discovered': len(article_urls),
            'errors': [],
            'version': 'v2',
        }
        
        return SourceDiscoveryResult(
            youtube_urls=youtube_urls,
            article_urls=article_urls,
            metadata=metadata,
        )
    
    def _discover_sources_v1(
        self,
        query: str,
        num_youtube: int = DEFAULT_NUM_YOUTUBE,
        num_articles: int = DEFAULT_NUM_ARTICLES,
        difficulty: Optional[str] = None,
    ) -> SourceDiscoveryResult:
        """
        Original V1 discovery logic (kept for backward compatibility).
        """
        # Check cache first
        cache_key = self._generate_cache_key(query, difficulty, num_youtube, num_articles)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        youtube_urls = []
        article_urls = []
        metadata = {
            'youtube_discovered': 0,
            'articles_discovered': 0,
            'errors': [],
        }
        
        # Search YouTube
        try:
            if self.youtube_service:
                youtube_urls = self._search_youtube(query, num_youtube, difficulty)
                metadata['youtube_discovered'] = len(youtube_urls)
            else:
                metadata['errors'].append('YouTube API key not configured')
        except Exception as e:
            metadata['errors'].append(f'YouTube search failed: {str(e)}')
            print(f"YouTube search error: {e}")
        
        # Search web articles
        try:
            article_urls = self._search_web_articles(query, num_articles)
            metadata['articles_discovered'] = len(article_urls)
        except Exception as e:
            metadata['errors'].append(f'Article search failed: {str(e)}')
            print(f"Article search error: {e}")
        
        result = SourceDiscoveryResult(
            youtube_urls=youtube_urls,
            article_urls=article_urls,
            metadata=metadata,
        )
        
        # Cache the result
        self._cache_result(cache_key, query, result)
        
        return result
    
    def _search_youtube(
        self,
        query: str,
        num_results: int,
        difficulty: Optional[str] = None,
    ) -> List[str]:
        """Search YouTube for videos with transcripts."""
        if not self.youtube_service:
            return []
        
        # Augment query based on difficulty
        augmented_query = self._augment_query(query, difficulty)
        
        # Build search query
        search_query = f"{augmented_query} tutorial explained"
        
        # Search parameters
        search_params = {
            'part': 'snippet',
            'q': search_query,
            'type': 'video',
            'videoCaption': 'closedCaption',  # Must have captions
            'relevanceLanguage': 'en',
            'maxResults': min(25, num_results * 3),  # Fetch more for ranking
            'order': 'relevance',
        }
        
        # Execute search
        search_response = self.youtube_service.search().list(**search_params).execute()
        
        # Get video details for ranking
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        if not video_ids:
            return []
        
        # Get video details (duration, statistics)
        videos_response = self.youtube_service.videos().list(
            part='contentDetails,statistics,snippet',
            id=','.join(video_ids)
        ).execute()
        
        # Process and rank videos
        video_candidates = []
        for video in videos_response.get('items', []):
            video_data = self._parse_youtube_video(video)
            if video_data and self._is_valid_youtube_video(video_data):
                video_candidates.append(video_data)
        
        # Rank and select diverse videos
        ranked_videos = self._rank_youtube_videos(video_candidates)
        selected_videos = self._diverse_sample(
            ranked_videos,
            num_results,
            key='channel_id'
        )
        
        # Convert to URLs
        urls = [f"https://www.youtube.com/watch?v={v['video_id']}" for v in selected_videos]
        
        return urls
    
    def _search_web_articles(
        self,
        query: str,
        num_results: int,
    ) -> List[str]:
        """Search web for articles using DuckDuckGo."""
        if DDGS is None:
            print("Warning: DuckDuckGo search library not available. Install with: pip install duckduckgo-search")
            return []
        
        try:
            # Use DuckDuckGo for free web search
            search_query = f"{query} tutorial guide"
            
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    search_query,
                    max_results=min(20, num_results * 3),  # Fetch more for ranking
                    region='us-en',
                ))
            
            # Process and rank articles
            article_candidates = []
            for result in results:
                article_data = self._parse_article_result(result)
                if article_data and self._is_valid_article(article_data):
                    article_candidates.append(article_data)
            
            # Rank and select diverse articles
            ranked_articles = self._rank_articles(article_candidates)
            selected_articles = self._diverse_sample(
                ranked_articles,
                num_results,
                key='domain'
            )
            
            return [article['url'] for article in selected_articles]
            
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
            return []
    
    def _augment_query(self, query: str, difficulty: Optional[str] = None) -> str:
        """Augment search query based on difficulty."""
        if difficulty == 'beginner':
            return f"{query} tutorial for beginners"
        elif difficulty == 'advanced':
            return f"{query} deep dive advanced"
        else:
            return query
    
    def _parse_youtube_video(self, video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse YouTube API video response."""
        try:
            video_id = video['id']
            snippet = video['snippet']
            content_details = video['contentDetails']
            statistics = video.get('statistics', {})
            
            # Parse duration (ISO 8601 format)
            duration_str = content_details.get('duration', '')
            duration_sec = self._parse_duration(duration_str)
            
            # Get statistics
            view_count = int(statistics.get('viewCount', 0))
            like_count = int(statistics.get('likeCount', 0))
            comment_count = int(statistics.get('commentCount', 0))
            
            # Calculate like ratio (avoid division by zero)
            like_ratio = like_count / max(view_count, 1)
            
            # Parse publish date
            publish_date = snippet.get('publishedAt', '')
            recency_score = self._calculate_recency_score(publish_date)
            
            return {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'channel_id': snippet.get('channelId', ''),
                'channel_title': snippet.get('channelTitle', ''),
                'description': snippet.get('description', ''),
                'duration_sec': duration_sec,
                'view_count': view_count,
                'like_count': like_count,
                'like_ratio': like_ratio,
                'comment_count': comment_count,
                'publish_date': publish_date,
                'recency_score': recency_score,
                'url': f"https://www.youtube.com/watch?v={video_id}",
            }
        except Exception as e:
            print(f"Error parsing YouTube video: {e}")
            return None
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration to seconds."""
        # Pattern: PT4M13S (4 minutes 13 seconds)
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def _calculate_recency_score(self, publish_date: str) -> float:
        """Calculate recency score (0.0 to 1.0) based on publish date."""
        try:
            # Parse ISO 8601 date
            publish_dt = datetime.fromisoformat(publish_date.replace('Z', '+00:00'))
            now = datetime.now(publish_dt.tzinfo)
            age_days = (now - publish_dt).days
            
            # Score: newer = higher (decay over 2 years)
            if age_days < 30:
                return 1.0
            elif age_days < 90:
                return 0.9
            elif age_days < 180:
                return 0.8
            elif age_days < 365:
                return 0.6
            elif age_days < 730:
                return 0.4
            else:
                return 0.2
        except Exception:
            return 0.5  # Default if parsing fails
    
    def _is_valid_youtube_video(self, video_data: Dict[str, Any]) -> bool:
        """Check if video meets quality criteria."""
        duration = video_data.get('duration_sec', 0)
        
        # Must have captions (already filtered by API)
        # Duration must be in acceptable range
        if duration < YOUTUBE_MIN_DURATION_SEC or duration > YOUTUBE_MAX_DURATION_SEC:
            return False
        
        # Check if already in database (deduplication)
        url = video_data['url']
        cached = cache_manager.get_cached_source(url)
        if cached:
            return False  # Skip already cached sources
        
        return True
    
    def _rank_youtube_videos(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank YouTube videos by quality score."""
        if not videos:
            return []
        
        # Normalize metrics
        max_views = max((v.get('view_count', 0) for v in videos), default=1)
        max_likes = max((v.get('like_count', 0) for v in videos), default=1)
        
        for video in videos:
            # Normalize view count (0.0 to 1.0)
            view_normalized = min(video.get('view_count', 0) / max_views, 1.0)
            
            # Like ratio is already 0.0 to 1.0
            like_ratio = video.get('like_ratio', 0.0)
            
            # Relevance score (placeholder - API already orders by relevance)
            relevance_score = 0.8  # Default, could be enhanced
            
            # Recency score (already calculated)
            recency_score = video.get('recency_score', 0.5)
            
            # Calculate composite score
            score = (
                YOUTUBE_VIEW_WEIGHT * view_normalized +
                YOUTUBE_LIKE_WEIGHT * like_ratio +
                YOUTUBE_RELEVANCE_WEIGHT * relevance_score +
                YOUTUBE_RECENCY_WEIGHT * recency_score
            )
            
            video['score'] = score
        
        # Sort by score (descending)
        return sorted(videos, key=lambda v: v.get('score', 0), reverse=True)
    
    def _parse_article_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse DuckDuckGo search result."""
        try:
            url = result.get('href', '')
            if not url:
                return None
            
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '')
            
            # Get domain authority score
            domain_score = self._get_domain_authority(domain)
            
            # Recency (DuckDuckGo doesn't always provide date)
            recency_score = 0.5  # Default
            
            return {
                'url': url,
                'title': result.get('title', ''),
                'snippet': result.get('body', ''),
                'domain': domain,
                'domain_score': domain_score,
                'recency_score': recency_score,
            }
        except Exception as e:
            print(f"Error parsing article result: {e}")
            return None
    
    def _get_domain_authority(self, domain: str) -> float:
        """Get domain authority score (0.0 to 1.0)."""
        # Check exact match
        for auth_domain, score in self.HIGH_AUTHORITY_DOMAINS.items():
            if auth_domain in domain:
                return score
        
        # Check TLD
        if domain.endswith('.edu'):
            return 1.0
        elif domain.endswith('.org'):
            return 0.6
        elif domain.endswith('.gov'):
            return 0.8
        
        return 0.3  # Default for unknown domains
    
    def _is_valid_article(self, article_data: Dict[str, Any]) -> bool:
        """Check if article meets quality criteria."""
        # Check if already in database (deduplication)
        url = article_data['url']
        cached = cache_manager.get_cached_source(url)
        if cached:
            return False
        
        # Note: We can't validate word count without fetching the article
        # This will be done during ingestion
        return True
    
    def _rank_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank articles by quality score."""
        if not articles:
            return []
        
        for article in articles:
            domain_score = article.get('domain_score', 0.3)
            relevance_score = 0.7  # Default, could be enhanced with semantic matching
            recency_score = article.get('recency_score', 0.5)
            
            # Calculate composite score
            score = (
                ARTICLE_DOMAIN_WEIGHT * domain_score +
                ARTICLE_RELEVANCE_WEIGHT * relevance_score +
                ARTICLE_RECENCY_WEIGHT * recency_score
            )
            
            article['score'] = score
        
        # Sort by score (descending)
        return sorted(articles, key=lambda a: a.get('score', 0), reverse=True)
    
    def _diverse_sample(
        self,
        items: List[Dict[str, Any]],
        num_items: int,
        key: str = 'channel_id'
    ) -> List[Dict[str, Any]]:
        """Sample items with diversity constraint (max 2 per key)."""
        if not items:
            return []
        
        selected = []
        key_counts = {}
        
        for item in items:
            if len(selected) >= num_items:
                break
            
            item_key = item.get(key, '')
            
            # Allow max 2 items with same key
            if key_counts.get(item_key, 0) < 2:
                selected.append(item)
                key_counts[item_key] = key_counts.get(item_key, 0) + 1
        
        return selected
    
    def _generate_cache_key(
        self,
        query: str,
        difficulty: Optional[str],
        num_youtube: int,
        num_articles: int,
    ) -> str:
        """Generate cache key for query."""
        params_str = f"{query}|{difficulty}|{num_youtube}|{num_articles}"
        return hashlib.sha256(params_str.encode()).hexdigest()
    
    def _get_cached_result(
        self,
        cache_key: str
    ) -> Optional[SourceDiscoveryResult]:
        """Get cached discovery result if still valid."""
        result = db.execute_one(
            """
            SELECT query, youtube_results, article_results, expires_at
            FROM source_discovery_cache
            WHERE query_hash = ? AND expires_at > datetime('now')
            """,
            (cache_key,)
        )
        
        if result:
            # sqlite3.Row uses bracket access - columns are in SELECT, so access directly
            youtube_json = result['youtube_results']
            article_json = result['article_results']
            youtube_urls = json.loads(youtube_json or '[]')
            article_urls = json.loads(article_json or '[]')
            
            return SourceDiscoveryResult(
                youtube_urls=youtube_urls,
                article_urls=article_urls,
                metadata={'from_cache': True},
            )
        
        return None
    
    def _cache_result(
        self,
        cache_key: str,
        query: str,
        result: SourceDiscoveryResult,
    ) -> None:
        """Cache discovery result."""
        expires_at = datetime.now() + timedelta(hours=CACHE_TTL_HOURS)
        
        db.execute_write(
            """
            INSERT OR REPLACE INTO source_discovery_cache
            (query_hash, query, youtube_results, article_results, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                query,
                json.dumps(result.youtube_urls),
                json.dumps(result.article_urls),
                expires_at.isoformat(),
            )
        )


# Global source discoverer instance
source_discoverer = SourceDiscoverer()

