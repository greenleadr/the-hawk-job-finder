"""Generate an HTML email digest from scored job postings.

Expects jobs in the format returned by ``scorer.score_jobs`` — each dict has
the original job fields plus a ``_score`` key with score, matched_skills,
gaps, and flags.

Usage:
    python digest.py          # renders a demo digest and writes digest_preview.html
    python -m digest          # same
"""

import html
import json
from datetime import date
from typing import Any

TOP_N = 10

# ---------------------------------------------------------------------------
# Color palette — elegant fantasy
# ---------------------------------------------------------------------------
# Background:  #faf6ef (warm ivory)
# Header bg:   #2c1810 (deep mahogany)
# Gold accent:  #b8963e
# Gold light:   #d4b869
# Text dark:    #2c1810
# Text body:    #4a3728
# Text muted:   #8a7560
# Score green:  #4a7c3f (forest)
# Score amber:  #9e7c23 (antique gold)
# Score red:    #8b3a3a (dark garnet)
# Pill bg:      #f0e8d8 (warm sand)
# Pill border:  #d4c4a8
# Card bg:      #ffffff
# Divider:      #e8dcc8

_BG_IVORY = "#faf6ef"
_BG_HEADER = "#2c1810"
_GOLD = "#b8963e"
_GOLD_LIGHT = "#d4b869"
_TEXT_DARK = "#2c1810"
_TEXT_BODY = "#4a3728"
_TEXT_MUTED = "#8a7560"
_SCORE_GREEN = "#4a7c3f"
_SCORE_AMBER = "#9e7c23"
_SCORE_RED = "#8b3a3a"
_PILL_BG = "#f0e8d8"
_PILL_BORDER = "#d4c4a8"
_CARD_BG = "#ffffff"
_DIVIDER = "#e8dcc8"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _score_color(score: int) -> tuple[str, str, str]:
    """Return (background, text_color, label) for a score badge."""
    if score >= 70:
        return _SCORE_GREEN, "#ffffff", "Worthy"
    if score >= 50:
        return _SCORE_AMBER, "#ffffff", "Promising"
    return _SCORE_RED, "#e8cccc", "Unworthy"


def _score_bar(score: int) -> str:
    bg, fg, label = _score_color(score)
    width = max(score, 8)
    return (
        f'<div style="background:{_DIVIDER};border-radius:12px;height:24px;'
        f'width:220px;display:inline-block;vertical-align:middle;">'
        f'<div style="background:{bg};border-radius:12px;height:24px;'
        f'width:{width * 2.2:.0f}px;max-width:220px;line-height:24px;'
        f'color:{fg};font-size:12px;font-weight:700;padding:0 10px;'
        f'white-space:nowrap;font-family:Georgia,serif;">'
        f'{score} &mdash; {label}</div></div>'
    )


def _badge(text: str, bg: str, fg: str, border: str) -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:11px;font-weight:600;padding:3px 10px;border-radius:4px;'
        f'margin:0 4px 4px 0;border:1px solid {border};">{_esc(text)}</span>'
    )


def _skill_pill(text: str) -> str:
    return _badge(text, bg=_PILL_BG, fg=_TEXT_DARK, border=_PILL_BORDER)


def _flag_pill(text: str) -> str:
    return _badge(text, bg="#fdf2f2", fg=_SCORE_RED, border="#e8c4c4")


def _render_job_row(job: dict[str, Any], rank: int) -> str:
    s = job.get("_score", {})
    score: int = s.get("score", 0)
    matched: list[str] = s.get("matched_skills", [])
    flags: list[str] = s.get("flags", [])

    title = _esc(job.get("title", "Unknown"))
    company = _esc(job.get("company", "Unknown"))
    location = _esc(job.get("location", "\u2014"))
    url = _esc(job.get("url", "#"))
    source = _esc(job.get("source", ""))
    date_posted = _esc(job.get("date_posted", ""))

    skills_html = " ".join(_skill_pill(sk) for sk in matched[:8])
    if len(matched) > 8:
        skills_html += (
            f' <span style="color:{_TEXT_MUTED};font-size:12px;font-style:italic;">'
            f'+{len(matched) - 8} more</span>'
        )

    flags_html = " ".join(_flag_pill(f) for f in flags) if flags else ""

    meta_parts = [location]
    if source:
        meta_parts.append(source)
    if date_posted:
        meta_parts.append(date_posted)
    meta = " &middot; ".join(meta_parts)

    # LLM insights (if available)
    llm = s.get("llm", {})
    llm_html = ""
    if llm:
        rec = llm.get("recommendation", "")
        rec_labels = {
            "Apply": "Pursue This Quest",
            "Maybe": "Investigate Further",
            "Skip": "Pass",
        }
        rec_label = rec_labels.get(rec, rec)
        rec_colors = {
            "Apply": _SCORE_GREEN,
            "Maybe": _SCORE_AMBER,
            "Skip": _SCORE_RED,
        }
        rec_color = rec_colors.get(rec, _TEXT_MUTED)
        llm_score = llm.get("llm_score", "?")
        strengths = llm.get("strengths", [])
        concerns = llm.get("concerns", [])

        rec_badge = (
            f'<span style="display:inline-block;background:{rec_color};color:#fff;'
            f'font-size:11px;font-weight:700;padding:4px 12px;border-radius:4px;'
            f'margin-right:8px;font-family:Georgia,serif;letter-spacing:0.5px;">'
            f'{_esc(rec_label)}</span>'
        )
        llm_score_text = (
            f'<span style="color:{_TEXT_MUTED};font-size:12px;font-style:italic;">'
            f'Oracle rating: {llm_score}/10</span>'
        )

        detail_items = ""
        if strengths:
            detail_items += "".join(
                f'<div style="color:{_SCORE_GREEN};font-size:12px;'
                f'line-height:1.6;padding-left:4px;">'
                f'&#9733; {_esc(s)}</div>'
                for s in strengths[:3]
            )
        if concerns:
            detail_items += "".join(
                f'<div style="color:{_SCORE_RED};font-size:12px;'
                f'line-height:1.6;padding-left:4px;">'
                f'&#9651; {_esc(c)}</div>'
                for c in concerns[:3]
            )

        llm_html = (
            f'<div style="margin-top:10px;padding:10px 14px;background:{_BG_IVORY};'
            f'border-radius:6px;border:1px solid {_DIVIDER};">'
            f'{rec_badge}{llm_score_text}'
            f'<div style="margin-top:8px;">{detail_items}</div>'
            f'</div>'
        )

    return f"""
    <tr style="border-bottom:1px solid {_DIVIDER};">
      <td style="padding:18px 12px;vertical-align:top;width:36px;
                 color:{_GOLD};font-size:22px;font-weight:700;
                 text-align:center;font-family:Georgia,serif;">
        {rank}
      </td>
      <td style="padding:18px 16px 18px 4px;">
        <div style="margin-bottom:6px;">
          <a href="{url}" style="color:{_TEXT_DARK};font-size:16px;font-weight:700;
                                  text-decoration:none;
                                  font-family:Georgia,serif;">{title}</a>
          <span style="color:{_TEXT_MUTED};font-size:14px;margin-left:10px;
                       font-style:italic;">{company}</span>
        </div>
        <div style="margin-bottom:8px;">{_score_bar(score)}</div>
        <div style="color:{_TEXT_MUTED};font-size:13px;margin-bottom:8px;">{meta}</div>
        <div style="margin-bottom:4px;">{skills_html}</div>
        {f'<div style="margin-top:6px;">{flags_html}</div>' if flags_html else ''}
        {llm_html}
      </td>
    </tr>"""


def _render_compact_row(job: dict[str, Any]) -> str:
    """Render a compact row for still-open / recently-closed sections."""
    title = _esc(job.get("title", "Unknown"))
    company = _esc(job.get("company", "Unknown"))
    location = _esc(job.get("location", "\u2014"))
    url = _esc(job.get("url", "#"))
    score = job.get("score", 0)
    bg, _fg, label = _score_color(score)

    return (
        f'<tr style="border-bottom:1px solid {_DIVIDER};">'
        f'<td style="padding:10px 16px;">'
        f'<a href="{url}" style="color:{_TEXT_DARK};font-size:14px;font-weight:600;'
        f'text-decoration:none;font-family:Georgia,serif;">{title}</a>'
        f'<span style="color:{_TEXT_MUTED};font-size:13px;margin-left:6px;'
        f'font-style:italic;">{company}</span>'
        f'<span style="color:{_TEXT_MUTED};font-size:12px;margin-left:6px;">{location}</span>'
        f'</td>'
        f'<td style="padding:10px 16px;text-align:right;">'
        f'<span style="background:{bg};color:#fff;font-size:11px;font-weight:700;'
        f'padding:3px 10px;border-radius:4px;font-family:Georgia,serif;">{score}</span>'
        f'</td></tr>'
    )


def _render_section(title: str, rows: list[dict[str, Any]], icon: str = "") -> str:
    """Render a secondary section with compact job rows."""
    if not rows:
        return ""
    rows_html = "\n".join(_render_compact_row(r) for r in rows[:10])
    extra = (
        f' <span style="color:{_TEXT_MUTED};font-size:13px;font-style:italic;">'
        f'(+{len(rows) - 10} more)</span>'
        if len(rows) > 10 else ""
    )
    return f"""
    <div style="background:{_CARD_BG};overflow:hidden;margin-top:2px;
                border-left:1px solid {_DIVIDER};
                border-right:1px solid {_DIVIDER};">
      <div style="padding:14px 24px;border-bottom:1px solid {_DIVIDER};
                  background:{_BG_IVORY};">
        <h3 style="margin:0;font-size:14px;color:{_TEXT_DARK};text-align:center;
                   font-family:Georgia,serif;letter-spacing:2px;
                   text-transform:uppercase;">
          {icon} {title} ({len(rows)}){extra}
        </h3>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""


def generate_digest(
    scored_jobs: list[dict[str, Any]],
    run_date: date | None = None,
    still_open: list[dict[str, Any]] | None = None,
    recently_closed: list[dict[str, Any]] | None = None,
    long_open: list[dict[str, Any]] | None = None,
) -> str:
    """Return an HTML email body for the given scored job list.

    *still_open*, *recently_closed*, and *long_open* are optional DB rows
    for extra sections.
    """
    today = run_date or date.today()
    date_str = today.strftime("%B %d, %Y")
    total = len(scored_jobs)

    jobs = sorted(
        scored_jobs,
        key=lambda j: j.get("_score", {}).get("score", 0),
        reverse=True,
    )
    top = jobs[:TOP_N]

    strong = sum(1 for j in jobs if j.get("_score", {}).get("score", 0) >= 70)
    moderate = sum(1 for j in jobs if 50 <= j.get("_score", {}).get("score", 0) < 70)

    rows_html = "\n".join(_render_job_row(j, i + 1) for i, j in enumerate(top))

    still_open_html = _render_section(
        "Still Open", still_open or [], icon="&#128994;"
    )
    long_open_html = _render_section(
        "Open 7+ Days \u2014 Apply Soon", long_open or [], icon="&#11088;"
    )
    closed_html = _render_section(
        "Recently Closed", recently_closed or [], icon="&#128308;"
    )

    # SVG hawk coat of arms — heraldic hawk on a shield, ivory/gold on dark
    hawk_crest = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" '
        'width="100" height="120" style="display:block;margin:0 auto 12px;">'
        # Shield
        '<path d="M100 8 L188 50 L188 140 Q188 200 100 232 Q12 200 12 140 L12 50 Z" '
        f'fill="{_BG_HEADER}" stroke="{_GOLD}" stroke-width="3.5"/>'
        # Inner border
        '<path d="M100 22 L176 58 L176 138 Q176 192 100 220 Q24 192 24 138 L24 58 Z" '
        f'fill="none" stroke="{_GOLD}" stroke-width="0.8" opacity="0.4"/>'
        # Hawk body
        '<path d="M100 58 Q114 61 118 74 L122 90 Q126 104 122 113 '
        'L113 132 Q108 142 100 147 Q92 142 87 132 L78 113 Q74 104 78 90 '
        f'L82 74 Q86 61 100 58 Z" fill="{_GOLD}" stroke="{_GOLD_LIGHT}" stroke-width="1"/>'
        # Head
        f'<circle cx="100" cy="65" r="13" fill="{_GOLD}" stroke="{_GOLD_LIGHT}" stroke-width="1"/>'
        # Beak
        f'<path d="M100 68 L106 74 L100 72 L94 74 Z" fill="{_BG_HEADER}"/>'
        # Eyes
        f'<circle cx="95" cy="62" r="2" fill="{_BG_HEADER}"/>'
        f'<circle cx="105" cy="62" r="2" fill="{_BG_HEADER}"/>'
        f'<circle cx="95.4" cy="61.5" r="0.7" fill="{_GOLD_LIGHT}"/>'
        f'<circle cx="105.4" cy="61.5" r="0.7" fill="{_GOLD_LIGHT}"/>'
        # Left wing
        '<path d="M82 88 Q58 70 34 74 Q42 83 52 92 Q43 88 30 91 '
        f'Q42 100 58 102 Q48 102 38 107 Q52 112 72 108 L78 100 Z" '
        f'fill="{_GOLD}" stroke="{_GOLD_LIGHT}" stroke-width="0.8"/>'
        # Right wing
        '<path d="M118 88 Q142 70 166 74 Q158 83 148 92 Q157 88 170 91 '
        f'Q158 100 142 102 Q152 102 162 107 Q148 112 128 108 L122 100 Z" '
        f'fill="{_GOLD}" stroke="{_GOLD_LIGHT}" stroke-width="0.8"/>'
        # Wing details
        f'<path d="M67 90 L53 85" stroke="{_GOLD_LIGHT}" stroke-width="0.5" opacity="0.6"/>'
        f'<path d="M60 97 L45 94" stroke="{_GOLD_LIGHT}" stroke-width="0.5" opacity="0.6"/>'
        f'<path d="M133 90 L147 85" stroke="{_GOLD_LIGHT}" stroke-width="0.5" opacity="0.6"/>'
        f'<path d="M140 97 L155 94" stroke="{_GOLD_LIGHT}" stroke-width="0.5" opacity="0.6"/>'
        # Tail
        '<path d="M92 145 L84 172 Q100 165 100 165 Q100 165 116 172 L108 145 Z" '
        f'fill="{_GOLD}" stroke="{_GOLD_LIGHT}" stroke-width="0.8"/>'
        f'<line x1="100" y1="147" x2="100" y2="165" stroke="{_GOLD_LIGHT}" '
        'stroke-width="0.5" opacity="0.6"/>'
        # Crown
        '<path d="M93 53 L96 46 L98 51 L100 44 L102 51 L104 46 L107 53" '
        f'fill="none" stroke="{_GOLD_LIGHT}" stroke-width="1.2"/>'
        f'<circle cx="100" cy="43" r="1.5" fill="{_GOLD_LIGHT}"/>'
        '</svg>'
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:{_BG_IVORY};font-family:
  Georgia,'Times New Roman',Times,serif;">

  <div style="max-width:680px;margin:0 auto;padding:24px 16px;">

    <!-- Header -->
    <div style="background:{_BG_HEADER};border-radius:8px 8px 0 0;
                padding:36px 32px 28px;color:#f5efe6;text-align:center;">

      {hawk_crest}

      <h1 style="margin:0;font-size:26px;font-weight:400;
                 letter-spacing:8px;text-transform:uppercase;
                 color:{_GOLD_LIGHT};">
        The Hawk
      </h1>
      <div style="font-size:11px;letter-spacing:4px;text-transform:uppercase;
                  color:{_GOLD};margin:2px 0 6px;opacity:0.8;">
        Quest Board
      </div>
      <div style="font-size:13px;color:#c4b49a;font-style:italic;">
        &ldquo;Sharp eyes find the finest quarry.&rdquo;
      </div>

      <!-- Divider -->
      <div style="margin:18px auto 16px;width:240px;height:1px;
                  background:linear-gradient(90deg,transparent,{_GOLD}80,transparent);">
      </div>

      <!-- Stats -->
      <table cellpadding="0" cellspacing="0" border="0"
             style="margin:0 auto;border-spacing:12px;">
        <tr>
          <td style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                     border-radius:6px;padding:12px 24px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:{_GOLD_LIGHT};
                        font-family:Georgia,serif;">{total}</div>
            <div style="font-size:9px;letter-spacing:2px;text-transform:uppercase;
                        color:{_GOLD};opacity:0.7;margin-top:2px;">Quests</div>
          </td>
          <td style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                     border-radius:6px;padding:12px 24px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:{_GOLD_LIGHT};
                        font-family:Georgia,serif;">{strong}</div>
            <div style="font-size:9px;letter-spacing:2px;text-transform:uppercase;
                        color:{_GOLD};opacity:0.7;margin-top:2px;">Worthy</div>
          </td>
          <td style="background:rgba(255,255,255,0.06);border:1px solid {_GOLD}40;
                     border-radius:6px;padding:12px 24px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:{_GOLD_LIGHT};
                        font-family:Georgia,serif;">{moderate}</div>
            <div style="font-size:9px;letter-spacing:2px;text-transform:uppercase;
                        color:{_GOLD};opacity:0.7;margin-top:2px;">Promising</div>
          </td>
        </tr>
      </table>

      <div style="font-size:12px;color:{_GOLD};opacity:0.5;margin-top:14px;">
        {date_str}
      </div>
    </div>

    <!-- Quest list -->
    <div style="background:{_CARD_BG};overflow:hidden;
                border-left:1px solid {_DIVIDER};
                border-right:1px solid {_DIVIDER};">
      <div style="padding:16px 24px;border-bottom:1px solid {_DIVIDER};
                  background:{_BG_IVORY};">
        <h2 style="margin:0;font-size:15px;color:{_TEXT_DARK};text-align:center;
                   font-family:Georgia,serif;letter-spacing:3px;
                   text-transform:uppercase;">
          &#9876;&ensp;Top {min(TOP_N, total)} Quests&ensp;&#9876;
        </h2>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>

    {still_open_html}
    {long_open_html}
    {closed_html}

    <!-- Footer -->
    <div style="background:{_BG_HEADER};border-radius:0 0 8px 8px;
                padding:16px 24px;text-align:center;">
      <div style="font-size:11px;letter-spacing:3px;color:{_GOLD};
                  opacity:0.6;font-family:Georgia,serif;">
        THE HAWK &middot; {date_str}
      </div>
      <div style="font-size:10px;color:{_GOLD};opacity:0.35;
                  font-style:italic;margin-top:4px;">
        By order of the realm, delivered by raven at dawn
      </div>
    </div>

  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    from scorer import _DEMO_JOBS, load_profile, score_jobs

    profile = load_profile()
    scored = score_jobs(_DEMO_JOBS, profile)

    html_body = generate_digest(scored)
    out = "digest_preview.html"
    with open(out, "w") as f:
        f.write(html_body)

    print(f"Digest preview written to {out}")
    print(f"Jobs: {len(scored)}, top score: {scored[0]['_score']['score']}")


if __name__ == "__main__":
    _demo()
