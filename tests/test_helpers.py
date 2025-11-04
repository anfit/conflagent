import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.exceptions import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from conflagent import app
from conflagent_core.confluence import ConfluenceClient


mock_config = {
    "gpt_shared_secret": "testsecret",
    "root_page_id": "root",
    "space_key": "SPACE",
    "base_url": "http://example.com",
    "email": "a",
    "api_token": "b",
}


def make_client() -> ConfluenceClient:
    return ConfluenceClient(mock_config)


def test_resolve_or_create_path():
    with app.test_request_context():
        client = make_client()
        with patch.object(ConfluenceClient, "get_page_by_title") as mock_get_title, patch.object(
            ConfluenceClient, "_request"
        ) as mock_request:
            mock_get_title.side_effect = [{"id": "123"}, None]
            post_response = MagicMock()
            post_response.json.return_value = {"id": "456"}
            mock_request.return_value = post_response

            result = client.resolve_or_create_path("Level1/Level2")

        assert result == "456"


def test_resolve_or_create_path_abort_on_failure():
    with app.test_request_context():
        client = make_client()
        failure = HTTPException("error")
        failure.code = 500
        with patch.object(ConfluenceClient, "get_page_by_title", return_value=None), patch.object(
            ConfluenceClient, "_request", side_effect=failure
        ):
            with pytest.raises(HTTPException) as exc:
                client.resolve_or_create_path("NewPage")

        assert getattr(exc.value, "code", None) == 500


def test_update_page():
    with app.test_request_context():
        client = make_client()
        get_response = MagicMock()
        get_response.json.return_value = {"version": {"number": 1}}
        put_response = MagicMock()
        with patch.object(ConfluenceClient, "_request", side_effect=[get_response, put_response]):
            result = client.update_page({"id": "999", "title": "TestPage"}, "Updated body")

        assert result == {"version": 2}


def test_update_page_abort_on_failure():
    with app.test_request_context():
        client = make_client()
        failure = HTTPException("oops")
        failure.code = 500
        with patch.object(ConfluenceClient, "_request", side_effect=failure):
            with pytest.raises(HTTPException) as exc:
                client.update_page({"id": "1", "title": "Fail"}, "body")

        assert getattr(exc.value, "code", None) == 500


def test_get_page_by_title_found():
    with app.test_request_context():
        client = make_client()
        response = MagicMock()
        response.json.return_value = {
            "results": [
                {"title": "Other", "id": "1"},
                {"title": "Match", "id": "2"},
            ]
        }
        with patch.object(ConfluenceClient, "_request", return_value=response):
            page = client.get_page_by_title("Match", "root")

        assert page["id"] == "2"


def test_get_page_by_title_missing():
    with app.test_request_context():
        client = make_client()
        response = MagicMock()
        response.json.return_value = {"results": []}
        with patch.object(ConfluenceClient, "_request", return_value=response):
            page = client.get_page_by_title("Missing", "root")

        assert page is None


def test_list_pages_recursive():
    with app.test_request_context():
        client = make_client()

        def request_side_effect(method, url, **kwargs):
            response = MagicMock()
            if url.endswith("/root/child/page"):
                response.json.return_value = {"results": [{"title": "Level1", "id": "1"}]}
            elif url.endswith("/1/child/page"):
                response.json.return_value = {"results": [{"title": "Level2", "id": "2"}]}
            else:
                response.json.return_value = {"results": []}
            return response

        with patch.object(ConfluenceClient, "_request", side_effect=request_side_effect):
            paths = client._list_pages_recursive("root")

        assert paths == ["Level1", "Level1/Level2"]


def test_get_page_by_path_found():
    with app.test_request_context():
        client = make_client()
        with patch.object(
            ConfluenceClient,
            "get_page_by_title",
            side_effect=[{"id": "1"}, {"id": "2"}],
        ):
            page = client.get_page_by_path("Level1/Level2")

        assert page == {"id": "2"}


def test_get_page_by_path_missing():
    with app.test_request_context():
        client = make_client()
        with patch.object(
            ConfluenceClient,
            "get_page_by_title",
            side_effect=[{"id": "1"}, None],
        ):
            page = client.get_page_by_path("Level1/Level2")

        assert page is None


def test_get_page_body():
    with app.test_request_context():
        client = make_client()
        response = MagicMock()
        response.json.return_value = {"body": {"storage": {"value": "<p>Body</p>"}}}
        with patch.object(ConfluenceClient, "_request", return_value=response):
            body = client.get_page_body("123")

        assert body == "<p>Body</p>"


def test_create_or_update_page_updates_existing():
    with app.test_request_context():
        client = make_client()
        existing_page = {"id": "1", "title": "Page"}
        with patch.object(ConfluenceClient, "resolve_or_create_path", return_value="parent"), patch.object(
            ConfluenceClient, "get_page_by_title", return_value=existing_page
        ), patch.object(ConfluenceClient, "update_page", return_value={"version": 2}) as mock_update:
            result = client.create_or_update_page("Parent/Page", "body")

        mock_update.assert_called_once_with(existing_page, "body")
        assert result == {"id": "1", "version": 2}


def test_create_or_update_page_creates_new():
    with app.test_request_context():
        client = make_client()
        post_response = MagicMock()
        post_response.json.return_value = {"id": "99"}
        with patch.object(ConfluenceClient, "resolve_or_create_path", return_value="parent"), patch.object(
            ConfluenceClient, "get_page_by_title", return_value=None
        ), patch.object(ConfluenceClient, "_request", return_value=post_response):
            result = client.create_or_update_page("Parent/NewPage", "body")

        assert result == {"id": "99", "version": 1}


def test_rename_page_success():
    with app.test_request_context():
        client = make_client()
        get_response = MagicMock()
        get_response.json.return_value = {"version": {"number": 1}}
        put_response = MagicMock()
        with patch.object(ConfluenceClient, "get_page_body", return_value="<p>Body</p>"), patch.object(
            ConfluenceClient, "_request", side_effect=[get_response, put_response]
        ):
            result = client.rename_page({"id": "1", "title": "Old"}, "New")

        assert result == {"old_title": "Old", "new_title": "New", "version": 2}


def test_rename_page_failure():
    with app.test_request_context():
        client = make_client()
        failure = HTTPException("error")
        failure.code = 500
        with patch.object(ConfluenceClient, "get_page_body", return_value=""), patch.object(
            ConfluenceClient, "_request", side_effect=failure
        ):
            with pytest.raises(HTTPException) as exc:
                client.rename_page({"id": "1", "title": "Old"}, "New")

        assert getattr(exc.value, "code", None) == 500

