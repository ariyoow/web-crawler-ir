import logging
from datetime import datetime
from pathlib import Path

from . import config
from .crawler import Crawler
from .fetcher import Fetcher
from .frontier import Frontier
from .parser import Parser
from .storage import Storage
from .url_checker import URLChecker


def setup_logging():
    logs_dir = Path(config.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / f"crawl_{datetime.now():%Y%m%d_%H%M%S}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main():
    setup_logging()

    crawler = Crawler(
        seed_url=config.SEED_URL,
        max_pages=config.MAX_PAGES,
        request_delay=config.REQUEST_DELAY,
        fetcher=Fetcher(
            config.REQUEST_TIMEOUT,
            config.MAX_RETRIES,
            config.USER_AGENT,
        ),
        frontier=Frontier(),
        parser=Parser(),
        url_checker=URLChecker(),
        storage=Storage(config.PAGES_DIR, config.METADATA_DIR),
        stats_path=config.STATS_PATH,
    )

    crawler.run()


if __name__ == "__main__":
    main()