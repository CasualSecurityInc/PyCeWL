from pycewl.text import count_groups, count_words, extract_emails, parse_html


def test_html_extracts_visible_meta_attribute_links_and_mailto():
    parsed = parse_html(
        """
        <html><head><meta name="keywords" content="alpha beta"></head>
        <body><script>hiddenKeyword()</script><a href="/next" title="Gamma">link</a>
        <img alt="Delta"><a href="mailto:user@example.com">mail</a></body></html>
        """
    )
    assert "alpha beta" in parsed.text
    assert "Gamma" in parsed.text
    assert "Delta" in parsed.text
    assert "hiddenKeyword" not in parsed.text
    assert "/next" in parsed.links
    assert parsed.emails == ["user@example.com"]


def test_word_filters_counts_numbers_lowercase_and_umlauts():
    counts = count_words(
        "Alpha alpha b2b äpfel Übergröße x",
        min_length=3,
        lowercase=True,
        with_numbers=False,
        convert_umlauts=True,
    )
    assert counts["alpha"] == 2
    assert "b2b" not in counts
    assert counts["aepfel"] == 1
    assert counts["uebergroesse"] == 1
    assert "x" not in counts


def test_convert_umlauts_from_html_entities():
    counts = count_words(
        "&auml;pfel &ouml;l &aring;l",
        min_length=2,
        convert_umlauts=True,
    )
    assert counts["aepfel"] == 1
    assert counts["oel"] == 1
    assert counts["al"] == 1


def test_swedish_aring_is_converted():
    counts = count_words(
        "ål Ål",
        min_length=2,
        lowercase=True,
        convert_umlauts=True,
    )
    assert counts["al"] == 2


def test_with_numbers_and_max_length():
    counts = count_words("abc123 abcdef short", min_length=3, max_length=6, with_numbers=True)
    assert counts["abc123"] == 1
    assert "abcdef" in counts
    assert "short" in counts


def test_groups_are_sliding_windows():
    groups = count_groups("one two three four", 2)
    assert groups["one two"] == 1
    assert groups["two three"] == 1
    assert groups["three four"] == 1


def test_email_extraction():
    assert extract_emails("Contact admin@example.com and root@test.local") == [
        "admin@example.com",
        "root@test.local",
    ]

