"""HTTP authorization and persistence regression tests: isolated SQLite and fake RAG."""
import json
import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import User, AuthSession, Conversation, Message, ChatHistory
from app.auth import hash_password, token_digest, verify_password
from app.migrations import upgrade
from app.permissions import get_allowed_document_roles, can_upload_document, can_delete_document

class PermissionMatrixTests(unittest.TestCase):
    def test_role_matrix(self):
        for role, allowed in [("employee", ["employee"]), ("hr", ["employee", "hr"]),
                              ("admin", ["employee", "hr", "admin"])]:
            self.assertEqual(get_allowed_document_roles(role), allowed)
            for doc_role in ("employee", "hr", "admin"):
                expected = role != "employee" and doc_role in allowed
                self.assertEqual(can_upload_document(role, doc_role), expected)
                self.assertEqual(can_delete_document(role, doc_role), expected)

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([User(id=i, username=role, password=hash_password("password123"), role=role)
                        for i, role in enumerate(("employee", "hr", "admin"), 1)])
            db.commit()
        def db_override():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)
        self.headers = {}
        for role in ("employee", "hr", "admin"):
            response = self.client.post("/login", json={"username": role, "password": "password123"})
            self.assertEqual(response.status_code, 200)
            self.headers[role] = {"Authorization": "Bearer " + response.json()["access_token"]}
        self.lock_patch = patch("app.knowledge.knowledge_lock", lambda: nullcontext())
        self.doc_lock_patch = patch("app.documents.knowledge_lock", lambda: nullcontext())
        self.lock_patch.start()
        self.doc_lock_patch.start()

    def tearDown(self):
        self.lock_patch.stop()
        self.doc_lock_patch.stop()
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def conversation(self, role="employee"):
        response = self.client.post("/conversations", json={"title": "test"}, headers=self.headers[role])
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_all_sensitive_endpoints_require_bearer(self):
        calls = [("get", "/users/me", {}), ("get", "/users", {}), ("get", "/history", {}),
                 ("get", "/admin/history", {}), ("get", "/documents?user_id=3", {}),
                 ("get", "/conversations", {}), ("get", "/conversations/1/messages", {}),
                 ("post", "/conversations", {"json": {"title": "forged"}}),
                 ("post", "/chat", {"json": {"question": "x", "conversation_id": 1}}),
                 ("put", "/users/1/role", {"json": {"role": "admin"}}),
                 ("delete", "/documents/private.pdf?user_id=3", {}),
                 ("get", "/documents/private.pdf/content", {}),
                 ("get", "/documents/private.pdf/download", {}),
                 ("post", "/documents", {"files": {"file": ("x.txt", b"hello")}})]
        for method, url, args in calls:
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, method)(url, **args).status_code, 401)

    def test_register_hashes_and_does_not_allow_role_or_identity(self):
        self.assertEqual(self.client.post("/register", json={"username": "x", "password": "password123", "role": "admin"}).status_code, 422)
        response = self.client.post("/register", json={"username": "new", "password": "password123"})
        self.assertEqual(response.status_code, 201)
        with self.factory() as db:
            user = db.get(User, response.json()["user_id"])
            self.assertEqual(user.role, "employee")
            self.assertNotEqual(user.password, "password123")
            self.assertTrue(verify_password("password123", user.password))
        self.assertEqual(self.client.post("/register", json={"username": "new", "password": "password123"}).status_code, 409)
        self.assertEqual(self.client.post("/login", json={"username": "employee", "password": "wrong"}).status_code, 401)
        self.assertEqual(self.client.post("/conversations", json={"user_id": 3}, headers=self.headers["employee"]).status_code, 422)

    def test_expiry_logout_and_role_revocation(self):
        headers = self.headers["employee"]
        self.assertEqual(self.client.post("/logout", headers=headers).status_code, 204)
        self.assertEqual(self.client.get("/users/me", headers=headers).status_code, 401)
        with self.factory() as db:
            token = self.headers["hr"]["Authorization"].split()[1]
            db.get(AuthSession, token_digest(token)).expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get("/users/me", headers=self.headers["hr"]).status_code, 401)

    def test_admin_users_and_role_update(self):
        self.assertEqual(self.client.get("/users", headers=self.headers["employee"]).status_code, 403)
        users = self.client.get("/users", headers=self.headers["admin"]).json()
        self.assertEqual(users["total"], 3)
        self.assertNotIn("password", users["items"][0])
        self.assertEqual(self.client.put("/users/1/role", json={"role": "admin"}, headers=self.headers["hr"]).status_code, 403)
        self.assertEqual(self.client.put("/users/1/role", json={"role": "admin", "operator_user_id": 3}, headers=self.headers["employee"]).status_code, 403)
        self.assertEqual(self.client.put("/users/1/role", json={"role": "hr"}, headers=self.headers["admin"]).status_code, 200)
        self.assertEqual(self.client.get("/users/me", headers=self.headers["employee"]).status_code, 401)
        self.assertEqual(self.client.put("/users/3/role", json={"role": "employee"}, headers=self.headers["admin"]).status_code, 409)

    def test_ownership_messages_chat_rename_delete(self):
        cid = self.conversation()
        for method, url, args in [
            ("get", f"/conversations/{cid}/messages", {}),
            ("patch", f"/conversations/{cid}", {"json": {"title": "other"}}),
            ("delete", f"/conversations/{cid}", {}),
            ("post", "/chat", {"json": {"question": "x", "conversation_id": cid}}),
        ]:
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(url, headers=self.headers["hr"], **args).status_code, 404)
        self.assertEqual(self.client.get("/conversations", headers=self.headers["hr"]).json(), [])
        self.assertEqual(self.client.patch(f"/conversations/{cid}", json={"title": "renamed"}, headers=self.headers["employee"]).status_code, 200)
        self.assertEqual(self.client.delete(f"/conversations/{cid}", headers=self.headers["employee"]).status_code, 204)

    def test_chat_atomic_history_single_source_and_error_rollback(self):
        cid = self.conversation()
        payload = {"question": "hello", "conversation_id": cid}
        with patch("app.knowledge.answer_question", side_effect=RuntimeError("offline")):
            self.assertEqual(self.client.post("/chat", json=payload, headers=self.headers["employee"]).status_code, 503)
        with self.factory() as db:
            self.assertEqual(db.query(Message).count(), 0)
        result = {"answer": "answer", "sources": [], "retrieval_results": [], "timings": {"total_ms": 1}}
        with patch("app.knowledge.answer_question", return_value=result) as answer:
            self.assertEqual(self.client.post("/chat", json=payload, headers=self.headers["employee"]).status_code, 200)
            self.assertEqual(answer.call_args.args[1:3], ("company", "employee"))
        with self.factory() as db:
            self.assertEqual(db.query(Message).count(), 2)
            self.assertEqual(db.query(ChatHistory).count(), 0)
        history = self.client.get("/history", headers=self.headers["employee"]).json()
        self.assertEqual(history[0]["question"], "hello")
        self.assertIsInstance(history[0]["sources"], list)
        self.assertEqual(self.client.get("/history", headers=self.headers["hr"]).json(), [])
        self.assertEqual(self.client.get("/admin/history", headers=self.headers["hr"]).status_code, 403)
        self.assertEqual(len(self.client.get("/admin/history", headers=self.headers["admin"]).json()), 1)
        self.client.delete(f"/conversations/{cid}", headers=self.headers["employee"])
        self.assertEqual(self.client.get("/history", headers=self.headers["employee"]).json(), [])

    def test_documents_are_filtered_and_employee_cannot_upload_delete(self):
        chunks = [{"id": str(i), "source": role + ".txt", "role": role, "text": role}
                  for i, role in enumerate(("employee", "hr", "admin"))]
        with patch("app.documents.read_chunks", return_value=chunks):
            docs = self.client.get("/documents", headers=self.headers["employee"]).json()
            self.assertEqual([x["filename"] for x in docs], ["employee.txt"])
        self.assertEqual(self.client.post("/documents", headers=self.headers["employee"],
                         files={"file": ("x.txt", b"hello")}).status_code, 403)
        with patch("app.knowledge.read_chunks", return_value=chunks):
            self.assertEqual(self.client.get("/documents/admin.txt/content", headers=self.headers["employee"]).status_code, 404)
            self.assertEqual(self.client.delete("/documents/employee.txt", headers=self.headers["employee"]).status_code, 403)
            self.assertEqual(self.client.get("/documents/employee.txt/content", headers=self.headers["employee"]).json()["chunks"][0]["text"], "employee")

    def test_revoked_session_during_generation_cannot_save_or_return_answer(self):
        cid = self.conversation()
        def revoke(*args):
            with self.factory() as db:
                db.query(AuthSession).filter_by(user_id=1).delete()
                db.commit()
            return {"answer": "must not be returned", "sources": [], "timings": {"total_ms": 1}}
        with patch("app.knowledge.answer_question", side_effect=revoke):
            response = self.client.post("/chat", json={"question": "hello", "conversation_id": cid},
                                        headers=self.headers["employee"])
        self.assertEqual(response.status_code, 401)
        with self.factory() as db:
            self.assertEqual(db.query(Message).count(), 0)

    def test_openapi_declares_bearer_for_every_protected_operation(self):
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"], "bearer")
        for path, operations in schema["paths"].items():
            if path in ("/", "/login", "/register"):
                continue
            for operation in operations.values():
                self.assertIn({"HTTPBearer": []}, operation["security"])

class MigrationTests(unittest.TestCase):
    def test_legacy_import_hashing_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.db"
            engine = create_engine("sqlite:///" + path.as_posix())
            Base.metadata.create_all(engine)
            with sessionmaker(bind=engine)() as db:
                db.add(User(id=1, username="old", password="legacy", role="user"))
                db.flush()
                db.add(Conversation(id=1, user_id=1, title="old"))
                db.flush()
                db.add_all([Message(conversation_id=1, role="user", content="q"),
                            Message(conversation_id=1, role="assistant", content="a"),
                            ChatHistory(user_id=1, session_id="1", question="q", answer="a"),
                            ChatHistory(user_id=1, session_id="old-session", question="q2", answer="a2")])
                db.commit()
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE conversations DROP COLUMN knowledge_base"))
            upgrade(engine)
            upgrade(engine)
            with sessionmaker(bind=engine)() as db:
                self.assertEqual(db.query(Message).count(), 4)
                self.assertEqual(db.query(ChatHistory).count(), 2)
                self.assertEqual(db.get(User, 1).role, "employee")
                self.assertTrue(verify_password("legacy", db.get(User, 1).password))
                self.assertEqual(db.get(Conversation, 1).knowledge_base, "paper")
            self.assertEqual(len(list((Path(directory) / "backups").glob("*.sqlite3"))), 1)
            engine.dispose()

if __name__ == "__main__":
    unittest.main()
