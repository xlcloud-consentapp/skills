#!/usr/bin/env bash
# Refreshes skills/consent-app/references/openapi.yaml from the live backend.
#   tools/refresh_openapi.sh          overwrite the snapshot
#   tools/refresh_openapi.sh --check  exit 1 if the snapshot differs from the live spec
set -euo pipefail

URL="https://api.consent.app/api/openapi.yaml"
DEST="$(cd "$(dirname "$0")/.." && pwd)/skills/consent-app/references/openapi.yaml"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsS "$URL" -o "$tmp"

if [[ "${1:-}" == "--check" ]]; then
  if ! diff -q --strip-trailing-cr "$DEST" "$tmp" >/dev/null; then
    echo "openapi.yaml differs from $URL - run tools/refresh_openapi.sh" >&2
    exit 1
  fi
  echo "openapi.yaml matches $URL"
  exit 0
fi

cp "$tmp" "$DEST"
echo "wrote $DEST from $URL"
