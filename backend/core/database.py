"""
SQLite database connection and initialization.
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from .config import DB_PATH


class Database:
    """Database manager for SQLite operations."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.ensure_tables()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_connection_raw(self):
        """Get a raw connection (for operations that need manual commit)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def ensure_tables(self):
        """Create all tables if they don't exist."""
        schema_file = Path(__file__).parent.parent / "db" / "schema.sql"
        if schema_file.exists():
            with open(schema_file, "r") as f:
                schema = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema)
    
    def execute(self, query: str, params: Optional[tuple] = None) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params or ())
            return cursor.fetchall()
    
    def execute_one(self, query: str, params: Optional[tuple] = None) -> Optional[sqlite3.Row]:
        """Execute a SELECT query and return first result."""
        results = self.execute(query, params)
        return results[0] if results else None
    
    def execute_write(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return last row ID."""
        conn = self.get_connection_raw()
        try:
            cursor = conn.execute(query, params or ())
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


# Global database instance
db = Database()

