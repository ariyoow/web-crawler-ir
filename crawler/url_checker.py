from urllib.parse import urljoin, urlsplit, urlunsplit


class URLChecker:

    def normalize(self, url, base_url):
        """
        Convert relative URLs to absolute URLs and normalize them.
        """
        if not isinstance(url, str) or not url.strip():
            return None

        try:
            # Convert relative URL to absolute URL
            url = urljoin(base_url, url)

            parsed = urlsplit(url)

            if parsed.username is not None or parsed.password is not None:
                return None

            # Normalize scheme and hostname
            scheme = parsed.scheme.lower()
            hostname = parsed.hostname

            if not hostname:
                return None

            hostname = hostname.lower()

            # Validate port format
            port = parsed.port

            # Remove default ports
            if port == 80 and scheme == "http":
                port = None
            elif port == 443 and scheme == "https":
                port = None

            # Rebuild network location
            if ":" in hostname:  # IPv6 address
                netloc = f"[{hostname}]"
            else:
                netloc = hostname

            if port is not None:
                netloc = f"{netloc}:{port}"

            # Remove fragment
            normalized_url = urlunsplit((
                scheme,
                netloc,
                parsed.path,
                parsed.query,
                ""
            ))

            return normalized_url

        except (ValueError, TypeError, AttributeError):
            return None

    def is_valid(self, url, allowed_domain):
        """
        Check whether a URL uses HTTP/HTTPS
        and belongs to the allowed domain.
        """

        try:
            parsed = urlsplit(url)

            # Check protocol
            if parsed.scheme not in ("http", "https"):
                return False

            # Check hostname
            hostname = parsed.hostname

            if not hostname:
                return False

            hostname = hostname.lower()

            # Reject URLs containing username or password
            if parsed.username is not None or parsed.password is not None:
                return False

            # Validate port
            parsed.port

            # Normalize allowed domain
            allowed_domain = allowed_domain.lower().strip()

            if "://" in allowed_domain:
                allowed_domain = urlsplit(allowed_domain).hostname

            if not allowed_domain:
                return False

            # Check domain and its subdomains
            if (
                hostname != allowed_domain
                and not hostname.endswith("." + allowed_domain)
            ):
                return False

            return True

        except (ValueError, TypeError, AttributeError):
            return False

    def filter_urls(self, urls, base_url, allowed_domain):
        """
        Normalize and filter a list of URLs.
        Returns valid and unique URLs.
        """

        valid_urls = []
        seen_urls = set()

        for url in urls:

            # Normalize URL
            normalized_url = self.normalize(url, base_url)

            if normalized_url is None:
                continue

            # Validate URL
            if not self.is_valid(normalized_url, allowed_domain):
                continue

            # Check duplicates
            if normalized_url in seen_urls:
                continue

            seen_urls.add(normalized_url)
            valid_urls.append(normalized_url)

        return valid_urls