from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree


PDF_PATTERNS = [
    re.compile(rb"pdf:Author='([^']*)'", re.I),
    re.compile(rb"xap:Author='([^']*)'", re.I),
    re.compile(rb"dc:creator='([^']*)'", re.I),
    re.compile(rb"/Author ?\(([^)]*)\)", re.I),
    re.compile(rb"<xap:creator>(.*?)</xap:creator>", re.I | re.S),
    re.compile(rb"<xap:Author>(.*?)</xap:Author>", re.I | re.S),
    re.compile(rb"<pdf:Author>(.*?)</pdf:Author>", re.I | re.S),
    re.compile(rb"<dc:creator>(.*?)</dc:creator>", re.I | re.S),
]

OOXML_FIELDS = [
    "{http://purl.org/dc/elements/1.1/}creator",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy",
]

OOXML_SUFFIXES = {
    ".docm",
    ".docx",
    ".dotm",
    ".dotx",
    ".potm",
    ".potx",
    ".ppam",
    ".ppsm",
    ".ppsx",
    ".pptm",
    ".pptx",
    ".xlam",
    ".xlsb",
    ".xlsm",
    ".xlsx",
    ".xltm",
    ".xltx",
}


def _clean(value: bytes | str) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore") or value.decode("latin-1", errors="ignore")
    return value.strip().replace("\\)", ")").replace("\\(", "(")


def get_pdf_data(path: str | Path) -> list[str]:
    data = Path(path).read_bytes()
    values: list[str] = []
    for pattern in PDF_PATTERNS:
        for match in pattern.findall(data):
            value = _clean(match)
            if value:
                values.append(value)
    return values


def get_ooxml_data(path: str | Path) -> list[str]:
    values: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            try:
                xml = archive.read("docProps/core.xml")
            except KeyError:
                return values
    except zipfile.BadZipFile:
        return values
    root = ElementTree.fromstring(xml)
    for field in OOXML_FIELDS:
        element = root.find(field)
        if element is not None and element.text and element.text.strip():
            values.append(element.text.strip())
    return values


def get_exiftool_data(path: str | Path) -> list[str]:
    if not shutil.which("exiftool"):
        return []
    fields = ("Author", "LastSavedBy", "Creator")
    args = ["exiftool", "-s3", *[f"-{field}" for field in fields], str(path)]
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode not in (0, 1):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def process_file(path: str | Path, *, use_exiftool: bool = True) -> list[str]:
    file_path = Path(path)
    if not file_path.is_file():
        return []
    suffix = file_path.suffix.lower()
    values: list[str] = []
    if suffix == ".pdf":
        if use_exiftool:
            values.extend(get_exiftool_data(file_path))
        values.extend(get_pdf_data(file_path))
    elif suffix in OOXML_SUFFIXES:
        values.extend(get_ooxml_data(file_path))
        if use_exiftool:
            values.extend(get_exiftool_data(file_path))
    elif use_exiftool:
        values.extend(get_exiftool_data(file_path))
    return sorted({value for value in values if value})

