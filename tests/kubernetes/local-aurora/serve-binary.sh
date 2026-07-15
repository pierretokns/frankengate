#!/bin/sh
set -eu

binary="${1:-/tmp/frankengate}"
port="${2:-18080}"
size="$(wc -c < "$binary" | tr -d ' ')"

while true; do
  {
    printf 'HTTP/1.1 200 OK\r\n'
    printf 'Content-Type: application/octet-stream\r\n'
    printf 'Content-Length: %s\r\n' "$size"
    printf 'Connection: close\r\n\r\n'
    cat "$binary"
  } | nc -l -p "$port"
done
