"""Utilities for serving the OpenAPI schema."""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict

from apispec import APISpec
from flask import Flask, abort

_API_DESCRIPTION = (
    "REST API bridge between Custom GPTs and a sandboxed Confluence root page. "
    "All requests must be authenticated using a Bearer token (Authorization: Bearer <token>). "
    "API enables programmatic listing, reading, creation, updating, and renaming of Confluence pages "
    "under a pre-defined root page."
)

BEARER_SECURITY_REQUIREMENT = [{"BearerAuth": []}]

def document_operation(
    path: str,
    method: str,
    **operation: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach an OpenAPI definition to a Flask view function.

    The decorator stores the provided OpenAPI operation object on the wrapped
    function so the generator can harvest them at runtime.
    """

    if not operation:
        raise ValueError(
            f"OpenAPI operation for {method.upper()} {path} must define at least one field"
        )

    normalised_method = method.lower()
    definition = copy.deepcopy(operation)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        docs: Dict[str, Dict[str, Any]] = getattr(func, "__openapi__", {})
        path_docs = docs.setdefault(path, {})
        if normalised_method in path_docs:
            raise ValueError(
                f"Duplicate OpenAPI definition for {method.upper()} {path} on {func.__name__}"
            )
        path_docs[normalised_method] = copy.deepcopy(definition)
        setattr(func, "__openapi__", docs)
        return func

    return decorator


def _collect_documented_paths(flask_app: Flask) -> Dict[str, Dict[str, Any]]:
    """Gather OpenAPI metadata from documented Flask view functions."""

    documented_paths: Dict[str, Dict[str, Any]] = {}
    for view_func in flask_app.view_functions.values():
        view_docs = getattr(view_func, "__openapi__", None)
        if not view_docs:
            continue
        for path, operations in view_docs.items():
            merged_operations = documented_paths.setdefault(path, {})
            for method, details in operations.items():
                if method in merged_operations and merged_operations[method] != details:
                    raise ValueError(
                        f"Conflicting OpenAPI definitions for {method.upper()} {path}"
                    )
                merged_operations[method] = copy.deepcopy(details)
    return documented_paths


def _build_spec(flask_app: Flask) -> APISpec:
    spec = APISpec(
        title="Conflagent API",
        version="2.2.0",
        openapi_version="3.1.0",
        info={"description": _API_DESCRIPTION},
    )

    spec.components.security_scheme(
        "BearerAuth",
        {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    )

    for path, operations in _collect_documented_paths(flask_app).items():
        spec.path(path=path, operations=operations)

    return spec


def generate_openapi_spec(
    endpoint_name: str,
    host_url: str,
    flask_app: Flask,
    template_path: str = "openapi.json",
) -> Dict[str, Any]:
    """Generate a customised OpenAPI specification for an endpoint."""

    try:
        spec = _build_spec(flask_app).to_dict()
    except Exception as exc:  # pragma: no cover - bubbled via abort
        abort(500, description=f"Failed to build OpenAPI specification: {exc}")

    spec.setdefault("components", {}).setdefault("schemas", {})
    spec["servers"] = [
        {
            "url": f"{host_url.rstrip('/')}/endpoint/{endpoint_name}",
            "description": "Endpoint-specific API",
        }
    ]
    return spec

