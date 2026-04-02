"""Generate and send a weekly summary digest.

Queries the SQLite database for the week's trends and sends a summary
email with: total new jobs, top companies hiring, score distribution,
application funnel, jobs that disappeared, and top matches.

Usage:
    python weekly_summary.py              # generate and send
    SKIP_EMAIL=true python weekly_summary.py  # generate only (print HTML)
"""

import json
import html as html_mod
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

import db

# Hawk theme palette
_BG_IVORY = "#faf6ef"
_BG_HEADER = "#2c1810"
_BG_CARD = "#ffffff"
_GOLD = "#b8963e"
_GOLD_LIGHT = "#d4b869"
_TEXT_DARK = "#2c1810"
_TEXT_BODY = "#4a3728"
_TEXT_MUTED = "#8a7560"
_SCORE_GREEN = "#4a7c3f"
_SCORE_AMBER = "#9e7c23"
_SCORE_RED = "#8b3a3a"
_DIVIDER = "#e8dcc8"
_PILL_BG = "#f0e8d8"


def _esc(text: str) -> str:
    return html_mod.escape(str(text or ""), quote=True)


def _stat_row(label: str, value: str, color: str = _TEXT_DARK) -> str:
    return (
        f'<tr><td style="padding:8px 16px;color:{_TEXT_MUTED};font-size:14px;">{_esc(label)}</td>'
        f'<td style="padding:8px 16px;font-size:14px;font-weight:700;color:{color};'
        f'font-family:Georgia,serif;">{_esc(value)}</td></tr>'
    )


def _bar(label: str, count: int, max_c: int, color: str) -> str:
    pct = int(count / max(max_c, 1) * 100)
    return (
        f'<div style="display:flex;align-items:center;margin-bottom:5px;">'
        f'<div style="width:120px;font-size:13px;color:{_TEXT_MUTED};">{_esc(label)}</div>'
        f'<div style="flex:1;background:{_DIVIDER};border-radius:4px;height:18px;margin:0 8px;">'
        f'<div style="background:{color};border-radius:4px;height:18px;width:{pct}%;'
        f'min-width:2px;"></div></div>'
        f'<div style="font-size:13px;font-weight:600;color:{_TEXT_DARK};width:30px;">{count}</div></div>'
    )


def _job_row(j: dict[str, Any]) -> str:
    title = _esc(j.get("title", ""))
    company = _esc(j.get("company", ""))
    url = _esc(j.get("url", "#"))
    score = j.get("score") or 0
    bg = _SCORE_GREEN if score >= 70 else _SCORE_AMBER if score >= 50 else _SCORE_RED
    return (
        f'<tr style="border-bottom:1px solid {_DIVIDER};">'
        f'<td style="padding:8px 16px;"><a href="{url}" style="color:{_TEXT_DARK};'
        f'font-weight:600;text-decoration:none;font-family:Georgia,serif;">{title}</a>'
        f'<span style="color:{_TEXT_MUTED};margin-left:8px;font-style:italic;">{company}</span></td>'
        f'<td style="padding:8px;text-align:center;">'
        f'<span style="background:{bg};color:#fff;font-size:11px;font-weight:700;'
        f'padding:3px 10px;border-radius:4px;font-family:Georgia,serif;">{score}</span></td></tr>'
    )


def generate_weekly_summary(conn, run_date: date | None = None) -> str:
    today = run_date or date.today()
    week_start = today - timedelta(days=7)
    date_str = today.strftime("%B %d, %Y")
    week_range = f"{week_start.strftime('%b %d')} \u2013 {today.strftime('%b %d, %Y')}"

    all_week = db.get_history(conn, days=7)
    open_jobs = db.get_open_jobs(conn, days=7)
    closed_jobs = db.get_closed_jobs(conn, days=7)
    long_open = db.get_long_open_jobs(conn, min_days=7, max_days=30)
    funnel = db.get_application_funnel(conn)

    total = len(all_week)
    strong = sum(1 for j in all_week if (j.get("score") or 0) >= 70)
    moderate = sum(1 for j in all_week if 50 <= (j.get("score") or 0) < 70)

    companies: dict[str, int] = {}
    for j in all_week:
        c = j.get("company", "Unknown")
        companies[c] = companies.get(c, 0) + 1
    top_companies = sorted(companies.items(), key=lambda x: -x[1])[:10]
    max_co = top_companies[0][1] if top_companies else 1
    co_chart = "\n".join(_bar(c[:25], n, max_co, _GOLD) for c, n in top_companies)

    sources: dict[str, int] = {}
    for j in all_week:
        s = j.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1
    src_colors = {
        "career_pages": _GOLD, "adzuna": _GOLD_LIGHT,
        "remotive": _SCORE_GREEN, "hn_hiring": _SCORE_AMBER,
    }
    max_src = max(sources.values()) if sources else 1
    src_chart = "\n".join(
        _bar(s, c, max_src, src_colors.get(s, _TEXT_MUTED))
        for s, c in sorted(sources.items(), key=lambda x: -x[1])
    )

    top_10 = sorted(all_week, key=lambda j: -(j.get("score") or 0))[:10]
    seen: set[str] = set()
    unique_top: list[dict[str, Any]] = []
    for j in top_10:
        key = f"{(j.get('title') or '').lower()}|{(j.get('company') or '').lower()}"
        if key not in seen:
            seen.add(key)
            unique_top.append(j)
    top_rows = "\n".join(_job_row(j) for j in unique_top)

    funnel_html = ""
    for status, label, color in [
        ("open", "Open", _SCORE_GREEN), ("applied", "Applied", _GOLD),
        ("interviewing", "Interviewing", _GOLD_LIGHT), ("offer", "Offer", _SCORE_GREEN),
        ("rejected", "Rejected", _SCORE_RED), ("closed", "Closed", _TEXT_MUTED),
    ]:
        count = funnel.get(status, 0)
        funnel_html += _stat_row(label, str(count), color)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:{_BG_IVORY};font-family:
  Georgia,'Times New Roman',Times,serif;">
  <div style="max-width:680px;margin:0 auto;padding:24px 16px;">

    <div style="background:{_BG_HEADER};border-radius:8px 8px 0 0;
                padding:28px 32px;color:{_GOLD_LIGHT};text-align:center;">
      <h1 style="margin:0;font-size:24px;font-weight:400;letter-spacing:6px;
                 text-transform:uppercase;">Weekly Summary</h1>
      <p style="margin:4px 0 0;font-size:13px;color:{_GOLD};opacity:0.8;
               letter-spacing:2px;">{week_range}</p>
      <div style="margin:18px auto 0;width:240px;height:1px;
                  background:linear-gradient(90deg,transparent,{_GOLD}80,transparent);"></div>
      <div style="margin-top:16px;display:flex;gap:12px;flex-wrap:wrap;justify-content:center;">
        <div style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                    border-radius:6px;padding:10px 18px;text-align:center;">
          <div style="font-size:26px;font-weight:700;">{total}</div>
          <div style="font-size:10px;opacity:0.7;letter-spacing:1px;">NEW QUESTS</div></div>
        <div style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                    border-radius:6px;padding:10px 18px;text-align:center;">
          <div style="font-size:26px;font-weight:700;">{strong}</div>
          <div style="font-size:10px;opacity:0.7;letter-spacing:1px;">WORTHY (70+)</div></div>
        <div style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                    border-radius:6px;padding:10px 18px;text-align:center;">
          <div style="font-size:26px;font-weight:700;">{moderate}</div>
          <div style="font-size:10px;opacity:0.7;letter-spacing:1px;">PROMISING</div></div>
        <div style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                    border-radius:6px;padding:10px 18px;text-align:center;">
          <div style="font-size:26px;font-weight:700;">{len(closed_jobs)}</div>
          <div style="font-size:10px;opacity:0.7;letter-spacing:1px;">CLOSED</div></div>
        <div style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                    border-radius:6px;padding:10px 18px;text-align:center;">
          <div style="font-size:26px;font-weight:700;">{len(long_open)}</div>
          <div style="font-size:10px;opacity:0.7;letter-spacing:1px;">OPEN 7+ DAYS</div></div>
      </div>
    </div>

    <div style="background:{_BG_CARD};border-left:1px solid {_DIVIDER};
                border-right:1px solid {_DIVIDER};padding:0;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0;">
        <div style="padding:20px 24px;border-right:1px solid {_DIVIDER};border-bottom:1px solid {_DIVIDER};">
          <h2 style="font-size:14px;margin:0 0 12px;border-bottom:1px solid {_DIVIDER};
                     padding-bottom:8px;color:{_TEXT_DARK};letter-spacing:2px;
                     text-transform:uppercase;">Top Companies</h2>
          {co_chart}
        </div>
        <div style="padding:20px 24px;border-bottom:1px solid {_DIVIDER};">
          <h2 style="font-size:14px;margin:0 0 12px;border-bottom:1px solid {_DIVIDER};
                     padding-bottom:8px;color:{_TEXT_DARK};letter-spacing:2px;
                     text-transform:uppercase;">By Source</h2>
          {src_chart}
        </div>
      </div>

      <div style="padding:20px 24px;border-bottom:1px solid {_DIVIDER};">
        <h2 style="font-size:14px;margin:0 0 12px;border-bottom:1px solid {_DIVIDER};
                   padding-bottom:8px;color:{_TEXT_DARK};letter-spacing:2px;
                   text-transform:uppercase;">Application Funnel</h2>
        <table style="width:100%;border-collapse:collapse;">{funnel_html}</table>
      </div>

      <div style="padding:20px 24px;">
        <h2 style="font-size:14px;margin:0 0 12px;border-bottom:1px solid {_DIVIDER};
                   padding-bottom:8px;color:{_TEXT_DARK};letter-spacing:2px;
                   text-transform:uppercase;">Top Quests This Week</h2>
        <table style="width:100%;border-collapse:collapse;">{top_rows}</table>
      </div>
    </div>

    <div style="background:{_BG_HEADER};border-radius:0 0 8px 8px;
                padding:16px 24px;text-align:center;">
      <div style="font-size:11px;letter-spacing:3px;color:{_GOLD};opacity:0.6;">
        THE HAWK &middot; Weekly Summary &middot; {date_str}
      </div>
    </div>

  </div>
</body>
</html>"""


def run() -> None:
    conn = db.init_db()
    today = date.today()
    html_body = generate_weekly_summary(conn, run_date=today)

    skip_email = os.environ.get("SKIP_EMAIL", "").lower() == "true"
    if skip_email:
        print(html_body)
        print("SKIP_EMAIL=true — printed HTML", file=sys.stderr)
    else:
        from emailer import send_digest
        send_digest(
            html_body,
            job_count=len(db.get_history(conn, days=7)),
            run_date=today,
        )

    conn.close()


if __name__ == "__main__":
    run()
