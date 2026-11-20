#!/usr/bin/env python3
"""Add a one-line summary and topic tags to segments that don't have them yet.

Uses the Claude API when ANTHROPIC_API_KEY is set; otherwise falls back to
keyword tagging and the feed description, so the site still builds.
Only new segments are sent, so a typical day is a few dozen short calls.
"""
import json, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "segments.json"
MODEL = os.environ.get("DIGEST_MODEL", "claude-haiku-5-5")

KEYWORDS = {
    "Politics": r"congress|senate|house|democrat|republican|election|speaker|trump|electoral|campaign",
    "World": r"china|russia|iran|ukraine|israel|gaza|myanmar|putin|xi |europe|africa|summit|international",
    "Tech & AI": r"\bai\b|artificial intelligence|anthropic|openai|nvidia|tech|outage|software|data center|cyber",
    "Economy": r"econom|ipo|market|stock|tax|inflation|jobs|manufactur|wealth|money|cost|investor",
    "Culture": r"film|movie|album|music|song|book|game|theater|concert|actor|singer|opera|tv",
    "Science & health": r"health|medical|disease|drug|therapy|science|climate|psychedel|vaccine|gene",
    "Justice": r"court|ruling|judge|execution|death penalty|police|prison|lawsuit|genocide",
}


def keyword_tags(text, topics):
    t = text.lower()
    tags = [k for k in topics if re.search(KEYWORDS.get(k, "$^"), t)]
    return tags[:3] or ["World"]


def first_sentence(s):
    m = re.match(r"(.{20,220}?[.!?])(\s|$)", s or "")
    return (m.group(1) if m else (s or "")[:200]).strip()


SYSTEM = (
    "You write entries for a personal digest of NPR radio and podcast segments. "
    "For each segment, write one plain sentence of at most 22 words saying what "
    "the segment covers, so a listener can decide whether to play it. Write it in "
    "your own words: do not copy or closely paraphrase any sentence from the "
    "title or description, and do not quote anyone. Then pick 1 to 3 "
    "topics from the allowed list, most relevant first."
)


def claude_tag(client, seg, topics):
    # Feed description only, never transcripts: NPR's terms restrict feeding
    # its content to AI systems, and the feed blurb is what NPR offers for reuse.
    body = seg.get("description") or ""
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "topics": {"type": "array", "items": {"type": "string", "enum": topics}},
        },
        "required": ["summary", "topics"],
        "additionalProperties": False,
    }
    msg = client.messages.create(
        model=MODEL,
        # Current models think by default and thinking counts toward max_tokens,
        # so leave room; low effort keeps a one-line task cheap.
        max_tokens=2048,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        system=SYSTEM,
        messages=[{"role": "user", "content":
                   f"Show: {seg['show']}\nTitle: {seg['title']}\n\nText:\n{body[:6000]}"}],
    )
    if msg.stop_reason != "end_turn":
        raise RuntimeError(f"stop_reason={msg.stop_reason}")
    data = json.loads(next(b.text for b in msg.content if b.type == "text"))
    data["topics"] = list(dict.fromkeys(t for t in data["topics"] if t in topics))[:3]
    if not data["summary"].strip():
        raise RuntimeError("empty summary")
    return data


def main():
    topics = json.loads((ROOT / "feeds.json").read_text())["topics"]
    store = json.loads(STORE.read_text())
    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
    # With a key, also redo items that got keyword tags on an earlier run
    # (no key yet, or an API error), so one bad run doesn't stick for a week.
    todo = [s for s in store.values()
            if not s.get("summary") or (client and s.get("tagged_by") != "claude")]

    n_claude = 0
    for seg in todo:
        try:
            if client is None:
                raise RuntimeError("no API key")
            out, by = claude_tag(client, seg, topics), "claude"
            n_claude += 1
        except Exception as e:
            if client:
                print(f"  fallback for {seg['title'][:50]}: {e}")
            if seg.get("summary"):
                continue  # keep the earlier keyword tags; retry next run
            out, by = {"summary": first_sentence(seg.get("description")),
                       "topics": keyword_tags(seg["title"] + " " + (seg.get("description") or ""), topics)}, "keywords"
        seg["summary"] = out["summary"]
        seg["topics"] = out["topics"] or ["World"]
        seg["tagged_by"] = by

    # The store is committed to a public repo, so keep no NPR text in it beyond
    # titles: descriptions (and any transcripts) are only input for tagging.
    # fetch_feeds.py re-reads descriptions from the feeds on every run, so a
    # segment awaiting a Claude retry still has its text while it's in the feed.
    stripped = 0
    for seg in store.values():
        for k in ("description", "transcript"):
            if seg.get(k):
                seg[k] = None
                stripped += 1

    STORE.write_text(json.dumps(store, indent=1, ensure_ascii=False))
    print(f"tagged {len(todo)} segments: {n_claude} by Claude ({MODEL}), "
          f"{len(todo) - n_claude} by keywords; removed {stripped} NPR text fields from the store")


if __name__ == "__main__":
    main()
