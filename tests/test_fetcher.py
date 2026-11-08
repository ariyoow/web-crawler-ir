
import pytest
import requests

from crawler.fetcher import Fetcher


# ==================================================
# Fixtures and Helpers
# ==================================================

@pytest.fixture
def fetcher():
    instance = Fetcher(
        timeout=10,
        max_retries=3,
        user_agent="TestCrawler/1.0"
    )

    yield instance

    instance.close()


def create_response(
    status_code=200,
    content_type="text/html; charset=utf-8",
    html="<html><body>Hello</body></html>",
    url="https://example.com"
):
    response = requests.Response()

    response.status_code = status_code
    response.headers["Content-Type"] = content_type
    response._content = html.encode("utf-8")
    response._content_consumed = True
    response.url = url
    response.encoding = "utf-8"

    return response


# ==================================================
# Basic Fetch Tests
# ==================================================

def test_successful_fetch(fetcher, monkeypatch):
    expected_html = "<html><body>Hello</body></html>"

    def mock_get(url, timeout, stream):
        return create_response()

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com")

    assert result.success is True
    assert result.html == expected_html
    assert result.status_code == 200
    assert result.url == "https://example.com"
    assert result.final_url == "https://example.com"
    assert result.error is None


def test_request_uses_configured_timeout(fetcher, monkeypatch):
    received = {}

    def mock_get(url, timeout, stream):
        received["url"] = url
        received["timeout"] = timeout
        received["stream"] = stream

        return create_response()

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    fetcher.fetch("https://example.com")

    assert received["url"] == "https://example.com"
    assert received["timeout"] == 10
    assert received["stream"] is True


def test_user_agent_is_configured(fetcher):
    assert fetcher.session.headers["User-Agent"] == "TestCrawler/1.0"


# ==================================================
# Content-Type Tests
# ==================================================

def test_non_html_content_is_rejected(fetcher, monkeypatch):
    def mock_get(url, timeout, stream):
        return create_response(
            content_type="application/pdf"
        )

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com/file.pdf")

    assert result.success is False
    assert result.html is None
    assert result.error == "Unsupported Content-Type"


def test_xhtml_content_is_accepted(fetcher, monkeypatch):
    def mock_get(url, timeout, stream):
        return create_response(
            content_type="application/xhtml+xml"
        )

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com")

    assert result.success is True
    assert result.html is not None


def test_content_type_is_case_insensitive(fetcher, monkeypatch):
    def mock_get(url, timeout, stream):
        return create_response(
            content_type="TEXT/HTML; charset=utf-8"
        )

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com")

    assert result.success is True


def test_empty_content_type_is_rejected(fetcher, monkeypatch):
    def mock_get(url, timeout, stream):
        return create_response(content_type="")

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com")

    assert result.success is False
    assert result.error == "Unsupported Content-Type"


# ==================================================
# HTTP Status Code Tests
# ==================================================

def test_404_does_not_retry(fetcher, monkeypatch):
    calls = []

    def mock_get(url, timeout, stream):
        calls.append(url)
        return create_response(status_code=404)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com/not-found")

    assert result.success is False
    assert result.status_code == 404
    assert result.error == "HTTP Error: 404"
    assert len(calls) == 1


def test_403_does_not_retry(fetcher, monkeypatch):
    calls = []

    def mock_get(url, timeout, stream):
        calls.append(url)
        return create_response(status_code=403)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com/forbidden")

    assert result.success is False
    assert result.status_code == 403
    assert len(calls) == 1


def test_server_error_retries_then_succeeds(fetcher, monkeypatch):
    calls = []
    delays = []

    responses = [
        create_response(status_code=503),
        create_response()
    ]

    def mock_get(url, timeout, stream):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    monkeypatch.setattr(
        "crawler.fetcher.time.sleep",
        lambda seconds: delays.append(seconds)
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is True
    assert result.status_code == 200
    assert len(calls) == 2
    assert delays == [1]


def test_retries_exhausted(fetcher, monkeypatch):
    calls = []
    delays = []

    def mock_get(url, timeout, stream):
        calls.append(url)
        return create_response(status_code=500)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    monkeypatch.setattr(
        "crawler.fetcher.time.sleep",
        lambda seconds: delays.append(seconds)
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is False
    assert result.status_code == 500
    assert result.error == "HTTP Error: 500"
    assert len(calls) == 4
    assert delays == [1, 2, 4]


def test_rate_limit_retries(fetcher, monkeypatch):
    calls = []

    responses = [
        create_response(status_code=429),
        create_response()
    ]

    def mock_get(url, timeout, stream):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    monkeypatch.setattr(
        "crawler.fetcher.time.sleep",
        lambda seconds: None
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is True
    assert len(calls) == 2


def test_request_timeout_status_retries(fetcher, monkeypatch):
    calls = []

    responses = [
        create_response(status_code=408),
        create_response()
    ]

    def mock_get(url, timeout, stream):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    monkeypatch.setattr(
        "crawler.fetcher.time.sleep",
        lambda seconds: None
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is True
    assert len(calls) == 2


# ==================================================
# Network Exception Tests
# ==================================================

def test_timeout_retries_then_succeeds(fetcher, monkeypatch):
    calls = []
    delays = []

    def mock_get(url, timeout, stream):
        calls.append(url)

        if len(calls) < 3:
            raise requests.Timeout("Connection timed out")

        return create_response()

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    monkeypatch.setattr(
        "crawler.fetcher.time.sleep",
        lambda seconds: delays.append(seconds)
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is True
    assert len(calls) == 3
    assert delays == [1, 2]


def test_connection_error_retries(fetcher, monkeypatch):
    calls = []
    delays = []

    def mock_get(url, timeout, stream):
        calls.append(url)
        raise requests.ConnectionError("Connection failed")

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    monkeypatch.setattr(
        "crawler.fetcher.time.sleep",
        lambda seconds: delays.append(seconds)
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is False
    assert result.status_code is None
    assert len(calls) == 4
    assert delays == [1, 2, 4]


def test_invalid_url_does_not_retry(fetcher, monkeypatch):
    calls = []

    def mock_get(url, timeout, stream):
        calls.append(url)
        raise requests.exceptions.InvalidURL("Invalid URL")

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("invalid-url")

    assert result.success is False
    assert result.status_code is None
    assert len(calls) == 1


# ==================================================
# Redirect Tests
# ==================================================

def test_final_url_after_redirect(fetcher, monkeypatch):
    final_url = "https://example.com/final"

    def mock_get(url, timeout, stream):
        return create_response(url=final_url)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com/redirect")

    assert result.success is True
    assert result.url == "https://example.com/redirect"
    assert result.final_url == final_url


# ==================================================
# Response Management Tests
# ==================================================

def test_response_is_closed_after_success(fetcher, monkeypatch):
    response = create_response()
    close_called = []

    original_close = response.close

    def mock_close():
        close_called.append(True)
        original_close()

    monkeypatch.setattr(response, "close", mock_close)

    monkeypatch.setattr(
        fetcher.session,
        "get",
        lambda url, timeout, stream: response
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is True
    assert close_called == [True]


def test_response_is_closed_after_http_error(fetcher, monkeypatch):
    response = create_response(status_code=404)
    close_called = []

    original_close = response.close

    def mock_close():
        close_called.append(True)
        original_close()

    monkeypatch.setattr(response, "close", mock_close)

    monkeypatch.setattr(
        fetcher.session,
        "get",
        lambda url, timeout, stream: response
    )

    result = fetcher.fetch("https://example.com")

    assert result.success is False
    assert close_called == [True]


def test_response_is_closed_after_unsupported_content(fetcher, monkeypatch):
    response = create_response(
        content_type="application/pdf"
    )
    close_called = []

    original_close = response.close

    def mock_close():
        close_called.append(True)
        original_close()

    monkeypatch.setattr(response, "close", mock_close)

    monkeypatch.setattr(
        fetcher.session,
        "get",
        lambda url, timeout, stream: response
    )

    result = fetcher.fetch("https://example.com/file.pdf")

    assert result.success is False
    assert close_called == [True]


# ==================================================
# Configuration Tests
# ==================================================

def test_zero_retries(fetcher, monkeypatch):
    fetcher.max_retries = 0

    calls = []

    def mock_get(url, timeout, stream):
        calls.append(url)
        return create_response(status_code=500)

    monkeypatch.setattr(fetcher.session, "get", mock_get)

    result = fetcher.fetch("https://example.com")

    assert result.success is False
    assert len(calls) == 1
