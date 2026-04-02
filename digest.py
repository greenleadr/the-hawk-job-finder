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


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _score_color(score: int) -> tuple[str, str]:
    """Return (background, label) for a score badge."""
    if score >= 70:
        return "#c9a84c", "Worthy"
    if score >= 50:
        return "#8b6914", "Promising"
    return "#6b2121", "Unworthy"


def _score_bar(score: int) -> str:
    bg, label = _score_color(score)
    width = max(score, 8)  # minimum visible width
    return (
        f'<div style="background:#2a1f14;border-radius:6px;height:22px;'
        f'width:200px;display:inline-block;vertical-align:middle;'
        f'border:1px solid #5a4630;">'
        f'<div style="background:{bg};border-radius:5px;height:22px;'
        f'width:{width * 2}px;max-width:200px;line-height:22px;'
        f'color:#1a1008;font-size:12px;font-weight:700;padding:0 8px;'
        f'white-space:nowrap;">{score} &mdash; {label}</div></div>'
    )


def _badge(text: str, bg: str = "#6b2121", fg: str = "#f5e6c8") -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:11px;font-weight:600;padding:2px 8px;border-radius:3px;'
        f'margin:0 4px 4px 0;border:1px solid {fg}30;">{_esc(text)}</span>'
    )


def _skill_pill(text: str) -> str:
    return _badge(text, bg="#1a1008", fg="#c9a84c")


def _flag_pill(text: str) -> str:
    return _badge(text, bg="#3d1111", fg="#e8a0a0")


def _render_job_row(job: dict[str, Any], rank: int) -> str:
    s = job.get("_score", {})
    score: int = s.get("score", 0)
    matched: list[str] = s.get("matched_skills", [])
    flags: list[str] = s.get("flags", [])

    title = _esc(job.get("title", "Unknown"))
    company = _esc(job.get("company", "Unknown"))
    location = _esc(job.get("location", "—"))
    url = _esc(job.get("url", "#"))
    source = _esc(job.get("source", ""))
    date_posted = _esc(job.get("date_posted", ""))

    skills_html = " ".join(_skill_pill(sk) for sk in matched[:8])
    if len(matched) > 8:
        skills_html += f' <span style="color:#64748b;font-size:12px;">+{len(matched) - 8} more</span>'

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
        # Fantasy-themed recommendation labels
        rec_labels = {"Apply": "Pursue This Quest", "Maybe": "Investigate Further", "Skip": "Pass"}
        rec_label = rec_labels.get(rec, rec)
        rec_colors = {"Apply": "#5a7a2e", "Maybe": "#8b6914", "Skip": "#6b2121"}
        rec_color = rec_colors.get(rec, "#5a4630")
        llm_score = llm.get("llm_score", "?")
        strengths = llm.get("strengths", [])
        concerns = llm.get("concerns", [])

        rec_badge = (
            f'<span style="display:inline-block;background:{rec_color};color:#f5e6c8;'
            f'font-size:11px;font-weight:700;padding:3px 10px;border-radius:3px;'
            f'margin-right:8px;border:1px solid #c9a84c40;'
            f'font-family:Georgia,serif;letter-spacing:1px;">{_esc(rec_label)}</span>'
        )
        llm_score_text = (
            f'<span style="color:#5a4630;font-size:12px;font-style:italic;">'
            f'Oracle rating: {llm_score}/10</span>'
        )

        detail_items = ""
        if strengths:
            detail_items += "".join(
                f'<span style="color:#5a7a2e;font-size:12px;">&#9733; {_esc(s)}</span><br>'
                for s in strengths[:3]
            )
        if concerns:
            detail_items += "".join(
                f'<span style="color:#8b3a3a;font-size:12px;">&#9888; {_esc(c)}</span><br>'
                for c in concerns[:3]
            )

        llm_html = (
            f'<div style="margin-top:8px;padding:8px 12px;background:#e8dcc4;'
            f'border-radius:3px;border:1px solid #c9a84c60;">'
            f'{rec_badge}{llm_score_text}'
            f'<div style="margin-top:6px;">{detail_items}</div>'
            f'</div>'
        )

    return f"""
    <tr style="border-bottom:1px solid #c9a84c40;">
      <td style="padding:16px;vertical-align:top;width:36px;color:#8b6914;
                 font-size:20px;font-weight:700;text-align:center;
                 font-family:Georgia,serif;">
        {rank}
      </td>
      <td style="padding:16px;">
        <div style="margin-bottom:4px;">
          <a href="{url}" style="color:#5a3000;font-size:16px;font-weight:700;
                                  text-decoration:none;
                                  font-family:Georgia,serif;">{title}</a>
          <span style="color:#6b5530;font-size:14px;margin-left:8px;
                       font-style:italic;">{company}</span>
        </div>
        <div style="margin-bottom:6px;">{_score_bar(score)}</div>
        <div style="color:#8b7355;font-size:13px;margin-bottom:6px;">{meta}</div>
        <div style="margin-bottom:4px;">{skills_html}</div>
        {f'<div style="margin-top:6px;">{flags_html}</div>' if flags_html else ''}
        {llm_html}
      </td>
    </tr>"""


def generate_digest(
    scored_jobs: list[dict[str, Any]],
    run_date: date | None = None,
) -> str:
    """Return an HTML email body for the given scored job list.

    *scored_jobs* should already contain ``_score`` dicts (as produced by
    ``scorer.score_jobs``).  They are re-sorted by score descending here for
    safety.
    """
    today = run_date or date.today()
    date_str = today.strftime("%B %d, %Y")
    total = len(scored_jobs)

    # Sort descending by score
    jobs = sorted(
        scored_jobs,
        key=lambda j: j.get("_score", {}).get("score", 0),
        reverse=True,
    )
    top = jobs[:TOP_N]

    strong = sum(1 for j in jobs if j.get("_score", {}).get("score", 0) >= 70)
    moderate = sum(1 for j in jobs if 50 <= j.get("_score", {}).get("score", 0) < 70)

    # Build job rows
    rows_html = "\n".join(_render_job_row(j, i + 1) for i, j in enumerate(top))

    # SVG hawk coat of arms — a heraldic hawk on a shield
    hawk_crest = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" '
        'width="120" height="144" style="display:block;margin:0 auto 8px;">'
        # Shield shape
        '<path d="M100 8 L188 50 L188 140 Q188 200 100 232 Q12 200 12 140 L12 50 Z" '
        'fill="#1a1008" stroke="#c9a84c" stroke-width="4"/>'
        # Inner shield border
        '<path d="M100 20 L178 56 L178 138 Q178 192 100 222 Q22 192 22 138 L22 56 Z" '
        'fill="none" stroke="#8b6914" stroke-width="1.5" stroke-dasharray="4,3"/>'
        # Diagonal cross / saltire behind hawk
        '<line x1="45" y1="50" x2="155" y2="190" stroke="#2a1f14" stroke-width="18"/>'
        '<line x1="155" y1="50" x2="45" y2="190" stroke="#2a1f14" stroke-width="18"/>'
        # Hawk body
        '<path d="M100 55 Q115 58 120 72 L125 90 Q130 105 125 115 '
        'L115 135 Q110 145 100 150 Q90 145 85 135 L75 115 Q70 105 75 90 '
        'L80 72 Q85 58 100 55 Z" fill="#c9a84c" stroke="#8b6914" stroke-width="1.5"/>'
        # Head
        '<circle cx="100" cy="62" r="14" fill="#c9a84c" stroke="#8b6914" stroke-width="1.5"/>'
        # Beak
        '<path d="M100 65 L107 72 L100 70 L93 72 Z" fill="#5a4630"/>'
        # Eyes
        '<circle cx="94" cy="59" r="2.5" fill="#1a1008"/>'
        '<circle cx="106" cy="59" r="2.5" fill="#1a1008"/>'
        '<circle cx="94.5" cy="58.5" r="0.8" fill="#c9a84c"/>'
        '<circle cx="106.5" cy="58.5" r="0.8" fill="#c9a84c"/>'
        # Left wing spread
        '<path d="M80 85 Q55 65 30 70 Q38 80 50 90 Q40 85 25 88 '
        'Q38 98 55 100 Q45 100 35 105 Q50 110 70 108 L75 100 Z" '
        'fill="#c9a84c" stroke="#8b6914" stroke-width="1"/>'
        # Right wing spread
        '<path d="M120 85 Q145 65 170 70 Q162 80 150 90 Q160 85 175 88 '
        'Q162 98 145 100 Q155 100 165 105 Q150 110 130 108 L125 100 Z" '
        'fill="#c9a84c" stroke="#8b6914" stroke-width="1"/>'
        # Wing feather details
        '<path d="M65 88 L50 82" stroke="#8b6914" stroke-width="0.7"/>'
        '<path d="M58 95 L42 92" stroke="#8b6914" stroke-width="0.7"/>'
        '<path d="M135 88 L150 82" stroke="#8b6914" stroke-width="0.7"/>'
        '<path d="M142 95 L158 92" stroke="#8b6914" stroke-width="0.7"/>'
        # Tail feathers
        '<path d="M90 148 L82 175 Q100 168 100 168 Q100 168 118 175 L110 148 Z" '
        'fill="#c9a84c" stroke="#8b6914" stroke-width="1"/>'
        '<line x1="92" y1="150" x2="88" y2="170" stroke="#8b6914" stroke-width="0.7"/>'
        '<line x1="100" y1="150" x2="100" y2="168" stroke="#8b6914" stroke-width="0.7"/>'
        '<line x1="108" y1="150" x2="112" y2="170" stroke="#8b6914" stroke-width="0.7"/>'
        # Talons
        '<path d="M90 148 L85 155 L83 152" stroke="#5a4630" stroke-width="1.5" fill="none"/>'
        '<path d="M110 148 L115 155 L117 152" stroke="#5a4630" stroke-width="1.5" fill="none"/>'
        # Crown / crest on head
        '<path d="M92 50 L95 42 L98 48 L100 40 L102 48 L105 42 L108 50" '
        'fill="none" stroke="#c9a84c" stroke-width="1.5"/>'
        '<circle cx="100" cy="39" r="2" fill="#c9a84c"/>'
        # Corner ornaments on shield
        '<path d="M40 55 Q50 50 55 55 Q50 60 40 55 Z" fill="#8b6914" opacity="0.5"/>'
        '<path d="M160 55 Q150 50 145 55 Q150 60 160 55 Z" fill="#8b6914" opacity="0.5"/>'
        '</svg>'
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0d0906;font-family:
  Georgia,'Times New Roman',Times,serif;">

  <!-- Parchment wrapper -->
  <div style="max-width:700px;margin:0 auto;padding:24px 16px;">

    <!-- Header — dark fantasy banner -->
    <div style="background:linear-gradient(180deg,#1a1008 0%,#2a1f14 50%,#1a1008 100%);
                border-radius:4px;padding:32px 32px 24px;color:#f5e6c8;
                margin-bottom:2px;text-align:center;
                border:2px solid #5a4630;
                box-shadow:inset 0 0 60px rgba(0,0,0,0.5);">

      <!-- Coat of Arms -->
      {hawk_crest}

      <h1 style="margin:4px 0 0;font-size:28px;font-weight:400;
                 letter-spacing:6px;text-transform:uppercase;
                 color:#c9a84c;font-family:Georgia,'Times New Roman',serif;">
        The Hawk
      </h1>
      <div style="font-size:11px;letter-spacing:4px;text-transform:uppercase;
                  color:#8b6914;margin-bottom:4px;">
        &mdash; Quest Board &mdash;
      </div>
      <div style="font-size:13px;color:#a08860;font-style:italic;">
        &ldquo;Sharp eyes find the finest quarry.&rdquo;
      </div>
      <div style="font-size:12px;color:#6b5530;margin-top:8px;">
        {date_str}
      </div>

      <!-- Ornamental divider -->
      <div style="margin:16px auto 16px;width:300px;height:1px;
                  background:linear-gradient(90deg,transparent,#c9a84c,transparent);">
      </div>

      <!-- Stats as heraldic plaques -->
      <div style="display:flex;gap:12px;justify-content:center;">
        <div style="background:#0d0906;border:1px solid #5a4630;border-radius:3px;
                    padding:10px 20px;text-align:center;">
          <div style="font-size:28px;font-weight:700;color:#c9a84c;
                      font-family:Georgia,serif;">{total}</div>
          <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;
                      color:#8b6914;">Quests Found</div>
        </div>
        <div style="background:#0d0906;border:1px solid #5a4630;border-radius:3px;
                    padding:10px 20px;text-align:center;">
          <div style="font-size:28px;font-weight:700;color:#c9a84c;
                      font-family:Georgia,serif;">{strong}</div>
          <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;
                      color:#8b6914;">Worthy (70+)</div>
        </div>
        <div style="background:#0d0906;border:1px solid #5a4630;border-radius:3px;
                    padding:10px 20px;text-align:center;">
          <div style="font-size:28px;font-weight:700;color:#c9a84c;
                      font-family:Georgia,serif;">{moderate}</div>
          <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;
                      color:#8b6914;">Promising (50-69)</div>
        </div>
      </div>
    </div>

    <!-- Top Matches — parchment scroll -->
    <div style="background:linear-gradient(180deg,#f5e6c8,#efe0c0,#f5e6c8);
                border-radius:2px;overflow:hidden;
                border:2px solid #5a4630;
                box-shadow:0 4px 12px rgba(0,0,0,0.4);">
      <div style="padding:18px 24px;
                  border-bottom:2px solid #c9a84c;
                  background:linear-gradient(90deg,#efe0c0,#f5e6c8,#efe0c0);">
        <h2 style="margin:0;font-size:17px;color:#2a1f14;text-align:center;
                   font-family:Georgia,serif;letter-spacing:2px;
                   text-transform:uppercase;">
          &#9876; Top {min(TOP_N, total)} Quests &#9876;
        </h2>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>

    <!-- Footer — dark parchment -->
    <div style="text-align:center;padding:20px 0 8px;font-size:12px;
                color:#5a4630;">
      <div style="margin:12px auto;width:200px;height:1px;
                  background:linear-gradient(90deg,transparent,#5a4630,transparent);">
      </div>
      <span style="letter-spacing:2px;font-family:Georgia,serif;">
        THE HAWK &middot; Quest Board &middot; {date_str}
      </span>
      <br>
      <span style="font-size:10px;color:#3d2c1a;font-style:italic;">
        By order of the realm, delivered by raven at dawn
      </span>
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
