from collections import Counter

import pytest

from pycewl.cli import build_cewl_parser, main, run_cewl, run_fab, _looks_like_uvx_wrapper_path
from pycewl.crawler import CrawlResult


def test_cewl_help_mentions_render():
    parser = build_cewl_parser()
    assert "--render" in parser.format_help()


def test_pycewl_dispatches_fab(tmp_path, capsys):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"/Author (Alice)")
    assert main(["fab", str(pdf)]) == 0
    assert "Alice" in capsys.readouterr().out


def test_uvx_wrapper_path_detection():
    assert _looks_like_uvx_wrapper_path("./pycewl")
    assert not _looks_like_uvx_wrapper_path("https://example.com")


def test_fab_no_data(tmp_path, capsys):
    empty = tmp_path / "empty.txt"
    empty.write_text("nothing")
    assert run_fab([str(empty)]) == 0
    assert "No data found" in capsys.readouterr().out


def test_cewl_writes_word_email_and_metadata_files(tmp_path, monkeypatch):
    def fake_crawl(url, options):
        assert url == "https://example.test"
        return CrawlResult(
            words=Counter({"alpha": 2, "beta": 1}),
            emails={"admin@example.test"},
            metadata={"Alice Example"},
        )

    monkeypatch.setattr("pycewl.cli.crawl", fake_crawl)
    words = tmp_path / "words.txt"
    emails = tmp_path / "emails.txt"
    metadata = tmp_path / "metadata.txt"
    assert (
        run_cewl(
            [
                "--count",
                "-e",
                "-a",
                "-w",
                str(words),
                "--email_file",
                str(emails),
                "--meta_file",
                str(metadata),
                "https://example.test",
            ]
        )
        == 0
    )
    assert words.read_text() == "alpha, 2\nbeta, 1\n"
    assert emails.read_text() == "admin@example.test\n"
    assert metadata.read_text() == "Alice Example\n"


def test_cewl_rejects_invalid_auth_combinations():
    with pytest.raises(SystemExit, match="provide a username and password"):
        run_cewl(["--auth_type", "basic", "--auth_user", "user", "https://example.test"])
    with pytest.raises(SystemExit, match="no auth type"):
        run_cewl(["--auth_user", "user", "https://example.test"])


def test_cewl_rejects_invalid_metadata_temp_dir(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(SystemExit, match="Meta temp directory"):
        run_cewl(["--meta-temp-dir", str(missing), "https://example.test"])
