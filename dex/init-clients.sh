#!/bin/bash
# Run once after `docker compose up --build` to create the three OAuth clients in Dex.
# After this, use UpdateClient to add/remove redirect URIs freely without restarting.
set -e

PROTO=/tmp/dex_api.proto
HOST=localhost:5557

if [ ! -f "$PROTO" ]; then
  echo "Downloading Dex API proto..."
  curl -sSf -o "$PROTO" https://raw.githubusercontent.com/dexidp/dex/v2.41.1/api/v2/api.proto
fi

echo "Waiting for Dex gRPC on $HOST..."
for i in $(seq 1 30); do
  if grpcurl -plaintext -import-path /tmp -proto dex_api.proto \
    -d '{}' "$HOST" api.Dex/ListClients > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

create_client() {
  local name="$1"
  local data="$2"
  echo "Creating $name..."
  grpcurl -plaintext -import-path /tmp -proto dex_api.proto \
    -d "$data" "$HOST" api.Dex/CreateClient 2>&1 | grep -v 'already_exists' || true
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

echo ""
echo "Clients ready. To add a Scalekit redirect URI run:"
echo ""
echo "  ./dex/add-redirect-uri.sh <REDIRECT_URI>"
echo ""
