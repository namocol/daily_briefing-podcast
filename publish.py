#!/usr/bin/env python3
"""Add an episode to the Daily Briefing feed and rebuild feed.xml.

Usage: python3 publish.py <episode.mp3> <YYYY-MM-DD> "<title>" "<short description>"
Copies the MP3 into episodes/, records it in episodes.json, drops episodes
older than KEEP_DAYS, and regenerates feed.xml.
"""
import json, os, shutil, subprocess, sys, datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape

BASE_URL = "https://namocol.github.io/daily_briefing-podcast"
KEEP_DAYS = 30
ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "episodes.json")


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return int(float(out.strip() or 0))


def main(src, date, title, desc):
    fname = f"daily-briefing-{date}.mp3"
    dest = os.path.join(ROOT, "episodes", fname)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(src, dest)
    eps = json.load(open(DB)) if os.path.exists(DB) else []
    eps = [e for e in eps if e["date"] != date]
    eps.append({"date": date, "title": title, "description": desc, "file": fname,
                "bytes": os.path.getsize(dest), "seconds": duration(dest)})
    cutoff = (datetime.date.fromisoformat(date) - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    for e in [e for e in eps if e["date"] < cutoff]:
        p = os.path.join(ROOT, "episodes", e["file"])
        if os.path.exists(p):
            os.remove(p)
    eps = sorted([e for e in eps if e["date"] >= cutoff], key=lambda e: e["date"], reverse=True)
    json.dump(eps, open(DB, "w"), indent=2)

    items = []
    for e in eps:
        d = datetime.date.fromisoformat(e["date"])
        pub = format_datetime(datetime.datetime(d.year, d.month, d.day, 11, 30, tzinfo=datetime.timezone.utc))
        m, s = divmod(e["seconds"], 60)
        items.append(f"""    <item>
      <title>{escape(e['title'])}</title>
      <description>{escape(e['description'])}</description>
      <enclosure url="{BASE_URL}/episodes/{e['file']}" length="{e['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">daily-briefing-{e['date']}</guid>
      <pubDate>{pub}</pubDate>
      <itunes:duration>{m}:{s:02d}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Daily Briefing</title>
    <link>{BASE_URL}/</link>
    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>Chad's weekday morning briefing: Fort Worth weather and news, headlines, markets, Microsoft 365 and Entra, threats and CVEs, and AI.</description>
    <language>en-us</language>
    <itunes:author>Claude</itunes:author>
    <itunes:image href="{BASE_URL}/cover.jpg"/>
    <itunes:category text="News"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:block>Yes</itunes:block>
{chr(10).join(items)}
  </channel>
</rss>
"""
    open(os.path.join(ROOT, "feed.xml"), "w").write(feed)
    print(f"Published {fname}; feed has {len(eps)} episode(s).")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
