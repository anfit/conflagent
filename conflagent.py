from flask import Flask, request, jsonify, abort, send_file, g
import requests
import base64
import os
import json
import copy

app = Flask(__name__)
CONFIG_CACHE = {}

def load_config(endpoint_name):
    if endpoint_name in CONFIG_CACHE:
        return CONFIG_CACHE[endpoint_name]

    path = f"conflagent.{endpoint_name}.properties"
    if not os.path.exists(path):
        abort(404, description=f"Configuration for endpoint '{endpoint_name}' not found")

    config = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if sep:
                config[key.strip()] = value.strip()

    required_keys = ["email", "api_token", "base_url", "space_key", "root_page_id", "gpt_shared_secret"]
    for key in required_keys:
        if key not in config:
            abort(500, description=f"Missing required config key '{key}' in {path}")

    CONFIG_CACHE[endpoint_name] = config
    return config

def with_config(f):
    def wrapped(endpoint_name, *args, **kwargs):
        g.config = load_config(endpoint_name)
        return f(endpoint_name, *args, **kwargs)
    wrapped.__name__ = f.__name__
    return wrapped

def check_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(403, description="Forbidden: Missing or invalid Authorization header")
    token = auth_header.split("Bearer ")[-1].strip()
    if token != g.config["gpt_shared_secret"]:
        abort(403, description="Forbidden: Invalid bearer token")

def build_headers():
    token = f"{g.config['email']}:{g.config['api_token']}"
    token_bytes = base64.b64encode(token.encode()).decode()
    return {
        "Authorization": f"Basic {token_bytes}",
        "Content-Type": "application/json"
    }

def get_page_by_title(title, parent_id):
    url = f"{g.config['base_url']}/rest/api/content/{parent_id}/child/page"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    results = response.json().get("results", [])
    for page in results:
        if page["title"] == title:
            return page
    return None

def resolve_or_create_path(path):
    parts = path.strip("/").split("/")
    current_parent_id = g.config['root_page_id']
    for part in parts:
        existing = get_page_by_title(part, current_parent_id)
        if existing:
            current_parent_id = existing["id"]
        else:
            payload = {
                "type": "page",
                "title": part,
                "ancestors": [{"id": current_parent_id}],
                "space": {"key": g.config['space_key']},
                "body": {"storage": {"value": "", "representation": "storage"}}
            }
            url = f"{g.config['base_url']}/rest/api/content"
            response = requests.post(url, headers=build_headers(), json=payload)
            if response.status_code != 200:
                abort(response.status_code, response.text)
            current_parent_id = response.json()["id"]
    return current_parent_id

def list_pages_recursive(parent_id, prefix=""):
    url = f"{g.config['base_url']}/rest/api/content/{parent_id}/child/page"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    results = response.json().get("results", [])
    paths = []
    for page in results:
        title = page["title"]
        path = f"{prefix}/{title}" if prefix else title
        paths.append(path)
        paths.extend(list_pages_recursive(page["id"], path))
    return paths

def get_page_by_path(path):
    parts = path.strip("/").split("/")
    current_parent_id = g.config['root_page_id']
    for part in parts:
        page = get_page_by_title(part, current_parent_id)
        if not page:
            return None
        current_parent_id = page["id"]
    return page

def get_page_body(page_id):
    url = f"{g.config['base_url']}/rest/api/content/{page_id}?expand=body.storage"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return response.json()["body"]["storage"]["value"]

def create_or_update_page(path, body):
    parts = path.strip("/").split("/")
    parent_path = "/".join(parts[:-1])
    page_title = parts[-1]
    parent_id = resolve_or_create_path(parent_path) if parent_path else g.config['root_page_id']
    existing = get_page_by_title(page_title, parent_id)
    if existing:
        return update_page(existing, body)
    payload = {
        "type": "page",
        "title": page_title,
        "ancestors": [{"id": parent_id}],
        "space": {"key": g.config['space_key']},
        "body": {"storage": {"value": body, "representation": "storage"}}
    }
    url = f"{g.config['base_url']}/rest/api/content"
    response = requests.post(url, headers=build_headers(), json=payload)
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return {"message": "Page created", "id": response.json()["id"]}

def update_page(page, new_body):
    url = f"{g.config['base_url']}/rest/api/content/{page['id']}?expand=version"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    version = response.json()["version"]["number"] + 1
    payload = {
        "id": page["id"],
        "type": "page",
        "title": page["title"],
        "version": {"number": version},
        "body": {"storage": {"value": new_body, "representation": "storage"}}
    }
    url = f"{g.config['base_url']}/rest/api/content/{page['id']}"
    response = requests.put(url, headers=build_headers(), json=payload)
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return {"message": "Page updated", "version": version}

def rename_page(page, new_title):
    url = f"{g.config['base_url']}/rest/api/content/{page['id']}?expand=version"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    version = response.json()["version"]["number"] + 1

    body = get_page_body(page["id"])  # <- fetch body content here

    payload = {
        "id": page["id"],
        "type": "page",
        "title": new_title,
        "version": {"number": version},
        "body": {"storage": {"value": body, "representation": "storage"}}
    }
    url = f"{g.config['base_url']}/rest/api/content/{page['id']}"
    response = requests.put(url, headers=build_headers(), json=payload)
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return {"message": "Page renamed", "version": version}


# === API Endpoints ===

@app.route("/endpoint/<endpoint_name>/pages", methods=["GET"])
@with_config
def api_list_subpages(endpoint_name):
    check_auth()
    return jsonify(list_pages_recursive(g.config['root_page_id']))

@app.route("/endpoint/<endpoint_name>/pages/<path:title>", methods=["GET"])
@with_config
def api_read_page(endpoint_name, title):
    check_auth()
    page = get_page_by_path(title)
    if not page:
        abort(404, description="Page not found")
    content = get_page_body(page["id"])
    return jsonify({"title": title, "body": content})

@app.route("/endpoint/<endpoint_name>/pages", methods=["POST"])
@with_config
def api_create_page(endpoint_name):
    check_auth()
    data = request.get_json(force=True)
    title = data.get("title")
    body = data.get("body", "")
    if not title:
        abort(400, description="Title is required")
    return jsonify(create_or_update_page(title, body))

@app.route("/endpoint/<endpoint_name>/pages/<path:title>", methods=["PUT"])
@with_config
def api_update_page(endpoint_name, title):
    check_auth()
    data = request.get_json(force=True)
    new_body = data.get("body", "")
    page = get_page_by_path(title)
    if not page:
        abort(404, description="Page not found")
    return jsonify(update_page(page, new_body))

@app.route('/endpoint/<endpoint_name>/pages/rename', methods=['POST'])
@with_config
def api_rename_page(endpoint_name):
    check_auth()
    data = request.get_json(force=True)
    old_title = data.get("old_title")
    new_title = data.get("new_title")

    if not old_title or not new_title:
        abort(400, description="Both 'old_title' and 'new_title' are required.")

    page = get_page_by_path(old_title)
    if not page:
        abort(404, description="Page not found")

    result = rename_page(page, new_title)
    result["new_title"] = new_title  # Ensure consistency for test expectations
    return jsonify(result)


@app.route("/endpoint/<endpoint_name>/openapi.json", methods=["GET"])
@with_config
def openapi_schema(endpoint_name):
    try:
        with open("openapi.json", "r") as f:
            template = json.load(f)
    except Exception as e:
        abort(500, description=f"Failed to load OpenAPI template: {e}")

    spec = copy.deepcopy(template)
    host_url = request.host_url.rstrip("/")
    spec["servers"] = [{"url": f"{host_url}/endpoint/{endpoint_name}", "description": "Endpoint-specific API"}]

    return jsonify(spec)

@app.route("/endpoint/<endpoint_name>/health", methods=["GET"])
@with_config
def api_health(endpoint_name):
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)