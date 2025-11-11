"""Utilities for serving the OpenAPI schema."""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, Iterable, Tuple

from apispec import APISpec
from flask import Flask, abort, g, has_request_context

_API_DESCRIPTION = (
    "REST API bridge between Custom GPTs and a sandboxed Confluence root page. "
    "All requests must be authenticated using a Bearer token (Authorization: Bearer <token>). "
    "API enables programmatic listing, reading, creation, updating, moving, and renaming of Confluence pages "
    "under a pre-defined root page, including traversal of hierarchical relationships."
)

BEARER_SECURITY_REQUIREMENT = [{"BearerAuth": []}]

def _normalise_flavors(flavors: Iterable[str] | None) -> Tuple[str, ...]:
    if not flavors:
        return ()

    normalised: list[str] = []
    for raw_flavor in flavors:
        if not isinstance(raw_flavor, str):
            raise TypeError("Flavor annotations must be strings")
        stripped = raw_flavor.strip()
        if not stripped:
            raise ValueError("Flavor annotations cannot be empty strings")
        lower = stripped.lower()
        if lower == "default":
            continue
        if lower not in normalised:
            normalised.append(lower)
    return tuple(normalised)


def document_operation(
    path: str,
    method: str,
    *,
    flavors: Iterable[str] | None = None,
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
    normalised_flavors = _normalise_flavors(flavors)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        docs: Dict[str, Dict[str, Any]] = getattr(func, "__openapi__", {})
        flavors_map: Dict[str, Dict[str, Tuple[str, ...]]] = getattr(
            func, "__openapi_flavors__", {}
        )
        path_docs = docs.setdefault(path, {})
        path_flavors = flavors_map.setdefault(path, {})
        if normalised_method in path_docs:
            raise ValueError(
                f"Duplicate OpenAPI definition for {method.upper()} {path} on {func.__name__}"
            )
        path_docs[normalised_method] = copy.deepcopy(definition)
        path_flavors[normalised_method] = normalised_flavors
        setattr(func, "__openapi__", docs)
        setattr(func, "__openapi_flavors__", flavors_map)
        return func

    return decorator


def _collect_documented_paths(
    flask_app: Flask,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Tuple[str, ...]]]]:
    """Gather OpenAPI metadata from documented Flask view functions."""

    documented_paths: Dict[str, Dict[str, Any]] = {}
    flavors_by_path: Dict[str, Dict[str, Tuple[str, ...]]] = {}
    for view_func in flask_app.view_functions.values():
        view_docs = getattr(view_func, "__openapi__", None)
        if not view_docs:
            continue
        view_flavors = getattr(view_func, "__openapi_flavors__", {})
        for path, operations in view_docs.items():
            merged_operations = documented_paths.setdefault(path, {})
            merged_flavors = flavors_by_path.setdefault(path, {})
            operation_flavors = view_flavors.get(path, {})
            for method, details in operations.items():
                if method in merged_operations and merged_operations[method] != details:
                    raise ValueError(
                        f"Conflicting OpenAPI definitions for {method.upper()} {path}"
                    )
                merged_operations[method] = copy.deepcopy(details)
                flavors_for_method = tuple(operation_flavors.get(method, ()))
                if method in merged_flavors and merged_flavors[method] != flavors_for_method:
                    raise ValueError(
                        f"Conflicting flavor annotations for {method.upper()} {path}"
                    )
                merged_flavors[method] = flavors_for_method
    return documented_paths, flavors_by_path


def _build_spec(paths: Dict[str, Dict[str, Any]]) -> APISpec:
    spec = APISpec(
        title="Conflagent API",
        version="2.4.0",
        openapi_version="3.1.0",
        info={"description": _API_DESCRIPTION},
    )

    spec.components.security_scheme(
        "BearerAuth",
        {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    )

    for path, operations in paths.items():
        spec.path(path=path, operations=operations)

    return spec


def _resolve_requested_flavor() -> str:
    if has_request_context():
        config = getattr(g, "config", None)
        if isinstance(config, dict):
            raw_flavor = config.get("flavor", "default")
            if isinstance(raw_flavor, str) and raw_flavor.strip():
                return raw_flavor.strip().lower()
    return "default"


def _should_include_operation(
    configured_flavor: str, operation_flavors: Tuple[str, ...]
) -> bool:
    if "always" in operation_flavors:
        return True
    if configured_flavor == "default":
        return True
    return configured_flavor in operation_flavors


def _filter_paths_by_flavor(
    paths: Dict[str, Dict[str, Any]],
    flavors: Dict[str, Dict[str, Tuple[str, ...]]],
    configured_flavor: str,
) -> Dict[str, Dict[str, Any]]:
    filtered: Dict[str, Dict[str, Any]] = {}
    for path, operations in paths.items():
        path_flavors = flavors.get(path, {})
        included_methods: Dict[str, Any] = {}
        for method, details in operations.items():
            operation_flavors = path_flavors.get(method, ())
            if _should_include_operation(configured_flavor, operation_flavors):
                included_methods[method] = copy.deepcopy(details)
        if included_methods:
            filtered[path] = included_methods
    return filtered


def generate_openapi_spec(
    endpoint_name: str,
    host_url: str,
    flask_app: Flask,
) -> Dict[str, Any]:
    """Generate a customised OpenAPI specification for an endpoint."""

    try:
        paths, flavors = _collect_documented_paths(flask_app)
        configured_flavor = _resolve_requested_flavor()
        filtered_paths = _filter_paths_by_flavor(paths, flavors, configured_flavor)
        spec = _build_spec(filtered_paths).to_dict()
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

