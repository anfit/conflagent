"""Confluence client for working with Conflagent routes."""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional, Sequence

import requests
from flask import abort


class ConfluenceClient:
    """A thin wrapper around the Confluence REST API."""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------
    @property
    def root_page_id(self) -> str:
        return self._config["root_page_id"]

    @property
    def space_key(self) -> str:
        return self._config["space_key"]

    @property
    def base_url(self) -> str:
        return self._config["base_url"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def build_headers(self) -> Dict[str, str]:
        token = f"{self._config['email']}:{self._config['api_token']}"
        token_bytes = base64.b64encode(token.encode()).decode()
        return {
            "Authorization": f"Basic {token_bytes}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        url: str,
        *,
        expected_status: Sequence[int] = (200, 201),
        **kwargs: Any,
    ) -> requests.Response:
        response = requests.request(method, url, headers=self.build_headers(), **kwargs)
        if response.status_code not in expected_status:
            abort(response.status_code, response.text)
        return response

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_pages(self) -> List[str]:
        return self._list_pages_recursive(self.root_page_id)

    def _list_pages_recursive(self, parent_id: str, prefix: str = "") -> List[str]:
        url = f"{self.base_url}/rest/api/content/{parent_id}/child/page"
        response = self._request("get", url)
        results = response.json().get("results", [])

        paths: List[str] = []
        for page in results:
            title = page["title"]
            current_path = f"{prefix}/{title}" if prefix else title
            paths.append(current_path)
            paths.extend(self._list_pages_recursive(page["id"], current_path))
        return paths

    def get_page_by_title(self, title: str, parent_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/rest/api/content/{parent_id}/child/page"
        response = self._request("get", url)
        results = response.json().get("results", [])
        for page in results:
            if page["title"] == title:
                return page
        return None

    def resolve_or_create_path(self, path: str) -> str:
        parts = path.strip("/").split("/") if path else []
        current_parent_id = self.root_page_id
        for part in parts:
            existing = self.get_page_by_title(part, current_parent_id)
            if existing:
                current_parent_id = existing["id"]
                continue

            payload = {
                "type": "page",
                "title": part,
                "ancestors": [{"id": current_parent_id}],
                "space": {"key": self.space_key},
                "body": {"storage": {"value": "", "representation": "storage"}},
            }
            url = f"{self.base_url}/rest/api/content"
            response = self._request("post", url, json=payload)
            current_parent_id = response.json()["id"]
        return current_parent_id

    def get_page_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        parts = path.strip("/").split("/")
        current_parent_id = self.root_page_id
        page: Optional[Dict[str, Any]] = None
        for part in parts:
            page = self.get_page_by_title(part, current_parent_id)
            if not page:
                return None
            current_parent_id = page["id"]
        return page

    def get_page_body(self, page_id: str) -> str:
        url = f"{self.base_url}/rest/api/content/{page_id}?expand=body.storage"
        response = self._request("get", url)
        return response.json()["body"]["storage"]["value"]

    def create_or_update_page(self, path: str, body: str) -> Dict[str, Any]:
        parts = path.strip("/").split("/")
        parent_path = "/".join(parts[:-1])
        page_title = parts[-1]
        parent_id = (
            self.resolve_or_create_path(parent_path)
            if parent_path
            else self.root_page_id
        )
        existing = self.get_page_by_title(page_title, parent_id)
        if existing:
            return self.update_page(existing, body)

        payload = {
            "type": "page",
            "title": page_title,
            "ancestors": [{"id": parent_id}],
            "space": {"key": self.space_key},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        url = f"{self.base_url}/rest/api/content"
        response = self._request("post", url, json=payload)
        return {"message": "Page created", "id": response.json()["id"]}

    def update_page(self, page: Dict[str, Any], new_body: str) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/content/{page['id']}?expand=version"
        response = self._request("get", url)
        version = response.json()["version"]["number"] + 1

        payload = {
            "id": page["id"],
            "type": "page",
            "title": page["title"],
            "version": {"number": version},
            "body": {"storage": {"value": new_body, "representation": "storage"}},
        }
        url = f"{self.base_url}/rest/api/content/{page['id']}"
        self._request("put", url, json=payload)
        return {"message": "Page updated", "version": version}

    def rename_page(self, page: Dict[str, Any], new_title: str) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/content/{page['id']}?expand=version"
        response = self._request("get", url)
        version = response.json()["version"]["number"] + 1

        body = self.get_page_body(page["id"])

        payload = {
            "id": page["id"],
            "type": "page",
            "title": new_title,
            "version": {"number": version},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        url = f"{self.base_url}/rest/api/content/{page['id']}"
        self._request("put", url, json=payload)
        return {"message": "Page renamed", "version": version}

    def delete_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/content/{page['id']}"
        self._request("delete", url, expected_status=(204, 200))
        return {"message": "Page deleted"}

