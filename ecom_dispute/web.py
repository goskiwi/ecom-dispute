from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .harness import DiagnosticHarness
from .repository import Repository

ASSETS = Path(__file__).resolve().parent.parent / "web"


class DemoApplication:
    def __init__(self, repository: Repository):
        self.repository = repository
        harness = DiagnosticHarness(repository)
        self._reports = {
            case_id: harness.diagnose_sync(repository.case(case_id))
            for case_id in repository.case_ids()
        }

    def cases(self) -> list[dict]:
        cases = []
        for case_id in self.repository.case_ids():
            case = self.repository.case(case_id)
            report = self._reports[case_id]
            cases.append(
                {
                    "case_id": case_id,
                    "business_type": case.business_type,
                    "source_type": case.source_type,
                    "decision": report.decision,
                    "responsible_party": report.responsible_party,
                    "review_required": report.review_required,
                    "conflict_count": len(report.conflicts),
                }
            )
        return cases

    def case(self, case_id: str) -> dict:
        case = self.repository.case(case_id)
        report = self._reports[case_id]
        return {
            "input": case.model_dump(mode="json"),
            "report": report.model_dump(mode="json"),
        }


def make_handler(application: DemoApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/cases":
                self._json(application.cases())
                return
            if path.startswith("/api/cases/"):
                case_id = unquote(path.removeprefix("/api/cases/"))
                try:
                    self._json(application.case(case_id))
                except KeyError:
                    self._json({"error": "case not found"}, HTTPStatus.NOT_FOUND)
                return
            asset = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
                "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
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


def serve(repository: Repository, host: str = "127.0.0.1", port: int = 8765) -> None:
    application = DemoApplication(repository)
    server = ThreadingHTTPServer((host, port), make_handler(application))
    print(f"EcomDispute demo: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
