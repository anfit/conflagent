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

## 📂 Project Structure

```
conflagent/
├── conflagent.py                   # Flask application implementing the API
├── openapi_conflagent.json        # OpenAPI 3.1 schema describing the API interface (update servers.url before use)
├── confluence.properties.example  # Example configuration file
├── conflagent                     # Example Nginx site configuration (reverse proxy)
├── conflagent.service             # Systemd unit file for Gunicorn deployment
```

## 🛠 Setup

Basic setup instructions are included below. For more detailed deployment steps, refer to [SETUP.md](./SETUP.md).

### 1. Install requirements
```bash
pip install flask requests gunicorn
```

### 2. Configure the application
Copy the example config:
```bash
cp confluence.properties.example confluence.properties
```

Edit `confluence.properties` to match your environment:
```
email = your@email.com
api_token = your_api_token_generated_at_id.atlassian.com
base_url = https://your-domain.atlassian.net/wiki
space_key = YOURSPACE
root_page_id = 1234567890
gpt_shared_secret = your_gpt_secret_key
```

### 3. Run the server
Development mode:
```bash
python conflagent.py
```

Production mode via Gunicorn:
```bash
gunicorn -w 4 -b 127.0.0.1:8000 conflagent:app
```

### 4. HTTPS Deployment
Use the provided Nginx configuration and a TLS certificate to expose the API securely. Detailed instructions in [SETUP.md](./SETUP.md).

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

## 🚥 Deployment

- **Nginx Reverse Proxy:** Configure using the included `conflagent` site file under `/etc/nginx/sites-available/`, then enable it with a symlink to `sites-enabled/`.
- **Systemd Service:** Use `conflagent.service` to manage the Gunicorn process as a service.

See [SETUP.md](./SETUP.md) for full deployment details.

## 📄 License

MIT License (or specify your desired license here)

## 🙌 Credits

Developed by [Your Name or Organization].

---

For questions, improvements or ideas — feel free to open an issue or PR.
