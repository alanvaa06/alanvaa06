#!/usr/bin/env python3
"""Draw the profile's stats SVGs from the GitHub GraphQL API.

Standard library only -- nothing to break in CI. Determinism rules
(both from hard-won experience, see the workflow):

  1. The contribution window is pinned to whole UTC days, so two runs on
     the same day are byte-identical.
  2. Language stats read PUBLIC repos only, so the numbers agree no
     matter whose token asks.
"""

import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, THEME_CSS, esc, font_face, svg_open

LOGIN = "alanvaa06"
OUT = ROOT / "assets"
W = 840  # shared page width for every graphic
API = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!, $since: GitTimestamp!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER,
                 isFork: false) {
      nodes {
        name
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    recent: repositories(first: 6, privacy: PUBLIC, ownerAffiliations: OWNER,
                         isFork: false,
                         orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { name description pushedAt }
    }
    punch: repositories(first: 25, privacy: PUBLIC, ownerAffiliations: OWNER,
                        isFork: false,
                        orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100, since: $since) { nodes { committedDate } }
            }
          }
        }
      }
    }
  }
}
"""


def fetch():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN not set")
    today = dt.datetime.now(dt.timezone.utc).date()
    frm = f"{today - dt.timedelta(days=364)}T00:00:00Z"
    to = f"{today}T23:59:59Z"
    body = json.dumps(
        {"query": QUERY, "variables": {"login": LOGIN, "from": frm, "to": to, "since": frm}}
    ).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": LOGIN,
        },
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]


def day_series(cal):
    days = []
    for wk in cal["weeks"]:
        for d in wk["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort()
    return days


def css():
    return (
        font_face("jbmono-latin.woff2", "jbm", 400)
        + font_face("jbmono-latin-bold.woff2", "jbm", 700)
        + THEME_CSS
    )


# --- graphic 1: activity — hero numbers + honest weekly columns ------------

def render_activity(cal, days):
    total = cal["totalContributions"]
    weekly = [sum(d[1] for d in wk) for wk in chunk_weeks(days)]
    h = 150
    s = [svg_open(W, h, css())]
    s.append(
        f'<text x="0" y="28" font-size="13" class="dim">contributions, past year</text>'
    )
    s.append(
        f'<text x="0" y="86" font-size="46" font-weight="700" class="fg">{total:,}</text>'
    )
    active = sum(1 for _, n in days if n > 0)
    s.append(
        f'<text x="0" y="118" font-size="13" class="dim">'
        f"{active} active days &#183; best week {max(weekly)}</text>"
    )
    # weekly columns, right half. Columns, not a line: sparse weeks are
    # honest as empty space, a line would claim values that never existed.
    x0, x1, y0, y1 = 380, W, 30, 118
    mx = max(weekly) or 1
    n = len(weekly)
    slot = (x1 - x0) / n
    bw = max(2.0, slot - 2.0)
    for i, v in enumerate(weekly):
        if v == 0:
            continue
        bh = max(2.0, (y1 - y0) * v / mx)
        s.append(
            f'<rect x="{x0 + i * slot:.1f}" y="{y1 - bh:.1f}" '
            f'width="{bw:.1f}" height="{bh:.1f}" rx="1" class="accent"/>'
        )
    s.append(
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" class="rule" stroke-width="1"/>'
    )
    s.append("</svg>")
    (OUT / "stats-activity.svg").write_text("".join(s), encoding="utf-8")


def chunk_weeks(days):
    return [days[i : i + 7] for i in range(0, len(days) - len(days) % 7, 7)] or [days]


# --- graphic 2: recently shipped -------------------------------------------

def render_recent(recent):
    # the profile repo updates itself nightly -- listing it here is noise
    rows = [r for r in recent["nodes"] if r["name"] != LOGIN][:3]
    h = 44 + len(rows) * 30
    s = [svg_open(W, h, css())]
    s.append('<text x="0" y="20" font-size="13" class="dim">recently shipped</text>')
    for i, r in enumerate(rows):
        y = 48 + i * 30
        name = esc(r["name"])
        desc = (r.get("description") or "").strip()
        if len(desc) > 62:
            desc = desc[:59].rstrip() + "..."
        date = dt.date.fromisoformat(r["pushedAt"][:10]).strftime("%b %d").replace(" 0", " ")
        s.append(
            f'<text x="0" y="{y}" font-size="13" font-weight="700" class="accent">{name}</text>'
        )
        s.append(
            f'<text x="300" y="{y}" font-size="13" class="dim">{esc(desc)}</text>'
        )
        s.append(
            f'<text x="{W}" y="{y}" font-size="13" text-anchor="end" class="fg">{date}</text>'
        )
    s.append("</svg>")
    (OUT / "stats-recent.svg").write_text("".join(s), encoding="utf-8")


# --- graphic 3: when I build — weekday x hour punch card -------------------

def render_punch(punch):
    # committedDate carries the author's own UTC offset, so fromisoformat
    # gives honest local wall-clock time — no timezone hardcoding.
    # Repos are solo-owned, so no author filter is needed.
    grid = [[0] * 24 for _ in range(7)]
    total = 0
    for repo in punch["nodes"]:
        ref = repo.get("defaultBranchRef")
        if not ref:
            continue
        for c in ref["target"]["history"]["nodes"]:
            t = dt.datetime.fromisoformat(c["committedDate"])
            grid[t.weekday()][t.hour] += 1
            total += 1
    if not total:
        return
    off_hours = sum(
        grid[d][h]
        for d in range(7)
        for h in range(24)
        if d >= 5 or h < 9 or h >= 18
    )
    pct = round(100 * off_hours / total)

    x0, y0, cw, rh = 46, 46, (W - 60) / 24, 18
    h = int(y0 + 7 * rh + 40)
    mx = max(max(r) for r in grid)
    s = [svg_open(W, h, css())]
    s.append('<text x="0" y="20" font-size="13" class="dim">when I build</text>')
    days_lbl = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    for d in range(7):
        cy = y0 + d * rh + rh / 2
        s.append(
            f'<text x="0" y="{cy + 4:.0f}" font-size="11" class="dim">{days_lbl[d]}</text>'
        )
        for hh in range(24):
            v = grid[d][hh]
            if not v:
                continue
            r = 1.5 + 5.5 * (v / mx) ** 0.5
            s.append(
                f'<circle cx="{x0 + hh * cw + cw / 2:.1f}" cy="{cy:.1f}" '
                f'r="{r:.1f}" class="accent"/>'
            )
    for hh in (0, 6, 12, 18, 23):
        s.append(
            f'<text x="{x0 + hh * cw + cw / 2:.0f}" y="{y0 + 7 * rh + 14:.0f}" '
            f'font-size="11" text-anchor="middle" class="dim">{hh:02d}</text>'
        )
    s.append(
        f'<text x="{W}" y="20" font-size="13" text-anchor="end" class="fg">'
        f"{pct}% of commits land nights or weekends</text>"
    )
    s.append("</svg>")
    (OUT / "stats-punch.svg").write_text("".join(s), encoding="utf-8")


# --- graphic 4: writing, scraped from my own site --------------------------

WRITING_URL = "https://www.alanvaa.cloud/writing"
WRITING_RE = (
    r'<a[^>]*href="((?:https?://[^"]*(?:eleconomista\.com\.mx|bloomberglinea\.com|'
    r'higherlogicdownload)[^"]*|/ai-chain[^"]*))"[^>]*>(.*?)</a>'
)
# curated: URL substrings, in display order
WRITING_PICKS = ["higherlogicdownload", "ai-chain", "productividad"]


def render_writing():
    import re

    try:
        req = urllib.request.Request(WRITING_URL, headers={"User-Agent": LOGIN})
        with urllib.request.urlopen(req, timeout=20) as r:
            src = r.read().decode("utf-8", "replace")
    except OSError:
        print("writing: fetch failed, keeping previous svg")
        return
    import html as html_mod

    found = {}
    for m in re.finditer(WRITING_RE, src, re.S):
        inner = re.sub(r"<[^>]+>", "|", m.group(2))
        parts = [
            html_mod.unescape(p).strip()
            for p in inner.split("|")
            if html_mod.unescape(p).strip() not in ("", "·")
        ]
        # markup yields [outlet, section(s), title, "Published in...", ...]:
        # the title is the last part before the boilerplate begins
        head = []
        for p in parts:
            if p.startswith(("Published", "Read", "Hover")):
                break
            head.append(p)
        if len(head) < 2:
            continue
        outlet = head[0] if len(head) == 2 else f"{head[0]} · {head[-2]}"
        for key in WRITING_PICKS:
            if key in m.group(1).lower() and key not in found:
                found[key] = (outlet, head[-1], m.group(1))
    items = [found[k] for k in WRITING_PICKS if k in found]
    if len(items) < 2:
        # site markup changed — keep whatever the last good run drew
        print("writing: scrape thin, keeping previous svg")
        return
    h = 44 + len(items) * 30
    s = [svg_open(W, h, css())]
    s.append(
        '<text x="0" y="20" font-size="13" class="dim">writing, off github</text>'
    )
    for i, (outlet, title, _url) in enumerate(items):
        y = 48 + i * 30
        s.append(
            f'<text x="0" y="{y}" font-size="13" class="dim">{esc(outlet)}</text>'
        )
        s.append(
            f'<text x="240" y="{y}" font-size="13" font-weight="700" '
            f'class="fg">{esc(title[:70])}</text>'
        )
    s.append("</svg>")
    (OUT / "stats-writing.svg").write_text("".join(s), encoding="utf-8")


# --- graphic 5: top languages, by bytes and by repo ------------------------

def render_langs(repos):
    by_bytes, by_repos = {}, {}
    for repo in repos["nodes"]:
        seen = set()
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            by_bytes[name] = by_bytes.get(name, 0) + e["size"]
            if name not in seen:
                by_repos[name] = by_repos.get(name, 0) + 1
                seen.add(name)
    top_b = sorted(by_bytes.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    top_r = sorted(by_repos.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    rows = max(len(top_b), len(top_r))
    h = 46 + rows * 28
    s = [svg_open(W, h, css())]
    tb = sum(v for _, v in top_b) or 1
    tr = max((v for _, v in top_r), default=1)

    def col(x, title, items, total, unit):
        s.append(f'<text x="{x}" y="20" font-size="13" class="dim">{title}</text>')
        for i, (name, v) in enumerate(items):
            y = 46 + i * 28
            pct = v / total
            s.append(
                f'<text x="{x}" y="{y}" font-size="13" class="fg">{esc(name)}</text>'
            )
            bw = 180 * pct
            s.append(
                f'<rect x="{x + 150}" y="{y - 10}" width="180" height="8" rx="2" class="faint"/>'
            )
            s.append(
                f'<rect x="{x + 150}" y="{y - 10}" width="{bw:.1f}" height="8" rx="2" class="accent"/>'
            )
            label = f"{pct * 100:.0f}%" if unit == "%" else f"{v}"
            s.append(
                f'<text x="{x + 342}" y="{y}" font-size="12" class="dim">{label}</text>'
            )

    col(0, "top languages, by bytes (public)", top_b, tb, "%")
    col(440, "by repository count", top_r, tr, "n")
    s.append("</svg>")
    (OUT / "stats-langs.svg").write_text("".join(s), encoding="utf-8")


def main():
    user = fetch()
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = day_series(cal)
    render_activity(cal, days)
    render_punch(user["punch"])
    render_recent(user["recent"])
    render_writing()
    render_langs(user["repositories"])
    print("done: assets/stats-*.svg")


if __name__ == "__main__":
    main()
