"""Tests for the dynamic OpenAPI generation helpers."""

from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask, g

from conflagent_core.openapi import (
    BEARER_SECURITY_REQUIREMENT,
    _collect_documented_paths,
    document_operation,
    generate_openapi_spec,
)


def test_document_operation_stores_copy_of_metadata() -> None:
    """The decorator should keep its own copy of the provided operation definition."""

    responses = {"200": {"description": "Successful response"}}

    @document_operation(
        "/demo",
        "get",
        flavors=("read", "default", "read"),
        summary="Demo endpoint",
        responses=responses,
        security=BEARER_SECURITY_REQUIREMENT,
    )
    def handler() -> str:
        return "demo"

    # Mutating the original inputs should not alter the stored OpenAPI details.
    responses["200"]["description"] = "Changed"
    BEARER_SECURITY_REQUIREMENT.append({"Another": []})
    BEARER_SECURITY_REQUIREMENT.pop()

    assert handler.__openapi__ == {
        "/demo": {
            "get": {
                "summary": "Demo endpoint",
                "responses": {"200": {"description": "Successful response"}},
                "security": [{"BearerAuth": []}],
            }
        }
    }

    assert handler.__openapi_flavors__ == {
        "/demo": {"get": ("read",)}
    }


def _build_documented_app() -> Tuple[Flask, dict, dict]:
    """Create a Flask app with documented routes for test purposes."""

    app = Flask(__name__)

    list_responses = {"200": {"description": "Listed"}}

    @document_operation(
        "/alpha",
        "get",
        flavors=("read",),
        summary="List alpha",
        responses=list_responses,
        security=BEARER_SECURITY_REQUIREMENT,
    )
    def list_alpha() -> str:
        return "alpha"

    app.add_url_rule(
        "/alpha",
        view_func=list_alpha,
        endpoint="list_alpha",
        methods=["GET"],
    )

    create_body = {
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            }
        }
    }
    create_responses = {"201": {"description": "Created"}}

    @document_operation(
        "/alpha",
        "post",
        flavors=("upload",),
        summary="Create alpha",
        requestBody=create_body,
        responses=create_responses,
        security=BEARER_SECURITY_REQUIREMENT,
    )
    def create_alpha() -> str:
        return "alpha"

    app.add_url_rule(
        "/alpha",
        view_func=create_alpha,
        endpoint="create_alpha",
        methods=["POST"],
    )

    return app, list_responses, create_responses


def test_collect_documented_paths_merges_operations() -> None:
    """Documented routes should be merged into a single OpenAPI path object."""

    app, list_responses, create_responses = _build_documented_app()
    collected, flavors = _collect_documented_paths(app)

    # Mutating the original dictionaries after collection should not change stored results.
    list_responses["200"]["description"] = "altered"
    create_responses["201"]["description"] = "altered"

    assert set(collected.keys()) == {"/alpha"}
    assert set(collected["/alpha"].keys()) == {"get", "post"}
    assert collected["/alpha"]["get"]["responses"] == {"200": {"description": "Listed"}}
    assert collected["/alpha"]["post"]["responses"] == {"201": {"description": "Created"}}
    assert flavors == {"/alpha": {"get": ("read",), "post": ("upload",)}}


def test_collect_documented_paths_detects_conflicts() -> None:
    """Conflicting documentation for the same method/path should raise an error."""

    app = Flask(__name__)

    @document_operation(
        "/conflict",
        "get",
        summary="First definition",
        responses={"200": {"description": "OK"}},
    )
    def first() -> str:
        return "first"

    app.add_url_rule("/first", view_func=first, endpoint="first")

    @document_operation(
        "/conflict",
        "get",
        summary="Second definition",
        responses={"200": {"description": "Different"}},
    )
    def second() -> str:
        return "second"

    app.add_url_rule("/second", view_func=second, endpoint="second")

    with pytest.raises(ValueError) as exc:
        _collect_documented_paths(app)

    assert "Conflicting OpenAPI definitions" in str(exc.value)


def test_generate_openapi_spec_includes_routes_and_server_metadata() -> None:
    """The generated spec should include metadata from the documented routes."""

    app, *_ = _build_documented_app()
    host_url = "https://example.test/root/"
    spec = generate_openapi_spec("alpha", host_url, app)

    assert spec["info"]["title"] == "Conflagent API"
    assert spec["info"]["version"] == "2.4.0"
    assert spec["servers"] == [
        {
            "url": "https://example.test/root/endpoint/alpha",
            "description": "Endpoint-specific API",
        }
    ]
    assert spec["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    assert "/alpha" in spec["paths"]
    assert "get" in spec["paths"]["/alpha"]
    assert "post" in spec["paths"]["/alpha"]
    assert spec["paths"]["/alpha"]["post"]["requestBody"]["content"]["application/json"]["schema"]["required"] == [
        "name"
    ]


def test_generate_openapi_spec_filters_by_configured_flavor() -> None:
    app, *_ = _build_documented_app()
    host_url = "https://example.test/root/"

    with app.test_request_context():
        g.config = {"flavor": "read"}
        spec = generate_openapi_spec("alpha", host_url, app)
        assert "/alpha" in spec["paths"]
        assert set(spec["paths"]["/alpha"].keys()) == {"get"}

    with app.test_request_context():
        g.config = {"flavor": "upload"}
        spec = generate_openapi_spec("alpha", host_url, app)
        assert "/alpha" in spec["paths"]
        assert set(spec["paths"]["/alpha"].keys()) == {"post"}


def test_generate_openapi_spec_always_operations_included() -> None:
    app = Flask(__name__)

    @document_operation("/visible", "get", flavors=("always",), responses={"200": {"description": "OK"}})
    def visible() -> str:
        return "visible"

    app.add_url_rule("/visible", view_func=visible, endpoint="visible", methods=["GET"])

    host_url = "https://example.test/root/"

    with app.test_request_context():
        g.config = {"flavor": "upload"}
        spec = generate_openapi_spec("alpha", host_url, app)
        assert "/visible" in spec["paths"]
        assert "get" in spec["paths"]["/visible"]

