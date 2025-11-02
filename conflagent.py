"""Flask routing entry point for Conflagent."""

from __future__ import annotations

from flask import Flask, abort, g, jsonify, request

from conflagent_core.auth import check_auth
from conflagent_core.config import with_config
from conflagent_core.confluence import ConfluenceClient
from conflagent_core.openapi import (
    BEARER_SECURITY_REQUIREMENT,
    document_operation,
    generate_openapi_spec,
)


app = Flask(__name__)


def _get_client() -> ConfluenceClient:
    return ConfluenceClient(g.config)


@app.route("/endpoint/<endpoint_name>/pages", methods=["GET"])
@with_config
@document_operation(
    "/pages",
    "get",
    summary="List subpages of the root page",
    description=(
        "Returns the titles of all pages that are direct children of the configured "
        "root page in the Confluence space."
    ),
    operationId="listSubpages",
    security=BEARER_SECURITY_REQUIREMENT,
    responses={
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
)
def api_list_subpages(endpoint_name: str):  # pragma: no cover - exercised via tests
    check_auth()
    client = _get_client()
    return jsonify(client.list_pages())


@app.route("/endpoint/<endpoint_name>/pages/<path:title>", methods=["GET"])
@with_config
@document_operation(
    "/pages/{title}",
    "get",
    summary="Read content of a page by title",
    description=(
        "Returns the content of a Confluence page identified by title (must be a "
        "direct child of root). Content is returned in Confluence storage format "
        "(HTML-like XML). When reading content, be careful not to mangle internal "
        "page links in subsequent updates."
    ),
    operationId="readPageByTitle",
    parameters=[
        {
            "name": "title",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
    security=BEARER_SECURITY_REQUIREMENT,
    responses={
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
                                "description": (
                                    "Content in Confluence storage format (HTML-like XML)."
                                ),
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
)
def api_read_page(endpoint_name: str, title: str):
    check_auth()
    client = _get_client()
    page = client.get_page_by_path(title)
    if not page:
        abort(404, description="Page not found")

    content = client.get_page_body(page["id"])
    return jsonify({"title": title, "body": content})


@app.route("/endpoint/<endpoint_name>/pages", methods=["POST"])
@with_config
@document_operation(
    "/pages",
    "post",
    summary="Create a new child page under root",
    description=(
        "Creates a new Confluence page as a direct child of the configured root "
        "page. Title must be unique under the root. Body may contain Markdown — "
        "it will be converted to Confluence storage format automatically."
    ),
    operationId="createPage",
    security=BEARER_SECURITY_REQUIREMENT,
    requestBody={
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
                            "description": (
                                "Optional Markdown body — will be converted to "
                                "Confluence HTML format."
                            ),
                        },
                    },
                }
            }
        },
    },
    responses={
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
)
def api_create_page(endpoint_name: str):
    check_auth()
    data = request.get_json(force=True)
    title = data.get("title")
    body = data.get("body", "")
    if not title:
        abort(400, description="Title is required")

    client = _get_client()
    return jsonify(client.create_or_update_page(title, body))


@app.route("/endpoint/<endpoint_name>/pages/<path:title>", methods=["PUT"])
@with_config
@document_operation(
    "/pages/{title}",
    "put",
    summary="Update content of a page by title",
    description=(
        "Updates the full content of a Confluence page identified by title. Only "
        "pages under the configured root are updatable. Markdown input is "
        "accepted and will be converted on the fly to Confluence storage format "
        "(HTML/XML). ⚠️ Full body content must be submitted — partial/diff "
        "updates are not supported."
    ),
    operationId="updatePageByTitle",
    parameters=[
        {
            "name": "title",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
    security=BEARER_SECURITY_REQUIREMENT,
    requestBody={
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["body"],
                    "properties": {
                        "body": {
                            "type": "string",
                            "description": (
                                "Markdown content to be converted to Confluence "
                                "HTML. Submit full content only — diffs/patches "
                                "are not supported."
                            ),
                        },
                    },
                }
            }
        },
    },
    responses={
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
)
def api_update_page(endpoint_name: str, title: str):
    check_auth()
    data = request.get_json(force=True)
    new_body = data.get("body", "")

    client = _get_client()
    page = client.get_page_by_path(title)
    if not page:
        abort(404, description="Page not found")

    return jsonify(client.update_page(page, new_body))


@app.route("/endpoint/<endpoint_name>/pages/rename", methods=["POST"])
@with_config
@document_operation(
    "/pages/rename",
    "post",
    summary="Rename a page by title",
    description=(
        "Renames a page by changing its title. The page must be a direct child of "
        "the configured root page. Title change is immediate and does not alter "
        "page hierarchy."
    ),
    operationId="renamePage",
    security=BEARER_SECURITY_REQUIREMENT,
    requestBody={
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
    responses={
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
)
def api_rename_page(endpoint_name: str):
    check_auth()
    data = request.get_json(force=True)
    old_title = data.get("old_title")
    new_title = data.get("new_title")

    if not old_title or not new_title:
        abort(400, description="Both 'old_title' and 'new_title' are required.")

    client = _get_client()
    page = client.get_page_by_path(old_title)
    if not page:
        abort(404, description="Page not found")

    result = client.rename_page(page, new_title)
    result["new_title"] = new_title
    return jsonify(result)


@app.route("/endpoint/<endpoint_name>/openapi.json", methods=["GET"])
@with_config
@document_operation(
    "/openapi.json",
    "get",
    summary="Get OpenAPI schema",
    description="Returns this OpenAPI schema document.",
    operationId="getOpenAPISchema",
    responses={
        "200": {
            "description": "OpenAPI JSON returned",
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": {}},
                }
            },
        }
    },
)
def openapi_schema(endpoint_name: str):
    spec = generate_openapi_spec(endpoint_name, request.host_url, app)
    return jsonify(spec)


@app.route("/endpoint/<endpoint_name>/health", methods=["GET"])
@with_config
@document_operation(
    "/health",
    "get",
    summary="Health check",
    description="Check whether API server is live. No authentication required.",
    operationId="healthCheck",
    responses={
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
)
def api_health(endpoint_name: str):
    return jsonify({"status": "ok"})


if __name__ == "__main__":  # pragma: no cover - manual execution only
    app.run(host="0.0.0.0", port=5000)

