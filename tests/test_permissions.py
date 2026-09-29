"""RBAC regression tests that do not touch the real app.db or chroma_db."""

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import User
from app.permissions import (
    can_delete_document,
    can_upload_document,
    get_allowed_document_roles,
    get_retrieval_where,
    normalize_user_role,
)
from app.users import RoleUpdateRequest, register, update_user_role
# Import endpoints without connecting to the real knowledge base.
with patch('chromadb.PersistentClient'):
    from app.documents import delete_document, list_documents


class PermissionMatrixTests(unittest.TestCase):
    def test_document_access_matrix(self):
        expected = {
            "employee": {"employee"},
            "hr": {"employee", "hr"},
            "admin": {"employee", "hr", "admin"},
        }
        for user_role, allowed in expected.items():
            with self.subTest(user_role=user_role):
                self.assertEqual(set(get_allowed_document_roles(user_role)), allowed)

    def test_upload_matrix(self):
        expected = {
            "employee": set(),
            "hr": {"employee", "hr"},
            "admin": {"employee", "hr", "admin"},
        }
        for user_role, allowed in expected.items():
            for document_role in ("employee", "hr", "admin"):
                with self.subTest(user_role=user_role, document_role=document_role):
                    self.assertEqual(
                        can_upload_document(user_role, document_role),
                        document_role in allowed,
                    )

    def test_delete_matrix(self):
        expected = {
            "employee": set(),
            "hr": {"employee", "hr"},
            "admin": {"employee", "hr", "admin"},
        }
        for user_role, allowed in expected.items():
            for document_role in ("employee", "hr", "admin"):
                with self.subTest(user_role=user_role, document_role=document_role):
                    self.assertEqual(
                        can_delete_document(user_role, document_role),
                        document_role in allowed,
                    )

    def test_chroma_retrieval_filters(self):
        self.assertEqual(get_retrieval_where("employee"), {"role": "employee"})
        self.assertEqual(
            get_retrieval_where("hr"),
            {"role": {"$in": ["employee", "hr"]}},
        )
        self.assertIsNone(get_retrieval_where("admin"))

    def test_legacy_user_role_is_least_privilege(self):
        self.assertEqual(normalize_user_role("user"), "employee")


class DatabaseTestBase:
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)

        db = self.session_factory()
        db.add_all(
            [
                User(username="employee_user", password="pw", role="employee"),
                User(username="hr_user", password="pw", role="hr"),
                User(username="admin_user", password="pw", role="admin"),
            ]
        )
        db.commit()
        self.ids = {user.username: user.id for user in db.query(User).all()}
        db.close()


class UserApiSecurityTests(DatabaseTestBase, unittest.TestCase):

    def test_public_registration_ignores_admin_role(self):
        with patch("app.users.SessionLocal", self.session_factory):
            result = register(
                {"username": "forged_admin", "password": "pw", "role": "admin"}
            )

        db = self.session_factory()
        created = db.query(User).filter(User.id == result["user_id"]).one()
        self.assertEqual(created.role, "employee")
        db.close()

    def test_non_admin_cannot_change_role(self):
        request = RoleUpdateRequest(
            operator_user_id=self.ids["hr_user"],
            role="hr",
        )
        with patch("app.users.SessionLocal", self.session_factory):
            with self.assertRaises(HTTPException) as raised:
                update_user_role(self.ids["employee_user"], request)
        self.assertEqual(raised.exception.status_code, 403)

    def test_admin_can_promote_employee_to_hr(self):
        request = RoleUpdateRequest(
            operator_user_id=self.ids["admin_user"],
            role="hr",
        )
        with patch("app.users.SessionLocal", self.session_factory):
            result = update_user_role(self.ids["employee_user"], request)
        self.assertEqual(result["new_role"], "hr")

    def test_role_update_rejects_invalid_role(self):
        request = RoleUpdateRequest(
            operator_user_id=self.ids["admin_user"],
            role="superadmin",
        )
        with patch("app.users.SessionLocal", self.session_factory):
            with self.assertRaises(HTTPException) as raised:
                update_user_role(self.ids["employee_user"], request)
        self.assertEqual(raised.exception.status_code, 400)

    def test_admin_gets_not_found_for_missing_target(self):
        request = RoleUpdateRequest(
            operator_user_id=self.ids["admin_user"],
            role="hr",
        )
        with patch("app.users.SessionLocal", self.session_factory):
            with self.assertRaises(HTTPException) as raised:
                update_user_role(999999, request)
        self.assertEqual(raised.exception.status_code, 404)


class FakeDocumentCollection:
    def __init__(self, metadatas):
        self.metadatas = metadatas
        self.deleted = False

    def get(self, **kwargs):
        where = kwargs.get("where")
        if where:
            selected = [
                meta
                for meta in self.metadatas
                if meta.get("source") == where.get("source")
            ]
        else:
            selected = self.metadatas
        return {"metadatas": selected}

    def delete(self, **_kwargs):
        self.deleted = True


class DocumentEndpointTests(DatabaseTestBase, unittest.TestCase):
    def test_list_hides_inaccessible_documents_and_supports_legacy_metadata(self):
        fake_collection = FakeDocumentCollection(
            [
                {"source": "employee.pdf", "role": "employee"},
                {"source": "hr.pdf", "role": "hr"},
                {"source": "admin.pdf", "role": "admin"},
                {"source": "legacy.pdf"},
            ]
        )
        with (
            patch("app.documents.SessionLocal", self.session_factory),
            patch("app.documents.collection", fake_collection),
        ):
            employee_docs = list_documents(self.ids["employee_user"])
            hr_docs = list_documents(self.ids["hr_user"])
            admin_docs = list_documents(self.ids["admin_user"])

        self.assertEqual(
            {item["filename"] for item in employee_docs},
            {"employee.pdf", "legacy.pdf"},
        )
        self.assertEqual(
            {item["filename"] for item in hr_docs},
            {"employee.pdf", "hr.pdf", "legacy.pdf"},
        )
        self.assertEqual(
            {item["filename"] for item in admin_docs},
            {"employee.pdf", "hr.pdf", "admin.pdf", "legacy.pdf"},
        )

    def test_delete_checks_permission_before_mutation(self):
        cases = [
            ("employee_user", "employee", 403, False),
            ("hr_user", "admin", 403, False),
            ("hr_user", "employee", 200, True),
            ("hr_user", "hr", 200, True),
            ("admin_user", "admin", 200, True),
        ]
        for username, document_role, expected_status, should_delete in cases:
            fake_collection = FakeDocumentCollection(
                [{"source": "permission-test-nonexistent.pdf", "role": document_role}]
            )
            with (
                self.subTest(username=username, document_role=document_role),
                patch("app.documents.SessionLocal", self.session_factory),
                patch("app.documents.collection", fake_collection),
            ):
                try:
                    delete_document(
                        "permission-test-nonexistent.pdf",
                        self.ids[username],
                    )
                    actual_status = 200
                except HTTPException as error:
                    actual_status = error.status_code
                self.assertEqual(actual_status, expected_status)
                self.assertEqual(fake_collection.deleted, should_delete)

    def test_delete_missing_document_returns_not_found_without_mutation(self):
        fake_collection = FakeDocumentCollection([])
        with (
            patch("app.documents.SessionLocal", self.session_factory),
            patch("app.documents.collection", fake_collection),
            self.assertRaises(HTTPException) as raised,
        ):
            delete_document(
                "permission-test-nonexistent.pdf",
                self.ids["admin_user"],
            )
        self.assertEqual(raised.exception.status_code, 404)
        self.assertFalse(fake_collection.deleted)


if __name__ == "__main__":
    unittest.main()
