---
name: analyze-domain
description: Run a full internal linking opportunity analysis for a website. Discovers pages, maps commercial keywords, scans blogs and footers, and outputs a CSV of linking recommendations.
when_to_use: Use when the user provides a domain URL and wants to find internal linking opportunities. This is the main entry point — it orchestrates all other skills in sequence.
argument-hint: [domain-url]
---

# Full Internal Linking Analysis

Run a complete internal linking opportunity analysis for **$ARGUMENTS**.

## Step 1 — Clarifying Questions

Before doing any work, ask the user:

1. **Target region** — Which country/market should keyword context reflect? (Default: India)
2. **Priority categories** — Any specific product categories or pages to prioritize? (Default: all)
3. **Exclusions** — Any URL patterns or sections to skip? (Default: none)
4. **Max links per page** — How many new internal links per source page? (Default: 2)

Wait for answers before proceeding.

## Step 2 — Share the Plan

Present a brief numbered plan to the user showing the phases you will execute:

1. Discover and classify all pages on the site
2. Map commercial pages (categories, products) and extract target keywords
3. Scan blog posts for unlinked keyword opportunities
4. Scan category page footer/SEO content for cross-linking opportunities
5. Score, filter, and deduplicate all matches
6. Export final recommendations as CSV to `output/`

Wait for user confirmation before executing.

## Step 3 — Execute Phases

Run each phase in sequence. Use the corresponding skill for each:

| Phase | Skill | What It Does |
|-------|-------|--------------|
| Discovery | `/discover-pages` | Crawl sitemaps and homepage, classify URLs |
| Commercial mapping | `/map-commercial` | Extract keywords from category/product pages |
| Blog analysis | `/analyze-blogs` | Scan blog content for unlinked keywords |
| Footer analysis | `/analyze-footers` | Scan category footer text for cross-links |
| Report generation | `/generate-report` | Score, filter, export CSV |

After each phase, briefly report what was found before moving to the next.

## Step 4 — Summary

After generating the report, present:
- Total opportunities found
- Breakdown: blog opportunities vs footer opportunities
- Top 5 highest-confidence recommendations
- Path to the saved CSV file

## Guardrails

- Never skip the clarifying questions in Step 1
- Never skip the plan confirmation in Step 2
- If a phase finds 0 results, report it and continue — do not silently skip
- If WebFetch fails for a page, log it and continue with other pages
- All output must be saved to the `output/` folder
