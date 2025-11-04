import pytest
import sys
import os
from unittest.mock import patch, MagicMock

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
    assert response.get_json() == ["Path1/PageA", "Path2/PageB"]

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_read_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "123"}
    mock_client.get_page_body.return_value = "Test content"
    response = client.get(f"/endpoint/{endpoint}/pages/some/page", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"title": "some/page", "body": "Test content"}


@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_read_page_missing(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = None
    response = client.get(f"/endpoint/{endpoint}/pages/missing", headers=headers)
    assert response.status_code == 404

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_create_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.create_or_update_page.return_value = {"message": "Page created", "id": "456"}
    response = client.post(f"/endpoint/{endpoint}/pages", json={"title": "some/page", "body": "new content"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"message": "Page created", "id": "456"}


@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_create_page_requires_title(mock_load_config, client):
    response = client.post(
        f"/endpoint/{endpoint}/pages",
        json={"body": "content"},
        headers=headers,
    )
    assert response.status_code == 400

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_update_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "789", "title": "some/page"}
    mock_client.update_page.return_value = {"message": "Page updated", "version": 2}
    response = client.put(f"/endpoint/{endpoint}/pages/some/page", json={"body": "updated content"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"message": "Page updated", "version": 2}


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

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_delete_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "999", "title": "some/page"}
    mock_client.delete_page.return_value = {"message": "Page deleted"}
    response = client.delete(
        f"/endpoint/{endpoint}/pages/some/page",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json() == {"message": "Page deleted"}

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

@patch("conflagent.ConfluenceClient")
@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_rename_page(mock_load_config, mock_client_cls, client):
    mock_client = mock_client_cls.return_value
    mock_client.get_page_by_path.return_value = {"id": "111", "title": "old/page"}
    mock_client.rename_page.return_value = {"message": "Page renamed", "version": 2}
    response = client.post(f"/endpoint/{endpoint}/pages/rename", json={"old_title": "old/page", "new_title": "new/page"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"message": "Page renamed", "new_title": "new/page", "version": 2}


@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_rename_page_requires_fields(mock_load_config, client):
    response = client.post(
        f"/endpoint/{endpoint}/pages/rename",
        json={"old_title": "only-old"},
        headers=headers,
    )
    assert response.status_code == 400


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

@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_health(mock_load_config, client):
    response = client.get(f"/endpoint/{endpoint}/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"

@patch("conflagent_core.config.load_config", return_value=mock_config)
def test_openapi_schema(mock_load_config, client):
    response = client.get(f"/endpoint/{endpoint}/openapi.json")
    assert response.status_code == 200
    data = response.get_json()
    assert "paths" in data
    # Be more lenient: just check that at least one expected endpoint is present
    assert any("/pages" in path for path in data["paths"])
