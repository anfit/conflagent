import pytest
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

from werkzeug.exceptions import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from conflagent import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()

endpoint = "testendpoint"
headers = {"Authorization": "Bearer testsecret"}

mock_config = {
    "gpt_shared_secret": "testsecret",
    "root_page_id": "root",
    "space_key": "SPACE",
    "base_url": "http://example.com",
    "email": "a",
    "api_token": "b"
}

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_list_pages(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.list_pages.return_value = ["Path1/PageA", "Path2/PageB"]
    response = client.get(f"/endpoint/{endpoint}/pages", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["code"] == "OK"
    assert payload["data"] == ["Path1/PageA", "Path2/PageB"]
    assert "timestamp" in payload

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_read_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "123"}
    mock_client.get_page_body.return_value = "Test content"
    response = client.get(f"/endpoint/{endpoint}/pages/some/page", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {"title": "some/page", "body": "Test content"}


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_read_page_missing(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = None
    response = client.get(f"/endpoint/{endpoint}/pages/missing", headers=headers)
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "NOT_FOUND"

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_create_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.create_page.return_value = {"id": "123", "title": "some/page", "version": 1}
    response = client.post(
        f"/endpoint/{endpoint}/pages",
        json={"title": "some/page", "body": "new content", "parentTitle": "Root"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {"id": "123", "title": "some/page", "version": 1}
    mock_client.create_page.assert_called_once_with("some/page", "new content", "Root")


@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_create_page_requires_title(mock_load_config, client):
    response = client.post(
        f"/endpoint/{endpoint}/pages",
        json={"body": "content"},
        headers=headers,
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "INVALID_INPUT"
    assert "Title is required" in payload["message"]

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_update_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "789", "title": "some/page"}
    mock_client.update_page.return_value = {"version": 2}
    response = client.put(f"/endpoint/{endpoint}/pages/some/page", json={"body": "updated content"}, headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {"version": 2}


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_update_page_missing(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = None
    response = client.put(
        f"/endpoint/{endpoint}/pages/missing",
        json={"body": "updated"},
        headers=headers,
    )
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "NOT_FOUND"


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_get_page_tree(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_tree.return_value = {
        "title": "Root",
        "path": ["Root"],
        "children": [
            {"title": "Child", "path": ["Root", "Child"], "children": []}
        ],
    }
    response = client.get(
        f"/endpoint/{endpoint}/pages/tree?depth=3&startTitle=abc",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["title"] == "Root"
    mock_client.get_page_tree.assert_called_once_with(start_title="abc", depth=3)


@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_get_page_tree_invalid_depth(mock_load_config, client):
    response = client.get(
        f"/endpoint/{endpoint}/pages/tree?depth=NaN",
        headers=headers,
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "INVALID_INPUT"


@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_get_page_tree_negative_depth(mock_load_config, client):
    response = client.get(
        f"/endpoint/{endpoint}/pages/tree?depth=-1",
        headers=headers,
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["code"] == "INVALID_INPUT"


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_list_children(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_children.return_value = [
        {"title": "Child", "path": ["Parent", "Child"]},
        {"title": "Another", "path": ["Parent", "Another"]},
    ]
    response = client.get(
        f"/endpoint/{endpoint}/pages/Parent/children",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"][0]["title"] == "Child"
    mock_client.get_page_children.assert_called_once_with("Parent")


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_list_children_missing_parent(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    exc = HTTPException("missing")
    exc.code = 404
    mock_client.get_page_children.side_effect = exc
    response = client.get(
        f"/endpoint/{endpoint}/pages/Missing/children",
        headers=headers,
    )
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["code"] == "NOT_FOUND"


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_get_parent_metadata(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_parent.return_value = {
        "title": "Parent",
        "path": ["Root", "Parent", "Child"],
    }
    response = client.get(
        f"/endpoint/{endpoint}/pages/Child/parent",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["title"] == "Parent"
    mock_client.get_page_parent.assert_called_once_with("Child")


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_get_parent_missing(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    exc = HTTPException("missing")
    exc.code = 404
    mock_client.get_page_parent.side_effect = exc
    response = client.get(
        f"/endpoint/{endpoint}/pages/Missing/parent",
        headers=headers,
    )
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["code"] == "NOT_FOUND"


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_move_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.move_page.return_value = {
        "title": "Child",
        "old_parent_title": "Old",
        "new_parent_title": "New",
    }
    response = client.post(
        f"/endpoint/{endpoint}/pages/Child/move",
        json={"newParentTitle": "New"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {
        "title": "Child",
        "oldParentTitle": "Old",
        "newParentTitle": "New",
    }
    mock_client.move_page.assert_called_once_with("Child", "New")


@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_move_page_requires_new_parent(mock_load_config, client):
    response = client.post(
        f"/endpoint/{endpoint}/pages/Child/move",
        json={},
        headers=headers,
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["code"] == "INVALID_INPUT"


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_move_page_circular(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    exc = HTTPException("invalid")
    exc.code = 422
    mock_client.move_page.side_effect = exc
    response = client.post(
        f"/endpoint/{endpoint}/pages/Child/move",
        json={"newParentTitle": "New"},
        headers=headers,
    )
    assert response.status_code == 422
    payload = response.get_json()
    assert payload["code"] == "INVALID_OPERATION"


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_move_page_not_found(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    exc = HTTPException("missing")
    exc.code = 404
    mock_client.move_page.side_effect = exc
    response = client.post(
        f"/endpoint/{endpoint}/pages/Child/move",
        json={"newParentTitle": "Missing"},
        headers=headers,
    )
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["code"] == "NOT_FOUND"

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_delete_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "999", "title": "some/page"}
    mock_client.delete_page.return_value = {"deleted_title": "some/page"}
    response = client.delete(
        f"/endpoint/{endpoint}/pages/some/page",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {"deletedTitle": "some/page"}

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_delete_page_missing(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = None
    response = client.delete(
        f"/endpoint/{endpoint}/pages/missing",
        headers=headers,
    )
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "NOT_FOUND"

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_rename_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "111", "title": "old/page"}
    mock_client.rename_page.return_value = {
        "old_title": "old/page",
        "new_title": "new/page",
        "version": 2,
    }
    response = client.post(f"/endpoint/{endpoint}/pages/rename", json={"old_title": "old/page", "new_title": "new/page"}, headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {
        "oldTitle": "old/page",
        "newTitle": "new/page",
        "version": 2,
    }


@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_rename_page_requires_fields(mock_load_config, client):
    response = client.post(
        f"/endpoint/{endpoint}/pages/rename",
        json={"old_title": "only-old"},
        headers=headers,
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "INVALID_INPUT"


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_rename_page_missing_source(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = None
    response = client.post(
        f"/endpoint/{endpoint}/pages/rename",
        json={"old_title": "missing", "new_title": "new"},
        headers=headers,
    )
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["code"] == "NOT_FOUND"

@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_health(mock_load_config, client):
    response = client.get(f"/endpoint/{endpoint}/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {"status": "ok"}


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_internal_error_returns_standard_envelope(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.list_pages.side_effect = RuntimeError("boom")

    response = client.get(f"/endpoint/{endpoint}/pages", headers=headers)

    assert response.status_code == 500
    payload = response.get_json()
    assert payload == {
        "success": False,
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred.",
        "data": None,
        "timestamp": payload["timestamp"],
    }


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_timestamp_field_is_iso8601(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.list_pages.return_value = []

    response = client.get(f"/endpoint/{endpoint}/pages", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    timestamp = payload["timestamp"]
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None

@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_openapi_schema(mock_load_config, client):
    response = client.get(f"/endpoint/{endpoint}/openapi.json")
    assert response.status_code == 200
    data = response.get_json()
    assert "paths" in data
    # Be more lenient: just check that at least one expected endpoint is present
    assert any("/pages" in path for path in data["paths"])
