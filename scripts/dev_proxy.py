"""Local-only stand-in for the frontend nginx container.

Serves the built Vite bundle (frontend/dist) and proxies ``/api/*`` and
``/health`` to the FastAPI service, mirroring frontend/nginx.conf.
Used for real end-to-end acceptance on a host without Docker.
"""
import http.server
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "dist"
API = os.getenv("API_URL", "http://127.0.0.1:8000")
PORT = int(os.getenv("WEB_PORT", "8080"))

PROXY_PREFIXES = ("/api/", "/health")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.startswith(PROXY_PREFIXES):
            return self._proxy()
        # SPA fallback
        target = ROOT / self.path.lstrip("/")
        if not self.path.startswith("/assets/") or not target.is_file():
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        self.send_error(404)

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(
            API + self.path, data=body, method=self.command,
            headers={"Content-Type": self.headers.get("Content-Type",
                                                      "application/json")})
        try:
            with urllib.request.urlopen(req, timeout=60) as up:
                data = up.read()
                self.send_response(up.status)
        except urllib.error.HTTPError as ex:
            data = ex.read()
            self.send_response(ex.code)
        except Exception as ex:
            self.send_error(502, f"proxy error: {ex}")
            return
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write("[web] " + fmt % args + "\n")


if __name__ == "__main__":
    print(f"serving {ROOT} on :{PORT}, proxy -> {API}")
    http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
