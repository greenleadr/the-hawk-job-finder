"""Remotive.com collector for remote software engineering roles.

Queries the free Remotive API for the "software-dev" category and filters
to senior-level engineering titles.

Usage:
    python -m collectors.remotive
"""

import json
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://remotive.com/api/remote-jobs?category=software-dev"

_SENIOR_TITLE_RE = re.compile(
    r"\b("
    r"senior\s+(software\s+)?engineer|"
    r"sr\.?\s+(software\s+)?engineer|"
    r"staff\s+(software\s+)?engineer|"
    r"principal\s+(software\s+)?engineer|"
    r"lead\s+(software\s+)?engineer|"
    r"software\s+development\s+engineer|"
    r"sde\s*(ii|iii|iv)|"
    r"senior\s+full[- ]?stack|"
    r"senior\s+front[- ]?end|"
    r"senior\s+back[- ]?end|"
    r"senior\s+platform\s+engineer|"
    r"senior\s+cloud\s+engineer|"
    r"senior\s+data\s+engineer"
    r")\b",
    re.I,
)


def _fetch(url: str, retries: int = 3) -> dict[str, Any]:
    """Fetch JSON with retry on transient errors."""
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "HawkJobFinder/1.0",
    })
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except (HTTPError, URLError) as exc:
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Remotive request error ({exc}) — retrying in {wait}s …", file=sys.stderr)
                import time
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Request failed after {retries} retries: {url}")


def _is_senior(title: str) -> bool:
    return bool(_SENIOR_TITLE_RE.search(title))


def _parse_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": job.get("title", ""),
        "company": (job.get("company_name") or ""),
        "location": job.get("candidate_required_location", "Worldwide"),
        "url": job.get("url", ""),
        "description": _strip_html(job.get("description", "")),
        "source": "remotive",
        "date_posted": job.get("publication_date", ""),
    }


def _strip_html(text: str) -> str:
    """Remove HTML tags for plain-text matching in the scorer."""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


def search_jobs() -> list[dict[str, Any]]:
    """Query Remotive for remote software engineering roles."""
    print("Fetching Remotive software-dev jobs …", file=sys.stderr)

    try:
        data = _fetch(API_URL)
    except (HTTPError, URLError, RuntimeError) as exc:
        print(f"  Remotive API error: {exc}", file=sys.stderr)
        return []

    all_jobs = data.get("jobs", [])
    print(f"  Remotive returned {len(all_jobs)} software-dev jobs", file=sys.stderr)

    results: list[dict[str, Any]] = []
    for raw in all_jobs:
        title = raw.get("title", "")
        if _is_senior(title):
            results.append(_parse_job(raw))

    print(f"  After senior-title filter: {len(results)} jobs", file=sys.stderr)
    return results


if __name__ == "__main__":
    jobs = search_jobs()
    print(json.dumps(jobs, indent=2))
