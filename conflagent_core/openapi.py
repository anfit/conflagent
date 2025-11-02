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

_BEARER_SECURITY_REQUIREMENT = [{"BearerAuth": []}]

_PATH_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "/pages": {
        "get": {
            "summary": "List subpages of the root page",
            "description": "Returns the titles of all pages that are direct children of the configured root page in the Confluence space.",
            "operationId": "listSubpages",
            "security": _BEARER_SECURITY_REQUIREMENT,
            "responses": {
                "200": {
                    "description": "List of subpages",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        }
                    },
                },
                "403": {"description": "Forbidden: Invalid token"},
            },
        },
        "post": {
            "summary": "Create a new child page under root",
            "description": "Creates a new Confluence page as a direct child of the configured root page. Title must be unique under the root. Body may contain Markdown — it will be converted to Confluence storage format automatically.",
            "operationId": "createPage",
            "security": _BEARER_SECURITY_REQUIREMENT,
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["title"],
                            "properties": {
                                "title": {"type": "string"},
                                "body": {
                                    "type": "string",
                                    "description": "Optional Markdown body — will be converted to Confluence HTML format.",
                                },
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Page created successfully",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"},
                                    "id": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "403": {"description": "Forbidden: Invalid token"},
                "409": {
                    "description": "Conflict: Page with this title already exists under root"
                },
            },
        },
    },
    "/pages/{title}": {
        "get": {
            "summary": "Read content of a page by title",
            "description": "Returns the content of a Confluence page identified by title (must be a direct child of root). Content is returned in Confluence storage format (HTML-like XML). When reading content, be careful not to mangle internal page links in subsequent updates.",
            "operationId": "readPageByTitle",
            "parameters": [
                {
                    "name": "title",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "security": _BEARER_SECURITY_REQUIREMENT,
            "responses": {
                "200": {
                    "description": "Page content returned",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "body": {
                                        "type": "string",
                                        "description": "Content in Confluence storage format (HTML-like XML).",
                                    },
                                },
                            }
                        }
                    },
                },
                "403": {"description": "Forbidden: Invalid token"},
                "404": {
                    "description": "Not Found: Page not found or not a child of root"
                },
            },
        },
        "put": {
            "summary": "Update content of a page by title",
            "description": "Updates the full content of a Confluence page identified by title. Only pages under the configured root are updatable. Markdown input is accepted and will be converted on the fly to Confluence storage format (HTML/XML). ⚠️ Full body content must be submitted — partial/diff updates are not supported.",
            "operationId": "updatePageByTitle",
            "parameters": [
                {
                    "name": "title",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "security": _BEARER_SECURITY_REQUIREMENT,
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["body"],
                            "properties": {
                                "body": {
                                    "type": "string",
                                    "description": "Markdown content to be converted to Confluence HTML. Submit full content only — diffs/patches are not supported.",
                                },
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Page updated successfully",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"},
                                    "version": {"type": "integer"},
                                },
                            }
                        }
                    },
                },
                "403": {"description": "Forbidden: Invalid token"},
                "404": {
                    "description": "Not Found: Page not found or not a child of root"
                },
            },
        },
    },
    "/pages/rename": {
        "post": {
            "summary": "Rename a page by title",
            "description": "Renames a page by changing its title. The page must be a direct child of the configured root page. Title change is immediate and does not alter page hierarchy.",
            "operationId": "renamePage",
            "security": _BEARER_SECURITY_REQUIREMENT,
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["old_title", "new_title"],
                            "properties": {
                                "old_title": {"type": "string"},
                                "new_title": {"type": "string"},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Page renamed successfully",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"},
                                    "new_title": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "403": {"description": "Forbidden: Invalid token"},
                "404": {
                    "description": "Not Found: Page not found or not a child of root"
                },
            },
        }
    },
    "/health": {
        "get": {
            "summary": "Health check",
            "description": "Check whether API server is live. No authentication required.",
            "operationId": "healthCheck",
            "responses": {
                "200": {
                    "description": "Server is running",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string", "example": "ok"},
                                },
                            }
                        }
                    },
                }
            },
        }
    },
    "/openapi.json": {
        "get": {
            "summary": "Get OpenAPI schema",
            "description": "Returns this OpenAPI schema document.",
            "operationId": "getOpenAPISchema",
            "responses": {
                "200": {
                    "description": "OpenAPI JSON returned",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {},
                            }
                        }
                    },
                }
            },
        }
    },
}


def document_operation(path: str, method: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach an OpenAPI definition to a Flask view function."""

    normalised_method = method.lower()
    if path not in _PATH_DEFINITIONS or normalised_method not in _PATH_DEFINITIONS[path]:
        raise KeyError(f"Unknown OpenAPI definition for {method.upper()} {path}")

    definition = copy.deepcopy(_PATH_DEFINITIONS[path][normalised_method])

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        docs: Dict[str, Dict[str, Any]] = getattr(func, "__openapi__", {})
        path_docs = docs.setdefault(path, {})
        if normalised_method in path_docs:
            raise ValueError(
                f"Duplicate OpenAPI definition for {method.upper()} {path} on {func.__name__}"
            )
        path_docs[normalised_method] = definition
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

