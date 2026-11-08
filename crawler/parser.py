
from bs4 import BeautifulSoup


class Parser:

    def parse(self, fetch_result):
        """
        Extract raw links from a successfully fetched HTML page.
        """

        if not fetch_result.success:
            raise ValueError("Cannot parse an unsuccessful fetch result.")

        if fetch_result.html is None:
            raise ValueError("Fetch result does not contain HTML.")

        soup = BeautifulSoup(fetch_result.html, "html.parser")

        links = []

        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()

            # Ignore empty links and page-internal fragments.
            if not href or href.startswith("#"):
                continue

            links.append(href)

        return links
