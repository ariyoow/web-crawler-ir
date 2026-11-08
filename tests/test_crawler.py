import dataclasses
import json

import pytest

from crawler.crawler import Crawler
from crawler.fetcher import FetchResult
from crawler.frontier import Frontier
from crawler.parser import Parser
from crawler.storage import Storage
from crawler.url_checker import URLChecker


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def page(html, final_url=None):
    """A successful HTML response (url/final_url are filled by the fetcher)."""
    return FetchResult(
        url="", final_url=final_url or "", html=html,
        status_code=200, content_type="text/html", success=True,
    )


def fail(status=None, error="error"):
    """A failed response."""
    return FetchResult(
        url="", final_url="", html=None, status_code=status,
        content_type=None, success=False, error=error,
    )


class FakeFetcher:
    """Serves a fake site. Values: FetchResult, or an Exception to raise."""

    def __init__(self, site):
        self.site = site
        self.requested = []
        self.closed = False

    def fetch(self, url):
        self.requested.append(url)
        res = self.site.get(url)

        if res is None:
            res = fail(404, "HTTP Error: 404")

        if isinstance(res, BaseException):
            raise res

        return dataclasses.replace(
            res, url=url, final_url=res.final_url or url
        )

    def close(self):
        self.closed = True


def make_crawler(tmp_path, site, seed="https://example.com/",
                 max_pages=100, delay=0):
    fetcher = FakeFetcher(site)
    storage = Storage(tmp_path / "pages", tmp_path / "meta")

    crawler = Crawler(
        seed_url=seed,
        max_pages=max_pages,
        request_delay=delay,
        fetcher=fetcher,
        frontier=Frontier(),
        parser=Parser(),
        url_checker=URLChecker(),
        storage=storage,
        stats_path=tmp_path / "stats.json",
    )
    return crawler, fetcher


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Never really sleep in tests; record the calls instead."""
    calls = []
    monkeypatch.setattr("crawler.crawler.time.sleep", calls.append)
    return calls


SITE = {
    "https://example.com/": page(
        '<a href="/a">a</a>'
        '<a href="https://other.com/x">external</a>'
        '<a href="/missing">missing</a>'
    ),
    "https://example.com/a": page('<a href="/">home</a><a href="/b">b</a>'),
    "https://example.com/b": page("<p>no links</p>"),
}


# ---------------------------------------------------------------------- #
# Basic behaviour
# ---------------------------------------------------------------------- #

def test_full_crawl(tmp_path):
    crawler, fetcher = make_crawler(tmp_path, SITE)
    stats = crawler.run()

    assert stats["saved_pages"] == 3
    assert stats["failed_requests"] == 1
    assert stats["failures_by_reason"] == {"HTTP 404": 1}
    assert "https://other.com/x" not in fetcher.requested
    assert len(fetcher.requested) == len(set(fetcher.requested))
    assert stats["total_requests"] == len(fetcher.requested) == 4


def test_single_page_site_terminates(tmp_path):
    site = {"https://example.com/": page("<p>nothing</p>")}
    crawler, fetcher = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert stats["saved_pages"] == 1
    assert stats["queue_remaining"] == 0
    assert fetcher.requested == ["https://example.com/"]


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_respects_max_pages(tmp_path, limit):
    crawler, _ = make_crawler(tmp_path, SITE, max_pages=limit)
    stats = crawler.run()

    assert stats["saved_pages"] == limit
    assert len(list((tmp_path / "pages").glob("*.html"))) == limit
    assert len(list((tmp_path / "meta").glob("*.json"))) == limit


def test_queue_remaining_when_stopped_early(tmp_path):
    crawler, _ = make_crawler(tmp_path, SITE, max_pages=1)
    stats = crawler.run()

    # /a and /missing were queued; other.com was rejected
    assert stats["queue_remaining"] == 2


def test_bfs_order(tmp_path):
    site = {
        "https://example.com/": page('<a href="/a">a</a><a href="/b">b</a>'),
        "https://example.com/a": page('<a href="/a1">a1</a>'),
        "https://example.com/b": page("<p>b</p>"),
        "https://example.com/a1": page("<p>a1</p>"),
    }
    crawler, fetcher = make_crawler(tmp_path, site)
    crawler.run()

    assert fetcher.requested == [
        "https://example.com/",
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/a1",
    ]


# ---------------------------------------------------------------------- #
# Seed and domain handling
# ---------------------------------------------------------------------- #

@pytest.mark.parametrize("bad_seed", [
    "ftp://example.com/", "not a url", "", "mailto:a@b.com",
])
def test_invalid_seed_raises(tmp_path, bad_seed):
    crawler, fetcher = make_crawler(tmp_path, SITE)
    crawler.seed_url = bad_seed

    with pytest.raises(ValueError):
        crawler.run()

    assert fetcher.requested == []


def test_www_is_stripped_from_allowed_domain(tmp_path):
    crawler, _ = make_crawler(
        tmp_path, {}, seed="https://www.example.com/"
    )
    assert crawler.allowed_domain == "example.com"


def test_subdomains_are_followed(tmp_path):
    site = {
        "https://www.example.com/": page(
            '<a href="https://blog.example.com/p">blog</a>'
            '<a href="https://example.com/q">bare</a>'
            '<a href="https://notexample.com/">evil</a>'
        ),
        "https://blog.example.com/p": page("<p>blog</p>"),
        "https://example.com/q": page("<p>q</p>"),
    }
    crawler, fetcher = make_crawler(
        tmp_path, site, seed="https://www.example.com/"
    )
    stats = crawler.run()

    assert stats["saved_pages"] == 3
    assert "https://notexample.com/" not in fetcher.requested


# ---------------------------------------------------------------------- #
# Redirects
# ---------------------------------------------------------------------- #

def test_redirect_out_of_scope_is_skipped(tmp_path):
    site = {
        "https://example.com/": page('<a href="/go">go</a>'),
        "https://example.com/go": page(
            "<p>external</p>", final_url="https://other.com/landing"
        ),
    }
    crawler, _ = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert stats["saved_pages"] == 1
    assert stats["skipped_out_of_scope"] == 1


def test_different_urls_with_same_final_url_saved_once(tmp_path):
    site = {
        "https://example.com/": page('<a href="/a">a</a><a href="/b">b</a>'),
        "https://example.com/a": page(
            "<p>c</p>", final_url="https://example.com/c"
        ),
        "https://example.com/b": page(
            "<p>c</p>", final_url="https://example.com/c"
        ),
    }
    crawler, _ = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert stats["saved_pages"] == 2           # "/" and "/c"
    assert stats["skipped_duplicate_pages"] == 1


def test_relative_links_use_final_url_as_base(tmp_path):
    site = {
        "https://example.com/": page(
            '<a href="item">item</a>',
            final_url="https://example.com/shop/",
        ),
        "https://example.com/shop/item": page("<p>item</p>"),
    }
    crawler, fetcher = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert "https://example.com/shop/item" in fetcher.requested
    assert "https://example.com/item" not in fetcher.requested
    assert stats["saved_pages"] == 2


# ---------------------------------------------------------------------- #
# Failures
# ---------------------------------------------------------------------- #

def test_failure_reasons_are_classified(tmp_path):
    site = {
        "https://example.com/": page(
            '<a href="/e404">1</a><a href="/e500">2</a>'
            '<a href="/pdf">3</a><a href="/net">4</a>'
        ),
        "https://example.com/e404": fail(404, "HTTP Error: 404"),
        "https://example.com/e500": fail(500, "HTTP Error: 500"),
        # Same shape the real Fetcher returns: status 200 + error text
        "https://example.com/pdf": fail(200, "Unsupported Content-Type"),
        "https://example.com/net": fail(None, "timed out"),
    }
    crawler, _ = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert stats["saved_pages"] == 1
    assert stats["failed_requests"] == 4
    assert stats["failures_by_reason"] == {
        "HTTP 404": 1,
        "HTTP 500": 1,
        "Unsupported Content-Type": 1,
        "Network error": 1,
    }


def test_unexpected_exception_does_not_stop_crawl(tmp_path):
    site = {
        "https://example.com/": page('<a href="/boom">x</a><a href="/ok">y</a>'),
        "https://example.com/boom": RuntimeError("kaboom"),
        "https://example.com/ok": page("<p>ok</p>"),
    }
    crawler, _ = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert stats["unexpected_errors"] == 1
    assert stats["saved_pages"] == 2
    assert stats["total_requests"] == 3


def test_empty_html_counts_as_storage_error(tmp_path):
    site = {
        "https://example.com/": page('<a href="/empty">e</a>'),
        "https://example.com/empty": page(""),
    }
    crawler, _ = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert stats["storage_errors"] == 1
    assert stats["saved_pages"] == 1


def test_keyboard_interrupt_stops_cleanly(tmp_path):
    site = {
        "https://example.com/": page('<a href="/stop">s</a><a href="/b">b</a>'),
        "https://example.com/stop": KeyboardInterrupt(),
        "https://example.com/b": page("<p>b</p>"),
    }
    crawler, fetcher = make_crawler(tmp_path, site)
    stats = crawler.run()                      # must not raise

    assert stats["interrupted"] is True
    assert stats["saved_pages"] == 1
    assert fetcher.closed is True
    assert (tmp_path / "stats.json").exists()
    assert "https://example.com/b" not in fetcher.requested


# ---------------------------------------------------------------------- #
# Links and duplicates
# ---------------------------------------------------------------------- #

def test_fragment_and_duplicate_links_requested_once(tmp_path):
    site = {
        "https://example.com/": page(
            '<a href="/a#top">1</a><a href="/a">2</a><a href="/a?">3</a>'
        ),
        "https://example.com/a": page("<p>a</p>"),
    }
    crawler, fetcher = make_crawler(tmp_path, site)
    crawler.run()

    assert fetcher.requested.count("https://example.com/a") == 1


def test_link_statistics(tmp_path):
    site = {
        "https://example.com/": page(
            '<a href="/a">a</a>'
            '<a href="/a">a again</a>'
            '<a href="mailto:x@example.com">mail</a>'
            '<a href="https://other.com/">ext</a>'
        ),
        "https://example.com/a": page("<p>a</p>"),
    }
    crawler, _ = make_crawler(tmp_path, site, max_pages=1)
    stats = crawler.run()

    assert stats["links_extracted"] == 4
    assert stats["links_new"] == 1
    assert stats["links_duplicate"] == 0


def test_already_discovered_links_counted_as_duplicate(tmp_path):
    site = {
        "https://example.com/": page('<a href="/a">a</a>'),
        "https://example.com/a": page('<a href="/">home</a>'),
    }
    crawler, _ = make_crawler(tmp_path, site)
    stats = crawler.run()

    assert stats["links_duplicate"] == 1       # "/" found again on /a


# ---------------------------------------------------------------------- #
# Delay
# ---------------------------------------------------------------------- #

def test_delay_between_requests_but_not_after_last(tmp_path, no_sleep):
    site = {
        "https://example.com/": page('<a href="/a">a</a>'),
        "https://example.com/a": page('<a href="/b">b</a>'),
        "https://example.com/b": page("<p>b</p>"),
    }
    crawler, _ = make_crawler(tmp_path, site, delay=0.5)
    crawler.run()

    assert no_sleep == [0.5, 0.5]              # 3 requests -> 2 sleeps


def test_delay_applied_after_failed_requests(tmp_path, no_sleep):
    site = {
        "https://example.com/": page('<a href="/missing">m</a>'),
    }
    crawler, _ = make_crawler(tmp_path, site, delay=1)
    crawler.run()

    assert no_sleep == [1]                     # after "/", before /missing


# ---------------------------------------------------------------------- #
# Output files
# ---------------------------------------------------------------------- #

def test_stats_file_matches_returned_stats(tmp_path):
    crawler, fetcher = make_crawler(tmp_path, SITE)
    stats = crawler.run()

    saved = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))

    assert saved == stats
    assert saved["elapsed_seconds"] >= 0
    assert fetcher.closed is True


def test_metadata_matches_saved_page(tmp_path):
    crawler, _ = make_crawler(tmp_path, SITE, max_pages=1)
    crawler.run()

    storage = Storage(tmp_path / "pages", tmp_path / "meta")
    meta = storage.get_metadata("page_0001")

    assert meta["url"] == "https://example.com/"
    assert meta["status_code"] == 200
    assert "/a" in storage.get_page("page_0001")