import pytest
import sys
import os
from flask import g
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from conflagent import resolve_or_create_path, update_page, app

mock_config = {
    "gpt_shared_secret": "testsecret",
    "root_page_id": "root",
    "space_key": "SPACE",
    "base_url": "http://example.com",
    "email": "a",
    "api_token": "b"
}

@patch("conflagent.get_page_by_title")
@patch("conflagent.build_headers")
@patch("conflagent.requests.post")
def test_resolve_or_create_path(mock_post, mock_headers, mock_get_title):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        def get_title_side_effect(title, parent_id):
            if title == "Level1":
                return {"id": "123"}
            return None
        mock_get_title.side_effect = get_title_side_effect

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "456"}
        mock_post.return_value = mock_response

        result = resolve_or_create_path("Level1/Level2")
        assert result == "456"

@patch("conflagent.build_headers")
@patch("conflagent.requests.put")
@patch("conflagent.requests.get")
def test_update_page(mock_get, mock_put, mock_headers):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"version": {"number": 1}}
        mock_get.return_value = mock_get_response

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_put.return_value = mock_put_response

        page = {"id": "999", "title": "TestPage"}
        result = update_page(page, "Updated body")
        assert result == {"message": "Page updated", "version": 2}