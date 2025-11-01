import pytest
import sys
import os
from flask import g
from unittest.mock import patch, MagicMock
from werkzeug.exceptions import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from conflagent import (
    resolve_or_create_path,
    update_page,
    get_page_by_title,
    list_pages_recursive,
    get_page_by_path,
    get_page_body,
    create_or_update_page,
    rename_page,
    app,
)

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
@patch("conflagent.requests.post")
@patch("conflagent.requests.get")
def test_resolve_or_create_path_abort_on_failure(mock_get, mock_post, mock_headers):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"results": []}
        mock_get.return_value = mock_get_response

        mock_post_response = MagicMock()
        mock_post_response.status_code = 500
        mock_post_response.text = "error"
        mock_post.return_value = mock_post_response

        with pytest.raises(HTTPException) as exc:
            resolve_or_create_path("NewPage")
        assert getattr(exc.value, "code", None) == 500

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


@patch("conflagent.build_headers")
@patch("conflagent.requests.get")
@patch("conflagent.requests.put")
def test_update_page_abort_on_failure(mock_put, mock_get, mock_headers):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_get_response = MagicMock()
        mock_get_response.status_code = 500
        mock_get_response.text = "oops"
        mock_get.return_value = mock_get_response

        with pytest.raises(HTTPException) as exc:
            update_page({"id": "1", "title": "Fail"}, "body")
        assert getattr(exc.value, "code", None) == 500


@patch("conflagent.requests.get")
@patch("conflagent.build_headers")
def test_get_page_by_title_found(mock_headers, mock_get):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"title": "Other", "id": "1"},
                {"title": "Match", "id": "2"},
            ]
        }
        mock_get.return_value = mock_response

        page = get_page_by_title("Match", "root")
        assert page["id"] == "2"


@patch("conflagent.requests.get")
@patch("conflagent.build_headers")
def test_get_page_by_title_missing(mock_headers, mock_get):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        page = get_page_by_title("Missing", "root")
        assert page is None


@patch("conflagent.requests.get")
@patch("conflagent.build_headers")
def test_list_pages_recursive(mock_headers, mock_get):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        def mock_get_side_effect(url, headers):
            response = MagicMock()
            response.status_code = 200
            if url.endswith("/root/child/page"):
                response.json.return_value = {
                    "results": [
                        {"title": "Level1", "id": "1"},
                    ]
                }
            elif url.endswith("/1/child/page"):
                response.json.return_value = {
                    "results": [
                        {"title": "Level2", "id": "2"}
                    ]
                }
            else:
                response.json.return_value = {
                    "results": []
                }
            return response

        mock_get.side_effect = mock_get_side_effect

        paths = list_pages_recursive("root")
        assert paths == ["Level1", "Level1/Level2"]


@patch("conflagent.get_page_by_title")
def test_get_page_by_path_found(mock_get_title):
    with app.test_request_context():
        g.config = mock_config
        mock_get_title.side_effect = [
            {"id": "1"},
            {"id": "2"},
        ]

        page = get_page_by_path("Level1/Level2")
        assert page == {"id": "2"}


@patch("conflagent.get_page_by_title")
def test_get_page_by_path_missing(mock_get_title):
    with app.test_request_context():
        g.config = mock_config
        mock_get_title.side_effect = [{"id": "1"}, None]

        page = get_page_by_path("Level1/Level2")
        assert page is None


@patch("conflagent.requests.get")
@patch("conflagent.build_headers")
def test_get_page_body(mock_headers, mock_get):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"body": {"storage": {"value": "<p>Body</p>"}}}
        mock_get.return_value = mock_response

        body = get_page_body("123")
        assert body == "<p>Body</p>"


@patch("conflagent.update_page")
@patch("conflagent.get_page_by_title")
@patch("conflagent.resolve_or_create_path")
def test_create_or_update_page_updates_existing(mock_resolve, mock_get_title, mock_update):
    with app.test_request_context():
        g.config = mock_config
        mock_resolve.return_value = "parent"
        existing_page = {"id": "1", "title": "Page"}
        mock_get_title.return_value = existing_page
        mock_update.return_value = {"message": "Page updated"}

        result = create_or_update_page("Parent/Page", "body")

        mock_update.assert_called_once_with(existing_page, "body")
        assert result == {"message": "Page updated"}


@patch("conflagent.requests.post")
@patch("conflagent.build_headers")
@patch("conflagent.get_page_by_title")
@patch("conflagent.resolve_or_create_path")
def test_create_or_update_page_creates_new(mock_resolve, mock_get_title, mock_headers, mock_post):
    with app.test_request_context():
        g.config = mock_config
        mock_resolve.return_value = "parent"
        mock_get_title.return_value = None
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "99"}
        mock_post.return_value = mock_response

        result = create_or_update_page("Parent/NewPage", "body")
        assert result == {"message": "Page created", "id": "99"}


@patch("conflagent.requests.put")
@patch("conflagent.requests.get")
@patch("conflagent.build_headers")
@patch("conflagent.get_page_body")
def test_rename_page_success(mock_get_body, mock_headers, mock_get, mock_put):
    with app.test_request_context():
        g.config = mock_config
        mock_get_body.return_value = "<p>Body</p>"
        mock_headers.return_value = {"Authorization": "Basic dummy"}

        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"version": {"number": 1}}
        mock_get.return_value = mock_get_response

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_put.return_value = mock_put_response

        result = rename_page({"id": "1", "title": "Old"}, "New")
        assert result == {"message": "Page renamed", "version": 2}


@patch("conflagent.requests.get")
@patch("conflagent.build_headers")
@patch("conflagent.get_page_body")
def test_rename_page_failure(mock_get_body, mock_headers, mock_get):
    with app.test_request_context():
        g.config = mock_config
        mock_headers.return_value = {"Authorization": "Basic dummy"}
        mock_get_body.return_value = ""

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "error"
        mock_get.return_value = mock_response

        with pytest.raises(HTTPException) as exc:
            rename_page({"id": "1", "title": "Old"}, "New")
        assert getattr(exc.value, "code", None) == 500

