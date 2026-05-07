"""
Database Module
================
SQLite database setup using aiosqlite for user management and chat history.
"""
import aiosqlite
import logging
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path(settings.DATABASE_PATH)


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    """Initialize database tables."""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT 'Yeni Sohbet',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
        """)
        await db.commit()
        logger.info("Database initialized successfully at %s", DB_PATH)
    finally:
        await db.close()


# ── User Operations ──────────────────────────────────────────────────────────

async def upsert_user(user_id: str, email: str, name: str | None = None, image: str | None = None) -> dict:
    """Create or update a user record."""
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO users (id, email, name, image)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                image = excluded.image
            """,
            (user_id, email, name, image),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {}
    finally:
        await db.close()


# ── Conversation Operations ──────────────────────────────────────────────────

async def create_conversation(user_id: str, title: str = "Yeni Sohbet") -> dict:
    """Create a new conversation."""
    conv_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, user_id, title, now, now),
        )
        await db.commit()
        return {"id": conv_id, "user_id": user_id, "title": title, "created_at": now, "updated_at": now}
    finally:
        await db.close()


async def get_conversations(user_id: str) -> list[dict]:
    """Get all conversations for a user, most recent first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_conversation(conversation_id: str, user_id: str) -> dict | None:
    """Get a single conversation if it belongs to the user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_conversation_title(conversation_id: str, title: str) -> None:
    """Update conversation title."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, datetime.utcnow().isoformat(), conversation_id),
        )
        await db.commit()
    finally:
        await db.close()


async def touch_conversation(conversation_id: str) -> None:
    """Update the updated_at timestamp."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), conversation_id),
        )
        await db.commit()
    finally:
        await db.close()


async def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """Delete a conversation if it belongs to the user. Returns True if deleted."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ── Message Operations ───────────────────────────────────────────────────────

async def add_message(conversation_id: str, role: str, content: str) -> dict:
    """Add a message to a conversation."""
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, now),
        )
        # Also update conversation's updated_at
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await db.commit()
        return {"id": msg_id, "conversation_id": conversation_id, "role": role, "content": content, "created_at": now}
    finally:
        await db.close()


async def get_messages(conversation_id: str) -> list[dict]:
    """Get all messages for a conversation, ordered chronologically."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
