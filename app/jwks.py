from __future__ import annotations

import json
import threading
import time
import urllib.request

from .config import OIDC_BACKEND_URL, OIDC_JWKS_CACHE_TTL


class _RemoteJWKSClient:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, dict] = {}  # kid -> full JWK dict (includes "alg", "kty", etc.)
        self._fetched_at: float = 0.0

    def get_key(self, kid: str) -> dict:
        with self._lock:
            now = time.time()
            if kid not in self._keys or (now - self._fetched_at) > OIDC_JWKS_CACHE_TTL:
                self._refresh()
            if kid not in self._keys:
                raise KeyError(f"Unknown kid: {kid}")
            return self._keys[kid]

    def _refresh(self) -> None:
        url = f"{OIDC_BACKEND_URL.rstrip('/')}/keys"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        new_keys: dict[str, dict] = {}
        for k in data.get("keys", []):
            if "kid" not in k:
                continue
            new_keys[k["kid"]] = k  # store the full JWK dict as-is
        self._keys = new_keys
        self._fetched_at = time.time()


jwks_client = _RemoteJWKSClient()
