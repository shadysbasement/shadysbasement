"""Generate readable GitHub profile cards from public account data.

This script runs in GitHub Actions with the repository's GITHUB_TOKEN. It only
reads public activity and writes two SVGs. Pass --calendar-json for a local
preview when a token is unavailable.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import urllib.request


LOGIN = "shadysbasement"
BASE = "https://api.github.com"
BG = "#0d1117"
PANEL = "#121820"
RULE = "#303846"
FG = "#e6edf3"
DIM = "#9daab8"
BLUE = "#59a7ff"
GREEN = "#4ec77c"
MONO = "JetBrains Mono,monospace"
SANS = "Noto Sans,sans-serif"


def request_json(url, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "shadysbasement-profile-renderer",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def rect(x, y, w, h, fill=PANEL, radius=0, stroke="none", sw=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def text(x, y, value, size=16, color=FG, weight=400, mono=False):
    family = MONO if mono else SANS
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>'


def line(x1, y1, x2, y2, color=RULE):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}"/>'


def circle(x, y, r, stroke, sw=2):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'


def svg(w, h, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n{body}\n</svg>\n'


def get_calendar(path):
    if path:
        data = json.loads(path.read_text())
    else:
        if not os.environ.get("GITHUB_TOKEN"):
            raise RuntimeError("GITHUB_TOKEN is required unless --calendar-json is supplied")
        query = '''query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks { contributionDays { date contributionCount } }
              }
            }
          }
        }'''
        data = request_json(f"{BASE}/graphql", {"query": query, "variables": {"login": LOGIN}})
    if data.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def activity_card(user, repos, calendar):
    total = calendar["totalContributions"]
    stars = sum(repo["stargazers_count"] for repo in repos)
    weeks = calendar["weeks"][-18:]
    s = [
        rect(0, 0, 680, 329, BG),
        rect(1, 1, 678, 327, "none", 11, RULE),
        text(27, 34, "CONTRIBUTIONS / PUBLIC DATA", 15, BLUE, 700, True),
        text(530, 34, "AUTO-UPDATED", 11, DIM, 400, True),
        text(27, 113, total, 69, FG, 700),
        text(120 if total < 10 else 155, 88, "contributions", 19, FG, 600),
        text(120 if total < 10 else 155, 113, "in the last year", 15, DIM),
        line(27, 132, 653, 132),
    ]
    stat_values = [("PUBLIC REPOS", len(repos)), ("REPO STARS", stars), ("FOLLOWERS", user["followers"])]
    for i, (label, value) in enumerate(stat_values):
        x = 28 + i * 211
        s.extend((text(x, 160, label, 12, DIM, 600, True), text(x, 190, value, 25, FG, 700)))
    s += [
        line(27, 205, 653, 205),
        text(27, 231, "Recent contribution calendar", 15, BLUE, 600),
        text(477, 231, "LAST 18 WEEKS", 11, DIM, 400, True),
    ]
    for col, week in enumerate(weeks):
        for row, day in enumerate(week["contributionDays"]):
            value = day["contributionCount"]
            color = "#242d36" if value == 0 else "#1d5f3b" if value == 1 else "#2d995a" if value < 4 else GREEN
            s.append(rect(28 + col * 24, 246 + row * 10, 17, 7, color, 1))
    s += [
        text(484, 265, "Public work only", 13, FG),
        text(484, 286, "Each square is", 12, DIM),
        text(484, 303, "one day.", 12, DIM),
    ]
    return svg(680, 329, "\n".join(s))


def signal_card(user, repos, events, now):
    since = now - timedelta(days=30)
    pushes = [event for event in events if event.get("type") == "PushEvent"
              and datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")) >= since]
    by_day = Counter(datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).weekday() for e in pushes)
    languages = Counter()
    for repo in repos:
        if repo["name"] == LOGIN or repo.get("fork"):
            continue
        languages.update(request_json(repo["languages_url"]))
    s = [
        rect(0, 0, 680, 325, BG),
        rect(1, 1, 678, 323, "none", 11, RULE),
        text(27, 34, "PUBLIC SIGNALS", 15, BLUE, 700, True),
        text(27, 65, "Recent pushes by weekday", 15, FG, 600),
        text(27, 89, "Last 30 days; public events only", 12, DIM),
        line(340, 49, 340, 185),
        text(363, 65, "Language activity", 15, FG, 600),
    ]
    max_count = max(by_day.values(), default=0)
    for day, label in enumerate("MTWTFSS"):
        x = 31 + day * 43
        count = by_day[day]
        h = int(62 * count / max_count) if max_count else 2
        s.append(rect(x, 165 - h, 23, h, GREEN if count else "#25313a", 4))
        s.append(text(x + 5, 184, label, 12, DIM, 400, True))
    if languages:
        total = sum(languages.values())
        for i, (name, amount) in enumerate(languages.most_common(3)):
            y = 94 + i * 29
            s += [text(363, y, name, 13, FG), rect(500, y - 12, 140, 8, "#25313a", 4),
                  rect(500, y - 12, max(3, round(140 * amount / total)), 8, GREEN, 4)]
    else:
        s += [text(363, 103, "No public source repos yet.", 14, DIM),
              text(363, 127, "This will fill in as code ships.", 12, DIM)]
    site_status = "Site linked; audit not configured" if user.get("blog", "").strip() else "No public site linked yet"
    s += [
        line(27, 200, 653, 200),
        text(27, 228, "PageSpeed Insights", 15, BLUE, 600),
        text(27, 249, site_status, 12, DIM),
    ]
    for i, label in enumerate(("PERFORMANCE", "ACCESSIBILITY", "PRACTICES", "SEO")):
        cx = 225 + i * 110
        s += [circle(cx, 251, 19, "#345545", 2), text(cx - 10, 256, "--", 13, GREEN, 700, True),
              text(cx - (len(label) * 3.5), 296, label, 10, DIM, 500, True)]
    return svg(680, 325, "\n".join(s))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar-json", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "assets")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    user = request_json(f"{BASE}/users/{LOGIN}")
    repos = request_json(f"{BASE}/users/{LOGIN}/repos?per_page=100&type=owner")
    events = request_json(f"{BASE}/users/{LOGIN}/events/public?per_page=100")
    calendar = get_calendar(args.calendar_json)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "activity.svg").write_text(activity_card(user, repos, calendar))
    (args.output_dir / "signals.svg").write_text(signal_card(user, repos, events, now))
    print(f"Rendered public profile stats: {calendar['totalContributions']} contributions, {len(repos)} repos")


if __name__ == "__main__":
    main()
