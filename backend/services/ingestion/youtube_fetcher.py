"""
YouTube transcript fetcher using youtube-transcript-api and yt-dlp.
"""
import yt_dlp
import uuid
import re
from typing import Dict, Any, Optional
from services.ingestion.cache_manager import cache_manager

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = False


class YouTubeFetcher:
    """Fetches transcripts and metadata from YouTube videos."""
    
    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def get_transcript(video_id: str) -> Optional[str]:
        """
        Get transcript text for a YouTube video ID.
        
        Uses youtube-transcript-api first (more reliable), falls back to yt-dlp.
        
        Args:
            video_id: YouTube video ID (e.g., "dQw4w9WgXcQ")
        
        Returns:
            Transcript text as string, or None if unavailable
        """
        if not video_id:
            return None
        
        # Method 1: Try youtube-transcript-api (most reliable)
        if YOUTUBE_TRANSCRIPT_API_AVAILABLE:
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                # Combine all transcript entries into text
                transcript_text = ' '.join([entry['text'] for entry in transcript_list])
                return transcript_text.strip()
            except (TranscriptsDisabled, NoTranscriptFound):
                # Transcript not available via API, try yt-dlp fallback
                pass
            except Exception as e:
                print(f"Error fetching transcript via youtube-transcript-api for {video_id}: {e}")
                # Fall through to yt-dlp
        
        # Method 2: Fallback to yt-dlp
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'skip_download': True,
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Try to get subtitle URL and fetch content
                subtitles = info.get('subtitles', {})
                auto_subtitles = info.get('automatic_captions', {})
                
                # Prefer manual subtitles, fallback to auto
                captions = subtitles.get('en', auto_subtitles.get('en', []))
                
                if captions and len(captions) > 0:
                    # Get the first available subtitle URL
                    sub_url = captions[0].get('url')
                    if sub_url:
                        # Fetch the subtitle content
                        import requests
                        response = requests.get(sub_url, timeout=10)
                        if response.status_code == 200:
                            # Parse subtitle content
                            return YouTubeFetcher._parse_subtitle_content(response.text)
                
        except Exception as e:
            print(f"Error fetching transcript via yt-dlp for {video_id}: {e}")
        
        return None
    
    @staticmethod
    def _parse_subtitle_content(content: str) -> str:
        """Parse subtitle content (WebVTT or TTML) into plain text."""
        lines = content.split('\n')
        transcript_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, timestamps, and metadata
            if not line:
                continue
            if '-->' in line:  # Timestamp line
                continue
            if line.startswith('WEBVTT') or line.startswith('NOTE'):
                continue
            if line.startswith('<') and line.endswith('>'):  # HTML/TTML tags
                continue
            # Skip cue identifiers (numbers)
            if line.isdigit():
                continue
            # Skip style blocks
            if line.startswith('STYLE') or line.startswith('::cue'):
                continue
            
            # Clean up HTML entities and tags
            line = re.sub(r'<[^>]+>', '', line)  # Remove HTML tags
            line = re.sub(r'&nbsp;', ' ', line)
            line = re.sub(r'&amp;', '&', line)
            line = re.sub(r'&lt;', '<', line)
            line = re.sub(r'&gt;', '>', line)
            
            if line:
                transcript_lines.append(line)
        
        # Join and clean up extra spaces
        transcript = ' '.join(transcript_lines)
        transcript = re.sub(r'\s+', ' ', transcript)
        return transcript.strip()
    
    @staticmethod
    def fetch_youtube_transcript(url: str) -> Dict[str, Any]:
        """
        Fetch transcript and metadata from a YouTube URL.
        
        Returns:
            {
                "source_id": str,
                "url": str,
                "title": str,
                "transcript": str,  # Empty string if unavailable
                "metadata": dict,
                "source_type": "youtube"
            }
        """
        # Check cache first
        cached = cache_manager.get_cached_source(url)
        if cached:
            return cached
        
        source_id = f"yt_{uuid.uuid4().hex[:12]}"
        
        # Extract video ID
        video_id = YouTubeFetcher._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")
        
        try:
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                title = info.get('title', 'Untitled')
                duration = info.get('duration', 0)
                uploader = info.get('uploader', 'Unknown')
                publish_date = info.get('upload_date', '')
                
                # Get transcript using the new method
                transcript = YouTubeFetcher.get_transcript(video_id) or ""
                
                metadata = {
                    "author": uploader,
                    "duration": duration,
                    "publish_date": publish_date,
                    "view_count": info.get('view_count', 0),
                    "description": info.get('description', '')[:500],  # Limit description length
                    "video_id": video_id,
                }
                
                result = {
                    "source_id": source_id,
                    "url": url,
                    "title": title,
                    "transcript": transcript,
                    "metadata": metadata,
                    "source_type": "youtube",
                }
                
                # Save to cache
                cache_manager.save_source(
                    source_id=source_id,
                    source_type="youtube",
                    url=url,
                    title=title,
                    transcript=transcript,
                    metadata=metadata,
                )
                
                return result
                
        except Exception as e:
            raise Exception(f"Failed to fetch YouTube video: {str(e)}")


# Global YouTube fetcher instance
youtube_fetcher = YouTubeFetcher()
