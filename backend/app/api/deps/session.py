"""Request-scoped database session dependency.

This is a thin alias for `app.db.session.get_db` so the API layer depends on
one implementation. The session is closed even when the handler raises, so a
connection can never leak back to the pool.

The session is synchronous because the runtime has no `greenlet` and
therefore cannot execute async ORM code.
"""

from app.db.session import SessionLocal, get_db

__all__ = ["SessionLocal", "get_db"]
