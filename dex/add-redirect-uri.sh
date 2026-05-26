#!/bin/bash
# Add a redirect URI to notes-confidential without restarting anything.
# Usage: ./dex/add-redirect-uri.sh <redirect_uri>
# Example: ./dex/add-redirect-uri.sh https://tenant.scalekit.cloud/sso/v1/oauth/conn_123/callback
set -e

NEW_URI="${1:?Usage: $0 <redirect_uri>}"
PROTO=/tmp/dex_api.proto
HOST=localhost:5557

if [ ! -f "$PROTO" ]; then
  curl -sSf -o "$PROTO" https://raw.githubusercontent.com/dexidp/dex/v2.41.1/api/v2/api.proto
fi

# Fetch current redirect URIs and append the new one
CURRENT=$(grpcurl -plaintext -import-path /tmp -proto dex_api.proto \
  -d '{"id":"notes-confidential"}' "$HOST" api.Dex/GetClient \
  | python3 -c "import sys,json; uris=json.load(sys.stdin)['client']['redirectUris']; print(json.dumps(uris))")

UPDATED=$(python3 -c "
import json, sys
uris = json.loads('$CURRENT')
new = '$NEW_URI'
if new not in uris:
    uris.append(new)
print(json.dumps(uris))
")

grpcurl -plaintext -import-path /tmp -proto dex_api.proto -d "{
  \"id\": \"notes-confidential\",
  \"redirect_uris\": $UPDATED
}" "$HOST" api.Dex/UpdateClient

echo "Done. Current redirect URIs:"
grpcurl -plaintext -import-path /tmp -proto dex_api.proto \
  -d '{"id":"notes-confidential"}' "$HOST" api.Dex/GetClient \
  | python3 -c "import sys,json; [print(' -', u) for u in json.load(sys.stdin)['client']['redirectUris']]"
