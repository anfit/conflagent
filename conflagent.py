from flask import Flask, request, jsonify, abort, send_file
import requests
import base64
import os

app = Flask(__name__)
CONFIG = {}

def load_config(path="conflagent.properties"):
    if not os.path.exists(path):
        raise RuntimeError(f"Configuration file '{path}' not found.")
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if sep:
                CONFIG[key.strip()] = value.strip()

    required_keys = ["email", "api_token", "base_url", "space_key", "root_page_id", "gpt_shared_secret"]
    for key in required_keys:
        if key not in CONFIG:
            raise RuntimeError(f"Missing required config key: {key}")

# ❗️ Ensure config is loaded at Flask import time — NOT in __main__ block
load_config()

def check_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(403, description="Forbidden: Missing or invalid Authorization header")
    token = auth_header.split("Bearer ")[-1].strip()
    if token != CONFIG["gpt_shared_secret"]:
        abort(403, description="Forbidden: Invalid bearer token")

def build_headers():
    token = f"{CONFIG['email']}:{CONFIG['api_token']}"
    token_bytes = base64.b64encode(token.encode()).decode()
    return {
        "Authorization": f"Basic {token_bytes}",
        "Content-Type": "application/json"
    }

def get_page_by_title(title, parent_id):
    url = f"{CONFIG['base_url']}/rest/api/content/{parent_id}/child/page"
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
    current_parent_id = CONFIG['root_page_id']
    for part in parts:
        existing = get_page_by_title(part, current_parent_id)
        if existing:
            current_parent_id = existing["id"]
        else:
            payload = {
                "type": "page",
                "title": part,
                "ancestors": [{"id": current_parent_id}],
                "space": {"key": CONFIG['space_key']},
                "body": {"storage": {"value": "", "representation": "storage"}}
            }
            url = f"{CONFIG['base_url']}/rest/api/content"
            response = requests.post(url, headers=build_headers(), json=payload)
            if response.status_code != 200:
                abort(response.status_code, response.text)
            current_parent_id = response.json()["id"]
    return current_parent_id

def list_pages_recursive(parent_id, prefix=""):
    url = f"{CONFIG['base_url']}/rest/api/content/{parent_id}/child/page"
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
    current_parent_id = CONFIG['root_page_id']
    for part in parts:
        page = get_page_by_title(part, current_parent_id)
        if not page:
            return None
        current_parent_id = page["id"]
    return page

def get_page_body(page_id):
    url = f"{CONFIG['base_url']}/rest/api/content/{page_id}?expand=body.storage"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return response.json()["body"]["storage"]["value"]

def create_or_update_page(path, body):
    parts = path.strip("/").split("/")
    parent_path = "/".join(parts[:-1])
    page_title = parts[-1]
    parent_id = resolve_or_create_path(parent_path) if parent_path else CONFIG['root_page_id']
    existing = get_page_by_title(page_title, parent_id)
    if existing:
        return update_page(existing, body)
    payload = {
        "type": "page",
        "title": page_title,
        "ancestors": [{"id": parent_id}],
        "space": {"key": CONFIG['space_key']},
        "body": {"storage": {"value": body, "representation": "storage"}}
    }
    url = f"{CONFIG['base_url']}/rest/api/content"
    response = requests.post(url, headers=build_headers(), json=payload)
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return {"message": "Page created", "id": response.json()["id"]}

def update_page(page, new_body):
    url = f"{CONFIG['base_url']}/rest/api/content/{page['id']}?expand=version"
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
    url = f"{CONFIG['base_url']}/rest/api/content/{page['id']}"
    response = requests.put(url, headers=build_headers(), json=payload)
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return {"message": "Page updated", "version": version}

# === API Endpoints ===

@app.route("/pages", methods=["GET"])
def api_list_subpages():
    check_auth()
    return jsonify(list_pages_recursive(CONFIG['root_page_id']))

@app.route("/pages/<path:title>", methods=["GET"])
def api_read_page(title):
    check_auth()
    page = get_page_by_path(title)
    if not page:
        abort(404, description="Page not found")
    content = get_page_body(page["id"])
    return jsonify({"title": title, "body": content})

@app.route("/pages", methods=["POST"])
def api_create_page():
    check_auth()
    data = request.get_json(force=True)
    title = data.get("title")
    body = data.get("body", "")
    if not title:
        abort(400, description="Title is required")
    return jsonify(create_or_update_page(title, body))

@app.route("/pages/<path:title>", methods=["PUT"])
def api_update_page(title):
    check_auth()
    data = request.get_json(force=True)
    new_body = data.get("body", "")
    page = get_page_by_path(title)
    if not page:
        abort(404, description="Page not found")
    return jsonify(update_page(page, new_body))

@app.route("/openapi.json", methods=["GET"])
def openapi_schema():
    return send_file("openapi.json", mimetype="application/json")

@app.route("/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    load_config()
    app.run(host="0.0.0.0", port=5000)