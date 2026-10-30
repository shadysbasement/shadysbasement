"""Render the profile's animated header and real GitHub contribution calendar."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import urllib.request

from PIL import Image, ImageDraw, ImageFont


LOGIN = "shadysbasement"
WIDTH = 680
BG = (3, 9, 7)
GREEN = (70, 240, 132)
PALE = (220, 242, 225)
MUTED = (116, 151, 126)
FONT_PATHS = (
    "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)
ART = (
    " ####  #   #    #    ####   #   #",
    "#      #   #   # #   #   #   # # ",
    " ###   #####  #####  #   #    #  ",
    "    #  #   #  #   #  #   #    #  ",
    "####   #   #  #   #  ####     #  ",
)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def calendar_from_github() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN or pass --calendar-json")
    query = """query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": LOGIN}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "shadysbasement-profile",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def rain(draw: ImageDraw.ImageDraw, frame: int, height: int) -> None:
    small = font(13)
    for col in range(28):
        x = 15 + col * 24
        phase = (col * 37) % height
        for j in range(10):
            y = (phase + j * 26 + frame * 10) % height
            char = "01"[(col * 3 + j * 7) % 2]
            shade = 23 + ((col * 17 + j * 11) % 32)
            if j == (frame + col) % 10:
                shade = 77
            draw.text((x, y), char, font=small, fill=(13, shade, 28))


def hero_frame(frame: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, 260), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((17, 16, 663, 244), radius=9, fill=(3, 11, 8), outline=(29, 77, 44), width=1)
    rain(d, frame, 260)
    d.rectangle((77, 65, 605, 201), fill=(3, 11, 8))
    d.text((40, 30), "$ whoami", font=font(17), fill=GREEN)
    face = font(21)
    for row, line in enumerate(ART):
        color = (122, 230, 151) if row == frame % len(ART) else PALE
        d.text((88, 69 + row * 25), line, font=face, fill=color)
    d.line((40, 210, 640, 210), fill=(28, 69, 42), width=1)
    d.text((40, 220), "i'm sufyan. i run arch and make stuff.", font=font(14), fill=MUTED)
    d.rectangle((608, 223, 616, 237), fill=GREEN if frame % 2 else (20, 54, 31))
    return img


def contribution_frame(calendar: dict, frame: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, 252), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((17, 16, 663, 236), radius=9, fill=(3, 11, 8), outline=(29, 77, 44), width=1)
    rain(d, frame, 252)
    d.rectangle((36, 75, 641, 205), fill=(3, 11, 8))
    d.text((40, 31), "contributions", font=font(20), fill=PALE)
    total = calendar["totalContributions"]
    count_label = f"{total} this year"
    count_font = font(15)
    count_width = d.textlength(count_label, font=count_font)
    d.text((640 - count_width, 35), count_label, font=count_font, fill=GREEN)
    weeks = calendar["weeks"][-30:]
    for col, week in enumerate(weeks):
        for row, day in enumerate(week["contributionDays"]):
            value = day["contributionCount"]
            if value == 0:
                fill = (17, 37, 25)
            elif value == 1:
                fill = (37, 104, 60)
            elif value < 4:
                fill = (51, 161, 83)
            else:
                fill = (70, 217, 111)
            x = 40 + col * 20
            y = 78 + row * 18
            d.rounded_rectangle((x, y, x + 15, y + 13), radius=2, fill=fill)
            if col == frame and value:
                d.rounded_rectangle((x - 2, y - 2, x + 17, y + 15), radius=3, outline=GREEN, width=2)
    sweep = 40 + frame * 20
    d.line((sweep, 73, sweep, 202), fill=(40, 96, 55), width=1)
    d.text((40, 215), "the past 30 weeks of public work", font=font(13), fill=MUTED)
    return img


def save_gif(frames: list[Image.Image], path: Path, duration: int) -> None:
    converted = [im.quantize(colors=64, method=Image.Quantize.FASTOCTREE) for im in frames]
    converted[0].save(
        path, save_all=True, append_images=converted[1:], duration=duration,
        loop=0, optimize=True, disposal=2,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar-json", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "assets")
    args = parser.parse_args()
    calendar = json.loads(args.calendar_json.read_text()) if args.calendar_json else calendar_from_github()
    if "data" in calendar:
        calendar = calendar["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    save_gif([hero_frame(i) for i in range(26)], args.output_dir / "matrix-hero.gif", 100)
    save_gif([contribution_frame(calendar, i) for i in range(30)], args.output_dir / "contributions.gif", 95)
    print(f"Rendered {calendar['totalContributions']} real contributions")


if __name__ == "__main__":
    main()
