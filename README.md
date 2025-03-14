# Conflagent – REST API Bridge to Confluence for Custom GPTs

**Conflagent** is a lightweight, standalone REST API service that acts as a bridge between a custom GPT (or any other HTTP client) and a sandboxed section of an Atlassian Confluence workspace. It allows programmatic listing, creation, reading, and updating of Confluence pages, enabling GPT-based document automation, intelligent assistants, or bot integrations.

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

- REST API secured via a pre-shared GPT secret (`X-GPT-Secret` header)
- Operations limited to a pre-defined Confluence space and root page
- Fully compatible with Custom GPTs via OpenAPI tool definition
- Minimal, self-contained Flask app with no external database
- OpenAPI schema served from `/openapi.json`
- Systemd and Nginx deployment-ready

## 📚 Use Case

Designed to integrate with a **Custom GPT Operator Tool**, this API allows a GPT to:
- **List** all subpages under a specified Confluence root page
- **Read** content of a child page by its title
- **Create** a new child page under the root
- **Update** an existing child page by title

This provides a clean way to expose a read/write Confluence sandbox to GPTs without exposing the entire Confluence workspace or admin API tokens.

## 🏗 Architecture Overview

Conflagent follows a minimal architecture for simplicity and portability:

```
Client (Custom GPT / HTTP client)
        │
        ▼
   [Nginx Reverse Proxy] ──▶ [Gunicorn WSGI Server] ──▶ [Flask App (conflagent.py)]
                                      │
                                      ▼
                            [Confluence REST API]
```

Deployment is managed via Systemd and served through Nginx (HTTP/HTTPS). SSL certificates can be provisioned via Let's Encrypt.

## 📂 Project Structure

```
conflagent/
├── conflagent.py                    # Flask application implementing the API
├── openapi_conflagent.json         # OpenAPI 3.1 schema describing the API interface (update servers.url before use)
├── confluence.properties.example   # Example configuration file
├── deployment/
│   ├── conflagent.http             # Nginx config for initial HTTP deployment
│   ├── conflagent.ssl              # Nginx config for HTTPS/SSL deployment
│   └── conflagent.service          # Systemd unit file for Gunicorn deployment
```

## ⚙️ Setup & Deployment

For full setup and deployment instructions, including HTTP → HTTPS transition, see: [SETUP.md](./SETUP.md)

## 🔐 Security Model

All protected operations require a pre-shared secret header:
```
X-GPT-Secret: your_gpt_secret
```
GPT tool calls must include this to access or modify Confluence content. The secret should be embedded in your Custom GPT configuration.

## 📘 API Endpoints (summary)

| Method | Path                | Description                              | Auth required |
|--------|---------------------|------------------------------------------|----------------|
| GET    | `/pages`            | List all subpages under the root         | ✅ Yes          |
| GET    | `/pages/{title}`    | Read a page by title                     | ✅ Yes          |
| POST   | `/pages`            | Create a new page under root             | ✅ Yes          |
| PUT    | `/pages/{title}`    | Update a page by title                   | ✅ Yes          |
| GET    | `/openapi.json`     | Get OpenAPI schema (for GPT integration) | ❌ No           |
| GET    | `/health`           | Health check                             | ❌ No           |

## 🤖 GPT Integration Guide

To integrate this API with a Custom GPT:
1. Upload or import `openapi_conflagent.json` into the GPT tool definition. **Before doing so, make sure you edit the file and replace the `servers.url` field (currently set to a placeholder) with the actual domain or IP address where your API is hosted.**
2. Configure the `X-GPT-Secret` header in your GPT setup.
3. Ensure the API server is reachable over HTTPS at the declared domain.
4. Your GPT will now be able to list, read, create, and update pages within the sandboxed Confluence space.

## 📄 License

MIT License (or specify your desired license here)

## 🙌 Credits

Developed by Jan Chimiak.

---

For questions, improvements or ideas — feel free to open an issue or PR.
