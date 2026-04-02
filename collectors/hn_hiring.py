"""Hacker News 'Who is Hiring?' collector.

Fetches the latest monthly HN 'Ask HN: Who is hiring?' thread via
the Algolia API and extracts software engineering job postings.

No API key required. Rate limit: 10,000 requests/hour.

Usage:
    python -m collectors.hn_hiring
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Algolia HN Search API — find the latest "Who is hiring" thread
SEARCH_URL = (
    "https://hn.algolia.com/api/v1/search_by_date"
    "?query=%22who+is+hiring%22"
    "&tags=ask_hn"
    "&hitsPerPage=5"
)

ITEM_URL = "https://hn.algolia.com/api/v1/items/{item_id}"

# Title filter — engineering roles at senior+ level
_ENGINEERING_RE = re.compile(
    r"\b(software|platform|cloud|data|full[- ]?stack|front[- ]?end|back[- ]?end|"
    r"systems?|devops|sre|infrastructure)\b",
    re.I,
)
_ROLE_RE = re.compile(r"\b(engineer|developer|sde|swe|architect)\b", re.I)
_SENIORITY_RE = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|ii\b|iii\b|iv\b)\b",
    re.I,
)


def _fetch_json(url: str, retries: int = 2) -> Any:
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "HawkJobFinder/1.0",
    })
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except (HTTPError, URLError, OSError) as exc:
            if attempt < retries:
                time.sleep(2)
                continue
            print(f"  HN API error: {exc}", file=sys.stderr)
            return None
    return None


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()


def _find_latest_thread() -> int | None:
    """Find the item ID of the most recent 'Who is hiring' thread."""
    data = _fetch_json(SEARCH_URL)
    if not data or not data.get("hits"):
        return None

    for hit in data["hits"]:
        title = hit.get("title", "").lower()
        if "who is hiring" in title and "freelancer" not in title:
            item_id = hit.get("objectID")
            if item_id:
                print(f"  Found thread: {hit.get('title')} (ID: {item_id})", file=sys.stderr)
                return int(item_id)
    return None


def _is_target_role(text: str) -> bool:
    """Check if the text mentions a senior engineering role."""
    return bool(
        _ENGINEERING_RE.search(text)
        and _ROLE_RE.search(text)
        and _SENIORITY_RE.search(text)
    )


def _parse_comment(comment: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single HN comment into a job dict, or return None if not relevant."""
    text = _strip_html(comment.get("text", ""))
    if not text or len(text) < 50:
        return None

    # HN job posts typically start with "Company | Title | Location | ..."
    first_line = text.split("\n")[0].strip()
    parts = [p.strip() for p in first_line.split("|")]

    # Check if any part contains a target engineering title
    title_match = None
    for part in parts:
        if _is_target_role(part):
            title_match = part
            break

    # Also check the full text for engineering role mentions
    if not title_match:
        if _is_target_role(text):
            title_match = parts[0] if parts else first_line[:100]
        else:
            return None

    # Extract company name (usually first part before |)
    company = parts[0] if parts else ""
    company = re.sub(r"\s*\([^)]*\)\s*", " ", company).strip()

    # Extract location hints
    location = ""
    location_patterns = ["remote", "minneapolis", "st. paul", "twin cities",
                         "madison", "milwaukee", "wisconsin", "minnesota",
                         "sf", "san francisco", "nyc", "new york", "london",
                         "worldwide", "us ", "usa", "hybrid", "on-site", "onsite"]
    for part in parts:
        if any(loc in part.lower() for loc in location_patterns):
            location = part.strip()
            break

    # Look for URLs in the text
    url_match = re.search(r"https?://\S+", text)
    url = url_match.group(0).rstrip(".,;)") if url_match else ""

    # Use the HN comment permalink if no URL found
    comment_id = comment.get("id")
    if not url and comment_id:
        url = f"https://news.ycombinator.com/item?id={comment_id}"

    return {
        "title": title_match[:200],
        "company": company[:100],
        "location": location or "See posting",
        "url": url,
        "description": text[:3000],
        "source": "hn_hiring",
        "date_posted": comment.get("created_at", ""),
    }


def search_jobs() -> list[dict[str, Any]]:
    """Fetch the latest HN 'Who is Hiring' thread and extract engineering jobs."""
    print("Fetching HN 'Who is Hiring' thread …", file=sys.stderr)

    thread_id = _find_latest_thread()
    if not thread_id:
        print("  Could not find 'Who is Hiring' thread", file=sys.stderr)
        return []

    # Fetch full thread with all comments
    data = _fetch_json(ITEM_URL.format(item_id=thread_id))
    if not data or "children" not in data:
        print("  Could not fetch thread comments", file=sys.stderr)
        return []

    children = data.get("children", [])
    print(f"  Thread has {len(children)} comments", file=sys.stderr)

    jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for comment in children:
        parsed = _parse_comment(comment)
        if parsed and parsed["url"] not in seen_urls:
            seen_urls.add(parsed["url"])
            jobs.append(parsed)

    print(f"  Found {len(jobs)} engineering postings", file=sys.stderr)
    return jobs


if __name__ == "__main__":
    jobs = search_jobs()
    print(json.dumps(jobs, indent=2))
