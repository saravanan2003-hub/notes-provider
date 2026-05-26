import json
import os
import subprocess

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

app = FastAPI(title="Dex Management API")

MANAGE_API_KEY = os.environ.get("MANAGE_API_KEY", "dev-manage-key")
DEX_HTTP = "http://localhost:15556"
GRPC_HOST = "localhost:15557"
PROTO_PATH = "/tmp/dex_api.proto"
PROTO_URL = "https://raw.githubusercontent.com/dexidp/dex/v2.41.1/api/v2/api.proto"


def _require_admin(x_admin_key: str) -> None:
    if x_admin_key != MANAGE_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def _ensure_proto() -> None:
    if not os.path.exists(PROTO_PATH):
        subprocess.run(["wget", "-q", "-O", PROTO_PATH, PROTO_URL], check=True)


def _grpc(method: str, data: dict) -> dict:
    _ensure_proto()
    result = subprocess.run(
        [
            "grpcurl", "-plaintext",
            "-import-path", "/tmp",
            "-proto", "dex_api.proto",
            "-d", json.dumps(data),
            GRPC_HOST,
            f"api.Dex/{method}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"gRPC {method} failed: {result.stderr.strip() or result.stdout.strip()}",
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _get_uris(client_id: str) -> list[str]:
    result = _grpc("GetClient", {"id": client_id})
    return result.get("client", {}).get("redirectUris", [])


def _set_uris(client_id: str, uris: list[str]) -> None:
    _grpc("UpdateClient", {"id": client_id, "redirect_uris": uris})


# ── Management endpoints ──────────────────────────────────────────────────────

@app.get("/__manage/redirect-uris")
async def list_redirect_uris(
    client_id: str = "notes-confidential",
    x_admin_key: str = Header(...),
):
    _require_admin(x_admin_key)
    uris = _get_uris(client_id)
    return {"client_id": client_id, "redirect_uris": uris}


@app.post("/__manage/redirect-uri", status_code=200)
async def add_redirect_uri(request: Request, x_admin_key: str = Header(...)):
    _require_admin(x_admin_key)
    body = await request.json()
    redirect_uri = body.get("redirect_uri")
    client_id = body.get("client_id", "notes-confidential")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="redirect_uri is required")

    uris = _get_uris(client_id)
    if redirect_uri in uris:
        return {"ok": True, "action": "already_exists", "client_id": client_id, "redirect_uris": uris}

    uris.append(redirect_uri)
    _set_uris(client_id, uris)
    return {"ok": True, "action": "added", "client_id": client_id, "redirect_uris": uris}


@app.delete("/__manage/redirect-uri", status_code=200)
async def delete_redirect_uri(request: Request, x_admin_key: str = Header(...)):
    _require_admin(x_admin_key)
    body = await request.json()
    redirect_uri = body.get("redirect_uri")
    client_id = body.get("client_id", "notes-confidential")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="redirect_uri is required")

    uris = _get_uris(client_id)
    if redirect_uri not in uris:
        raise HTTPException(status_code=404, detail=f"{redirect_uri} is not registered")

    uris.remove(redirect_uri)
    _set_uris(client_id, uris)
    return {"ok": True, "action": "deleted", "client_id": client_id, "redirect_uris": uris}


# ── Proxy: forward everything else to Dex ────────────────────────────────────

@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_to_dex(path: str, request: Request):
    url = f"{DEX_HTTP}/{path}"
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5556, log_level="info")
