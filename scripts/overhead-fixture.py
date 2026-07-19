#!/usr/bin/env python3
"""Deterministic local fixture for the gateway overhead benchmark."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - stdlib handler API
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        if self.path == "/gateway":
            request = json.loads(body or b"{}")
            # Simulate bounded local governance and OTEL metadata work.
            _ = {"tenant": request.get("tenant", "bench"), "vk": request.get("vk", "vk-bench")}
            _ = {"operation": "chat.completion", "model": request.get("model", "fixture")}
        payload = b'{"id":"fixture","choices":[{"message":{"content":"ok"}}]}'
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
