"""Idempotent local migration. Back up the SQLite file before upgrading it."""
import sqlite3
from contextlib import closing
from collections import Counter
from datetime import datetime
from pathlib import Path
from filelock import FileLock
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.database import Base
from app.models import User, Conversation, Message, ChatHistory, Migration
from app.auth import hash_password

VERSION = "2026_10_authenticated_chat_v1"

def upgrade(engine):
    database = engine.url.database
    if database and database != ":memory:":
        with FileLock(str(Path(database).parent / ".migration.lock"), timeout=120):
            return _upgrade(engine)
    return _upgrade(engine)

def _upgrade(engine):
    inspector = inspect(engine)
    existing = inspector.get_table_names()
    if "app_migrations" in existing:
        with Session(engine) as db:
            if db.get(Migration, VERSION):
                return
    database = engine.url.database
    if database and database != ":memory:" and Path(database).exists() and existing:
        backup_dir = Path(database).parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        target = backup_dir / ("app-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3")
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(target)) as backup:
            source.backup(backup)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        columns = {x["name"] for x in inspect(conn).get_columns("conversations")}
        if "knowledge_base" not in columns:
            # Existing conversations used the old paper pipeline.
            conn.execute(text("ALTER TABLE conversations ADD COLUMN knowledge_base VARCHAR(20) NOT NULL DEFAULT 'paper'"))
        # Existing SQLite tables cannot gain foreign keys via ALTER TABLE.
        # Equivalent triggers enforce ownership references without dropping any user data.
        for table, column, parent in (("conversations", "user_id", "users"),
                                      ("messages", "conversation_id", "conversations")):
            for operation in ("INSERT", "UPDATE"):
                conn.execute(text(f"""CREATE TRIGGER IF NOT EXISTS fk_{table}_{operation.lower()}
                    BEFORE {operation} ON {table}
                    WHEN NOT EXISTS (SELECT 1 FROM {parent} WHERE id=NEW.{column})
                    BEGIN SELECT RAISE(ABORT, 'invalid parent reference'); END"""))
        conn.execute(text("""CREATE TRIGGER IF NOT EXISTS cascade_conversation_messages
            AFTER DELETE ON conversations BEGIN DELETE FROM messages WHERE conversation_id=OLD.id; END"""))
        conn.execute(text("""CREATE TRIGGER IF NOT EXISTS cascade_user_conversations
            AFTER DELETE ON users BEGIN DELETE FROM conversations WHERE user_id=OLD.id; END"""))
    with Session(engine) as db:
        for user in db.query(User):
            if not user.password.startswith("scrypt$"):
                user.password = hash_password(user.password)
            if user.role == "user":
                user.role = "employee"
        db.flush()
        # Match existing completed turns with multiplicity; import only legacy-only turns.
        seen, pending = Counter(), {}
        owners = {x.id: x.user_id for x in db.query(Conversation)}
        for message in db.query(Message).order_by(Message.id):
            if message.role == "user":
                pending[message.conversation_id] = message.content
            elif message.role == "assistant" and message.conversation_id in pending:
                seen[(owners.get(message.conversation_id), str(message.conversation_id),
                      pending.pop(message.conversation_id), message.content)] += 1
        imported_conversations = {}
        for record in db.query(ChatHistory).order_by(ChatHistory.id):
            key = (record.user_id, record.session_id, record.question, record.answer)
            if seen[key]:
                seen[key] -= 1
                continue
            if not db.get(User, record.user_id):
                # Preserve orphaned legacy records in the original archive, never expose them.
                continue
            conv = db.get(Conversation, int(record.session_id)) if (record.session_id or "").isdigit() else None
            if not conv or conv.user_id != record.user_id:
                legacy_key = (record.user_id, record.session_id)
                conv = imported_conversations.get(legacy_key)
                if conv is None:
                    conv = Conversation(user_id=record.user_id, title=record.question[:42],
                                        knowledge_base="paper", created_time=record.created_time,
                                        updated_time=record.created_time)
                    db.add(conv)
                    db.flush()
                    imported_conversations[legacy_key] = conv
            db.add_all([Message(conversation_id=conv.id, role="user", content=record.question,
                                created_time=record.created_time),
                        Message(conversation_id=conv.id, role="assistant", content=record.answer,
                                sources=record.sources, created_time=record.created_time)])
        db.add(Migration(name=VERSION))
        db.commit()
