# SETUP.md — Deploying the Conflagent Server (Gunicorn + Nginx + HTTPS)

This document describes how to install and deploy the `conflagent` REST API server in production using **Gunicorn** behind **Nginx**, first via HTTP, then upgrading to HTTPS via **Let's Encrypt / Certbot**.

This setup exposes the `conflagent` API (defined in `conflagent.py`) under a public domain (e.g., `conflagent.someplace.eu`) for integration with tools like **Custom GPTs**.

---

## 📋 Requirements

- Ubuntu Linux server (tested on Ubuntu 22.04+)
- Python 3.10+ installed
- A **configured subdomain** (e.g., `conflagent.someplace.eu`) already pointing to your server IP address (via DNS A record)
- Firewall open for **ports 80 (HTTP)** and **443 (HTTPS)**

---

# Part 1 — Initial HTTP Setup (No SSL)

## ⚙️ 1. Install Required System Packages

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv nginx -y
```

---

## 🐍 2. Set Up Python Environment and Application

Navigate to your project directory (example: `/home/ubuntu/projects/conflagent`) and set up:

```bash
cd /home/ubuntu/projects/conflagent
python3 -m venv venv
source venv/bin/activate
pip install flask requests gunicorn
```

Test the server locally:

```bash
gunicorn -b 127.0.0.1:5000 conflagent:app
```

---

## 🔧 3. Configure Systemd Service (Gunicorn)

Use the systemd service file located in `deployment/`:

```bash
sudo cp deployment/conflagent.service /etc/systemd/system/conflagent.service
sudo systemctl daemon-reload
sudo systemctl enable conflagent
sudo systemctl start conflagent
```

Verify logs:

```bash
sudo journalctl -u conflagent -n 50 --no-pager
```

---

## 🌐 4. Set Up Nginx Reverse Proxy (HTTP only)

Use the HTTP-only configuration file:

```bash
sudo cp deployment/conflagent.http /etc/nginx/sites-available/conflagent
sudo ln -s /etc/nginx/sites-available/conflagent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

✅ At this point, your API is accessible via:
```
http://conflagent.someplace.eu/
```

Confirm that the site is publicly reachable before continuing to SSL setup.

---

# Part 2 — Upgrading to HTTPS (SSL/TLS)

## 🔐 5. Install Certbot

```bash
sudo apt install certbot python3-certbot-nginx -y
```

## 🔒 6. Obtain SSL Certificate (Let's Encrypt)

```bash
sudo certbot --nginx -d conflagent.someplace.eu
```

## 🆕 7. Switch to SSL Nginx Configuration

Replace the HTTP config with the SSL-enabled one:

```bash
sudo cp deployment/conflagent.ssl /etc/nginx/sites-available/conflagent
sudo nginx -t
sudo systemctl reload nginx
```

## 🔁 8. Redirect HTTP to HTTPS (Optional)

If not already in `conflagent.ssl`, ensure it contains a redirect block for HTTP to HTTPS.

---

## 🔄 9. Auto-Renewal of SSL Certificates

Verify Certbot timer:
```bash
sudo systemctl list-timers | grep certbot
```

Test dry run:
```bash
sudo certbot renew --dry-run
```

---

## ✅ 10. Verify Deployment

Check your endpoint:
```
https://conflagent.someplace.eu/health
```

---

## 📂 Additional Notes

- Configuration is from `confluence.properties` (see `confluence.properties.example`)
- API schema: `/openapi.json`
- Keep your GPT token secure at all times

---

## 📌 Summary

| Component | Role                            |
|----------|----------------------------------|
| Flask     | REST API app                    |
| Gunicorn  | Production WSGI server          |
| Nginx     | Reverse proxy and TLS endpoint  |
| Certbot   | HTTPS/SSL certificate manager   |

🔔 Don't forget to update the `servers.url` field in `openapi_conflagent.json` to match your final HTTPS domain.