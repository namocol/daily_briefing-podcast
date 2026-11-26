#!/usr/bin/env python3
"""Add an episode to the Daily Briefing feed and rebuild feed.xml.

Usage:
  python3 publish.py <episode.mp3> <YYYY-MM-DD> "<title>" "<short description>" [--vtt FILE.vtt] [--notes FILE.md]

Copies the MP3 (and the optional transcript and notes) into episodes/, records
it in episodes.json, drops episodes older than KEEP_DAYS, and regenerates
feed.xml.
  --vtt    WebVTT transcript, linked with <podcast:transcript> (Apple Podcasts
           and other apps show it alongside the episode)
  --notes  Markdown script + "## Sources" section; becomes a transcript web page
           and the episode's show notes, with clickable source links
"""
import argparse, html, json, os, re, shutil, subprocess, sys, datetime
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


def _inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)


def md_to_html(md):
    """Minimal Markdown for the notes file: headings, bullet lists, rules, paragraphs, links."""
    out, in_list = [], False
    for block in re.split(r"\n\s*\n", md.strip()):
        for line in block.splitlines():
            line = line.rstrip()
            if line.startswith("- "):
                if not in_list:
                    out.append("<ul>"); in_list = True
                out.append(f"<li>{_inline(line[2:])}</li>")
                continue
            if in_list:
                out.append("</ul>"); in_list = False
            if not line:
                continue
            h = re.match(r"(#{1,3}) (.*)", line)
            if h:
                n = len(h.group(1))
                out.append(f"<h{n}>{_inline(h.group(2))}</h{n}>")
            elif line.strip() == "---":
                out.append("<hr>")
            else:
                out.append(f"<p>{_inline(line)}</p>")
        if in_list:
            out.append("</ul>"); in_list = False
    return "\n".join(out)


def sources_html(md):
    m = re.search(r"^## Sources\s*$(.*)", md, re.M | re.S)
    return md_to_html(m.group(1)) if m else ""


def main(src, date, title, desc, vtt=None, notes=None):
    fname = f"daily-briefing-{date}.mp3"
    dest = os.path.join(ROOT, "episodes", fname)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(src, dest)
    eps = json.load(open(DB)) if os.path.exists(DB) else []
    eps = [e for e in eps if e["date"] != date]
    ep = {"date": date, "title": title, "description": desc, "file": fname,
          "bytes": os.path.getsize(dest), "seconds": duration(dest)}
    if vtt:
        ep["vtt"] = f"daily-briefing-{date}.vtt"
        shutil.copyfile(vtt, os.path.join(ROOT, "episodes", ep["vtt"]))
    if notes:
        md = open(notes).read()
        ep["page"] = f"daily-briefing-{date}.html"
        ep["sources_html"] = sources_html(md)
        page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>body{{font:17px/1.6 -apple-system,system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
a{{color:#0b5cad}}h1{{font-size:1.5rem;line-height:1.3}}audio{{width:100%;margin:1rem 0}}
@media (prefers-color-scheme: dark){{body{{background:#111;color:#e8e8e8}}a{{color:#6fb3ff}}}}</style></head>
<body><audio controls preload="none" src="{fname}"></audio>
{md_to_html(md)}
</body></html>
"""
        open(os.path.join(ROOT, "episodes", ep["page"]), "w").write(page)
    eps.append(ep)
    cutoff = (datetime.date.fromisoformat(date) - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    for e in [e for e in eps if e["date"] < cutoff]:
        for key in ("file", "vtt", "page"):
            old = os.path.join(ROOT, "episodes", e.get(key) or "")
            if e.get(key) and os.path.exists(old):
                os.remove(old)
    eps = sorted([e for e in eps if e["date"] >= cutoff], key=lambda e: e["date"], reverse=True)
    json.dump(eps, open(DB, "w"), indent=2)

    items = []
    for e in eps:
        d = datetime.date.fromisoformat(e["date"])
        pub = format_datetime(datetime.datetime(d.year, d.month, d.day, 11, 30, tzinfo=datetime.timezone.utc))
        m, s = divmod(e["seconds"], 60)
        notes = f"<p>{html.escape(e['description'])}</p>"
        extra = ""
        if e.get("page"):
            notes += f'<p><a href="{BASE_URL}/episodes/{e["page"]}">Read the full transcript</a></p>'
            extra += f"\n      <link>{BASE_URL}/episodes/{e['page']}</link>"
        if e.get("sources_html"):
            notes += "<h3>Sources</h3>" + e["sources_html"]
        if e.get("vtt"):
            extra += (f'\n      <podcast:transcript url="{BASE_URL}/episodes/{e["vtt"]}" '
                      f'type="text/vtt" language="en-us"/>')
        items.append(f"""    <item>
      <title>{escape(e['title'])}</title>
      <description>{escape(e['description'])}</description>
      <content:encoded><![CDATA[{notes.replace("]]>", "]]&gt;")}]]></content:encoded>{extra}
      <enclosure url="{BASE_URL}/episodes/{e['file']}" length="{e['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">daily-briefing-{e['date']}</guid>
      <pubDate>{pub}</pubDate>
      <itunes:duration>{m}:{s:02d}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:podcast="https://podcastindex.org/namespace/1.0">
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
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("mp3"); ap.add_argument("date"); ap.add_argument("title"); ap.add_argument("description")
    ap.add_argument("--vtt"); ap.add_argument("--notes")
    a = ap.parse_args()
    main(a.mp3, a.date, a.title, a.description, a.vtt, a.notes)
