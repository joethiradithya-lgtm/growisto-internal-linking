---
name: generate-report
description: Score, deduplicate, filter, and export internal linking recommendations as a CSV to the Outputs/ folder. Final phase of internal linking analysis.
when_to_use: Use after /analyze-blogs and /analyze-footers have produced raw opportunity lists. Combines, scores, filters, and exports the final deliverable.
argument-hint: [domain-name]
---

# Generate Internal Linking Report

Combine all raw opportunities, apply quality filters, score and rank, then export as CSV.

## Inputs

From conversation context:
- Raw blog opportunities (from `/analyze-blogs`)
- Raw footer opportunities (from `/analyze-footers`)
- Keyword-to-URL target map (from `/map-commercial`)
- User preferences (region, max links per page) from `/analyze-domain`

## Workflow

### 1. Merge all opportunities

Combine blog opportunities and footer opportunities into a single list.

### 2. Deduplicate

Remove duplicates where:
- Same source URL + same target URL (keep the one with the longer/more specific anchor text)
- Same anchor text + same target URL from different source pages (keep all — these are valid separate opportunities on different pages)

### 3. Filter weak suggestions

Remove opportunities that match ANY of these criteria:

| Filter | Rule |
|--------|------|
| **Too-short anchor** | Anchor text is fewer than 2 words (unless it is a specific product/brand name) |
| **Stop-word anchor** | Anchor text is entirely common words: "the best", "click here", "read more", "learn more", "this product" |
| **Self-link** | Source URL equals target URL |
| **Already linked** | Source page already has a link to the target URL (detected during analysis) |
| **Low confidence** | The keyword context suggests the match is coincidental, not topically relevant |
| **Duplicate anchor** | Same page already recommends a link to the same target (keep the better anchor) |

### 4. Enforce per-page cap

For each source page, keep only the top **2** recommendations (or the user-specified cap). Selection criteria:
1. Higher-specificity anchor text (longer, more descriptive phrases win)
2. Target pages with fewer existing internal links (these benefit more)
3. Blog body matches over footer content matches (body links carry more context)

### 5. Score and rank

Assign a confidence tier to each remaining opportunity:

| Tier | Criteria | Label |
|------|----------|-------|
| **High** | 3+ word anchor, exact keyword match, topically relevant context sentence | High confidence |
| **Medium** | 2-word anchor, close variant match, reasonable context | Medium confidence |
| **Low** | Short anchor, partial match, or ambiguous context | Low confidence |

Remove all "Low confidence" opportunities from the final output.

Sort the final list by:
1. Confidence tier (High first)
2. Source type (Blog before Footer)
3. Alphabetical by source URL (for consistency)

### 6. Export CSV

Save to: `Outputs/{domain}-internal-linking-{YYYY-MM-DD}.csv`

CSV columns:

```csv
Opportunity Page URL,Anchor Text,Location on Page,Target URL
```

| Column | Description | Example |
|--------|-------------|---------|
| Opportunity Page URL | The page where the link should be added | `https://example.com/blog/battery-guide/` |
| Anchor Text | The keyword phrase to hyperlink | `inverter batteries` |
| Location on Page | Where the anchor text appears | `Body` or `Footer Content` |
| Target URL | The commercial page to link to | `https://example.com/inverter-batteries/` |

Use the `Write` tool to save the CSV file. Ensure:
- UTF-8 encoding
- Proper CSV escaping (quote fields containing commas)
- No trailing whitespace in URLs
- No blank rows

### 7. Present summary

After saving, display to the user:

```
REPORT SAVED: Outputs/{filename}.csv

Total recommendations: {count}
  Blog opportunities: {count}
  Footer opportunities: {count}

High confidence: {count}
Medium confidence: {count}

Top source pages (most opportunities):
  1. {url} — {count} recommendations
  2. {url} — {count} recommendations

Top target pages (most recommended):
  1. {url} — {count} incoming link suggestions
  2. {url} — {count} incoming link suggestions
```

## Guardrails

- Maximum 2 recommendations per source page (unless user specified otherwise)
- Never include "Low confidence" matches in the final CSV
- Never include self-links
- CSV must be saved to `Outputs/` — never save to any other location
- If the final filtered list has 0 recommendations, save an empty CSV with headers only and explain why no opportunities were found
- Column order must be exactly: Opportunity Page URL, Anchor Text, Location on Page, Target URL

## Non-Goals

- This skill does NOT re-analyze page content — it works from the opportunity data already in context
- This skill does NOT add keyword volume or traffic data unless Ahrefs MCP tools were used in earlier phases
- This skill does NOT modify any website pages — it only produces recommendations
