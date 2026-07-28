"""SQLite engine, connection pragmas, and first-launch initialisation.

The user never runs a migration command. ``init_db()`` is called at startup and
creates the data directories and any missing tables.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from src import config

# Importing the models registers every table on SQLModel.metadata, which
# create_all() needs. Without this import the schema would come out empty.
from src import models  # noqa: F401

_engines: dict[Path, Engine] = {}


def _configure_connection(dbapi_connection, connection_record) -> None:
    """Apply the pragmas this application depends on, per connection.

    ``foreign_keys`` is a per-connection setting in SQLite and defaults to OFF,
    so without this the foreign keys in the schema would be decorative.
    ``journal_mode=WAL`` persists in the database file, but setting it here
    means a freshly created database gets it immediately.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        # Wait rather than fail if another connection holds a write lock.
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def get_engine() -> Engine:
    """Return the engine for the currently configured database path.

    Engines are cached per path so the test suite can point
    ``FIELD_TICKET_DATA_DIR`` at a temporary directory and get a clean engine.
    """
    path = config.database_path()
    engine = _engines.get(path)
    if engine is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            f"sqlite:///{path}",
            echo=False,
            # Streamlit reruns scripts across threads; sessions are short-lived
            # and never shared, so this is safe here.
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _configure_connection)
        _engines[path] = engine
    return engine


def dispose_engines() -> None:
    """Close all pooled connections. Used by tests and before restoring a backup."""
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()


@contextmanager
def get_session() -> Iterator[Session]:
    """A session that commits on success and rolls back on error.

    ``expire_on_commit=False`` keeps objects usable after the ``with`` block,
    which matters because Streamlit renders them after the session has closed.
    """
    session = Session(get_engine(), expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_data_directories() -> None:
    for directory in config.all_data_dirs():
        directory.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    """Create the data directories and any missing tables. Safe to call repeatedly."""
    create_data_directories()
    SQLModel.metadata.create_all(get_engine())
    _ensure_company_settings()


def _ensure_company_settings() -> None:
    """Guarantee the single settings row exists so pages can always read it."""
    from src.models import CompanySettings

    with get_session() as session:
        if session.get(CompanySettings, 1) is None:
            session.add(
                CompanySettings(
                    id=1,
                    payment_terms=config.DEFAULT_PAYMENT_TERMS,
                    invoice_prefix=config.DEFAULT_INVOICE_PREFIX,
                    next_invoice_number=config.DEFAULT_STARTING_INVOICE_NUMBER,
                    default_gst_rate=config.DEFAULT_GST_RATE,
                    ollama_model=config.DEFAULT_OLLAMA_MODEL,
                )
            )


def pragma(name: str) -> object:
    """Read a SQLite pragma. Used by the tests and the diagnostics page."""
    with get_engine().connect() as connection:
        return connection.execute(text(f"PRAGMA {name}")).scalar()
