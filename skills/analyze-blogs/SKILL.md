---
name: analyze-blogs
description: Scan blog post content to find unlinked keywords that match commercial page targets. Produces raw internal linking opportunities from blog body text.
when_to_use: Use after /map-commercial has produced the keyword-to-URL map. Scans blog content to find natural anchor text opportunities.
---

# Blog Content Opportunity Analysis

Scan blog posts for keywords from the target map that are NOT already linked to the corresponding commercial pages.

## Inputs

From conversation context:
- Blog page URLs (from `/discover-pages`)
- Keyword-to-URL target map (from `/map-commercial`)

## Workflow

### 1. Prioritize which blogs to fetch

If there are more than 30 blog posts, prioritize by:
1. **Topical relevance** — blog title or URL slug overlaps with a target keyword category (e.g., a blog about "how to choose a car battery" is relevant to the "car batteries" target)
2. **Recency** — newer posts are more valuable (check sitemap `<lastmod>` dates if available)
3. **Content length** — longer posts have more keyword opportunities

Select the top 30 blog posts for analysis. If fewer than 30 exist, analyze all.

### 2. Fetch each blog post

For each blog URL, use `WebFetch` with this prompt:

> "From this blog post, extract: (1) The article title. (2) The full body text of the article, preserving paragraph structure. (3) All existing internal links — list each as 'anchor text → destination URL'. Then check if any of the following keywords or close variations appear in the body text: [{KEYWORD_LIST}]. For each match found, report: the exact matched text, the surrounding sentence for context, and whether that text is already hyperlinked. Only report matches that are NOT already hyperlinked."

Replace `{KEYWORD_LIST}` with relevant keywords from the target map. To keep the prompt manageable:
- Group keywords by category (e.g., all battery keywords together, all solar keywords together)
- For blog posts with a clear topic (identifiable from URL/title), only pass the relevant keyword group
- For general blogs, pass the top 20 highest-priority keywords

### 3. Record raw opportunities

For each unlinked keyword match, record:

| Field | Value |
|-------|-------|
| **Opportunity Page URL** | The blog post URL |
| **Anchor Text** | The exact keyword text found in the content |
| **Location on Page** | "Body" (all blog matches are body content) |
| **Target URL** | The commercial page URL from the keyword map |
| **Context** | The surrounding sentence (for confidence assessment) |

### 4. Inline quality check

Discard a match immediately if:
- The keyword appears only in a navigation menu, sidebar, or comment section (not the article body)
- The keyword is part of a proper noun or brand name that doesn't refer to the target page
- The match is a partial word collision (e.g., "car" matching inside "careful")
- The blog post is already linking to the same target URL with different anchor text
- The keyword appears in a context that is clearly unrelated to the target page (e.g., "batteries" in "batteries of tests")

### 5. Per-page cap

If a single blog post has more than 2 valid opportunities, keep only the 2 strongest:
1. Prefer longer, more specific keyword phrases over shorter generic ones
2. Prefer keywords that appear naturally in a descriptive sentence over keywords in a list or heading
3. Prefer keywords whose target page has fewer existing internal links

## Output

A list of raw blog opportunities:

```
BLOG OPPORTUNITIES ({count}):

1. Blog: {blog_url}
   Anchor: "{keyword}"
   Target: {target_url}
   Context: "...sentence where keyword appears..."

2. ...
```

Retain this list in conversation context for the report generation phase.

## Guardrails

- Maximum **2 link recommendations per blog post**
- Never recommend linking a keyword that is already hyperlinked (to any destination)
- Never recommend a link from a page to itself
- Do not match single-word keywords unless they are highly specific product names (e.g., brand-specific terms)
- If WebFetch returns very sparse content for a page (under 100 words of body text), skip it — it may be JavaScript-rendered; log the skip
- Maintain a polite delay between requests (~1-2 seconds)
- If the blog has a table of contents with anchor links, do not count those as existing internal links to commercial pages
