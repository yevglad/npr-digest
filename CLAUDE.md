# NPR Digest — project brief

A personal "what did I miss on NPR" page. A GitHub Actions job fetches NPR's public RSS feeds a few times a day, tags each segment by topic with a one-line summary (Claude API), and publishes one static page to GitHub Pages. The owner reads it on their phone, picks a segment, and listens.

## Status at handoff

A working prototype already exists, built by hand. The page design is settled; what's missing is the automation.

- `templates/index.html` is the finished page design: days → shows → segments, topic bars that filter, show chips, search, and Listen / On NPR links. Treat its look and behaviour as the spec. Don't redesign it unless asked.
- `sample/digest.json` holds real data for Nov 18–19, 2026: 38 segments from 12 shows, already summarized and tagged. Use it to test the page without touching the network.
- `scripts/` has first-pass, lightly tested versions of each step. Feed parsing, keyword fallback and the page build were run against test data. **Live fetching from NPR has not been run yet**, because the environment that wrote these scripts couldn't reach npr.org.

## Architecture

```
feeds.json ─► scripts/fetch_feeds.py ─► data/segments.json  (committed; window_days + 1)
                                             │
                    scripts/summarize.py ◄───┘  adds summary + topics to new items only
                                             │
                    scripts/build_page.py ───► site/index.html  (last window_days days, ET; 7 by default)
                                             │
              .github/workflows/daily.yml ───► GitHub Pages
```

- **Accumulating store.** The Morning Edition and All Things Considered feeds only keep their latest ~10 segments, so a single daily fetch misses most of the show. The workflow runs 3× a day and `data/segments.json` keeps every item seen, keyed by guid, pruned one day after the page window (`window_days` in `feeds.json`).
- **No transcripts in the repo.** Transcripts are fetched only as input for tagging. `summarize.py` sets every `transcript` to `null` before saving, because `data/segments.json` is committed to a public repo. The `null` key tells `fetch_feeds.py` the page was already fetched.
- **Idempotent tagging.** `summarize.py` only processes items without a `summary`, so reruns are cheap.
- **Graceful degradation.** With no `ANTHROPIC_API_KEY`, tagging falls back to keyword rules and the first sentence of the feed description, so the site still builds.
- **Data injection.** `build_page.py` replaces the literal `/*__DATA__*/null` in the template with a JSON payload `{generated, topics, shows, segments}`. Escape `</` (already done).

## Tasks, in order

1. **Local smoke test.** Run `python scripts/build_page.py sample/digest.json`, open `site/index.html`, and confirm 2 days and 38 segments render and the filters work.
2. **Live fetch.** Run `python scripts/fetch_feeds.py` and confirm all 12 feeds parse. Fix any feed whose shape differs: enclosure missing, odd dates, CDATA.
3. **Transcripts.** `fetch_transcript()` guesses at `https://www.npr.org/transcripts/<story_id>` and a `div.transcript` selector. Check both against a real page and fix the parser. Many podcast-only episodes have no transcript; that's fine.
4. **Claude tagging.** With a key set, run `summarize.py` on a fresh store. Check that summaries are original one-liners (no copied NPR text) and that topics come only from `feeds.json`. Keep the model configurable via the `DIGEST_MODEL` env var.
5. **GitHub setup.** Create the repo, add the `ANTHROPIC_API_KEY` secret, set Pages → Source = GitHub Actions, and trigger `workflow_dispatch` once. Confirm the Pages URL loads on a phone.
6. **Hardening.** Handle a feed that times out (already isolated per feed), a push race between overlapping runs (concurrency group is set), and an empty window (the page shows an empty state).

## Nice-to-haves (only if the owner asks)

- Split long magazine segments, such as Morning news brief, into sub-topics using transcripts.
- A "listened" checkmark per segment (localStorage only; it's a static page).
- A daily email or push notification with the top 5 segments.
- Let the owner edit `feeds.json` from the GitHub mobile app to add or remove shows. That already works; just document it.

## Constraints

- Python stdlib, plus `anthropic` for tagging. No frontend build step: the page is one self-contained HTML file.
- Be a polite client. Send a User-Agent, limit to 3 runs/day, and fetch transcripts only for new items.
- Don't reproduce NPR article text on the page. Use titles, our own short summaries, and links back to NPR and its audio.
- Keep the repo public (free Pages). It only contains public feed data. A private repo needs a paid GitHub plan for Pages.

## Commands

```bash
python scripts/build_page.py sample/digest.json   # offline preview
python scripts/fetch_feeds.py --transcripts        # live fetch into data/
ANTHROPIC_API_KEY=... python scripts/summarize.py  # tag new items
python scripts/build_page.py                        # build from data/
open site/index.html
```
