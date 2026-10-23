import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session
from app.database import Base
from app.migrations import upgrade, VERSION
from app.models import Migration, User, Conversation, Message


class AgentMigrationTests(unittest.TestCase):
    def test_existing_v1_database_gets_additive_column_and_backup_once(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = create_engine('sqlite:///' + (Path(folder) / 'app.db').as_posix())
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                db.add(User(id=1, username='old', password='not-used', role='employee'))
                db.flush()
                db.add(Conversation(id=1, user_id=1, title='existing'))
                db.flush()
                db.add(Message(id=1, conversation_id=1, role='assistant', content='preserve me', sources='[]'))
                db.add(Migration(name=VERSION))
                db.commit()
            with engine.begin() as connection:
                connection.execute(text('ALTER TABLE messages DROP COLUMN agent_metadata'))
            upgrade(engine)
            upgrade(engine)
            self.assertIn('agent_metadata', {x['name'] for x in inspect(engine).get_columns('messages')})
            with Session(engine) as db:
                self.assertEqual(db.get(Message, 1).content, 'preserve me')
                self.assertIsNone(db.get(Message, 1).agent_metadata)
            self.assertEqual(len(list((Path(folder) / 'backups').glob('*.sqlite3'))), 1)
            engine.dispose()
