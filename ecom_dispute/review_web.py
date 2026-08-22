from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ASSETS = Path(__file__).resolve().parent.parent / "review_web"


class ReviewFormApplication:
    def __init__(self, form_path: Path) -> None:
        self.form_path = form_path
        self._lock = threading.Lock()

    def form(self) -> dict:
        with self._lock:
            return json.loads(self.form_path.read_text(encoding="utf-8"))

    def update(self, review_id: str, ratings: dict) -> dict:
        with self._lock:
            form = json.loads(self.form_path.read_text(encoding="utf-8"))
            item = next(
                (entry for entry in form["items"] if entry["review_id"] == review_id), None
            )
            if item is None:
                raise KeyError(review_id)
            item["ratings"] = ratings
            self.form_path.write_text(
                json.dumps(form, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return item


def make_review_handler(
    application: ReviewFormApplication,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/form":
                self._json(application.form())
                return
            asset = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/app.css": ("app.css", "text/css; charset=utf-8"),
            }.get(path)
            if not asset:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            filename, content_type = asset
            body = (ASSETS / filename).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if not path.startswith("/api/items/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            review_id = unquote(path.removeprefix("/api/items/"))
            try:
                length = int(self.headers.get("Content-Length", "0"))
                ratings = json.loads(self.rfile.read(length).decode("utf-8"))
                self._json(application.update(review_id, ratings))
            except KeyError:
                self._json({"error": "review item not found"}, HTTPStatus.NOT_FOUND)

        def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve_review_form(form_path: Path, host: str, port: int) -> None:
    application = ReviewFormApplication(form_path)
    server = ThreadingHTTPServer((host, port), make_review_handler(application))
    print(f"Review A/B: http://{host}:{port} -> {form_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
