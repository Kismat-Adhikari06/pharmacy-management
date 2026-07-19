"""Database connection — SQLAlchemy session for the Flask web app."""
from __future__ import annotations

import logging
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent

from sqlalchemy import create_engine, event, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker, Session

from models import Base

logger = logging.getLogger(__name__)

DB_PATH = ROOT / "data" / "pharmacy.db"
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _rec):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


@contextmanager
def db_session():
    session = get_db()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Ensure all tables and columns exist. Safe to call on every startup."""
    # Create any missing tables
    Base.metadata.create_all(bind=engine)

    # Add missing columns (schema migration for existing databases)
    inspector = sa_inspect(engine)
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspector.get_table_names():
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name not in existing_cols:
                col_type = col.type.compile(engine.dialect)
                nullable = "" if col.nullable else " NOT NULL"
                default = ""
                if col.default is not None:
                    val = col.default.arg
                    if isinstance(val, str) and val == "":
                        default = " DEFAULT ''"
                    elif val is None:
                        default = " DEFAULT NULL"
                    else:
                        default = f" DEFAULT '{val}'" if isinstance(val, str) else f" DEFAULT {val}"
                elif not col.nullable:
                    default = " DEFAULT ''"
                ddl = f"ALTER TABLE [{table_name}] ADD COLUMN [{col.name}] {col_type}{nullable}{default}"
                with engine.connect() as conn:
                    conn.execute(text(ddl))
                    conn.commit()
                logger.info("Added column %s.%s", table_name, col.name)
