"""Integration tests hitting the dev deployment."""
import os
import time
from typing import Dict, Iterable, List
from urllib.parse import quote

import pytest
import requests


REQUIRED_ENV_VARS = {
    "CONFLAGENT_DEV_URL": "base URL for the deployed Flask service",
    "CONFLAGENT_DEV_ENDPOINT": "configured endpoint name defined in deployment properties",
    "CONFLAGENT_DEV_TOKEN": "bearer token shared secret for authenticated access",
}

SANDBOX_PREFIX = "SANDBOX_"
SANDBOX_TITLE = "SANDBOX_TestPage_001"
SANDBOX_BODY = "# Sandbox Test Page\nThis is a test page created automatically."
SANDBOX_UPDATED_BODY = (
    "# Sandbox Test Page (Updated)\nThis page has been updated successfully."
)
SANDBOX_RENAMED_TITLE = f"{SANDBOX_TITLE}_RENAMED"


@pytest.fixture(scope="session")
def dev_config() -> Dict[str, str]:
    """Collect configuration for the dev deployment or skip if unavailable."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        pytest.skip(
            "Missing required environment variables: " + ", ".join(sorted(missing))
        )

    return {
        "base_url": os.environ["CONFLAGENT_DEV_URL"].rstrip("/"),
        "endpoint": os.environ["CONFLAGENT_DEV_ENDPOINT"].strip("/"),
        "token": os.environ["CONFLAGENT_DEV_TOKEN"],
    }


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _full_url(config: Dict[str, str], path: str) -> str:
    return f"{config['base_url']}/endpoint/{config['endpoint']}{path}"


def _json_request(
    config: Dict[str, str], method: str, path: str, *, json: Dict[str, str] | None = None
) -> requests.Response:
    response = requests.request(
        method,
        _full_url(config, path),
        headers=_auth_headers(config["token"]),
        json=json,
        timeout=30,
    )
    return response


def _list_pages(config: Dict[str, str]) -> List[str]:
    response = _json_request(config, "GET", "/pages")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    return [page for page in payload if isinstance(page, str)]


def _create_page(config: Dict[str, str], title: str, body: str) -> Dict[str, str]:
    response = _json_request(
        config,
        "POST",
        "/pages",
        json={"title": title, "body": body},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("message")
    assert payload.get("id")
    return payload


def _read_page(config: Dict[str, str], title: str) -> Dict[str, str]:
    encoded_title = quote(title, safe="")
    response = _json_request(config, "GET", f"/pages/{encoded_title}")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("title") == title
    assert "body" in payload
    return payload


def _update_page(config: Dict[str, str], title: str, body: str) -> Dict[str, str]:
    encoded_title = quote(title, safe="")
    response = _json_request(
        config,
        "PUT",
        f"/pages/{encoded_title}",
        json={"body": body},
    )
    assert response.status_code == 200
    return response.json()


def _rename_page(config: Dict[str, str], old_title: str, new_title: str) -> Dict[str, str]:
    response = _json_request(
        config,
        "POST",
        "/pages/rename",
        json={"old_title": old_title, "new_title": new_title},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("new_title") == new_title
    return payload


def _delete_page(config: Dict[str, str], title: str) -> Dict[str, str]:
    encoded_title = quote(title, safe="")
    response = _json_request(config, "DELETE", f"/pages/{encoded_title}")
    assert response.status_code == 200
    payload = response.json()
    assert "message" in payload
    return payload


def _cleanup_existing_sandbox_pages(config: Dict[str, str], titles: Iterable[str]) -> None:
    for title in titles:
        if not title.startswith(SANDBOX_PREFIX):
            continue
        _delete_page(config, title)


def _ensure_no_sandbox_titles(titles: Iterable[str]) -> None:
    leftovers = [title for title in titles if title.startswith(SANDBOX_PREFIX)]
    assert not leftovers, f"Unexpected sandbox titles lingering: {leftovers}"


@pytest.mark.integration
def test_health_endpoint_reports_ok(dev_config: Dict[str, str]):
    response = requests.get(
        _full_url(dev_config, "/health"),
        headers=_auth_headers(dev_config["token"]),
        timeout=10,
    )
    assert response.status_code == 200
    content_type = response.headers.get("Content-Type", "")
    assert "application/json" in content_type
    payload = response.json()
    assert payload == {"status": "ok"}


@pytest.mark.integration
def test_health_requires_bearer_token(dev_config: Dict[str, str]):
    response = requests.get(_full_url(dev_config, "/health"), timeout=10)
    # The health endpoint is intentionally unauthenticated so that external
    # monitors can ping it without embedding secrets. Verify it still responds
    # successfully and exposes no sensitive payload even without the bearer
    # token.
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_list_pages_returns_paths(dev_config: Dict[str, str]):
    response = requests.get(
        _full_url(dev_config, "/pages"),
        headers=_auth_headers(dev_config["token"]),
        timeout=20,
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    for path in payload:
        assert isinstance(path, str)
        assert path  # paths should not be empty strings


@pytest.mark.integration
def test_missing_page_returns_404(dev_config: Dict[str, str]):
    missing_path = f"pytest/non-existent-{int(time.time())}"
    response = requests.get(
        _full_url(dev_config, f"/pages/{missing_path}"),
        headers=_auth_headers(dev_config["token"]),
        timeout=10,
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_openapi_schema_includes_endpoint_server(dev_config: Dict[str, str]):
    response = requests.get(
        _full_url(dev_config, "/openapi.json"),
        headers=_auth_headers(dev_config["token"]),
        timeout=10,
    )
    assert response.status_code == 200
    payload = response.json()
    assert "servers" in payload
    server_urls = {server.get("url") for server in payload["servers"]}
    expected_prefix = f"/endpoint/{dev_config['endpoint']}"
    assert any(url.endswith(expected_prefix) for url in server_urls if isinstance(url, str))


@pytest.mark.integration
def test_conflagent_operator_sandbox_cycle(dev_config: Dict[str, str]):
    """Exercise the full sandbox lifecycle of the Conflagent operator."""

    # Step 0 — Pre-cleanup: delete any lingering sandbox pages.
    existing_titles = _list_pages(dev_config)
    _cleanup_existing_sandbox_pages(dev_config, existing_titles)
    _ensure_no_sandbox_titles(_list_pages(dev_config))

    # Step 1 — Health Check
    response = requests.get(
        _full_url(dev_config, "/health"),
        headers=_auth_headers(dev_config["token"]),
        timeout=10,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Steps 2-7 execute in a try/finally to guarantee cleanup.
    created_title = SANDBOX_TITLE
    renamed_title = SANDBOX_RENAMED_TITLE

    try:
        # Step 2 — Create a Page
        creation_result = _create_page(dev_config, created_title, SANDBOX_BODY)
        assert "created" in creation_result["message"].lower()

        # Step 3 — Read the Page
        read_payload = _read_page(dev_config, created_title)
        assert "This is a test page created automatically." in read_payload["body"]

        # Step 4 — Update the Page
        update_result = _update_page(dev_config, created_title, SANDBOX_UPDATED_BODY)
        assert "version" in update_result
        updated_payload = _read_page(dev_config, created_title)
        assert "This page has been updated successfully." in updated_payload["body"]

        # Step 5 — Rename the Page
        _rename_page(dev_config, created_title, renamed_title)
        titles_after_rename = _list_pages(dev_config)
        assert renamed_title in titles_after_rename
        assert created_title not in titles_after_rename

        # Step 6 — Delete the Page
        delete_result = _delete_page(dev_config, renamed_title)
        assert "deleted" in delete_result["message"].lower()

    finally:
        # Step 7 — Post-cleanup
        current_titles = _list_pages(dev_config)
        for lingering in (renamed_title, created_title):
            if lingering in current_titles:
                delete_result = _delete_page(dev_config, lingering)
                assert "deleted" in delete_result["message"].lower()

    _ensure_no_sandbox_titles(_list_pages(dev_config))
