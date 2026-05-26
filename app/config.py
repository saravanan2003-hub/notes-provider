import os

ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "dev-admin-key")

OIDC_ISSUER_URL: str = os.environ.get("OIDC_ISSUER", "http://localhost:8000")
OIDC_BACKEND_URL: str = os.environ.get("OIDC_BACKEND_URL", OIDC_ISSUER_URL)
OIDC_ACCEPTED_AUDIENCES: list[str] = [
    a.strip()
    for a in os.environ.get("OIDC_ACCEPTED_AUDIENCES", "").split(",")
    if a.strip()
]
OIDC_JWKS_CACHE_TTL: int = int(os.environ.get("OIDC_JWKS_CACHE_TTL", "300"))
OIDC_LEEWAY_SECONDS: int = int(os.environ.get("OIDC_LEEWAY_SECONDS", "30"))
MACHINE_USER_PREFIX: str = "machine:"

BASIC_USERS: dict[str, str] = {
    "e2e-basic-user": "e2e-basic-pass",
}

BEARER_TOKENS: dict[str, str] = {
    "e2e-bearer-token-abc12345": "e2e-bearer-user",
}

API_KEYS: dict[str, str] = {
    "e2e-apikey-abc12345": "e2e-apikey-user",
}
