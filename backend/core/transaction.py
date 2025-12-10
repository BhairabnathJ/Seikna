"""
Database transaction management with rollback support.
"""
import sqlite3
import time
from typing import Optional, Callable, List, Any
from contextlib import contextmanager
from functools import wraps
from core.database import db


class TransactionManager:
    """Manages database transactions with rollback and compensation."""

    def __init__(self):
        self.compensation_handlers: List[Callable] = []

    @contextmanager
    def transaction(self, isolation_level: Optional[str] = None):
        """
        Context manager for database transactions.

        Usage:
            with transaction_manager.transaction():
                db.execute_write_in_transaction(...)
                db.execute_write_in_transaction(...)
                # If exception raised, all writes rolled back

        Args:
            isolation_level: Optional SQLite isolation level
                - None: Default (DEFERRED)
                - "IMMEDIATE": Lock database immediately
                - "EXCLUSIVE": Exclusive lock

        Yields:
            Connection object for manual operations
        """
        conn = db.get_connection_raw()

        # Set isolation level if specified
        if isolation_level:
            conn.isolation_level = isolation_level

        try:
            # Start transaction
            conn.execute("BEGIN")

            yield conn

            # Commit transaction
            conn.commit()

            # Clear compensation handlers on success
            self.compensation_handlers.clear()

        except Exception as e:
            # Rollback transaction
            conn.rollback()

            # Execute compensation handlers (for external operations)
            self._execute_compensation()

            # Re-raise exception
            raise

        finally:
            conn.close()

    @contextmanager
    def savepoint(self, conn: sqlite3.Connection, name: str):
        """
        Create a savepoint for nested transactions.

        Usage:
            with transaction_manager.savepoint(conn, "stage_3"):
                # Partial rollback possible

        Args:
            conn: Active connection
            name: Savepoint identifier
        """
        try:
            conn.execute(f"SAVEPOINT {name}")
            yield
            conn.execute(f"RELEASE SAVEPOINT {name}")
        except Exception:
            conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
            raise

    def register_compensation(self, handler: Callable[[], None]):
        """
        Register a compensation handler for external operations.

        Compensation handlers execute on rollback to undo
        non-database operations (e.g., delete cached files).

        Args:
            handler: Function to call on rollback
        """
        self.compensation_handlers.append(handler)

    def _execute_compensation(self):
        """Execute all registered compensation handlers in reverse order."""
        for handler in reversed(self.compensation_handlers):
            try:
                handler()
            except Exception as e:
                # Log but don't re-raise (rollback already happened)
                print(f"Compensation handler failed: {e}")


# Global transaction manager instance
transaction_manager = TransactionManager()


def retry_on_transient_error(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator to retry operations on transient errors.

    Detects SQLite busy errors, network timeouts, etc.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        # Database locked, retry
                        delay = base_delay * (2 ** attempt)
                        print(f"Database locked, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    raise
                except Exception as e:
                    # Check if error is transient
                    if _is_transient_error(e) and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Transient error, retrying in {delay}s: {e}")
                        time.sleep(delay)
                        continue
                    raise

            return func(*args, **kwargs)

        return wrapper
    return decorator


def _is_transient_error(error: Exception) -> bool:
    """Determine if error is transient (retryable)."""
    error_str = str(error).lower()
    transient_indicators = [
        "timeout",
        "connection reset",
        "temporary failure",
        "service unavailable",
        "429",  # Rate limit
        "503",  # Service unavailable
    ]
    return any(indicator in error_str for indicator in transient_indicators)

