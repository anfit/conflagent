"""Tests for generated OpenAPI specification."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from conflagent import app
from conflagent_core.openapi import generate_openapi_spec


def test_generated_spec_matches_template():
    """The generated spec should match the checked-in template aside from server URL."""

    template_path = Path("openapi.json")
    template = json.loads(template_path.read_text(encoding="utf-8"))

    endpoint_name = "demo"
    host_url = "https://example.test/"
    generated = generate_openapi_spec(endpoint_name, host_url, app)

    expected = copy.deepcopy(template)
    expected["servers"] = [
        {
            "url": f"{host_url.rstrip('/')}/endpoint/{endpoint_name}",
            "description": "Endpoint-specific API",
        }
    ]

    assert generated == expected

