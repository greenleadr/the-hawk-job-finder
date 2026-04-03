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

API_URLS = [
    "https://remotive.com/api/remote-jobs?category=software-dev",
    "https://remotive.com/api/remote-jobs?category=devops",
    "https://remotive.com/api/remote-jobs?category=data",
]

# Match software engineering roles at any level (mid through senior)
# Excludes intern/junior/co-op
_TITLE_RE = re.compile(
    r"\b("
    r"software\s+(engineer|developer)|"
    r"full[- ]?stack\s+(engineer|developer)|"
    r"front[- ]?end\s+(engineer|developer)|"
    r"back[- ]?end\s+(engineer|developer)|"
    r"web\s+developer|"
    r"java\s+developer|"
    r"react\s+developer|"
    r"application\s+developer|"
    r"sde\b|swe\b"
    r")\b",
    re.I,
)
_EXCLUDE_RE = re.compile(
    r"\b(intern\b|internship|co[- ]?op|junior|entry[- ]level|new\s+grad)\b",
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


def _is_target_role(title: str) -> bool:
    return bool(_TITLE_RE.search(title) and not _EXCLUDE_RE.search(title))


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
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for api_url in API_URLS:
        category = api_url.split("category=")[-1]
        print(f"  Remotive [{category}] …", file=sys.stderr, end=" ")

        try:
            data = _fetch(api_url)
        except (HTTPError, URLError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            continue

        all_jobs = data.get("jobs", [])
        count = 0
        for raw in all_jobs:
            title = raw.get("title", "")
            if _is_target_role(title):
                parsed = _parse_job(raw)
                if parsed["url"] and parsed["url"] not in seen_urls:
                    seen_urls.add(parsed["url"])
                    results.append(parsed)
                    count += 1
        print(f"{len(all_jobs)} jobs, {count} senior matches", file=sys.stderr)

    print(f"  After title filter: {len(results)} jobs", file=sys.stderr)
    return results


if __name__ == "__main__":
    jobs = search_jobs()
    print(json.dumps(jobs, indent=2))
