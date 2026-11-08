import json
import logging
import time
from pathlib import Path
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


class Crawler:

    def __init__(
        self,
        seed_url,
        max_pages,
        request_delay,
        fetcher,
        frontier,
        parser,
        url_checker,
        storage,
        stats_path=None,
    ):
        self.seed_url = seed_url
        self.max_pages = max_pages
        self.request_delay = request_delay

        self.fetcher = fetcher
        self.frontier = frontier
        self.parser = parser
        self.url_checker = url_checker
        self.storage = storage
        self.stats_path = Path(stats_path) if stats_path else None

        self.allowed_domain = self._extract_domain(seed_url)
        self.saved_final_urls = set()

        self.stats = {
            "seed_url": seed_url,
            "allowed_domain": self.allowed_domain,
            "total_requests": 0,
            "saved_pages": 0,
            "failed_requests": 0,
            "failures_by_reason": {},
            "skipped_out_of_scope": 0,
            "skipped_duplicate_pages": 0,
            "storage_errors": 0,
            "unexpected_errors": 0,
            "links_extracted": 0,
            "links_rejected": 0,
            "links_new": 0,
            "links_duplicate": 0,
            "queue_remaining": 0,
            "interrupted": False,
            "elapsed_seconds": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run(self):
        start_time = time.monotonic()

        seed = self.url_checker.normalize(self.seed_url, self.seed_url)

        if seed is None or not self.url_checker.is_valid(
            seed, self.allowed_domain
        ):
            raise ValueError(f"Invalid seed URL: {self.seed_url}")

        self.frontier.add_urls([seed])

        logger.info(
            "Crawl started | seed=%s | domain=%s | max_pages=%d",
            seed, self.allowed_domain, self.max_pages
        )

        try:
            while (
                self.stats["saved_pages"] < self.max_pages
                and not self.frontier.is_empty()
            ):
                url = self.frontier.get_next_url()

                try:
                    self._process_url(url)
                except KeyboardInterrupt:
                    raise
                except Exception:
                    self.stats["unexpected_errors"] += 1
                    logger.exception("Unexpected error while processing %s", url)

                # Delay after every request (even failed ones),
                # but not after the final page.
                if (
                    self.stats["saved_pages"] < self.max_pages
                    and not self.frontier.is_empty()
                ):
                    time.sleep(self.request_delay)

        except KeyboardInterrupt:
            self.stats["interrupted"] = True
            logger.warning("Crawl interrupted by user.")

        finally:
            self.stats["elapsed_seconds"] = round(
                time.monotonic() - start_time, 2
            )
            self.stats["queue_remaining"] = len(self.frontier.queue)
            self.fetcher.close()
            self._save_stats()
            self._print_stats()

        return self.stats

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _process_url(self, url):
        self.stats["total_requests"] += 1

        result = self.fetcher.fetch(url)

        # 1) Failed fetch
        if not result.success:
            self._record_failure(result)
            return

        # 2) Redirect to another domain / invalid final URL
        final_url = self.url_checker.normalize(result.final_url, url)

        if final_url is None or not self.url_checker.is_valid(
            final_url, self.allowed_domain
        ):
            self.stats["skipped_out_of_scope"] += 1
            logger.info("Skipped (redirected out of scope): %s -> %s",
                        url, result.final_url)
            return

        # 3) Different URLs redirecting to the same page
        if final_url in self.saved_final_urls:
            self.stats["skipped_duplicate_pages"] += 1
            logger.info("Skipped (duplicate final URL): %s", final_url)
            return

        # 4) Save page
        try:
            saved = self.storage.save_page(result)
        except (ValueError, OSError) as exc:
            self.stats["storage_errors"] += 1
            logger.error("Storage error for %s: %s", url, exc)
            return

        self.saved_final_urls.add(final_url)
        self.stats["saved_pages"] += 1

        # 5) Extract and filter links (base = final_url, not original url)
        raw_links = self.parser.parse(result)
        valid_links = self.url_checker.filter_urls(
            raw_links, final_url, self.allowed_domain
        )

        added = self.frontier.add_urls(valid_links)

        self.stats["links_extracted"] += len(raw_links)
        self.stats["links_rejected"] += len(raw_links) - len(valid_links)
        self.stats["links_new"] += added
        self.stats["links_duplicate"] += len(valid_links) - added

        logger.info(
            "[%d/%d] saved %s as %s | links=%d new=%d queue=%d",
            self.stats["saved_pages"], self.max_pages, final_url,
            saved.page_id, len(raw_links), added, len(self.frontier.queue)
        )

    def _record_failure(self, result):
        self.stats["failed_requests"] += 1

        if result.error == "Unsupported Content-Type":
            reason = "Unsupported Content-Type"
        elif result.status_code:
            reason = f"HTTP {result.status_code}"
        else:
            reason = "Network error"

        reasons = self.stats["failures_by_reason"]
        reasons[reason] = reasons.get(reason, 0) + 1

        logger.warning("Fetch failed (%s): %s", reason, result.url)

    @staticmethod
    def _extract_domain(url):
        hostname = urlsplit(url).hostname

        if not hostname:
            raise ValueError(f"Cannot extract domain from: {url}")

        hostname = hostname.lower()

        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname

    def _save_stats(self):
        if self.stats_path is None:
            return

        try:
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            with self.stats_path.open("w", encoding="utf-8") as file:
                json.dump(self.stats, file, ensure_ascii=False, indent=4)
        except OSError as exc:
            logger.error("Could not save stats: %s", exc)

    def _print_stats(self):
        logger.info("========== Crawl Summary ==========")
        for key, value in self.stats.items():
            logger.info("%s: %s", key, value)