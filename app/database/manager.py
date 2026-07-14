from __future__ import annotations

import hashlib
import logging

from sqlalchemy import inspect as sa_inspect, text

from app.database.engine import Base, get_engine, new_session
from app.models.settings import Settings
from app.models.user import User

logger = logging.getLogger(__name__)

_DEFAULT_ADMIN_USERNAME = "admin"
_DEFAULT_ADMIN_PASSWORD = "admin"
_DEFAULT_ADMIN_ROLE = "Admin"
_DEFAULT_ADMIN_FULL_NAME = "Administrator"

_DEFAULT_PHARMACY_NAME = "My Pharmacy"
_DEFAULT_THEME = "dark"


class DatabaseManager:
    """Manages database lifecycle: creation, seeding, and session access."""

    @staticmethod
    def init_db() -> None:
        """Create the database file, tables, and seed initial data.

        Safe to call on every startup — existing data is never overwritten.
        """
        engine = get_engine()
        inspector = sa_inspect(engine)

        existing_tables = inspector.get_table_names()
        tables_to_create = [
            t for t in Base.metadata.tables.keys() if t not in existing_tables
        ]

        if tables_to_create:
            Base.metadata.create_all(bind=engine, tables=[
                Base.metadata.tables[t] for t in tables_to_create
            ])
            logger.info("Created tables: %s", ", ".join(tables_to_create))
        else:
            logger.info("All tables already exist.")

        DatabaseManager._migrate_columns(engine, inspector)
        DatabaseManager._seed_defaults()

    @staticmethod
    def _seed_defaults() -> None:
        """Insert the admin user and default settings if they don't exist."""
        session = new_session()
        try:
            DatabaseManager._seed_admin(session)
            DatabaseManager._seed_settings(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _migrate_columns(engine, inspector) -> None:
        """Add missing columns to existing tables for schema evolution."""
        for table_name, table_meta in Base.metadata.tables.items():
            if table_name not in inspector.get_table_names():
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for col in table_meta.columns:
                if col.name not in existing_cols:
                    nullable = col.nullable if col.nullable is not None else True
                    col_type = col.type.compile(engine.dialect)
                    ddl = f'ALTER TABLE [{table_name}] ADD COLUMN [{col.name}] {col_type}'
                    if not nullable:
                        default_val = col.default.arg if col.default is not None else None
                        if default_val is not None:
                            ddl += f' DEFAULT {repr(default_val)}'
                        else:
                            ddl += " DEFAULT ''"
                    with engine.connect() as conn:
                        conn.execute(text(ddl))
                        conn.commit()
                    logger.info("Added column %s.%s", table_name, col.name)

    @staticmethod
    def _seed_admin(session) -> None:
        """Insert default admin user if no users exist yet."""
        from sqlalchemy import select

        stmt = select(User).where(User.username == _DEFAULT_ADMIN_USERNAME)
        if session.execute(stmt).scalar_one_or_none() is not None:
            return

        password_hash = hashlib.sha256(
            _DEFAULT_ADMIN_PASSWORD.encode("utf-8")
        ).hexdigest()

        admin = User(
            username=_DEFAULT_ADMIN_USERNAME,
            password_hash=password_hash,
            role=_DEFAULT_ADMIN_ROLE,
            full_name=_DEFAULT_ADMIN_FULL_NAME,
        )
        session.add(admin)
        logger.info("Seeded default admin user.")

    @staticmethod
    def _seed_settings(session) -> None:
        """Insert default pharmacy settings if none exist."""
        from sqlalchemy import select

        stmt = select(Settings).limit(1)
        if session.execute(stmt).scalar_one_or_none() is not None:
            return

        settings = Settings(
            pharmacy_name=_DEFAULT_PHARMACY_NAME,
            address="",
            phone="",
            pan_number="",
            default_theme=_DEFAULT_THEME,
        )
        session.add(settings)
        logger.info("Seeded default settings.")
