import logging
import os
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .auth import clear_auth_context, resolve_user_for_mcp, set_auth_context
from .mcp_server import mcp
from .routes_admin import router as admin_router
from .routes_notes import router as notes_router

_OIDC_BASE = os.environ.get("OIDC_BACKEND_URL", "http://localhost:5556").rstrip("/")
_OIDC_PROXY_PATHS = ("/auth", "/token", "/keys", "/.well-known", "/theme", "/static")
logging.basicConfig(
    level=logging.DEBUG,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# Trigger lazy session-manager creation before lifespan runs
_mcp_asgi = mcp.streamable_http_app()


class MCPAuthMiddleware:
    """ASGI middleware: resolves auth, sets ContextVar, then delegates to the MCP app."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request_id = str(uuid.uuid4())[:8]

        try:
            user_id, scheme = resolve_user_for_mcp(request)
        except HTTPException as exc:
            response = JSONResponse(
                {"error": exc.detail},
                status_code=exc.status_code,
                headers=dict(exc.headers or {}),
            )
            await response(scope, receive, send)
            logger.info("auth_failed request_id=%s status=%s", request_id, exc.status_code)
            return
        except Exception:
            logger.exception("mcp_auth_error request_id=%s", request_id)
            response = JSONResponse({"error": "internal_error"}, status_code=500)
            await response(scope, receive, send)
            return

        set_auth_context(user_id, scheme)
        logger.info("mcp_request request_id=%s user_id=%s scheme=%s", request_id, user_id, scheme)
        try:
            await self.app(scope, receive, send)
        finally:
            clear_auth_context()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Notes Provider", version="1.0.0", lifespan=lifespan)

app.include_router(admin_router)
app.include_router(notes_router)

app.mount("/mcp", MCPAuthMiddleware(_mcp_asgi))


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def oidc_proxy(path: str, request: Request):
    full_path = "/" + path
    if not any(full_path.startswith(p) for p in _OIDC_PROXY_PATHS):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    url = _OIDC_BASE + full_path
    if request.url.query:
        url += "?" + request.url.query
    body = await request.body()
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=body,
            follow_redirects=False,
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )
