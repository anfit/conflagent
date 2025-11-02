"""Utilities for serving the OpenAPI schema."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict

from flask import abort


def generate_openapi_spec(endpoint_name: str, host_url: str, template_path: str = "openapi.json") -> Dict[str, Any]:
    """Generate a customised OpenAPI specification for an endpoint."""

    try:
        with open(template_path, "r", encoding="utf-8") as file_handle:
            template = json.load(file_handle)
    except Exception as exc:  # pragma: no cover - bubbled via abort
        abort(500, description=f"Failed to load OpenAPI template: {exc}")

    spec = copy.deepcopy(template)
    spec["servers"] = [
        {
            "url": f"{host_url.rstrip('/')}/endpoint/{endpoint_name}",
            "description": "Endpoint-specific API",
        }
    ]
    return spec

