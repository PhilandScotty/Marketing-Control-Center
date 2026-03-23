import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DB_PATH

os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else "data", exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_outreach_columns()


def _migrate_outreach_columns():
    """Add new outreach contact columns if they don't exist (SQLite safe)."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(outreach_contacts)")
    existing = {row[1] for row in cursor.fetchall()}
    new_cols = [
        ("contact_email", "TEXT"),
        ("twitter_handle", "TEXT"),
        ("instagram_handle", "TEXT"),
        ("website_url", "TEXT"),
        ("outreach_log", "TEXT DEFAULT ''"),
        ("youtube_channel", "TEXT"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE outreach_contacts ADD COLUMN {col_name} {col_type}")
    conn.commit()
    conn.close()
