
import pytest

from crawler.frontier import Frontier


@pytest.fixture
def frontier():
    return Frontier()


def test_initial_frontier_is_empty(frontier):
    assert frontier.is_empty()


def test_add_single_url(frontier):
    added_count = frontier.add_urls(["https://example.com"])

    assert added_count == 1
    assert not frontier.is_empty()


def test_add_multiple_urls(frontier):
    urls = [
        "https://example.com",
        "https://example.com/about",
        "https://example.com/contact"
    ]

    added_count = frontier.add_urls(urls)

    assert added_count == 3
    assert len(frontier.queue) == 3


def test_fifo_order(frontier):
    urls = [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c"
    ]

    frontier.add_urls(urls)

    assert frontier.get_next_url() == urls[0]
    assert frontier.get_next_url() == urls[1]
    assert frontier.get_next_url() == urls[2]


def test_duplicate_urls_are_not_added(frontier):
    urls = [
        "https://example.com",
        "https://example.com/about",
        "https://example.com"
    ]

    added_count = frontier.add_urls(urls)

    assert added_count == 2
    assert len(frontier.queue) == 2


def test_discovered_urls_are_not_added_again(frontier):
    url = "https://example.com"

    frontier.add_urls([url])
    frontier.get_next_url()

    added_count = frontier.add_urls([url])

    assert added_count == 0
    assert frontier.is_empty()


def test_get_next_url_from_empty_frontier(frontier):
    assert frontier.get_next_url() is None


def test_add_urls_after_queue_becomes_empty(frontier):
    frontier.add_urls(["https://example.com"])
    frontier.get_next_url()

    new_url = "https://example.com/about"

    added_count = frontier.add_urls([new_url])

    assert added_count == 1
    assert frontier.get_next_url() == new_url
    assert frontier.is_empty()


def test_add_urls_returns_only_new_urls(frontier):
    frontier.add_urls([
        "https://example.com/a",
        "https://example.com/b"
    ])

    added_count = frontier.add_urls([
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/a",
        "https://example.com/d"
    ])

    assert added_count == 2
