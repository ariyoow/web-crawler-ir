
import time
import requests

from dataclasses import dataclass
from typing import Optional


@dataclass
class FetchResult:
    url: str
    final_url: str
    html: Optional[str]
    status_code: Optional[int]
    content_type: Optional[str]
    success: bool
    error: Optional[str] = None


class Fetcher:

    def __init__(self, timeout, max_retries, user_agent):
        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent
        })

    def fetch(self, url):

        for attempt in range(self.max_retries + 1):

            response = None

            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    stream=True
                )

                content_type = response.headers.get("Content-Type", "")
                status_code = response.status_code

                # Retry for temporary HTTP errors
                if status_code in (408, 429) or status_code >= 500:

                    if attempt < self.max_retries:
                        time.sleep(2 ** attempt)
                        continue

                    return FetchResult(
                        url=url,
                        final_url=response.url,
                        html=None,
                        status_code=status_code,
                        content_type=content_type,
                        success=False,
                        error=f"HTTP Error: {status_code}"
                    )

                # Handle permanent HTTP errors
                if not response.ok:
                    return FetchResult(
                        url=url,
                        final_url=response.url,
                        html=None,
                        status_code=status_code,
                        content_type=content_type,
                        success=False,
                        error=f"HTTP Error: {status_code}"
                    )

                # Check Content-Type before downloading the body
                content_type_lower = content_type.lower()

                if not (
                    "text/html" in content_type_lower
                    or "application/xhtml+xml" in content_type_lower
                ):
                    return FetchResult(
                        url=url,
                        final_url=response.url,
                        html=None,
                        status_code=status_code,
                        content_type=content_type,
                        success=False,
                        error="Unsupported Content-Type"
                    )

                # Read HTML body
                html = response.text

                return FetchResult(
                    url=url,
                    final_url=response.url,
                    html=html,
                    status_code=status_code,
                    content_type=content_type,
                    success=True
                )

            except (requests.Timeout, requests.ConnectionError) as exc:

                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue

                return FetchResult(
                    url=url,
                    final_url=url,
                    html=None,
                    status_code=None,
                    content_type=None,
                    success=False,
                    error=str(exc)
                )

            except requests.exceptions.RequestException as exc:
                return FetchResult(
                    url=url,
                    final_url=url,
                    html=None,
                    status_code=None,
                    content_type=None,
                    success=False,
                    error=str(exc)
                )

            finally:
                if response is not None:
                    response.close()

    def close(self):
        self.session.close()
