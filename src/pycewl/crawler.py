from __future__ import annotations

import re
import tempfile
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import httpx

from .metadata import process_file
from .text import count_groups, count_words, extract_emails, parse_html


IGNORED_LINK_SUFFIXES = (".zip", ".gz", ".bz2", ".png", ".gif", ".jpg", ".jpeg")
DOCUMENT_SUFFIXES = {
    ".doc",
    ".docm",
    ".docx",
    ".dot",
    ".dotm",
    ".dotx",
    ".pdf",
    ".pot",
    ".potm",
    ".potx",
    ".ppam",
    ".pps",
    ".ppsm",
    ".ppsx",
    ".ppt",
    ".pptm",
    ".pptx",
    ".xlam",
    ".xls",
    ".xlsb",
    ".xlsm",
    ".xlsx",
    ".xlt",
    ".xltm",
    ".xltx",
}

JAVASCRIPT_REDIRECT_RE = re.compile(
    r"""(?:window\.)?location(?:\.href)?\s*=\s*["']([^"']+)["']""",
    re.I,
)


@dataclass
class CrawlOptions:
    depth: int = 2
    min_word_length: int = 3
    max_word_length: int | None = None
    offsite: bool = False
    exclude: set[str] = field(default_factory=set)
    allowed: re.Pattern[str] | None = None
    user_agent: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    lowercase: bool = False
    with_numbers: bool = False
    convert_umlauts: bool = False
    groups: int = -1
    words: bool = True
    email: bool = False
    meta: bool = False
    keep: bool = False
    meta_temp_dir: Path = Path(tempfile.gettempdir())
    auth_type: str | None = None
    auth_user: str | None = None
    auth_pass: str | None = None
    proxy_host: str | None = None
    proxy_port: int = 8080
    proxy_username: str | None = None
    proxy_password: str | None = None
    timeout: float = 20.0
    verbose: bool = False
    debug: bool = False


@dataclass
class CrawlResult:
    words: Counter[str] = field(default_factory=Counter)
    groups: Counter[str] = field(default_factory=Counter)
    emails: set[str] = field(default_factory=set)
    metadata: set[str] = field(default_factory=set)
    visited: list[str] = field(default_factory=list)


def normalize_start_url(url: str) -> str:
    if not re.match(r"^https?://", url, flags=re.I):
        return f"http://{url}"
    return url


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    return parsed.scheme, parsed.hostname or "", parsed.port


def _request_uri(url: str) -> str:
    parsed = urlparse(url)
    uri = parsed.path or "/"
    if parsed.query:
        uri += f"?{parsed.query}"
    return uri


def _suffix(url: str) -> str:
    return Path(unquote(urlparse(url).path)).suffix.lower()


def _proxy_url(options: CrawlOptions) -> str | None:
    if not options.proxy_host:
        return None
    auth = ""
    if options.proxy_username:
        password = options.proxy_password or ""
        auth = f"{options.proxy_username}:{password}@"
    return f"http://{auth}{options.proxy_host}:{options.proxy_port or 8080}"


def _auth(options: CrawlOptions) -> httpx.Auth | None:
    if not options.auth_type:
        return None
    if options.auth_type == "basic":
        return httpx.BasicAuth(options.auth_user or "", options.auth_pass or "")
    if options.auth_type == "digest":
        return httpx.DigestAuth(options.auth_user or "", options.auth_pass or "")
    return None


def http_client_kwargs(options: CrawlOptions) -> dict[str, object]:
    headers = dict(options.headers)
    if options.user_agent:
        headers["User-Agent"] = options.user_agent
    client_kwargs: dict[str, object] = {
        "headers": headers,
        "auth": _auth(options),
        "follow_redirects": True,
        "timeout": options.timeout,
        "verify": False,
    }
    proxy = _proxy_url(options)
    if proxy:
        client_kwargs["proxy"] = proxy
    return client_kwargs


def should_follow(start_url: str, candidate: str, options: CrawlOptions) -> bool:
    if not candidate or candidate.startswith("#"):
        return False
    if candidate.lower().startswith("mailto:"):
        return False
    absolute = urljoin(start_url, candidate)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return False
    if _suffix(absolute) in IGNORED_LINK_SUFFIXES:
        return False
    if not options.offsite and _origin(absolute) != _origin(start_url):
        return False
    if _request_uri(absolute) in options.exclude:
        return False
    if options.allowed and not options.allowed.search(parsed.path):
        return False
    return True


def discover_links(start_url: str, current_url: str, links: list[str], options: CrawlOptions) -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()
    for link in links:
        if should_follow(start_url, link, options):
            absolute = urljoin(current_url, link)
            absolute = absolute.split("#", 1)[0]
            if absolute not in seen:
                seen.add(absolute)
                discovered.append(absolute)
    return discovered


def discover_javascript_redirects(content: str) -> list[str]:
    return [match.strip() for match in JAVASCRIPT_REDIRECT_RE.findall(content) if match.strip()]


def _metadata_filename(url: str, suffix: str, options: CrawlOptions) -> Path:
    if options.keep:
        name = Path(unquote(urlparse(url).path)).name or f"cewl_tmp{suffix}"
    else:
        name = f"cewl_tmp{suffix}"
    return options.meta_temp_dir / name


def _handle_document(url: str, content: bytes, result: CrawlResult, options: CrawlOptions) -> None:
    if not options.meta:
        return
    suffix = _suffix(url)
    if suffix not in DOCUMENT_SUFFIXES:
        return
    path = _metadata_filename(url, suffix, options)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    result.metadata.update(process_file(path))
    if not options.keep:
        path.unlink(missing_ok=True)


def _handle_html(url: str, content: str, result: CrawlResult, options: CrawlOptions) -> list[str]:
    parsed = parse_html(content)
    text = parsed.text
    if options.email:
        result.emails.update(parsed.emails)
        result.emails.update(extract_emails(text))
    if options.words:
        result.words.update(
            count_words(
                text,
                min_length=options.min_word_length,
                max_length=options.max_word_length,
                lowercase=options.lowercase,
                with_numbers=options.with_numbers,
                convert_umlauts=options.convert_umlauts,
            )
        )
    if options.groups > 0:
        result.groups.update(
            count_groups(
                text,
                options.groups,
                lowercase=options.lowercase,
                with_numbers=options.with_numbers,
                convert_umlauts=options.convert_umlauts,
            )
        )
    return [*parsed.links, *discover_javascript_redirects(content)]


def crawl(url: str, options: CrawlOptions) -> CrawlResult:
    start_url = normalize_start_url(url)
    result = CrawlResult()
    client_kwargs = http_client_kwargs(options)
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    seen: set[str] = set()
    with httpx.Client(**client_kwargs) as client:
        while queue:
            current_url, depth = queue.popleft()
            if current_url in seen or depth > options.depth:
                continue
            seen.add(current_url)
            if options.verbose:
                print(f"Visiting: {current_url}")
            try:
                response = client.get(current_url)
            except httpx.HTTPError as exc:
                if options.verbose:
                    print(f"Unable to fetch {current_url}: {exc}")
                continue
            final_url = str(response.url)
            result.visited.append(final_url)
            suffix = _suffix(final_url)
            content_type = response.headers.get("content-type", "")
            if suffix in DOCUMENT_SUFFIXES:
                _handle_document(final_url, response.content, result, options)
                continue
            if "text/html" in content_type or not content_type or suffix in {"", ".html", ".htm", ".php", ".asp", ".aspx", ".cfm", ".css"}:
                links = _handle_html(final_url, response.text, result, options)
                if depth < options.depth:
                    for link in discover_links(start_url, final_url, links, options):
                        if link not in seen:
                            queue.append((link, depth + 1))
            elif options.email:
                result.emails.update(extract_emails(response.text))
    return result
