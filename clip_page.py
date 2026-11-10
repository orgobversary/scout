#!/usr/bin/env python3
"""Preview or save a Defuddle clip with a separate list of download links.

Requires defuddle on PATH. Keep download_links.py alongside this script.
"""
import argparse
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from shutil import which
import subprocess
import sys
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit
from urllib.request import urlopen

from download_links import DEFAULT_SUFFIXES, LinkParser


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", help="Webpage URL or saved HTML file")
    parser.add_argument("-o", "--output", type=Path, help="Save the clip to a Markdown file")
    parser.add_argument("--base-url", help="Original webpage URL for saved HTML")
    parser.add_argument("--glob", help="Filter download links, e.g. '*.zip'")
    parser.add_argument("--links-only", action="store_true", help="Show only the file links")
    args = parser.parse_args()
    source = args.source or input("Paste a URL or saved HTML path: ").strip()
    scheme = urlsplit(source).scheme
    if scheme not in {"", "http", "https"}:
        parser.error("source must be an HTTP(S) URL or local HTML path")
    if args.base_url and urlsplit(args.base_url).scheme not in {"http", "https"}:
        parser.error("--base-url must be an HTTP(S) URL")

    defuddle = which("defuddle")
    if not args.links_only and not defuddle:
        parser.exit(1, "Install Defuddle first with npm install -g defuddle.\n")

    try:
        if scheme:
            with urlopen(source, timeout=30) as response:
                base = response.geturl()
                html = response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
        else:
            base = args.base_url or ""
            html = Path(source).expanduser().read_text(encoding="utf-8-sig")

        links = LinkParser()
        links.feed(html)
        base = urljoin(base, links.base or "")
        downloads = {}
        for href in links.links:
            url, _ = urldefrag(urljoin(base, href))
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path.endswith("/"):
                continue
            name = unquote(PurePosixPath(parts.path).name)
            matches = fnmatchcase(name, args.glob) if args.glob else name.lower().endswith(DEFAULT_SUFFIXES)
            if matches:
                downloads[url] = name

        content = ""
        if not args.links_only:
            result = subprocess.run(
                [defuddle, "parse", "-", "--markdown"], input=html,
                text=True, encoding="utf-8", stdout=subprocess.PIPE, timeout=60,
            )
            if result.returncode:
                parser.exit(1, "Defuddle failed. Try --links-only to inspect the original HTML.\n")
            content = result.stdout.strip()

        lines = ["## Download links", ""]
        for url, name in downloads.items():
            label = " ".join(name.split()).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            target = quote(url, safe=":/?#[]@!$&'()*+,;=%")
            lines.append(f"- [{label}](<{target}>)")
        if not downloads:
            lines.append("No matching download links found in the original HTML.")

        clip = "\n\n".join(part for part in (content, "\n".join(lines)) if part) + "\n"
        if args.output:
            with args.output.expanduser().open("x", encoding="utf-8") as output:
                output.write(clip)
            print(f"Saved {args.output} ({len(downloads)} download links)")
        else:
            print(clip, end="")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Could not clip source: {error}\n")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nCancelled.")
