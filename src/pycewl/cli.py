from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .crawler import CrawlOptions, crawl
from .metadata import process_file
from .render import crawl_rendered
from .text import sorted_counter, unique_sorted


def _parse_header(values: list[str] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values or []:
        if ":" not in value:
            raise argparse.ArgumentTypeError(f"Invalid header: {value}")
        name, header_value = value.split(":", 1)
        headers[name.strip()] = header_value.strip()
    return headers


def build_cewl_parser(prog: str = "cewl") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Custom word list generator")
    parser.add_argument("url")
    parser.add_argument("-k", "--keep", action="store_true", help="Keep downloaded metadata files")
    parser.add_argument("-d", "--depth", type=int, default=2, help="Depth to spider to, default 2")
    parser.add_argument("-m", "--min_word_length", "--min-word-length", type=int, default=3)
    parser.add_argument("-x", "--max_word_length", "--max-word-length", type=int)
    parser.add_argument("-o", "--offsite", action="store_true", help="Let the spider visit other sites")
    parser.add_argument("--exclude", help="File containing request paths to exclude")
    parser.add_argument("--allowed", help="Regex pattern that URL path must match")
    parser.add_argument("-w", "--write", help="Write words/groups to this file")
    parser.add_argument("-u", "--ua", help="User agent to send")
    parser.add_argument("-n", "--no-words", action="store_true", help="Do not output the wordlist")
    parser.add_argument("-g", "--groups", type=int, default=-1, help="Return groups of words as well")
    parser.add_argument("--lowercase", action="store_true", help="Lowercase all parsed words")
    parser.add_argument("--with-numbers", action="store_true", help="Accept words with numbers")
    parser.add_argument("--convert-umlauts", action="store_true", help="Convert common Latin-1 umlauts")
    parser.add_argument("-a", "--meta", action="store_true", help="Include metadata")
    parser.add_argument("--meta_file", "--meta-file", help="Output file for metadata")
    parser.add_argument("-e", "--email", action="store_true", help="Include email addresses")
    parser.add_argument("--email_file", "--email-file", help="Output file for email addresses")
    parser.add_argument("--meta-temp-dir", default="/tmp", help="Temporary directory for metadata files")
    parser.add_argument("-c", "--count", action="store_true", help="Show counts")
    parser.add_argument("--render", action="store_true", help="Render pages with Playwright before extracting text")
    parser.add_argument("--auth_type", "--auth-type", choices=("basic", "digest"))
    parser.add_argument("--auth_user", "--auth-user")
    parser.add_argument("--auth_pass", "--auth-pass")
    parser.add_argument("-H", "--header", action="append", default=[])
    parser.add_argument("--proxy_host", "--proxy-host")
    parser.add_argument("--proxy_port", "--proxy-port", type=int, default=8080)
    parser.add_argument("--proxy_username", "--proxy-username")
    parser.add_argument("--proxy_password", "--proxy-password")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _read_exclude(path: str | None) -> set[str]:
    if not path:
        return set()
    return {line.strip() for line in Path(path).read_text().splitlines() if line.strip()}


def _build_options(args: argparse.Namespace) -> CrawlOptions:
    if args.depth < 0:
        raise SystemExit("Depth must be >= 0")
    if args.min_word_length < 1:
        raise SystemExit("Minimum word length must be >= 1")
    if args.max_word_length is not None and args.max_word_length < 1:
        raise SystemExit("Maximum word length must be >= 1")
    if args.auth_type and (not args.auth_user or not args.auth_pass):
        raise SystemExit("If using auth you must provide a username and password")
    if not args.auth_type and (args.auth_user or args.auth_pass):
        raise SystemExit("Authentication details provided but no auth type")
    meta_temp_dir = Path(args.meta_temp_dir)
    if not meta_temp_dir.is_dir():
        raise SystemExit("Meta temp directory is not a directory")
    return CrawlOptions(
        depth=args.depth,
        min_word_length=args.min_word_length,
        max_word_length=args.max_word_length,
        offsite=args.offsite,
        exclude=_read_exclude(args.exclude),
        allowed=re.compile(args.allowed) if args.allowed else None,
        user_agent=args.ua,
        headers=_parse_header(args.header),
        lowercase=args.lowercase,
        with_numbers=args.with_numbers,
        convert_umlauts=args.convert_umlauts,
        groups=args.groups,
        words=not args.no_words,
        email=args.email,
        meta=args.meta,
        keep=args.keep,
        meta_temp_dir=meta_temp_dir,
        auth_type=args.auth_type,
        auth_user=args.auth_user,
        auth_pass=args.auth_pass,
        proxy_host=args.proxy_host,
        proxy_port=args.proxy_port,
        proxy_username=args.proxy_username,
        proxy_password=args.proxy_password,
        verbose=args.verbose,
        debug=args.debug,
    )


def _write_lines(path: str | None, lines: list[str], stream) -> None:
    if path:
        Path(path).write_text("\n".join(lines) + ("\n" if lines else ""))
    else:
        for line in lines:
            print(line, file=stream)


def run_cewl(argv: list[str] | None = None, *, prog: str = "cewl") -> int:
    parser = build_cewl_parser(prog)
    args = parser.parse_args(argv)
    options = _build_options(args)
    result = crawl_rendered(args.url, options) if args.render else crawl(args.url, options)
    word_lines: list[str] = []
    if options.words:
        for word, count in sorted_counter(result.words):
            word_lines.append(f"{word}, {count}" if args.count else word)
    if options.groups > 0:
        for group, count in sorted_counter(result.groups):
            word_lines.append(f"{group}, {count}" if args.count else group)
    _write_lines(args.write, word_lines, sys.stdout)
    if options.email:
        emails = unique_sorted(result.emails)
        if args.email_file:
            _write_lines(args.email_file, emails, sys.stdout)
        elif emails:
            if word_lines:
                print()
            print("Email addresses found")
            print("---------------------")
            _write_lines(None, emails, sys.stdout)
    if options.meta:
        metadata = unique_sorted(result.metadata)
        if args.meta_file:
            _write_lines(args.meta_file, metadata, sys.stdout)
        elif metadata:
            if word_lines or result.emails:
                print()
            print("Meta data found")
            print("---------------")
            _write_lines(None, metadata, sys.stdout)
    return 0


def build_fab_parser(prog: str = "fab") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Files Already Bagged metadata extractor")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("files", nargs="+", metavar="filename/list")
    return parser


def run_fab(argv: list[str] | None = None, *, prog: str = "fab") -> int:
    parser = build_fab_parser(prog)
    args = parser.parse_args(argv)
    values: list[str] = []
    for filename in args.files:
        if args.verbose:
            print(f"processing file: {filename}", file=sys.stderr)
        values.extend(process_file(filename))
    values = unique_sorted(values)
    if values:
        print("\n".join(values))
    else:
        print("No data found")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and _looks_like_uvx_wrapper_path(argv[0]):
        argv.pop(0)
    if argv and argv[0] == "fab":
        return run_fab(argv[1:], prog="pycewl fab")
    return run_cewl(argv, prog="pycewl")


def _looks_like_uvx_wrapper_path(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return False
    path = Path(value)
    return path.name == "pycewl" and path.is_file()


def cewl_main() -> int:
    return run_cewl()


def fab_main() -> int:
    return run_fab()


if __name__ == "__main__":
    raise SystemExit(main())
