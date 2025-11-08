"""Confluence client for working with Conflagent routes."""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

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

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        response = requests.request(method, url, headers=self.build_headers(), **kwargs)
        if response.status_code != 200:
            abort(response.status_code, response.text)
        return response

    def _search_pages_by_title(
        self,
        title: str,
        *,
        expand: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        expansions: List[str] = []
        if expand:
            expansions.extend([part for part in expand.split(",") if part])
        if "ancestors" not in expansions:
            expansions.append("ancestors")

        params: Dict[str, Any] = {"spaceKey": self.space_key, "title": title}
        if expansions:
            params["expand"] = ",".join(expansions)

        url = f"{self.base_url}/rest/api/content"
        response = self._request("get", url, params=params)
        return response.json().get("results", [])

    def _search_page_by_title(
        self,
        title: str,
        *,
        expand: Optional[str] = None,
        descendants_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        results = self._search_pages_by_title(title, expand=expand)
        if not results:
            return None

        if descendants_only:
            for page in results:
                if self._is_descendant_of_root(page):
                    return page
            return None

        return results[0]

    def _ensure_page_by_title(self, title: str, *, expand: Optional[str] = None) -> Dict[str, Any]:
        page = self._search_page_by_title(title, expand=expand, descendants_only=True)
        if not page:
            abort(404, description=f"Page titled '{title}' not found")
        return page

    def _is_descendant_of_root(self, page: Dict[str, Any]) -> bool:
        """Return True if the page resides under the configured root page."""

        if page.get("id") == self.root_page_id:
            return True

        return any(
            ancestor.get("id") == self.root_page_id
            for ancestor in page.get("ancestors", [])
        )

    def _fetch_children(self, page_id: str) -> List[Dict[str, str]]:
        url = f"{self.base_url}/rest/api/content/{page_id}/child/page"
        response = self._request("get", url)
        return [
            {"id": page["id"], "title": page["title"]}
            for page in response.json().get("results", [])
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_pages(self) -> List[str]:
        return self._list_pages_recursive(self.root_page_id)

    def _get_page(self, page_id: str, *, expand: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/content/{page_id}"
        params: Dict[str, Any] = {}
        if expand:
            params["expand"] = expand
        response = self._request("get", url, params=params)
        return response.json()

    def get_page_children(self, page_title: str) -> List[Dict[str, Any]]:
        page = self._ensure_page_by_title(page_title)
        path = [ancestor["title"] for ancestor in page.get("ancestors", [])] + [page["title"]]
        children = self._fetch_children(page["id"])
        return [
            {"title": child["title"], "path": path + [child["title"]]}
            for child in children
        ]

    def get_page_parent(self, page_title: str) -> Optional[Dict[str, Any]]:
        page = self._ensure_page_by_title(page_title)
        ancestors = page.get("ancestors", [])
        if not ancestors:
            return None
        parent = ancestors[-1]
        path = [ancestor["title"] for ancestor in ancestors] + [page["title"]]
        return {"title": parent["title"], "path": path}

    def get_page_tree(self, start_title: Optional[str] = None, depth: int = 2) -> Dict[str, Any]:
        if start_title:
            start_page = self._ensure_page_by_title(start_title)
        else:
            start_page = self._get_page(self.root_page_id, expand="ancestors")

        path = [ancestor["title"] for ancestor in start_page.get("ancestors", [])] + [
            start_page["title"]
        ]
        return self._build_tree_node(start_page["id"], start_page["title"], depth, path)

    def _build_tree_node(self, page_id: str, title: str, depth: int, path: List[str]) -> Dict[str, Any]:
        node = {"title": title, "path": path, "children": []}
        if depth <= 0:
            return node

        children = self._fetch_children(page_id)
        node["children"] = [
            self._build_tree_node(
                child["id"], child["title"], depth - 1, path + [child["title"]]
            )
            for child in children
        ]
        return node

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
        normalized = path.strip("/")
        if not normalized:
            return None

        parts = normalized.split("/")

        if len(parts) == 1:
            results = self._search_pages_by_title(parts[0], expand="ancestors")
            for page in results:
                if self._is_descendant_of_root(page):
                    return page
            return None

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
            updated = self.update_page(existing, body)
            updated["id"] = existing["id"]
            return updated

        payload = {
            "type": "page",
            "title": page_title,
            "ancestors": [{"id": parent_id}],
            "space": {"key": self.space_key},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        url = f"{self.base_url}/rest/api/content"
        response = self._request("post", url, json=payload)
        response_json = response.json()
        version_info = response_json.get("version", {})
        version_number = version_info.get("number")
        if version_number is None:
            version_number = 1
        return {
            "id": response_json["id"],
            "version": version_number,
        }

    def create_page(self, title: str, body: str, parent_title: Optional[str]) -> Dict[str, Any]:
        if parent_title:
            parent_page = self._ensure_page_by_title(parent_title)
            ancestor_id = parent_page["id"]
        else:
            ancestor_id = self.root_page_id
        payload = {
            "type": "page",
            "title": title,
            "ancestors": [{"id": ancestor_id}],
            "space": {"key": self.space_key},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        url = f"{self.base_url}/rest/api/content"
        response = self._request("post", url, json=payload)
        response_json = response.json()
        page_id = response_json.get("id")
        version_info = response_json.get("version", {})
        version_number = version_info.get("number", 1)
        return {"id": page_id, "title": title, "version": version_number}

    def move_page(self, page_title: str, new_parent_title: str) -> Dict[str, Any]:
        page = self._ensure_page_by_title(page_title, expand="version")
        page_id = page["id"]
        detailed_page = self._get_page(page_id, expand="ancestors,version")

        if not self._is_descendant_of_root(detailed_page):
            abort(404, description="Page not found")

        ancestors = detailed_page.get("ancestors", [])
        old_parent_title: Optional[str] = None
        if ancestors:
            old_parent_title = ancestors[-1]["title"]

        new_parent = self._ensure_page_by_title(new_parent_title)
        new_parent_id = new_parent["id"]
        new_parent_details = self._get_page(new_parent_id, expand="ancestors")

        if not self._is_descendant_of_root(new_parent_details):
            abort(404, description="New parent not found")
        new_parent_ancestors = [ancestor["id"] for ancestor in new_parent_details.get("ancestors", [])]
        ancestry_chain = new_parent_ancestors + [new_parent_id]
        if page_id in ancestry_chain:
            abort(422, description="Cannot move page into its own subtree")

        version_number = detailed_page["version"]["number"] + 1
        payload = {
            "id": page_id,
            "type": "page",
            "title": detailed_page["title"],
            "version": {"number": version_number},
            "ancestors": [{"id": new_parent_id}],
        }
        url = f"{self.base_url}/rest/api/content/{page_id}"
        self._request("put", url, json=payload)
        return {
            "title": detailed_page["title"],
            "old_parent_title": old_parent_title,
            "new_parent_title": new_parent_details["title"],
        }

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
        return {"version": version}

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
        return {"old_title": page["title"], "new_title": new_title, "version": version}

    def delete_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/content/{page['id']}"
        response = requests.request("delete", url, headers=self.build_headers())
        if response.status_code not in {200, 202, 204}:
            abort(response.status_code, response.text)
        return {"deleted_title": page["title"]}

