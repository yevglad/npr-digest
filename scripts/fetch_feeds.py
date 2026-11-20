#!/usr/bin/env python3
"""Fetch NPR feeds and merge new items into data/segments.json.

Stdlib only. Keeps an accumulating store (so Morning Edition / ATC segments
that scroll off their 10-item feeds are not lost between runs), pruned to
the page window (`window_days` in feeds.json) plus one day.

Usage: python scripts/fetch_feeds.py [--transcripts]
"""
import json, re, sys, html, time, urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "segments.json"
UA = "npr-digest/1.0 (personal daily digest)"


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def secs_from(duration, audio_url):
    """<itunes:duration> is seconds or [HH:]MM:SS; fall back to the d= param
    NPR puts on podcast enclosure URLs."""
    d = (duration or "").strip()
    if re.fullmatch(r"\d+(?::\d{1,2}){0,2}", d):
        secs = 0
        for part in d.split(":"):
            secs = secs * 60 + int(part)
        if secs:
            return secs
    m = re.search(r"[?&]d=(\d+)", audio_url or "")
    return int(m.group(1)) if m else None


def story_id(link, audio_url=None):
    m = re.search(r"/(nx-s\d-\d+(?:-e\d+)?|\d{8,})/", link or "")
    if m:
        return m.group(1)
    # Some podcast items (e.g. Up First "Newsmakers") have no <link>, but the
    # enclosure URL carries the story id as e=nx-s1-...
    m = re.search(r"[?&]e=(nx-s\d-\d+(?:-e\d+)?)", audio_url or "")
    return m.group(1) if m else None


def parse_feed(show, xml_bytes):
    root = ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate"))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue  # undated item: can't place it on the page, skip it
        link = (it.findtext("link") or "").strip() or None
        enc = it.find("enclosure")
        audio = (enc.get("url") or "").strip() or None if enc is not None else None
        title = strip_tags(it.findtext("title"))
        guid = ((it.findtext("guid") or "").strip() or link or audio or title)
        if not guid:
            continue
        yield {
            "id": guid,
            "show": show,
            "date": pub.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "title": title,
            "description": strip_tags(it.findtext("description"))[:1200],
            "page": link,
            "audio": audio,
            "secs": secs_from(it.findtext(ITUNES + "duration"), audio),
            "story_id": story_id(link, audio),
        }


def fetch_transcript(sid):
    """Best effort. Returns (text or None, canonical story URL or None).

    Checked against live pages on 2026-11-19: the transcript sits in
    <div class="transcript storytext"> as runs of unclosed <p> tags, followed
    by <p class="disclaimer"> and the copyright notice. Pages without a transcript
    (common for new podcast episodes) have no such div.
    """
    try:
        page = get(f"https://www.npr.org/transcripts/{sid}").decode("utf-8", "ignore")
    except Exception:
        return None, None
    m = re.search(r'<link rel="canonical" href="([^"]+)"', page)
    canonical = m.group(1) if m and "/transcripts/" not in m.group(1) else None
    start = page.find('<div class="transcript storytext"')
    if start < 0:
        return None, canonical
    end = page.find('class="disclaimer"', start)
    end = page.rfind("<", start, end) if end > 0 else page.find("</div>", start)
    block = page[start:end]
    block = re.sub(r'<b class="icn-story-transcript-wrap">.*?</b>', " ", block, flags=re.S)
    text = strip_tags(block)
    return text[:20000] or None, canonical


def main():
    cfg = json.loads((ROOT / "feeds.json").read_text())
    store = json.loads(STORE.read_text()) if STORE.exists() else {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.get("window_days", 7) + 1)
    want_tx = "--transcripts" in sys.argv
    errors = []
    tx_fetched = 0

    for show in cfg["shows"]:
        try:
            items = list(parse_feed(show["name"], get(show["url"])))
        except Exception as e:  # one bad feed shouldn't sink the run
            errors.append(f"{show['name']}: {e}")
            continue
        for item in items:
            if datetime.fromisoformat(item["date"].replace("Z", "+00:00")) < cutoff:
                continue
            old = store.get(item["id"], {})
            item = {**old, **item}  # keep summary/topics/transcript from earlier runs
            if not item["page"] and old.get("page"):
                item["page"] = old["page"]  # canonical URL found on an earlier run
            # One attempt per item: being polite matters more than catching
            # transcripts that NPR posts a day later (tagging has run by then).
            if want_tx and item.get("story_id") and "transcript" not in item:
                text, canonical = fetch_transcript(item["story_id"])
                item["transcript"] = text
                item["page"] = item["page"] or canonical
                tx_fetched += 1
                time.sleep(0.5)
            store[item["id"]] = item

    store = {k: v for k, v in store.items()
             if datetime.fromisoformat(v["date"].replace("Z", "+00:00")) >= cutoff}
    STORE.parent.mkdir(exist_ok=True)
    STORE.write_text(json.dumps(store, indent=1, ensure_ascii=False))
    print(f"{len(store)} segments stored; {len(errors)} feed errors"
          + (f"; {tx_fetched} transcript pages fetched" if want_tx else ""))
    for e in errors:
        print("  !", e)
    if len(errors) == len(cfg["shows"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
