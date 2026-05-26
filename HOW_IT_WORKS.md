# How This Project Works — Beginner-Friendly Guide

If you are new to this project, start here. This guide explains everything from scratch — no prior knowledge needed.

---

## 1. What Is This Project?

This project is a **Notes app** — it lets users create, read, update, and delete notes (like a simple sticky-note app).

But it is not just any notes app. It is designed so that an **AI agent** (powered by Scalekit) can log in on behalf of a user and manage their notes automatically using a tool called **MCP** (Model Context Protocol).

So the two main things this project does:

1. **Let users log in** — using a username and password.
2. **Let AI agents call the Notes API** — after the user has logged in.

---

## 2. Two Programs Running at the Same Time

This project runs as **two separate programs** (called services or processes):

```
┌─────────────────────────────────────────────────────┐
│  Program 1: oidc-go  (written in Go language)        │
│  Runs on port 5556                                   │
│  Job: Handle login and issue tokens (like a          │
│       "security guard who checks ID and gives        │
│        you a badge")                                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Program 2: notes-provider  (written in Python)      │
│  Runs on port 8000                                   │
│  Job: Store and serve notes (like a "file cabinet    │
│       that only lets you in if you show your badge") │
└─────────────────────────────────────────────────────┘
```

Think of it like a **hotel**:
- `oidc-go` is the **reception desk** — it checks your identity and gives you a key card.
- `notes-provider` is the **hotel room** — it only lets you in if you show the key card.

---

## 3. What Is a Token?

When a user logs in successfully, the Go program creates a small piece of text called a **token** (also called a JWT — JSON Web Token).

This token:
- Contains information like "this is alice, she logged in at 10am, this expires at 11am".
- Is **digitally signed** so nobody can fake it or change it.
- Is sent to the Python app when the user (or AI agent) wants to access notes.
- Python checks the token is valid before allowing access.

Think of it like a **concert wristband** — the security at the gate (Go) puts it on your wrist, and the bar inside (Python) trusts it without calling the gate again.

---

## 4. How a Login Flow Works (Step by Step)

This is what happens when someone logs in using Scalekit:

```
Step 1: Scalekit sends the user to our login page
        → browser opens https://our-url/auth

Step 2: User types their email and password
        → e.g. alice@example.com / alice-pass

Step 3: Go checks the credentials
        → if correct, creates a "code" (a temporary ticket)
        → redirects browser back to Scalekit with the code

Step 4: Scalekit calls our /token endpoint with the code
        → Go exchanges the code for a proper token (JWT)
        → returns the token to Scalekit

Step 5: Scalekit stores the token
        → from now on, any API call to /notes or /mcp/ uses this token
```

---

## 5. How the Python App Checks If a Token Is Real

The Python app does not trust tokens blindly. Here is how it verifies one:

1. The Go program has a **private key** (like a secret stamp). It uses this to sign every token.
2. Go also publishes the **public key** at the URL `/keys` — anyone can read it.
3. When Python receives a token, it fetches the public key from Go and uses it to verify the token's signature.
4. If the signature matches → the token is real → Python allows the request.
5. If not → Python returns a 401 Unauthorized error.

Python fetches the public key once and **caches it for 5 minutes** (so it does not call Go every single time).

---

## 6. What Is the Proxy? (Why Does Python Forward Requests to Go?)

Here is a problem we solved:

- We use **ngrok** to make our local app reachable from the internet (so Scalekit can call it).
- The free ngrok plan gives you **only one public URL**.
- But we have **two programs** running on two different ports (5556 and 8000).

**Solution:** Expose only the Python app (port 8000) to the internet. When Python receives a request meant for Go (like `/auth` or `/token`), it **passes it along** to Go internally and sends Go's response back.

```
Internet → ngrok URL → Python :8000
                          │
                          ├── /notes, /mcp/  → handled by Python itself
                          │
                          └── /auth, /token, /keys → forwarded to Go :5556
                                                      → response sent back
```

This is called a **proxy** — Python acts as a middleman for OIDC requests.

---

## 7. Test Users (Built Into the App)

The app comes with 3 users already set up (hardcoded in the Go program). You can use these to test the login:

| Email | Password |
|---|---|
| `alice@example.com` | `alice-pass` |
| `bob@example.com` | `bob-pass` |
| `carol@example.com` | `carol-pass` |

These are **fake test users** — do not use real passwords here.

---

## 8. OAuth Clients (How the App Knows Who Is Calling)

When Scalekit calls `/token`, it identifies itself using a **client ID** and **client secret** — like a username and password for the app itself (not the end user).

Three clients are built in:

| Client ID | Client Secret | Use case |
|---|---|---|
| `notes-public-pkce` | (no secret) | Browser-based login with PKCE security |
| `notes-confidential` | `notes-confidential-secret` | Server-side app login |
| `notes-machine` | `notes-machine-secret` | Machine-to-machine (no user involved) |

For Scalekit integration, use `notes-confidential`.

---

## 9. Quick Credentials Reference

If you want to test the Notes API **without going through the full login flow**, use these:

| How to authenticate | What to send |
|---|---|
| Bearer token (in `Authorization` header) | `e2e-bearer-token-abc12345` |
| Basic auth (username / password) | `e2e-basic-user` / `e2e-basic-pass` |
| API key (in `X-API-Key` header) | `e2e-apikey-abc12345` |

Example:
```bash
curl -H "Authorization: Bearer e2e-bearer-token-abc12345" http://localhost:8000/notes
```

---

## 10. Notes API — What You Can Do

All requests need an `Authorization` header. Replace `$TOKEN` with a real token (see step 11 for how to get one).

### Create a note
```bash
curl -X POST http://localhost:8000/notes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello", "body": "My first note"}'
```

### List all your notes
```bash
curl http://localhost:8000/notes \
  -H "Authorization: Bearer $TOKEN"
```

### Get one note
```bash
curl http://localhost:8000/notes/<note_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Update a note
```bash
curl -X PUT http://localhost:8000/notes/<note_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated title", "body": "New content"}'
```

### Delete a note
```bash
curl -X DELETE http://localhost:8000/notes/<note_id> \
  -H "Authorization: Bearer $TOKEN"
```

---

## 11. Run It Locally (Start Both Programs)

Open **two terminal windows**.

### Terminal 1 — Start the Go OIDC service

```bash
cd notes_provider/oidc_go
go mod tidy
OIDC_ISSUER=http://localhost:5556 ADMIN_API_KEY=dev-admin-key go run ./cmd/server
```

You should see:
```
oidc-go listening on :5556 issuer=http://localhost:5556
```

### Terminal 2 — Start the Python Notes app

```bash
cd notes_provider
source .venv/bin/activate
OIDC_ISSUER=http://localhost:5556 \
OIDC_ACCEPTED_AUDIENCES=notes-public-pkce,notes-confidential,notes-machine \
OIDC_BACKEND_URL=http://localhost:5556 \
ADMIN_API_KEY=dev-admin-key \
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Check everything is working

```bash
# Should return {"status":"ok"}
curl http://localhost:8000/healthz

# Get a machine token (no user login needed)
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -d "grant_type=client_credentials" \
  -d "client_id=notes-machine" \
  -d "client_secret=notes-machine-secret" \
  -d "scope=openid" | jq -r .access_token)

# Use the token to list notes
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/notes
# Should return {"notes": [], "total": 0}
```

---

## 12. Expose to the Internet With ngrok (For Scalekit Testing)

Scalekit is a cloud service — it cannot reach `localhost`. Use ngrok to give your local app a public URL.

### Step 1 — Start ngrok on port 8000 only

```bash
ngrok http --url=rockstar-tile-saturday.ngrok-free.dev 8000
```

This gives you a public URL like `https://rockstar-tile-saturday.ngrok-free.dev`.

### Step 2 — Restart both programs with the public URL

Stop both programs (Ctrl+C) and restart them with the ngrok URL:

**Terminal 1 (Go):**
```bash
OIDC_ISSUER=https://rockstar-tile-saturday.ngrok-free.dev \
ADMIN_API_KEY=dev-admin-key \
go run ./cmd/server
```

**Terminal 2 (Python):**
```bash
OIDC_ISSUER=https://rockstar-tile-saturday.ngrok-free.dev \
OIDC_ACCEPTED_AUDIENCES=notes-public-pkce,notes-confidential,notes-machine \
OIDC_BACKEND_URL=http://localhost:5556 \
ADMIN_API_KEY=dev-admin-key \
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> **Important:** `OIDC_BACKEND_URL` always stays as `http://localhost:5556` — this is how Python reaches Go internally. Never set it to the ngrok URL.

---

## 13. Set Up the Scalekit Custom Connector

In the Scalekit dashboard, create a **Custom Connector** and fill in:

| Field | Value |
|---|---|
| Auth Strategy | OAuth 2.0 |
| Authorization URL | `https://rockstar-tile-saturday.ngrok-free.dev/auth` |
| Token URL | `https://rockstar-tile-saturday.ngrok-free.dev/token` |
| Client ID | `notes-confidential` |
| Client Secret | `notes-confidential-secret` |
| Scopes | `openid email offline_access` |
| MCP Server URL | `https://rockstar-tile-saturday.ngrok-free.dev/mcp/` |

> The trailing slash on `/mcp/` is required.

---

## 14. Register a Redirect URL Before Testing

When you create a Scalekit **Connection**, Scalekit gives you a redirect URL that looks like:

```
https://yourcompany.scalekit.cloud/sso/v1/oauth/conn_12345/callback
```

You need to **tell our Go app to allow this URL** before running the login flow. Otherwise the login will fail with a 400 error.

### Register the URL

```bash
curl -X POST https://rockstar-tile-saturday.ngrok-free.dev/__admin/redirect_uris \
  -H "X-Admin-Key: dev-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "https://yourcompany.scalekit.cloud/sso/v1/oauth/conn_12345/callback", "ttl_seconds": 600}'
```

### Check it was added

```bash
curl https://rockstar-tile-saturday.ngrok-free.dev/__admin/redirect_uris \
  -H "X-Admin-Key: dev-admin-key"
```

### Remove it after testing

```bash
curl -X DELETE \
  "https://rockstar-tile-saturday.ngrok-free.dev/__admin/redirect_uris?redirect_uri=https://yourcompany.scalekit.cloud/sso/v1/oauth/conn_12345/callback" \
  -H "X-Admin-Key: dev-admin-key"
```

---

## 15. Deploy With Docker (Run Everything in Containers)

If you have Docker installed, you can start both services with one command:

```bash
cd notes_provider
docker compose up --build
```

This builds and starts both `oidc-go` and `notes-provider` automatically.

> **One thing to add:** Open `docker-compose.yml` and add `OIDC_BACKEND_URL: "http://oidc-go:5556"` under the `notes-provider` environment section. Without this, Python cannot reach Go inside Docker.

---

## 16. Deploy to Render (Put It on the Internet Permanently)

Render is a cloud hosting platform. The file `render.yaml` at the root of `notes_provider/` describes how to deploy both services.

### Step 1 — Push your code to GitHub

Make sure all files are committed and pushed.

### Step 2 — Create a Blueprint on Render

1. Go to [render.com](https://render.com) → **New → Blueprint**.
2. Connect your GitHub repo.
3. Render reads `render.yaml` and creates two services: `notes-oidc-go` and `notes-provider`.

### Step 3 — Set these environment variables after first deploy

On **notes-oidc-go** (Go service):

| Variable | Value |
|---|---|
| `OIDC_ISSUER` | `https://notes-oidc-go.onrender.com` |

On **notes-provider** (Python service):

| Variable | Value |
|---|---|
| `OIDC_ISSUER` | `https://notes-oidc-go.onrender.com` |
| `OIDC_BACKEND_URL` | `https://notes-oidc-go.onrender.com` |
| `OIDC_ACCEPTED_AUDIENCES` | `notes-public-pkce,notes-confidential,notes-machine` |

### Step 4 — Set the same ADMIN_API_KEY on both services

By default Render generates a different key for each. Change both to the same value.

### Step 5 — Check it works

```bash
curl https://notes-provider.onrender.com/healthz
# → {"status":"ok"}
```

---

## 17. Common Errors and How to Fix Them

| What you see | Why it happened | How to fix it |
|---|---|---|
| `address already in use` on port 5556 | Go is already running from before | Run `lsof -ti:5556 \| xargs kill -9` to kill it |
| `go: cannot find main module` | You ran Go from the wrong folder | `cd notes_provider/oidc_go` first, then run Go |
| 404 on `/auth` via ngrok | Python proxy can't reach Go | Make sure Go is running and `OIDC_BACKEND_URL=http://localhost:5556` |
| Login works but `/notes` returns 401 | `OIDC_ISSUER` is different on Go vs Python | They must be the exact same URL on both |
| Everything 500 on Render | `OIDC_BACKEND_URL` is still pointing to localhost | Set it to `https://notes-oidc-go.onrender.com` on Render |
| 400 error on login redirect | Redirect URL not registered | Call `POST /__admin/redirect_uris` with the Scalekit redirect URL |

---

## 18. What the Files Do (Quick Reference)

| File | What it is |
|---|---|
| `oidc_go/cmd/server/main.go` | Entry point for the Go app — starts the server |
| `oidc_go/internal/config/config.go` | All settings (users, clients, env vars) for Go |
| `oidc_go/internal/keys/keys.go` | Generates the RSA key pair used to sign tokens |
| `oidc_go/internal/store/store.go` | In-memory storage for login codes and tokens |
| `oidc_go/internal/handlers/auth.go` | The login form (`/auth`) and login submit (`/auth/login`) |
| `oidc_go/internal/handlers/token.go` | The `/token` endpoint that gives out access tokens |
| `oidc_go/internal/handlers/admin.go` | The `/__admin/redirect_uris` API |
| `app/main.py` | Entry point for the Python app — sets up routes + proxy |
| `app/auth.py` | Checks every incoming request for a valid token |
| `app/jwks.py` | Fetches the public key from Go to verify tokens |
| `app/routes_notes.py` | The `/notes` REST API (create, list, get, update, delete) |
| `app/mcp_server.py` | The MCP tools (same as REST but for AI agents) |
| `app/routes_admin.py` | The `/__admin/notes` API for test cleanup |
| `docker-compose.yml` | Runs both services together with Docker |
| `render.yaml` | Deploys both services to Render cloud |
