"""Tests for generated OpenAPI specification."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from flask import Flask

from conflagent import app
from conflagent_core import openapi as openapi_module


def build_test_app() -> Flask:
    """Create a minimal Flask app with documented routes for testing."""

    test_app = Flask(__name__)

    @test_app.route("/endpoint/<endpoint_name>/health", methods=["GET"])
    @openapi_module.document_operation("/health", "get")
    def health(_endpoint_name: str):
        return "ok"

    return test_app


def test_document_operation_attaches_deep_copied_metadata():
    """Decorated functions should expose isolated OpenAPI metadata copies."""

    @openapi_module.document_operation("/health", "get")
    def handler():
        return "ok"

    docs = handler.__openapi__  # type: ignore[attr-defined]
    assert docs == {"/health": {"get": openapi_module._PATH_DEFINITIONS["/health"]["get"]}}

    # Mutating the attached metadata must not affect the module-level definition.
    docs["/health"]["get"]["summary"] = "changed"
    assert (
        openapi_module._PATH_DEFINITIONS["/health"]["get"]["summary"]
        == "Health check"
    )


def test_document_operation_rejects_unknown_paths():
    """Referencing an unknown path/method combination should fail fast."""

    with pytest.raises(KeyError):

        @openapi_module.document_operation("/unknown", "get")
        def _unknown():
            return "ok"


def test_document_operation_rejects_duplicates():
    """Applying the same documentation twice should raise a clear error."""

    decorator = openapi_module.document_operation("/health", "get")

    with pytest.raises(ValueError):

        @decorator
        @decorator
        def _duplicate():
            return "ok"


def test_generate_openapi_spec_includes_documented_routes():
    """The runtime-generated spec should reflect documented Flask routes."""

    test_app = build_test_app()
    spec = openapi_module.generate_openapi_spec("demo", "https://example.test/", test_app)

    assert spec["paths"]["/health"]["get"] == openapi_module._PATH_DEFINITIONS["/health"][
        "get"
    ]
    assert spec["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    assert spec["servers"] == [
        {
            "url": "https://example.test/endpoint/demo",
            "description": "Endpoint-specific API",
        }
    ]


def test_generated_spec_matches_template():
    """The generated spec should match the checked-in template aside from server URL."""

    template_path = Path("openapi.json")
    template = json.loads(template_path.read_text(encoding="utf-8"))

    endpoint_name = "demo"
    host_url = "https://example.test/"
    generated = openapi_module.generate_openapi_spec(endpoint_name, host_url, app)

    expected = copy.deepcopy(template)
    expected["servers"] = [
        {
            "url": f"{host_url.rstrip('/')}/endpoint/{endpoint_name}",
            "description": "Endpoint-specific API",
        }
    ]

    assert generated == expected

