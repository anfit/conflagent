import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from conflagent import app


endpoint = "testendpoint"
headers = {"Authorization": "Bearer testsecret"}

mock_config = {
    "gpt_shared_secret": "testsecret",
    "root_page_id": "root",
    "space_key": "SPACE",
    "base_url": "http://example.com",
    "email": "a",
    "api_token": "b",
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@patch("conflagent_core.config.load_config", return_value=mock_config)
@patch("conflagent.ConfluenceClient._request")
def test_create_page_converts_markdown(mock_request, _mock_load_config, client):
    response = MagicMock()
    response.json.return_value = {"id": "123", "version": {"number": 1}}
    mock_request.return_value = response

    result = client.post(
        f"/endpoint/{endpoint}/pages",
        json={"title": "Markdown", "body": "# Heading"},
        headers=headers,
    )

    assert result.status_code == 200
    called_kwargs = mock_request.call_args.kwargs
    storage_value = called_kwargs["json"]["body"]["storage"]["value"]
    assert "<h1>Heading</h1>" in storage_value


@patch("conflagent_core.config.load_config", return_value=mock_config)
@patch("conflagent.ConfluenceClient.get_page_by_path", return_value={"id": "1", "title": "Markdown"})
@patch("conflagent.ConfluenceClient._request")
def test_update_page_converts_markdown(mock_request, _mock_get_page, _mock_load_config, client):
    get_response = MagicMock()
    get_response.json.return_value = {"version": {"number": 2}}
    put_response = MagicMock()
    put_response.json.return_value = {}
    mock_request.side_effect = [get_response, put_response]

    result = client.put(
        f"/endpoint/{endpoint}/pages/Markdown",
        json={"body": "*emphasis*"},
        headers=headers,
    )

    assert result.status_code == 200
    assert mock_request.call_count == 2
    called_kwargs = mock_request.call_args.kwargs
    storage_value = called_kwargs["json"]["body"]["storage"]["value"]
    assert "<em>emphasis</em>" in storage_value
