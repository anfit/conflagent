"""Flask routing entry point for Conflagent."""

from __future__ import annotations

from flask import Flask, abort, g, jsonify, request

from conflagent_core.auth import check_auth
from conflagent_core.config import with_config
from conflagent_core.confluence import ConfluenceClient
from conflagent_core.openapi import generate_openapi_spec


app = Flask(__name__)


def _get_client() -> ConfluenceClient:
    return ConfluenceClient(g.config)


@app.route("/endpoint/<endpoint_name>/pages", methods=["GET"])
@with_config
def api_list_subpages(endpoint_name: str):  # pragma: no cover - exercised via tests
    check_auth()
    client = _get_client()
    return jsonify(client.list_pages())


@app.route("/endpoint/<endpoint_name>/pages/<path:title>", methods=["GET"])
@with_config
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
def openapi_schema(endpoint_name: str):
    spec = generate_openapi_spec(endpoint_name, request.host_url)
    return jsonify(spec)


@app.route("/endpoint/<endpoint_name>/health", methods=["GET"])
@with_config
def api_health(endpoint_name: str):
    return jsonify({"status": "ok"})


if __name__ == "__main__":  # pragma: no cover - manual execution only
    app.run(host="0.0.0.0", port=5000)

