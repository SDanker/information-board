from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
is_sqlite = settings.database_url.startswith("sqlite")
is_sqlite_memory = is_sqlite and (":memory:" in settings.database_url or settings.database_url in ("sqlite://", "sqlite:///"))
engine_kwargs: dict = {"pool_pre_ping": True}
if is_sqlite_memory:
    # Only the in-memory database (used by tests) must share one connection across
    # threads; a file-based SQLite database must not be forced into StaticPool.
    engine_kwargs.update(connect_args={"check_same_thread": False}, poolclass=StaticPool)

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

if is_sqlite:
    # SQLite ignores foreign keys (including ON DELETE SET NULL/CASCADE) unless enabled
    # per connection. PostgreSQL always enforces them; this keeps development and tests
    # consistent so integrity problems are not discovered only in production.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
