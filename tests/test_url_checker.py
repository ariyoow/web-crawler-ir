
import pytest

from crawler.url_checker import URLChecker


@pytest.fixture
def checker():
    return URLChecker()


# -------------------------
# Test normalize()
# -------------------------

@pytest.mark.parametrize(
    "url, base_url, expected",
    [
        # Relative URL
        (
            "/products/1",
            "https://example.com",
            "https://example.com/products/1"
        ),

        # Absolute URL
        (
            "https://example.com/products/1",
            "https://example.com",
            "https://example.com/products/1"
        ),

        # Remove fragment
        (
            "https://example.com/products/1#reviews",
            "https://example.com",
            "https://example.com/products/1"
        ),

        # Normalize hostname
        (
            "https://EXAMPLE.COM/Products/1",
            "https://example.com",
            "https://example.com/Products/1"
        ),

        # Remove default HTTPS port
        (
            "https://example.com:443/products/1",
            "https://example.com",
            "https://example.com/products/1"
        ),

        # Remove default HTTP port
        (
            "http://example.com:80/products/1",
            "https://example.com",
            "http://example.com/products/1"
        ),

        # Keep non-default port
        (
            "https://example.com:8080/products/1",
            "https://example.com",
            "https://example.com:8080/products/1"
        ),

        # Preserve query parameters
        (
            "https://example.com/products?page=2#top",
            "https://example.com",
            "https://example.com/products?page=2"
        ),
    ]
)
def test_normalize(checker, url, base_url, expected):
    assert checker.normalize(url, base_url) == expected


def test_normalize_invalid_url(checker):
    assert checker.normalize(None, "https://example.com") is None


# -------------------------
# Test is_valid()
# -------------------------

@pytest.mark.parametrize(
    "url, allowed_domain, expected",
    [
        # Valid HTTP
        ("http://example.com/page", "example.com", True),

        # Valid HTTPS
        ("https://example.com/page", "example.com", True),

        # Valid subdomain
        ("https://shop.example.com/page", "example.com", True),

        # Invalid protocol
        ("ftp://example.com/file", "example.com", False),

        # External domain
        ("https://google.com", "example.com", False),

        # Fake subdomain
        ("https://example.com.evil.com", "example.com", False),

        # Missing hostname
        ("https:///page", "example.com", False),

        # Invalid port
        ("https://example.com:invalid/page", "example.com", False),

        # Username/password
        ("https://user:pass@example.com/page", "example.com", False),

        # JavaScript URL
        ("javascript:void(0)", "example.com", False),

        # Mail URL
        ("mailto:info@example.com", "example.com", False),
    ]
)
def test_is_valid(checker, url, allowed_domain, expected):
    assert checker.is_valid(url, allowed_domain) is expected


# -------------------------
# Test filter_urls()
# -------------------------

def test_filter_urls(checker):
    urls = [
        "/products/1",
        "https://EXAMPLE.com/products/2",
        "https://example.com:443/products/3",
        "https://example.com/products/1#reviews",
        "https://shop.example.com/products/4",
        "https://google.com/page",
        "javascript:void(0)",
        "mailto:info@example.com",
        "https://example.com/products/2",
    ]

    result = checker.filter_urls(
        urls,
        "https://example.com",
        "example.com"
    )

    expected = [
        "https://example.com/products/1",
        "https://example.com/products/2",
        "https://example.com/products/3",
        "https://shop.example.com/products/4",
    ]

    assert result == expected


def test_filter_urls_empty_list(checker):
    result = checker.filter_urls(
        [],
        "https://example.com",
        "example.com"
    )

    assert result == []


def test_filter_urls_all_invalid(checker):
    urls = [
        "https://google.com",
        "javascript:void(0)",
        "mailto:info@example.com",
    ]

    result = checker.filter_urls(
        urls,
        "https://example.com",
        "example.com"
    )

    assert result == []


def test_filter_urls_preserves_order(checker):
    urls = [
        "/products/3",
        "/products/1",
        "/products/2",
    ]

    result = checker.filter_urls(
        urls,
        "https://example.com",
        "example.com"
    )

    assert result == [
        "https://example.com/products/3",
        "https://example.com/products/1",
        "https://example.com/products/2",
    ]
