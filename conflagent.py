from flask import Flask, request, jsonify, abort, send_file
import requests
import base64
import os

app = Flask(__name__)
CONFIG = {}

def load_config(path="confluence.properties"):
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
    secret = request.headers.get("X-GPT-Secret")
    if not secret or secret != CONFIG["gpt_shared_secret"]:
        abort(403, description="Forbidden: Invalid GPT shared secret")

def build_headers():
    token = f"{CONFIG['email']}:{CONFIG['api_token']}"
    token_bytes = base64.b64encode(token.encode()).decode()
    return {
        "Authorization": f"Basic {token_bytes}",
        "Content-Type": "application/json"
    }

def list_subpages():
    url = f"{CONFIG['base_url']}/rest/api/content/{CONFIG['root_page_id']}/child/page"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    results = response.json().get("results", [])
    return [{"id": r["id"], "title": r["title"]} for r in results]

def find_child_page_by_title(title):
    children = list_subpages()
    for page in children:
        if page["title"] == title:
            return page
    return None

def get_page_body(page_id):
    url = f"{CONFIG['base_url']}/rest/api/content/{page_id}?expand=body.storage"
    response = requests.get(url, headers=build_headers())
    if response.status_code != 200:
        abort(response.status_code, response.text)
    return response.json()["body"]["storage"]["value"]

def create_page(title, body):
    payload = {
        "type": "page",
        "title": title,
        "ancestors": [{"id": CONFIG['root_page_id']}],
        "space": {"key": CONFIG['space_key']},
        "body": {
            "storage": {
                "value": body or "",
                "representation": "storage"
            }
        }
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
        "body": {
            "storage": {
                "value": new_body,
                "representation": "storage"
            }
        }
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
    return jsonify(list_subpages())

@app.route("/pages/<string:title>", methods=["GET"])
def api_read_page(title):
    check_auth()
    page = find_child_page_by_title(title)
    if not page:
        abort(404, description="Page not found or not a child of root")
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
    if find_child_page_by_title(title):
        abort(409, description="Page with this title already exists under root")
    return jsonify(create_page(title, body))

@app.route("/pages/<string:title>", methods=["PUT"])
def api_update_page(title):
    check_auth()
    data = request.get_json(force=True)
    new_body = data.get("body", "")
    page = find_child_page_by_title(title)
    if not page:
        abort(404, description="Page not found or not a child of root")
    return jsonify(update_page(page, new_body))

@app.route("/openapi.json", methods=["GET"])
def openapi_schema():
    return send_file("openapi_conflagent.json", mimetype="application/json")

@app.route("/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    load_config()
    app.run(host="0.0.0.0", port=5000)
