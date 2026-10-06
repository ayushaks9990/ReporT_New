from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings


engine_options: dict = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_options)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _sqlite_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def initialize_database() -> None:
    # Import every table before create_all. Existing app tables are left intact.
    from backend import models  # noqa: F401

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            # Serialize startup DDL across workers / overlapping Render deploys.
            connection.execute(text("SELECT pg_advisory_xact_lock(736217401)"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=connection)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
