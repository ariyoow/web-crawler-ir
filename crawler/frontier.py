
from collections import deque


class Frontier:
    def __init__(self):
        self.queue = deque()
        self.discovered_urls = set()

    def add_urls(self, urls):
        added_count = 0

        for url in urls:
            if url not in self.discovered_urls:
                self.queue.append(url)
                self.discovered_urls.add(url)
                added_count += 1

        return added_count

    def get_next_url(self):
        if self.is_empty():
            return None

        return self.queue.popleft()

    def is_empty(self):
        return len(self.queue) == 0
