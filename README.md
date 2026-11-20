# NPR Digest

A daily page showing what NPR covered over the last seven days, grouped by date, show and topic, with links to listen. It's rebuilt automatically by GitHub Actions, so there's nothing to keep running.

## Setup (about 10 minutes)

1. Create a **public** GitHub repo and push this folder to it.
2. **Settings → Secrets and variables → Actions → New repository secret.** Name it `ANTHROPIC_API_KEY` and paste your key from console.anthropic.com. This step is optional: without a key, topics come from keyword rules.
3. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
4. **Actions → Daily NPR digest → Run workflow.** When it finishes, the page is at `https://<your-username>.github.io/<repo-name>/`.
5. Bookmark that URL on your phone, or add it to your home screen.

After that, it runs at about 10am, 3pm and 8pm Eastern. To refresh early, open the GitHub mobile app → the repo → Actions → Run workflow.

## Changing shows

Edit `feeds.json`: add or remove entries under `shows`. NPR podcast feeds follow the pattern `https://feeds.npr.org/<id>/podcast.xml`.

## Cost

Tagging uses a small Claude model and only processes new segments: roughly 60–100 short requests a day, typically a few cents. GitHub Actions and Pages are free for public repos.

## Working on it

See `CLAUDE.md` for the architecture and the open tasks. `python scripts/build_page.py sample/digest.json` builds an offline preview from the included sample data.
