# Deployment Guide

This guide covers deploying CoCai on a VPS under the subpath `https://yourdomain.com/coc-ai/`.

**Assumed environment**

| Item | Value |
|------|-------|
| OS | Debian 13 |
| Reverse proxy | Caddy |
| Deploy path | `/coc-ai/` |
| App port | **8003** (adjust if taken) |

---

## 1. Install system dependencies

```bash
# Run as root or with sudo
apt update && apt install -y git curl

# just (task runner)
curl --proto '=https' --tlsv1.2 -sSf \
  https://just.systems/install.sh | bash -s -- --to /usr/local/bin

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env   # or open a new shell
```

---

## 2. Deploy the project

```bash
# Create a dedicated user
useradd -m -s /bin/bash cocai

# Clone to /opt/cocai
git clone https://github.com/youruser/Cocai.git /opt/cocai
chown -R cocai:cocai /opt/cocai

# Install Python dependencies
su - cocai
cd /opt/cocai
uv sync
```

---

## 3. Configure config.toml and .env

```bash
# Fill in API base URLs and model names
nano /opt/cocai/config.toml

# Create .env from the example template
cp /opt/cocai/.env.example /opt/cocai/.env
nano /opt/cocai/.env   # fill in all API keys

# Generate the Chainlit session secret and add it to .env as CHAINLIT_AUTH_SECRET
cd /opt/cocai && uv run chainlit create-secret
```

---

## 4. Create a systemd service

```bash
# Run as root
cat > /etc/systemd/system/cocai.service << 'EOF'
[Unit]
Description=CoCai AI Game Master
After=network.target

[Service]
Type=simple
User=cocai
WorkingDirectory=/opt/cocai
ExecStart=/opt/cocai/.venv/bin/uvicorn server:app \
    --app-dir src \
    --host 127.0.0.1 \
    --port 8003 \
    --root-path /coc-ai
EnvironmentFile=/opt/cocai/.env
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now cocai
systemctl status cocai   # verify it started successfully
```

> **Why `--root-path /coc-ai`?**
> Starlette propagates `root_path` to every sub-application via the ASGI scope.
> Chainlit reads it to compute the correct Socket.IO path (`/coc-ai/chat/ws`).
> Without it, the browser would try to connect to `/chat/ws` (root-relative) and
> the WebSocket handshake would fail behind the reverse proxy.

---

## 5. Update the Caddyfile

Add the CoCai block **between the last `handle_path` service block and the `header` block**:

```caddyfile
	# CoCai - AI Game Master
	handle_path /coc-ai/* {
		reverse_proxy 127.0.0.1:8003 {
			header_up Host {host}
			header_up X-Real-IP {remote}
			# WebSocket support for Socket.IO (Chainlit)
			header_up Upgrade {http.request.header.Upgrade}
			header_up Connection {http.request.header.Connection}
		}
	}
```

> **Why `handle_path` and not `handle`?**
> `handle_path` strips the matched prefix (`/coc-ai`) before forwarding to the
> backend, so the app continues to handle routes as `/chat`, `/play`, `/api/events`,
> etc. without any changes to its own routing.

Then update the `Content-Security-Policy` line inside the existing `header` block.
The diff is three additions (marked with `+`):

```
script-src  ... + https://cdn.jsdelivr.net
style-src   ... + https://cdn.jsdelivr.net
img-src     ... + https:
```

Full updated line:

```caddyfile
Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.socket.io https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' https://pbs.twimg.com https:; connect-src 'self' wss://yourdomain.com https://api.currencyfreaks.com;"
```

| Addition | Reason |
|----------|--------|
| `cdn.jsdelivr.net` in `script-src` / `style-src` | Bootstrap JS/CSS and Split.js loaded by the play UI |
| `https:` in `img-src` | AI-generated images are served from various CDN origins (OpenRouter / Seedream); the exact host is not fixed |

Apply and reload:

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
```

---

## 6. Access URLs

| Page | URL |
|------|-----|
| Chat UI | `https://yourdomain.com/coc-ai/chat` |
| Play UI | `https://yourdomain.com/coc-ai/play` |

---

## Subpath compatibility — changes already applied to the repo

The following fixes are already committed so no manual edits are required:

| File | Change | Reason |
|------|--------|--------|
| `public/play.html` | `<iframe src="/chat">` → `<iframe src="chat">` | Absolute path `/chat` resolves to the domain root and 404s under a subpath; the relative form resolves correctly relative to the current page URL |
| `public/play.js` | `new EventSource('/api/events')` → derived from `window.location.pathname` | Same issue: absolute `/api/events` bypasses the `/coc-ai/` prefix; the dynamic form works in both local dev and production |
| `.chainlit/config.toml` | `custom_css = "/public/..."` → `custom_css = "public/..."` | Removing the leading `/` makes it a relative URL; the browser resolves it to `/coc-ai/chat/public/custom_chainlit.css`, which Caddy strips to `/chat/public/custom_chainlit.css` and Chainlit serves correctly |

---

## Routine operations

```bash
# View logs
journalctl -u cocai -f

# Restart after a code update
cd /opt/cocai && git pull && uv sync
systemctl restart cocai

# Stop / start
systemctl stop cocai
systemctl start cocai
```
