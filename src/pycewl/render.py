from __future__ import annotations

import asyncio

import httpx

from .crawler import CrawlOptions, CrawlResult, discover_links, http_client_kwargs, normalize_start_url
from .crawler import DOCUMENT_SUFFIXES, _handle_document, _suffix
from .crawler import _handle_html  # Render mode shares the same extraction pipeline.


async def _render_crawl(url: str, options: CrawlOptions) -> CrawlResult:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "--render requires the optional render extra. "
            'Install with: uvx "pycewl[render]" --render <url>. '
            "Browser binaries may also need: playwright install chromium"
        ) from exc

    start_url = normalize_start_url(url)
    result = CrawlResult()
    seen: set[str] = set()
    queue: list[tuple[str, int]] = [(start_url, 0)]
    http_kwargs = http_client_kwargs(options)
    async with async_playwright() as playwright:
        launch_kwargs: dict[str, object] = {"headless": True}
        if options.proxy_host:
            proxy = {"server": f"http://{options.proxy_host}:{options.proxy_port or 8080}"}
            if options.proxy_username:
                proxy["username"] = options.proxy_username
                proxy["password"] = options.proxy_password or ""
            launch_kwargs["proxy"] = proxy
        browser = await playwright.chromium.launch(**launch_kwargs)
        context_kwargs: dict[str, object] = {
            "extra_http_headers": options.headers or None,
            "ignore_https_errors": True,
        }
        if options.user_agent:
            context_kwargs["user_agent"] = options.user_agent
        if options.auth_type == "basic" and options.auth_user:
            context_kwargs["http_credentials"] = {
                "username": options.auth_user,
                "password": options.auth_pass or "",
            }
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        while queue:
            current_url, depth = queue.pop(0)
            if current_url in seen or depth > options.depth:
                continue
            seen.add(current_url)
            if options.verbose:
                print(f"Rendering: {current_url}")
            if _suffix(current_url) in DOCUMENT_SUFFIXES:
                try:
                    with httpx.Client(**http_kwargs) as client:
                        document_response = client.get(current_url)
                except httpx.HTTPError as exc:
                    if options.verbose:
                        print(f"Unable to fetch metadata file {current_url}: {exc}")
                    continue
                final_document_url = str(document_response.url)
                result.visited.append(final_document_url)
                _handle_document(final_document_url, document_response.content, result, options)
                continue
            try:
                response = await page.goto(current_url, wait_until="networkidle", timeout=int(options.timeout * 1000))
            except Exception as exc:
                if options.verbose:
                    print(f"Unable to render {current_url}: {exc}")
                continue
            final_url = page.url
            result.visited.append(final_url)
            html = await page.content()
            links = _handle_html(final_url, html, result, options)
            if response and options.email:
                headers = await response.all_headers()
                if "text/html" not in headers.get("content-type", ""):
                    continue
            if depth < options.depth:
                for link in discover_links(start_url, final_url, links, options):
                    if link not in seen:
                        queue.append((link, depth + 1))
        await browser.close()
    return result


def crawl_rendered(url: str, options: CrawlOptions) -> CrawlResult:
    return asyncio.run(_render_crawl(url, options))
