from __future__ import annotations

import base64
import re
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pycewl.crawler import CrawlOptions, crawl, discover_javascript_redirects, discover_links, normalize_start_url, should_follow


def test_normalize_start_url_adds_http():
    assert normalize_start_url("example.com") == "http://example.com"
    assert normalize_start_url("https://example.com") == "https://example.com"


def test_should_follow_same_site_filters_exclude_allowed_and_ignored_suffixes():
    options = CrawlOptions(exclude={"/blocked"}, allowed=None)
    start = "https://example.com/index.html"
    assert should_follow(start, "/next", options)
    assert not should_follow(start, "https://other.example/", options)
    assert not should_follow(start, "/blocked", options)
    assert not should_follow(start, "/image.png", options)
    assert not should_follow(start, "mailto:a@example.com", options)


def test_discover_links_resolves_and_deduplicates_fragments():
    options = CrawlOptions()
    links = discover_links("https://example.com/", "https://example.com/a/page.html", ["../b#top", "../b"], options)
    assert links == ["https://example.com/b"]


def test_discovers_javascript_location_href_redirects():
    assert discover_javascript_redirects("""<script>location.href = "/next";</script>""") == ["/next"]
    assert discover_javascript_redirects("""<script>window.location = 'other.html';</script>""") == ["other.html"]


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.seen.append(  # type: ignore[attr-defined]
            {
                "path": self.path,
                "user_agent": self.headers.get("User-Agent"),
                "x_token": self.headers.get("X-Token"),
                "authorization": self.headers.get("Authorization"),
            }
        )
        if self.path == "/basic":
            expected = "Basic " + base64.b64encode(b"user:pass").decode()
            if self.headers.get("Authorization") != expected:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="test"')
                self.end_headers()
                return
            self._html("Authorized SecretWord")
            return
        if self.path == "/":
            self._html(
                """
                <html><body>
                RootWord <a href="/page1">one</a>
                <a href="/blocked">blocked</a>
                <a href="/meta.docx">doc</a>
                <a href="mailto:admin@example.test">mail</a>
                <a href="http://127.0.0.1:9/offsite">off</a>
                <script>location.href = "/js-redirect"</script>
                </body></html>
                """
            )
            return
        if self.path == "/page1":
            self._html('PageOneWord <a href="/page2">two</a>')
            return
        if self.path == "/page2":
            self._html("DepthTwoWord")
            return
        if self.path == "/js-redirect":
            self._html("RedirectWord")
            return
        if self.path == "/blocked":
            self._html("BlockedWord")
            return
        if self.path == "/meta.docx":
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            self.end_headers()
            self.wfile.write(self.server.docx_bytes)  # type: ignore[attr-defined]
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return

    def _html(self, body: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())


def _docx_bytes() -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    core_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <cp:coreProperties
      xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
      xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:creator>Doc Author</dc:creator>
      <cp:lastModifiedBy>Doc Editor</cp:lastModifiedBy>
    </cp:coreProperties>
    """
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("docProps/core.xml", core_xml)
    return buffer.getvalue()


def _serve():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    server.seen = []
    server.docx_bytes = _docx_bytes()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_crawl_depth_redirect_mailto_headers_auth_and_filters(tmp_path):
    server, base_url = _serve()
    try:
        options = CrawlOptions(
            depth=1,
            min_word_length=3,
            lowercase=True,
            email=True,
            meta=True,
            keep=True,
            exclude={"/blocked"},
            allowed=None,
            user_agent="CeWL-Test-Agent",
            headers={"X-Token": "expected"},
            meta_temp_dir=tmp_path,
        )
        result = crawl(base_url, options)
        assert result.words["rootword"] == 1
        assert result.words["pageoneword"] == 1
        assert result.words["redirectword"] == 1
        assert "depthtwoword" not in result.words
        assert "blockedword" not in result.words
        assert result.emails == {"admin@example.test"}
        assert result.metadata == {"Doc Author", "Doc Editor"}
        assert (tmp_path / "meta.docx").exists()
        assert all(entry["user_agent"] == "CeWL-Test-Agent" for entry in server.seen)
        assert all(entry["x_token"] == "expected" for entry in server.seen)

        allowed_result = crawl(base_url, CrawlOptions(depth=1, lowercase=True, allowed=re.compile("page1")))
        assert allowed_result.words["pageoneword"] == 1
        assert "redirectword" not in allowed_result.words

        auth_result = crawl(
            f"{base_url}/basic",
            CrawlOptions(lowercase=True, auth_type="basic", auth_user="user", auth_pass="pass"),
        )
        assert auth_result.words["authorized"] == 1
        assert auth_result.words["secretword"] == 1
    finally:
        server.shutdown()
        server.server_close()
