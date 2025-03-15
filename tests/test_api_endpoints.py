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

headers = {"X-GPT-Secret": "testsecret"}

@patch("conflagent.CONFIG", {"gpt_shared_secret": "testsecret", "root_page_id": "root", "space_key": "SPACE", "base_url": "http://example.com", "email": "a", "api_token": "b"})
@patch("conflagent.list_pages_recursive")
def test_list_pages(mock_list_pages, client):
    mock_list_pages.return_value = ["Path1/PageA", "Path2/PageB"]
    response = client.get("/pages", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == ["Path1/PageA", "Path2/PageB"]

@patch("conflagent.CONFIG", {"gpt_shared_secret": "testsecret", "root_page_id": "root", "space_key": "SPACE", "base_url": "http://example.com", "email": "a", "api_token": "b"})
@patch("conflagent.get_page_by_path")
@patch("conflagent.get_page_body")
def test_read_page(mock_get_body, mock_get_page, client):
    mock_get_page.return_value = {"id": "123"}
    mock_get_body.return_value = "Test content"
    response = client.get("/pages/some/page", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"title": "some/page", "body": "Test content"}

@patch("conflagent.CONFIG", {"gpt_shared_secret": "testsecret", "root_page_id": "root", "space_key": "SPACE", "base_url": "http://example.com", "email": "a", "api_token": "b"})
@patch("conflagent.create_or_update_page")
def test_create_page(mock_create, client):
    mock_create.return_value = {"message": "Page created", "id": "456"}
    response = client.post("/pages", json={"title": "some/page", "body": "new content"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"message": "Page created", "id": "456"}

@patch("conflagent.CONFIG", {"gpt_shared_secret": "testsecret", "root_page_id": "root", "space_key": "SPACE", "base_url": "http://example.com", "email": "a", "api_token": "b"})
@patch("conflagent.get_page_by_path")
@patch("conflagent.update_page")
def test_update_page(mock_update, mock_get_page, client):
    mock_get_page.return_value = {"id": "789", "title": "some/page"}
    mock_update.return_value = {"message": "Page updated", "version": 2}
    response = client.put("/pages/some/page", json={"body": "updated content"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"message": "Page updated", "version": 2}

@patch("conflagent.CONFIG", {"gpt_shared_secret": "testsecret"})
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"