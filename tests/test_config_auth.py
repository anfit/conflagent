import sys
import os
import base64
from unittest.mock import patch, mock_open

import pytest
from flask import g
from werkzeug.exceptions import Forbidden, NotFound, InternalServerError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from conflagent import load_config, CONFIG_CACHE, check_auth, build_headers, app


def _valid_properties():
    return "\n".join(
        [
            "email=user@example.com",
            "api_token=token",
            "base_url=http://example.com",
            "space_key=SPACE",
            "root_page_id=root",
            "gpt_shared_secret=secret",
        ]
    )


@patch("conflagent.os.path.exists", return_value=True)
def test_load_config_parses_and_caches(mock_exists):
    CONFIG_CACHE.clear()
    properties = _valid_properties()
    with patch("builtins.open", mock_open(read_data=properties)) as mock_file:
        result = load_config("demo")
        assert result["email"] == "user@example.com"
        assert CONFIG_CACHE["demo"] is result
        mock_file.assert_called_once_with("../conflagent.demo.properties", "r")

        mock_file.reset_mock()
        cached = load_config("demo")
        assert cached is result
        mock_file.assert_not_called()


@patch("conflagent.os.path.exists", return_value=False)
def test_load_config_missing_file(mock_exists):
    CONFIG_CACHE.clear()
    with app.test_request_context("/"):
        with pytest.raises(NotFound):
            load_config("missing")


@patch("conflagent.os.path.exists", return_value=True)
def test_load_config_missing_key(mock_exists):
    CONFIG_CACHE.clear()
    with app.test_request_context("/"):
        with patch("builtins.open", mock_open(read_data="email=user")):
            with pytest.raises(InternalServerError):
                load_config("demo")


def test_check_auth_missing_header():
    with app.test_request_context("/"):
        g.config = {"gpt_shared_secret": "secret"}
        with pytest.raises(Forbidden):
            check_auth()


def test_check_auth_invalid_token():
    with app.test_request_context("/", headers={"Authorization": "Bearer wrong"}):
        g.config = {"gpt_shared_secret": "secret"}
        with pytest.raises(Forbidden):
            check_auth()


def test_check_auth_success():
    with app.test_request_context("/", headers={"Authorization": "Bearer secret"}):
        g.config = {"gpt_shared_secret": "secret"}
        assert check_auth() is None


def test_build_headers_base64():
    with app.test_request_context("/"):
        g.config = {"email": "user", "api_token": "token"}
        headers = build_headers()
    token = base64.b64encode(b"user:token").decode()
    assert headers["Authorization"] == f"Basic {token}"
    assert headers["Content-Type"] == "application/json"
