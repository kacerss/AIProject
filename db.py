from sqlalchemy import create_engine, text, select, insert, update, delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SQLSession
from pathlib import Path
from typing import List, Optional
from models import Document, Session, Message, Page, DocumentStatus, MessageRole, Citation
import json

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


# --- Database Operations ---

def get_db_session() -> SQLSession:
    """Get a database session for operations."""
    return SQLSession(get_engine())


# --- Document Operations ---

def create_document(doc: Document) -> int:
    """Create a new document record and return its ID."""
    with get_db_session() as session:
        stmt = insert("documents").values(
            name=doc.name,
            bytes=doc.bytes,
            pages=doc.pages,
            sha256=doc.sha256,
            status=doc.status
        ).returning(text("id"))
        result = session.execute(stmt)
        doc_id = result.scalar()
        session.commit()
        return doc_id


def get_document(doc_id: int) -> Optional[Document]:
    """Get a document by ID."""
    with get_db_session() as session:
        stmt = select(
            text("id, name, bytes, pages, sha256, status, created_at")
        ).select_from(text("documents")).where(text("id = :doc_id"))
        
        result = session.execute(stmt, {"doc_id": doc_id}).fetchone()
        if result:
            return Document(
                id=result.id,
                name=result.name,
                bytes=result.bytes,
                pages=result.pages,
                sha256=result.sha256,
                status=result.status,
                created_at=result.created_at
            )
        return None


def update_document_status(doc_id: int, status: DocumentStatus) -> None:
    """Update document processing status."""
    with get_db_session() as session:
        stmt = update(text("documents")).where(
            text("id = :doc_id")
        ).values(status=status)
        session.execute(stmt, {"doc_id": doc_id})
        session.commit()


def list_documents() -> List[Document]:
    """List all documents."""
    with get_db_session() as session:
        stmt = select(
            text("id, name, bytes, pages, sha256, status, created_at")
        ).select_from(text("documents")).order_by(text("created_at DESC"))
        
        results = session.execute(stmt).fetchall()
        return [
            Document(
                id=row.id,
                name=row.name,
                bytes=row.bytes,
                pages=row.pages,
                sha256=row.sha256,
                status=row.status,
                created_at=row.created_at
            )
            for row in results
        ]


def delete_document(doc_id: int) -> None:
    """Delete a document and its associated pages."""
    with get_db_session() as session:
        # Delete pages first (foreign key constraint)
        session.execute(
            delete(text("pages")).where(text("doc_id = :doc_id")),
            {"doc_id": doc_id}
        )
        # Delete document
        session.execute(
            delete(text("documents")).where(text("id = :doc_id")),
            {"doc_id": doc_id}
        )
        session.commit()


# --- Page Operations ---

def create_page(page: Page) -> int:
    """Create a new page record and return its ID."""
    with get_db_session() as session:
        stmt = insert("pages").values(
            doc_id=page.doc_id,
            page_no=page.page_no,
            text=page.text
        ).returning(text("id"))
        result = session.execute(stmt)
        page_id = result.scalar()
        session.commit()
        return page_id


def get_pages_for_document(doc_id: int) -> List[Page]:
    """Get all pages for a document."""
    with get_db_session() as session:
        stmt = select(
            text("id, doc_id, page_no, text")
        ).select_from(text("pages")).where(
            text("doc_id = :doc_id")
        ).order_by(text("page_no"))
        
        results = session.execute(stmt, {"doc_id": doc_id}).fetchall()
        return [
            Page(
                id=row.id,
                doc_id=row.doc_id,
                page_no=row.page_no,
                text=row.text
            )
            for row in results
        ]


def search_pages(query: str, limit: int = 10) -> List[tuple[Page, float]]:
    """Search pages by text content (simple LIKE search)."""
    with get_db_session() as session:
        stmt = select(
            text("id, doc_id, page_no, text")
        ).select_from(text("pages")).where(
            text("text LIKE :query")
        ).limit(limit)
        
        results = session.execute(stmt, {"query": f"%{query}%"}).fetchall()
        # Return pages with a dummy score of 1.0 (will be replaced by vector search)
        return [
            (Page(
                id=row.id,
                doc_id=row.doc_id,
                page_no=row.page_no,
                text=row.text
            ), 1.0)
            for row in results
        ]


# --- Session Operations ---

def create_session(session: Session) -> int:
    """Create a new session and return its ID."""
    with get_db_session() as db_session:
        stmt = insert("sessions").values(title=session.title).returning(text("id"))
        result = db_session.execute(stmt)
        session_id = result.scalar()
        db_session.commit()
        return session_id


def get_session(session_id: int) -> Optional[Session]:
    """Get a session by ID."""
    with get_db_session() as session:
        stmt = select(
            text("id, title, created_at")
        ).select_from(text("sessions")).where(text("id = :session_id"))
        
        result = session.execute(stmt, {"session_id": session_id}).fetchone()
        if result:
            return Session(
                id=result.id,
                title=result.title,
                created_at=result.created_at
            )
        return None


def list_sessions() -> List[Session]:
    """List all sessions."""
    with get_db_session() as session:
        stmt = select(
            text("id, title, created_at")
        ).select_from(text("sessions")).order_by(text("created_at DESC"))
        
        results = session.execute(stmt).fetchall()
        return [
            Session(
                id=row.id,
                title=row.title,
                created_at=row.created_at
            )
            for row in results
        ]


def delete_session(session_id: int) -> None:
    """Delete a session and its messages."""
    with get_db_session() as session:
        # Delete messages first (foreign key constraint)
        session.execute(
            delete(text("messages")).where(text("session_id = :session_id")),
            {"session_id": session_id}
        )
        # Delete session
        session.execute(
            delete(text("sessions")).where(text("id = :session_id")),
            {"session_id": session_id}
        )
        session.commit()


# --- Message Operations ---

def create_message(message: Message) -> int:
    """Create a new message and return its ID."""
    with get_db_session() as session:
        # Serialize citations to JSON
        citations_json = None
        if message.citations:
            citations_json = json.dumps([c.dict() for c in message.citations])
        
        stmt = insert("messages").values(
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            citations=citations_json
        ).returning(text("id"))
        result = session.execute(stmt)
        message_id = result.scalar()
        session.commit()
        return message_id


def get_messages_for_session(session_id: int) -> List[Message]:
    """Get all messages for a session."""
    with get_db_session() as session:
        stmt = select(
            text("id, session_id, role, content, citations, created_at")
        ).select_from(text("messages")).where(
            text("session_id = :session_id")
        ).order_by(text("created_at ASC"))
        
        results = session.execute(stmt, {"session_id": session_id}).fetchall()
        messages = []
        
        for row in results:
            # Parse citations from JSON
            citations = None
            if row.citations:
                try:
                    citations_data = json.loads(row.citations)
                    citations = [Citation(**c) for c in citations_data]
                except (json.JSONDecodeError, ValueError):
                    citations = None
            
            messages.append(Message(
                id=row.id,
                session_id=row.session_id,
                role=row.role,
                content=row.content,
                citations=citations,
                created_at=row.created_at
            ))
        
        return messages


def get_message_count_for_session(session_id: int) -> int:
    """Get the number of messages in a session."""
    with get_db_session() as session:
        stmt = select(text("COUNT(*)")).select_from(text("messages")).where(
            text("session_id = :session_id")
        )
        result = session.execute(stmt, {"session_id": session_id}).scalar()
        return result or 0


def delete_message(message_id: int) -> None:
    """Delete a message by ID."""
    with get_db_session() as session:
        session.execute(
            delete(text("messages")).where(text("id = :message_id")),
            {"message_id": message_id}
        )
        session.commit()
