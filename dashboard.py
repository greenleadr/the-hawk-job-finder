"""Generate a static HTML dashboard for GitHub Pages.

Reads the SQLite database and produces a self-contained HTML page with:
  - Pipeline stats (total jobs, sources, score distribution)
  - Top matches table with score bars and skill pills
  - Still-open jobs section
  - Recently closed jobs section
  - Source breakdown chart (CSS-only, no JS dependencies)
  - 7-day trend summary
  - Application tracking funnel
  - Hawk-themed dark mode

Usage:
    python dashboard.py                 # writes docs/index.html
    python -m dashboard                 # same
"""

import json
import html as html_mod
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import db

DOCS_DIR = Path(__file__).resolve().parent / "docs"
OUTPUT_FILE = DOCS_DIR / "index.html"

# Hawk theme palette
_BG = "#1a1008"
_BG_CARD = "#2a1f14"
_BG_BAR = "#3d2c1a"
_GOLD = "#b8963e"
_GOLD_LIGHT = "#d4b869"
_TEXT = "#f5e6c8"
_TEXT_MUTED = "#a08860"
_GREEN = "#4a7c3f"
_AMBER = "#9e7c23"
_RED = "#8b3a3a"
_BORDER = "#5a4630"


def _esc(text: str) -> str:
    return html_mod.escape(str(text or ""), quote=True)


def _score_color(score: int) -> tuple[str, str]:
    if score >= 70:
        return _GREEN, "Worthy"
    if score >= 50:
        return _AMBER, "Promising"
    return _RED, "Unworthy"


def _score_bar_html(score: int, width: int = 160) -> str:
    bg, label = _score_color(score)
    fill = max(int(score / 100 * width), 6)
    return (
        f'<div style="background:{_BG_BAR};border-radius:6px;height:18px;'
        f'width:{width}px;display:inline-block;vertical-align:middle;">'
        f'<div style="background:{bg};border-radius:6px;height:18px;'
        f'width:{fill}px;line-height:18px;color:{_TEXT};font-size:11px;'
        f'font-weight:700;padding:0 6px;white-space:nowrap;'
        f'font-family:Georgia,serif;">'
        f'{score}</div></div>'
    )


def _pill(text: str, bg: str = _BG, fg: str = _GOLD) -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px;'
        f'margin:0 3px 3px 0;border:1px solid {_BORDER};">{_esc(text)}</span>'
    )


def _stat_card(value: str, label: str, color: str = _TEXT) -> str:
    return (
        f'<div style="background:rgba(255,255,255,0.04);border:1px solid {_BORDER};'
        f'border-radius:6px;padding:14px 20px;text-align:center;min-width:90px;">'
        f'<div style="font-size:28px;font-weight:700;color:{color};'
        f'font-family:Georgia,serif;">{value}</div>'
        f'<div style="font-size:10px;color:{_TEXT_MUTED};margin-top:2px;'
        f'letter-spacing:1px;text-transform:uppercase;">{label}</div>'
        f'</div>'
    )


def _bar_chart_row(label: str, count: int, max_count: int, color: str) -> str:
    pct = int(count / max(max_count, 1) * 100)
    return (
        f'<div style="display:flex;align-items:center;margin-bottom:6px;">'
        f'<div style="width:100px;font-size:12px;color:{_TEXT_MUTED};">{_esc(label)}</div>'
        f'<div style="flex:1;background:{_BG_BAR};border-radius:4px;height:20px;margin:0 8px;">'
        f'<div style="background:{color};border-radius:4px;height:20px;width:{pct}%;'
        f'min-width:2px;"></div></div>'
        f'<div style="font-size:12px;font-weight:600;color:{_TEXT};width:30px;">{count}</div>'
        f'</div>'
    )


def _render_job_row(job: dict[str, Any]) -> str:
    title = _esc(job.get("title", ""))
    company = _esc(job.get("company", ""))
    location = _esc(job.get("location", "\u2014"))
    url = _esc(job.get("url", "#"))
    score = job.get("score", 0) or 0
    source = _esc(job.get("source", ""))
    status = job.get("status", "open")

    skills_raw = job.get("matched_skills", "[]")
    try:
        skills = json.loads(skills_raw) if isinstance(skills_raw, str) else skills_raw
    except json.JSONDecodeError:
        skills = []
    skills_html = " ".join(_pill(s) for s in (skills or [])[:6])
    if len(skills or []) > 6:
        skills_html += f' <span style="color:{_TEXT_MUTED};font-size:11px;">+{len(skills) - 6}</span>'

    flags_raw = job.get("flags", "[]")
    try:
        flags = json.loads(flags_raw) if isinstance(flags_raw, str) else flags_raw
    except json.JSONDecodeError:
        flags = []
    flags_html = " ".join(_pill(f, bg=_RED, fg="#e8cccc") for f in (flags or [])[:3])

    status_dot = "&#128994;" if status == "open" else "&#128308;"
    first_seen = job.get("first_seen", "")[:10]
    flags_div = f'<div style="margin-top:4px;">{flags_html}</div>' if flags_html else ""

    return (
        f'<tr style="border-bottom:1px solid {_BORDER};">'
        f'<td style="padding:12px 16px;vertical-align:top;">'
        f'<div><a href="{url}" target="_blank" style="color:{_GOLD_LIGHT};font-size:14px;'
        f'font-weight:600;text-decoration:none;font-family:Georgia,serif;">{title}</a></div>'
        f'<div style="color:{_TEXT_MUTED};font-size:13px;">{company}'
        f'<span style="color:{_TEXT_MUTED};margin-left:8px;opacity:0.6;">{location}</span></div>'
        f'<div style="margin-top:4px;">{skills_html}</div>'
        f'{flags_div}'
        f'</td>'
        f'<td style="padding:12px 8px;vertical-align:top;text-align:center;">'
        f'{_score_bar_html(score)}</td>'
        f'<td style="padding:12px 8px;vertical-align:top;text-align:center;'
        f'font-size:12px;color:{_TEXT_MUTED};">{source}</td>'
        f'<td style="padding:12px 8px;vertical-align:top;text-align:center;'
        f'font-size:12px;color:{_TEXT_MUTED};">{status_dot} {first_seen}</td>'
        f'</tr>'
    )


def _render_tracking_section(funnel: dict[str, int]) -> str:
    statuses = [
        ("applied", _GOLD, "Applied"),
        ("interviewing", _GOLD_LIGHT, "Interviewing"),
        ("offer", _GREEN, "Offer"),
        ("rejected", _RED, "Rejected"),
        ("withdrawn", _TEXT_MUTED, "Withdrawn"),
    ]
    rows = ""
    for key, color, label in statuses:
        count = funnel.get(key, 0)
        if count:
            rows += (
                f'<div style="display:flex;align-items:center;margin-bottom:8px;">'
                f'<div style="width:12px;height:12px;border-radius:50%;background:{color};'
                f'margin-right:10px;"></div>'
                f'<div style="color:{_TEXT};font-size:14px;flex:1;font-family:Georgia,serif;">'
                f'{label}</div>'
                f'<div style="color:{color};font-size:20px;font-weight:700;'
                f'font-family:Georgia,serif;">{count}</div>'
                f'</div>'
            )
    if not rows:
        return ""
    return (
        f'<div class="card">'
        f'<h2>Application Tracking</h2>'
        f'{rows}'
        f'<div style="margin-top:10px;font-size:11px;color:{_TEXT_MUTED};">'
        f'Use <code style="background:{_BG_BAR};padding:2px 6px;border-radius:4px;'
        f'color:{_GOLD};">'
        f'python track.py set &lt;id&gt; applied</code> to track applications</div>'
        f'</div>'
    )


def generate_dashboard(conn: sqlite3.Connection, run_date: date | None = None) -> str:
    """Generate the full dashboard HTML from database state."""
    today = run_date or date.today()
    date_str = today.strftime("%B %d, %Y")

    try:
        import tracking
        track_conn = tracking.init_tracking()
        overrides = tracking.get_all_overrides(track_conn)
        track_funnel = tracking.get_funnel(track_conn)
        track_conn.close()
    except Exception:
        overrides = {}
        track_funnel = {}

    all_7d = db.get_history(conn, days=7)
    for j in all_7d:
        ov = overrides.get(j.get("id"))
        if ov:
            j["status"] = ov["status"]
    open_jobs = db.get_open_jobs(conn, days=7)
    closed_jobs = db.get_closed_jobs(conn, days=7)
    all_30d = db.get_history(conn, days=30)

    total_7d = len(all_7d)
    total_open = len(open_jobs)
    total_closed = len(closed_jobs)
    strong = sum(1 for j in all_7d if (j.get("score") or 0) >= 70)
    moderate = sum(1 for j in all_7d if 50 <= (j.get("score") or 0) < 70)
    tracked_count = sum(track_funnel.values())

    sources: dict[str, int] = {}
    for j in all_7d:
        s = j.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1
    max_source = max(sources.values()) if sources else 1
    source_colors = {
        "career_pages": _GOLD,
        "adzuna": _GOLD_LIGHT,
        "remotive": _GREEN,
        "hn_hiring": _AMBER,
    }

    score_buckets = {"90-100": 0, "70-89": 0, "50-69": 0, "30-49": 0, "0-29": 0}
    for j in all_7d:
        s = j.get("score") or 0
        if s >= 90:
            score_buckets["90-100"] += 1
        elif s >= 70:
            score_buckets["70-89"] += 1
        elif s >= 50:
            score_buckets["50-69"] += 1
        elif s >= 30:
            score_buckets["30-49"] += 1
        else:
            score_buckets["0-29"] += 1
    max_bucket = max(score_buckets.values()) if any(score_buckets.values()) else 1
    bucket_colors = {
        "90-100": _GREEN, "70-89": "#6a9c5f",
        "50-69": _AMBER, "30-49": "#8b6914", "0-29": _RED,
    }

    daily: dict[str, int] = {}
    for i in range(7):
        d = (today - timedelta(days=i)).isoformat()
        daily[d] = 0
    for j in all_7d:
        fs = (j.get("first_seen") or "")[:10]
        if fs in daily:
            daily[fs] += 1

    companies: dict[str, int] = {}
    for j in all_7d:
        c = j.get("company", "Unknown")
        companies[c] = companies.get(c, 0) + 1
    top_companies = sorted(companies.items(), key=lambda x: -x[1])[:10]
    max_company = top_companies[0][1] if top_companies else 1

    seen_keys: set[str] = set()
    unique_jobs: list[dict[str, Any]] = []
    for j in sorted(all_7d, key=lambda j: -(j.get("score") or 0)):
        key = f"{(j.get('title') or '').lower()}|{(j.get('company') or '').lower()}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique_jobs.append(j)
    top_jobs = unique_jobs[:20]
    top_rows = "\n".join(_render_job_row(j) for j in top_jobs)

    source_chart = "\n".join(
        _bar_chart_row(s, c, max_source, source_colors.get(s, _TEXT_MUTED))
        for s, c in sorted(sources.items(), key=lambda x: -x[1])
    )
    score_chart = "\n".join(
        _bar_chart_row(b, c, max_bucket, bucket_colors[b])
        for b, c in score_buckets.items()
    )
    company_chart = "\n".join(
        _bar_chart_row(c[:20], n, max_company, _GOLD)
        for c, n in top_companies
    )
    daily_chart = "\n".join(
        _bar_chart_row(d[5:], n, max(daily.values()) or 1, _GOLD_LIGHT)
        for d, n in sorted(daily.items())
    )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Hawk &mdash; Quest Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: {_BG}; font-family: Georgia, 'Times New Roman', serif;
      color: {_TEXT}; }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 24px 16px; }}
    .header {{ background: linear-gradient(180deg, #2c1810, {_BG_CARD});
      border-radius: 8px; padding: 28px 32px; color: {_TEXT};
      margin-bottom: 20px; border: 1px solid {_BORDER}; text-align: center; }}
    .header h1 {{ font-size: 26px; font-weight: 400; letter-spacing: 6px;
      text-transform: uppercase; color: {_GOLD_LIGHT}; }}
    .header p {{ font-size: 13px; color: {_TEXT_MUTED}; margin-top: 4px;
      letter-spacing: 2px; }}
    .stats {{ display: flex; gap: 12px; margin-top: 18px; flex-wrap: wrap;
      justify-content: center; }}
    .card {{ background: {_BG_CARD}; border-radius: 6px; padding: 20px 24px;
      margin-bottom: 16px; border: 1px solid {_BORDER}; }}
    .card h2 {{ font-size: 15px; color: {_GOLD_LIGHT}; margin-bottom: 14px;
      padding-bottom: 10px; border-bottom: 1px solid {_BORDER};
      letter-spacing: 2px; text-transform: uppercase; font-weight: 400; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; padding: 10px 16px; font-size: 11px;
      color: {_TEXT_MUTED}; font-weight: 600; border-bottom: 1px solid {_BORDER};
      letter-spacing: 1px; text-transform: uppercase; }}
    .footer {{ text-align: center; padding: 24px 0; color: {_TEXT_MUTED};
      font-size: 11px; letter-spacing: 2px; }}
    a {{ color: {_GOLD_LIGHT}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; color: {_GOLD}; }}
    .legend {{ display: flex; gap: 20px; align-items: center; padding: 12px 24px;
      border-top: 1px solid {_BORDER}; font-size: 11px; color: {_TEXT_MUTED}; flex-wrap: wrap; }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  </style>
</head>
<body>
  <div class="wrap">

    <div class="header">
      <h1>The Hawk</h1>
      <p>Quest Dashboard &mdash; {date_str}</p>
      <div class="stats">
        {_stat_card(str(total_7d), "Quests (7d)", _TEXT)}
        {_stat_card(str(total_open), "Open", _GREEN)}
        {_stat_card(str(strong), "Worthy 70+", _GREEN)}
        {_stat_card(str(moderate), "Promising 50+", _AMBER)}
        {_stat_card(str(total_closed), "Closed", _RED)}
        {_stat_card(str(len(all_30d)), "Total (30d)", _GOLD_LIGHT)}
        {_stat_card(str(tracked_count), "Tracked", _GOLD) if tracked_count else ""}
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Score Distribution (7d)</h2>
        {score_chart}
      </div>
      <div class="card">
        <h2>By Source (7d)</h2>
        {source_chart}
      </div>
      <div class="card">
        <h2>Daily New Quests</h2>
        {daily_chart}
      </div>
      <div class="card">
        <h2>Top Companies (7d)</h2>
        {company_chart}
      </div>
    </div>

    {_render_tracking_section(track_funnel) if tracked_count else ""}

    <div class="card">
      <h2>Top 20 Quests (7d)</h2>
      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Quest</th>
              <th style="text-align:center;">Score</th>
              <th style="text-align:center;">Source</th>
              <th style="text-align:center;">Status</th>
            </tr>
          </thead>
          <tbody>
            {top_rows if top_rows else f'<tr><td colspan="4" style="padding:24px;text-align:center;color:{_TEXT_MUTED};">No quests in the last 7 days. Run the pipeline first.</td></tr>'}
          </tbody>
        </table>
      </div>
      <div class="legend">
        <span style="color:{_TEXT_MUTED};font-weight:600;">Legend:</span>
        <div class="legend-item">&#128994;<span>Open</span></div>
        <div class="legend-item">&#128308;<span>Closed</span></div>
        <div class="legend-item">
          <span style="background:{_GREEN};color:{_TEXT};font-size:10px;font-weight:700;
            padding:1px 6px;border-radius:4px;">70+</span>
          <span>Worthy</span>
        </div>
        <div class="legend-item">
          <span style="background:{_AMBER};color:{_TEXT};font-size:10px;font-weight:700;
            padding:1px 6px;border-radius:4px;">50-69</span>
          <span>Promising</span>
        </div>
        <div class="legend-item">
          <span style="background:{_RED};color:{_TEXT};font-size:10px;font-weight:700;
            padding:1px 6px;border-radius:4px;">&lt;50</span>
          <span>Unworthy</span>
        </div>
      </div>
    </div>

    <div class="footer">
      THE HAWK &middot; Generated {generated_at} &middot;
      By order of the realm
    </div>

  </div>
</body>
</html>"""


def build(db_path: str | Path | None = None) -> Path:
    """Generate the dashboard and write to docs/index.html."""
    DOCS_DIR.mkdir(exist_ok=True)
    conn = db.init_db(db_path)
    html = generate_dashboard(conn)
    conn.close()
    OUTPUT_FILE.write_text(html)
    print(f"Dashboard written to {OUTPUT_FILE}", file=sys.stderr)
    return OUTPUT_FILE


if __name__ == "__main__":
    build()
