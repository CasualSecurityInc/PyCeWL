import subprocess
import zipfile

from pycewl.metadata import get_exiftool_data, get_ooxml_data, get_pdf_data, process_file


def test_pdf_regex_metadata(tmp_path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF\n/Author (Alice Example)\n<pdf:Author>Bob Example</pdf:Author>")
    assert get_pdf_data(pdf) == ["Alice Example", "Bob Example"]


def test_ooxml_core_metadata(tmp_path):
    docx = tmp_path / "sample.docx"
    core_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <cp:coreProperties
      xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
      xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:creator>Alice</dc:creator>
      <cp:lastModifiedBy>Bob</cp:lastModifiedBy>
    </cp:coreProperties>
    """
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("docProps/core.xml", core_xml)
    assert get_ooxml_data(docx) == ["Alice", "Bob"]


def test_exiftool_fallback_reads_author_last_saved_by_and_creator(tmp_path, monkeypatch):
    sample = tmp_path / "legacy.doc"
    sample.write_bytes(b"legacy")
    captured = {}

    def fake_which(name):
        assert name == "exiftool"
        return "/usr/bin/exiftool"

    def fake_run(args, check, capture_output, text, timeout):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="Alice\nBob\nCarol\n", stderr="")

    monkeypatch.setattr("pycewl.metadata.shutil.which", fake_which)
    monkeypatch.setattr("pycewl.metadata.subprocess.run", fake_run)

    assert get_exiftool_data(sample) == ["Alice", "Bob", "Carol"]
    assert "-Author" in captured["args"]
    assert "-LastSavedBy" in captured["args"]
    assert "-Creator" in captured["args"]


def test_process_file_uses_exiftool_for_unknown_suffix(tmp_path, monkeypatch):
    sample = tmp_path / "unknown.bin"
    sample.write_bytes(b"unknown")
    monkeypatch.setattr("pycewl.metadata.get_exiftool_data", lambda path: ["Unknown Creator"])

    assert process_file(sample) == ["Unknown Creator"]
