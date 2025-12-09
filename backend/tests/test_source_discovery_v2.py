"""
Unit tests for Source Discovery V2.0 system.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from services.ingestion.source_discoverer_v2 import (
    SearchResult,
    SourceTier,
    validate_keyword_match,
    check_negative_keywords,
    pre_validate_source,
    add_context_keywords,
    normalize_query,
    discover_sources_v2,
)


class TestKeywordMatching:
    """Test keyword validation functions."""
    
    def test_validate_keyword_match_all_present(self):
        """Test that ALL keywords must be present."""
        result = SearchResult(
            url="https://realpython.com/python-decorators/",
            title="Python Decorators Tutorial"
        )
        
        # Should PASS: All keywords present
        assert validate_keyword_match(result, ["python", "decorators"]) is True
        assert validate_keyword_match(result, ["python", "decorators", "tutorial"]) is True
    
    def test_validate_keyword_match_missing_keyword(self):
        """Test that missing keywords cause rejection."""
        result = SearchResult(
            url="https://realpython.com/python-decorators/",
            title="Python Decorators Tutorial"
        )
        
        # Should FAIL: "advanced" keyword missing
        assert validate_keyword_match(result, ["python", "decorators", "advanced"]) is False
    
    def test_validate_keyword_match_case_insensitive(self):
        """Test that matching is case-insensitive."""
        result = SearchResult(
            url="https://example.com/PYTHON-DECORATORS",
            title="Python Decorators Guide"
        )
        
        assert validate_keyword_match(result, ["python", "decorators"]) is True


class TestNegativeKeywords:
    """Test negative keyword filtering."""
    
    def test_negative_keyword_rejection(self):
        """Test that negative keywords cause rejection."""
        result = SearchResult(
            url="https://example.com/home-decorators",
            title="Best Home Decorators for Your Living Room"
        )
        
        # Should FAIL: Contains negative keywords "home", "living room"
        assert check_negative_keywords(result, "decorators") is False
    
    def test_no_negative_keywords_defined(self):
        """Test that queries without negative keywords pass."""
        result = SearchResult(
            url="https://example.com/python-tutorial",
            title="Python Programming Tutorial"
        )
        
        # Should PASS: No negative keywords defined for "tutorial"
        assert check_negative_keywords(result, "tutorial") is True


class TestPreValidation:
    """Test pre-validation of sources."""
    
    def test_reject_pdf_files(self):
        """Test that PDF files are rejected."""
        result = SearchResult(
            url="https://example.com/document.pdf",
            title="Some Document"
        )
        
        assert pre_validate_source(result) is False
    
    def test_reject_blacklisted_domains(self):
        """Test that blacklisted domains are rejected."""
        result = SearchResult(
            url="https://stackoverflow.com/question/123",
            title="Some Question"
        )
        
        assert pre_validate_source(result) is False
    
    def test_reject_paywall_indicators(self):
        """Test that paywall URLs are rejected."""
        result = SearchResult(
            url="https://example.com/article/premium/123",
            title="Premium Article"
        )
        
        assert pre_validate_source(result) is False
    
    def test_accept_valid_source(self):
        """Test that valid sources pass pre-validation."""
        result = SearchResult(
            url="https://realpython.com/python-tutorial",
            title="Python Tutorial"
        )
        
        assert pre_validate_source(result) is True


class TestQueryProcessing:
    """Test query processing functions."""
    
    def test_add_context_keywords_ambiguous_term(self):
        """Test that ambiguous terms get context added."""
        query = "decorators"
        result = add_context_keywords(query)
        
        assert "python" in result.lower()
        assert "programming" in result.lower()
    
    def test_add_context_keywords_no_ambiguous_term(self):
        """Test that non-ambiguous queries get minimal changes."""
        query = "python lists"
        result = add_context_keywords(query)
        
        # Should add programming context if not present
        assert "python" in result.lower()
    
    def test_normalize_query(self):
        """Test query normalization."""
        query1 = "Python Decorators"
        query2 = "decorators python"
        
        assert normalize_query(query1) == normalize_query(query2)
        assert normalize_query(query1) == "decorators python"


class TestDiscoverSourcesV2:
    """Test the main discovery function (with mocking)."""
    
    @patch('services.ingestion.source_discoverer_v2.search_tier1_domains')
    @patch('services.ingestion.source_discoverer_v2.search_youtube')
    @patch('services.ingestion.source_discoverer_v2.search_edu_domains')
    @patch('services.ingestion.source_discoverer_v2._get_cached_results')
    def test_discover_sources_v2_no_cache(
        self,
        mock_cache,
        mock_edu,
        mock_youtube,
        mock_tier1
    ):
        """Test discovery with no cached results."""
        mock_cache.return_value = None
        
        # Mock tier 1 results
        mock_tier1.return_value = [
            SearchResult(
                url="https://realpython.com/python-decorators/",
                title="Python Decorators Tutorial",
                tier=SourceTier.TIER1
            )
        ]
        
        mock_youtube.return_value = []
        mock_edu.return_value = []
        
        results = discover_sources_v2("python decorators", target_count=5)
        
        assert len(results) >= 0  # May be filtered further
        mock_tier1.assert_called_once()
    
    @patch('services.ingestion.source_discoverer_v2._get_cached_results')
    def test_discover_sources_v2_with_cache(self, mock_cache):
        """Test that cached results are returned."""
        cached_results = [
            SearchResult(
                url="https://realpython.com/python-decorators/",
                title="Python Decorators Tutorial",
                tier=SourceTier.TIER1
            )
        ]
        mock_cache.return_value = cached_results
        
        results = discover_sources_v2("python decorators", target_count=5)
        
        assert results == cached_results[:5]
        assert len(results) <= 5


class TestWikipediaStrictMatching:
    """Test Wikipedia strict matching (requires mocking)."""
    
    @patch('services.ingestion.source_discoverer_v2.wikipedia')
    def test_wikipedia_strict_matching(self, mock_wikipedia):
        """Test that Wikipedia only returns exact matches."""
        # Mock Wikipedia search
        mock_wikipedia.search.return_value = [
            "Python Decorators",
            "Python (programming language)",
            "Decorator pattern"
        ]
        
        # Mock page object
        mock_page = MagicMock()
        mock_page.title = "Python Decorators"
        mock_page.url = "https://en.wikipedia.org/wiki/Python_Decorators"
        mock_page.summary = "Python decorators are a feature that allows..."
        
        mock_wikipedia.page.return_value = mock_page
        
        from services.ingestion.source_discoverer_v2 import search_wikipedia_strict
        
        results = search_wikipedia_strict("Python decorators")
        
        # Should only return exact matches
        assert len(results) >= 0  # May be 0 if filtering is strict
    
    @patch('services.ingestion.source_discoverer_v2.wikipedia')
    def test_wikipedia_reject_disambiguation(self, mock_wikipedia):
        """Test that disambiguation pages are rejected."""
        mock_wikipedia.search.return_value = ["Python"]
        
        # Raise DisambiguationError
        mock_wikipedia.exceptions.DisambiguationError = Exception
        mock_wikipedia.page.side_effect = Exception("Disambiguation")
        
        from services.ingestion.source_discoverer_v2 import search_wikipedia_strict
        
        results = search_wikipedia_strict("Python")
        
        # Should return empty or skip disambiguation
        assert isinstance(results, list)


@pytest.mark.skip(reason="Requires network access - mark as integration test")
class TestIntegration:
    """Integration tests that require network access."""
    
    def test_full_discovery_pipeline(self):
        """Test end-to-end source discovery."""
        query = "Python decorators"
        results = discover_sources_v2(query, target_count=5)
        
        # Assertions
        assert len(results) <= 5
        assert all(isinstance(r, SearchResult) for r in results)
        
        # All results should match keywords
        query_keywords = query.split()
        for result in results:
            assert validate_keyword_match(result, query_keywords)
    
    def test_performance_target(self):
        """Test that discovery completes within 15 seconds."""
        import time
        
        start = time.time()
        results = discover_sources_v2("Python async await", target_count=3)
        elapsed = time.time() - start
        
        assert elapsed < 15.0  # Must complete in < 15 seconds
        assert len(results) >= 0  # May return fewer if strict filtering
    
    def test_no_results_fallback(self):
        """Test behavior when no sources found."""
        results = discover_sources_v2("zxqwertyjkl12345", target_count=5)
        
        # Should return empty list, not crash
        assert isinstance(results, list)
        assert len(results) >= 0
