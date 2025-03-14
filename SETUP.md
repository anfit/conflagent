# SETUP.md — Deploying the Conflagent Server (Gunicorn + Nginx + HTTPS)

This document describes how to install and deploy the `conflagent` REST API server in production using **Gunicorn** behind **Nginx**, with optional HTTPS support via **Let's Encrypt / Certbot**.

This setup is intended to expose the `conflagent` API (defined in `conflagent.py`) securely under a public domain (e.g., `conflagent.someplace.eu`) for integration with tools like **Custom GPTs**.

---

## 📋 Requirements

- Ubuntu Linux server (tested on Ubuntu 22.04+)
- Python 3.10+ installed
- A valid domain (e.g., `conflagent.someplace.eu`) pointing to your server IP
- Ports **80 (HTTP)** and **443 (HTTPS)** open in the firewall

---

## ⚙️ 1. Install Required System Packages

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv nginx -y
```

---

## 🐍 2. Set Up Python Environment and Application

Navigate to your project directory (example: `/home/ubuntu/projects/conflagent`) and prepare the environment:

```bash
cd /home/ubuntu/projects/conflagent
python3 -m venv venv
source venv/bin/activate
pip install flask requests gunicorn
```

Ensure `conflagent.py` exists in the directory. You can test the server locally:

```bash
gunicorn -b 127.0.0.1:5000 conflagent:app
```

---

## 🔧 3. Configure Systemd Service (Gunicorn)

The repository includes an example service file: `conflagent.service`.

To install it system-wide:

```bash
sudo cp conflagent.service /etc/systemd/system/conflagent.service
sudo systemctl daemon-reload
sudo systemctl enable conflagent
sudo systemctl start conflagent
```

To verify logs:

```bash
sudo journalctl -u conflagent -n 50 --no-pager
```

---

## 🌐 4. Set Up Nginx Reverse Proxy

The repository also includes an example Nginx site config: `conflagent`.

Install it into your system:

```bash
sudo cp conflagent /etc/nginx/sites-available/conflagent
sudo ln -s /etc/nginx/sites-available/conflagent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

At this point, your API should be publicly accessible via `http://conflagent.someplace.eu/`.

---

## 🔒 5. Enable HTTPS via Let’s Encrypt (Recommended)

### Install Certbot:

```bash
sudo apt install certbot python3-certbot-nginx -y
```

### Obtain and configure SSL certificate:

```bash
sudo certbot --nginx -d conflagent.someplace.eu
```

### (Optional) Redirect HTTP to HTTPS:

If not handled automatically by Certbot, edit your Nginx config:

```nginx
server {
    listen 80;
    server_name conflagent.someplace.eu;
    return 301 https://$host$request_uri;
}
```

Then reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🔄 6. Auto-Renewal of SSL Certificates

Let’s Encrypt certificates auto-renew by default. Verify the timer:

```bash
sudo systemctl list-timers | grep certbot
```

You can test manual renewal:

```bash
sudo certbot renew --dry-run
```

---

## ✅ 7. Verify Deployment

Visit:
```
https://conflagent.someplace.eu/health
```

You should see a JSON hello message if the server is working correctly.

---

## 📂 Additional Notes

- Configuration options are loaded from `confluence.properties` (see `confluence.properties.example` in repo).
- API endpoints are defined in `openapi_conflagent.json`, available at `/openapi.json`.
- Be sure to keep your GPT secret token secure in both the server and GPT tool config.

---

## 📌 Summary

| Component | Role                            |
|----------|----------------------------------|
| Flask     | REST API app                    |
| Gunicorn  | Production WSGI server          |
| Nginx     | Reverse proxy and TLS endpoint  |
| Certbot   | HTTPS/SSL certificate manager   |

After completing this guide, your Conflagent API server is fully deployed and secured for GPT integration.

**📌 Note:** You must also update the `servers.url` field in `openapi_conflagent.json` to reflect your actual domain (e.g., `https://conflagent.yourdomain.com`) before uploading it to a GPT tool or client.

