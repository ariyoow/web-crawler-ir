# IR Single-Thread Web Crawler

A single-threaded, breadth-first web crawler built as a university project for an Information Retrieval course. It downloads HTML pages from one site (including its subdomains), stores every page together with its URL, and reports crawl statistics.

## Requirements Coverage

| Requirement | Where it is handled |
|---|---|
| Single-threaded crawler | `Crawler.run()` processes one URL at a time, no threads |
| Queue, Fetcher, Parser, URLChecker | `frontier.py`, `fetcher.py`, `parser.py`, `url_checker.py` |
| Downloads only HTML pages | `Fetcher` rejects any response whose `Content-Type` is not `text/html` or `application/xhtml+xml` |
| Every page saved with its URL | `Storage` writes `page_XXXX.html` plus `page_XXXX.json` containing the URL |
| Subdomains of the site are acceptable | `URLChecker.is_valid` accepts the domain and all of its subdomains |

## Architecture

| Module | Responsibility |
|---|---|
| `main.py` | Entry point: sets up logging, builds the components, runs the crawler |
| `config.py` | All tunable parameters (seed, limits, timeouts, paths) |
| `crawler.py` | Core loop: connects all components, collects statistics |
| `frontier.py` | FIFO queue of pending URLs plus a set of already discovered URLs |
| `fetcher.py` | HTTP GET with `requests`, timeout, retries with exponential backoff, Content-Type check |
| `parser.py` | Extracts `href` values from `<a>` tags using BeautifulSoup |
| `url_checker.py` | Resolves relative URLs, normalizes, validates scheme/domain, removes duplicates |
| `storage.py` | Atomically writes HTML and metadata files with sequential page IDs |

### Crawl Workflow

1. `main` loads configuration and builds the components.
2. `Crawler` normalizes the seed URL and adds it to the `Frontier`.
3. Loop until `MAX_PAGES` pages are saved or the queue is empty:
   1. `Frontier` returns the next URL.
   2. `Fetcher` downloads it (failures are counted and skipped).
   3. The final URL (after redirects) is checked: pages that redirected outside the allowed domain, or whose final URL was already saved, are skipped.
   4. `Storage` saves the HTML and metadata.
   5. `Parser` extracts links; `URLChecker` resolves them against the **final** URL, validates and deduplicates them.
   6. `Frontier` receives the new URLs.
   7. The crawler sleeps for `REQUEST_DELAY` seconds.
4. Statistics are printed and saved to `data/stats.json`.

The allowed domain is derived from the seed URL (`www.` is removed), so `www.example.com` as seed allows `example.com` and every `*.example.com`.

## Output Format

```
data/
├── pages/
│   ├── page_0001.html
│   ├── page_0002.html
│   └── ...
├── metadata/
│   ├── page_0001.json
│   ├── page_0002.json
│   └── ...
└── stats.json
logs/
└── crawl_YYYYMMDD_HHMMSS.log
```

Each metadata file links a page to its URL:

```json
{
    "url": "https://example.com/",
    "final_url": "https://example.com/",
    "status_code": 200,
    "content_type": "text/html; charset=utf-8",
    "fetched_at": "2026-11-08T08:00:23+00:00",
    "file_name": "page_0001.html",
    "response_size": 12345
}
```

`stats.json` contains: total requests, saved pages, failed requests (grouped by reason), skipped out-of-scope and duplicate pages, storage and unexpected errors, links extracted / rejected / new / duplicate, remaining queue size, whether the run was interrupted, and elapsed time.

## Installation

```
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Dependencies: `requests`, `beautifulsoup4` (see `requirements.txt`). Development: `pytest` (see `requirements-dev.txt`).

## Usage

Edit `crawler/config.py`, then run from the project root:

```
python -m crawler.main
```

Main settings:

| Setting | Meaning |
|---|---|
| `SEED_URL` | Starting URL; its domain defines the crawl scope |
| `MAX_PAGES` | Number of successfully saved pages after which crawling stops |
| `REQUEST_TIMEOUT` | Per-request timeout in seconds |
| `MAX_RETRIES` | Retries for timeouts, connection errors, HTTP 408/429/5xx (so up to `MAX_RETRIES + 1` attempts) |
| `REQUEST_DELAY` | Pause between requests in seconds (politeness) |
| `USER_AGENT` | User-Agent header sent with every request |
| `PAGES_DIR`, `METADATA_DIR`, `LOGS_DIR`, `STATS_PATH` | Output locations |

Press `Ctrl+C` to stop early; statistics up to that moment are still saved.

> Delete `data/pages` and `data/metadata` before a final run: `Storage` continues numbering from existing files, so test runs would mix with the final output.

## Testing

```
pip install -r requirements-dev.txt
pytest -v
```

`tests/test_url_checker.py` covers URL handling. `tests/test_crawler.py` runs the real `Crawler`, `Frontier`, `Parser`, `URLChecker` and `Storage` against a fake in-memory site (a fake `Fetcher`), so it needs no network. It checks BFS order, the page limit, domain and subdomain scope, redirects, duplicate detection, failure classification, error handling, `Ctrl+C`, delays and output files.

## Design Decisions

- **Stop condition counts saved pages**, not requests, so a run produces exactly `MAX_PAGES` stored pages.
- **Deduplication happens when a URL enters the queue** (`Frontier.discovered_urls`), after normalization (lowercase scheme/host, default ports and fragments removed).
- **Delay after every request**, including failed ones, to avoid hammering the server.
- **Each URL is processed in its own `try/except`**, so one unexpected error cannot abort the whole crawl.
- **Components are injected into `Crawler`**, which makes it testable without the network.

## Known Limitations

- **No JavaScript execution.** Only server-rendered HTML is crawled. Sites that build their pages on the client (for example the Digikala home page, which returns an empty Next.js shell with no `<a>` tags) yield no links from such pages. *(Describe here which seed / strategy was finally used and why.)*
- **`robots.txt` is not checked.** Politeness relies on `REQUEST_DELAY` only.
- **Single-threaded**, so throughput is limited by `REQUEST_DELAY` and network latency.
- **No URL prioritization.** Plain BFS can fill the queue with query-parameter variants of the same page.
- **The whole response body is read into memory** (no size cap).
- `links_rejected` also counts duplicate links that appear within the same page.

## Results of the Final Run

*(Fill in after the final run, taken from `data/stats.json`.)*

| Metric | Value |
|---|---|
| Seed URL | |
| Saved pages | |
| Total requests | |
| Failed requests (by reason) | |
| Links extracted / new | |
| Elapsed time | |
