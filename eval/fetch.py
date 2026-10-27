"""Cached crawling for evaluation runs.

Cache: eval/cache/<sha1(url)>.json (a CrawlResult). Manual override for pages
that cannot be crawled: eval/cache/manual/<sha1(url)>.txt, optionally starting
with a line `date: YYYY-MM-DD`.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pipeline.crawl import CrawlResult, crawl

CACHE = Path(__file__).resolve().parent / "cache"
MANUAL = CACHE / "manual"


@dataclass
class Fetched:
    url: str
    text: str | None
    published_at: date | None
    error: str = ""
    warnings: tuple[str, ...] = ()


def key(url: str) -> str:
    return hashlib.sha1(url.strip().encode()).hexdigest()


def _manual(path: Path, url: str) -> Fetched:
    raw = path.read_text(encoding="utf-8")
    published = None
    if m := re.match(r"date:\s*(\d{4}-\d{2}-\d{2})\s*\n", raw):
        published, raw = date.fromisoformat(m.group(1)), raw[m.end():]
    return Fetched(url, raw.strip(), published)


def fetch(url: str, title: str = "", refresh: bool = False) -> Fetched:
    CACHE.mkdir(parents=True, exist_ok=True)
    MANUAL.mkdir(parents=True, exist_ok=True)
    if (manual := MANUAL / f"{key(url)}.txt").exists():
        return _manual(manual, url)
    cached = CACHE / f"{key(url)}.json"
    if cached.exists() and not refresh:
        res = CrawlResult.from_json(cached.read_text(encoding="utf-8"))
    else:
        res = crawl(url, title)
        if res.ok:  # failures are retried next run
            cached.write_text(res.to_json(), encoding="utf-8")
    if not res.ok:
        hint = f" → đặt nội dung vào {manual.relative_to(CACHE.parent.parent)}"
        return Fetched(url, None, None, f"{res.status}: {res.error}{hint}")
    return Fetched(url, res.text, res.published_at, warnings=tuple(res.warnings))
