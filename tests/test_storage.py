
import json
import pytest

from crawler.storage import Storage
from crawler.fetcher import FetchResult


@pytest.fixture
def storage(tmp_path):
    return Storage(
        pages_dir=tmp_path / "pages",
        metadata_dir=tmp_path / "metadata"
    )


@pytest.fixture
def fetch_result():
    return FetchResult(
        url="https://example.com",
        final_url="https://example.com/",
        html="<html><body>Hello World</body></html>",
        status_code=200,
        content_type="text/html; charset=UTF-8",
        success=True,
        error=None
    )


def test_directories_are_created(tmp_path):
    pages_dir = tmp_path / "pages"
    metadata_dir = tmp_path / "metadata"

    Storage(pages_dir, metadata_dir)

    assert pages_dir.exists()
    assert metadata_dir.exists()


def test_save_page(storage, fetch_result):
    result = storage.save_page(fetch_result)

    assert result.page_id == "page_0001"
    assert result.html_path.exists()
    assert result.metadata_path.exists()


def test_saved_html_content(storage, fetch_result):
    result = storage.save_page(fetch_result)

    content = result.html_path.read_text(encoding="utf-8")

    assert content == fetch_result.html


def test_saved_metadata(storage, fetch_result):
    result = storage.save_page(fetch_result)

    with result.metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    assert metadata["url"] == fetch_result.url
    assert metadata["final_url"] == fetch_result.final_url
    assert metadata["status_code"] == 200
    assert metadata["content_type"] == fetch_result.content_type
    assert metadata["file_name"] == "page_0001.html"
    assert metadata["response_size"] == len(
        fetch_result.html.encode("utf-8")
    )
    assert "fetched_at" in metadata


def test_get_page(storage, fetch_result):
    storage.save_page(fetch_result)

    content = storage.get_page("page_0001")

    assert content == fetch_result.html


def test_get_metadata(storage, fetch_result):
    storage.save_page(fetch_result)

    metadata = storage.get_metadata("page_0001")

    assert metadata["url"] == fetch_result.url
    assert metadata["status_code"] == 200


def test_sequential_page_ids(storage, fetch_result):
    first = storage.save_page(fetch_result)
    second = storage.save_page(fetch_result)

    assert first.page_id == "page_0001"
    assert second.page_id == "page_0002"


def test_continue_numbering_after_restart(tmp_path, fetch_result):
    pages_dir = tmp_path / "pages"
    metadata_dir = tmp_path / "metadata"

    first_storage = Storage(pages_dir, metadata_dir)
    first_storage.save_page(fetch_result)

    # Create a new Storage instance using the same directories.
    second_storage = Storage(pages_dir, metadata_dir)
    result = second_storage.save_page(fetch_result)

    assert result.page_id == "page_0002"


def test_failed_fetch_result_is_not_saved(storage, fetch_result):
    fetch_result.success = False

    with pytest.raises(ValueError):
        storage.save_page(fetch_result)

    assert list(storage.pages_dir.iterdir()) == []
    assert list(storage.metadata_dir.iterdir()) == []


def test_empty_html_is_not_saved(storage, fetch_result):
    fetch_result.html = ""

    with pytest.raises(ValueError):
        storage.save_page(fetch_result)

    assert list(storage.pages_dir.iterdir()) == []
    assert list(storage.metadata_dir.iterdir()) == []


def test_invalid_page_id(storage):
    with pytest.raises(ValueError):
        storage.get_page("../some_file")

    with pytest.raises(ValueError):
        storage.get_metadata("../some_file")
