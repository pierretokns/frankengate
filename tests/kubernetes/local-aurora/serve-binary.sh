#!/bin/sh
set -eu

binary="${1:-/tmp/frankengate}"
port="${2:-18080}"

size="$(wc -c < "$binary" | tr -d ' ')"

# Keep the dependency surface to the tools present in the pinned PostgreSQL
# test image.
# Clients use bounded retries because this intentionally tiny server accepts
# one connection at a time; the retry budget makes concurrent pod bootstrap
# deterministic without adding a second image or a host-side dependency.
while true; do
  {
    printf 'HTTP/1.1 200 OK\r\n'
    printf 'Content-Type: application/octet-stream\r\n'
    printf 'Content-Length: %s\r\n' "$size"
    printf 'Connection: close\r\n\r\n'
    cat "$binary"
  } | nc -l -p "$port"
done
