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
from svgkit import ROOT, THEME_CSS, char_w, esc, font_face, svg_open

LOGIN = "alanvaa06"
OUT = ROOT / "assets"
W = 840  # shared page width for every graphic
RAMP = " .:-=+*#%@"

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
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
        {"query": QUERY, "variables": {"login": LOGIN, "from": frm, "to": to}}
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


def streaks(days):
    cur = longest = 0
    cur_range = longest_range = ("", "")
    run_start = None
    for date, n in days:
        if n > 0:
            if run_start is None:
                run_start = date
            cur += 1
            cur_range = (run_start, date)
            if cur > longest:
                longest, longest_range = cur, cur_range
        else:
            cur, run_start = 0, None
    # current streak counts back from the last day (today may still be 0)
    tail = 0
    tail_range = ("", "")
    for date, n in reversed(days):
        if n > 0:
            tail += 1
            tail_range = (date, tail_range[1] or date)
        elif date != days[-1][0]:
            break
    return tail, tail_range, longest, longest_range


def fmt_range(a, b):
    if not a:
        return "--"
    da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    f = lambda d: d.strftime("%b %d").replace(" 0", " ")
    return f"{f(da)} - {f(db)}" if a != b else f(da)


def css():
    return (
        font_face("jbmono-latin.woff2", "jbm", 400)
        + font_face("jbmono-latin-bold.woff2", "jbm", 700)
        + THEME_CSS
    )


def ramp_css():
    # the grid draws with the ramp subset; the label needs real letters
    return (
        font_face("jbmono-ramp.woff2", "jbmr", 400)
        + font_face("jbmono-latin.woff2", "jbm", 400)
        + THEME_CSS
    )


# --- graphic 1: hero total + weekly sparkline ------------------------------

def render_hero(cal, days):
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
    # weekly area sparkline, right half; weekly aggregates make a line honest
    x0, x1, y0, y1 = 380, W, 30, 120
    mx = max(weekly) or 1
    n = len(weekly)
    pts = []
    for i, v in enumerate(weekly):
        x = x0 + (x1 - x0) * i / (n - 1)
        y = y1 - (y1 - y0) * v / mx
        pts.append(f"{x:.1f},{y:.1f}")
    area = f"{x0},{y1} " + " ".join(pts) + f" {x1},{y1}"
    s.append(f'<polygon points="{area}" class="accent" opacity="0.15"/>')
    s.append(
        f'<polyline points="{" ".join(pts)}" fill="none" class="accent" '
        f'stroke="var(--accent)" stroke-width="1.5"/>'
    )
    s.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" class="rule" stroke-width="1"/>')
    s.append("</svg>")
    (OUT / "stats-hero.svg").write_text("".join(s), encoding="utf-8")


def chunk_weeks(days):
    return [days[i : i + 7] for i in range(0, len(days) - len(days) % 7, 7)] or [days]


# --- graphic 2: streaks ----------------------------------------------------

def render_streak(days):
    cur, cur_r, lng, lng_r = streaks(days)
    h = 110
    s = [svg_open(W, h, css())]
    for i, (label, n, rng) in enumerate(
        [("current streak", cur, cur_r), ("longest streak", lng, lng_r)]
    ):
        x = 0 if i == 0 else 380
        s.append(f'<text x="{x}" y="24" font-size="13" class="dim">{label}</text>')
        s.append(
            f'<text x="{x}" y="66" font-size="34" font-weight="700" class="fg">'
            f'{n} <tspan font-size="16" font-weight="400" class="dim">days</tspan></text>'
        )
        s.append(
            f'<text x="{x}" y="94" font-size="13" class="dim">{fmt_range(*rng)}</text>'
        )
    s.append(f'<line x1="330" y1="14" x2="330" y2="96" class="rule" stroke-width="1"/>')
    s.append("</svg>")
    (OUT / "stats-streak.svg").write_text("".join(s), encoding="utf-8")


# --- graphic 3: top languages, by bytes and by repo ------------------------

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


# --- graphic 4: the year, one character per day, portrait ramp -------------

def render_year(days):
    weeks = [days[i : i + 7] for i in range(0, len(days), 7)]
    counts = sorted(n for _, n in days if n > 0)

    def level(n):
        if n == 0 or not counts:
            return 0
        q = sum(1 for c in counts if c <= n) / len(counts)
        return 1 + min(int(q * (len(RAMP) - 2)), len(RAMP) - 2)

    fs = 13.0
    cw = char_w(fs)  # 7.8
    lh = 15.0
    x0, y0 = 0, 34
    h = int(y0 + 7 * lh + 24)
    s = [svg_open(W, h, ramp_css())]
    s.append(
        '<text x="0" y="18" font-size="13" class="dim">the year, one character per day</text>'
    )
    for row in range(7):
        chars = []
        for wk in weeks:
            if row < len(wk):
                chars.append(RAMP[level(wk[row][1])])
            else:
                chars.append(" ")
        line = esc("".join(chars)).replace(" ", "&#160;")
        y = y0 + row * lh + 12
        s.append(
            f'<text x="{x0}" y="{y}" font-size="{fs}" '
            f"style=\"font-family:'jbmr',monospace\" xml:space=\"preserve\" "
            f'textLength="{len(weeks) * cw:.1f}" class="accent">{line}</text>'
        )
    s.append("</svg>")
    (OUT / "stats-year.svg").write_text("".join(s), encoding="utf-8")


def main():
    user = fetch()
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = day_series(cal)
    render_hero(cal, days)
    render_streak(days)
    render_langs(user["repositories"])
    render_year(days)
    print("wrote 4 svgs to assets/")


if __name__ == "__main__":
    main()
