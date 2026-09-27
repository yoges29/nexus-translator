import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("nexus.translator.db")
settings = get_settings()

try:
    engine = create_engine(settings.normalized_database_url, pool_pre_ping=True)
    # Probe connection
    with engine.connect() as conn:
        pass
except Exception as exc:
    logger.warning(
        "PostgreSQL connection failed (%s). Using SQLite database for persistence.",
        exc.__class__.__name__,
    )
    engine = create_engine("sqlite:///./nexus_translator.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import conversation, document, translation  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("Database init_db warning: %s", exc)


