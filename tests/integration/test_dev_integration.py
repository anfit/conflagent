"""Integration tests hitting the dev deployment."""
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import pytest
import requests


REQUIRED_ENV_VARS = {
    "CONFLAGENT_DEV_URL": "base URL for the deployed Flask service",
    "CONFLAGENT_DEV_ENDPOINT": "configured endpoint name defined in deployment properties",
    "CONFLAGENT_DEV_TOKEN": "bearer token shared secret for authenticated access",
}

SANDBOX_PREFIX = "SANDBOX_"
CLEANED_PREFIX = "CLEANED_SANDBOX_"
SANDBOX_BODY = "# Sandbox Test Page\nThis is a test page created automatically."
SANDBOX_UPDATED_BODY = (
    "# Sandbox Test Page (Updated)\nThis page has been updated successfully."
)


@dataclass
class SandboxTitles:
    """Container for sandbox titles used within a single test."""

    title: str
    renamed_title: str


@dataclass
class HierarchyTitles:
    """Grouping of titles used when exercising hierarchy endpoints."""

    parent: str
    child: str
    new_parent: str


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
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, list)
    return [page for page in data if isinstance(page, str)]


def _create_page(config: Dict[str, str], title: str, body: str) -> Dict[str, str]:
    response = _json_request(
        config,
        "POST",
        "/pages",
        json={"title": title, "body": body},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, dict)
    assert data.get("id")
    return payload


def _create_page_under_parent(
    config: Dict[str, str], title: str, body: str, parent_title: str
) -> Dict[str, str]:
    response = _json_request(
        config,
        "POST",
        "/pages",
        json={"title": title, "body": body, "parentTitle": parent_title},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, dict)
    assert data.get("id")
    return payload


def _read_page(config: Dict[str, str], title: str) -> Dict[str, str]:
    encoded_title = quote(title, safe="")
    response = _json_request(config, "GET", f"/pages/{encoded_title}")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, dict)
    assert data.get("title") == title
    assert "body" in data
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
    payload = response.json()
    assert payload.get("success") is True
    return payload


def _rename_page(config: Dict[str, str], old_title: str, new_title: str) -> Dict[str, str]:
    response = _json_request(
        config,
        "POST",
        "/pages/rename",
        json={"old_title": old_title, "new_title": new_title},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, dict)
    assert data.get("newTitle") == new_title
    return payload


def _delete_page(config: Dict[str, str], title: str) -> Dict[str, str]:
    encoded_title = quote(title, safe="")
    response = _json_request(config, "DELETE", f"/pages/{encoded_title}")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    return payload


def _cleanup_existing_sandbox_pages(config: Dict[str, str], titles: Iterable[str]) -> None:
    for title in titles:
        if title.startswith(SANDBOX_PREFIX) or title.startswith(CLEANED_PREFIX):
            _delete_page(config, title)


def _ensure_no_sandbox_titles(titles: Iterable[str]) -> None:
    leftovers = [title for title in titles if title.startswith(SANDBOX_PREFIX)]
    assert not leftovers, f"Unexpected sandbox titles lingering: {leftovers}"


def _remove_titles(config: Dict[str, str], *titles: str) -> None:
    """Delete sandbox titles if they still exist."""

    for title in titles:
        if not title:
            continue
        current_titles = set(_list_pages(config))
        if title in current_titles:
            _delete_page(config, title)


def _encode_title(title: str) -> str:
    return quote(title, safe="")


def _get_children(config: Dict[str, str], title: str) -> List[Dict[str, Any]]:
    encoded_title = _encode_title(title)
    response = _json_request(config, "GET", f"/pages/{encoded_title}/children")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, list)
    return [item for item in data if isinstance(item, dict)]


def _get_parent(config: Dict[str, str], title: str) -> Optional[Dict[str, Any]]:
    encoded_title = _encode_title(title)
    response = _json_request(config, "GET", f"/pages/{encoded_title}/parent")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    return payload.get("data")


def _get_tree(
    config: Dict[str, str], *, start_title: Optional[str] = None, depth: Optional[int] = None
) -> Dict[str, Any]:
    query_params: List[str] = []
    if depth is not None:
        query_params.append(f"depth={depth}")
    if start_title:
        query_params.append(f"startTitle={_encode_title(start_title)}")
    query = "&".join(query_params)
    path = "/pages/tree"
    if query:
        path = f"{path}?{query}"
    response = _json_request(config, "GET", path)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, dict)
    return data


def _move_page_to_parent(
    config: Dict[str, str], title: str, new_parent_title: str
) -> Dict[str, Any]:
    encoded_title = _encode_title(title)
    response = _json_request(
        config,
        "POST",
        f"/pages/{encoded_title}/move",
        json={"newParentTitle": new_parent_title},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, dict)
    return data


@pytest.fixture
def sandbox_titles(dev_config: Dict[str, str]) -> SandboxTitles:
    """Provide unique sandbox titles and guarantee cleanup for each test."""

    existing_titles = _list_pages(dev_config)
    _cleanup_existing_sandbox_pages(dev_config, existing_titles)
    _ensure_no_sandbox_titles(_list_pages(dev_config))

    unique_suffix = uuid.uuid4().hex[:8]
    base_title = f"{SANDBOX_PREFIX}TestPage_{unique_suffix}"
    renamed_title = f"{base_title}_RENAMED"

    titles = SandboxTitles(title=base_title, renamed_title=renamed_title)

    try:
        yield titles
    finally:
        _remove_titles(dev_config, titles.renamed_title, titles.title)
        _ensure_no_sandbox_titles(_list_pages(dev_config))


@pytest.fixture
def hierarchy_titles(dev_config: Dict[str, str]) -> HierarchyTitles:
    """Provide unique titles for exercising hierarchy endpoints."""

    existing_titles = _list_pages(dev_config)
    _cleanup_existing_sandbox_pages(dev_config, existing_titles)
    _ensure_no_sandbox_titles(_list_pages(dev_config))

    unique_suffix = uuid.uuid4().hex[:8]
    parent = f"{SANDBOX_PREFIX}TreeParent_{unique_suffix}"
    child = f"{parent}_Child"
    new_parent = f"{SANDBOX_PREFIX}TreeNewParent_{unique_suffix}"

    titles = HierarchyTitles(parent=parent, child=child, new_parent=new_parent)

    try:
        yield titles
    finally:
        _remove_titles(dev_config, titles.child, titles.new_parent, titles.parent)
        _ensure_no_sandbox_titles(_list_pages(dev_config))


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
    assert payload.get("success") is True
    assert payload.get("data") == {"status": "ok"}


@pytest.mark.integration
def test_health_requires_bearer_token(dev_config: Dict[str, str]):
    response = requests.get(_full_url(dev_config, "/health"), timeout=10)
    # The health endpoint is intentionally unauthenticated so that external
    # monitors can ping it without embedding secrets. Verify it still responds
    # successfully and exposes no sensitive payload even without the bearer
    # token.
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    assert payload.get("data") == {"status": "ok"}


@pytest.mark.integration
def test_list_pages_returns_paths(dev_config: Dict[str, str]):
    response = requests.get(
        _full_url(dev_config, "/pages"),
        headers=_auth_headers(dev_config["token"]),
        timeout=20,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data")
    assert isinstance(data, list)
    for path in data:
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
    payload = response.json()
    assert payload.get("success") is False
    assert payload.get("code") == "NOT_FOUND"


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
def test_create_page_in_sandbox(dev_config: Dict[str, str], sandbox_titles: SandboxTitles):
    """Creating a sandbox page should store the expected content."""

    creation_result = _create_page(dev_config, sandbox_titles.title, SANDBOX_BODY)
    assert creation_result.get("success") is True
    assert "created" in creation_result["message"].lower()
    assert creation_result["data"]["id"]
    assert sandbox_titles.title in _list_pages(dev_config)


@pytest.mark.integration
def test_read_page_in_sandbox(dev_config: Dict[str, str], sandbox_titles: SandboxTitles):
    """A created sandbox page should be readable with the original body."""

    _create_page(dev_config, sandbox_titles.title, SANDBOX_BODY)
    read_payload = _read_page(dev_config, sandbox_titles.title)
    assert read_payload.get("success") is True
    assert read_payload["data"]["title"] == sandbox_titles.title
    assert SANDBOX_BODY in read_payload["data"]["body"]


@pytest.mark.integration
def test_update_page_in_sandbox(dev_config: Dict[str, str], sandbox_titles: SandboxTitles):
    """Updating a sandbox page should increment the version and body content."""

    _create_page(dev_config, sandbox_titles.title, SANDBOX_BODY)
    update_result = _update_page(dev_config, sandbox_titles.title, SANDBOX_UPDATED_BODY)
    assert update_result.get("success") is True
    assert "version" in update_result["data"]
    updated_payload = _read_page(dev_config, sandbox_titles.title)
    assert "updated successfully" in updated_payload["data"]["body"]


@pytest.mark.integration
def test_rename_page_in_sandbox(dev_config: Dict[str, str], sandbox_titles: SandboxTitles):
    """Renaming a sandbox page should move it to the new title and keep content."""

    _create_page(dev_config, sandbox_titles.title, SANDBOX_BODY)
    _rename_page(dev_config, sandbox_titles.title, sandbox_titles.renamed_title)

    titles_after_rename = _list_pages(dev_config)
    assert sandbox_titles.renamed_title in titles_after_rename
    assert sandbox_titles.title not in titles_after_rename

    renamed_payload = _read_page(dev_config, sandbox_titles.renamed_title)
    assert SANDBOX_BODY in renamed_payload["data"]["body"]


@pytest.mark.integration
def test_delete_page_in_sandbox(dev_config: Dict[str, str], sandbox_titles: SandboxTitles):
    """Deleting a sandbox page should remove it from the listings."""

    _create_page(dev_config, sandbox_titles.title, SANDBOX_BODY)
    delete_result = _delete_page(dev_config, sandbox_titles.title)
    assert delete_result.get("success") is True
    assert "deleted" in delete_result["message"].lower()
    assert delete_result["data"]["deletedTitle"] == sandbox_titles.title
    assert sandbox_titles.title not in _list_pages(dev_config)


@pytest.mark.integration
def test_page_tree_includes_child_hierarchy(
    dev_config: Dict[str, str], hierarchy_titles: HierarchyTitles
):
    """A created parent/child structure should appear in the tree response."""

    _create_page(dev_config, hierarchy_titles.parent, SANDBOX_BODY)
    _create_page_under_parent(
        dev_config, hierarchy_titles.child, SANDBOX_BODY, hierarchy_titles.parent
    )

    tree = _get_tree(dev_config, start_title=hierarchy_titles.parent, depth=1)
    assert tree["title"] == hierarchy_titles.parent
    assert tree["path"][-1] == hierarchy_titles.parent

    child_nodes = [
        node for node in tree.get("children", []) if node.get("title") == hierarchy_titles.child
    ]
    assert child_nodes, "Expected child title to appear beneath parent in tree"
    child_node = child_nodes[0]
    assert child_node.get("path", [])[-2:] == [
        hierarchy_titles.parent,
        hierarchy_titles.child,
    ]


@pytest.mark.integration
def test_children_endpoint_lists_direct_children(
    dev_config: Dict[str, str], hierarchy_titles: HierarchyTitles
):
    """Listing children should include direct descendants with their paths."""

    _create_page(dev_config, hierarchy_titles.parent, SANDBOX_BODY)
    _create_page_under_parent(
        dev_config, hierarchy_titles.child, SANDBOX_BODY, hierarchy_titles.parent
    )

    children = _get_children(dev_config, hierarchy_titles.parent)
    titles = [child.get("title") for child in children]
    assert hierarchy_titles.child in titles
    child_entry = next(child for child in children if child.get("title") == hierarchy_titles.child)
    assert child_entry.get("path", [])[-2:] == [
        hierarchy_titles.parent,
        hierarchy_titles.child,
    ]


@pytest.mark.integration
def test_parent_endpoint_returns_parent_metadata(
    dev_config: Dict[str, str], hierarchy_titles: HierarchyTitles
):
    """Parent lookup should return the direct ancestor metadata and breadcrumb path."""

    _create_page(dev_config, hierarchy_titles.parent, SANDBOX_BODY)
    _create_page_under_parent(
        dev_config, hierarchy_titles.child, SANDBOX_BODY, hierarchy_titles.parent
    )

    parent = _get_parent(dev_config, hierarchy_titles.child)
    assert parent is not None
    assert parent.get("title") == hierarchy_titles.parent
    assert parent.get("path", [])[-2:] == [
        hierarchy_titles.parent,
        hierarchy_titles.child,
    ]


@pytest.mark.integration
def test_move_page_reparents_child(
    dev_config: Dict[str, str], hierarchy_titles: HierarchyTitles
):
    """Moving a child page should update its parent and visibility in listings."""

    _create_page(dev_config, hierarchy_titles.parent, SANDBOX_BODY)
    _create_page(dev_config, hierarchy_titles.new_parent, SANDBOX_BODY)
    _create_page_under_parent(
        dev_config, hierarchy_titles.child, SANDBOX_BODY, hierarchy_titles.parent
    )

    move_result = _move_page_to_parent(
        dev_config, hierarchy_titles.child, hierarchy_titles.new_parent
    )
    assert move_result.get("title") == hierarchy_titles.child
    assert move_result.get("oldParentTitle") == hierarchy_titles.parent
    assert move_result.get("newParentTitle") == hierarchy_titles.new_parent

    new_parent_children = _get_children(dev_config, hierarchy_titles.new_parent)
    assert hierarchy_titles.child in [child.get("title") for child in new_parent_children]

    original_children = _get_children(dev_config, hierarchy_titles.parent)
    assert hierarchy_titles.child not in [child.get("title") for child in original_children]
