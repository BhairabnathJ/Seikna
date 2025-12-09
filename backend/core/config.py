"""
Configuration management for Seikna backend.
Loads configuration from environment variables and .env file.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
# Look for .env file in the backend directory or project root
BACKEND_DIR = Path(__file__).parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Load .env file if it exists
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    # Also try loading from backend directory
    backend_env = BACKEND_DIR / ".env"
    if backend_env.exists():
        load_dotenv(backend_env)

# Base paths
BASE_DIR = PROJECT_ROOT
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
FRAMES_DIR = DATA_DIR / "frames"
DB_PATH = DATA_DIR / "seikna.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MIXTRAL_MODEL = os.getenv("OLLAMA_MIXTRAL_MODEL", "mixtral:latest")
OLLAMA_LLAVA_MODEL = os.getenv("OLLAMA_LLAVA_MODEL", "llava:latest")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")

# API Keys (for source discovery)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", None)
WEB_SEARCH_API_KEY = os.getenv("WEB_SEARCH_API_KEY", None)  # SerpAPI key (optional)
SERPAPI_KEY = os.getenv("SERPAPI_KEY", None)  # Alternative to WEB_SEARCH_API_KEY

# Source Discovery Configuration
DEFAULT_NUM_YOUTUBE = int(os.getenv("DEFAULT_NUM_YOUTUBE", "5"))
DEFAULT_NUM_ARTICLES = int(os.getenv("DEFAULT_NUM_ARTICLES", "3"))
YOUTUBE_MIN_DURATION_SEC = int(os.getenv("YOUTUBE_MIN_DURATION_SEC", "240"))  # 4 minutes
YOUTUBE_MAX_DURATION_SEC = int(os.getenv("YOUTUBE_MAX_DURATION_SEC", "1200"))  # 20 minutes
ARTICLE_MIN_WORDS = int(os.getenv("ARTICLE_MIN_WORDS", "500"))
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

# Ranking weights for YouTube videos
YOUTUBE_VIEW_WEIGHT = float(os.getenv("YOUTUBE_VIEW_WEIGHT", "0.4"))
YOUTUBE_LIKE_WEIGHT = float(os.getenv("YOUTUBE_LIKE_WEIGHT", "0.3"))
YOUTUBE_RELEVANCE_WEIGHT = float(os.getenv("YOUTUBE_RELEVANCE_WEIGHT", "0.2"))
YOUTUBE_RECENCY_WEIGHT = float(os.getenv("YOUTUBE_RECENCY_WEIGHT", "0.1"))

# Ranking weights for articles
ARTICLE_DOMAIN_WEIGHT = float(os.getenv("ARTICLE_DOMAIN_WEIGHT", "0.5"))
ARTICLE_RELEVANCE_WEIGHT = float(os.getenv("ARTICLE_RELEVANCE_WEIGHT", "0.3"))
ARTICLE_RECENCY_WEIGHT = float(os.getenv("ARTICLE_RECENCY_WEIGHT", "0.2"))

# LLM settings (can be overridden via env vars)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

# API configuration
API_V1_PREFIX = "/api/v1"
# CORS origins can be comma-separated list in env var
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",")]

# Ingestion settings
MAX_SOURCES_PER_QUERY = int(os.getenv("MAX_SOURCES_PER_QUERY", "8"))
DEFAULT_NUM_SOURCES = int(os.getenv("DEFAULT_NUM_SOURCES", "5"))

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", None)  # For future PostgreSQL migration

# Course Generation Pipeline Configuration
CHUNK_TARGET_SIZE = int(os.getenv("CHUNK_TARGET_SIZE", "300"))  # words
CHUNK_MIN_SIZE = int(os.getenv("CHUNK_MIN_SIZE", "150"))
CHUNK_MAX_SIZE = int(os.getenv("CHUNK_MAX_SIZE", "500"))
CHUNK_OVERLAP_SIZE = int(os.getenv("CHUNK_OVERLAP_SIZE", "50"))
USE_EMBEDDING_CHUNKING = os.getenv("USE_EMBEDDING_CHUNKING", "true").lower() == "true"

# Quality thresholds
MIN_COHERENCE_SCORE = float(os.getenv("MIN_COHERENCE_SCORE", "0.7"))
MIN_COMPLETENESS_SCORE = float(os.getenv("MIN_COMPLETENESS_SCORE", "0.6"))
MIN_SEMANTIC_DENSITY = float(os.getenv("MIN_SEMANTIC_DENSITY", "0.3"))

# Expansion parameters
EXPANSION_MODEL = os.getenv("EXPANSION_MODEL", OLLAMA_MIXTRAL_MODEL)
EXPANSION_TEMPERATURE = float(os.getenv("EXPANSION_TEMPERATURE", "0.3"))
EXPANSION_MAX_TOKENS = int(os.getenv("EXPANSION_MAX_TOKENS", "2048"))
MIN_CLAIMS_PER_CHUNK = int(os.getenv("MIN_CLAIMS_PER_CHUNK", "2"))
MAX_COGNITIVE_LOAD = float(os.getenv("MAX_COGNITIVE_LOAD", "0.9"))

# Section parameters
MIN_SECTION_WORD_COUNT = int(os.getenv("MIN_SECTION_WORD_COUNT", "200"))
MIN_CITATIONS_PER_SECTION = int(os.getenv("MIN_CITATIONS_PER_SECTION", "1"))
TARGET_TAKEAWAYS_PER_SECTION = int(os.getenv("TARGET_TAKEAWAYS_PER_SECTION", "3"))
TARGET_QUESTIONS_PER_SECTION = int(os.getenv("TARGET_QUESTIONS_PER_SECTION", "3"))

# Processing optimization
LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "5"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "10"))

# Validation
ENABLE_QUALITY_VALIDATION = os.getenv("ENABLE_QUALITY_VALIDATION", "true").lower() == "true"
FAIL_ON_LOW_QUALITY = os.getenv("FAIL_ON_LOW_QUALITY", "false").lower() == "true"

# Source Discovery V2 Configuration
USE_SOURCE_DISCOVERY_V2 = os.getenv("USE_SOURCE_DISCOVERY_V2", "True").lower() == "true"


class SourceDiscoveryConfigV2:
    """Configuration for Source Discovery V2.0 system."""
    
    # Tier 1 Domains (Whitelisted)
    TIER_1_DOMAINS = [
        "realpython.com",
        "python.org",
        "docs.python.org",
        "pythontutorial.net",
        "learnpython.org",
        "w3schools.com",
        "geeksforgeeks.org",
        "freecodecamp.org",
    ]
    
    # Blacklisted Domains
    BLACKLISTED_DOMAINS = [
        "stackoverflow.com",
        "reddit.com",
        "quora.com",
        "researchgate.net",
        "arxiv.org",
    ]
    
    # YouTube Constraints
    YOUTUBE_MIN_DURATION = 300  # 5 minutes
    YOUTUBE_MAX_DURATION = 3600  # 60 minutes
    
    # Transcript Settings
    ACCEPT_AUTO_CAPTIONS = True
    MIN_TRANSCRIPT_WORDS = 100
    
    # Search Timeouts
    SEARCH_TIMEOUT_PER_TIER = 5  # seconds
    TOTAL_SEARCH_TIMEOUT = 15  # seconds
    
    # Target Counts
    TARGET_SOURCE_COUNT = 5
    MIN_SOURCES_BEFORE_WIKIPEDIA = 2  # Use Wikipedia only if < 2 sources
    
    # Negative Keywords (Topic Disambiguation)
    NEGATIVE_KEYWORDS = {
        "decorators": ["home", "interior", "wall", "room", "design", "furniture"],
        "classes": ["school", "university", "classroom", "student"],
        "async": ["asynchronous motor", "electrical"]
    }
    
    # Keyword Match Threshold
    KEYWORD_MATCH_THRESHOLD = 1.0  # ALL keywords must match (100%)
    
    # File Extensions to Reject
    REJECTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.zip', '.exe']
    
    # Paywall Indicators
    PAYWALL_INDICATORS = ['/premium/', '/subscribe/', '/membership/']
    
    # Administrative page keywords to filter from .edu domains
    ADMIN_PAGE_KEYWORDS = ['admissions', 'contact', 'about', 'directory', 'calendar']

