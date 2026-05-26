# Build Notes Provider App (MCP, 4 auth schemes)

## Context

Scalekit Agentkit custom providers only speak **MCP** (Model Context Protocol). To get true E2E coverage we need a third-party app we fully control — a small **Notes** application — that exposes a CRUD surface over MCP and supports **all four authentication schemes** at its login layer (Basic, Bearer, API Key, OAuth 2.0). The user will register this app as a custom provider in their staging Scalekit account; test cases that exercise that registration come **later** and are out of scope for this plan.

What this plan covers:
1. Building the Notes app: MCP server, 5 CRUD tools, 4 auth schemes, in-memory store, OAuth 2.0 endpoints.
2. Deploying it to a stable staging URL.
3. A short outline (not a design) of how future test cases will consume it.

What is **not** in this plan:
- Scalekit-side provider/connection/connected-account setup (user handles in staging dashboard).
- Test case implementation (separate plan once the app is running).

---

## Architecture

```
                ┌──────────────────────────────────────────────┐
                │  Notes Provider App  (FastAPI, staging URL)  │
                │                                              │
   Scalekit ───▶│  /mcp     ◀── MCP Streamable-HTTP transport  │
   (custom      │   │           routes 5 tools to handlers     │
   provider)    │   ▼                                          │
                │  Auth middleware (resolves user from header) │
                │   │     ┌──────────────────────────┐         │
                │   │     │ Basic   Bearer   API Key │         │
                │   │     │ OAuth-JWT (issued here)  │         │
                │   │     └──────────────────────────┘         │
                │   ▼                                          │
                │  NotesStore  {user_id: {note_id: Note}}      │
                │   ▲                                          │
                │   │                                          │
                │  /oauth/{authorize, token}                   │
                │   - auto_approve=true skips consent          │
                │   - HS256 JWT access tokens (2 min TTL)      │
                │   - opaque refresh tokens (30 day TTL)       │
                │                                              │
                │  /healthz, /__admin/notes (test-only)        │
                └──────────────────────────────────────────────┘
```

---

## Notes Provider App

**Location:** `notes_provider/` (top-level folder in this repo, deployed to staging)  
**Stack:** Python 3.11 + FastAPI + uvicorn + official `mcp` Python SDK  
**Persistence:** in-memory dict, namespaced per resolved user — `{user_id: {note_id: Note}}`. Resets on restart; per-user namespacing keeps requests isolated.

### File layout

```
notes_provider/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app, mounts /mcp + /oauth + /healthz + /__admin
│   ├── mcp_server.py      # MCP server: 5 tools wired to NotesStore
│   ├── auth.py            # Multi-scheme auth resolver (Basic/Bearer/API Key/OAuth JWT)
│   ├── routes_oauth.py    # /oauth/authorize, /oauth/token
│   ├── routes_admin.py    # /__admin/notes (test verification surface, single admin key)
│   ├── store.py           # NotesStore: in-mem dict, per-user
│   ├── models.py          # Pydantic: Note, CreateNoteRequest, UpdateNoteRequest, TokenResponse
│   └── config.py          # Static creds, JWT secret, admin key, OAuth clients
├── requirements.txt       # fastapi, uvicorn[standard], python-jose, pydantic, mcp
├── Dockerfile             # python:3.11-slim, uvicorn entry, $PORT from env
└── README.md              # local run, auth examples, MCP handshake, deploy notes
```

---

## MCP Server — the production surface

Mounted at `/mcp` on the same FastAPI app. Transport: **Streamable HTTP** (`mcp.server.streamable_http`), which is the transport Scalekit expects for custom MCP providers.

Five tools, each accepting a JSON Schema input and returning structured JSON:

| Tool name | Input | Output |
|---|---|---|
| `create_note` | `{title: string, body: string}` | `{id, title, body, created_at}` |
| `get_note` | `{id: string}` | `{id, title, body, created_at, updated_at}` |
| `list_notes` | `{limit?: int, offset?: int}` | `{notes: [...], total: int}` |
| `update_note` | `{id, title?: string, body?: string}` | updated note |
| `delete_note` | `{id: string}` | `{deleted: true, id}` |

Each tool handler:
1. Reads the resolved `user_id` from the request context (set by the auth middleware).
2. Delegates to `NotesStore` with that `user_id`.
3. Returns a structured result; errors raise `mcp.shared.exceptions.McpError` with appropriate codes (`NOT_FOUND` for missing ids, `INVALID_PARAMS` for bad input).

The MCP `initialize` handshake advertises tool definitions only; no resources or prompts are exposed.

---

## Auth Middleware — supports all 4 schemes

`app/auth.py → resolve_user(request) -> (user_id, scheme)` is invoked on every `/mcp` request. It inspects headers in this order and returns the first match:

1. `Authorization: Bearer <token>`
   - First try **OAuth JWT validation** (HS256, `JWT_SECRET`). If `sub` claim resolves → `(sub, "oauth")`.
   - Else look up `<token>` in `BEARER_TOKENS` map → `(user_id, "bearer")`.
2. `Authorization: Basic <b64(user:pass)>` — decode, look up in `BASIC_USERS` → `(user_id, "basic")`.
3. `X-API-Key: <key>` — look up in `API_KEYS` → `(user_id, "api_key")`.
4. No match → `401` with `WWW-Authenticate: Bearer, Basic` header.

The resolver writes `(user_id, scheme)` onto a `contextvars.ContextVar` so MCP tool handlers (which don't directly see the HTTP request) can read it. A small ASGI middleware wraps the MCP mount to set/clear the ContextVar around each request.

---

## OAuth 2.0 — Authorization Code Grant

### Endpoints

**`GET /oauth/authorize`** — params: `client_id`, `redirect_uri`, `state`, `scope`, `response_type=code`, optional `auto_approve=true`
- `auto_approve=true` → immediately `302` to `redirect_uri?code=...&state=...` (no browser needed for automated flows).
- Otherwise renders a tiny HTML consent page with Approve/Deny buttons (for manual exploration only).

**`POST /oauth/token`** — accepts:
- `grant_type=authorization_code` with `code`, `client_id`, `client_secret`, `redirect_uri`
- `grant_type=refresh_token` with `refresh_token`, `client_id`, `client_secret`

Returns: `{access_token, refresh_token, expires_in, token_type: "Bearer", scope}`

### Tokens

**Access token** — signed JWT (HS256, `JWT_SECRET`) with `sub=user_id`, `exp`, `scope`, `iss="notes-provider"`.
- **Lifetime: 2 minutes (120 seconds)** — deliberately short so test cases can observe the token expiring and verify Scalekit automatically calls `/oauth/token` with `grant_type=refresh_token` to mint a new one before retrying the tool call.
- Configurable via `ACCESS_TOKEN_TTL_SECONDS` env var (default `120`).
- When an expired token hits `/mcp`, the response is `401` with:
  ```
  WWW-Authenticate: Bearer error="invalid_token", error_description="token expired"
  ```
  This is the standard signal Scalekit's MCP client looks for to trigger a refresh.

**Refresh token** — opaque random 32-byte URL-safe string, stored in-mem with `(user_id, client_id, expires_at)`.
- Lifetime: 30 days (`REFRESH_TOKEN_TTL_SECONDS`, default `2592000`).
- Rotation enabled by default (`REFRESH_TOKEN_ROTATE=true`): each refresh issues a new refresh token and invalidates the old one. Reusing a rotated refresh token returns `400 invalid_grant`.

### Static OAuth clients (config.py)

```python
OAUTH_CLIENTS = {
    "e2e-oauth-client": {
        "client_secret": <from env OAUTH_CLIENT_SECRET>,
        "user_id": "e2e-oauth-user",
        "redirect_uris": ["https://app.scalekit.com/oauth/callback"],
    },
}
```

---

## Static Credentials (config.py)

```python
BASIC_USERS    = {"e2e-basic-user":  "e2e-basic-pass"}
BEARER_TOKENS  = {"e2e-bearer-token-xxxxxxxx": "e2e-bearer-user"}
API_KEYS       = {"e2e-apikey-xxxxxxxx":       "e2e-apikey-user"}
ADMIN_API_KEY  = <from env ADMIN_API_KEY>   # /__admin/* only
JWT_SECRET     = <from env JWT_SECRET>
```

---

## Admin Surface — test verification only

`GET /__admin/notes?user_id=...` and `DELETE /__admin/notes?user_id=...`  
Protected by `X-Admin-Key: <ADMIN_API_KEY>`. Tests use this for state assertions and cleanup — it is not part of the MCP/provider surface visible to Scalekit.

---

## Health + Ops

- `GET /healthz` → `{"status": "ok"}` — platform health check.
- Structured JSON logs to stdout: `auth_scheme`, `tool_name`, `user_id`, `request_id` on every request.

---

## Deployment

**Dockerfile**: `python:3.11-slim`, install `requirements.txt`, `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$PORT"]`.  
Platform-agnostic — Render / Fly / Cloud Run / internal infra.

**Required env vars:**

| Var | Purpose |
|---|---|
| `PORT` | Platform-provided listen port |
| `JWT_SECRET` | Signs OAuth access tokens |
| `OAUTH_CLIENT_SECRET` | Secret for `e2e-oauth-client` |
| `ADMIN_API_KEY` | Gates `/__admin/*` routes |

**Optional env vars:**

| Var | Default | Notes |
|---|---|---|
| `ACCESS_TOKEN_TTL_SECONDS` | `120` | Short by design — enables refresh-flow testing |
| `REFRESH_TOKEN_TTL_SECONDS` | `2592000` | 30 days |
| `REFRESH_TOKEN_ROTATE` | `true` | Rotate refresh token on each use |

Single replica only — in-memory store does not survive multi-replica scale-out (acceptable for a test fixture).

---

## Local Dev

```bash
cd notes_provider
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

JWT_SECRET=dev OAUTH_CLIENT_SECRET=dev ADMIN_API_KEY=dev \
  uvicorn app.main:app --reload

# Smoke checks
curl localhost:8000/healthz
curl -u e2e-basic-user:e2e-basic-pass \
     "localhost:8000/__admin/notes?user_id=e2e-basic-user"
```

---

## How Future Test Cases Will Consume This App (outline only)

Once the Notes app is deployed and registered in Scalekit staging as a custom MCP provider, a separate test plan will be written. In brief, those tests will:

1. Read provider/connector ids and credentials from env vars (`NOTES_*`).
2. Use the existing `Connection.create_agentkit_connection`, `ConnectedAccount`, and `Tool.execute_tool` helpers in `api_functions/` to create one connection per auth scheme (Basic, Bearer, API Key, OAuth) and call each of the 5 CRUD tools.
3. Assert on (a) Scalekit's `execute_tool` response and (b) the Notes app's `/__admin/notes` view to confirm state actually changed in the backing store.
4. For OAuth specifically, tests will also verify the 2-minute token expiry triggers a transparent refresh before the tool call completes.
5. Use Faker-tagged note titles for per-test isolation; run safely under pytest-xdist.

---

## Open Items

1. **Staging hosting target** — Render / Fly / Cloud Run / internal? Affects deploy command.
2. **Public hostname** — will be the MCP provider URL set in Scalekit and `NOTES_PROVIDER_BASE_URL` for future tests.
3. **Unit test suite for the Notes app** — strongly recommended (~15 fast tests covering each auth scheme, each CRUD op, OAuth happy/refresh paths) to derisk before Scalekit-side registration. Confirm in/out of scope.

---

## Critical Files

**New files (all under `notes_provider/`)**

- `app/main.py`
- `app/mcp_server.py`
- `app/auth.py`
- `app/routes_oauth.py`
- `app/routes_admin.py`
- `app/store.py`
- `app/models.py`
- `app/config.py`
- `requirements.txt`
- `Dockerfile`
- `README.md`

No modifications to existing repo files at this stage.

---

## Verification Checklist

1. **Boots locally** — `curl localhost:8000/healthz` → `{"status":"ok"}`
2. **All 4 auth schemes accepted** on `/mcp`:
   - Basic: `curl -u e2e-basic-user:e2e-basic-pass ...` → 200
   - Bearer: `curl -H "Authorization: Bearer e2e-bearer-token-xxxxxxxx" ...` → 200
   - API Key: `curl -H "X-API-Key: e2e-apikey-xxxxxxxx" ...` → 200
   - OAuth JWT: complete authorize → token round-trip, then `curl -H "Authorization: Bearer <jwt>" ...` → 200
   - No auth: 401 with `WWW-Authenticate` header
3. **MCP handshake works** — `initialize` succeeds, `tools/list` returns 5 tools, `tools/call create_note` returns a note id
4. **MCP enforces auth** — `tools/call` with no/invalid auth returns `-32001` (unauthorized)
5. **Per-user isolation** — two different credentials see disjoint `list_notes` results
6. **OAuth refresh — short TTL end-to-end**:
   - Token response reports `expires_in: 120`
   - JWT `exp - iat == 120`
   - Token works against `/mcp` while valid
   - After 121 s (or force-expiry): `/mcp` returns `401 WWW-Authenticate: Bearer error="invalid_token"`
   - Refresh call → new access token + rotated refresh token; new token works
   - Old refresh token returns `invalid_grant`
7. **Refresh-token rotation reuse-detection** — second use of a rotated refresh token → `400 invalid_grant`
8. **Admin surface gated** — `/__admin/notes` without `X-Admin-Key` → 401; with key → returns rows
9. **Deployed and reachable** — `curl https://<NOTES_PROVIDER_BASE_URL>/healthz` → 200; MCP handshake over public URL succeeds
10. **README self-contained** — a teammate can run locally, hit all 4 auth schemes, and understand the 2-minute TTL design decision without asking questions

---

## Current architecture (v3 — merged single app)

Dex was considered and removed (it requires Go). The OIDC provider is now a **Python implementation** built into the same FastAPI app as the Notes Provider. There is **one process, one port (8000)**.

```
                     ┌──────────────────────────────────────────────┐
   user / Scalekit ─▶│  Notes Provider + OIDC (FastAPI, port 8000) │
                     │                                              │
                     │  OIDC endpoints (oidc_provider/router.py):   │
                     │    GET  /.well-known/openid-configuration    │
                     │    GET  /keys  (JWKS)                        │
                     │    GET  /auth  (login page)                  │
                     │    POST /auth/login                          │
                     │    POST /token                               │
                     │                                              │
                     │  Notes endpoints (app/):                     │
                     │    /notes  /mcp  /healthz  /__admin/*        │
                     │                                              │
                     │  JWT validation: in-process (no HTTP hop)    │
                     └──────────────────────────────────────────────┘
```

### OIDC clients

| Client ID | Type | Use |
|---|---|---|
| `notes-public-pkce` | public (no secret) | Auth Code + PKCE (S256) |
| `notes-confidential` | confidential | Auth Code |
| `notes-machine` | confidential | Client Credentials (M2M) |

### Test users

| Email | Password | `sub` |
|---|---|---|
| `alice@example.com` | `alice-pass` | `user-alice` |
| `bob@example.com` | `bob-pass` | `user-bob` |
| `carol@example.com` | `carol-pass` | `user-carol` |

### All four auth schemes

| Scheme | Header | Credential |
|---|---|---|
| Basic | `Authorization: Basic <b64>` | `e2e-basic-user` / `e2e-basic-pass` |
| Bearer (static) | `Authorization: Bearer <token>` | `e2e-bearer-token-abc12345` |
| API Key | `X-API-Key: <key>` | `e2e-apikey-abc12345` |
| OAuth 2.0 | `Authorization: Bearer <RS256 JWT>` | see OIDC clients above |

### Environment variables

| Var | Default | Notes |
|---|---|---|
| `OIDC_ISSUER` | `http://localhost:8000` | Public URL of this app — must match `iss` in tokens |
| `OIDC_ACCEPTED_AUDIENCES` | `""` (accept any) | Comma-separated client IDs |
| `OIDC_JWKS_CACHE_TTL` | `300` | No longer used (in-process key), kept for future |
| `OIDC_LEEWAY_SECONDS` | `30` | Clock-skew tolerance for JWT `exp` |
| `EXTRA_REDIRECT_URIS` | `""` | Comma-separated URIs to add to OAuth client allow-lists (for Scalekit callback) |
| `ADMIN_API_KEY` | `dev-admin-key` | For `/__admin/*` endpoints |

### How to run locally

```bash
# Start
uvicorn app.main:app --reload --port 8000

# With a public URL (ngrok tunnel for Scalekit)
OIDC_ISSUER=https://abc123.ngrok.app \
OIDC_ACCEPTED_AUDIENCES=notes-public-pkce,notes-confidential,notes-machine \
EXTRA_REDIRECT_URIS=https://api.scalekit.com/v1/connections/<id>/callback \
uvicorn app.main:app --port 8000
```

### Adding to Scalekit

**OAuth Connection:**
- Authorization URL: `<OIDC_ISSUER>/auth`
- Token URL: `<OIDC_ISSUER>/token`
- Client ID: `notes-confidential`
- Client Secret: `notes-confidential-secret`
- Scopes: `openid profile email offline_access`
- After creating the connection, copy Scalekit's redirect URI and set `EXTRA_REDIRECT_URIS=<that URI>`, then restart.

**Basic Connection:** username `e2e-basic-user`, password `e2e-basic-pass`

**Bearer Token Connection:** token value `e2e-bearer-token-abc12345`

**API Key Connection:** header `X-API-Key`, value `e2e-apikey-abc12345`
