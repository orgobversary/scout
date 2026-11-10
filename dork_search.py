#!/usr/bin/env python3
"""Build a Google search query for datasets, documents, or other public pages.

Run without arguments for prompts. Use --print-only to copy the URL.
"""
import argparse
from urllib.parse import urlencode
import webbrowser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("terms", nargs="*", help="Keywords or raw Google operators")
    parser.add_argument("--exact", action="append", default=[], help="Exact phrase (repeatable)")
    parser.add_argument("--site", help="Limit to a domain or URL prefix")
    parser.add_argument("--filetype", help="File extension, e.g. csv or pdf")
    parser.add_argument("--exclude", action="append", default=[], help="Exclude a word or phrase (repeatable)")
    parser.add_argument("--after", help="Updated after a year or date")
    parser.add_argument("--before", help="Updated before a year or date")
    parser.add_argument("--print-only", action="store_true", help="Print the query and URL without opening a browser")
    args = parser.parse_args()

    terms = " ".join(args.terms).strip()
    if not any((terms, args.exact, args.site, args.filetype, args.exclude, args.after, args.before)):
        terms = input("Keywords or raw query: ").strip()
        exact = input("Exact phrase [optional]: ").strip()
        if exact:
            args.exact.append(exact)
        args.site = input("Site/domain [optional]: ").strip()
        args.filetype = input("File type [optional]: ").strip()

    query = [terms] if terms else []
    query.extend(f'"{phrase}"' for phrase in args.exact)
    for operator, value in (
        ("site", args.site),
        ("filetype", (args.filetype or "").lstrip(".")),
        ("after", args.after),
        ("before", args.before),
    ):
        if value:
            if any(character.isspace() for character in value):
                parser.error(f"--{operator} requires a value without spaces")
            query.append(f"{operator}:{value}")
    for value in args.exclude:
        query.append(f'-"{value}"' if any(c.isspace() for c in value) else f"-{value}")
    if not query:
        parser.error("enter at least one search term or filter")

    query_text = " ".join(query)
    url = "https://www.google.com/search?" + urlencode({"q": query_text})
    print(query_text)
    print(url, flush=True)
    if not args.print_only and input("Open in browser? [y/N]: ").strip().lower() in {"y", "yes"}:
        if not webbrowser.open_new_tab(url):
            print("Could not launch a browser. Paste the URL above into your browser.")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("\nCancelled.")
