from __future__ import annotations

import base64
import logging
from contextvars import ContextVar
from typing import Optional, Tuple

from fastapi import Request, HTTPException
from jose import jwt, JWTError, ExpiredSignatureError

from .config import (
    BASIC_USERS,
    BEARER_TOKENS,
    API_KEYS,
    OIDC_ISSUER_URL,
    OIDC_ACCEPTED_AUDIENCES,
    OIDC_LEEWAY_SECONDS,
    MACHINE_USER_PREFIX,
)

logger = logging.getLogger(__name__)

_auth_context: ContextVar[Optional[Tuple[str, str]]] = ContextVar("_auth_context", default=None)


def get_current_user() -> Tuple[str, str]:
    val = _auth_context.get()
    if val is None:
        raise HTTPException(status_code=401, detail="Unauthenticated")
    return val


def set_auth_context(user_id: str, scheme: str) -> None:
    _auth_context.set((user_id, scheme))


def clear_auth_context() -> None:
    _auth_context.set(None)


def _validate_oidc_token(token: str) -> Optional[Tuple[str, str]]:
    """Validate a JWT issued by our OIDC provider. Returns (user_id, scheme) or None."""
    from .jwks import jwks_client

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as e:
        logger.debug("oidc_validate: bad header: %s", e)
        return None

    kid = header.get("kid")
    if not kid:
        logger.debug("oidc_validate: no kid in header")
        return None

    try:
        jwk = jwks_client.get_key(kid)
    except KeyError:
        logger.debug("oidc_validate: kid=%s not found in JWKS", kid)
        return None

    alg = jwk.get("alg") or header.get("alg")
    if not alg:
        logger.debug("oidc_validate: no alg")
        return None

    try:
        payload = jwt.decode(
            token,
            jwk,
            algorithms=[alg],
            issuer=OIDC_ISSUER_URL,
            options={
                "verify_aud": False,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
                "leeway": OIDC_LEEWAY_SECONDS,
                "verify_at_hash": False,
            },
        )
    except JWTError as e:
        logger.warning("oidc_validate: jwt.decode failed: %s", e)
        raise

    aud = payload.get("aud")
    aud_list: list[str] = aud if isinstance(aud, list) else ([aud] if aud else [])
    if OIDC_ACCEPTED_AUDIENCES and not any(a in OIDC_ACCEPTED_AUDIENCES for a in aud_list):
        return None

    sub: str = payload.get("sub", "")
    if sub in OIDC_ACCEPTED_AUDIENCES and "email" not in payload:
        return (f"{MACHINE_USER_PREFIX}{sub}", "oauth_cc")
    return (sub, "oauth")


def resolve_user(request: Request) -> Tuple[str, str]:
    auth_header = request.headers.get("Authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        result = _validate_oidc_token(token)
        if result is not None:
            return result
        if token in BEARER_TOKENS:
            return (BEARER_TOKENS[token], "bearer")
        raise HTTPException(
            status_code=401,
            detail="invalid_token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid Basic credentials")
        if BASIC_USERS.get(username) == password:
            return (username, "basic")
        raise HTTPException(status_code=401, detail="Invalid Basic credentials")

    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        if api_key in API_KEYS:
            return (API_KEYS[api_key], "api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="notes", '
                f'authorization_uri="{OIDC_ISSUER_URL}/auth", '
                f'token_uri="{OIDC_ISSUER_URL}/token", '
                f'Basic, ApiKey'
            )
        },
    )


def resolve_user_for_mcp(request: Request) -> Tuple[str, str]:
    """Like resolve_user but returns expired-token hint when OIDC JWT has expired."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            result = _validate_oidc_token(token)
            if result is not None:
                return result
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="token expired",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="token expired"'},
            )
        except JWTError:
            pass

        if token in BEARER_TOKENS:
            return (BEARER_TOKENS[token], "bearer")
        raise HTTPException(
            status_code=401,
            detail="invalid_token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    return resolve_user(request)
