"""
Configuration validation for Seikna backend.
Validates prompt files, models, database, and settings on startup.
"""
import os
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass

class ConfigValidator:
    """Validates system configuration before pipeline execution."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Dict[str, Any]:
        """
        Run all validation checks.

        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str]
            }
        """
        self.errors = []
        self.warnings = []

        # Run all checks
        self._validate_prompt_files()
        self._validate_ollama_connection()
        self._validate_ollama_models()
        self._validate_database()
        self._validate_directories()
        self._validate_config_values()

        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings
        }

    def _validate_prompt_files(self):
        """Check that all required prompt files exist."""
        from core.config import BACKEND_DIR

        prompts_dir = BACKEND_DIR / "prompts"
        required_prompts = [
            "claim_extraction.txt",
            "chunk_expansion.txt",
            "course_structure.txt",
        ]

        if not prompts_dir.exists():
            self.errors.append(
                f"Prompts directory not found: {prompts_dir}. "
                "Create directory and add prompt files."
            )
            return

        for prompt_file in required_prompts:
            path = prompts_dir / prompt_file
            if not path.exists():
                self.errors.append(
                    f"Required prompt file missing: {prompt_file}. "
                    f"Expected at: {path}"
                )
            elif path.stat().st_size == 0:
                self.warnings.append(f"Prompt file is empty: {prompt_file}")

    def _validate_ollama_connection(self):
        """Check that Ollama service is reachable."""
        from core.config import OLLAMA_BASE_URL

        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            self.errors.append(
                f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
                "Ensure Ollama is running: `ollama serve`"
            )
        except requests.exceptions.Timeout:
            self.errors.append(
                f"Ollama connection timeout at {OLLAMA_BASE_URL}. "
                "Check network or Ollama performance."
            )
        except Exception as e:
            self.errors.append(f"Ollama connection error: {e}")

    def _validate_ollama_models(self):
        """Check that required models are pulled and available."""
        from core.config import (
            OLLAMA_BASE_URL,
            OLLAMA_MIXTRAL_MODEL,
            OLLAMA_EMBED_MODEL,
        )

        required_models = {
            "Mixtral (text generation)": OLLAMA_MIXTRAL_MODEL,
            "Nomic-Embed (embeddings)": OLLAMA_EMBED_MODEL,
        }

        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
            available_models = [model["name"] for model in response.json().get("models", [])]

            for model_name, model_id in required_models.items():
                if model_id not in available_models:
                    self.errors.append(
                        f"Required model not found: {model_name} ({model_id}). "
                        f"Pull it with: `ollama pull {model_id}`"
                    )

        except Exception as e:
            # Ollama connection already checked, skip if failed
            pass

    def _validate_database(self):
        """Check that database is accessible and schema is initialized."""
        from core.config import DB_PATH

        if not DB_PATH.exists():
            self.warnings.append(
                f"Database file not found at {DB_PATH}. "
                "Will be created on first run."
            )
            return

        # Try to connect
        try:
            from core.database import db

            # Check that required tables exist
            required_tables = [
                "sources",
                "claims",
                "courses",
                "raw_transcripts",
                "transcript_chunks",
                "expanded_chunks",
            ]

            for table in required_tables:
                result = db.execute_one(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                if not result:
                    self.errors.append(
                        f"Required database table missing: {table}. "
                        "Run schema initialization."
                    )

        except Exception as e:
            self.errors.append(f"Database connection error: {e}")

    def _validate_directories(self):
        """Check that required directories exist."""
        from core.config import DATA_DIR, CACHE_DIR, FRAMES_DIR

        directories = {
            "Data directory": DATA_DIR,
            "Cache directory": CACHE_DIR,
            "Frames directory": FRAMES_DIR,
        }

        for name, path in directories.items():
            if not path.exists():
                self.warnings.append(
                    f"{name} not found at {path}. Will be created automatically."
                )

    def _validate_config_values(self):
        """Validate configuration value ranges and types."""
        from core.config import (
            CHUNK_TARGET_SIZE,
            CHUNK_MIN_SIZE,
            CHUNK_MAX_SIZE,
            MIN_COHERENCE_SCORE,
            LLM_TEMPERATURE,
        )

        # Chunk size validation
        if CHUNK_MIN_SIZE >= CHUNK_TARGET_SIZE:
            self.errors.append(
                f"CHUNK_MIN_SIZE ({CHUNK_MIN_SIZE}) must be < CHUNK_TARGET_SIZE ({CHUNK_TARGET_SIZE})"
            )

        if CHUNK_TARGET_SIZE >= CHUNK_MAX_SIZE:
            self.errors.append(
                f"CHUNK_TARGET_SIZE ({CHUNK_TARGET_SIZE}) must be < CHUNK_MAX_SIZE ({CHUNK_MAX_SIZE})"
            )

        # Quality threshold validation
        if not (0.0 <= MIN_COHERENCE_SCORE <= 1.0):
            self.errors.append(
                f"MIN_COHERENCE_SCORE ({MIN_COHERENCE_SCORE}) must be between 0.0 and 1.0"
            )

        # Temperature validation
        if not (0.0 <= LLM_TEMPERATURE <= 1.0):
            self.warnings.append(
                f"LLM_TEMPERATURE ({LLM_TEMPERATURE}) outside normal range [0.0, 1.0]"
            )

# Global validator instance
config_validator = ConfigValidator()

