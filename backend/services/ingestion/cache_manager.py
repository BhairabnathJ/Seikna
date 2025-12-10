"""
Cache manager for storing and retrieving fetched sources.
"""
import json
import hashlib
from typing import Optional, Dict, Any
from core.database import db


class CacheManager:
    """Manages caching of fetched sources to avoid re-fetching."""
    
    @staticmethod
    def _hash_url(url: str) -> str:
        """Generate hash for URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    
    def get_cached_source(self, url: str) -> Optional[Dict[str, Any]]:
        """Check if source is cached and return it."""
        result = db.execute_one(
            "SELECT * FROM sources WHERE url = ?",
            (url,)
        )
        
        if result:
            # sqlite3.Row uses bracket access - required columns accessed directly
            # Handle optional/nullable columns safely
            metadata_json = result["metadata"] if "metadata" in result.keys() else None
            return {
                "source_id": result["source_id"],
                "source_type": result["source_type"],
                "url": result["url"],
                "title": result["title"] if "title" in result.keys() else None,
                "transcript": result["transcript"] if "transcript" in result.keys() else None,
                "metadata": json.loads(metadata_json) if metadata_json else {},
                "vct_tier": result["vct_tier"] if "vct_tier" in result.keys() else None,
                "fetched_at": result["fetched_at"] if "fetched_at" in result.keys() else None,
            }
        return None
    
    def save_source(
        self,
        source_id: str,
        source_type: str,
        url: str,
        title: Optional[str] = None,
        transcript: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        vct_tier: Optional[int] = None,
    ) -> None:
        """Save a source to cache."""
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Try to insert, ignore if already exists
        db.execute_write(
            """
            INSERT OR IGNORE INTO sources 
            (source_id, source_type, url, title, transcript, metadata, vct_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, source_type, url, title, transcript, metadata_json, vct_tier)
        )
    
    def delete_source(self, url: str) -> None:
        """Delete source from cache (compensation handler)."""
        db.execute_write(
            "DELETE FROM sources WHERE url = ?",
            (url,)
        )


# Global cache manager instance
cache_manager = CacheManager()

