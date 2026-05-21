import csv
import os
from typing import Any


FIELDNAMES = [
    "job_link",
    "next_job_link",
    "title",
    "job_type",
    "budget",
    "experience_level",
    "duration",
    "hours_per_week",
    "posted_at",
    "category",
    "skills",
    "proposals",
    "client_country",
    "client_rating",
    "client_total_spent",
    "client_hires",
    "client_member_since",
    "description",
]


class CsvWriter:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._file = open(path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(
            self._file, fieldnames=FIELDNAMES, extrasaction="ignore"
        )
        self._writer.writeheader()
        self._file.flush()

    def write(self, job_info: dict[str, Any], next_job_link: str | None):
        row = dict(job_info)
        row["job_link"] = job_info.get("url", "")
        row["next_job_link"] = next_job_link or ""
        self._writer.writerow(row)
        self._file.flush()

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
