"""Integration tests hitting the dev deployment."""
import os
import time
from typing import Dict

import pytest
import requests


REQUIRED_ENV_VARS = {
    "CONFLAGENT_DEV_URL": "base URL for the deployed Flask service",
    "CONFLAGENT_DEV_ENDPOINT": "configured endpoint name defined in deployment properties",
    "CONFLAGENT_DEV_TOKEN": "bearer token shared secret for authenticated access",
}


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
    assert response.status_code == 403


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
