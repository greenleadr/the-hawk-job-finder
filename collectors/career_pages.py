"""Career-pages collector.

Queries Greenhouse, Lever, and Ashby public APIs for all companies in
companies.json.  Filters to product-leadership titles and returns
normalized job dicts.

Usage:
    python -m collectors.career_pages
"""

import json
import re
import sys
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_COMPANIES_PATH = Path(__file__).resolve().parent.parent / "companies.json"

# Titles we care about — must match software engineering roles at senior+ level
_ENGINEERING_RE = re.compile(
    r"\b(software|platform|cloud|data|full[- ]?stack|front[- ]?end|back[- ]?end|systems?)\b",
    re.I,
)
_ROLE_RE = re.compile(
    r"\b(engineer|developer|sde|swe)\b",
    re.I,
)
_SENIORITY_RE = re.compile(
    r"\b("
    r"senior|sr\.?|staff|principal|lead|"
    r"ii\b|iii\b|iv\b|"
    r"sde\s*(ii|iii)|"
    r"software\s+development\s+engineer"
    r")\b",
    re.I,
)

REQUEST_DELAY = 0.5  # seconds between API calls


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", unescape(text or ""))
    return re.sub(r"\s+", " ", clean).strip()


def _is_target_role(title: str) -> bool:
    return bool(
        _ENGINEERING_RE.search(title)
        and _ROLE_RE.search(title)
        and _SENIORITY_RE.search(title)
    )


def _fetch_json(url: str, retries: int = 2, method: str = "GET",
                body: bytes | None = None) -> Any:
    headers = {"Accept": "application/json", "User-Agent": "HawkJobFinder/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, headers=headers, method=method, data=body)
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as exc:
            if exc.code == 429:
                wait = 2 ** (attempt + 1)
                print(f"    Rate limited — waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if exc.code in (404, 403):
                return None  # board doesn't exist or is private
            if attempt < retries:
                time.sleep(1)
                continue
            return None
        except (URLError, OSError):
            if attempt < retries:
                time.sleep(1)
                continue
            return None
    return None


# ---------------------------------------------------------------------------
# Greenhouse  —  GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
# ---------------------------------------------------------------------------

def _board_token(url: str) -> str | None:
    """Extract the board token from a Greenhouse URL."""
    # job-boards.greenhouse.io/smartsheet
    m = re.search(r"greenhouse\.io/(?:embed/job_board\?for=)?(\w[\w-]*)", url, re.I)
    if m:
        return m.group(1)
    # boards.greenhouse.io/embed/job_board?for=stripe
    m = re.search(r"[?&]for=(\w[\w-]*)", url, re.I)
    if m:
        return m.group(1)
    return None


def _fetch_greenhouse(company: dict[str, Any]) -> list[dict[str, Any]]:
    token = _board_token(company["careers_url"])
    if not token:
        return []

    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    data = _fetch_json(url)
    if not data or "jobs" not in data:
        return []

    jobs: list[dict[str, Any]] = []
    for j in data["jobs"]:
        title = j.get("title", "")
        if not _is_target_role(title):
            continue
        loc = (j.get("location", {}) or {}).get("name", "")
        jobs.append({
            "title": title,
            "company": company["name"],
            "location": loc,
            "url": j.get("absolute_url", ""),
            "description": _strip_html(j.get("content", "")),
            "source": "career_pages",
            "date_posted": j.get("updated_at", ""),
        })
    return jobs


# ---------------------------------------------------------------------------
# Lever  —  GET https://api.lever.co/v0/postings/{slug}?mode=json
# ---------------------------------------------------------------------------

def _lever_slug(url: str) -> str | None:
    m = re.search(r"lever\.co/(\w[\w-]*)", url, re.I)
    if m:
        return m.group(1)
    # Fallback: use company name lowered
    return None


def _fetch_lever(company: dict[str, Any]) -> list[dict[str, Any]]:
    slug = _lever_slug(company["careers_url"])
    if not slug:
        return []

    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    data = _fetch_json(url)
    if not data or not isinstance(data, list):
        return []

    jobs: list[dict[str, Any]] = []
    for j in data:
        title = j.get("text", "")
        if not _is_target_role(title):
            continue
        cats = j.get("categories", {}) or {}
        loc = cats.get("location", "")
        desc_parts = []
        if j.get("descriptionPlain"):
            desc_parts.append(j["descriptionPlain"])
        for lst in j.get("lists", []):
            if lst.get("content"):
                desc_parts.append(_strip_html(lst["content"]))
        if j.get("additionalPlain"):
            desc_parts.append(j["additionalPlain"])

        jobs.append({
            "title": title,
            "company": company["name"],
            "location": loc,
            "url": j.get("hostedUrl", ""),
            "description": " ".join(desc_parts),
            "source": "career_pages",
            "date_posted": "",
        })
        # Set date from createdAt (millisecond timestamp)
        ts = j.get("createdAt")
        if ts and isinstance(ts, (int, float)):
            from datetime import datetime, timezone
            jobs[-1]["date_posted"] = datetime.fromtimestamp(
                ts / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return jobs


# ---------------------------------------------------------------------------
# Ashby  —  GET https://api.ashbyhq.com/posting-api/job-board/{slug}
# ---------------------------------------------------------------------------

def _ashby_slug(url: str) -> str | None:
    m = re.search(r"ashbyhq\.com/(\w[\w.-]*)", url, re.I)
    if m:
        return m.group(1)
    return None


def _fetch_ashby(company: dict[str, Any]) -> list[dict[str, Any]]:
    slug = _ashby_slug(company["careers_url"])
    if not slug:
        return []

    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    data = _fetch_json(url)
    if not data or "jobs" not in data:
        return []

    jobs: list[dict[str, Any]] = []
    for j in data["jobs"]:
        title = j.get("title", "")
        if not _is_target_role(title):
            continue
        loc = j.get("location", "")
        if isinstance(loc, dict):
            loc = loc.get("name", "")
        jobs.append({
            "title": title,
            "company": company["name"],
            "location": loc,
            "url": j.get("jobUrl", ""),
            "description": _strip_html(j.get("descriptionHtml", "") or j.get("descriptionPlain", "")),
            "source": "career_pages",
            "date_posted": j.get("publishedAt", ""),
        })
    return jobs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FETCHERS = {
    "greenhouse": _fetch_greenhouse,
    "lever": _fetch_lever,
    "ashby": _fetch_ashby,
}


def search_jobs(companies_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Query career pages for all companies in companies.json."""
    path = Path(companies_path) if companies_path else _COMPANIES_PATH
    with open(path) as f:
        companies = json.load(f)

    all_jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    queried = 0
    skipped = 0

    for company in companies:
        ats = company.get("ats_type", "")
        fetcher = _FETCHERS.get(ats)
        if not fetcher:
            skipped += 1
            continue

        name = company["name"]
        print(f"  {name} ({ats}) …", file=sys.stderr, end=" ")

        try:
            jobs = fetcher(company)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            jobs = []

        for job in jobs:
            if job["url"] and job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                all_jobs.append(job)

        print(f"{len(jobs)} matches", file=sys.stderr)
        queried += 1
        time.sleep(REQUEST_DELAY)

    print(
        f"  career_pages: queried {queried} companies, "
        f"skipped {skipped} (unsupported ATS), "
        f"found {len(all_jobs)} software engineering jobs",
        file=sys.stderr,
    )
    return all_jobs


if __name__ == "__main__":
    jobs = search_jobs()
    print(json.dumps(jobs, indent=2))
