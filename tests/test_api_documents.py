
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.core.auth import authenticate_user


@pytest.fixture
def client():
    app.dependency_overrides[authenticate_user] = (
        lambda: "employee-001"
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(authenticate_user, None)


def make_database_mock():
    """Create mocked database connection and cursor objects."""
    connection = MagicMock()
    cursor = MagicMock()

    connection.__enter__.return_value = connection
    connection.__exit__.return_value = False

    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False

    return connection, cursor


def test_document_list_filters_by_authenticated_employee(client):
    connection, cursor = make_database_mock()

    created_at = datetime.now(timezone.utc)
    cursor.fetchall.return_value = [
        (10, "employee_a.txt", "indexed", created_at, 3),
    ]

    with patch(
        "app.api.main.psycopg.connect",
        return_value=connection,
    ):
        response = client.get("/api/v1/documents")

    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["documents"][0]["document_id"] == 10
    assert body["documents"][0]["filename"] == "employee_a.txt"

    executed_sql = cursor.execute.call_args.args[0]
    executed_params = cursor.execute.call_args.args[1]

    assert "dp.principal_id = %s" in executed_sql
    assert executed_params == ("employee-001",)


def test_employee_cannot_delete_document_without_permission(client):
    connection, cursor = make_database_mock()

    # No matching document permission exists for this employee.
    cursor.fetchone.return_value = None

    with patch(
        "app.api.main.psycopg.connect",
        return_value=connection,
    ):
        response = client.delete("/api/v1/documents/99")

    assert response.status_code == 404

    # The route must stop before deleting permissions or documents.
    assert cursor.execute.call_count == 1

    executed_sql = cursor.execute.call_args.args[0]
    executed_params = cursor.execute.call_args.args[1]

    assert "dp.principal_id = %s" in executed_sql
    assert executed_params == (99, "employee-001")


def test_removing_access_preserves_document_for_other_users(client):
    connection, cursor = make_database_mock()

    cursor.fetchone.side_effect = [
        ("shared_policy.txt",),  # Document is accessible.
        (1,),                     # One permission remains.
    ]

    with (
        patch(
            "app.api.main.psycopg.connect",
            return_value=connection,
        ),
        patch("app.api.main.log_audit_event") as audit_mock,
    ):
        response = client.delete("/api/v1/documents/42")

    assert response.status_code == 200

    body = response.json()
    assert body["document_id"] == 42
    assert body["access_removed"] is True
    assert body["document_deleted"] is False

    sql_statements = [
        call.args[0]
        for call in cursor.execute.call_args_list
    ]

    assert any(
        "DELETE FROM document_permissions" in sql
        for sql in sql_statements
    )

    assert not any(
        "DELETE FROM document_chunks" in sql
        for sql in sql_statements
    )

    assert not any(
        "DELETE FROM documents" in sql
        for sql in sql_statements
    )

    audit_mock.assert_called_once()


def test_document_deleted_when_no_permissions_remain(client):
    connection, cursor = make_database_mock()

    cursor.fetchone.side_effect = [
        ("private_policy.txt",),  # Document is accessible.
        (0,),                      # No permissions remain.
    ]

    with (
        patch(
            "app.api.main.psycopg.connect",
            return_value=connection,
        ),
        patch("app.api.main.log_audit_event"),
    ):
        response = client.delete("/api/v1/documents/51")

    assert response.status_code == 200

    body = response.json()
    assert body["access_removed"] is True
    assert body["document_deleted"] is True

    sql_statements = [
        call.args[0]
        for call in cursor.execute.call_args_list
    ]

    assert any(
        "DELETE FROM document_permissions" in sql
        for sql in sql_statements
    )

    assert any(
        "DELETE FROM document_chunks" in sql
        for sql in sql_statements
    )

    assert any(
        "DELETE FROM documents" in sql
        for sql in sql_statements
    )
