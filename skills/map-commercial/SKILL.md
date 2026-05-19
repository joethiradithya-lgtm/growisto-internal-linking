---
name: map-commercial
description: Extract keywords and metadata from category and product pages to build the target keyword map used for internal linking opportunity matching.
when_to_use: Use after /discover-pages has produced a classified URL inventory. Builds the keyword-to-URL mapping that subsequent analysis phases depend on.
---

# Commercial Page Mapping

Build a keyword-to-URL target map from the category and product pages identified during discovery.

## Inputs

Uses the classified URL inventory from `/discover-pages` (already in conversation context):
- All category page URLs
- All product page URLs

## Workflow

### 1. Fetch each commercial page

For each category and product page, use `WebFetch` to extract:

| Field | Where to Find | Priority |
|-------|---------------|----------|
| **Page title** | `<title>` tag, cleaned (strip site name after `|` or `-`) | Highest |
| **H1 heading** | First `<h1>` on the page | Highest |
| **URL slug keywords** | Path segments converted: hyphens to spaces (e.g., `/car-batteries/` to "car batteries") | High |
| **Breadcrumb trail** | Breadcrumb nav text (skip "Home") | High |
| **H2 headings** | Descriptive H2s only (skip generic ones like "Why Choose Us") | Medium |
| **Meta description** | `<meta name="description">` content | Medium |

Use this WebFetch prompt template:
> "From this page extract: (1) the page title, (2) the H1 heading, (3) all H2 headings, (4) the breadcrumb trail text, (5) the meta description, (6) a count of existing internal links on this page. List each field clearly."

### 2. Generate keyword candidates

For each page, produce keyword candidates from the extracted fields:

- **Full title/H1** as-is (e.g., "Inverter Batteries for Home")
- **URL slug phrases** (e.g., "inverter batteries", "car batteries")
- **2-3 word subphrases** from title/H1 (e.g., from "Best Inverter Batteries for Home" extract "inverter batteries")
- **Breadcrumb terms** (e.g., "Automotive Batteries" > "Car Batteries")
- **Descriptive H2s** that name a product type or feature

### 3. Clean and filter keywords

Remove candidates that are:
- Single common words (stop words: "best", "top", "buy", "online", "price", "shop", "home", "india")
- Shorter than 4 characters
- Generic headings: "products", "services", "about us", "contact", "features", "benefits"
- Duplicates of the domain or brand name alone

### 4. Build the keyword-to-URL map

Create a lookup table. If the same keyword maps to multiple pages, keep the one with the highest priority source (title > H1 > slug > breadcrumb > H2 > meta).

```
KEYWORD TARGET MAP ({count} keywords across {count} pages):

"car batteries" → /automotive-batteries/car-batteries/  [source: H1]
"inverter for home" → /inverter-and-batteries/inverter-for-home/  [source: title]
"solar panels" → /solar-solutions/solar-panels/  [source: slug]
...
```

### 5. Record existing internal link counts

For each commercial page, note how many internal links currently point to it (from the WebFetch extraction). This is used later for prioritization — pages with fewer existing internal links benefit more from new ones.

## Output

The keyword-to-URL map with:
- Keyword phrase
- Target URL
- Source field (title/H1/slug/breadcrumb/H2/meta)
- Existing internal link count for that target page

Retain this map in conversation context for the analysis phases.

## Guardrails

- Fetch pages with a polite delay (~1-2 seconds between requests)
- If a page returns a 404 or redirect, log it and skip — do not include dead pages as targets
- Do NOT include utility pages (about, contact, warranty) as targets
- If a site has more than 40 commercial pages, prioritize the top 30 by:
  1. Category pages before product pages (categories are higher-value link targets)
  2. Pages closer to the root (fewer path segments = more important)
  3. Pages visible in the main navigation
- Keep keyword candidates to a maximum of 10 per page to avoid noise
