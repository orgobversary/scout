#!/usr/bin/env python3
"""Find likely public download indexes from a homepage and XML sitemaps.

Keep download_links.py alongside this script.
"""
import argparse
from collections import deque
from pathlib import PurePosixPath
import re
from shutil import which
import subprocess
import sys
from urllib.parse import unquote, urldefrag, urljoin, urlsplit
from urllib.request import urlopen
from xml.etree import ElementTree

from download_links import DEFAULT_SUFFIXES, LinkParser

MAX_BYTES = 5 * 1024 * 1024
HINT = re.compile(r"(?:^|[/. _-])(index|archive|archives|download|downloads|dataset|datasets|data|files|releases)(?:$|[/. _-])", re.I)


def fetch(url):
    try:
        with urlopen(url, timeout=10) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("response exceeds 5 MiB")
            charset = response.headers.get_content_charset() or "utf-8"
            return response.geturl(), body, charset
    except (OSError, ValueError) as error:
        print(f"Could not read {url}: {error}", file=sys.stderr)
        return None


def candidate(url):
    path = unquote(urlsplit(url).path)
    if PurePosixPath(path).name.lower().endswith(DEFAULT_SUFFIXES):
        return "file"
    if HINT.search(path):
        return "possible index"
    return None


def scout(source, sitemap_limit):
    found = {}
    home = fetch(source)
    base = home[0] if home else source
    parts = urlsplit(base)
    origin = f"{parts.scheme}://{parts.netloc}/"

    def record(href, source_url, via):
        url, _ = urldefrag(urljoin(source_url, href))
        parsed = urlsplit(url)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            kind = candidate(url)
            if kind:
                found.setdefault(url, (kind, via))

    if home:
        _, body, charset = home
        parser = LinkParser()
        parser.feed(body.decode(charset, "replace"))
        link_base = urljoin(base, parser.base or "")
        record(base, base, "input")
        for href in parser.links:
            record(href, link_base, "page link")

    robots = fetch(urljoin(origin, "robots.txt"))
    maps = deque()
    if robots:
        robots_url, body, charset = robots
        for line in body.decode(charset, "replace").splitlines():
            key, _, value = line.partition(":")
            if key.strip().lower() == "sitemap" and value.strip():
                maps.append(urljoin(robots_url, value.strip()))
    if not maps:
        maps.append(urljoin(origin, "sitemap.xml"))

    seen = set()
    while maps and len(seen) < sitemap_limit:
        url, _ = urldefrag(maps.popleft())
        parsed = urlsplit(url)
        if url in seen or parsed.scheme not in {"http", "https"} or parsed.hostname != parts.hostname:
            continue
        seen.add(url)
        response = fetch(url)
        if not response:
            continue
        sitemap_url, body, _ = response
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError:
            print(f"Could not parse XML sitemap {sitemap_url}", file=sys.stderr)
            continue
        for location in root.findall("{*}sitemap/{*}loc"):
            if location.text:
                maps.append(urljoin(sitemap_url, location.text.strip()))
        for location in root.findall("{*}url/{*}loc"):
            if location.text:
                record(location.text.strip(), sitemap_url, "sitemap")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="Domain or HTTP(S) page URL")
    parser.add_argument("--max-sitemaps", type=int, default=5, help="Maximum XML sitemap requests (default: 5)")
    parser.add_argument("--dig", action="store_true", help="Show CNAME, A and AAAA lookups before discovery")
    parser.add_argument("--list", action="store_true", help="Print only candidate URLs")
    args = parser.parse_args()
    source = args.source if "://" in args.source else f"https://{args.source}"
    parts = urlsplit(source)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        parser.error("enter a domain or HTTP(S) URL")
    if args.max_sitemaps < 0:
        parser.error("--max-sitemaps must be zero or greater")
    if args.dig:
        dig = which("dig")
        if not dig:
            parser.error("--dig requires dig on PATH")
        for record_type in ("CNAME", "A", "AAAA"):
            print(f"DNS {record_type} for {parts.hostname}", file=sys.stderr)
            subprocess.run([dig, "+short", "+time=2", "+tries=1", "-q", parts.hostname,
                            "-t", record_type], stdout=sys.stderr)

    found = scout(source, args.max_sitemaps)
    for url, (kind, via) in sorted(found.items(), key=lambda item: (item[1][0] == "file", item[0])):
        print(url if args.list else f"{kind:14}  {via:10}  {url}")
    if not found:
        print("No candidate URLs found.", file=sys.stderr)
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
