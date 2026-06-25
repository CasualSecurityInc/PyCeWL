from __future__ import annotations

import html
import re
from collections import Counter, deque
from html.parser import HTMLParser
from typing import Iterable


EMAIL_RE = re.compile(r"\b([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b", re.I)

UMLAUTS = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "å": "a",
        "Å": "A",
    }
)


class ParsedHTML:
    def __init__(self) -> None:
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self.emails: list[str] = []

    @property
    def text(self) -> str:
        return " ".join(part for part in self.text_parts if part)


class CeWLHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parsed = ParsedHTML()
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if tag == "a" and attrs_dict.get("href"):
            href = attrs_dict["href"].strip()
            self.parsed.links.append(href)
            if href.lower().startswith("mailto:"):
                address = href.split(":", 1)[1].split("?", 1)[0]
                if address:
                    self.parsed.emails.append(address)
        if tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            if name in {"description", "keywords"} and attrs_dict.get("content"):
                self.parsed.text_parts.append(attrs_dict["content"])
        for attr_name in ("alt", "title"):
            if attrs_dict.get(attr_name):
                self.parsed.text_parts.append(attrs_dict[attr_name])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parsed.text_parts.append(data)


def parse_html(content: str) -> ParsedHTML:
    parser = CeWLHTMLParser()
    parser.feed(content)
    return parser.parsed


def extract_emails(text: str) -> list[str]:
    return EMAIL_RE.findall(text)


def normalize_words(
    text: str,
    *,
    lowercase: bool = False,
    with_numbers: bool = False,
    convert_umlauts: bool = False,
) -> list[str]:
    text = html.unescape(text)
    if lowercase:
        text = text.lower()
    if convert_umlauts:
        text = text.translate(UMLAUTS)
    pattern = r"[^\W_]+" if with_numbers else r"[^\W\d_]+"
    return re.findall(pattern, text, flags=re.UNICODE)


def count_words(
    text: str,
    *,
    min_length: int = 3,
    max_length: int | None = None,
    lowercase: bool = False,
    with_numbers: bool = False,
    convert_umlauts: bool = False,
) -> Counter[str]:
    counter: Counter[str] = Counter()
    for word in normalize_words(
        text,
        lowercase=lowercase,
        with_numbers=with_numbers,
        convert_umlauts=convert_umlauts,
    ):
        if len(word) < min_length:
            continue
        if max_length is not None and len(word) > max_length:
            continue
        counter[word] += 1
    return counter


def count_groups(
    text: str,
    group_size: int,
    *,
    lowercase: bool = False,
    with_numbers: bool = False,
    convert_umlauts: bool = False,
) -> Counter[str]:
    counter: Counter[str] = Counter()
    if group_size <= 0:
        return counter
    window: deque[str] = deque(maxlen=group_size)
    for word in normalize_words(
        text,
        lowercase=lowercase,
        with_numbers=with_numbers,
        convert_umlauts=convert_umlauts,
    ):
        window.append(word)
        if len(window) == group_size:
            counter[" ".join(window)] += 1
    return counter


def sorted_counter(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value.strip() for value in values if value and value.strip()})

