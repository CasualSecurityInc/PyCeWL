# PyCeWL - Python Custom Word List Generator

PyCeWL is a Python reimplementation of [CeWL](https://github.com/digininja/CeWL),
originally designed by Robin Wood (robin@digi.ninja).

It spiders a target website and builds custom word lists from the words it finds.
The output can be used with password auditing tools such as John the Ripper.

By default CeWL stays on the target site, follows links to depth 2, and prints
unique words of at least three characters to stdout. Options can increase the
depth, allow offsite links, write to a file, collect email addresses, extract
document metadata, and emit groups of words.

CeWL also includes FAB, Files Already Bagged, which extracts author, creator,
and email metadata from files that have already been downloaded.

Use this only where you have permission to test. Large depths, offsite crawling,
and broad URL patterns can generate a lot of traffic.

Homepage: <https://digi.ninja/projects/cewl.php>

GitHub: <https://github.com/digininja/CeWL>

## Quick Start

Run from a checkout with the `./pycewl` wrapper:

```sh
./pycewl https://example.com
./pycewl -d 3 -w words.txt https://example.com
./pycewl fab document.pdf
```

The wrapper uses `uvx --from .[render] pycewl`, so it can run directly from the
checkout and includes the optional Playwright dependency needed by `--render`.
If Playwright has not installed browser binaries yet, run:

```sh
uvx --from "pycewl[render]" playwright install chromium
```

Published package command names are available through `uvx`:

```sh
uvx --from pycewl cewl https://example.com
uvx --from pycewl fab document.pdf
```

For local development:

```sh
make setup
make test
make build
```

Equivalent direct commands:

```sh
uv sync
uv run pytest
uv build
```

## Common Examples

Most runs are one of two shapes: a normal HTTP crawl for server-rendered pages,
or a rendered crawl for a JavaScript-heavy site. These examples were captured
against live websites on 2026-06-23, so exact counts may drift as those sites
change.

For a regular page, the default HTTP crawler is enough. This single-page run
against IANA's reserved domains page keeps words with at least five characters,
lowercases them, and prints counts for inspection:

```sh
./pycewl -d 0 -m 5 --lowercase --count https://www.iana.org/domains/reserved
```

Captured output excerpt:

```text
domains, 18
domain, 7
registry, 6
overview, 5
policy, 5
reserved, 5
icann, 4
names, 4
special, 4
technical, 4
these, 4
arabic, 3
available, 3
example, 3
number, 3
```

For a cracker wordlist, write plain words to a file:

```sh
./pycewl -d 2 -m 5 --lowercase -w words.txt https://www.iana.org/domains/reserved
```

For a SPA-ish site, add `--render` so the page is loaded in Chromium before
words are extracted. This run uses Angular's documentation site:

```sh
./pycewl --render -d 0 -m 5 --lowercase --count https://angular.dev/
```

Captured output excerpt:

```text
angular, 24
google, 6
learn, 6
signals, 6
about, 5
searchterm, 5
signal, 5
community, 4
forward, 4
arrow, 3
computed, 3
development, 3
filtereditems, 3
framework, 3
github, 3
search, 3
where, 3
```

## Usage

Show CeWL help:

```sh
./pycewl --help
```

Common commands:

```sh
# Crawl a site with default settings.
./pycewl https://example.com

# Crawl deeper and write words to a file.
./pycewl -d 3 -w words.txt https://example.com

# Include email addresses and metadata.
./pycewl -e -a --meta_file metadata.txt https://example.com

# Allow offsite links. Use carefully.
./pycewl -o https://example.com

# Extract metadata from an already downloaded file.
./pycewl fab document.pdf
```

Current CeWL options:

```text
usage: pycewl [-h] [-k] [-d DEPTH] [-m MIN_WORD_LENGTH]
              [-x MAX_WORD_LENGTH] [-o] [--exclude EXCLUDE]
              [--allowed ALLOWED] [-w WRITE] [-u UA] [-n] [-g GROUPS]
              [--lowercase] [--with-numbers] [--convert-umlauts] [-a]
              [--meta_file META_FILE] [-e] [--email_file EMAIL_FILE]
              [--meta-temp-dir META_TEMP_DIR] [-c] [--render]
              [--auth_type {basic,digest}] [--auth_user AUTH_USER]
              [--auth_pass AUTH_PASS] [-H HEADER]
              [--proxy_host PROXY_HOST] [--proxy_port PROXY_PORT]
              [--proxy_username PROXY_USERNAME]
              [--proxy_password PROXY_PASSWORD] [-v] [--debug] [--version]
              url

Custom word list generator
```

Important flags:

```text
-k, --keep                  Keep downloaded metadata files.
-d, --depth                 Depth to spider to, default 2.
-m, --min_word_length       Minimum word length, default 3.
-x, --max_word_length       Maximum word length, default unset.
-o, --offsite               Let the spider visit other sites.
--exclude                   File containing request paths to exclude.
--allowed                   Regex pattern that URL path must match.
-w, --write                 Write words/groups to this file.
-u, --ua                    User agent to send.
-n, --no-words              Do not output the wordlist.
-g, --groups                Return groups of words as well.
--lowercase                 Lowercase all parsed words.
--with-numbers              Accept words with numbers.
--convert-umlauts           Convert common Latin-1 umlauts.
-a, --meta                  Include metadata.
--meta_file                 Output file for metadata.
-e, --email                 Include email addresses.
--email_file                Output file for email addresses.
--meta-temp-dir             Temporary directory for metadata files.
-c, --count                 Show the count for each word found.
--render                    Render pages with Playwright before extracting.
-H, --header                Send an HTTP header. Can be passed multiple times.
```

Authentication:

```text
--auth_type                 basic or digest.
--auth_user                 Authentication username.
--auth_pass                 Authentication password.
```

Proxy support:

```text
--proxy_host                Proxy host.
--proxy_port                Proxy port, default 8080.
--proxy_username            Username for proxy, if required.
--proxy_password            Password for proxy, if required.
```

Render mode uses the same extraction and output pipeline as the normal HTTP
crawler after the browser has loaded each page. Basic auth, custom headers,
user-agent, depth, same-site/offsite filtering, excludes, allowed path regexes,
emails, words, groups, and output formatting are supported. Digest auth and
some proxy edge cases depend on browser support; use the normal HTTP crawler
when those transport features are required.

Metadata extraction uses pure Python PDF and Office Open XML parsing, with
`exiftool` used opportunistically when it is available on `PATH`.

## Make Targets

```sh
make setup              # uv sync
make cewl ARGS="..."    # uv run pycewl ...
make fab ARGS="..."     # uv run fab ...
make test               # uv run pytest
make build              # uv build
make clean              # remove Python caches and build artifacts
```

## Docker

Docker packaging is pending a Python refresh. The current Dockerfile is left
unchanged in this pass and should not be treated as the primary way to run the
Python implementation.

## Troubleshooting

If `--render` cannot start Chromium, install the browser binary:

```sh
uvx --from "pycewl[render]" playwright install chromium
```

If metadata extraction misses fields in older Office documents or unusual file
types, install `exiftool` and make sure it is on `PATH`:

```sh
exiftool -ver
```

The project page has additional notes for common runtime problems:
<https://digi.ninja/projects/cewl.php>

## License

Copyright (c) 2022, Robin Wood <robin@digi.ninja>

This project is released under the Creative Commons Attribution-Share Alike 2.0
UK: England & Wales license.

<http://creativecommons.org/licenses/by-sa/2.0/uk/>

Alternatively, you can use GPL-3.0 or later.

<http://opensource.org/licenses/GPL-3.0>
