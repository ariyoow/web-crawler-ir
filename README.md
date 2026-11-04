# IR Single-Thread Web Crawler

A single-threaded web crawler built as a university project for an **Information Retrieval** course.

## Requirements
- Single-threaded crawler with all core components: **Queue**, **Fetcher**, **Parser**, **URLChecker**
- Downloads **only HTML pages**
- Output includes every downloaded HTML page **together with its URL**
- Pages discovered under the same site subdomain are acceptable

## Architecture
| Component | Responsibility |
|-----------|----------------|
| Queue | Holds URLs pending crawling (frontier) |
| Fetcher | Downloads pages over HTTP |
| Parser | Extracts links from HTML |
| URLChecker | Validates/deduplicates URLs, filters non-HTML, same-site policy |

## Output Format
Each downloaded page is stored alongside its URL, e.g.:
output/
├── index.json      # list of {url, file}
├── page_0001.html
├── page_0002.html
└── ...

## Tech Stack
- Python 3.x
- [requests / urllib] + [BeautifulSoup / lxml]

## Usage
pip install -r requirements.txt
python crawler.py --start-url https://example.com --max-pages 100
