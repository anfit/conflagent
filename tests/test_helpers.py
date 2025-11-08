import os
import sys
from unittest.mock import MagicMock, call, patch

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


def test_get_page_by_path_single_title_descendant():
    with app.test_request_context():
        client = make_client()
        page_payload = {
            "id": "123",
            "title": "Anywhere",
            "ancestors": [{"id": mock_config["root_page_id"]}],
        }
        with patch.object(
            ConfluenceClient,
            "_search_pages_by_title",
            return_value=[page_payload],
        ) as mock_search:
            page = client.get_page_by_path("Anywhere")

        mock_search.assert_called_once_with("Anywhere", expand="ancestors")
        assert page == page_payload


def test_get_page_by_path_single_title_outside_root():
    with app.test_request_context():
        client = make_client()
        page_payload = {
            "id": "123",
            "title": "OtherSpace",
            "ancestors": [{"id": "not-root"}],
        }
        with patch.object(
            ConfluenceClient,
            "_search_pages_by_title",
            return_value=[page_payload],
        ):
            page = client.get_page_by_path("OtherSpace")

        assert page is None


def test_search_page_by_title_prefers_descendant():
    with app.test_request_context():
        client = make_client()
        response = MagicMock()
        response.json.return_value = {
            "results": [
                {"id": "1", "title": "Example", "ancestors": [{"id": "not-root"}]},
                {
                    "id": "2",
                    "title": "Example",
                    "ancestors": [{"id": mock_config["root_page_id"]}],
                },
            ]
        }
        with patch.object(ConfluenceClient, "_request", return_value=response):
            page = client._search_page_by_title("Example", descendants_only=True)

        assert page == {
            "id": "2",
            "title": "Example",
            "ancestors": [{"id": mock_config["root_page_id"]}],
        }


def test_search_page_by_title_descendant_missing():
    with app.test_request_context():
        client = make_client()
        response = MagicMock()
        response.json.return_value = {
            "results": [
                {"id": "1", "title": "Example", "ancestors": [{"id": "other"}]}
            ]
        }
        with patch.object(ConfluenceClient, "_request", return_value=response):
            page = client._search_page_by_title("Example", descendants_only=True)

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
        ), patch.object(ConfluenceClient, "_request", return_value=post_response) as mock_request:
            result = client.create_or_update_page("Parent/NewPage", "body")

        assert result == {"id": "99", "version": 1}
        called_kwargs = mock_request.call_args.kwargs
        assert called_kwargs["json"]["body"]["storage"]["value"].startswith("<p>")


def test_create_page_defaults_to_root_parent():
    with app.test_request_context():
        client = make_client()
        post_response = MagicMock()
        post_response.json.return_value = {"id": "42", "version": {"number": 3}}
        with patch.object(ConfluenceClient, "_request", return_value=post_response) as mock_request:
            result = client.create_page("Title", "body", None)

        assert result == {"id": "42", "title": "Title", "version": 3}
        called_args, called_kwargs = mock_request.call_args
        assert called_args[0] == "post"
        assert "rest/api/content" in called_args[1]
        assert called_kwargs["json"]["ancestors"] == [{"id": mock_config["root_page_id"]}]
        assert called_kwargs["json"]["body"]["storage"]["value"].startswith("<p>")


def test_create_page_with_parent_title():
    with app.test_request_context():
        client = make_client()
        parent_page = {"id": "parent", "title": "Parent"}
        post_response = MagicMock()
        post_response.json.return_value = {"id": "77", "version": {"number": 5}}
        with patch.object(
            ConfluenceClient, "_ensure_page_by_title", return_value=parent_page
        ) as mock_lookup, patch.object(ConfluenceClient, "_request", return_value=post_response) as mock_request:
            result = client.create_page("Child", "body", "Parent")

        mock_lookup.assert_called_once_with("Parent")
        called_args, called_kwargs = mock_request.call_args
        assert called_kwargs["json"]["ancestors"] == [{"id": "parent"}]
        assert called_kwargs["json"]["body"]["storage"]["value"].startswith("<p>")
        assert result == {"id": "77", "title": "Child", "version": 5}


def test_get_page_children_returns_minimal_payload():
    with app.test_request_context():
        client = make_client()
        page_info = {"id": "root", "title": "Parent", "ancestors": [{"title": "Root"}]}
        child_results = [
            {"id": "1", "title": "Child"},
            {"id": "2", "title": "Sibling"},
        ]
        with patch.object(
            ConfluenceClient, "_ensure_page_by_title", return_value=page_info
        ) as mock_lookup, patch.object(
            ConfluenceClient, "_fetch_children", return_value=child_results
        ) as mock_fetch:
            children = client.get_page_children("Parent")

        mock_lookup.assert_called_once_with("Parent")
        mock_fetch.assert_called_once_with("root")
        assert children == [
            {"title": "Child", "path": ["Root", "Parent", "Child"]},
            {"title": "Sibling", "path": ["Root", "Parent", "Sibling"]},
        ]


def test_get_page_parent_returns_path():
    with app.test_request_context():
        client = make_client()
        page_info = {
            "id": "child",
            "title": "Child",
            "ancestors": [
                {"title": "Root"},
                {"title": "Parent"},
            ],
        }
        with patch.object(ConfluenceClient, "_ensure_page_by_title", return_value=page_info) as mock_lookup:
            parent = client.get_page_parent("Child")

        mock_lookup.assert_called_once_with("Child")
        assert parent == {
            "title": "Parent",
            "path": ["Root", "Parent", "Child"],
        }


def test_get_page_parent_root_returns_none():
    with app.test_request_context():
        client = make_client()
        page_info = {"id": "root", "title": "Root", "ancestors": []}
        with patch.object(ConfluenceClient, "_ensure_page_by_title", return_value=page_info):
            parent = client.get_page_parent("Root")

        assert parent is None


def test_get_page_tree_respects_depth():
    with app.test_request_context():
        client = make_client()
        root_page = {"id": "root", "title": "Root", "ancestors": []}
        with patch.object(
            ConfluenceClient, "_get_page", return_value=root_page
        ) as mock_get_page, patch.object(
            ConfluenceClient, "_fetch_children", return_value=[{"id": "child", "title": "Child"}]
        ) as mock_children:
            tree = client.get_page_tree(depth=1)

        mock_get_page.assert_called_once_with(client.root_page_id, expand="ancestors")
        mock_children.assert_called_once_with("root")
        assert tree == {
            "title": "Root",
            "path": ["Root"],
            "children": [
                {"title": "Child", "path": ["Root", "Child"], "children": []}
            ],
        }


def test_get_page_tree_zero_depth_skips_children():
    with app.test_request_context():
        client = make_client()
        root_page = {"id": "root", "title": "Root", "ancestors": []}
        with patch.object(
            ConfluenceClient, "_get_page", return_value=root_page
        ) as mock_get_page, patch.object(
            ConfluenceClient, "_fetch_children"
        ) as mock_children:
            tree = client.get_page_tree(depth=0)

        mock_get_page.assert_called_once_with(client.root_page_id, expand="ancestors")
        mock_children.assert_not_called()
        assert tree == {"title": "Root", "path": ["Root"], "children": []}


def test_move_page_success():
    with app.test_request_context():
        client = make_client()
        page_lookup = [
            {
                "id": "child",
                "title": "Child",
                "version": {"number": 1},
                "ancestors": [
                    {"id": "root", "title": "Root"},
                    {"id": "old", "title": "Old"},
                ],
            },
            {
                "id": "parent",
                "title": "New",
                "ancestors": [{"id": "root", "title": "Root"}],
            },
        ]
        page_details = {
            "id": "child",
            "title": "Child",
            "ancestors": [
                {"id": "root", "title": "Root"},
                {"id": "old", "title": "Old"},
            ],
            "version": {"number": 1},
        }
        parent_details = {
            "id": "parent",
            "title": "New",
            "ancestors": [{"id": "root", "title": "Root"}],
        }
        with patch.object(
            ConfluenceClient,
            "_ensure_page_by_title",
            side_effect=page_lookup,
        ) as mock_lookup, patch.object(
            ConfluenceClient,
            "_get_page",
            side_effect=[page_details, parent_details],
        ) as mock_get_page, patch.object(ConfluenceClient, "_request") as mock_request:
            result = client.move_page("Child", "New")

        assert mock_lookup.call_args_list == [
            call("Child", expand="version"),
            call("New"),
        ]
        assert mock_get_page.call_args_list == [
            call("child", expand="ancestors,version"),
            call("parent", expand="ancestors"),
        ]
        mock_request.assert_called_with(
            "put",
            f"{mock_config['base_url']}/rest/api/content/child",
            json={
                "id": "child",
                "type": "page",
                "title": "Child",
                "version": {"number": 2},
                "ancestors": [{"id": "parent"}],
            },
        )
        assert result == {
            "title": "Child",
            "old_parent_title": "Old",
            "new_parent_title": "New",
        }


def test_move_page_prevents_circular_dependency():
    with app.test_request_context():
        client = make_client()
        page_lookup = [
            {
                "id": "child",
                "title": "Child",
                "version": {"number": 1},
                "ancestors": [{"id": "root", "title": "Root"}],
            },
            {
                "id": "parent",
                "title": "Parent",
                "ancestors": [
                    {"id": "root", "title": "Root"},
                    {"id": "child", "title": "Child"},
                ],
            },
        ]
        page_details = {
            "id": "child",
            "title": "Child",
            "ancestors": [{"id": "root", "title": "Root"}],
            "version": {"number": 1},
        }
        parent_details = {
            "id": "parent",
            "title": "Parent",
            "ancestors": [
                {"id": "root", "title": "Root"},
                {"id": "child", "title": "Child"},
            ],
        }
        with patch.object(
            ConfluenceClient,
            "_ensure_page_by_title",
            side_effect=page_lookup,
        ), patch.object(
            ConfluenceClient,
            "_get_page",
            side_effect=[page_details, parent_details],
        ):
            with pytest.raises(HTTPException) as exc:
                client.move_page("Child", "Parent")

        assert exc.value.code == 422


def test_move_page_rejects_page_outside_root():
    with app.test_request_context():
        client = make_client()
        page_lookup = {"id": "child", "title": "Child", "version": {"number": 1}}
        page_details = {
            "id": "child",
            "title": "Child",
            "ancestors": [{"id": "other", "title": "Other"}],
            "version": {"number": 1},
        }
        with patch.object(
            ConfluenceClient, "_ensure_page_by_title", return_value=page_lookup
        ), patch.object(ConfluenceClient, "_get_page", return_value=page_details):
            with pytest.raises(HTTPException) as exc:
                client.move_page("Child", "New")

        assert exc.value.code == 404


def test_move_page_rejects_new_parent_outside_root():
    with app.test_request_context():
        client = make_client()
        page_lookup = [
            {
                "id": "child",
                "title": "Child",
                "version": {"number": 1},
                "ancestors": [{"id": "root", "title": "Root"}],
            },
            {"id": "parent", "title": "Parent", "ancestors": []},
        ]
        page_details = {
            "id": "child",
            "title": "Child",
            "ancestors": [{"id": "root", "title": "Root"}],
            "version": {"number": 1},
        }
        parent_details = {
            "id": "parent",
            "title": "Parent",
            "ancestors": [{"id": "other", "title": "Other"}],
        }
        with patch.object(
            ConfluenceClient,
            "_ensure_page_by_title",
            side_effect=page_lookup,
        ), patch.object(
            ConfluenceClient,
            "_get_page",
            side_effect=[page_details, parent_details],
        ):
            with pytest.raises(HTTPException) as exc:
                client.move_page("Child", "Parent")

        assert exc.value.code == 404


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

