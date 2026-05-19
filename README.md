# Growisto Internal Linking — Claude Code Plugin

Crawls a domain to find internal linking opportunities — places where blog posts or category-page footers mention commercial keywords without linking to the right landing page.

This plugin is a Claude Code conversion of the Internal Linking tool in the [Growisto SEO AI Suite](https://github.com/joethiradithya-lgtm/growisto-seo-ai-suite). The original is a Flask web app; this plugin lets teammates invoke the same logic by talking to Claude.

## What it does

Given a domain URL (and optionally a specific target page or keyword), the plugin:

1. **Discovers category pages** from the homepage navigation
2. **Discovers blog URLs** from the sitemap (WordPress / Shopify / generic auto-detected)
3. **Builds a keyword → URL map** by extracting keywords from each commercial page's title/H1/breadcrumb/H2/slug
4. **Scans blog body text** for un-linked mentions of those keywords (max 2 recommendations per blog)
5. **Scans category-page footer SEO blocks** for un-linked mentions (max 2 per category)
6. **Outputs a CSV** with columns: `Opportunity Page URL`, `Anchor Text`, `Location on Page`, `Target URL`

The Claude skill workflow ties these phases together and reports the highest-confidence recommendations at the end.

## Install

### Option A — From this GitHub repo
```bash
claude plugins install growisto-internal-linking \
  --git https://github.com/joethiradithya-lgtm/growisto-internal-linking
```

### Option B — Org-wide (after pilot phase)
```bash
claude plugins install growisto-internal-linking --marketplace growisto-seo
```

## Use

In Claude Code, just say:
> find internal linking opportunities for nike.com

or more specifically:
> what blog posts on livguard.com mention car batteries but don't link to /automotive-batteries/car-batteries/

Claude will:
1. Run `scripts/internal_linking_finder.py` with the right flags
2. Stream the progress per phase (category discovery → blog discovery → keyword map → blog scan → footer scan)
3. Hand you the path to the finished CSV

## Requirements

Python 3.9+ with:
- `requests>=2.31.0`
- `beautifulsoup4>=4.12.0`
- `lxml>=5.0.0`

Install via:
```bash
pip install -r requirements.txt
```

## CLI usage (without Claude)

The script also runs standalone:

```bash
# Full site scan
python3 scripts/internal_linking_finder.py https://www.livguard.com

# Limit blog posts crawled (faster test runs)
python3 scripts/internal_linking_finder.py https://www.livguard.com --max-blogs 5

# Single target — find pages that should link to /automotive-batteries/car-batteries/
python3 scripts/internal_linking_finder.py https://www.livguard.com \
    --target https://www.livguard.com/automotive-batteries/car-batteries/

# Single target + specific keyword
python3 scripts/internal_linking_finder.py https://www.livguard.com \
    --target https://www.livguard.com/automotive-batteries/car-batteries/ \
    --keyword "car batteries"

# Adjust crawl politeness (default 1.0 s between requests)
python3 scripts/internal_linking_finder.py https://www.livguard.com --delay 2.0

# Custom output path (default: <plugin>/output/{domain}-internal-linking-{date}.csv)
python3 scripts/internal_linking_finder.py https://www.livguard.com \
    --output /Users/joe/Downloads/livguard-links.csv
```

## Output format

CSV with these columns:

| Opportunity Page URL | Anchor Text | Location on Page | Target URL |
|---|---|---|---|
| https://livguard.com/blog/best-car-batteries | car batteries | Blog Body | https://livguard.com/automotive-batteries/car-batteries/ |
| https://livguard.com/blog/battery-maintenance-tips | car battery | Blog Body | https://livguard.com/automotive-batteries/car-batteries/ |
| https://livguard.com/automotive-batteries/ | car batteries | Footer Content | https://livguard.com/automotive-batteries/car-batteries/ |

Max 2 rows per source page (so a single blog can't be flagged 10 times for one target).

## How it differs from the Render web tool

| | Render web tool | This plugin |
|---|---|---|
| Trigger | Open URL in browser, fill form | Say "find internal linking opportunities for X" |
| Output delivery | Browser CSV download | CSV file on disk |
| Sub-skills exposed | No | Yes — Claude can run individual phases (`/discover-pages`, `/map-commercial`, etc.) |
| Deployment | Render.com | Runs locally on teammate's machine |
| API keys | None | None |

## Sub-skills

This plugin ships with 6 SKILL.md files. The main one is `analyze-domain` (full workflow). The other 5 are phase-specific and can be invoked individually if you want to inspect intermediate output:

- `analyze-domain` — orchestrator, runs the full 5-phase workflow
- `discover-pages` — phase 1: crawl + classify all pages
- `map-commercial` — phase 2: extract keywords from category/product pages
- `analyze-blogs` — phase 3: scan blog content for un-linked keyword mentions
- `analyze-footers` — phase 4: scan footer SEO blocks
- `generate-report` — phase 5: dedupe, filter, score, export CSV

## Related

This is **plugin 2 of 9** being converted from the Growisto SEO AI Suite. Pilot was the Keyword Classifier ([growisto-keyword-classifier](https://github.com/joethiradithya-lgtm/growisto-keyword-classifier)). Once all 9 ship, they'll be published to the Growisto org marketplace.
