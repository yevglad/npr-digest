#!/usr/bin/env python3
"""Render site/index.html from templates/index.html and data/segments.json.

Usage:
  python scripts/build_page.py                 # from data/segments.json
  python scripts/build_page.py sample/digest.json   # from the handoff sample
"""
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, dict) and "segments" in raw:          # sample format
        return raw["segments"], raw.get("generated")
    return list(raw.values()), None                           # store format


def main():
    cfg = json.loads((ROOT / "feeds.json").read_text())
    src = sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "segments.json"
    segs, generated = load(src)
    now = datetime.now(timezone.utc)
    if generated is None:
        # Whole calendar days in the show's timezone (today + yesterday by
        # default), so the page never opens with a half day at the bottom.
        tz = ZoneInfo(cfg.get("timezone", "America/New_York"))
        first_day = now.astimezone(tz).date() - timedelta(days=cfg.get("window_days", 2) - 1)
        segs = [s for s in segs
                if datetime.fromisoformat(s["date"].replace("Z", "+00:00")).astimezone(tz).date() >= first_day]
        generated = now.isoformat(timespec="seconds").replace("+00:00", "Z")

    data = [{k: s.get(k) for k in ("show", "date", "page", "audio", "secs", "title", "summary", "topics")}
            for s in segs]
    payload = {"generated": generated, "topics": cfg["topics"],
               "shows": [s["name"] for s in cfg["shows"]], "segments": data}

    tpl = (ROOT / "templates" / "index.html").read_text()
    # </ is escaped so a title can never close the script tag
    js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    out = ROOT / "site" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(tpl.replace("/*__DATA__*/null", js))
    print(f"wrote {out} with {len(data)} segments")


if __name__ == "__main__":
    main()
