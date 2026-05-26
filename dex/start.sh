#!/bin/sh
set -e

PROTO=/tmp/dex_api.proto
GRPC_HOST=localhost:15557

# 1. Download Dex API proto
if [ ! -f "$PROTO" ]; then
  echo "Downloading Dex API proto..."
  wget -q -O "$PROTO" "https://raw.githubusercontent.com/dexidp/dex/v2.41.1/api/v2/api.proto"
fi

# 2. Render $ISSUER into config
sed "s|\$ISSUER|${ISSUER}|g" /etc/dex/config.template.yaml > /etc/dex/config.docker.yaml

# 3. Start Dex in background
echo "Starting Dex..."
/usr/local/bin/dex serve /etc/dex/config.docker.yaml &

# 4. Wait for Dex gRPC to be ready (up to 30 seconds)
echo "Waiting for Dex gRPC on $GRPC_HOST..."
for i in $(seq 1 30); do
  if grpcurl -plaintext -import-path /tmp -proto dex_api.proto \
      -d '{}' "$GRPC_HOST" api.Dex/ListClients > /dev/null 2>&1; then
    echo "Dex gRPC is ready."
    break
  fi
  sleep 1
done

# 5. Create OAuth clients dynamically so they can be updated via gRPC later.
#    Static clients in dex.yaml are read-only via gRPC — dynamic ones are not.
create_client() {
  local name="$1"
  local data="$2"
  echo "Creating client: $name"
  grpcurl -plaintext -import-path /tmp -proto dex_api.proto \
    -d "$data" "$GRPC_HOST" api.Dex/CreateClient || true
}

create_client "notes-public-pkce" '{
  "client": {
    "id": "notes-public-pkce",
    "name": "Notes Public PKCE",
    "public": true,
    "redirect_uris": ["http://localhost:8765/callback", "http://127.0.0.1:8765/callback"]
  }
}'

create_client "notes-confidential" '{
  "client": {
    "id": "notes-confidential",
    "secret": "notes-confidential-secret",
    "name": "Notes Confidential",
    "redirect_uris": ["http://localhost:8765/callback", "http://127.0.0.1:8765/callback"]
  }
}'

create_client "notes-machine" '{
  "client": {
    "id": "notes-machine",
    "secret": "notes-machine-secret",
    "name": "Notes Machine",
    "redirect_uris": ["http://localhost:8765/callback", "http://127.0.0.1:8765/callback"]
  }
}'

echo "All clients ready. Starting management API on port 5556..."

# 6. Start management API in foreground (proxies OIDC traffic to Dex + management endpoints)
exec /opt/manage-venv/bin/uvicorn manage:app --host 0.0.0.0 --port 5556 --app-dir /etc/dex
