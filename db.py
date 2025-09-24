from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from pathlib import Path

# --- Config (adjust if your DB path is different) ---
DATA_DIR = Path("./data").resolve()
DB_PATH = DATA_DIR / "rag_app.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Singleton SQLAlchemy engine pointing to the local SQLite file."""
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
    return _engine


# --- Schema: documents, sessions, messages, pages ---
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    bytes INTEGER NOT NULL DEFAULT 0,
    pages INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,         -- 'user' | 'assistant'
    content TEXT NOT NULL,
    citations TEXT,             -- JSON string (list of {doc_name,page,score})
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    page_no INTEGER NOT NULL,
    text TEXT NOT NULL,
    FOREIGN KEY(doc_id) REFERENCES documents(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pages_doc_page ON pages(doc_id, page_no);
"""


def init_db() -> None:
    """Create tables/idempotent schema."""
    eng = get_engine()
    with eng.begin() as conn:
        for stmt in SCHEMA_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
