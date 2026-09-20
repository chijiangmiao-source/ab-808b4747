"""Local-only stand-in for the nginx web container: serves the built React
bundle and proxies /api to the FastAPI service. Used for integration
verification when Docker is unavailable; docker deployments use nginx.

    SERVE_DIR=../frontend/dist UPSTREAM=http://127.0.0.1:8000 PORT=8080 \
        python scripts/dev_web_proxy.py
"""

from __future__ import annotations

import http.client
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVE_DIR = Path(os.environ.get("SERVE_DIR", "../frontend/dist")).resolve()
UPSTREAM = urllib.parse.urlparse(os.environ.get("UPSTREAM", "http://127.0.0.1:8000"))
PORT = int(os.environ.get("PORT", "8080"))

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        try:
            conn = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port, timeout=30)
            conn.request(self.command, self.path, body=body, headers={
                k: v for k, v in self.headers.items() if k.lower() != "host"
            })
            resp = conn.getresponse()
            data = resp.read()
        except Exception as exc:  # noqa: BLE001
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(exc).encode())
            return
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in ("transfer-encoding", "connection"):
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self):
        path = urllib.parse.urlparse(self.path).path
        rel = path.lstrip("/") or "index.html"
        target = (SERVE_DIR / rel).resolve()
        if not str(target).startswith(str(SERVE_DIR)) or not target.is_file():
            target = SERVE_DIR / "index.html"  # SPA fallback
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self._serve_static()

    do_POST = _proxy
    do_PUT = _proxy
    do_DELETE = _proxy


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"serving {SERVE_DIR} on :{PORT}, proxying /api -> {UPSTREAM.geturl()}")
    server.serve_forever()
