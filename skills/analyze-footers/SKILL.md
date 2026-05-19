---
name: analyze-footers
description: Scan category page footer and SEO text content for cross-linking opportunities to other commercial pages. Finds keywords in footer description blocks.
when_to_use: Use after /map-commercial has produced the keyword-to-URL map. Scans footer SEO text on category pages for linking opportunities to other categories or products.
---

# Category Footer Opportunity Analysis

Scan the footer SEO text content on category pages for keywords that could link to OTHER commercial pages on the same site.

## Context

Many e-commerce and product sites include a block of SEO text at the bottom of category pages — below the product grid. This text often mentions related product types, use cases, or categories. These mentions are opportunities to add internal links to the relevant commercial pages.

## Inputs

From conversation context:
- Category page URLs (from `/discover-pages`)
- Keyword-to-URL target map (from `/map-commercial`)

## Workflow

### 1. Identify category pages with footer content

Not all category pages have SEO text blocks. Prioritize:
1. Top-level category pages (e.g., `/automotive-batteries/`, `/solar-solutions/`)
2. Sub-category pages with long footer descriptions
3. Any category page visible in the main navigation

Select up to 15 category pages for analysis.

### 2. Fetch footer content

For each category page, use `WebFetch` with this prompt:

> "From this category/collection page, extract: (1) Any SEO text block or descriptive content that appears BELOW the product listings — this is typically a content block with paragraphs of text about the category. It may be at the very bottom of the page before the site footer. (2) Any sidebar descriptive text. (3) All existing internal links in these content areas — list each as 'anchor text → destination URL'. Then check if any of the following keywords appear in this footer/description text: [{KEYWORD_LIST}]. For each match, report: exact text, and whether it is already hyperlinked."

Replace `{KEYWORD_LIST}` with keywords from the target map, EXCLUDING keywords that point back to the page being analyzed (no self-links).

### 3. Distinguish footer content from site-wide footer

Important distinction:
- **Category footer content** = the SEO text block specific to that category page (the analysis target)
- **Site-wide footer** = the navigation footer that appears on every page (NOT an analysis target)

Only analyze the category-specific SEO text. Ignore:
- The global site footer (navigation links, copyright, social media)
- Header/navigation content
- Product card titles within the grid
- Breadcrumb navigation

### 4. Record raw opportunities

For each unlinked keyword match, record:

| Field | Value |
|-------|-------|
| **Opportunity Page URL** | The category page URL |
| **Anchor Text** | The exact keyword text found in the footer content |
| **Location on Page** | "Footer Content" |
| **Target URL** | The other commercial page URL from the keyword map |
| **Context** | The surrounding sentence |

### 5. Inline quality check

Discard a match if:
- The keyword points back to the same page (self-link)
- The keyword is already hyperlinked to the target URL
- The keyword is already hyperlinked to a different URL (don't double-link)
- The match is in the site-wide footer, not the category-specific SEO block
- The keyword context is irrelevant (e.g., a generic mention, not a recommendation or description)

### 6. Per-page cap

Maximum **2 link recommendations per category page**. If more are found, keep the strongest:
1. Prefer cross-category links (e.g., "solar batteries" on the automotive batteries page → /solar-solutions/solar-batteries/)
2. Prefer keywords with higher specificity
3. Prefer targets with fewer existing internal links

## Output

A list of raw footer opportunities:

```
FOOTER OPPORTUNITIES ({count}):

1. Category: {category_url}
   Anchor: "{keyword}"
   Target: {target_url}
   Context: "...sentence where keyword appears..."

2. ...
```

Retain this list in conversation context for the report generation phase.

## Guardrails

- Maximum **2 link recommendations per category page**
- Only analyze the category-specific SEO/description text, never the site-wide footer
- Never recommend self-links
- If a category page has no footer/SEO text (just a product grid and nothing else), skip it and report: "No footer content found on {url}"
- Some pages may load footer content via JavaScript — if WebFetch returns empty or very short content for a page that should have it, note this limitation
- Maintain a polite delay between requests (~1-2 seconds)
