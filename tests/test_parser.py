
import pytest

from crawler.parser import Parser
from crawler.fetcher import FetchResult


@pytest.fixture
def parser():
    return Parser()


@pytest.fixture
def fetch_result():
    html = """
    <html>
        <body>
            <a href="https://example.com/about">About</a>
            <a href="/products">Products</a>
            <a href="contact">Contact</a>
            <a href="mailto:info@example.com">Email</a>
            <a href="javascript:void(0)">JavaScript</a>
        </body>
    </html>
    """

    return FetchResult(
        url="https://example.com",
        final_url="https://example.com/",
        html=html,
        status_code=200,
        content_type="text/html",
        success=True,
        error=None
    )


def test_extract_links(parser, fetch_result):
    links = parser.parse(fetch_result)

    assert links == [
        "https://example.com/about",
        "/products",
        "contact",
        "mailto:info@example.com",
        "javascript:void(0)"
    ]


def test_extract_only_anchor_tags(parser):
    html = """
    <html>
        <body>
            <a href="/page1">Page 1</a>
            <img src="/image.jpg">
            <link href="/style.css" rel="stylesheet">
            <script src="/script.js"></script>
        </body>
    </html>
    """

    fetch_result = FetchResult(
        url="https://example.com",
        final_url="https://example.com/",
        html=html,
        status_code=200,
        content_type="text/html",
        success=True
    )

    links = parser.parse(fetch_result)

    assert links == ["/page1"]


def test_ignore_tags_without_href(parser):
    html = """
    <html>
        <body>
            <a>Link without href</a>
            <a href="/valid">Valid link</a>
        </body>
    </html>
    """

    fetch_result = FetchResult(
        url="https://example.com",
        final_url="https://example.com/",
        html=html,
        status_code=200,
        content_type="text/html",
        success=True
    )

    links = parser.parse(fetch_result)

    assert links == ["/valid"]


def test_ignore_empty_links(parser):
    html = """
    <html>
        <body>
            <a href="">Empty</a>
            <a href="   ">Whitespace</a>
            <a href="/valid">Valid</a>
        </body>
    </html>
    """

    fetch_result = FetchResult(
        url="https://example.com",
        final_url="https://example.com/",
        html=html,
        status_code=200,
        content_type="text/html",
        success=True
    )

    links = parser.parse(fetch_result)

    assert links == ["/valid"]


def test_ignore_fragment_only_links(parser):
    html = """
    <html>
        <body>
            <a href="#section1">Section 1</a>
            <a href="  #section2">Section 2</a>
            <a href="/about#details">About</a>
        </body>
    </html>
    """

    fetch_result = FetchResult(
        url="https://example.com",
        final_url="https://example.com/",
        html=html,
        status_code=200,
        content_type="text/html",
        success=True
    )

    links = parser.parse(fetch_result)

    assert links == ["/about#details"]


def test_preserve_relative_urls(parser):
    html = """
    <html>
        <body>
            <a href="/about">About</a>
            <a href="../contact">Contact</a>
            <a href="products/item">Product</a>
        </body>
    </html>
    """

    fetch_result = FetchResult(
        url="https://example.com",
        final_url="https://example.com/category/page",
        html=html,
        status_code=200,
        content_type="text/html",
        success=True
    )

    links = parser.parse(fetch_result)

    assert links == [
        "/about",
        "../contact",
        "products/item"
    ]


def test_keep_duplicate_links(parser):
    html = """
    <html>
        <body>
            <a href="/about">About 1</a>
            <a href="/about">About 2</a>
        </body>
    </html>
    """

    fetch_result = FetchResult(
        url="https://example.com",
        final_url="https://example.com/",
        html=html,
        status_code=200,
        content_type="text/html",
        success=True
    )

    links = parser.parse(fetch_result)

    assert links == ["/about", "/about"]


def test_unsuccessful_fetch_result(parser, fetch_result):
    fetch_result.success = False

    with pytest.raises(ValueError):
        parser.parse(fetch_result)


def test_missing_html(parser, fetch_result):
    fetch_result.html = None

    with pytest.raises(ValueError):
        parser.parse(fetch_result)


def test_empty_html(parser, fetch_result):
    fetch_result.html = ""

    links = parser.parse(fetch_result)

    assert links == []
