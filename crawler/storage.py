
import json
import re

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class StorageResult:
    page_id: str
    html_path: Path
    metadata_path: Path


class Storage:
    def __init__(self, pages_dir, metadata_dir):
        self.pages_dir = Path(pages_dir)
        self.metadata_dir = Path(metadata_dir)

        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def save_page(self, fetch_result):
        if not fetch_result.success:
            raise ValueError("Cannot save an unsuccessful fetch result.")

        if not fetch_result.html:
            raise ValueError("Cannot save an empty HTML page.")

        page_id = self._get_next_page_id()

        html_path = self.pages_dir / f"{page_id}.html"
        metadata_path = self.metadata_dir / f"{page_id}.json"

        metadata = {
            "url": fetch_result.url,
            "final_url": fetch_result.final_url,
            "status_code": fetch_result.status_code,
            "content_type": fetch_result.content_type,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "file_name": html_path.name,
            "response_size": len(fetch_result.html.encode("utf-8"))
        }

        html_temp = None
        metadata_temp = None

        try:
            html_temp = self._write_temp_file(
                html_path.parent,
                fetch_result.html
            )

            metadata_temp = self._write_temp_file(
                metadata_path.parent,
                json.dumps(metadata, ensure_ascii=False, indent=4)
            )

            # Replace temporary files with final files.
            html_temp.replace(html_path)
            metadata_temp.replace(metadata_path)

        except Exception:
            # Remove temporary and partially created files.
            if html_temp and html_temp.exists():
                html_temp.unlink()

            if metadata_temp and metadata_temp.exists():
                metadata_temp.unlink()

            if html_path.exists():
                html_path.unlink()

            if metadata_path.exists():
                metadata_path.unlink()

            raise

        return StorageResult(
            page_id=page_id,
            html_path=html_path,
            metadata_path=metadata_path
        )

    def get_page(self, page_id):
        self._validate_page_id(page_id)

        html_path = self.pages_dir / f"{page_id}.html"

        return html_path.read_text(encoding="utf-8")

    def get_metadata(self, page_id):
        self._validate_page_id(page_id)

        metadata_path = self.metadata_dir / f"{page_id}.json"

        with metadata_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _get_next_page_id(self):
        pattern = re.compile(r"^page_(\d+)$")
        max_number = 0

        for directory in (self.pages_dir, self.metadata_dir):
            for file_path in directory.iterdir():
                match = pattern.match(file_path.stem)

                if match:
                    number = int(match.group(1))
                    max_number = max(max_number, number)

        return f"page_{max_number + 1:04d}"

    def _write_temp_file(self, directory, content):
        temp_path = directory / f".tmp_{datetime.now(timezone.utc).timestamp()}"

        # Avoid accidental overwriting of an existing temporary file.
        counter = 0
        while temp_path.exists():
            counter += 1
            temp_path = directory / (
                f".tmp_{datetime.now(timezone.utc).timestamp()}_{counter}"
            )

        temp_path.write_text(content, encoding="utf-8")
        return temp_path

    def _validate_page_id(self, page_id):
        if not isinstance(page_id, str) or not re.fullmatch(
            r"page_\d+", page_id
        ):
            raise ValueError("Invalid page ID.")
