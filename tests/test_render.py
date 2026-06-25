from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pycewl.crawler import CrawlOptions
from pycewl.render import crawl_rendered


class SPAHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.seen.append({"path": self.path, "user_agent": self.headers.get("User-Agent")})  # type: ignore[attr-defined]
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"""
                <html><body>
                <div id="app">InitialWord</div>
                <script>
                document.getElementById("app").textContent = "InjectedRenderTerm";
                </script>
                </body></html>
                """
            )
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def test_render_crawl_extracts_javascript_injected_terms():
    pytest.importorskip("playwright.async_api")
    server = ThreadingHTTPServer(("127.0.0.1", 0), SPAHandler)
    server.seen = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            result = crawl_rendered(
                f"http://127.0.0.1:{server.server_port}",
                CrawlOptions(depth=0, min_word_length=5, lowercase=True, user_agent="Render-Agent"),
            )
        except Exception as exc:
            if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc).lower():
                pytest.skip("Playwright browser binaries are not installed")
            raise
        assert result.words["injectedrenderterm"] == 1
        assert server.seen[0]["user_agent"] == "Render-Agent"
    finally:
        server.shutdown()
        server.server_close()
