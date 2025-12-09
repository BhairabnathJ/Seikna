"""
Web article scraper using requests and BeautifulSoup.
"""
import requests
import uuid
import re
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from services.ingestion.cache_manager import cache_manager


class ArticleScraper:
    """Fetches and extracts content from web articles."""
    
    @staticmethod
    def fetch_article(url: str) -> Dict[str, Any]:
        """
        Fetch and extract content from an article URL.
        
        Returns:
            {
                "source_id": str,
                "url": str,
                "title": str,
                "content": str,
                "metadata": dict
            }
        """
        # Check cache first
        cached = cache_manager.get_cached_source(url)
        if cached:
            # Map transcript to content for articles
            cached["content"] = cached.pop("transcript", "")
            return cached
        
        source_id = f"art_{uuid.uuid4().hex[:12]}"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = ""
            if soup.find('title'):
                title = soup.find('title').get_text().strip()
            elif soup.find('h1'):
                title = soup.find('h1').get_text().strip()
            elif soup.find('meta', property='og:title'):
                title = soup.find('meta', property='og:title').get('content', '').strip()
            
            # Extract main content
            # Try common article selectors
            content_selectors = [
                'article',
                '[role="article"]',
                '.article-content',
                '.post-content',
                '.entry-content',
                'main',
                '.content',
            ]
            
            content = ""
            for selector in content_selectors:
                article_elem = soup.select_one(selector)
                if article_elem:
                    # Remove script and style elements
                    for script in article_elem(["script", "style", "nav", "header", "footer", "aside"]):
                        script.decompose()
                    content = article_elem.get_text(separator=' ', strip=True)
                    break
            
            # Fallback: get body text if no article found
            if not content:
                body = soup.find('body')
                if body:
                    for script in body(["script", "style", "nav", "header", "footer", "aside"]):
                        script.decompose()
                    content = body.get_text(separator=' ', strip=True)
            
            # Clean up content
            content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
            content = content[:50000]  # Limit content length
            
            # Extract metadata
            author = ""
            if soup.find('meta', property='article:author'):
                author = soup.find('meta', property='article:author').get('content', '')
            elif soup.find('meta', {'name': 'author'}):
                author = soup.find('meta', {'name': 'author'}).get('content', '')
            
            publish_date = ""
            if soup.find('meta', property='article:published_time'):
                publish_date = soup.find('meta', property='article:published_time').get('content', '')
            elif soup.find('time'):
                publish_date = soup.find('time').get('datetime', '')
            
            metadata = {
                "author": author,
                "publish_date": publish_date,
                "word_count": len(content.split()),
            }
            
            result = {
                "source_id": source_id,
                "url": url,
                "title": title,
                "content": content,
                "transcript": content,  # Store as transcript for compatibility
                "metadata": metadata,
            }
            
            # Save to cache
            cache_manager.save_source(
                source_id=source_id,
                source_type="article",
                url=url,
                title=title,
                transcript=content,
                metadata=metadata,
            )
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to fetch article: {str(e)}")


# Global article scraper instance
article_scraper = ArticleScraper()

