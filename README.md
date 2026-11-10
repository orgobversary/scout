# Download Links

A small Python CLI for when you find a page full of ZIPs, CSVs, or archives and want to grab a batch in one go. Give it a webpage URL, a local Markdown export, or a public S3 bucket. Preview the files, pick a destination, and see the total size before you start.

## Quick start

Save `download_links.py` and run it from the directory where you saved it. It uses the Python 3 standard library, so there are no packages to install.

```bash
python3 download_links.py
```

1. Paste a webpage URL, an S3 URI, or the path to a local Markdown file.
2. Review the numbered list and choose a destination. Press Enter to use `./downloads` relative to your current directory.
3. Enter `all`, a single number like `2`, or a selection like `1,3-6`. Press Enter at the selection prompt to cancel.
4. Review the total and type `y` at `Start download? [y/N]`. The CLI creates the destination folder after confirmation.

Pass `--all` to skip the selection prompt and `-o` to skip the folder prompt. The final confirmation still applies.

## Examples

### Download files from a webpage

Pass the URL of a page with direct links in its HTML. Replace the example URL with your own.

```bash
# Preview and pick files
python3 download_links.py 'https://example.org/datasets/index.html' -o ./data/raw

# Select all CSV files and review the total
python3 download_links.py 'https://example.org/datasets/index.html' '*.csv' --all -o ./data/raw
```

### Use a local Markdown export

Pass the system path to a Markdown file containing download links. Quote paths with spaces.

```bash
python3 download_links.py "$HOME/Downloads/archive export.md" --all -o "$HOME/data/raw"
```

If the export contains relative links such as `[January](files/january.zip)`, pass the original page URL so the CLI can resolve them.

```bash
python3 download_links.py ./archive.md '*.zip' --base-url 'https://example.org/data/index.html' -o ./data/raw
```

### Download a year of Citi Bike trip data from S3

The URI `s3://tripdata/2025` uses `tripdata` as the bucket name and `2025` as the object-key prefix. The filename glob selects the NYC ZIPs for that year.

```bash
# List the matching URLs without downloading the archives
python3 download_links.py 's3://tripdata/2025' '2025*.zip' --list

# Select all 12 monthly archives and review the total
python3 download_links.py 's3://tripdata/2025' '2025*.zip' --all -o "$HOME/data/citi-bike/2025"
```

If you are already in the directory where you want the files, use `-o .`. For this example, see the [Citi Bike Data Sharing Policy](https://citibikenyc.com/data-sharing-policy) before sharing downloaded data.

## Commands and flags

```text
python3 download_links.py [SOURCE] [GLOB] [OPTIONS]
```

| Argument or flag | What it does |
| --- | --- |
| `SOURCE` | HTTP(S) webpage, local Markdown path, or `s3://BUCKET/PREFIX`. Omit it to enter the source interactively. |
| `GLOB` | Optional case-sensitive pattern applied to the filename, such as `'2025*.zip'` or `'*.tar.gz'`. Quote it so your shell passes it through. |
| `-o DIR`, `--output DIR` | Set the destination directory. Without this flag, the CLI prompts for a folder and offers `./downloads` as the default. |
| `--all` | Select every match and go straight to the size review after choosing a folder. |
| `--list` | Print one matching URL per line and exit before the folder and approval prompts. |
| `--base-url URL` | Resolve relative links in a Markdown export against the original HTTP(S) page URL. |
| `-h`, `--help` | Show the CLI help. |

Without a glob, the CLI matches `.zip`, `.csv`, `.tar`, `.tar.gz`, `.tgz`, `.gz`, `.7z`, `.bz2`, `.xz`, `.zst`, `.tsv`, and `.parquet` case-insensitively.

## What the size review counts

S3 previews show the sizes returned by the bucket listing. For webpage and Markdown sources, the CLI checks the selected URLs for a `Content-Length` header. If a server leaves the size unknown, the CLI shows the known subtotal plus the number of files with unknown sizes. The total describes the files as downloaded, before extraction.

The CLI saves files by filename into the chosen folder. Existing files and later matches that share a destination filename are skipped and excluded from the total.

## Source requirements

- **Webpages** need file links in their HTML. If a site builds its list in JavaScript, use a Markdown export containing the links or a public S3 URI if the archive is backed by a listable bucket.
- **Markdown** can contain inline links, reference definitions, or pasted URLs. Use `--base-url` for relative links.
- **S3** requires anonymous permission to list the bucket and download the selected objects. A direct object URL can work even when listing is restricted.
