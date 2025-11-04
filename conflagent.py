"""Flask routing entry point for Conflagent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Flask, abort, g, jsonify, request
from werkzeug.exceptions import HTTPException

from conflagent_core.auth import check_auth
from conflagent_core.config import with_config
from conflagent_core.confluence import ConfluenceClient
from conflagent_core.openapi import (
    BEARER_SECURITY_REQUIREMENT,
    document_operation,
    generate_openapi_spec,
)
from conflagent_core.response import error_response, success_response


app = Flask(__name__)


_ERROR_CODE_BY_STATUS: Dict[int, str] = {
    400: "INVALID_INPUT",
    401: "UNAUTHORIZED",
    403: "UNAUTHORIZED",
    404: "NOT_FOUND",
    409: "VERSION_CONFLICT",
    500: "INTERNAL_ERROR",
}


def _map_error_code(status_code: int) -> str:
    return _ERROR_CODE_BY_STATUS.get(status_code, "INTERNAL_ERROR")


def _success(message: str, data: Optional[Any] = None, *, code: str = "OK", status_code: int = 200):
    return success_response(message, data, code=code, status_code=status_code)


def _response_schema(data_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    schema: Dict[str, Any] = {
        "type": "object",
        "required": ["success", "code", "message", "timestamp"],
        "properties": {
            "success": {"type": "boolean"},
            "code": {"type": "string"},
            "message": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
        },
    }

    if data_schema is None:
        schema["properties"]["data"] = {"type": "null"}
    else:
        schema["properties"]["data"] = {
            "oneOf": [data_schema, {"type": "null"}],
        }

    return schema


def _get_client() -> ConfluenceClient:
    return ConfluenceClient(g.config)


@app.errorhandler(HTTPException)
def _handle_http_exception(exc: HTTPException):  # pragma: no cover - behaviour asserted in tests
    message = exc.description or exc.name
    code = _map_error_code(exc.code)
    return error_response(code, message, status_code=exc.code)


@app.errorhandler(Exception)
def _handle_unexpected_exception(exc: Exception):  # pragma: no cover - behaviour asserted in tests
    return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


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
                    "schema": _response_schema(
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of subpage paths",
                        }
                    )
                }
            },
        },
        "403": {"description": "Forbidden: Invalid token"},
    },
)
def api_list_subpages(endpoint_name: str):  # pragma: no cover - exercised via tests
    check_auth()
    client = _get_client()
    pages = client.list_pages()
    return _success("Subpages retrieved.", data=pages)


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
                    "schema": _response_schema(
                        {
                            "type": "object",
                            "required": ["title", "body"],
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
                    )
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
    return _success(
        "Page retrieved.",
        data={"title": title, "body": content},
    )


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
                    "schema": _response_schema(
                        {
                            "type": "object",
                            "required": ["id", "version"],
                            "properties": {
                                "id": {"type": "string"},
                                "version": {"type": "integer"},
                            },
                        }
                    )
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
    result = client.create_or_update_page(title, body)
    data = {"id": result["id"], "version": result["version"]}
    return _success("Page created.", data=data)


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
                    "schema": _response_schema(
                        {
                            "type": "object",
                            "required": ["version"],
                            "properties": {
                                "version": {"type": "integer"},
                            },
                        }
                    )
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

    result = client.update_page(page, new_body)
    return _success("Page updated.", data={"version": result["version"]})


@app.route("/endpoint/<endpoint_name>/pages/<path:title>", methods=["DELETE"])
@with_config
@document_operation(
    "/pages/{title}",
    "delete",
    summary="Delete a page by title",
    description=(
        "Deletes a Confluence page identified by title. Only pages under the "
        "configured root are deletable."
    ),
    operationId="deletePageByTitle",
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
            "description": "Page deleted successfully",
            "content": {
                "application/json": {
                    "schema": _response_schema(
                        {
                            "type": "object",
                            "required": ["deletedTitle"],
                            "properties": {
                                "deletedTitle": {"type": "string"},
                            },
                        }
                    )
                }
            },
        },
        "403": {"description": "Forbidden: Invalid token"},
        "404": {
            "description": "Not Found: Page not found or not a child of root"
        },
    },
)
def api_delete_page(endpoint_name: str, title: str):
    check_auth()

    client = _get_client()
    page = client.get_page_by_path(title)
    if not page:
        abort(404, description="Page not found")

    result = client.delete_page(page)
    return _success(
        "Page deleted.",
        data={"deletedTitle": result["deleted_title"]},
    )


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
                    "schema": _response_schema(
                        {
                            "type": "object",
                            "required": ["oldTitle", "newTitle", "version"],
                            "properties": {
                                "oldTitle": {"type": "string"},
                                "newTitle": {"type": "string"},
                                "version": {"type": "integer"},
                            },
                        }
                    )
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
    data = {
        "oldTitle": result["old_title"],
        "newTitle": result["new_title"],
        "version": result["version"],
    }
    return _success("Page renamed.", data=data)


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
                    "schema": _response_schema(
                        {
                            "type": "object",
                            "required": ["status"],
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "example": "ok",
                                }
                            },
                        }
                    )
                }
            },
        }
    },
)
def api_health(endpoint_name: str):
    return _success("Service healthy.", data={"status": "ok"})


if __name__ == "__main__":  # pragma: no cover - manual execution only
    app.run(host="0.0.0.0", port=5000)

