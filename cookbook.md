# Dork, Scout, Clip, Download

Run these recipes from the directory containing the four Python scripts. Use Python 3.10 or newer. For readable Markdown clips, install Defuddle with `npm install -g defuddle`. The clipper's `--links-only` mode works without it.

| Step | Script | Output |
| --- | --- | --- |
| Search | `dork_search.py` | Google query and browser URL |
| Scout | `scout_indexes.py` | Candidate files and archive pages from links and sitemaps |
| Clip | `clip_page.py` | Markdown with a separate list of direct download links |
| Download | `download_links.py` | Selected files saved to your output directory |

## Find PGA TOUR statistics and download a CSV

### 1. Search Google

Start broad, then change one search term at a time. Type `y` to open the browser or add `--print-only` to copy the URL.

```bash
python3 dork_search.py golf stats --filetype csv
python3 dork_search.py statistics --exact 'PGA Tour' --filetype csv
python3 dork_search.py --exact 'PGA Tour' --exact 'strokes gained' --filetype csv
python3 dork_search.py dataset --exact 'PGA Tour' --exact 'round scores'
```

Use `--filetype csv` in Google. Use a quoted glob like `'*.csv'` when clipping or downloading. The last query leaves off the file type so it can surface dataset pages whose actual CSVs are behind a download button or an asset list.

### 2. Scout a result

Copy a promising publisher or archive URL when prompted. The scout checks links on that page and up to three same-host XML sitemaps.

```bash
read -r -p 'Publisher or archive URL: ' source_url
python3 scout_indexes.py "$source_url" --max-sitemaps 3
```

Open a candidate and check the publisher, seasons, row granularity, and reuse terms. For a stats bot, a row per player per tournament answers different questions than a row per player per round.

#### Check robots.txt and follow its sitemap

Use the site's origin for `robots.txt`. This example uses the public golfastr documentation site. Run it to see the site's current response.

```bash
origin='https://golfastr.com'
curl -fsSL "$origin/robots.txt" | awk 'tolower($1) == "sitemap:" {print $2}'
python3 scout_indexes.py "$origin" --max-sitemaps 3
```

The first command prints any advertised sitemap URLs. The scout reads `robots.txt` itself, follows same-host sitemap URLs, and tries `/sitemap.xml` if no sitemap is advertised. If you only want links from the supplied page, set `--max-sitemaps 0`. Sitemap entries help you discover URLs. Check the publisher's reuse terms before redistributing a dataset.

### 3. Clip the download page

Paste the page that actually contains the file links. A project landing page and its downloadable assets can be separate pages.

```bash
mkdir -p clips
read -r -p 'Page containing the CSV links: ' download_page
python3 clip_page.py "$download_page" --glob '*.csv' -o clips/pga-stats.md
```

If you just want a link manifest, add `--links-only`. Use a new output filename for each source because the clipper creates new files and refuses to overwrite existing ones.

### 4. Preview and download from the clip

```bash
python3 download_links.py clips/pga-stats.md '*.csv' --list
python3 download_links.py clips/pga-stats.md '*.csv' -o data/raw/golf
```

The first command prints matching URLs. The second lets you choose by number or range, review the size, and confirm. Add `--all` to select every match while keeping the final confirmation. To narrow to a single season, use a pattern like `'*2025*.csv'` if the filenames include the year.

## Clip saved HTML

If the terminal cannot fetch a page but your browser can, save the HTML containing the file links and supply the original page URL to resolve relative paths.

```bash
mkdir -p clips
read -r -p 'Original page URL: ' source_url
python3 clip_page.py ./saved-page.html --base-url "$source_url" --links-only --glob '*.csv' -o clips/saved-links.md
python3 download_links.py clips/saved-links.md '*.csv' --list
```

If the site builds links dynamically and they are absent from the saved HTML, expand the assets in your browser and paste the direct file URLs into a Markdown file, one per line. Pass that file to the downloader.

## Download the 2025 NYC Citi Bike archive from S3

When you already know the public bucket and prefix, start at the downloader. Preview first and then select the full year.

```bash
python3 download_links.py 's3://tripdata/2025' '2025*.zip' --list
python3 download_links.py 's3://tripdata/2025' '2025*.zip' --all -o data/raw/citi-bike/2025
```

The prefix and glob select the NYC monthly archives. Existing files are skipped by filename, so you can rerun the command to pick up missing archives. Check the [Citi Bike Data Sharing Policy](https://citibikenyc.com/data-sharing-policy) before redistributing the files.
