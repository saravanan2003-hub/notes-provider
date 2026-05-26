# Notes Provider

A FastAPI app that exposes a Notes CRUD surface over MCP (Streamable-HTTP) and REST. It includes a built-in Python OIDC provider so the whole stack runs as **one process on one port** — no Dex, no Docker required for local dev. Used as a custom Scalekit Agentkit provider in E2E tests.

## Quick Start (local)

```bash
cd notes_provider
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Verify:
```bash
curl http://localhost:8000/healthz                              # {"status":"ok"}
curl http://localhost:8000/.well-known/openid-configuration    # OIDC discovery doc
```

## Test Users

| Email | Password | `sub` |
|---|---|---|
| `alice@example.com` | `alice-pass` | `user-alice` |
| `bob@example.com` | `bob-pass` | `user-bob` |
| `carol@example.com` | `carol-pass` | `user-carol` |

## Auth Schemes

All four schemes are accepted on `/mcp` and `/notes/*`.

### Basic Auth
```bash
curl -u e2e-basic-user:e2e-basic-pass http://localhost:8000/notes
```

### Bearer Token (static)
```bash
curl -H "Authorization: Bearer e2e-bearer-token-abc12345" http://localhost:8000/notes
```

### API Key
```bash
curl -H "X-API-Key: e2e-apikey-abc12345" http://localhost:8000/notes
```

### OAuth 2.0

#### Auth Code + PKCE (public client `notes-public-pkce`)

Generate verifier + challenge:
```bash
VERIFIER=$(python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode())")
CHALLENGE=$(python3 -c "import sys,hashlib,base64; v=sys.argv[1]; print(base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b'=').decode())" "$VERIFIER")
```

Open in browser (login as alice):
```
http://localhost:8000/auth?client_id=notes-public-pkce&response_type=code&scope=openid%20offline_access%20profile%20email&code_challenge=$CHALLENGE&code_challenge_method=S256&redirect_uri=http://localhost:8765/callback&state=xyz
```

Exchange code for tokens:
```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=authorization_code" \
  -d "code=<code>" \
  -d "code_verifier=$VERIFIER" \
  -d "client_id=notes-public-pkce" \
  -d "redirect_uri=http://localhost:8765/callback"
# → {"access_token":"<jwt>","id_token":"<jwt>","refresh_token":"<opaque>","token_type":"bearer",...}
```

#### Auth Code (confidential client `notes-confidential`)

```
http://localhost:8000/auth?client_id=notes-confidential&response_type=code&scope=openid%20offline_access%20profile%20email&redirect_uri=http://localhost:8765/callback&state=xyz
```

Exchange (client_secret required):
```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=authorization_code" \
  -d "code=<code>" \
  -d "client_id=notes-confidential" \
  -d "client_secret=notes-confidential-secret" \
  -d "redirect_uri=http://localhost:8765/callback"
```

#### Refresh Token

```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=<refresh_token>" \
  -d "client_id=notes-confidential" \
  -d "client_secret=notes-confidential-secret"
```

#### Client Credentials (`notes-machine`)

```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=client_credentials" \
  -d "client_id=notes-machine" \
  -d "client_secret=notes-machine-secret" \
  -d "scope=openid"
# → access_token with sub="notes-machine" (no email)
# Notes Provider maps this to principal: machine:notes-machine
```

## Token Validation

The Notes Provider validates Bearer tokens by:
1. Checking `alg=RS256` and `kid` in the JWT header.
2. Looking up the RSA public key in-process (same app generated it — no HTTP hop).
3. Verifying signature, `iss`, `exp`, `nbf`.
4. Checking `aud` contains a known client ID.
5. User tokens: principal = `sub` (e.g. `user-alice`).
6. Machine tokens: principal = `machine:{sub}` (no `email` claim).

Static Bearer (`e2e-bearer-token-abc12345`) is still accepted as a fallback when the token isn't an RS256 JWT.

## MCP Tools

Five tools available (require `Accept: application/json, text/event-stream`):

| Tool | Input | Output |
|---|---|---|
| `create_note` | `title`, `body` | note object with `id` |
| `get_note` | `id` | note object |
| `list_notes` | `limit?`, `offset?` | `{notes, total}` |
| `update_note` | `id`, `title?`, `body?` | updated note |
| `delete_note` | `id` | `{deleted: true, id}` |

Each tool operates on the authenticated user's namespace.

## REST Endpoints

```
POST   /notes          → create note (201)
GET    /notes          → list notes (?limit=20&offset=0)
GET    /notes/{id}     → get note
PUT    /notes/{id}     → update note
DELETE /notes/{id}     → delete note
```

## Admin Surface (test-only)

Protected by `X-Admin-Key` header.

```bash
# List all notes for a user
curl -H "X-Admin-Key: dev-admin-key" "localhost:8000/__admin/notes?user_id=user-alice"

# Delete all notes for a user
curl -X DELETE -H "X-Admin-Key: dev-admin-key" "localhost:8000/__admin/notes?user_id=user-alice"
```

## Adding to Scalekit

### Prerequisites: expose locally with ngrok

```bash
# Terminal 1: start the app with your public URL
OIDC_ISSUER=https://abc123.ngrok.app \
OIDC_ACCEPTED_AUDIENCES=notes-public-pkce,notes-confidential,notes-machine \
uvicorn app.main:app --port 8000

# Terminal 2: open the tunnel
ngrok http 8000
```

### OAuth Connection

In the Scalekit dashboard → Connections → New:

| Field | Value |
|---|---|
| Authorization URL | `https://abc123.ngrok.app/auth` |
| Token URL | `https://abc123.ngrok.app/token` |
| Client ID | `notes-confidential` |
| Client Secret | `notes-confidential-secret` |
| Scopes | `openid profile email offline_access` |

After saving, Scalekit shows a **redirect URI** (e.g. `https://api.scalekit.com/v1/connections/<id>/callback`). Restart the app with that URI added:

```bash
OIDC_ISSUER=https://abc123.ngrok.app \
OIDC_ACCEPTED_AUDIENCES=notes-public-pkce,notes-confidential,notes-machine \
EXTRA_REDIRECT_URIS=https://api.scalekit.com/v1/connections/<id>/callback \
uvicorn app.main:app --port 8000
```

Then create a **Connected Account** → click the magic link → login as `alice@example.com` / `alice-pass`. Status = ACTIVE.

### Basic Connection

| Field | Value |
|---|---|
| Username | `e2e-basic-user` |
| Password | `e2e-basic-pass` |

### Bearer Token Connection

| Field | Value |
|---|---|
| Token | `e2e-bearer-token-abc12345` |

### API Key Connection

| Field | Value |
|---|---|
| Header name | `X-API-Key` |
| Value | `e2e-apikey-abc12345` |

## Environment Variables

| Var | Default | Notes |
|---|---|---|
| `OIDC_ISSUER` | `http://localhost:8000` | Public URL of this app — must match `iss` claim in tokens |
| `OIDC_ACCEPTED_AUDIENCES` | `""` (accept any) | Comma-separated client IDs |
| `OIDC_LEEWAY_SECONDS` | `30` | Clock-skew tolerance for JWT `exp` |
| `EXTRA_REDIRECT_URIS` | `""` | Comma-separated redirect URIs to whitelist (add Scalekit's callback here) |
| `ADMIN_API_KEY` | `dev-admin-key` | Gates `/__admin/*` |
| `ACCESS_TOKEN_TTL` | `3600` | Token lifetime in seconds |
| `REFRESH_TOKEN_TTL` | `86400` | Refresh token lifetime in seconds |

## Docker

```bash
docker compose up          # builds and starts the merged app on port 8000
```
