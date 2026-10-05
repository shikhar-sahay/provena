"""Database foundation: engine, session factory, declarative base.

No application tables are defined yet. Future domain modules
(auth, cases, evidence, ...) will add models under ``app/modules/``
and import ``Base`` from here.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    if not settings.database_url:
        return None
    return create_engine(settings.database_url, pool_pre_ping=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None


def check_database() -> dict:
    """Return a small, non-fragile database status dict.

    Never raises: the health endpoint must stay up even when the
    database is down or unconfigured.
    """
    if engine is None:
        return {"configured": False, "reachable": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"configured": True, "reachable": True}
    except Exception:
        return {"configured": True, "reachable": False}
