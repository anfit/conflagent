# Conflagent – REST API Bridge to Confluence for Custom GPTs

**Conflagent** is a lightweight, standalone REST API service that acts as a bridge between a custom GPT (or any other HTTP client) and a sandboxed section of an Atlassian Confluence workspace. It allows programmatic listing, creation, reading, updating, and renaming of Confluence pages, enabling GPT-based document automation, intelligent assistants, or bot integrations.

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

- REST API secured via a pre-shared GPT secret (Bearer token via `Authorization: Bearer <token>` header)
- Supports **multiple independent endpoint instances**, each isolated under `/endpoint/<name>/` and configured via separate `conflagent.<name>.properties` files
- Dynamic OpenAPI schema rendering per endpoint at `/endpoint/<name>/openapi.json`
- Operations limited to a pre-defined Confluence space and root page per endpoint
- Fully compatible with Custom GPTs via OpenAPI tool definition
- Minimal, self-contained Flask app with no external database

## 📚 Use Case

Designed to integrate with a **Custom GPT Operator Tool**, this API allows a GPT to:
- **List** all subpages under a specified Confluence root page
- **Read** content of a child page by its title
- **Create** a new child page under the root
- **Update** an existing child page by title
- **Rename** a child page by title

> ⚠️ When updating pages, **submit full content only** – the API does **not support diffs or partial updates**.
> Markdown input is accepted and will be automatically converted to Confluence HTML format.
> Take care **not to mangle internal page links** during updates.

This provides a clean way to expose a read/write Confluence sandbox to GPTs without exposing the entire Confluence workspace or admin API tokens.

## 🔐 Multi-endpoint Architecture

Each GPT or user-specific configuration lives in its own file named `conflagent.<endpoint>.properties`. These endpoints are isolated and **treated as private secrets** — there is **no discovery API** for listing endpoints.

The API structure for each endpoint is:
```
/endpoint/<name>/pages
/endpoint/<name>/pages/<title>
/endpoint/<name>/pages/rename
/endpoint/<name>/openapi.json   ← dynamic OpenAPI schema
/endpoint/<name>/health
```
It should be placed *outside* deployment folder.

## 📂 Project Structure

```
conflagent/
├── conflagent.py                    # Flask application implementing the API
├── conflagent.properties.example    # Example configuration file
├── openapi.json                     # OpenAPI 3.1 schema template used per endpoint
├── tests/                           # Test suite covering all endpoints
```

## ⚙️ Setup & Deployment

This repository contains only the Conflagent service code. The automation that builds
and ships the application lives in a separate, private deployment repository. In
practice this means:

- **Three permanent environments** – `main` deploys to the dev instance, `staging`
  to the stage instance for manual verification, and `prod` to the production
  instance that must remain stable.
- **Trunk-based development** – feature work branches off `main`, is merged via
  small, continuously integrated changes, and then flows through staging to
  production.
- **Environment-specific logic** – infrastructure templates, secrets management,
  and any pipeline-specific scripts are managed outside of this repo. Coordinate
  with the deployment repository for changes to those assets.

Regardless of environment, Conflagent must be hosted behind HTTPS to keep GPT
secrets and Confluence tokens protected in transit.

## 🔐 Security Model

All protected operations require a pre-shared Bearer token header:
```
Authorization: Bearer your_gpt_secret
```
GPT tool calls must include this to access or modify Confluence content. The secret should be embedded in your Custom GPT configuration. **Each endpoint has its own secret.**

## 📖 API Endpoints (summary for each `<endpoint>`)

| Method | Path                                         | Description                                                                      | Auth required |
|--------|----------------------------------------------|----------------------------------------------------------------------------------|----------------|
| GET    | `/endpoint/<endpoint>/pages`                | List all subpages under the root                                                 | ✅ Yes          |
| GET    | `/endpoint/<endpoint>/pages/{title}`        | Read a page by title (returned as Confluence HTML)                              | ✅ Yes          |
| POST   | `/endpoint/<endpoint>/pages`                | Create a new page under root. Accepts Markdown, auto-converted to Confluence.   | ✅ Yes          |
| PUT    | `/endpoint/<endpoint>/pages/{title}`        | Update a page. Submit **full** content. Accepts Markdown input.                  | ✅ Yes          |
| POST   | `/endpoint/<endpoint>/pages/rename`         | Rename a page from one title to another                                          | ✅ Yes          |
| GET    | `/endpoint/<endpoint>/openapi.json`         | Dynamic OpenAPI schema for GPT tooling                                           | ❌ No           |
| GET    | `/endpoint/<endpoint>/health`               | Health check                                                                     | ❌ No           |

## 🤖 GPT Integration Guide

To integrate this API with a Custom GPT:
1. Upload or import `openapi.json` into the GPT tool definition. **No need to modify it — the dynamic endpoint renders the correct schema with injected base URL and paths.**
2. Configure the `Authorization` header with `Bearer your_gpt_secret` in your GPT setup.
3. Ensure the API server is reachable over HTTPS at the declared domain and under the endpoint prefix you defined.
4. Your GPT will now be able to list, read, create, update, and rename pages within the sandboxed Confluence space for that endpoint.

## 📄 License

MIT License

## 🙌 Credits

Developed by Jan Chimiak.

---

For questions, improvements or ideas — feel free to open an issue or PR.