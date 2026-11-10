#!/usr/bin/env python3
"""Pick and download files from a webpage, Markdown file, or public S3 bucket.

python3 download_links.py                          # Paste a URL at the prompt
python3 download_links.py PAGE_URL -o data/raw     # Preview and pick files
python3 download_links.py PAGE_URL '2025*.zip'     # Narrow the preview
python3 download_links.py PAGE_URL --list          # Print URLs and exit

Use s3://BUCKET/PREFIX for an anonymously listable S3 bucket.
Type 'all' or a selection like '1,3-6' to review the download size. Press Enter to cancel.
Pages that generate their links in JavaScript need a direct HTML file index.
"""
import argparse
from datetime import timedelta
from fnmatch import fnmatchcase
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import re
import sys
from tempfile import NamedTemporaryFile
from time import monotonic
from urllib.parse import quote, unquote, urlencode, urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


DEFAULT_SUFFIXES = (".zip", ".csv", ".tar", ".tar.gz", ".tgz", ".gz", ".7z",
                    ".bz2", ".xz", ".zst", ".tsv", ".parquet")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.base = None

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href")
        if href and tag == "a":
            self.links.append(href)
        if href and tag == "base" and self.base is None:
            self.base = href


def markdown_links(path):
    text = path.read_text(encoding="utf-8-sig")
    # Inline and reference destinations, angle autolinks, and bare URLs.
    pattern = re.compile(
        r"(?<!!)\[[^\]\n]*\]\([ \t]*(?:<([^>\n]+)>|([^\s()]+))"
        r"|(?m:^[ \t]*\[[^\]\n]+\]:[ \t]*(?:<([^>\n]+)>|([^\s<>]+)))"
        r"|<(https?://[^>\s]+)>"
        r"|(https?://[^\s<>\[\]`]+)"
    )
    for match in pattern.finditer(text):
        *explicit, bare = match.groups()
        yield next((link for link in explicit if link), None) or bare.rstrip(".,;:!?)")


def transfer(response, output, expected_size):
    length = response.headers.get("Content-Length", "")
    total = int(length) if length.isascii() and length.isdecimal() else expected_size
    live = sys.stderr.isatty()
    received = 0
    started = last_update = monotonic()
    previous_width = 0
    try:
        while chunk := response.read1(256 * 1024):
            output.write(chunk)
            received += len(chunk)
            now = monotonic()
            if live and now - last_update >= 0.25:
                elapsed = now - started
                speed = received / elapsed
                progress = size_label(received, exact=False)
                if total:
                    progress = f"{received / total:5.1%}  {progress} / {size_label(total, exact=False)}"
                eta = f"  ETA {timedelta(seconds=int(max(0, total - received) / speed))}" if total else ""
                line = (f"{progress}  {size_label(int(speed), exact=False)}/s"
                        f"  Elapsed {timedelta(seconds=int(elapsed))}{eta}")
                print("\r" + line.ljust(previous_width), end="", file=sys.stderr, flush=True)
                previous_width = len(line)
                last_update = now
        if total is not None and received != total:
            raise OSError(f"Expected {total:,} bytes, received {received:,}")
    finally:
        if previous_width:
            print(file=sys.stderr, flush=True)


def download(url, destination, expected_size=None):
    temporary = None
    try:
        with urlopen(url, timeout=60) as response:
            with NamedTemporaryFile(dir=destination.parent, delete=False) as output:
                temporary = Path(output.name)
                transfer(response, output, expected_size)
        # Publish the completed file without overwriting an existing download.
        destination.hardlink_to(temporary)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def s3_links(bucket, prefix):
    endpoint = f"https://s3.amazonaws.com/{quote(bucket, safe='')}"
    query = {"list-type": "2", "prefix": prefix, "encoding-type": "url"}
    while True:
        with urlopen(f"{endpoint}?{urlencode(query)}", timeout=60) as response:
            listing = ElementTree.parse(response).getroot()
        for item in listing.findall("{*}Contents"):
            yield f"{endpoint}/{item.findtext('{*}Key')}", int(item.findtext("{*}Size"))
        if listing.findtext("{*}IsTruncated") != "true":
            return
        query["continuation-token"] = listing.findtext("{*}NextContinuationToken")


def size_label(size, *, exact=True):
    for unit, divisor in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if size >= divisor:
            label = f"{size / divisor:,.2f} {unit}"
            return f"{label} ({size:,} bytes)" if exact else label
    return f"{size:,} bytes"


def remote_size(url):
    try:
        with urlopen(Request(url, method="HEAD"), timeout=10) as response:
            size = int(response.headers.get("Content-Length", "-1"))
            return size if size >= 0 else None
    except (OSError, ValueError):
        return None


def select_files(count):
    while True:
        choice = input("Download [all / 1,3-6 / Enter to cancel]: ").strip().lower()
        if not choice:
            return set()
        if choice == "all":
            return set(range(1, count + 1))
        selected = set()
        try:
            for token in choice.split(","):
                start, separator, end = token.strip().partition("-")
                first = int(start)
                last = int(end) if separator else first
                if not 1 <= first <= last <= count:
                    raise ValueError
                selected.update(range(first, last + 1))
        except ValueError:
            print(f"Enter numbers or ranges between 1 and {count}.")
            continue
        return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("page", nargs="?", help="Webpage URL, local Markdown path, or s3://BUCKET/PREFIX")
    parser.add_argument("glob", nargs="?", help="Filename pattern, such as '*.zip'")
    parser.add_argument("--base-url", help="Original page URL for relative Markdown links")
    parser.add_argument("--all", action="store_true", help="Select all matches and review the total")
    parser.add_argument("--list", action="store_true", help="Print matching URLs and exit")
    parser.add_argument("--download", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-o", "--output", type=Path, help="Destination folder (default: ./downloads)")
    args = parser.parse_args()
    page_url = args.page or input("Paste a URL or local Markdown path: ").strip()
    source = urlsplit(page_url)
    if args.base_url and urlsplit(args.base_url).scheme not in {"http", "https"}:
        parser.error("--base-url must be an HTTP or HTTPS URL")
    try:
        if not source.scheme:
            base = args.base_url or ""
            candidates = [(href, None) for href in markdown_links(Path(page_url).expanduser())]
        elif source.scheme == "s3" and source.hostname:
            base = ""
            candidates = list(s3_links(source.hostname, unquote(source.path.lstrip("/"))))
        elif source.scheme in {"http", "https"}:
            links = LinkParser()
            with urlopen(page_url, timeout=60) as page:
                base = page.geturl()
                links.feed(page.read().decode(page.headers.get_content_charset() or "utf-8", "replace"))
            base = urljoin(base, links.base or "")
            candidates = [(href, None) for href in links.links]
        else:
            parser.error("source must be an HTTP, HTTPS, or s3:// URL or a local Markdown path")
    except (OSError, ValueError, ElementTree.ParseError) as error:
        parser.exit(1, f"Could not list source: {error}\n")

    matches = {}
    for href, size in candidates:
        url, _ = urldefrag(urljoin(base, href))
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or parts.path.endswith("/"):
            continue
        name = unquote(PurePosixPath(parts.path).name)
        if not name or name in {".", ".."} or any(c in name for c in "/\\\x00"):
            continue
        if args.glob is not None:
            matches_name = fnmatchcase(name, args.glob)
        else:
            matches_name = name.lower().endswith(DEFAULT_SUFFIXES)
        if matches_name:
            matches[url] = (name, size)

    if not matches:
        parser.exit(1, "No matching file links found. Relative Markdown links need --base-url. Dynamic webpages need a direct index.\n")
    files = list(matches.items())
    if args.list:
        for url, _ in files:
            print(url)
        return 0

    for index, (url, (name, size)) in enumerate(files, 1):
        detail = size_label(size) if size is not None else urlsplit(url).netloc
        print(f"{index:>4}. {name!r}  [{detail!r}]")

    folder = args.output
    if folder is None:
        folder = Path(input("Save to [./downloads]: ").strip() or "downloads")
    folder = folder.expanduser()
    print(f"Destination: {folder.absolute()}")
    selected = range(1, len(files) + 1) if args.all else select_files(len(files))
    if not selected:
        return 0
    pending = {}
    skipped = 0
    for index in sorted(selected):
        url, (name, size) = files[index - 1]
        destination = folder / name
        if destination.exists() or destination in pending:
            skipped += 1
            continue
        pending[destination] = (url, size)

    if not pending:
        print(f"Nothing to download. {skipped} existing or duplicate filename(s) skipped.")
        return 0

    if any(size is None for _, size in pending.values()):
        print("Checking sizes for the selected files...", flush=True)
    total = unknown = 0
    for destination, (url, size) in pending.items():
        if size is None:
            size = remote_size(url)
            pending[destination] = (url, size)
        if size is None:
            unknown += 1
        else:
            total += size
    extra = f" + {unknown} file(s) of unknown size" if unknown else ""
    print(f"Total download: {size_label(total)}{extra} across {len(pending)} file(s).")
    if skipped:
        print(f"Skipping {skipped} existing or duplicate filename(s).")
    if input("Start download? [y/N]: ").strip().lower() not in {"y", "yes"}:
        return 0

    folder.mkdir(parents=True, exist_ok=True)
    failed = False
    for destination, (url, expected_size) in pending.items():
        name = destination.name
        try:
            print(f"Downloading {name!r}...", flush=True)
            download(url, destination, expected_size)
            print(f"Saved {destination}")
        except FileExistsError:
            print(f"Skipped {destination} (already exists)")
        except OSError as error:
            failed = True
            print(f"Failed {url}: {error}", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nCancelled.")
    except OSError as error:
        sys.exit(str(error))
